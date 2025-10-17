"""Business logic for process runs."""

from datetime import timedelta

from sqlalchemy import text
from sqlmodel import Session, select

from app.core.exceptions import ProcessNotFoundError, RunNotFoundError
from app.models import (
    Process,
    ProcessRun,
    ProcessRunCreate,
    ProcessStepRun,
)


class ProcessRunService:
    """Service for managing process runs."""

    def __init__(self, db: Session):
        self.db = db

    def create_run_with_steps(
        self,
        run_data: ProcessRunCreate,
    ) -> ProcessRun:
        """
        Create a new process run and initialize all step runs.

        Args:
            run_data: Process run creation data

        Returns:
            Created ProcessRun with all step runs initialized

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        # Verify process exists
        process = self.db.get(Process, run_data.process_id)
        if not process:
            raise ProcessNotFoundError(run_data.process_id)

        # Create the run
        run = ProcessRun.model_validate(run_data)

        # Calculate scheduled deletion based on process retention policy
        if process.retention_months:
            run.scheduled_deletion_at = run.created_at + timedelta(
                days=30 * process.retention_months
            )

        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        # Create step runs for all process steps
        for step in process.steps:
            step_run = self._create_step_run_from_template(run.id, step)
            self.db.add(step_run)

        self.db.commit()
        self.db.refresh(run)
        return run

    def _create_step_run_from_template(self, run_id: int, step) -> ProcessStepRun:
        """Create a step run from a step template."""
        max_reruns = 0
        rerun_config = {}

        if step.is_rerunnable:
            rerun_config = step.rerun_config.copy() if step.rerun_config else {}
            max_reruns = step.rerun_config.get("max_retries", 3) if step.rerun_config else 3

        return ProcessStepRun(
            run_id=run_id,
            step_id=step.id,
            can_rerun=step.is_rerunnable,
            rerun_config=rerun_config,
            max_reruns=max_reruns,
        )

    def get_run(self, run_id: int) -> ProcessRun:
        """
        Get a process run by ID.

        Raises:
            RunNotFoundError: If run doesn't exist
        """
        run = self.db.get(ProcessRun, run_id)
        if not run:
            raise RunNotFoundError(run_id)
        return run

    def list_runs(
        self,
        process_id: int | None = None,
        entity_id: str | None = None,
        entity_name: str | None = None,
        status: str | None = None,
        started_after: str | None = None,
        started_before: str | None = None,
        finished_after: str | None = None,
        finished_before: str | None = None,
        meta_filter: list[str] | None = None,
        order_by: str = "created_at",
        sort_direction: str = "desc",
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        include_neutralized: bool = True,
    ) -> list[ProcessRun]:
        """
        List process runs with filtering and sorting.

        Args:
            include_deleted: If True, include soft-deleted runs
            include_neutralized: If True, include neutralized runs

        Returns:
            List of ProcessRun objects matching filters
        """
        statement = select(ProcessRun)

        # Filter out soft-deleted runs unless explicitly requested
        if not include_deleted:
            statement = statement.where(ProcessRun.deleted_at.is_(None))

        # Filter out neutralized runs if requested
        if not include_neutralized:
            statement = statement.where(ProcessRun.is_neutralized == False)  # noqa

        # Apply other filters
        statement = self._apply_basic_filters(statement, process_id, entity_id, entity_name, status)
        statement = self._apply_date_filters(
            statement, started_after, started_before, finished_after, finished_before
        )
        statement = self._apply_metadata_filters(statement, meta_filter)
        statement = self._apply_sorting(statement, order_by, sort_direction)

        # Pagination
        statement = statement.offset(skip).limit(limit)

        runs = self.db.exec(statement).all()
        return list(runs)

    def build_filtered_statement(
        self,
        process_id: int | None = None,
        entity_id: str | None = None,
        entity_name: str | None = None,
        status: str | None = None,
        started_after: str | None = None,
        started_before: str | None = None,
        finished_after: str | None = None,
        finished_before: str | None = None,
        meta_filter: list[str] | None = None,
        order_by: str = "created_at",
        sort_direction: str = "desc",
        include_deleted: bool = False,
        include_neutralized: bool = False,
    ):
        """
        Build a filtered and sorted SQLModel statement for process runs.

        Args:
            include_deleted: If True, include soft-deleted runs
            include_neutralized: If True, include neutralized runs

        Returns:
            SQLModel Select statement with all filters and sorting applied

        Raises:
            ValueError: If meta_filter format is invalid
        """
        statement = select(ProcessRun)

        # Filter out soft-deleted runs unless explicitly requested
        if not include_deleted:
            statement = statement.where(ProcessRun.deleted_at.is_(None))

        # Filter out neutralized runs if requested
        if not include_neutralized:
            statement = statement.where(ProcessRun.is_neutralized == False)  # noqa

        # Apply filters
        statement = self._apply_basic_filters(statement, process_id, entity_id, entity_name, status)
        statement = self._apply_date_filters(
            statement, started_after, started_before, finished_after, finished_before
        )
        statement = self._apply_metadata_filters(statement, meta_filter)
        statement = self._apply_sorting(statement, order_by, sort_direction)

        return statement

    def _apply_basic_filters(
        self,
        statement,
        process_id: int | None,
        entity_id: str | None,
        entity_name: str | None,
        status: str | None,
    ):
        """Apply basic filters to query."""
        if process_id:
            statement = statement.where(ProcessRun.process_id == process_id)
        if entity_id:
            statement = statement.where(ProcessRun.entity_id == entity_id)
        if entity_name:
            statement = statement.where(ProcessRun.entity_name.contains(entity_name))
        if status:
            statement = statement.where(ProcessRun.status == status)
        return statement

    def _apply_date_filters(
        self,
        statement,
        started_after: str | None,
        started_before: str | None,
        finished_after: str | None,
        finished_before: str | None,
    ):
        """Apply date range filters to query."""
        if started_after:
            statement = statement.where(ProcessRun.started_at >= started_after)
        if started_before:
            statement = statement.where(ProcessRun.started_at <= started_before)
        if finished_after:
            statement = statement.where(ProcessRun.finished_at >= finished_after)
        if finished_before:
            statement = statement.where(ProcessRun.finished_at <= finished_before)
        return statement

    def _apply_metadata_filters(self, statement, meta_filter: list[str] | None):
        """Apply metadata filters to query.

        Multiple values for the same field are OR'd together.
        Different fields are AND'd together.

        Raises:
            ValueError: If meta_filter format is invalid
        """
        if not meta_filter:
            return statement

        # Validate format and group filters by field
        from collections import defaultdict

        filters_by_field = defaultdict(list)

        for filter_item in meta_filter:
            if ":" not in filter_item:
                raise ValueError(
                    f"Invalid meta_filter format: '{filter_item}'. Expected format: 'field:value'"
                )
            field, value = filter_item.split(":", 1)
            field = field.strip()
            value = value.strip()
            if not field:
                raise ValueError(
                    f"Invalid meta_filter format: '{filter_item}'. Field name cannot be empty"
                )
            filters_by_field[field].append(value)

        # Apply filters: OR within same field, AND across different fields
        for field, values in filters_by_field.items():
            if len(values) == 1:
                # Single value: simple equality
                statement = statement.where(
                    text(f"JSON_VALUE(process_run.meta, '$.{field}') = :meta_{field}")
                ).params(**{f"meta_{field}": values[0]})
            else:
                # Multiple values: OR them together
                or_conditions = []
                sql_params = {}
                for idx, value in enumerate(values):
                    param_name = f"meta_{field}_{idx}"
                    or_conditions.append(
                        f"JSON_VALUE(process_run.meta, '$.{field}') = :{param_name}"
                    )
                    sql_params[param_name] = value
                statement = statement.where(text(" OR ".join(or_conditions))).params(**sql_params)
        return statement

    def _apply_sorting(self, statement, order_by: str, sort_direction: str):
        """Apply sorting to query."""
        if order_by.startswith("meta."):
            # Sort by JSON field
            json_field = order_by.replace("meta.", "")
            direction = "DESC" if sort_direction.lower() == "desc" else "ASC"
            statement = statement.order_by(
                text(f"JSON_VALUE(process_run.meta, '$.{json_field}') {direction}")
            )
        else:
            # Sort by regular field
            column = getattr(ProcessRun, order_by, ProcessRun.created_at)
            if sort_direction.lower() == "desc":
                statement = statement.order_by(column.desc())
            else:
                statement = statement.order_by(column.asc())
        return statement
