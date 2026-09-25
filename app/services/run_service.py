"""Business logic for process runs."""

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, literal_column, or_, text
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.core.exceptions import ProcessNotFoundError, RunNotFoundError
from app.models import (
    Process,
    ProcessRun,
    ProcessRunCreate,
    ProcessStepRun,
)
from app.models.enums import ProcessRunStatus

# Plain columns a run list may be sorted by. ``process_name``, ``duration`` and
# ``meta.<field>`` are handled separately in ``_apply_sorting``.
SORTABLE_RUN_COLUMNS = frozenset(
    {
        "id",
        "process_id",
        "entity_id",
        "entity_name",
        "status",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
        "is_neutralized",
        "deleted_at",
        "scheduled_deletion_at",
    }
)

# One segment of a metadata path: letters (incl. æøå), digits, _, - and space.
# Anything else — above all quotes and backslashes — could break out of the
# SQL string literal the path is embedded in.
_META_SEGMENT = re.compile(r"^[\w\- ]{1,128}$")


# ``meta`` is a TEXT column (``UnicodeJSON`` over ``TEXT``), and SQL Server's
# JSON_VALUE rejects TEXT outright ("Argument data type text is invalid"), so
# every JSON function must read it through this cast.
META_JSON = "CAST(process_run.meta AS NVARCHAR(MAX))"


def json_path(field: str) -> str:
    """Build a quoted JSON path (``$."a"."b"``) from a validated field name.

    Dots separate nested keys, as they did before quoting was added.

    Raises:
        ValueError: If any segment contains a character outside ``_META_SEGMENT``
    """
    segments = field.split(".")
    for segment in segments:
        if not _META_SEGMENT.match(segment):
            raise ValueError(
                f"Invalid metadata field: '{field}'. Use letters, digits, '_', '-' or "
                "spaces, with '.' between nested keys"
            )
    return "$." + ".".join(f'"{segment}"' for segment in segments)


def _parse_statuses(value: str) -> list[ProcessRunStatus]:
    """Parse ``failed`` or ``failed,cancelled`` into run statuses.

    Raises:
        ValueError: On an unknown status
    """
    statuses = []
    for raw in value.split(","):
        raw = raw.strip().lower()
        if not raw:
            continue
        try:
            statuses.append(ProcessRunStatus(raw))
        except ValueError:
            allowed = ", ".join(s.value for s in ProcessRunStatus)
            raise ValueError(f"Invalid run_status: '{raw}'. Use one of {allowed}") from None
    if not statuses:
        raise ValueError("run_status cannot be empty")
    return statuses


