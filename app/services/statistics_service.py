"""Business logic for aggregated statistics."""

from datetime import timedelta
from typing import Any

from sqlalchemy import cast
from sqlalchemy.dialects.mssql import DATE
from sqlmodel import Session, func, select

from app.core.exceptions import ProcessNotFoundError
from app.models import (
    Process,
    ProcessRun,
    ProcessRunStatus,
    ProcessStep,
    ProcessStepRun,
    StepRunStatus,
)
from app.utils.datetime_utils import ensure_utc_aware, utc_now

# Default number of step-failure hotspots to return.
HOTSPOT_LIMIT = 10


class StatisticsService:
    """Service for computing aggregated statistics across processes and runs.

    All queries exclude soft-deleted rows. The same private helpers back both
    the system-wide and per-process views; pass ``process_id`` to scope a helper
    to a single process or ``None`` for system-wide aggregation.
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_system_statistics(self, days: int = 30) -> dict[str, Any]:
        """Aggregate statistics across all (non-deleted) processes."""
        status_breakdown = self._status_breakdown(process_id=None)

        statement = select(func.count()).where(Process.deleted_at.is_(None))
        total_processes = self.db.exec(statement).one()

        return {
            "scope": "system",
            "total_processes": total_processes,
            "status_breakdown": status_breakdown,
            "success_rate": self._success_rate(status_breakdown),
            "timing": self._timing_metrics(process_id=None, running=status_breakdown["running"]),
            "step_failure_hotspots": self._step_failure_hotspots(process_id=None),
            "trends": self._run_trends(process_id=None, days=days),
            "period_days": days,
        }

    def get_process_statistics(self, process_id: int, days: int = 30) -> dict[str, Any]:
        """Aggregate statistics for a single (non-deleted) process."""
        statement = (
            select(Process)
            .where(Process.id == process_id)
            .where(Process.deleted_at.is_(None))
        )
        process = self.db.exec(statement).first()
        if not process:
            raise ProcessNotFoundError(process_id)

        status_breakdown = self._status_breakdown(process_id=process_id)

        return {
            "scope": "process",
            "process_id": process_id,
            "process_name": process.name,
            "status_breakdown": status_breakdown,
            "success_rate": self._success_rate(status_breakdown),
            "timing": self._timing_metrics(
                process_id=process_id, running=status_breakdown["running"]
            ),
            "step_failure_hotspots": self._step_failure_hotspots(process_id=process_id),
            "trends": self._run_trends(process_id=process_id, days=days),
            "period_days": days,
        }

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    def _status_breakdown(self, process_id: int | None) -> dict[str, int]:
        """Count runs grouped by status (all statuses present, defaulting to 0)."""
        statement = (
            select(ProcessRun.status, func.count())
            .where(ProcessRun.deleted_at.is_(None))
            .group_by(ProcessRun.status)
        )
        if process_id is not None:
            statement = statement.where(ProcessRun.process_id == process_id)

        counts = {status.value: 0 for status in ProcessRunStatus}
        for status_value, count in self.db.exec(statement).all():
            if isinstance(status_value, ProcessRunStatus):
                key = status_value.value
            else:
                key = str(status_value)
            counts[key] = count
        counts["total"] = sum(counts.values())
        return counts

    def _success_rate(self, status_breakdown: dict[str, int]) -> float:
        """Percentage of completed runs out of all runs."""
        total = status_breakdown["total"]
        if total == 0:
            return 0.0
        return round(status_breakdown[ProcessRunStatus.COMPLETED.value] / total * 100, 2)

    def _timing_metrics(self, process_id: int | None, running: int) -> dict[str, Any]:
        """Avg/min/max run duration (seconds) over runs with start and finish times."""
        statement = (
            select(ProcessRun.started_at, ProcessRun.finished_at)
            .where(ProcessRun.deleted_at.is_(None))
            .where(ProcessRun.started_at.is_not(None))
            .where(ProcessRun.finished_at.is_not(None))
        )
        if process_id is not None:
            statement = statement.where(ProcessRun.process_id == process_id)

        durations: list[float] = []
        for started_at, finished_at in self.db.exec(statement).all():
            started = ensure_utc_aware(started_at)
            finished = ensure_utc_aware(finished_at)
            if started and finished:
                durations.append((finished - started).total_seconds())

        if durations:
            return {
                "completed_with_timing": len(durations),
                "avg_duration_seconds": round(sum(durations) / len(durations), 2),
                "min_duration_seconds": round(min(durations), 2),
                "max_duration_seconds": round(max(durations), 2),
                "running_now": running,
            }
        return {
            "completed_with_timing": 0,
            "avg_duration_seconds": None,
            "min_duration_seconds": None,
            "max_duration_seconds": None,
            "running_now": running,
        }

    def _step_failure_hotspots(
        self, process_id: int | None, limit: int = HOTSPOT_LIMIT
    ) -> list[dict[str, Any]]:
        """Steps with the most failed step runs, highest first."""
        statement = (
            select(
                ProcessStepRun.step_id,
                ProcessStep.name,
                ProcessStepRun.step_index,
                func.count(),
            )
            .join(ProcessStep, ProcessStepRun.step_id == ProcessStep.id, isouter=True)
            .where(ProcessStepRun.deleted_at.is_(None))
            .where(ProcessStepRun.status == StepRunStatus.FAILED)
            .group_by(ProcessStepRun.step_id, ProcessStep.name, ProcessStepRun.step_index)
            .order_by(func.count().desc())
            .limit(limit)
        )
        if process_id is not None:
            statement = statement.join(
                ProcessRun, ProcessStepRun.run_id == ProcessRun.id
            ).where(ProcessRun.process_id == process_id)

        return [
            {
                "step_id": step_id,
                "step_name": step_name,
                "step_index": step_index,
                "failure_count": count,
            }
            for step_id, step_name, step_index, count in self.db.exec(statement).all()
        ]

    def _run_trends(self, process_id: int | None, days: int) -> list[dict[str, Any]]:
        """Runs created and completed per day over the last ``days`` days."""
        threshold = utc_now() - timedelta(days=days)

        created = self._count_by_day(ProcessRun.created_at, threshold, process_id)
        completed = self._count_by_day(
            ProcessRun.finished_at,
            threshold,
            process_id,
            extra_filter=ProcessRun.status == ProcessRunStatus.COMPLETED,
        )

        all_days = sorted(set(created) | set(completed))
        return [
            {
                "date": day,
                "created": created.get(day, 0),
                "completed": completed.get(day, 0),
            }
            for day in all_days
        ]

    def _count_by_day(
        self,
        date_column,
        threshold,
        process_id: int | None,
        extra_filter=None,
    ) -> dict[str, int]:
        """Group non-deleted runs by the date portion of ``date_column``.

        Uses the SQL Server ``DATE`` type explicitly: SQLAlchemy's generic
        ``Date`` renders as ``DATETIME`` under the mssql dialect, which would
        bucket by full timestamp instead of by day.
        """
        day = cast(date_column, DATE)
        statement = (
            select(day, func.count())
            .where(ProcessRun.deleted_at.is_(None))
            .where(date_column.is_not(None))
            .where(date_column >= threshold)
            .group_by(day)
        )
        if process_id is not None:
            statement = statement.where(ProcessRun.process_id == process_id)
        if extra_filter is not None:
            statement = statement.where(extra_filter)

        return {
            day_value.isoformat(): count
            for day_value, count in self.db.exec(statement).all()
        }
