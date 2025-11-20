from typing import Optional

from app.adapters.automation_server_adapter import AutomationServerAdapter
from app.adapters.base import BaseRerunAdapter
from app.core.config import settings


class RerunAdapterRegistry:
    """Registry for rerun adapters."""

    _adapters: dict[str, type[BaseRerunAdapter]] = {}
    _instance: Optional["BaseRerunAdapter"] = None

    @classmethod
    def register(cls, name: str, adapter_class: type[BaseRerunAdapter]) -> None:
        """Register a rerun adapter class with a given name."""
        cls._adapters[name] = adapter_class

    @classmethod
    def get_adapter(cls) -> BaseRerunAdapter:
        """Get an instance of the registered rerun adapter."""

        if cls._instance is None:
            adapter_type = settings.RERUN_ADAPTER_TYPE

            if adapter_type not in cls._adapters:
                raise ValueError(f"Unknown rerun adapter type: {adapter_type}")

            adapter_class = cls._adapters[adapter_type]

            if adapter_type == "automation_server":
                cls._instance = adapter_class(
                    base_url=settings.AUTOMATION_SERVER_URL,
                    token=settings.AUTOMATION_SERVER_TOKEN,
                )
            else:
                cls._instance = adapter_class()

        return cls._instance


RerunAdapterRegistry.register("automation_server", AutomationServerAdapter)
