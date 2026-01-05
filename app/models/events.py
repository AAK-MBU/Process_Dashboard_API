"""SQLAlchemy event handlers for automatic model updates."""

import logging

from sqlalchemy import event
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def register_events():
    """Register all SQLAlchemy event handlers."""
    from app.models.process_run import ProcessRun
    from app.models.process_step_run import ProcessStepRun

    @event.listens_for(ProcessStepRun, "before_insert")
    def set_step_index_on_insert(mapper, connection, target: ProcessStepRun):
        """
        Automatically populate step_index from related ProcessStep.

        This event fires before inserting a new ProcessStepRun and sets
        the step_index field based on the index of the related
        ProcessStep.
        """
        # Only set if not explicitly provided (None or 0)
        if target.step_index is None or target.step_index == 0:
            session = Session.object_session(target)
            if session and target.step_id:
                # Use query to avoid identity map issues
                from app.models.process_step import ProcessStep

                step = session.query(ProcessStep).filter(ProcessStep.id == target.step_id).first()
                if step:
                    target.step_index = step.index
                    logger.debug(
                        "Event: Auto-set step_index=%s for step_run (step_id=%s)",
                        step.index,
                        target.step_id,
                    )
                else:
                    # Default to 0 if step not found
                    target.step_index = 0
                    logger.warning(
                        "Event: Step %s not found, defaulting step_index to 0",
                        target.step_id,
                    )

    @event.listens_for(Session, "before_commit", propagate=True)
    def update_run_status_before_commit(session):
        """Update parent ProcessRun status before commit.

        Uses only objects already loaded in the session to avoid
        database queries that could cause deadlocks during the
        transaction.
        """
        # Use a dict keyed by run_id instead of a set of objects
        runs_to_update: dict[int, ProcessRun] = {}

        # Collect step runs and their parent runs from the session's
        # identity map. Do NOT execute any queries here - only use
        # objects already loaded
        for obj in session.identity_map.values():
            if isinstance(obj, ProcessStepRun) and obj.run_id:
                # Use session.get() which checks identity map first
                # before querying
                run = session.get(ProcessRun, obj.run_id)
                if run and obj.run_id not in runs_to_update:
                    runs_to_update[obj.run_id] = run

        # Update each affected run using already-loaded data
        for run_id, run in runs_to_update.items():
            # Get steps from identity map instead of querying
            steps = [
                obj
                for obj in session.identity_map.values()
                if isinstance(obj, ProcessStepRun) and obj.run_id == run_id
            ]

            if steps:
                old_status = run.status
                # Use the new method that accepts steps directly
                run.update_status_from_steps(steps)
                if old_status != run.status:
                    logger.debug(
                        "Event: Updated run %s status from %s to %s",
                        run_id,
                        old_status,
                        run.status,
                    )

    logger.info("SQLAlchemy events registered successfully")
    return True
