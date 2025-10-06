"""Process models."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON
from sqlalchemy.orm import RelationshipProperty
from sqlmodel import Column, Field, Relationship, SQLModel

from app.models.base import TimestampsMixin

if TYPE_CHECKING:
    from app.models.process_run import ProcessRun
    from app.models.process_step import ProcessStep, ProcessStepPublic


class ProcessBase(SQLModel):
    """Base model for Process."""

    name: str = Field(index=True, max_length=255)
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Process(ProcessBase, TimestampsMixin, table=True):
    """Process database model."""

    __tablename__ = "process"

    id: int | None = Field(default=None, primary_key=True)

    steps: list["ProcessStep"] = Relationship(
        back_populates="process",
        sa_relationship=RelationshipProperty(order_by="ProcessStep.index"),
    )
    runs: list["ProcessRun"] = Relationship(back_populates="process")


class ProcessCreate(ProcessBase):
    """Schema for creating a process."""


class ProcessPublic(ProcessBase):
    """Public schema for Process with relationships."""

    id: int
    meta: dict[str, Any]
    steps: list["ProcessStepPublic"] = []
