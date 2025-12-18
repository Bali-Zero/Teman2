"""
Prerequisites Checker Service
Responsibility: Check step prerequisites
"""

import logging

logger = logging.getLogger(__name__)


class PrerequisitesCheckerService:
    """
    Service for checking step prerequisites.

    Responsibility: Verify if prerequisites for a step are met.
    """

    def check_prerequisites(self, journey, step_id: str) -> tuple[bool, list[str]]:
        """
        Check if prerequisites for a step are met.

        Args:
            journey: ClientJourney instance
            step_id: Step identifier

        Returns:
            Tuple of (prerequisites_met, missing_prerequisites)
        """
        # Find step
        step = None
        for s in journey.steps:
            if s.step_id == step_id:
                step = s
                break

        if not step:
            return False, [f"Step {step_id} not found"]

        # Check prerequisites
        missing = []
        for prereq_id in step.prerequisites:
            prereq_step = None
            for s in journey.steps:
                if s.step_id == prereq_id:
                    prereq_step = s
                    break

            if not prereq_step:
                missing.append(f"Prerequisite step {prereq_id} not found")
            elif prereq_step.status.value != "completed":
                missing.append(f"Prerequisite {prereq_id} ({prereq_step.title}) not completed")

        return len(missing) == 0, missing
