"""Simple token-based authentication - no users, just tokens."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

# Security scheme
security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """
    Verify that the provided token matches the configured API token.

    Args:
        credentials: HTTP Bearer credentials with token

    Returns:
        True if token is valid

    Raises:
        HTTPException: 401 if token is invalid
    """
    token = credentials.credentials

    if token != settings.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


# Dependency for protected endpoints
RequireAuth = Annotated[bool, Depends(verify_token)]
