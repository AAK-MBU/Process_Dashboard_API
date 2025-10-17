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
        """
        Update parent ProcessRun status before commit.

        This runs after flush but before commit,
        allowing status changes to be included.
        """
        # Track which runs need updating
        runs_to_update = set()

        # Check all ProcessStepRun objects that were modified
        for obj in session.identity_map.values():
            if isinstance(obj, ProcessStepRun) and obj.run_id:
                runs_to_update.add(obj.run_id)

        # Update each affected run
        for run_id in runs_to_update:
            run = session.get(ProcessRun, run_id)
            if run:
                old_status = run.status
                run.update_status()
                new_status = run.status

                if old_status != new_status:
                    logger.debug(
                        "Event: Updated run %s status from %s to %s before commit",
                        run_id,
                        old_status,
                        new_status,
                    )

    logger.info("SQLAlchemy events registered successfully")
    return True
