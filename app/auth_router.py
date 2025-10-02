"""Simple authentication - just token verification."""

from fastapi import APIRouter, Depends

from app.auth import verify_token

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/verify", summary="Verify Token", description="Verify if provided token is valid")
def verify_token_endpoint(_: bool = Depends(verify_token)) -> dict:
    """Verify that the token is valid."""
    return {"status": "valid", "message": "Token is valid"}
