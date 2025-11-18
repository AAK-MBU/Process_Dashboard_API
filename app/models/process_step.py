"""ProcessStep models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlmodel import Column, Field, Relationship, SQLModel

from app.models.base import TimestampsMixin
from app.models.process_run import UnicodeJSON

if TYPE_CHECKING:
    from app.models.process import Process


class ProcessStepBase(SQLModel):
    """Base model for ProcessStep."""

    index: int = Field(ge=0)
    name: str = Field(max_length=255, index=True)
    process_id: int | None = Field(default=None, foreign_key="process.id")

    is_rerunnable: bool = Field(default=False, description="Whether this step type supports reruns")
    rerun_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(UnicodeJSON),
        description="Template configuration for how to rerun this step type",
    )


class ProcessStep(ProcessStepBase, TimestampsMixin, table=True):
    """ProcessStep database model."""

    __tablename__ = "process_step"

    id: int | None = Field(default=None, primary_key=True)
    deleted_at: datetime | None = Field(
        default=None, index=True, description="Soft delete timestamp"
    )

    process: Optional["Process"] = Relationship(back_populates="steps")


class ProcessStepCreate(ProcessStepBase):
    """Schema for creating a process step."""


class ProcessStepPublic(ProcessStepBase):
    """Public schema for ProcessStep."""

    id: int
