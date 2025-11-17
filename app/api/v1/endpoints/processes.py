"""API endpoints for managing process definitions."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import paginate
from sqlmodel import select

from app.api.dependencies import (
    ProcessServiceDep,
    RequireAdminKey,
    RunServiceDep,
)
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
    "/{process_id}/filter-metadata",
    summary="Get combined filter metadata for process",
    description=(
        "Get all searchable/filterable field definitions AND "
        "available metadata filter values in a single request. "
        "Combines data from field schemas and actual run data."
    ),
)
def get_filter_metadata(
    *,
    process_service: ProcessServiceDep,
    run_service: RunServiceDep,
    process_id: int,
) -> dict[str, Any]:
    """
    Get combined filter metadata for a process.

    Returns both:
    - Field definitions (types, descriptions, sortable/filterable info)
    - Actual metadata filter values from existing runs

    This single endpoint provides all the data needed to build
    a complete search/filter UI.

    Example response:
    {
        "process_id": 1,
        "process_name": "Aktindsigt Process",
        "searchable_fields": {
            "standard_fields": {...},
            "metadata_fields": {...}
        },
        "metadata_filters": {
            "clinic": ["Viby", "Aarhus"],
            "patient_id": ["12345", "67890"]
        },
        ...
    }
    """
    return process_service.get_filter_metadata(process_id, run_service)


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
