"""Business logic for process steps."""

from sqlmodel import Session, select

from app.core.exceptions import ProcessNotFoundError, StepNotFoundError
from app.models import Process, ProcessStep, ProcessStepCreate


class StepService:
    """Service for managing process steps."""

    def __init__(self, db: Session):
        self.db = db

    def create_step(self, step_data: ProcessStepCreate) -> ProcessStep:
        """
        Create a new process step.

        Args:
            step_data: Step creation data

        Returns:
            Created ProcessStep object

        Raises:
            ProcessNotFoundError: If parent process doesn't exist
        """
        # Verify process exists
        process = self.db.get(Process, step_data.process_id)
        if not process:
            raise ProcessNotFoundError(step_data.process_id)

        step = ProcessStep.model_validate(step_data)
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def get_step(self, step_id: int) -> ProcessStep:
        """
        Get a process step by ID.

        Args:
            step_id: ID of the step to retrieve

        Returns:
            ProcessStep object

        Raises:
            StepNotFoundError: If step doesn't exist
        """
        step = self.db.get(ProcessStep, step_id)
        if not step:
            raise StepNotFoundError(step_id)
        return step

    def list_steps_for_process(self, process_id: int) -> list[ProcessStep]:
        """
        List all steps for a specific process, ordered by index.

        Args:
            process_id: ID of the process

        Returns:
            List of ProcessStep objects ordered by index
        """
        statement = (
            select(ProcessStep)
            .where(ProcessStep.process_id == process_id)
            .order_by(ProcessStep.index)
        )
        steps = self.db.exec(statement).all()
        return list(steps)

    def list_rerunnable_steps(self, process_id: int) -> list[ProcessStep]:
        """
        List all rerunnable steps for a specific process.

        Args:
            process_id: ID of the process

        Returns:
            List of rerunnable ProcessStep objects ordered by index
        """
        statement = (
            select(ProcessStep)
            .where(ProcessStep.process_id == process_id)
            .where(ProcessStep.is_rerunnable == True)
            .order_by(ProcessStep.index)
        )
        steps = self.db.exec(statement).all()
        return list(steps)

    def update_step(self, step_id: int, update_data: dict) -> ProcessStep:
        """
        Update a process step.

        Args:
            step_id: ID of the step to update
            update_data: Dictionary of fields to update

        Returns:
            Updated ProcessStep object

        Raises:
            StepNotFoundError: If step doesn't exist
        """
        step = self.get_step(step_id)

        for key, value in update_data.items():
            if hasattr(step, key):
                setattr(step, key, value)

        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def delete_step(self, step_id: int) -> None:
        """
        Delete a process step.

        Args:
            step_id: ID of the step to delete

        Raises:
            StepNotFoundError: If step doesn't exist
        """
        step = self.get_step(step_id)
        self.db.delete(step)
        self.db.commit()

    def reorder_steps(self, process_id: int, step_order: list[int]) -> list[ProcessStep]:
        """
        Reorder steps for a process.

        Args:
            process_id: ID of the process
            step_order: List of step IDs in desired order

        Returns:
            List of reordered ProcessStep objects

        Raises:
            ProcessNotFoundError: If process doesn't exist
            StepNotFoundError: If any step ID is invalid
        """
        # Verify process exists
        process = self.db.get(Process, process_id)
        if not process:
            raise ProcessNotFoundError(process_id)

        # Verify all steps exist and belong to this process
        steps = []
        for step_id in step_order:
            step = self.get_step(step_id)
            if step.process_id != process_id:
                raise StepNotFoundError(step_id)
            steps.append(step)

        # Update indices
        for new_index, step in enumerate(steps):
            step.index = new_index
            self.db.add(step)

        self.db.commit()

        # Return updated steps
        return self.list_steps_for_process(process_id)
