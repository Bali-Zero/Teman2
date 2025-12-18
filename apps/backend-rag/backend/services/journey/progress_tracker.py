"""
Progress Tracker Service
Responsibility: Track journey progress
"""

import logging

logger = logging.getLogger(__name__)


class ProgressTrackerService:
    """
    Service for tracking journey progress.

    Responsibility: Calculate progress metrics and identify next steps.
    """

    def get_next_steps(self, journey) -> list:
        """
        Get next actionable steps (prerequisites met, not completed).

        Args:
            journey: ClientJourney instance

        Returns:
            List of next steps
        """
        from services.journey.prerequisites_checker import PrerequisitesCheckerService

        checker = PrerequisitesCheckerService()
        next_steps = []

        from services.client_journey_orchestrator import StepStatus

        for step in journey.steps:
            if step.status in [StepStatus.COMPLETED, StepStatus.IN_PROGRESS, StepStatus.BLOCKED]:
                continue

            # Check prerequisites
            prerequisites_met, _ = checker.check_prerequisites(journey, step.step_id)
            if prerequisites_met:
                next_steps.append(step)

        return next_steps

    def get_progress(self, journey) -> dict:
        """
        Get journey progress summary.

        Args:
            journey: ClientJourney instance

        Returns:
            Progress dictionary
        """
        from services.client_journey_orchestrator import StepStatus

        total_steps = len(journey.steps)
        completed_steps = sum(1 for s in journey.steps if s.status == StepStatus.COMPLETED)
        in_progress_steps = sum(1 for s in journey.steps if s.status == StepStatus.IN_PROGRESS)
        blocked_steps = sum(1 for s in journey.steps if s.status == StepStatus.BLOCKED)
        pending_steps = sum(1 for s in journey.steps if s.status == StepStatus.PENDING)

        progress_percent = (completed_steps / total_steps * 100) if total_steps > 0 else 0

        return {
            "total_steps": total_steps,
            "completed": completed_steps,
            "in_progress": in_progress_steps,
            "blocked": blocked_steps,
            "pending": pending_steps,
            "progress_percent": round(progress_percent, 1),
            "status": journey.status,
        }
