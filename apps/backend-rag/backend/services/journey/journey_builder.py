"""
Journey Builder Service
Responsibility: Build journeys from templates
"""

import logging
from datetime import datetime, timedelta

from services.journey.journey_templates import JourneyTemplatesService

logger = logging.getLogger(__name__)


class JourneyBuilderService:
    """
    Service for building client journeys.

    Responsibility: Create journeys from templates or custom steps.
    """

    def __init__(self, templates_service: JourneyTemplatesService | None = None):
        """
        Initialize journey builder service.

        Args:
            templates_service: Optional JourneyTemplatesService instance
        """
        self.templates = templates_service or JourneyTemplatesService()

    def build_journey_from_template(
        self,
        journey_id: str,
        journey_type: str,
        client_id: str,
        template_key: str,
        metadata: dict | None = None,
    ):
        """
        Build journey from template.

        Args:
            journey_id: Unique journey identifier
            journey_type: Journey type (e.g., "company_setup")
            client_id: Client identifier
            template_key: Template key (e.g., "pt_pma_setup")
            metadata: Optional metadata

        Returns:
            ClientJourney instance
        """
        from services.client_journey_orchestrator import ClientJourney, JourneyStatus, JourneyStep

        template = self.templates.get_template(template_key)
        if not template:
            raise ValueError(f"Unknown template: {template_key}")

        # Build steps from template
        steps = []
        for idx, step_template in enumerate(template["steps"], start=1):
            step = JourneyStep(
                step_id=step_template["step_id"],
                step_number=idx,
                title=step_template["title"],
                description=step_template["description"],
                prerequisites=step_template.get("prerequisites", []),
                required_documents=step_template.get("required_documents", []),
                estimated_duration_days=step_template.get("estimated_duration_days", 0),
            )
            steps.append(step)

        # Calculate estimated completion
        total_days = sum(s.estimated_duration_days for s in steps)
        estimated_completion = (datetime.now() + timedelta(days=total_days)).isoformat()

        journey = ClientJourney(
            journey_id=journey_id,
            journey_type=journey_type,
            client_id=client_id,
            title=template["title"],
            description=template["description"],
            steps=steps,
            status=JourneyStatus.NOT_STARTED,
            estimated_completion=estimated_completion,
            metadata=metadata or {},
        )

        logger.info(
            f"✅ Built journey {journey_id} from template {template_key} ({len(steps)} steps)"
        )

        return journey

    def build_custom_journey(
        self,
        journey_id: str,
        journey_type: str,
        client_id: str,
        title: str,
        description: str,
        steps: list[dict],
        metadata: dict | None = None,
    ):
        """
        Build custom journey from provided steps.

        Args:
            journey_id: Unique journey identifier
            journey_type: Journey type
            client_id: Client identifier
            title: Journey title
            description: Journey description
            steps: List of step dictionaries
            metadata: Optional metadata

        Returns:
            ClientJourney instance
        """
        from services.client_journey_orchestrator import ClientJourney, JourneyStatus, JourneyStep

        journey_steps = []
        for idx, step_data in enumerate(steps, start=1):
            step = JourneyStep(
                step_id=step_data.get("step_id", f"step_{idx}"),
                step_number=idx,
                title=step_data.get("title", f"Step {idx}"),
                description=step_data.get("description", ""),
                prerequisites=step_data.get("prerequisites", []),
                required_documents=step_data.get("required_documents", []),
                estimated_duration_days=step_data.get("estimated_duration_days", 0),
            )
            journey_steps.append(step)

        # Calculate estimated completion
        total_days = sum(s.estimated_duration_days for s in journey_steps)
        estimated_completion = (datetime.now() + timedelta(days=total_days)).isoformat()

        journey = ClientJourney(
            journey_id=journey_id,
            journey_type=journey_type,
            client_id=client_id,
            title=title,
            description=description,
            steps=journey_steps,
            status=JourneyStatus.NOT_STARTED,
            estimated_completion=estimated_completion,
            metadata=metadata or {},
        )

        logger.info(f"✅ Built custom journey {journey_id} ({len(journey_steps)} steps)")

        return journey
