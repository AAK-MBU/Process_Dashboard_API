"""Database models for process monitoring system."""

import enum
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON
from sqlalchemy.orm import RelationshipProperty
from sqlmodel import Column, Field, Relationship, SQLModel


class StepRunStatus(str, enum.Enum):
    """Status values for a process step run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ProcessRunStatus(str, enum.Enum):
    """Status values for a process run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Mixins
class TimestampsMixin(SQLModel):
    """Mixin for created_at and updated_at timestamps."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
    )


# Process Models
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


# Process Step Models
class ProcessStepBase(SQLModel):
    """Base model for ProcessStep."""

    index: int = Field(ge=0)
    name: str = Field(max_length=255, index=True)
    process_id: int | None = Field(default=None, foreign_key="process.id")

    is_rerunnable: bool = Field(default=False, description="Whether this step type supports reruns")
    rerun_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Template configuration for how to rerun this step type",
    )


class ProcessStep(ProcessStepBase, TimestampsMixin, table=True):
    """ProcessStep database model."""

    __tablename__ = "process_step"

    id: int | None = Field(default=None, primary_key=True)

    process: Process | None = Relationship(back_populates="steps")


class ProcessStepCreate(ProcessStepBase):
    """Schema for creating a process step."""


class ProcessStepPublic(ProcessStepBase):
    """Public schema for ProcessStep."""

    id: int


# Process Run Models
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
    process: Process | None = Relationship(back_populates="runs")

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


# Process Step Run Models
class ProcessStepRunBase(SQLModel):
    """Base model for ProcessStepRun."""

    status: StepRunStatus = Field(default=StepRunStatus.PENDING)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    failure: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    run_id: int | None = Field(default=None, foreign_key="process_run.id")
    step_id: int | None = Field(default=None, foreign_key="process_step.id")
    step_index: int = Field(ge=0)

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

    run: ProcessRun | None = Relationship(back_populates="steps")
    step: ProcessStep | None = Relationship()


class ProcessStepRunCreate(SQLModel):
    """Schema for creating a process step run."""

    step_id: int
    step_index: int = Field(ge=0)
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


# API Key Models for authentication
class ApiKeyBase(SQLModel):
    """Base model for API keys."""

    name: str = Field(max_length=100, description="Human-readable name for the API key")
    description: str | None = Field(
        default=None, max_length=500, description="Optional description"
    )
    is_active: bool = Field(default=True, description="Whether the key is active")
    expires_at: datetime | None = Field(default=None, description="Optional expiration date")
    role: str = Field(default="user", max_length=20, description="Role: 'admin' or 'user'")


class ApiKey(ApiKeyBase, TimestampsMixin, table=True):
    """API key database model."""

    __tablename__ = "api_key"

    id: int | None = Field(default=None, primary_key=True)
    key_hash: str = Field(
        max_length=64, index=True, unique=True, description="SHA-256 hash of the API key"
    )
    key_prefix: str = Field(max_length=8, description="First 8 characters for identification")
    last_used_at: datetime | None = Field(default=None, description="Last time this key was used")
    usage_count: int = Field(default=0, description="Number of times this key has been used")

    @classmethod
    def generate_key(cls) -> str:
        """Generate a new secure API key."""
        return f"pd_{secrets.token_urlsafe(32)}"

    @classmethod
    def hash_key(cls, key: str) -> str:
        """Hash an API key for storage."""
        import hashlib

        return hashlib.sha256(key.encode()).hexdigest()


class ApiKeyCreate(ApiKeyBase):
    """Schema for creating an API key."""


class ApiKeyPublic(ApiKeyBase):
    """Public schema for API key (without sensitive data)."""

    id: int
    last_used_at: datetime | None
    usage_count: int
    created_at: datetime
    updated_at: datetime


class ApiKeyWithSecret(ApiKeyPublic):
    """API key with the actual secret (only returned once during creation)."""

    key: str
