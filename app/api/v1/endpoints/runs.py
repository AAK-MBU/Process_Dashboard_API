"""API endpoints for managing process runs."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import paginate

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
    run_service: RunServiceDep,
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
    meta_filter: list[str] | None = Query(
        None,
        description=("Metadata filter in format 'field:value'. Can be specified multiple times"),
    ),
    # Sorting
    order_by: str = Query("created_at", description="Field to sort by"),
    sort_direction: str = Query("desc", regex="^(asc|desc)$"),
    # Pagination
    params: Params = Depends(),
) -> Page[ProcessRun]:
    """List all process runs with optional filters and sorting."""
    # Build filtered statement using service layer
    try:
        statement = run_service.build_filtered_statement(
            process_id=process_id,
            entity_id=entity_id,
            entity_name=entity_name,
            status=run_status,
            started_after=started_after,
            started_before=started_before,
            finished_after=finished_after,
            finished_before=finished_before,
            meta_filter=meta_filter,
            order_by=order_by,
            sort_direction=sort_direction,
            include_deleted=False,
            include_neutralized=True,
        )
    except ValueError as e:
        # Convert service layer validation errors to HTTP errors
        raise HTTPException(status_code=400, detail=str(e)) from e

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
