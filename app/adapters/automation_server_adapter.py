"""Adapter for interacting with an external automation server for process reruns."""

import httpx

from app.adapters.base import BaseRerunAdapter, RerunResult
from app.core.config import settings


class AutomationServerAdapter(BaseRerunAdapter):
    """Adapter for interacting with an external automation server for process reruns."""

    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = base_url or settings.AUTOMATION_SERVER_URL
        if not self.base_url:
            msg = (
                "AUTOMATION_SERVER_URL must be set in settings or "
                "provided to AutomationServerAdapter"
            )
            raise ValueError(msg)
        self.base_url = self.base_url.rstrip("/")
        self.token = token or settings.AUTOMATION_SERVER_TOKEN
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def can_rerun(self, process_run_id: int) -> bool:
        """Check if the process run can be rerun."""
        return True

    async def trigger_rerun(self, process_run_id: int, **kwargs) -> tuple[RerunResult, None | str]:
        """Trigger a rerun via the automation server."""
        try:
            workitem_id = kwargs.get("workitem_id")

            if not workitem_id:
                return (
                    RerunResult.FAILURE,
                    "Missing required parameter: workitem_id",
                )

            # TODO: REMOVE AFTER TESTING
            # SET TO verify=True FOR TESTING PURPOSES
            async with httpx.AsyncClient(verify=False) as client:
                # Update workitem status to NEW to trigger rerun
                response = await client.put(
                    f"{self.base_url}/workitems/{workitem_id}/status",
                    headers=self.headers,
                    json={"status": "new"},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    return (
                        RerunResult.SUCCESS,
                        f"Workitem {workitem_id} reset to NEW",
                    )

                return (
                    RerunResult.SOURCE_ERROR,
                    f"Failed to update workitem: {response.text}",
                )

        except httpx.RequestError as e:
            return RerunResult.SOURCE_ERROR, f"Request error: {str(e)}"
        except Exception as e:
            return RerunResult.FAILURE, f"Unexpected error: {str(e)}"

    def get_adapter_name(self) -> str:
        """Get the name of the adapter."""
        return "automation_server"
