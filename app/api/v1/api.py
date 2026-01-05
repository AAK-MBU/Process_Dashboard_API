"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    api_keys,
    audit,
    auth,
    processes,
    runs,
    step_runs,
    steps,
    test,
)
from app.api.v1.endpoints import (
    overview as dashboard,
)

# Create the main API v1 router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

api_router.include_router(processes.router, prefix="/processes", tags=["processes"])

api_router.include_router(runs.router, prefix="/runs", tags=["process-runs"])

api_router.include_router(steps.router, prefix="/steps", tags=["process-steps"])

api_router.include_router(step_runs.router, prefix="/step-runs", tags=["step-runs"])

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

api_router.include_router(
    api_keys.router, prefix="/api-keys", tags=["api-keys"], include_in_schema=True
)

api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

api_router.include_router(audit.router, prefix="/audit-logs", tags=["audit-logs"])

api_router.include_router(test.router, prefix="/test", tags=["testing"])
