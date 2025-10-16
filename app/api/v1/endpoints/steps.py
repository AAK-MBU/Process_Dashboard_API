"""API endpoints for managing process steps."""

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.dependencies import RequireAdminKey
from app.db.database import SessionDep
from app.models import (
    Process,
    ProcessStep,
    ProcessStepCreate,
    ProcessStepPublic,
)

router = APIRouter()


@router.post(
    "/",
    response_model=ProcessStepPublic,
    status_code=201,
    summary="Create a process step",
    description="Create a new step for a process",
)
def create_process_step(
    *, session: SessionDep, step_in: ProcessStepCreate, admin_key: RequireAdminKey
) -> ProcessStep:
    """Create a new process step."""
    # Verify process exists
    process = session.get(Process, step_in.process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    step = ProcessStep.model_validate(step_in)
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


@router.get(
    "/process/{process_id}",
    response_model=list[ProcessStepPublic],
    summary="List steps for a process",
    description="Retrieve all steps for a specific process, ordered by index",
)
def list_process_steps(*, session: SessionDep, process_id: int) -> list[ProcessStep]:
    """List all steps for a specific process."""
    statement = (
        select(ProcessStep)
        .where(ProcessStep.process_id == process_id)
        .where(ProcessStep.deleted_at.is_(None))
        .order_by("index")
    )
    steps = session.exec(statement).all()
    return list(steps)


@router.get(
    "/process/{process_id}/rerunnable",
    response_model=list[ProcessStepPublic],
    summary="List rerunnable steps for a process",
    description="Retrieve all steps that are configured as rerunnable for a process",
)
def list_rerunnable_steps(*, session: SessionDep, process_id: int) -> list[ProcessStep]:
    """List all rerunnable steps for a specific process."""
    statement = (
        select(ProcessStep)
        .where(ProcessStep.process_id == process_id)
        .where(ProcessStep.is_rerunnable)
        .where(ProcessStep.deleted_at.is_(None))
        .order_by("index")
    )
    steps = session.exec(statement).all()
    return list(steps)
