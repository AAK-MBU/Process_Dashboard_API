"""Business logic for process step runs."""

from sqlmodel import Session, select

from app.core.exceptions import (
    ProcessRunNotFoundError,
    StepNotFoundError,
    StepRunError,
    StepRunNotFoundError,
)
from app.models import (
    ProcessRun,
    ProcessStep,
    ProcessStepRun,
    ProcessStepRunCreate,
    ProcessStepRunUpdate,
    StepRunStatus,
)


class StepRunService:
    """Service for managing process step runs."""

    def __init__(self, db: Session):
        self.db = db

    def create_step_run(self, step_run_data: ProcessStepRunCreate) -> ProcessStepRun:
        """
        Create a new process step run.

        Raises:
            ProcessRunNotFoundError: If process run doesn't exist
            StepNotFoundError: If process step doesn't exist
        """
        # Verify run exists
        run = self.db.get(ProcessRun, step_run_data.run_id)
        if not run:
            raise ProcessRunNotFoundError(step_run_data.run_id)

        # Verify step exists
        step = self.db.get(ProcessStep, step_run_data.step_id)
        if not step:
            raise StepNotFoundError(step_run_data.step_id)

        step_run = ProcessStepRun.model_validate(step_run_data)
        self.db.add(step_run)
        self.db.commit()
        self.db.refresh(step_run)
        return step_run

    def update_step_run(
        self, step_run_id: int, update_data: ProcessStepRunUpdate
    ) -> ProcessStepRun:
        """
        Update a process step run status.

        Also updates the parent run's status automatically.

        Raises:
            StepRunNotFoundError: If step run doesn't exist
        """
        step_run = self.db.get(ProcessStepRun, step_run_id)
        if not step_run:
            raise StepRunNotFoundError(step_run_id)

        # Update fields
        for key, value in update_data.model_dump(exclude_unset=True).items():
            setattr(step_run, key, value)

        self.db.add(step_run)
        self.db.commit()
        self.db.refresh(step_run)

        # Update parent run status
        self._update_parent_run_status(step_run.run_id)

        return step_run

    def rerun_step(self, step_run_id: int) -> ProcessStepRun:
        """
        Rerun a failed process step.

        Raises:
            StepRunNotFoundError: If step run doesn't exist
            StepRunError: If step cannot be rerun
        """
        step_run = self.db.get(ProcessStepRun, step_run_id)
        if not step_run:
            raise StepRunNotFoundError(step_run_id)

        # Validate rerun conditions
        self._validate_rerun_conditions(step_run)

        # Reset step run for rerun
        step_run.rerun_count += 1
        step_run.status = StepRunStatus.PENDING
        step_run.started_at = None
        step_run.finished_at = None
        step_run.failure = None

        self.db.add(step_run)
        self.db.commit()
        self.db.refresh(step_run)

        # Update parent run status
        self._update_parent_run_status(step_run.run_id)

        return step_run

    def _validate_rerun_conditions(self, step_run: ProcessStepRun) -> None:
        """Validate that a step run can be rerun."""
        if not step_run.can_rerun:
            raise StepRunError(f"Step run {step_run.id} cannot be rerun (can_rerun=False)")

        if step_run.rerun_count >= step_run.max_reruns:
            raise StepRunError(
                f"Maximum reruns ({step_run.max_reruns}) exceeded for step {step_run.id}"
            )

        if step_run.status != StepRunStatus.FAILED:
            raise StepRunError(
                f"Step must be in FAILED status to be rerun (current: {step_run.status})"
            )

    def _update_parent_run_status(self, run_id: int) -> None:
        """Update the parent run's status based on step statuses."""
        run = self.db.get(ProcessRun, run_id)
        if run:
            run.update_status()
            self.db.add(run)
            self.db.commit()

    def list_step_runs_for_run(self, run_id: int) -> list[ProcessStepRun]:
        """List all step runs for a specific process run."""
        statement = (
            select(ProcessStepRun).where(ProcessStepRun.run_id == run_id).order_by("step_index")
        )
        step_runs = self.db.exec(statement).all()
        return list(step_runs)

    def list_rerunnable_step_runs(self, run_id: int) -> list[ProcessStepRun]:
        """List all rerunnable (failed) step runs for a process run."""
        statement = (
            select(ProcessStepRun)
            .where(ProcessStepRun.run_id == run_id)
            .where(ProcessStepRun.can_rerun == True)
            .where(ProcessStepRun.status == StepRunStatus.FAILED)
            .order_by("step_index")
        )
        step_runs = self.db.exec(statement).all()
        return list(step_runs)
