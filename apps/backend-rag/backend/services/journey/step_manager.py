"""
Step Manager Service
Responsibility: Manage step lifecycle
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class StepManagerService:
    """
    Service for managing step lifecycle.

    Responsibility: Start, complete, and block steps.
    """

    def start_step(self, journey, step_id: str) -> bool:
        """
        Start a journey step.

        Args:
            journey: ClientJourney instance
            step_id: Step identifier

        Returns:
            True if started successfully
        """
        step = self._find_step(journey, step_id)
        if not step:
            return False

        from services.client_journey_orchestrator import JourneyStatus, StepStatus

        if step.status == StepStatus.COMPLETED:
            logger.warning(f"Step {step_id} already completed")
            return False

        step.status = StepStatus.IN_PROGRESS
        step.started_at = datetime.now().isoformat()

        # Update journey status if needed
        if journey.status == JourneyStatus.NOT_STARTED:
            journey.status = JourneyStatus.IN_PROGRESS
            journey.started_at = datetime.now().isoformat()

        logger.info(f"▶️ Started step: {step_id} - {step.title}")
        return True

    def complete_step(self, journey, step_id: str, notes: list[str] | None = None) -> bool:
        """
        Complete a journey step.

        Args:
            journey: ClientJourney instance
            step_id: Step identifier
            notes: Optional completion notes

        Returns:
            True if completed successfully
        """
        step = self._find_step(journey, step_id)
        if not step:
            return False

        from services.client_journey_orchestrator import StepStatus

        if step.status == StepStatus.COMPLETED:
            logger.warning(f"Step {step_id} already completed")
            return False

        step.status = StepStatus.COMPLETED
        step.completed_at = datetime.now().isoformat()

        if notes:
            step.notes.extend(notes)

        logger.info(f"✅ Completed step: {step_id} - {step.title}")

        # Check if journey is complete
        self._update_journey_status(journey)

        return True

    def block_step(self, journey, step_id: str, reason: str) -> bool:
        """
        Block a journey step.

        Args:
            journey: ClientJourney instance
            step_id: Step identifier
            reason: Blocking reason

        Returns:
            True if blocked successfully
        """
        step = self._find_step(journey, step_id)
        if not step:
            return False

        from services.client_journey_orchestrator import JourneyStatus, StepStatus

        step.status = StepStatus.BLOCKED
        step.blocked_reason = reason

        # Update journey status
        journey.status = JourneyStatus.BLOCKED

        logger.warning(f"🚫 Blocked step: {step_id} - {step.title} (Reason: {reason})")
        return True

    def _find_step(self, journey, step_id: str):
        """Find step by ID."""
        for step in journey.steps:
            if step.step_id == step_id:
                return step
        return None

    def _update_journey_status(self, journey):
        """Update journey status based on step completion."""
        from services.client_journey_orchestrator import (
            JourneyStatus,  # noqa: F401
            StepStatus,
        )

        completed_steps = sum(1 for s in journey.steps if s.status == StepStatus.COMPLETED)
        total_steps = len(journey.steps)

        if completed_steps == total_steps:
            journey.status = JourneyStatus.COMPLETED
            journey.completed_at = datetime.now().isoformat()
            journey.actual_completion = datetime.now().isoformat()
            logger.info(f"🎉 Journey {journey.journey_id} completed!")
