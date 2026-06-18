"""API endpoints for aggregated statistics."""

from typing import Any

from fastapi import APIRouter, Query

from app.api.dependencies import RequireAdminKey, StatisticsServiceDep

router = APIRouter()


@router.get(
    "/",
    summary="Get system-wide statistics",
    description="Aggregated statistics across all processes: status breakdown, "
    "success rate, run timing, step failure hotspots, and trends (admin only).",
)
def get_system_statistics(
    *,
    statistics_service: StatisticsServiceDep,
    admin_key: RequireAdminKey,
    days: int = Query(30, ge=1, description="Window in days for time-based trends"),
) -> dict[str, Any]:
    """Get aggregated statistics across all processes."""
    return statistics_service.get_system_statistics(days=days)


@router.get(
    "/process/{process_id}",
    summary="Get statistics for a single process",
    description="Aggregated statistics scoped to one process: status breakdown, "
    "success rate, run timing, step failure hotspots, and trends (admin only).",
)
def get_process_statistics(
    *,
    statistics_service: StatisticsServiceDep,
    admin_key: RequireAdminKey,
    process_id: int,
    days: int = Query(30, ge=1, description="Window in days for time-based trends"),
) -> dict[str, Any]:
    """Get aggregated statistics for a specific process.

    Raises ProcessNotFoundError (handled globally as 404) if the process does
    not exist or has been soft-deleted.
    """
    return statistics_service.get_process_statistics(process_id, days=days)
