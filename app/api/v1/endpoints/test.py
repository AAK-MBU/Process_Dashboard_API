"""Test endpoints for audit log error message testing."""

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import RequireAdminKey

router = APIRouter()


@router.get(
    "/test-error-400",
    summary="Test 400 error logging",
    description="Endpoint that always returns 400 Bad Request",
    include_in_schema=True,
)
def test_error_400(admin_key: RequireAdminKey):
    """Test endpoint that raises a 400 error."""
    raise HTTPException(status_code=400, detail="This is a test 400 error for audit logging")


@router.get(
    "/test-error-404",
    summary="Test 404 error logging",
    description="Endpoint that always returns 404 Not Found",
)
def test_error_404(admin_key: RequireAdminKey):
    """Test endpoint that raises a 404 error."""
    raise HTTPException(status_code=404, detail="This is a test 404 error for audit logging")


@router.get(
    "/test-error-500",
    summary="Test 500 error logging",
    description="Endpoint that always raises an unhandled exception",
)
def test_error_500(admin_key: RequireAdminKey):
    """Test endpoint that raises an unhandled exception."""
    # This will cause a 500 Internal Server Error
    raise ValueError("This is a test unhandled exception for audit logging")


@router.get(
    "/test-validation-error",
    summary="Test validation error logging",
    description="Endpoint with validation that will fail",
)
def test_validation_error(
    admin_key: RequireAdminKey,
    age: int = Query(..., ge=0, le=120, description="Age must be between 0 and 120"),
):
    """Test endpoint for validation errors."""
    return {"age": age, "message": "Valid age provided"}


@router.get(
    "/test-success",
    summary="Test successful request logging",
    description="Endpoint that succeeds (for comparison)",
)
def test_success(admin_key: RequireAdminKey):
    """Test endpoint that succeeds normally."""
    return {"message": "This request succeeded", "status": "success"}
