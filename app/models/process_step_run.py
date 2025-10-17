"""ProcessStepRun models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON
from sqlmodel import Column, Field, Relationship, SQLModel

from app.models.base import TimestampsMixin
from app.models.enums import StepRunStatus

if TYPE_CHECKING:
    from app.models.process_run import ProcessRun
    from app.models.process_step import ProcessStep


class ProcessStepRunBase(SQLModel):
    """Base model for ProcessStepRun."""

    status: StepRunStatus = Field(default=StepRunStatus.PENDING)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    failure: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    run_id: int | None = Field(default=None, foreign_key="process_run.id")
    step_id: int | None = Field(default=None, foreign_key="process_step.id")
    step_index: int | None = Field(default=None, ge=0)

    can_rerun: bool = Field(
        default=False, description="Whether this specific step run can be rerun"
    )
    rerun_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Configuration for how to rerun this specific step",
    )
    rerun_count: int = Field(default=0, description="Number of times this step has been rerun")
    max_reruns: int = Field(default=3, description="Maximum number of reruns allowed")


class ProcessStepRun(ProcessStepRunBase, TimestampsMixin, table=True):
    """ProcessStepRun database model."""

    __tablename__ = "process_step_run"

    id: int | None = Field(default=None, primary_key=True)
    deleted_at: datetime | None = Field(
        default=None, index=True, description="Soft delete timestamp"
    )

    run: Optional["ProcessRun"] = Relationship(back_populates="steps")
    step: Optional["ProcessStep"] = Relationship()


class ProcessStepRunCreate(SQLModel):
    """Schema for creating a process step run."""

    step_id: int
    step_index: int | None = Field(default=None, ge=0)
    run_id: int


class ProcessStepRunUpdate(SQLModel):
    """Schema for updating a process step run."""

    status: StepRunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure: dict[str, Any] | None = None


class ProcessStepRunPublic(ProcessStepRunBase):
    """Public schema for ProcessStepRun."""

    id: int
    created_at: datetime
    updated_at: datetime
