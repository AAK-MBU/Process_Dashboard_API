"""Dependencies for FastAPI routes."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlmodel import Session

from app.core.exceptions import AuthenticationError
from app.db.database import get_session
from app.models import ApiKey
from app.services.auth_service import AuthService
from app.services.process_service import ProcessService
from app.services.run_service import ProcessRunService
from app.services.search_service import SearchService
from app.services.step_run_service import StepRunService
from app.services.step_service import StepService

logger = logging.getLogger(__name__)


def get_process_service(db: Session = Depends(get_session)) -> ProcessService:
    """Dependency for getting ProcessService."""
    return ProcessService(db)


def get_run_service(db: Session = Depends(get_session)) -> ProcessRunService:
    """Dependency for getting ProcessRunService."""
    return ProcessRunService(db)


def get_search_service(db: Session = Depends(get_session)) -> SearchService:
    """Dependency for getting SearchService."""
    return SearchService(db)


def get_step_service(db: Session = Depends(get_session)) -> StepService:
    """Get step service instance."""
    return StepService(db)


def get_step_run_service(db: Session = Depends(get_session)) -> StepRunService:
    """Get step run service instance."""
    return StepRunService(db)


def get_auth_service(db: Session = Depends(get_session)) -> AuthService:
    """Get authentication service instance."""
    return AuthService(db)


# Security scheme for API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


# Authentication Dependencies
def verify_api_key(
    x_api_key: str = Depends(api_key_header),
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiKey:
    """
    Verify API key from header.

    Args:
        x_api_key: API key from X-API-Key header
        auth_service: Authentication service

    Returns:
        ApiKey object if valid

    Raises:
        HTTPException: If authentication fails
    """
    try:
        return auth_service.verify_api_key(x_api_key)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "ApiKey"},
        ) from e


def require_admin_key(api_key: ApiKey = Depends(verify_api_key)) -> ApiKey:
    """
    Require admin role for the API key.

    Args:
        api_key: Verified API key

    Returns:
        ApiKey object if admin

    Raises:
        HTTPException: If not admin role
    """
    if api_key.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return api_key


# Service Type Aliases
ProcessServiceDep = Annotated[ProcessService, Depends(get_process_service)]
ProcessRunServiceDep = Annotated[ProcessRunService, Depends(get_run_service)]
RunServiceDep = Annotated[ProcessRunService, Depends(get_run_service)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
StepRunServiceDep = Annotated[StepRunService, Depends(get_step_run_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

# Authentication Type Aliases
RequireApiKey = Annotated[ApiKey, Depends(verify_api_key)]
RequireAdminKey = Annotated[ApiKey, Depends(require_admin_key)]
