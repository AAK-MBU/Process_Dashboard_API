"""API endpoints for managing process step runs."""

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.api.dependencies import RequireAdminKey
from app.db.database import SessionDep
from app.models import (
    ProcessRun,
    ProcessStep,
    ProcessStepRun,
    ProcessStepRunCreate,
    ProcessStepRunPublic,
    ProcessStepRunUpdate,
    StepRunStatus,
)
from app.services.rerun_service import RerunService

router = APIRouter()


@router.post(
    "/",
    response_model=ProcessStepRunPublic,
    status_code=201,
    summary="Create a step run",
    description="Create a new step run (usually done automatically when creating a process run)",
)
def create_step_run(
    *, session: SessionDep, step_run_in: ProcessStepRunCreate, admin_key: RequireAdminKey
) -> ProcessStepRun:
    """Create a new process step run."""
    # Verify run and step exist
    run = session.get(ProcessRun, step_run_in.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Process run not found")

    step = session.get(ProcessStep, step_run_in.step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Process step not found")

    step_run = ProcessStepRun.model_validate(step_run_in)
    session.add(step_run)
    session.commit()
    session.refresh(step_run)
    return step_run


@router.patch(
    "/{step_run_id}",
    response_model=ProcessStepRunPublic,
    summary="Update step run status",
    description="Update the status of a specific step run",
)
def update_step_run(
    *, session: SessionDep, step_run_id: int, update_in: ProcessStepRunUpdate
) -> ProcessStepRun:
    """Update a process step run status."""
    # step_run = session.get(ProcessStepRun, step_run_id)
    statement = (
        select(ProcessStepRun)
        .where(ProcessStepRun.id == step_run_id)
        .options(selectinload(ProcessStepRun.run).selectinload(ProcessRun.steps))
    )
    step_run = session.exec(statement).first()

    if not step_run:
        raise HTTPException(status_code=404, detail="Process step run not found")

    # Apply updates
    update_data = update_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(step_run, key, value)

    # If finished_at is not supplied and status is a finished state, set finished_at to None
    finished_statuses = [StepRunStatus.SUCCESS, StepRunStatus.FAILED]
    if "finished_at" not in update_data and update_in.status in finished_statuses:
        step_run.finished_at = None

    # If started_at is not supplied and status is RUNNING, set started_at to None
    if "started_at" not in update_data and update_in.status == StepRunStatus.RUNNING:
        step_run.started_at = None

    session.add(step_run)
    session.commit()
    session.refresh(step_run)

    return step_run


@router.post(
    "/{step_run_id}/rerun",
    summary="Rerun a process step",
    description=(
        "Rerun a specific step run if it's configured as rerunnable. "
        "This will trigger the external orchestrator to rerun the step."
    ),
)
async def rerun_step(*, session: SessionDep, step_run_id: int, admin_key: RequireAdminKey) -> dict:
    """Rerun a process step run."""
    statement = (
        select(ProcessStepRun)
        .where(ProcessStepRun.id == step_run_id)
        .options(selectinload(ProcessStepRun.run).selectinload(ProcessRun.steps))
    )
    step_run = session.exec(statement).first()
    if not step_run:
        raise HTTPException(status_code=404, detail="Process step run not found")

    # Check if this specific step run can be rerun
    if not step_run.can_rerun:
        raise HTTPException(
            status_code=400,
            detail="This step run cannot be rerun (can_rerun=False)",
        )

    # Check if maximum reruns exceeded
    if step_run.rerun_count >= step_run.max_reruns:
        raise HTTPException(
            status_code=400,
            detail=(f"Maximum reruns ({step_run.max_reruns}) exceeded for this step"),
        )

    # Check if step is in a rerunnable state (failed or stopped)
    if step_run.status not in [StepRunStatus.FAILED]:
        raise HTTPException(
            status_code=400,
            detail=(f"Step must be in FAILED status to be rerun (current: {step_run.status})"),
        )

    # Trigger external orchestrator rerun
    rerun_service = RerunService(session)
    try:
        rerun_result = await rerun_service.trigger_rerun(step_run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Check if rerun was successful
    if rerun_result["result"] == "success":
        # Update internal state after successful orchestrator call
        step_run.rerun_count += 1
        step_run.status = StepRunStatus.PENDING
        step_run.started_at = None
        step_run.finished_at = None
        step_run.failure = None
    else:
        # Rerun failed - update failure message with error details
        step_run.failure = {
            "error": "Rerun failed",
            "message": rerun_result["message"],
            "adapter": rerun_result["adapter"],
            "result_type": rerun_result["result"],
        }

    session.add(step_run)
    session.commit()
    session.refresh(step_run)

    return {
        "step_run": ProcessStepRunPublic.model_validate(step_run),
        "rerun_result": rerun_result,
    }


@router.get(
    "/run/{run_id}",
    response_model=list[ProcessStepRunPublic],
    summary="List step runs for a process run",
    description="Retrieve all step runs for a specific process run",
)
def list_step_runs_for_run(*, session: SessionDep, run_id: int) -> list[ProcessStepRun]:
    """List all step runs for a specific process run."""
    statement = (
        select(ProcessStepRun)
        .where(ProcessStepRun.run_id == run_id)
        .where(ProcessStepRun.deleted_at.is_(None))
        .order_by("step_index")
    )
    step_runs = session.exec(statement).all()
    return list(step_runs)


@router.get(
    "/run/{run_id}/step/{step_id}",
    response_model=ProcessStepRunPublic,
    summary="Get a step run by run and step",
    description="Retrieve a specific step run for a given process run and step.",
)
def get_step_run_by_run_and_step(
    *, session: SessionDep, run_id: int, step_id: int
) -> ProcessStepRun:
    """Get a specific step run by process run ID and step ID."""
    statement = (
        select(ProcessStepRun)
        .where(ProcessStepRun.run_id == run_id)
        .where(ProcessStepRun.step_id == step_id)
        .where(ProcessStepRun.deleted_at.is_(None))
    )
    step_run = session.exec(statement).first()
    if not step_run:
        raise HTTPException(status_code=404, detail="Step run not found for given run and step")
    return step_run


@router.get(
    "/run/{run_id}/rerunnable",
    response_model=list[ProcessStepRunPublic],
    summary="List rerunnable step runs",
    description="List step runs that can be rerun (failed steps with rerun capability)",
)
def list_rerunnable_step_runs(*, session: SessionDep, run_id: int) -> list[ProcessStepRun]:
    """List all step runs that can be rerun for a specific process run."""
    statement = (
        select(ProcessStepRun)
        .where(ProcessStepRun.run_id == run_id)
        .where(ProcessStepRun.can_rerun == True)  # noqa: E712
        .where(ProcessStepRun.status == StepRunStatus.FAILED)
        .where(ProcessStepRun.deleted_at.is_(None))
        .order_by("step_index")
    )
    step_runs = session.exec(statement).all()
    return list(step_runs)
