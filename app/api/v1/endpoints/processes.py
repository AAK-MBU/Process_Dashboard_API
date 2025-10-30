"""API endpoints for managing process definitions."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import paginate
from sqlmodel import select

from app.api.dependencies import RequireAdminKey
from app.core.pagination import add_pagination_links
from app.db.database import SessionDep
from app.models import Process, ProcessCreate, ProcessPublic, RetentionUpdate
from app.services import ProcessService

router = APIRouter()


@router.post(
    "/",
    response_model=ProcessPublic,
    status_code=201,
    summary="Create a new process",
    description="Create a new process definition with metadata",
)
def create_process(
    *, session: SessionDep, process_in: ProcessCreate, admin_key: RequireAdminKey
) -> Process:
    """Create a new process."""
    process = Process.model_validate(process_in)
    session.add(process)
    session.commit()
    session.refresh(process)
    return process


@router.get(
    "/",
    response_model=Page[ProcessPublic],
    summary="List all processes",
    description="Retrieve a list of all process definitions with pagination",
)
def list_processes(
    request: Request,
    response: Response,
    session: SessionDep,
    params: Params = Depends(),
) -> Page[Process]:
    """List all processes with pagination."""
    statement = select(Process).where(Process.deleted_at.is_(None)).order_by("id")
    page_data = paginate(session, statement, params)

    # Add Link headers for pagination navigation
    add_pagination_links(request, response, page_data)

    return page_data


@router.get(
    "/{process_id}",
    response_model=ProcessPublic,
    summary="Get process by ID",
    description="Retrieve a specific process definition including its steps",
)
def get_process(*, session: SessionDep, process_id: int) -> Process:
    """Get a specific process by ID."""
    process = session.get(Process, process_id)
    if not process or process.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Process not found")
    return process


@router.get(
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
            "values": [
                "pending", "running", "completed", "failed", "cancelled"
            ],
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

    metadata_schema = process.meta.get("run_metadata_schema", {})

    try:
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


@router.delete(
    "/{process_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a process",
    description="Soft delete a process and its steps (runs are not affected)",
)
def delete_process(*, session: SessionDep, process_id: int, admin_key: RequireAdminKey) -> None:
    """Soft delete a process."""
    service = ProcessService(session)
    try:
        service.delete_process(process_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/{process_id}/restore",
    response_model=ProcessPublic,
    summary="Restore a soft-deleted process",
    description="Restore a previously soft-deleted process and its steps",
)
def restore_process(*, session: SessionDep, process_id: int, admin_key: RequireAdminKey) -> Process:
    """Restore a soft-deleted process."""
    service = ProcessService(session)
    try:
        return service.restore_process(process_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put(
    "/{process_id}/retention",
    response_model=ProcessPublic,
    summary="Update retention period",
    description=(
        "Update the retention period for a process. "
        "This determines how long before runs are neutralized. "
        "Set to null for no automatic neutralization."
    ),
)
def update_retention(
    *,
    session: SessionDep,
    process_id: int,
    retention: RetentionUpdate,
    admin_key: RequireAdminKey,
) -> Process:
    """Update retention period for a process."""
    service = ProcessService(session)
    try:
        return service.update_retention_period(process_id, retention.retention_months)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
