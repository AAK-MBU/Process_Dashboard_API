"""Service for data retention and neutralization of sensitive data."""

from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import Process, ProcessRun
from app.utils.datetime_utils import utc_now


class DataRetentionService:
    """Service for managing data retention and neutralization."""

    def __init__(self, db: Session):
        self.db = db

    def calculate_scheduled_deletion(self, process: Process, run_created_at) -> datetime | None:
        """
        Calculate when a run should be neutralized based on process retention.

        Args:
            process: Process with retention_months setting
            run_created_at: When the run was created

        Returns:
            Datetime when neutralization should occur, or None if no retention
        """
        if not process.retention_months:
            return None

        # Calculate deletion date based on retention period
        deletion_date = run_created_at + timedelta(days=30 * process.retention_months)
        return deletion_date

    def neutralize_run_data(self, run: ProcessRun) -> ProcessRun:
        """
        Neutralize sensitive data in a process run.

        This removes personally identifiable information while keeping
        the run record for statistical purposes.

        Args:
            run: ProcessRun to neutralize

        Returns:
            Neutralized ProcessRun
        """
        if run.is_neutralized:
            return run  # Already neutralized

        # Neutralize sensitive fields
        run.entity_id = f"NEUTRALIZED_{run.id}"
        run.entity_name = None

        # Clear sensitive metadata but keep structure
        if run.meta:
            run.meta = self._neutralize_metadata(run.meta)

        # Mark as neutralized
        run.is_neutralized = True

        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        return run

    def _neutralize_metadata(self, meta: dict) -> dict:
        """
        Neutralize sensitive metadata fields.

        Keeps statistical data but removes PII.
        Override this method to customize what to keep/remove.
        """
        # List of metadata keys that are considered safe to keep
        safe_keys = {
            "category",
            "type",
            "department",
            "status_code",
            # Add other non-sensitive keys as needed
        }

        neutralized = {}
        for key, value in meta.items():
            if key in safe_keys:
                neutralized[key] = value
            # Replace sensitive values with placeholder
            elif isinstance(value, str):
                neutralized[key] = "[NEUTRALIZED]"
            elif isinstance(value, (int, float)):
                neutralized[key] = 0
            elif isinstance(value, bool):
                neutralized[key] = False

        return neutralized

    def get_runs_due_for_neutralization(self, limit: int = 100) -> list[ProcessRun]:
        """
        Get runs that are due for neutralization.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of ProcessRuns that should be neutralized
        """
        now = utc_now()

        statement = (
            select(ProcessRun)
            .where(ProcessRun.scheduled_deletion_at <= now)
            .where(ProcessRun.is_neutralized == False)  # noqa: E712
            .where(ProcessRun.deleted_at.is_(None))
            .limit(limit)
        )

        runs = self.db.exec(statement).all()
        return list(runs)

    def neutralize_due_runs(self, batch_size: int = 100) -> dict:
        """
        Neutralize all runs that are due for neutralization.

        Args:
            batch_size: Number of runs to process in one batch

        Returns:
            Dictionary with neutralization statistics
        """
        due_runs = self.get_runs_due_for_neutralization(limit=batch_size)

        stats = {
            "total_found": len(due_runs),
            "neutralized": 0,
            "failed": 0,
            "errors": [],
        }

        for run in due_runs:
            try:
                self.neutralize_run_data(run)
                stats["neutralized"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"run_id": run.id, "error": str(e)})

        return stats

    def soft_delete_run(self, run: ProcessRun) -> ProcessRun:
        """
        Soft delete a run and its step runs.

        Args:
            run: ProcessRun to soft delete

        Returns:
            Soft deleted ProcessRun
        """
        now = utc_now()

        # Soft delete the run
        run.deleted_at = now
        self.db.add(run)

        # Soft delete all step runs
        for step_run in run.steps:
            step_run.deleted_at = now
            self.db.add(step_run)

        self.db.commit()
        self.db.refresh(run)

        return run

    def restore_run(self, run: ProcessRun) -> ProcessRun:
        """
        Restore a soft-deleted run and its step runs.

        Args:
            run: ProcessRun to restore

        Returns:
            Restored ProcessRun
        """
        # Restore the run
        run.deleted_at = None
        self.db.add(run)

        # Restore all step runs
        for step_run in run.steps:
            step_run.deleted_at = None
            self.db.add(step_run)

        self.db.commit()
        self.db.refresh(run)

        return run
