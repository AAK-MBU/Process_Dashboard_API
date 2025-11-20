from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional


class RerunResult(Enum):
    """Enumeration for rerun results."""

    SUCCESS = "success"
    FAILURE = "failure"
    NOT_SUPPORTED = "not_supported"
    SOURCE_ERROR = "source_error"


class BaseRerunAdapter(ABC):
    """Abstract base class for process run rerun adapters."""

    @abstractmethod
    async def can_rerun(self, process_run_id: int) -> bool:
        """Check if the process run can be rerun."""

    @abstractmethod
    async def trigger_rerun(
        self, process_run_id: int, **kwargs
    ) -> tuple[RerunResult, Optional[str]]:
        """
        Trigger a rerun of the specified process run.

        Args:
            process_run_id: The ID of the process run to rerun.
            **kwargs: Additional parameters for the rerun.

        Returns:
            A tuple containing the RerunResult and an optional message.

        """

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Get the name of the adapter."""
