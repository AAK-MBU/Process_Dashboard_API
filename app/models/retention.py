"""Pydantic models for data retention operations."""

from pydantic import BaseModel


class RetentionUpdate(BaseModel):
    """Schema for updating retention period."""

    retention_months: int | None


class NeutralizationResult(BaseModel):
    """Result of a neutralization operation."""

    run_id: int
    was_already_neutralized: bool
    success: bool
    message: str


class CleanupResult(BaseModel):
    """Result of cleanup operation."""

    total_found: int
    neutralized: int
    failed: int
    errors: list[dict]


class CleanupStats(BaseModel):
    """Statistics about data retention."""

    runs_due_for_neutralization: int
    sample_run_ids: list[int]
