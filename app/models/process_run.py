"""ProcessRun models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON
from sqlalchemy.orm import RelationshipProperty
from sqlmodel import Column, Field, Relationship, SQLModel

from app.models.base import TimestampsMixin
from app.models.enums import ProcessRunStatus, StepRunStatus

if TYPE_CHECKING:
    from app.models.process import Process
    from app.models.process_step_run import (
        ProcessStepRun,
        ProcessStepRunPublic,
    )


class ProcessRunBase(SQLModel):
    """Base model for ProcessRun."""

    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    entity_id: str = Field(index=True, max_length=100)
    entity_name: str | None = Field(default=None, max_length=255)
    status: ProcessRunStatus = Field(default=ProcessRunStatus.PENDING, index=True)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    process_id: int | None = Field(default=None, foreign_key="process.id")


class ProcessRun(ProcessRunBase, TimestampsMixin, table=True):
    """ProcessRun database model."""

    __tablename__ = "process_run"

    id: int | None = Field(default=None, primary_key=True)

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

        if StepRunStatus.RUNNING in step_statuses:
            self.status = ProcessRunStatus.RUNNING
        elif StepRunStatus.FAILED in step_statuses:
            self.status = ProcessRunStatus.FAILED
        elif StepRunStatus.SUCCESS in step_statuses:
            self.status = ProcessRunStatus.COMPLETED
        elif StepRunStatus.SUCCESS in step_statuses and StepRunStatus.PENDING in step_statuses:
            self.status = ProcessRunStatus.RUNNING
        else:
            self.status = ProcessRunStatus.PENDING

        return self


class ProcessRunCreate(SQLModel):
    """Schema for creating a process run."""

    entity_id: str = Field(max_length=100)
    entity_name: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    process_id: int


class ProcessRunPublic(ProcessRunBase):
    """Public schema for ProcessRun with relationships."""

    id: int
    meta: dict[str, Any]
    status: ProcessRunStatus
    steps: list["ProcessStepRunPublic"] = []
