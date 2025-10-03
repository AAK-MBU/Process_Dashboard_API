"""API key authentication and verification endpoints."""

from fastapi import APIRouter

from app.auth import RequireApiKey

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get(
    "/verify",
    summary="Verify API Key",
    description="Verify API key and get key info",
    include_in_schema=False,
)
def verify_token_endpoint(api_key: RequireApiKey) -> dict:
    """Verify that the API key is valid and return key information."""
    return {
        "status": "valid",
        "message": "API key is valid",
        "key_info": {
            "name": api_key.name,
            "role": api_key.role,
            "last_used_at": api_key.last_used_at,
            "is_active": api_key.is_active,
        },
    }


@router.get(
    "/me",
    summary="Get Current API Key Info",
    description="Get detailed information about the current API key",
)
def get_current_api_key_info(api_key: RequireApiKey) -> dict:
    """Get detailed information about the current API key."""
    return {
        "name": api_key.name,
        "description": api_key.description,
        "role": api_key.role,
        "is_active": api_key.is_active,
        "last_used_at": api_key.last_used_at,
        "created_at": api_key.created_at,
        "updated_at": api_key.updated_at,
    }
