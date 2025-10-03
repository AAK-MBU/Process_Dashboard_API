"""Database-based API key authentication."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from .database import get_session
from .models import ApiKey

security = HTTPBearer()


def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> ApiKey:
    """
    Verify API key against database.

    Args:
        credentials: HTTP Bearer credentials with API key
        session: Database session

    Returns:
        ApiKey object if valid

    Raises:
        HTTPException: 401 if token is invalid
    """
    token = credentials.credentials

    token_hash = ApiKey.hash_key(token)

    statement = select(ApiKey).where(ApiKey.key_hash == token_hash, ApiKey.is_active == True)
    api_key = session.exec(statement).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key.last_used_at = datetime.now(timezone.utc)
    api_key.usage_count += 1
    session.add(api_key)
    session.commit()

    return api_key


def require_admin_key(api_key: ApiKey = Depends(verify_api_key)) -> ApiKey:
    """
    Verify that the API key has admin role.

    Args:
        api_key: Verified API key from verify_api_key

    Returns:
        ApiKey object if it has admin role

    Raises:
        HTTPException: 403 if not admin role
    """
    if api_key.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return api_key


RequireApiKey = Annotated[ApiKey, Depends(verify_api_key)]
RequireAdminKey = Annotated[ApiKey, Depends(require_admin_key)]
