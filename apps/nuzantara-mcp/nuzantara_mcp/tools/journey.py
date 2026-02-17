"""Journey Orchestration Tools - 4 tools for multi-step client journey management."""

from typing import Optional


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def create_journey(
        journey_type: str,
        client_id: str,
        custom_steps: Optional[list[str]] = None,
    ) -> dict:
        """
        Create a new multi-step client journey.

        Builds a structured journey with ordered steps, timelines, and
        automatic progress tracking.

        Args:
            journey_type: Type of journey to create. Options:
                - pt_pma_setup (Complete PT PMA company setup - 7 steps)
                - kitas_application (KITAS visa application - 5 steps)
                - property_purchase (Property purchase process - 6 steps)
            client_id: UUID of the client
            custom_steps: Optional list of custom step descriptions to override template

        Returns:
            Journey object with id, steps, estimated timeline.
        """
        payload: dict = {
            "journey_type": journey_type,
            "client_id": client_id,
        }
        if custom_steps:
            payload["custom_steps"] = custom_steps
        return await _call("/api/agents/journey/create", method="POST", json=payload)

    @mcp.tool()
    async def get_journey(journey_id: str) -> dict:
        """
        Get journey details and current progress.

        Args:
            journey_id: UUID of the journey

        Returns:
            Full journey object: steps, completion %, current step, timeline.
        """
        return await _call(f"/api/agents/journey/{journey_id}")

    @mcp.tool()
    async def complete_journey_step(
        journey_id: str,
        step_id: str,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Mark a journey step as completed.

        Advances the journey to the next step and updates progress.

        Args:
            journey_id: UUID of the journey
            step_id: UUID of the step to complete
            notes: Optional completion notes

        Returns:
            Updated journey with new current step and progress %.
        """
        params = {}
        if notes:
            params["notes"] = notes
        return await _call(
            f"/api/agents/journey/{journey_id}/step/{step_id}/complete",
            method="POST",
            params=params if params else None,
        )

    @mcp.tool()
    async def get_journey_next_steps(journey_id: str) -> dict:
        """
        Get the next available steps in a journey.

        Returns pending steps that can be worked on, with requirements
        and estimated effort for each.

        Args:
            journey_id: UUID of the journey

        Returns:
            List of next steps with requirements and estimated timelines.
        """
        return await _call(f"/api/agents/journey/{journey_id}/next-steps")
