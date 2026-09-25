"""API endpoints for managing process runs."""

from collections.abc import Sequence

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy.orm import selectinload

from app.api.dependencies import (
    RequireAdminKey,
    RequireApiKey,
    RunServiceDep,
    SearchServiceDep,
)
from app.core.pagination import add_pagination_links
from app.db.database import SessionDep
from app.models import (
    NeutralizationResult,
    ProcessRun,
    ProcessRunCreate,
    ProcessRunListItem,
    ProcessRunMetadataUpdate,
    ProcessRunPublic,
    ProcessStepRun,
    StepRunStatus,
    # SearchResultItem,
)
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
    "/search",
    response_model=dict,
    summary="Global search across process runs",
    description=(
        "Search across all searchable fields and return which fields "
        "matched for each result. Includes field names and matched values."
    ),
)
def search_process_runs(
    request: Request,
    response: Response,
    session: SessionDep,
    search_service: SearchServiceDep,
    q: str = Query(
        ...,
        min_length=1,
        description="Search term (case-insensitive, partial match)",
    ),
    process_id: int | None = Query(
        None,
        description="Optional process ID to filter and include metadata search",
    ),
    params: Params = Depends(),
) -> dict:
    """
    Global search across process runs with match annotations.

    Searches across standard fields (entity_id, entity_name, status) and
    optionally metadata fields if process_id is specified.

    Returns search results with additional metadata showing which fields
    matched the search term and their values.
    """
    statement = search_service.search_items(
        search_params=q,
        process_id=process_id,
    )

    # Paginate
    page_data = paginate(session, statement, params)
    add_pagination_links(request, response, page_data)

    # Annotate results with match information
    annotated_items = search_service.annotate_matches(
        runs=list(page_data.items),
        search_term=q,
        process_id=process_id,
    )

    # Return paginated response with annotated items
    return {
        "items": annotated_items,
        "total": page_data.total,
        "page": page_data.page,
        "size": page_data.size,
        "pages": page_data.pages,
    }


class RunFilters:
    """Query parameters shared by ``GET /runs/`` and ``GET /runs/overview``.

    One definition, so the list and the overview can never disagree about what
    a filter means.
    """

    def __init__(
        self,
        # Basic filters
        process_id: int | None = Query(None, description="Filter by process ID"),
        entity_id: str | None = Query(None, description="Filter by entity ID (exact match)"),
        entity_name: str | None = Query(None, description="Filter by entity name (partial match)"),
        run_status: str | None = Query(
            None,
            description=(
                "Filter by status. Several may be given separated by commas, "
                "e.g. 'failed,cancelled'"
            ),
        ),
        q: str | None = Query(
            None,
            description=(
                "Free text, partial and case-insensitive, matched against entity_id, "
                "entity_name and top-level metadata values. Combines with every other filter"
            ),
        ),
        is_neutralized: bool | None = Query(
            None, description="Only neutralized (true) or not neutralized (false) runs"
        ),
        # Date filters (ISO 8601, inclusive)
        started_after: str | None = Query(
            None, description="Filter runs started at or after this date (ISO format)"
        ),
        started_before: str | None = Query(
            None, description="Filter runs started at or before this date (ISO format)"
        ),
        finished_after: str | None = Query(
            None, description="Filter runs finished at or after this date (ISO format)"
        ),
        finished_before: str | None = Query(
            None, description="Filter runs finished at or before this date (ISO format)"
        ),
        created_after: str | None = Query(
            None, description="Filter runs created at or after this date (ISO format)"
        ),
        created_before: str | None = Query(
            None, description="Filter runs created at or before this date (ISO format)"
        ),
        # Metadata filters (dynamic)
        meta_filter: list[str] | None = Query(
            None,
            description=(
                "Metadata filter in format 'field:value'. Can be specified multiple "
                "times; the same field is OR'd, different fields are AND'd"
            ),
        ),
        # Step failure filter
        failed_at: int | None = Query(
            None,
            description="Filter runs that failed at a specific step_id",
        ),
        # Soft delete
        include_deleted: bool = Query(
            False,
            description="Include soft-deleted runs in the result (requires an admin API key)",
        ),
        # Sorting
        order_by: str = Query(
            "created_at",
            description=(
                "Field to sort by: a run column, process_name, duration or meta.<field>. "
                "Unknown fields return 400"
            ),
        ),
        sort_direction: str = Query("desc", pattern="^(asc|desc)$"),
    ):
        self.process_id = process_id
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.run_status = run_status
        self.q = q
        self.is_neutralized = is_neutralized
        self.started_after = started_after
        self.started_before = started_before
        self.finished_after = finished_after
        self.finished_before = finished_before
        self.created_after = created_after
        self.created_before = created_before
        self.meta_filter = meta_filter
        self.failed_at = failed_at
        self.include_deleted = include_deleted
        self.order_by = order_by
        self.sort_direction = sort_direction

    def statement(self, run_service, api_key):
        """Build the filtered statement, turning bad input into 400/403."""
        if self.include_deleted and api_key.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required to include soft-deleted runs",
            )
        try:
            return run_service.build_filtered_statement(
                process_id=self.process_id,
                entity_id=self.entity_id,
                entity_name=self.entity_name,
                status=self.run_status,
                started_after=self.started_after,
                started_before=self.started_before,
                finished_after=self.finished_after,
                finished_before=self.finished_before,
                meta_filter=self.meta_filter,
                failed_at=self.failed_at,
                order_by=self.order_by,
                sort_direction=self.sort_direction,
                include_deleted=self.include_deleted,
                include_neutralized=True,
                q=self.q,
                is_neutralized=self.is_neutralized,
                created_after=self.created_after,
                created_before=self.created_before,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


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
    api_key: RequireApiKey,
    filters: RunFilters = Depends(),
    # Pagination
    params: Params = Depends(),
) -> Page[ProcessRun]:
    """List all process runs with optional filters and sorting."""
    statement = filters.statement(run_service, api_key)

    # Paginate and add Link headers
    page_data = paginate(session, statement, params)
    add_pagination_links(request, response, page_data)

    return page_data


