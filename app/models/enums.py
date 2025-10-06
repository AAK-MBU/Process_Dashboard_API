"""Enum definitions for process and step run statuses."""

import enum


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
