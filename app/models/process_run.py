"""ProcessRun models."""

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.types import TEXT, TypeDecorator
from sqlmodel import Column, Field, Relationship, SQLModel

from app.models.base import TimestampsMixin
from app.models.enums import ProcessRunStatus, StepRunStatus

if TYPE_CHECKING:
    from app.models.process import Process
    from app.models.process_step_run import (
        ProcessStepRun,
        ProcessStepRunPublic,
    )


class UnicodeJSON(TypeDecorator):
    """Custom SQLAlchemy type for storing JSON as Unicode text."""

    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value, ensure_ascii=False)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None

    def process_literal_param(self, value, dialect):
        """Process literal parameters for SQL expressions."""
        if value is not None:
            return json.dumps(value, ensure_ascii=False)
        return None

    @property
    def python_type(self):
        """Return the Python type handled by this custom type."""
        return dict


class ProcessRunBase(SQLModel):
    """Base model for ProcessRun."""

    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(UnicodeJSON))
    entity_id: str = Field(index=True, max_length=100)
    entity_name: str | None = Field(default=None, max_length=255)
    status: ProcessRunStatus = Field(default=ProcessRunStatus.PENDING, index=True, max_length=25)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    process_id: int | None = Field(default=None, foreign_key="process.id")
    is_neutralized: bool = Field(
        default=False,
        index=True,
        description="Om personfølsomme data er slettet",
    )


class ProcessRun(ProcessRunBase, TimestampsMixin, table=True):
    """ProcessRun database model."""

    __tablename__ = "process_run"

    id: int | None = Field(default=None, primary_key=True)
    deleted_at: datetime | None = Field(
        default=None, index=True, description="Soft delete timestamp"
    )
    scheduled_deletion_at: datetime | None = Field(
        default=None,
        index=True,
        description=(
            "Beregnet tidspunkt hvor personfølsomme data skal "
            "neutraliseres baseret på retention_months"
        ),
    )

    steps: list["ProcessStepRun"] = Relationship(
        back_populates="run",
        sa_relationship=RelationshipProperty(order_by="ProcessStepRun.step_index"),
    )
    process: Optional["Process"] = Relationship(back_populates="runs")

    def update_status(self) -> "ProcessRun":
        """Update the overall status based on step statuses."""
        if not self.steps:
            self.status = ProcessRunStatus.PENDING
            return self

        step_statuses = [step.status for step in self.steps]
        previous_status = self.status

        # Priority 1: If run is explicitly cancelled, keep it cancelled
        if self.status == ProcessRunStatus.CANCELLED:
            return self

        # Priority 2: If any step failed, mark as failed
        if StepRunStatus.FAILED in step_statuses:
            self.status = ProcessRunStatus.FAILED
        # Priority 3: If any step is cancelled, mark as cancelled
        elif StepRunStatus.CANCELLED in step_statuses:
            self.status = ProcessRunStatus.CANCELLED
        # Priority 4: If any step is running, mark as running
        elif StepRunStatus.RUNNING in step_statuses:
            self.status = ProcessRunStatus.RUNNING
        # Priority 5: Check if all required steps are complete
        elif self._all_required_steps_complete(step_statuses):
            self.status = ProcessRunStatus.COMPLETED
        # Priority 6: If there are pending steps, mark as running
        elif StepRunStatus.PENDING in step_statuses:
            self.status = ProcessRunStatus.RUNNING
        # Priority 7: Default to pending
        else:
            self.status = ProcessRunStatus.PENDING

        # Auto-set finished_at when transitioning to terminal status
        self._update_finished_at(previous_status, self.status)

        return self

    def _all_required_steps_complete(self, step_statuses: list[StepRunStatus]) -> bool:
        """Check if all required steps are complete (success).

        Only optional steps don't count as required for completion.
        Cancelled steps are blocking and prevent completion.
        """
        blocking_statuses = [
            StepRunStatus.PENDING,
            StepRunStatus.RUNNING,
            StepRunStatus.FAILED,
            StepRunStatus.CANCELLED,
        ]

        for status in step_statuses:
            if status in blocking_statuses:
                return False
            # Only SUCCESS and OPTIONAL steps don't block completion

        # At least one step must be successful for completion
        return StepRunStatus.SUCCESS in step_statuses

    def _update_finished_at(
        self, previous_status: ProcessRunStatus, new_status: ProcessRunStatus
    ) -> None:
        """Update finished_at timestamp when transitioning to terminal status.

        Args:
            previous_status: The status before the change
            new_status: The new status after the change
        """
        terminal_statuses = {
            ProcessRunStatus.COMPLETED,
            ProcessRunStatus.FAILED,
            ProcessRunStatus.CANCELLED,
        }

        non_terminal_statuses = {
            ProcessRunStatus.PENDING,
            ProcessRunStatus.RUNNING,
        }

        # Set finished_at when transitioning from non-terminal to terminal
        if (
            previous_status in non_terminal_statuses
            and new_status in terminal_statuses
            and self.finished_at is None
        ):
            self.finished_at = datetime.now(timezone.utc)

        # Clear finished_at when transitioning from terminal to non-terminal
        elif previous_status in terminal_statuses and new_status in non_terminal_statuses:
            self.finished_at = None

        # Set started_at when transitioning from PENDING to RUNNING
        if (
            previous_status == ProcessRunStatus.PENDING
            and new_status == ProcessRunStatus.RUNNING
            and self.started_at is None
        ):
            self.started_at = datetime.now(timezone.utc)


class ProcessRunCreate(SQLModel):
    """Schema for creating a process run."""

    entity_id: str = Field(max_length=100)
    entity_name: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    process_id: int


class ProcessRunMetadataUpdate(SQLModel):
    """Schema for updating existing metadata fields only."""

    meta: dict[str, Any] = Field(
        default_factory=dict,
        description=("Metadata fields to update. Only existing fields will be updated."),
    )


class ProcessRunPublic(ProcessRunBase):
    """Public schema for ProcessRun with relationships."""

    id: int
    meta: dict[str, Any] = Field(default_factory=dict)
    status: ProcessRunStatus = ProcessRunStatus.PENDING
    steps: list["ProcessStepRunPublic"] = []
