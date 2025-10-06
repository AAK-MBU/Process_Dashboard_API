"""Business logic for process definitions."""

from typing import Any

from sqlmodel import Session, select

from app.core.exceptions import ProcessNotFoundError
from app.models import Process, ProcessCreate


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

    def get_process(self, process_id: int) -> Process:
        """
        Get a process by ID.

        Args:
            process_id: ID of the process to retrieve

        Returns:
            Process object

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        process = self.db.get(Process, process_id)
        if not process:
            raise ProcessNotFoundError(process_id)
        return process

    def list_processes(self, skip: int = 0, limit: int = 100) -> list[Process]:
        """
        List all processes with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Process objects
        """
        statement = select(Process).order_by(Process.id).offset(skip).limit(limit)
        processes = self.db.exec(statement).all()
        return list(processes)

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
        Delete a process definition.

        Args:
            process_id: ID of the process to delete

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        process = self.get_process(process_id)
        self.db.delete(process)
        self.db.commit()