def _parse_date(name: str, value: str) -> datetime:
    """Parse an ISO date or datetime query value.

    Raises:
        ValueError: If the value is not ISO 8601
    """
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Invalid {name}: '{value}'. Expected an ISO 8601 date") from None
    # The columns hold naive UTC, so an offset-aware bound is converted rather
    # than compared as-is (which would silently shift it by the offset).
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards (SQL Server also treats ``[`` as one)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace("[", "\\[")


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
        statement = (
            select(Process)
            .where(Process.id == run_data.process_id)
            .options(selectinload(Process.steps))
        )
        process = self.db.exec(statement).first()

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

    def update_run_metadata(self, run_id: int, metadata_update: dict[str, any]) -> ProcessRun:
        """
        Update only existing metadata fields in a process run.

        Args:
            run_id: ID of the process run to update
            metadata_update: Dictionary of metadata fields to update

        Returns:
            Updated ProcessRun object

        Raises:
            RunNotFoundError: If run doesn't exist
            ValueError: If any provided metadata keys don't exist in current
                metadata
        """
        statement = (
            select(ProcessRun)
            .where(ProcessRun.id == run_id)
            .options(selectinload(ProcessRun.steps))
        )
        run = self.db.exec(statement).first()

        if not run:
            raise RunNotFoundError(run_id)

        # Check that all provided keys exist in current metadata
        current_meta = run.meta or {}

        # If the run has no metadata and we're trying to add some, reject it
        if not current_meta and metadata_update:
            raise ValueError(
                "Cannot update metadata: run has no existing metadata fields. Existing keys: []"
            )

        unknown_keys = set(metadata_update.keys()) - set(current_meta.keys())

        if unknown_keys:
            unknown_keys_list = sorted(list(unknown_keys))
            existing_keys_list = sorted(list(current_meta.keys()))
            raise ValueError(
                f"Unknown metadata keys: {unknown_keys_list}. Existing keys: {existing_keys_list}"
            )

        # Update the metadata with new values
        updated_meta = current_meta.copy()
        updated_meta.update(metadata_update)

        # Update the run
        run.meta = updated_meta
        self.db.commit()
        self.db.refresh(run)

        return run

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
        failed_at: int | None = None,
        order_by: str = "created_at",
        sort_direction: str = "desc",
        include_deleted: bool = False,
        include_neutralized: bool = False,
        q: str | None = None,
        is_neutralized: bool | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ):
        """
        Build a filtered and sorted SQLModel statement for process runs.

        Args:
            status: One status, or several separated by commas (OR'd)
            include_deleted: If True, include soft-deleted runs
            include_neutralized: If True, include neutralized runs
            failed_at: If provided, filter runs that failed at this specific step_id
            q: Free text, matched against entity_id, entity_name and the run's
                top-level metadata values
            is_neutralized: If set, only runs with this neutralization state

        Returns:
            SQLModel Select statement with all filters and sorting applied

        Raises:
            ValueError: On an invalid status, date, metadata field or sort field
        """
        statement = select(ProcessRun)

        # Filter out soft-deleted runs unless explicitly requested
        if not include_deleted:
            statement = statement.where(ProcessRun.deleted_at.is_(None))

        # Filter out neutralized runs if requested
        if not include_neutralized:
            statement = statement.where(ProcessRun.is_neutralized == False)  # noqa
        if is_neutralized is not None:
            statement = statement.where(ProcessRun.is_neutralized == is_neutralized)  # noqa

        # Apply filters
        statement = self._apply_basic_filters(statement, process_id, entity_id, entity_name, status)
        statement = self._apply_date_filters(
            statement, started_after, started_before, finished_after, finished_before
        )
        statement = self._apply_created_filters(statement, created_after, created_before)
        statement = self._apply_metadata_filters(statement, meta_filter)
        statement = self._apply_failed_at_filter(statement, failed_at)
        statement = self._apply_search(statement, q)
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
        if process_id is not None:
            statement = statement.where(ProcessRun.process_id == process_id)
        if entity_id:
            statement = statement.where(ProcessRun.entity_id == entity_id)
        if entity_name:
            statement = statement.where(ProcessRun.entity_name.contains(entity_name))
        if status:
            statuses = _parse_statuses(status)
            if len(statuses) == 1:
                statement = statement.where(ProcessRun.status == statuses[0])
            else:
                statement = statement.where(ProcessRun.status.in_(statuses))
        return statement

    def _apply_date_filters(
        self,
        statement,
        started_after: str | None,
        started_before: str | None,
        finished_after: str | None,
        finished_before: str | None,
    ):
        """Apply date range filters to query. Bounds are inclusive."""
        if started_after:
            statement = statement.where(
                ProcessRun.started_at >= _parse_date("started_after", started_after)
            )
        if started_before:
            statement = statement.where(
                ProcessRun.started_at <= _parse_date("started_before", started_before)
            )
        if finished_after:
            statement = statement.where(
                ProcessRun.finished_at >= _parse_date("finished_after", finished_after)
            )
        if finished_before:
            statement = statement.where(
                ProcessRun.finished_at <= _parse_date("finished_before", finished_before)
            )
        return statement

    def _apply_created_filters(
        self, statement, created_after: str | None, created_before: str | None
    ):
        """Apply created_at range filters. Bounds are inclusive."""
        if created_after:
            statement = statement.where(
                ProcessRun.created_at >= _parse_date("created_after", created_after)
            )
        if created_before:
            statement = statement.where(
                ProcessRun.created_at <= _parse_date("created_before", created_before)
            )
        return statement

    def _apply_metadata_filters(self, statement, meta_filter: list[str] | None):
        """Apply metadata filters to query.

        Multiple values for the same field are OR'd together.
        Different fields are AND'd together.

        The field name ends up inside a SQL string literal (the JSON path), so it
        is validated and quoted by ``json_path`` rather than interpolated raw.
        The value is always a bound parameter.

        Raises:
            ValueError: If meta_filter format or a field name is invalid
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

        # Apply filters: OR within same field, AND across different fields.
        # Parameter names are positional, never derived from the field name.
        for field_idx, (field, values) in enumerate(filters_by_field.items()):
            path = json_path(field)
            conditions = []
            sql_params = {}
            for value_idx, value in enumerate(values):
                param_name = f"meta_{field_idx}_{value_idx}"
                conditions.append(f"JSON_VALUE({META_JSON}, '{path}') = :{param_name}")
                sql_params[param_name] = value
            clause = conditions[0] if len(conditions) == 1 else f"({' OR '.join(conditions)})"
            statement = statement.where(text(clause).bindparams(**sql_params))
        return statement

    def _apply_failed_at_filter(self, statement, failed_at: int | None):
        """Apply filter for runs that failed at a specific step_id.

        An EXISTS rather than a join, so a run with more than one failed step run
        for the same step is still listed once.

        Args:
            statement: The SQLModel statement to filter
            failed_at: The step_id to filter by

        Returns:
            Filtered statement showing only runs that failed at the given step
        """
        if failed_at is None:
            return statement

        from app.models.enums import StepRunStatus

        failed_step = (
            select(ProcessStepRun.id)
            .where(
                ProcessStepRun.run_id == ProcessRun.id,
                ProcessStepRun.step_id == failed_at,
                ProcessStepRun.status == StepRunStatus.FAILED,
                ProcessStepRun.deleted_at.is_(None),
            )
            .exists()
        )
        return statement.where(failed_step)

    def _apply_search(self, statement, q: str | None):
        """Free-text match on entity_id, entity_name and top-level metadata values.

        Metadata is searched across every process (unlike ``/runs/search``, which
        only reads a process's declared schema). ``OPENJSON`` walks the stored
        JSON so keys are never matched, only string/number/boolean values.
        ``meta`` is a TEXT column, hence the cast; ``ISJSON`` keeps a malformed
        row from failing the whole query.
        """
        if not q or not q.strip():
            return statement
        like = f"%{_escape_like(q.strip())}%"
        meta_match = text(
            "EXISTS (SELECT 1 FROM OPENJSON("
            f"CASE WHEN ISJSON({META_JSON}) = 1 THEN {META_JSON} END) AS meta_kv "
            "WHERE meta_kv.[type] IN (1, 2, 3) AND meta_kv.[value] LIKE :q_like ESCAPE '\\')"
        ).bindparams(q_like=like)
        return statement.where(
            or_(
                ProcessRun.entity_id.ilike(like, escape="\\"),
                ProcessRun.entity_name.ilike(like, escape="\\"),
                meta_match,
            )
        )

    def _apply_sorting(self, statement, order_by: str, sort_direction: str):
        """Apply sorting to query, with ``id`` as a tie-breaker for stable paging.

        Raises:
            ValueError: If order_by is not a sortable field
        """
        descending = sort_direction.lower() == "desc"
        if order_by.startswith("meta."):
            # Sort by JSON field
            path = json_path(order_by[len("meta.") :])
            direction = "DESC" if descending else "ASC"
            statement = statement.order_by(text(f"JSON_VALUE({META_JSON}, '{path}') {direction}"))
        elif order_by == "process_name":
            statement = statement.outerjoin(Process, Process.id == ProcessRun.process_id)
            statement = statement.order_by(
                Process.name.desc() if descending else Process.name.asc()
            )
        elif order_by == "duration":
            duration = func.datediff(
                literal_column("second"), ProcessRun.started_at, ProcessRun.finished_at
            )
            statement = statement.order_by(duration.desc() if descending else duration.asc())
        elif order_by in SORTABLE_RUN_COLUMNS:
            column = getattr(ProcessRun, order_by)
            statement = statement.order_by(column.desc() if descending else column.asc())
        else:
            allowed = ", ".join(sorted(SORTABLE_RUN_COLUMNS | {"process_name", "duration"}))
            raise ValueError(
                f"Invalid order_by: '{order_by}'. Use one of {allowed}, or meta.<field>"
            )
        if order_by == "id":
            # SQL Server rejects a column listed twice in ORDER BY.
            return statement
        return statement.order_by(ProcessRun.id.desc() if descending else ProcessRun.id.asc())

    def get_metadata_filter_options(
        self, process_id: int, session: Session
    ) -> dict[str, list[str]]:
        """
        Get all unique metadata values for a specific process.

        Returns a dictionary where keys are metadata field names and values
        are sorted lists of unique values found in that field across all
        process runs for the given process.

        Args:
            process_id: The process ID to get metadata options for
            session: The database session

        Returns:
            Dictionary mapping field names to lists of unique values
            Example: {"clinic": ["Viby", "Aarhus"], "cpr":
                     ["123456", "789012"]}

        Raises:
            ProcessNotFoundError: If process doesn't exist
        """
        # Verify process exists
        process = session.get(Process, process_id)
        if not process:
            raise ProcessNotFoundError(process_id)

        # Get all runs for this process with their metadata
        statement = (
            select(ProcessRun)
            .where(ProcessRun.process_id == process_id)
            .where(ProcessRun.deleted_at.is_(None))
        )

        runs = session.exec(statement).all()

        # Collect all unique values for each metadata field
        metadata_options: dict[str, set[str]] = {}

        for run in runs:
            if run.meta:
                for key, value in run.meta.items():
                    if key not in metadata_options:
                        metadata_options[key] = set()

                    # Convert value to string for consistent filtering
                    if value is not None:
                        metadata_options[key].add(str(value))

        # Convert sets to sorted lists for consistent output
        result = {key: sorted(list(values)) for key, values in metadata_options.items()}

        return result
