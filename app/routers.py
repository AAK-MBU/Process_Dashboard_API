"""API routers for process monitoring endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.database import SessionDep
from app.models import (
    Process,
    ProcessCreate,
    ProcessPublic,
    ProcessRun,
    ProcessRunCreate,
    ProcessRunPublic,
    ProcessStep,
    ProcessStepCreate,
    ProcessStepPublic,
    ProcessStepRun,
    ProcessStepRunCreate,
    ProcessStepRunPublic,
    ProcessStepRunUpdate,
)

# Process Router
router_process = APIRouter(prefix="/processes", tags=["processes"])


@router_process.post(
    "/",
    response_model=ProcessPublic,
    status_code=201,
    summary="Create a new process",
    description="Create a new process definition with metadata",
)
def create_process(*, session: SessionDep, process_in: ProcessCreate) -> Process:
    """Create a new process."""
    process = Process.model_validate(process_in)
    session.add(process)
    session.commit()
    session.refresh(process)
    return process


@router_process.get(
    "/",
    response_model=list[ProcessPublic],
    summary="List all processes",
    description="Retrieve a list of all process definitions",
)
def list_processes(
    session: SessionDep,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
) -> list[Process]:
    """List all processes with pagination."""
    statement = select(Process).order_by("id").offset(skip).limit(limit)
    processes = session.exec(statement).all()
    return list(processes)


@router_process.get(
    "/{process_id}",
    response_model=ProcessPublic,
    summary="Get process by ID",
    description="Retrieve a specific process definition including its steps",
)
def get_process(*, session: SessionDep, process_id: int) -> Process:
    """Get a specific process by ID."""
    process = session.get(Process, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return process


# Process Steps Router
router_steps = APIRouter(prefix="/steps", tags=["process-steps"])


@router_steps.post(
    "/",
    response_model=ProcessStepPublic,
    status_code=201,
    summary="Create a process step",
    description="Create a new step for a process",
)
def create_process_step(*, session: SessionDep, step_in: ProcessStepCreate) -> ProcessStep:
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


@router_steps.get(
    "/process/{process_id}",
    response_model=list[ProcessStepPublic],
    summary="List steps for a process",
    description="Retrieve all steps for a specific process, ordered by index",
)
def list_process_steps(*, session: SessionDep, process_id: int) -> list[ProcessStep]:
    """List all steps for a specific process."""
    statement = select(ProcessStep).where(ProcessStep.process_id == process_id).order_by("index")
    steps = session.exec(statement).all()
    return list(steps)


# Process Runs Router
router_runs = APIRouter(prefix="/runs", tags=["process-runs"])


@router_runs.post(
    "/",
    response_model=ProcessRunPublic,
    status_code=201,
    summary="Create a process run",
    description="Create a new process run for a specific entity (e.g., citizen)",
)
def create_process_run(*, session: SessionDep, run_in: ProcessRunCreate) -> ProcessRun:
    """Create a new process run."""
    # Verify process exists
    process = session.get(Process, run_in.process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    run = ProcessRun.model_validate(run_in)
    session.add(run)
    session.commit()
    session.refresh(run)

    # Create step runs for all process steps
    for step in process.steps:
        step_run = ProcessStepRun(
            run_id=run.id,
            step_id=step.id,
            step_index=step.index,
        )
        session.add(step_run)

    session.commit()
    session.refresh(run)
    return run


@router_runs.get(
    "/",
    response_model=list[ProcessRunPublic],
    summary="List all process runs",
    description="Retrieve all process runs with optional filtering",
)
def list_process_runs(
    session: SessionDep,
    process_id: int | None = Query(None, description="Filter by process ID"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[ProcessRun]:
    """List all process runs with optional filters."""
    statement = select(ProcessRun)

    if process_id:
        statement = statement.where(ProcessRun.process_id == process_id)
    if entity_id:
        statement = statement.where(ProcessRun.entity_id == entity_id)

    statement = statement.order_by("id").offset(skip).limit(limit)
    runs = session.exec(statement).all()
    return list(runs)


@router_runs.get(
    "/{run_id}",
    response_model=ProcessRunPublic,
    summary="Get process run by ID",
    description="Retrieve a specific process run including all step statuses",
)
def get_process_run(*, session: SessionDep, run_id: int) -> ProcessRun:
    """Get a specific process run by ID."""
    run = session.get(ProcessRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Process run not found")
    return run


# Process Step Runs Router
router_step_runs = APIRouter(prefix="/step-runs", tags=["step-runs"])


@router_step_runs.post(
    "/",
    response_model=ProcessStepRunPublic,
    status_code=201,
    summary="Create a step run",
    description="Create a new step run (usually done automatically when creating a process run)",
)
def create_step_run(*, session: SessionDep, step_run_in: ProcessStepRunCreate) -> ProcessStepRun:
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


@router_step_runs.patch(
    "/{step_run_id}",
    response_model=ProcessStepRunPublic,
    summary="Update step run status",
    description="Update the status of a specific step run",
)
def update_step_run(
    *, session: SessionDep, step_run_id: int, update_in: ProcessStepRunUpdate
) -> ProcessStepRun:
    """Update a process step run status."""
    step_run = session.get(ProcessStepRun, step_run_id)
    if not step_run:
        raise HTTPException(status_code=404, detail="Process step run not found")

    # Update fields
    for key, value in update_in.model_dump(exclude_unset=True).items():
        setattr(step_run, key, value)

    session.add(step_run)
    session.commit()
    session.refresh(step_run)

    # Update parent run status
    run = session.get(ProcessRun, step_run.run_id)
    if run:
        run.update_status()
        session.add(run)
        session.commit()

    return step_run


@router_step_runs.get(
    "/run/{run_id}",
    response_model=list[ProcessStepRunPublic],
    summary="List step runs for a process run",
    description="Retrieve all step runs for a specific process run",
)
def list_step_runs_for_run(*, session: SessionDep, run_id: int) -> list[ProcessStepRun]:
    """List all step runs for a specific process run."""
    statement = select(ProcessStepRun).where(ProcessStepRun.run_id == run_id).order_by("step_index")
    step_runs = session.exec(statement).all()
    return list(step_runs)


# Dashboard Router
router_dashboard = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router_dashboard.get(
    "/overview/{process_id}",
    summary="Get process overview for dashboard",
    description="Retrieve complete process overview with all runs and step statuses",
)
def get_dashboard_overview(*, session: SessionDep, process_id: int) -> dict[str, Any]:
    """Get complete dashboard overview for a process."""
    process = session.get(Process, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    # Get all runs for this process
    statement = select(ProcessRun).where(ProcessRun.process_id == process_id)
    runs = session.exec(statement).all()

    return {
        "process": ProcessPublic.model_validate(process),
        "runs": [ProcessRunPublic.model_validate(run) for run in runs],
        "total_runs": len(runs),
        "completed_runs": sum(1 for run in runs if run.status == "completed"),
        "failed_runs": sum(1 for run in runs if run.status == "failed"),
        "running_runs": sum(1 for run in runs if run.status == "running"),
    }
