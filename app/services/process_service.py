"""Business logic for process definitions."""

from typing import Any

from sqlmodel import Session, select

from app.core.exceptions import ProcessNotFoundError
from app.models import Process, ProcessCreate
from app.utils.datetime_utils import utc_now


class ProcessService:
    """Service for managing process definitions."""

    def __init__(self, db: Session):
        self.db = db

    def create_process(self, process_data: ProcessCreate) -> Process:
        """
        Create a new process definition.

        Args:
            process_data: Process creation data

        Returns:
            Created Process object
        """
        process = Process.model_validate(process_data)
        self.db.add(process)
        self.db.commit()
        self.db.refresh(process)
        return process

    def get_process(self, process_id: int, include_deleted: bool = False) -> Process:
        """
        Get a process by ID.

        Args:
            process_id: ID of the process to retrieve
            include_deleted: If True, include soft-deleted processes

        Returns:
            Process object

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        process = self.db.get(Process, process_id)
        if not process:
            raise ProcessNotFoundError(process_id)

        # Check if process is soft-deleted
        if not include_deleted and process.deleted_at is not None:
            raise ProcessNotFoundError(process_id)

        return process

    def list_processes(
        self, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> list[Process]:
        """
        List all processes with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: If True, include soft-deleted processes

        Returns:
            List of Process objects
        """
        statement = select(Process)

        # Filter out soft-deleted processes unless explicitly requested
        if not include_deleted:
            statement = statement.where(Process.deleted_at.is_(None))

        statement = statement.order_by(Process.id).offset(skip).limit(limit)
        processes = self.db.exec(statement).all()
        return list(processes)

    def get_filter_metadata(self, process_id: int, run_service=None) -> dict[str, Any]:
        """
        Get combined filter metadata for a process.

        This includes searchable/filterable field definitions AND
        actual metadata filter values from existing runs.

        Args:
            process_id: ID of the process
            run_service: RunService instance for getting filter options

        Returns:
            Dictionary containing field definitions and filter values

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        process = self.get_process(process_id)

        # Get field definitions
        standard_fields = self._get_standard_fields()
        metadata_schema = process.meta.get("run_metadata_schema", {})
        metadata_fields = self._build_metadata_fields(metadata_schema)

        # Get actual filter values if run_service provided
        metadata_filter_values = {}
        if run_service:
            try:
                metadata_filter_values = run_service.get_metadata_filter_options(
                    process_id, self.db
                )
            except Exception:
                # If error getting filter values, continue without
                pass

        return {
            "process_id": process_id,
            "process_name": process.name,
            "searchable_fields": {
                "standard_fields": standard_fields,
                "metadata_fields": metadata_fields,
            },
            "metadata_filters": metadata_filter_values,
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
                "metadata": ("Use meta_filter parameter with format 'field:value'"),
                "dates": ("Use ISO format for date filters (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"),
                "partial_match": "entity_name supports partial matching",
            },
        }

    def get_searchable_fields(self, process_id: int) -> dict[str, Any]:
        """
        Get all searchable and filterable fields for a process.

        This includes both standard fields and metadata fields defined
        in the process's run_metadata_schema.

        Args:
            process_id: ID of the process

        Returns:
            Dictionary containing field definitions

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        process = self.get_process(process_id)

        # Standard fields available for all processes
        standard_fields = self._get_standard_fields()

        # Get metadata schema from process definition
        metadata_schema = process.meta.get("run_metadata_schema", {})

        # Build metadata fields info
        metadata_fields = self._build_metadata_fields(metadata_schema)

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

    def _get_standard_fields(self) -> dict[str, Any]:
        """Get standard fields available for all processes."""
        return {
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
                "values": ["pending", "running", "completed", "failed", "cancelled"],
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

    def _build_metadata_fields(self, metadata_schema: dict) -> dict[str, Any]:
        """Build metadata field definitions from schema."""
        metadata_fields = {}
        for field, field_type in metadata_schema.items():
            field_info = {
                "type": field_type,
                "description": f"Metadata field: {field}",
                "sortable": True,
                "filterable": True,
                "sortable_as": f"meta.{field}",
                "filter_format": "meta_filter parameter: field:value",
            }
            metadata_fields[field] = field_info
        return metadata_fields

    def update_process(self, process_id: int, update_data: dict[str, Any]) -> Process:
        """
        Update a process definition.

        Args:
            process_id: ID of the process to update
            update_data: Dictionary of fields to update

        Returns:
            Updated Process object

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        process = self.get_process(process_id)

        for key, value in update_data.items():
            if hasattr(process, key):
                setattr(process, key, value)

        self.db.add(process)
        self.db.commit()
        self.db.refresh(process)
        return process

    def delete_process(self, process_id: int) -> None:
        """
        Soft delete a process definition and its steps.

        This marks the process and all its steps as deleted without
        removing them from the database. Runs are not affected.

        Args:
            process_id: ID of the process to delete

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        process = self.get_process(process_id)
        now = utc_now()

        # Soft delete the process
        process.deleted_at = now

        # Soft delete all steps
        for step in process.steps:
            step.deleted_at = now
            self.db.add(step)

        self.db.add(process)
        self.db.commit()

    def restore_process(self, process_id: int) -> Process:
        """
        Restore a soft-deleted process and its steps.

        Args:
            process_id: ID of the process to restore

        Returns:
            Restored Process object

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        process = self.get_process(process_id, include_deleted=True)

        # Restore the process
        process.deleted_at = None

        # Restore all steps
        for step in process.steps:
            step.deleted_at = None
            self.db.add(step)

        self.db.add(process)
        self.db.commit()
        self.db.refresh(process)

        return process

    def update_retention_period(self, process_id: int, retention_months: int | None) -> Process:
        """
        Update retention period for a process.

        Args:
            process_id: ID of the process to update
            retention_months: Retention period in months, or None for no limit

        Returns:
            Updated Process object

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        process = self.get_process(process_id)
        process.retention_months = retention_months

        self.db.add(process)
        self.db.commit()
        self.db.refresh(process)

        return process
