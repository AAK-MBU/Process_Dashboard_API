from sqlmodel import Session

from app.adapters.registry import RerunAdapterRegistry
from app.models.process_step_run import ProcessStepRun


class RerunService:
    """Service for handling process step run reruns."""

    def __init__(self, session: Session):
        self.session = session
        self.adapter = RerunAdapterRegistry.get_adapter()

    async def can_rerun(self, step_run_id: int) -> bool:
        """Check if the specified step run can be rerun."""
        step_run = self.session.get(ProcessStepRun, step_run_id)
        if not step_run or step_run.deleted_at:
            return False

        # Check if adapter supports rerun for this step
        return await self.adapter.can_rerun(step_run_id)

    async def trigger_rerun(self, step_run_id: int) -> dict:
        """Trigger a rerun of the specified step run."""
        step_run = self.session.get(ProcessStepRun, step_run_id)

        if not step_run or step_run.deleted_at:
            msg = f"Step run {step_run_id} not found or deleted."
            raise ValueError(msg)

        # Get the workitem_id from the step run's rerun_config
        workitem_id = step_run.rerun_config.get("workitem_id")

        if not workitem_id:
            msg = "Step run has no workitem_id in rerun_config"
            raise ValueError(msg)

        result, message = await self.adapter.trigger_rerun(step_run_id, workitem_id=workitem_id)

        return {
            "result": result.value,
            "message": message,
            "adapter": self.adapter.get_adapter_name(),
        }