def _to_list_items(runs: Sequence[ProcessRun]) -> list[ProcessRunListItem]:
    """Summarise runs for the overview. Steps and process are eager-loaded."""
    items = []
    for run in runs:
        steps = [step for step in run.steps if step.deleted_at is None]
        failed = [step for step in steps if step.status == StepRunStatus.FAILED]
        duration = None
        if run.started_at and run.finished_at:
            duration = (run.finished_at - run.started_at).total_seconds()
        items.append(
            ProcessRunListItem(
                id=run.id,
                process_id=run.process_id,
                process_name=run.process.name if run.process else None,
                entity_id=run.entity_id,
                entity_name=run.entity_name,
                status=run.status,
                meta=run.meta or {},
                started_at=run.started_at,
                finished_at=run.finished_at,
                duration_seconds=duration,
                created_at=run.created_at,
                updated_at=run.updated_at,
                is_neutralized=run.is_neutralized,
                deleted_at=run.deleted_at,
                scheduled_deletion_at=run.scheduled_deletion_at,
                step_count=len(steps),
                failed_step_count=len(failed),
                failed_steps=[
                    step.step.name if step.step else f"step {step.step_index}" for step in failed
                ],
            )
        )
    return items


@router.get(
    "/overview",
    response_model=Page[ProcessRunListItem],
    summary="Runs across all processes, as table rows",
    description=(
        "The same filters, sorting and pagination as GET /runs/, but each item is a "
        "flat row: process name, timestamps, duration and step counts instead of the "
        "full steps list. Fetch GET /runs/{id} for a run's steps."
    ),
)
def list_process_runs_overview(
    request: Request,
    response: Response,
    session: SessionDep,
    run_service: RunServiceDep,
    api_key: RequireApiKey,
    filters: RunFilters = Depends(),
    params: Params = Depends(),
) -> Page[ProcessRunListItem]:
    """List runs as overview rows, with a fixed number of queries per page."""
    statement = filters.statement(run_service, api_key).options(
        selectinload(ProcessRun.steps).selectinload(ProcessStepRun.step),
        selectinload(ProcessRun.process),
    )
    page_data = paginate(session, statement, params, transformer=_to_list_items)
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


@router.patch(
    "/{run_id}/metadata",
    response_model=ProcessRunPublic,
    summary="Update existing metadata fields",
    description=(
        "Update only existing metadata fields in a process run. "
        "New fields will not be added, only existing fields will be updated."
    ),
)
def update_run_metadata(
    *,
    session: SessionDep,
    run_id: int,
    metadata_update: ProcessRunMetadataUpdate,
    service: RunServiceDep,
    admin_key: RequireAdminKey,
) -> ProcessRun:
    """Update existing metadata fields in a process run."""
    run = session.get(ProcessRun, run_id)
    if not run or run.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Process run not found")

    try:
        updated_run = service.update_run_metadata(run_id, metadata_update.meta)
        return updated_run
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
