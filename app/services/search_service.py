"""Search service for querying process runs based on various parameters."""

from typing import Any

from sqlalchemy import or_, text
from sqlmodel import Session, select

from app.models import MatchedField, ProcessRun
from app.services.process_service import ProcessService


class SearchService:
    """Service for searching process runs."""

    def __init__(self, db: Session):
        self.db = db
        self.process_service = ProcessService(db)

    def search_items(
        self,
        search_params: str,
        process_id: int | None = None,
    ):
        """Search items based on query and optional filters."""
        statement = select(ProcessRun).where(ProcessRun.deleted_at.is_(None))
        or_conditions = []
        search_pattern = f"%{search_params}%"

        or_conditions.append(ProcessRun.entity_id.ilike(search_pattern))
        or_conditions.append(ProcessRun.entity_name.ilike(search_pattern))
        or_conditions.append(ProcessRun.status.ilike(search_pattern))

        if process_id is not None:
            statement = statement.where(ProcessRun.process_id == process_id)

            try:
                fields_info = self.process_service.get_searchable_fields(process_id)
                metadata_fields = fields_info.get("metadata_fields", {})

                for field_name in metadata_fields.keys():
                    or_conditions.append(
                        text(f"JSON_VALUE(process_run.meta, '$.{field_name}') LIKE :search")
                    )
            except Exception:
                pass

        statement = statement.where(or_(*or_conditions))

        if process_id is not None:
            try:
                fields_info = self.process_service.get_searchable_fields(process_id)
                metadata_fields = fields_info.get("metadata_fields", {})
                if metadata_fields:
                    statement = statement.params(search=search_pattern)
            except Exception:
                pass

        return statement.order_by(ProcessRun.created_at.desc())

    def annotate_matches(
        self,
        runs: list[ProcessRun],
        search_term: str,
        process_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Annotate search results with matched field information.

        Args:
            runs: List of ProcessRun objects from search results
            search_term: The search term used
            process_id: Optional process ID to get metadata fields

        Returns:
            List of dicts with 'run' and 'matches' keys
        """
        term = search_term.lower()
        annotated = []

        searchable_meta: list[str] = []
        if process_id is not None:
            try:
                fields_info = self.process_service.get_searchable_fields(process_id)
                searchable_meta = list(fields_info.get("metadata_fields", {}).keys())
            except Exception:
                pass

        from app.models import ProcessRunPublic

        for run in runs:
            matches: list[MatchedField] = []

            if run.entity_id and term in str(run.entity_id).lower():
                matches.append(MatchedField(field="entity_id", value=run.entity_id))

            if run.entity_name and term in str(run.entity_name).lower():
                matches.append(MatchedField(field="entity_name", value=run.entity_name))

            if run.status and term in str(run.status).lower():
                matches.append(MatchedField(field="status", value=run.status))

            if run.meta and searchable_meta:
                for field_name in searchable_meta:
                    field_value = run.meta.get(field_name)
                    if field_value is None:
                        continue

                    str_value = str(field_value).lower()
                    if term in str_value:
                        matches.append(
                            MatchedField(
                                field=f"meta.{field_name}",
                                value=field_value,
                            )
                        )

            # Use ProcessRunPublic for serialization
            run_public = ProcessRunPublic.model_validate(run)
            run_dict = run_public.model_dump()
            run_dict["matches"] = [m.model_dump() for m in matches]
            annotated.append(run_dict)

        return annotated
