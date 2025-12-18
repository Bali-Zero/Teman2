"""
Team Members List Plugin

Migrated from: backend/services/zantara_tools.py -> _get_team_members_list
"""

import logging
from typing import Any

from core.plugins import Plugin, PluginCategory, PluginInput, PluginMetadata, PluginOutput
from pydantic import Field

from services.collaborator_service import CollaboratorService

logger = logging.getLogger(__name__)


class TeamListInput(PluginInput):
    """Input schema for team list"""

    department: str | None = Field(
        None, description="Optional: filter by department (technology, operations, creative, etc.)"
    )


class TeamListOutput(PluginOutput):
    """Output schema for team list"""

    total_members: int | None = Field(None, description="Total number of team members")
    by_department: dict[str, list[dict[str, Any]]] | None = Field(
        None, description="Team members grouped by department"
    )
    roster: list[dict[str, Any]] | None = Field(None, description="Full team roster")
    stats: dict[str, Any] | None = Field(None, description="Team statistics")


class TeamMembersListPlugin(Plugin):
    """
    Get full Bali Zero team roster, optionally filtered by department.

    Returns complete team roster with roles, departments, expertise levels, and stats.
    """

    def __init__(self, config: dict | None = None, collaborator_service=None):
        """
        Initialize team list plugin

        Args:
            config: Optional plugin configuration
            collaborator_service: Optional collaborator service instance (for dependency injection/testing)
        """
        super().__init__(config)
        self.collaborator_service = collaborator_service or CollaboratorService()

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="team.list_members",
            version="1.0.0",
            description="Get full Bali Zero team roster, optionally filtered by department",
            category=PluginCategory.AUTH,
            tags=["team", "roster", "list", "members"],
            requires_auth=False,
            estimated_time=0.5,
            rate_limit=30,  # 30 calls per minute
            allowed_models=["haiku", "sonnet", "opus"],
            legacy_handler_key="get_team_members_list",
        )

    @property
    def input_schema(self):
        return TeamListInput

    @property
    def output_schema(self):
        return TeamListOutput

    async def execute(self, input_data: TeamListInput) -> TeamListOutput:
        """Execute team list query"""
        try:
            department = input_data.department.lower().strip() if input_data.department else None

            logger.debug(f"Team list: department={department}")

            profiles = self.collaborator_service.list_members(department)

            roster = [
                {
                    "name": profile.name,
                    "email": profile.email,
                    "role": profile.role,
                    "department": profile.department,
                    "expertise_level": profile.expertise_level,
                    "language": profile.language,
                    "traits": profile.traits,
                    "notes": profile.notes,
                }
                for profile in profiles
            ]

            # Group by department for better readability
            by_department = {}
            for member in roster:
                dept = member["department"]
                if dept not in by_department:
                    by_department[dept] = []
                by_department[dept].append(member)

            # Get team stats
            stats = self.collaborator_service.get_team_stats()

            return TeamListOutput(
                success=True,
                data={
                    "total_members": len(roster),
                    "by_department": by_department,
                    "roster": roster,
                    "stats": stats,
                },
                total_members=len(roster),
                by_department=by_department,
                roster=roster,
                stats=stats,
            )

        except Exception as e:
            logger.error(f"Team list error: {e}", exc_info=True)
            return TeamListOutput(success=False, error=f"Team list failed: {str(e)}")
