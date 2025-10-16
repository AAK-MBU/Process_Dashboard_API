"""API endpoints for managing process runs."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy import text
from sqlmodel import select

from app.api.dependencies import RequireAdminKey, RunServiceDep
from app.core.pagination import add_pagination_links
from app.db.database import SessionDep
from app.models import NeutralizationResult, ProcessRun, ProcessRunCreate, ProcessRunPublic
from app.services import DataRetentionService

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
    response_model=Page[ProcessRunPublic],
    summary="List all process runs",
    description="Retrieve all process runs with optional filtering and sorting",
)
def list_process_runs(
    request: Request,
    response: Response,
    session: SessionDep,
    # Basic filters
    process_id: int | None = Query(None, description="Filter by process ID"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
    entity_name: str | None = Query(None, description="Filter by entity name (partial match)"),
    run_status: str | None = Query(None, description="Filter by status"),
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
    params: Params = Depends(),
) -> Page[ProcessRun]:
    """List all process runs with optional filters and sorting."""
    # Base query
    statement = select(ProcessRun)

    # Exclude soft-deleted runs by default
    statement = statement.where(ProcessRun.deleted_at.is_(None))

    # Basic filters
    if process_id:
        statement = statement.where(ProcessRun.process_id == process_id)
    if entity_id:
        statement = statement.where(ProcessRun.entity_id == entity_id)
    if entity_name:
        statement = statement.where(ProcessRun.entity_name.contains(entity_name))
    if run_status:
        statement = statement.where(ProcessRun.status == run_status)

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

    # Paginate and add Link headers
    page_data = paginate(session, statement, params)
    add_pagination_links(request, response, page_data)

    return page_data


@router.get(
    "/{run_id}",
    response_model=ProcessRunPublic,
    summary="Get process run by ID",
    description="Retrieve a specific process run including all step statuses",
)
def get_process_run(*, session: SessionDep, run_id: int) -> ProcessRun:
    """Get a specific process run by ID."""
    run = session.get(ProcessRun, run_id)
    if not run or run.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Process run not found")
    return run


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a run",
    description="Soft delete a process run and all its step runs",
)
def delete_run(*, session: SessionDep, run_id: int, admin_key: RequireAdminKey) -> None:
    """Soft delete a process run."""
    run = session.get(ProcessRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Process run not found")

    retention_service = DataRetentionService(session)
    retention_service.soft_delete_run(run)


@router.post(
    "/{run_id}/restore",
    response_model=ProcessRunPublic,
    summary="Restore a soft-deleted run",
    description="Restore a previously soft-deleted run and its step runs",
)
def restore_run(*, session: SessionDep, run_id: int, admin_key: RequireAdminKey) -> ProcessRun:
    """Restore a soft-deleted run."""
    run = session.get(ProcessRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Process run not found")

    retention_service = DataRetentionService(session)
    return retention_service.restore_run(run)


@router.post(
    "/{run_id}/neutralize",
    response_model=NeutralizationResult,
    summary="Neutralize sensitive data",
    description=(
        "Manually neutralize personally identifiable information in a run. "
        "This removes entity_id, entity_name, and sensitive metadata "
        "while keeping the run record for statistics."
    ),
)
def neutralize_run(
    *, session: SessionDep, run_id: int, admin_key: RequireAdminKey
) -> NeutralizationResult:
    """Neutralize sensitive data in a process run."""
    run = session.get(ProcessRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Process run not found")

    was_neutralized = run.is_neutralized

    retention_service = DataRetentionService(session)
    retention_service.neutralize_run_data(run)

    return NeutralizationResult(
        run_id=run_id,
        was_already_neutralized=was_neutralized,
        success=True,
        message=(
            "Run was already neutralized" if was_neutralized else "Run successfully neutralized"
        ),
    )
