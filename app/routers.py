"""API routers for process monitoring endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
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
    StepRunStatus,
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


@router_process.get(
    "/{process_id}/searchable-fields",
    summary="Get all searchable fields for process runs",
    description="Get complete overview of all searchable/sortable fields",
)
def get_process_searchable_fields(*, session: SessionDep, process_id: int) -> dict[str, Any]:
    """Get all searchable fields for a process."""
    process = session.get(Process, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    # Standard fields that are always available
    standard_fields = {
        "id": {
            "type": "integer",
            "description": "Process run ID",
            "sortable": True,
            "filterable": False,
        },
        "entity_id": {
            "type": "string",
            "description": "Entity identifier (e.g., CPR, case number)",
            "sortable": True,
            "filterable": True,
        },
        "entity_name": {
            "type": "string",
            "description": "Entity name (e.g., person name)",
            "sortable": True,
            "filterable": True,
        },
        "status": {
            "type": "enum",
            "description": "Process run status",
            "values": ["pending", "running", "completed", "failed"],
            "sortable": True,
            "filterable": True,
        },
        "started_at": {
            "type": "datetime",
            "description": "When the process run started",
            "sortable": True,
            "filterable": True,
            "filter_types": ["after", "before"],
        },
        "finished_at": {
            "type": "datetime",
            "description": "When the process run finished",
            "sortable": True,
            "filterable": True,
            "filter_types": ["after", "before"],
        },
        "created_at": {
            "type": "datetime",
            "description": "When the record was created",
            "sortable": True,
            "filterable": False,
        },
        "updated_at": {
            "type": "datetime",
            "description": "When the record was last updated",
            "sortable": True,
            "filterable": False,
        },
    }

    # Get metadata schema from process definition
    metadata_schema = process.meta.get("run_metadata_schema", {})

    # Get actual metadata fields from data - use schema as fallback
    try:
        # Simple approach: use the schema fields for now
        actual_metadata_fields = list(metadata_schema.keys())
    except Exception:
        actual_metadata_fields = []

    # Build metadata fields info
    metadata_fields = {}
    for field in actual_metadata_fields:
        field_info = {
            "type": metadata_schema.get(field, "string"),
            "description": f"Metadata field: {field}",
            "sortable": True,
            "filterable": True,
            "sortable_as": f"meta.{field}",
            "filter_format": "meta_filter parameter: field:value",
        }
        metadata_fields[field] = field_info

    return {
        "process_id": process_id,
        "process_name": process.name,
        "standard_fields": standard_fields,
        "metadata_fields": metadata_fields,
        "all_sortable_fields": list(standard_fields.keys())
        + [f"meta.{field}" for field in metadata_fields.keys()],
        "all_filterable_fields": [
            field for field, info in standard_fields.items() if info.get("filterable", False)
        ]
        + [f"meta.{field}" for field in metadata_fields.keys()],
        "field_count": {
            "standard": len(standard_fields),
            "metadata": len(metadata_fields),
            "total": len(standard_fields) + len(metadata_fields),
        },
        "filtering_help": {
            "metadata": "Use meta_filter parameter with format 'field:value' or 'field1:value1,field2:value2'",
            "dates": "Use ISO format for date filters (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
            "partial_match": "entity_name supports partial matching",
        },
    }


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


@router_steps.get(
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
        .order_by("index")
    )
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
        # Extract max_reruns from step template config or use default
        max_reruns = 0
        rerun_config = {}
        if step.is_rerunnable:
            rerun_config = step.rerun_config.copy() if step.rerun_config else {}
            max_reruns = step.rerun_config.get("max_retries", 3) if step.rerun_config else 3

        step_run = ProcessStepRun(
            run_id=run.id,
            step_id=step.id,
            step_index=step.index,
            can_rerun=step.is_rerunnable,  # Inherit from step
            rerun_config=rerun_config,  # Copy from step template
            max_reruns=max_reruns,  # Extract from template or default
        )
        session.add(step_run)

    session.commit()
    session.refresh(run)
    return run


@router_runs.get(
    "/",
    response_model=list[ProcessRunPublic],
    summary="List all process runs",
    description="Retrieve all process runs with optional filtering and sorting",
)
def list_process_runs(
    session: SessionDep,
    # Basic filters
    process_id: int | None = Query(None, description="Filter by process ID"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
    entity_name: str | None = Query(None, description="Filter by entity name (partial match)"),
    status: str | None = Query(None, description="Filter by status"),
    # Date filters
    started_after: str | None = Query(
        None, description="Filter runs started after this date (ISO format)"
    ),
    started_before: str | None = Query(
        None, description="Filter runs started before this date (ISO format)"
    ),
    finished_after: str | None = Query(
        None, description="Filter runs finished after this date (ISO format)"
    ),
    finished_before: str | None = Query(
        None, description="Filter runs finished before this date (ISO format)"
    ),
    # Metadata filters (dynamic)
    meta_filter: str | None = Query(
        None, description="Metadata filter in format 'field:value' or 'field:value,field2:value2'"
    ),
    # Sorting
    order_by: str = Query("created_at", description="Field to sort by"),
    sort_direction: str = Query("desc", regex="^(asc|desc)$"),
    # Pagination
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[ProcessRun]:
    """List all process runs with optional filters and sorting."""
    statement = select(ProcessRun)

    # Basic filters
    if process_id:
        statement = statement.where(ProcessRun.process_id == process_id)
    if entity_id:
        statement = statement.where(ProcessRun.entity_id == entity_id)
    if entity_name:
        statement = statement.where(ProcessRun.entity_name.contains(entity_name))
    if status:
        statement = statement.where(ProcessRun.status == status)

    # Date filters
    if started_after:
        statement = statement.where(ProcessRun.started_at >= started_after)
    if started_before:
        statement = statement.where(ProcessRun.started_at <= started_before)
    if finished_after:
        statement = statement.where(ProcessRun.finished_at >= finished_after)
    if finished_before:
        statement = statement.where(ProcessRun.finished_at <= finished_before)

    # Metadata filters
    if meta_filter:
        # Parse metadata filters: "field:value,field2:value2"
        filters = meta_filter.split(",")
        for filter_item in filters:
            if ":" in filter_item:
                field, value = filter_item.split(":", 1)
                field = field.strip()
                value = value.strip()
                # Use SQL Server JSON_VALUE for metadata filtering
                statement = statement.where(
                    text(f"JSON_VALUE(process_run.meta, '$.{field}') = :meta_{field}")
                ).params(**{f"meta_{field}": value})

    # Handle sorting
    if order_by.startswith("meta."):
        # Sort by JSON field using SQL Server syntax
        json_field = order_by.replace("meta.", "")
        if sort_direction.lower() == "desc":
            statement = statement.order_by(
                text(f"JSON_VALUE(process_run.meta, '$.{json_field}') DESC")
            )
        else:
            statement = statement.order_by(
                text(f"JSON_VALUE(process_run.meta, '$.{json_field}') ASC")
            )
    else:
        # Sort by regular field - use SQLModel column references
        if order_by == "id":
            column = ProcessRun.id
        elif order_by == "entity_id":
            column = ProcessRun.entity_id
        elif order_by == "entity_name":
            column = ProcessRun.entity_name
        elif order_by == "status":
            column = ProcessRun.status
        elif order_by == "started_at":
            column = ProcessRun.started_at
        elif order_by == "finished_at":
            column = ProcessRun.finished_at
        elif order_by == "created_at":
            column = ProcessRun.created_at
        elif order_by == "updated_at":
            column = ProcessRun.updated_at
        else:
            raise HTTPException(status_code=400, detail=f"Invalid sort field '{order_by}'")

        if sort_direction.lower() == "desc":
            statement = statement.order_by(column.desc())
        else:
            statement = statement.order_by(column.asc())

    statement = statement.offset(skip).limit(limit)
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


@router_step_runs.post(
    "/{step_run_id}/rerun",
    response_model=ProcessStepRunPublic,
    summary="Rerun a process step",
    description="Rerun a specific step run if it's configured as rerunnable",
)
def rerun_step(*, session: SessionDep, step_run_id: int) -> ProcessStepRun:
    """Rerun a process step run."""
    step_run = session.get(ProcessStepRun, step_run_id)
    if not step_run:
        raise HTTPException(status_code=404, detail="Process step run not found")

    # Check if this specific step run can be rerun
    if not step_run.can_rerun:
        raise HTTPException(
            status_code=400, detail=f"This step run cannot be rerun (can_rerun=False)"
        )

    # Check if maximum reruns exceeded
    if step_run.rerun_count >= step_run.max_reruns:
        raise HTTPException(
            status_code=400, detail=f"Maximum reruns ({step_run.max_reruns}) exceeded for this step"
        )

    # Check if step is in a rerunnable state (failed or stopped)
    if step_run.status not in [StepRunStatus.FAILED]:
        raise HTTPException(
            status_code=400,
            detail=f"Step must be in FAILED status to be rerun (current: {step_run.status})",
        )

    # Increment rerun count and reset step run to pending status
    step_run.rerun_count += 1
    step_run.status = StepRunStatus.PENDING
    step_run.started_at = None
    step_run.finished_at = None
    step_run.failure = None

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


@router_step_runs.get(
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
        .where(ProcessStepRun.can_rerun == True)
        .where(ProcessStepRun.status == StepRunStatus.FAILED)
        .order_by("step_index")
    )
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
