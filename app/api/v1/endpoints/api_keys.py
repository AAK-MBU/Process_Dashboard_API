"""API endpoints for managing API keys."""

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.dependencies import RequireAdminKey
from app.db.database import SessionDep
from app.models import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyPublic,
    ApiKeyWithSecret,
)

router = APIRouter()


@router.post(
    "/",
    response_model=ApiKeyWithSecret,
    status_code=201,
    summary="Create a new API key",
    description="Create a new API key for authentication. The key is only shown once!",
)
def create_api_key(
    *, session: SessionDep, api_key_in: ApiKeyCreate, admin_key: RequireAdminKey
) -> ApiKeyWithSecret:
    """Create a new API key."""

    # Generate the actual key
    key = ApiKey.generate_key()
    key_hash = ApiKey.hash_key(key)
    key_prefix = key[:8]

    # Create the database record
    api_key = ApiKey(
        **api_key_in.model_dump(),
        key_hash=key_hash,
        key_prefix=key_prefix,
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    # Return with the actual key (only time it's shown)
    return ApiKeyWithSecret(**api_key.model_dump(), key=key)


@router.get(
    "/",
    response_model=list[ApiKeyPublic],
    summary="List all API keys",
    description="List all API keys (without showing the actual keys)",
)
def list_api_keys(*, session: SessionDep, admin_key: RequireAdminKey) -> list[ApiKeyPublic]:
    """List all API keys."""
    statement = select(ApiKey)
    api_keys = session.exec(statement).all()
    return [ApiKeyPublic.model_validate(key) for key in api_keys]


@router.delete(
    "/{api_key_id}",
    summary="Delete an API key",
    description="Delete an API key by ID",
)
def delete_api_key(
    *, session: SessionDep, api_key_id: int, admin_key: RequireAdminKey
) -> dict[str, str]:
    """Delete an API key."""
    api_key = session.get(ApiKey, api_key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    session.delete(api_key)
    session.commit()

    return {"message": "API key deleted successfully"}


@router.patch(
    "/{api_key_id}/toggle",
    response_model=ApiKeyPublic,
    summary="Toggle API key active status",
    description="Enable or disable an API key",
)
def toggle_api_key(*, session: SessionDep, api_key_id: int, admin_key: RequireAdminKey) -> ApiKey:
    """Toggle API key active status."""
    api_key = session.get(ApiKey, api_key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = not api_key.is_active
    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    return api_key
