"""API endpoints for managing process runs."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlmodel import select

from app.api.dependencies import RequireAdminKey, RunServiceDep
from app.db.database import SessionDep
from app.models import (
    ProcessRun,
    ProcessRunCreate,
    ProcessRunPublic,
)

router = APIRouter()


@router.post(
    "/",
    response_model=ProcessRunPublic,
    status_code=201,
    summary="Create a process run",
    description="Create a new process run for a specific entity (e.g., citizen)",
)
def create_process_run(
    run_in: ProcessRunCreate, service: RunServiceDep, admin_key: RequireAdminKey
) -> ProcessRun:
    """Create a new process run."""
    run = service.create_run_with_steps(run_in)
    return ProcessRun.model_validate(run)


@router.get(
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


@router.get(
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
