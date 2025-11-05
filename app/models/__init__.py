"""Database models and schemas for the Process Dashboard API."""

from app.models.api_key import (
    ApiKey,
    ApiKeyBase,
    ApiKeyCreate,
    ApiKeyPublic,
    ApiKeyWithSecret,
)
from app.models.base import TimestampsMixin
from app.models.enums import ProcessRunStatus, StepRunStatus
from app.models.process import Process, ProcessBase, ProcessCreate, ProcessPublic
from app.models.process_run import (
    ProcessRun,
    ProcessRunBase,
    ProcessRunCreate,
    ProcessRunMetadataUpdate,
    ProcessRunPublic,
)
from app.models.process_step import (
    ProcessStep,
    ProcessStepBase,
    ProcessStepCreate,
    ProcessStepPublic,
)
from app.models.process_step_run import (
    ProcessStepRun,
    ProcessStepRunBase,
    ProcessStepRunCreate,
    ProcessStepRunPublic,
    ProcessStepRunUpdate,
)
from app.models.retention import (
    CleanupResult,
    CleanupStats,
    NeutralizationResult,
    RetentionUpdate,
)
from app.models.search import MatchedField

__all__ = [
    # Enums
    "StepRunStatus",
    "ProcessRunStatus",
    # Mixins
    "TimestampsMixin",
    # Process
    "Process",
    "ProcessBase",
    "ProcessCreate",
    "ProcessPublic",
    # Process Step
    "ProcessStep",
    "ProcessStepBase",
    "ProcessStepCreate",
    "ProcessStepPublic",
    # Process Run
    "ProcessRun",
    "ProcessRunBase",
    "ProcessRunCreate",
    "ProcessRunMetadataUpdate",
    "ProcessRunPublic",
    # Process Step Run
    "ProcessStepRun",
    "ProcessStepRunBase",
    "ProcessStepRunCreate",
    "ProcessStepRunUpdate",
    "ProcessStepRunPublic",
    # API Key
    "ApiKey",
    "ApiKeyBase",
    "ApiKeyCreate",
    "ApiKeyPublic",
    "ApiKeyWithSecret",
    # Retention
    "NeutralizationResult",
    "RetentionUpdate",
    "CleanupResult",
    "CleanupStats",
    # Search
    "MatchedField",
]

# Rebuild models to resolve forward references
# This is necessary when models are split across multiple files
Process.model_rebuild()
ProcessStep.model_rebuild()
ProcessRun.model_rebuild()
ProcessStepRun.model_rebuild()
ProcessPublic.model_rebuild()
ProcessStepPublic.model_rebuild()
ProcessRunPublic.model_rebuild()
ProcessStepRunPublic.model_rebuild()
