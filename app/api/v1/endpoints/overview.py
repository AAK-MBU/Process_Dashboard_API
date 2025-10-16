"""API endpoints for dashboard overview."""

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.db.database import SessionDep
from app.models import (
    Process,
    ProcessPublic,
    ProcessRun,
    ProcessRunPublic,
)

router = APIRouter()


@router.get(
    "/overview/{process_id}",
    summary="Get process overview for dashboard",
    description="Retrieve complete process overview with all runs and step statuses",
)
def get_dashboard_overview(*, session: SessionDep, process_id: int) -> dict[str, Any]:
    """Get complete dashboard overview for a process."""
    process = session.get(Process, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    # Get all runs for this process (exclude soft-deleted)
    statement = (
        select(ProcessRun)
        .where(ProcessRun.process_id == process_id)
        .where(ProcessRun.deleted_at.is_(None))
    )
    runs = session.exec(statement).all()

    return {
        "process": ProcessPublic.model_validate(process),
        "runs": [ProcessRunPublic.model_validate(run) for run in runs],
        "total_runs": len(runs),
        "completed_runs": sum(1 for run in runs if run.status == "completed"),
        "failed_runs": sum(1 for run in runs if run.status == "failed"),
        "running_runs": sum(1 for run in runs if run.status == "running"),
    }
