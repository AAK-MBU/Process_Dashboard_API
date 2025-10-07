"""Admin endpoints for data retention and cleanup operations."""

from fastapi import APIRouter, Query

from app.api.dependencies import RequireAdminKey
from app.db.database import SessionDep
from app.models import CleanupResult, CleanupStats
from app.services import DataRetentionService

router = APIRouter()


@router.post(
    "/cleanup/neutralize",
    response_model=CleanupResult,
    summary="Neutralize due runs",
    description=(
        "Manually trigger neutralization of runs that have exceeded "
        "their retention period. This removes personally identifiable "
        "information while keeping run records for statistics."
    ),
)
def trigger_cleanup(
    *,
    session: SessionDep,
    admin_key: RequireAdminKey,
    batch_size: int = Query(100, ge=1, le=1000, description="Number of runs to process"),
) -> CleanupResult:
    """Trigger manual cleanup of runs due for neutralization."""
    service = DataRetentionService(session)
    stats = service.neutralize_due_runs(batch_size=batch_size)

    return CleanupResult(
        total_found=stats["total_found"],
        neutralized=stats["neutralized"],
        failed=stats["failed"],
        errors=stats["errors"],
    )


@router.get(
    "/cleanup/stats",
    response_model=CleanupStats,
    summary="Get cleanup statistics",
    description="Get statistics about runs due for neutralization",
)
def get_cleanup_stats(
    *,
    session: SessionDep,
    admin_key: RequireAdminKey,
    limit: int = Query(10, ge=1, le=100, description="Max run IDs to return as sample"),
) -> CleanupStats:
    """Get statistics about runs due for neutralization."""
    service = DataRetentionService(session)
    due_runs = service.get_runs_due_for_neutralization(limit=limit)

    return CleanupStats(
        runs_due_for_neutralization=len(due_runs),
        sample_run_ids=[run.id for run in due_runs if run.id],
    )
