"""
Team Member Search Plugin

Migrated from: backend/services/zantara_tools.py -> _search_team_member
"""

import logging
from typing import Any

from core.plugins import Plugin, PluginCategory, PluginInput, PluginMetadata, PluginOutput
from pydantic import Field

from services.collaborator_service import CollaboratorService

logger = logging.getLogger(__name__)


class TeamSearchInput(PluginInput):
    """Input schema for team member search"""

    query: str = Field(..., description="Name to search for (e.g. 'Dea', 'Zero', 'Krisna')")


class TeamSearchOutput(PluginOutput):
    """Output schema for team member search"""

    count: int | None = Field(None, description="Number of results found")
    results: list[dict[str, Any]] | None = Field(None, description="List of matching team members")
    message: str | None = Field(None, description="Message if no results found")
    suggestion: str | None = Field(None, description="Suggestion if no results found")


class TeamMemberSearchPlugin(Plugin):
    """
    Search for Bali Zero team members by name.

    Returns contact info, role, department, expertise level, and language.
    """

    def __init__(self, config: dict | None = None, collaborator_service=None):
        """
        Initialize team search plugin

        Args:
            config: Optional plugin configuration
            collaborator_service: Optional collaborator service instance (for dependency injection/testing)
        """
        super().__init__(config)
        self.collaborator_service = collaborator_service or CollaboratorService()

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="team.search_member",
            version="1.0.0",
            description="Search for a Bali Zero team member by name",
            category=PluginCategory.AUTH,
            tags=["team", "search", "member", "contact"],
            requires_auth=False,
            estimated_time=0.3,
            rate_limit=60,  # 60 calls per minute
            allowed_models=["haiku", "sonnet", "opus"],
            legacy_handler_key="search_team_member",
        )

    @property
    def input_schema(self):
        return TeamSearchInput

    @property
    def output_schema(self):
        return TeamSearchOutput

    async def validate(self, input_data: TeamSearchInput) -> bool:
        """Validate input"""
        if not input_data.query or not input_data.query.strip():
            return False
        return True

    async def execute(self, input_data: TeamSearchInput) -> TeamSearchOutput:
        """Execute team member search"""
        try:
            query = input_data.query.lower().strip()

            logger.debug(f"Team search: query={query}")

            profiles = self.collaborator_service.search_members(query)

            results = [
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

            if not results:
                return TeamSearchOutput(
                    success=True,
                    data={
                        "message": f"No team member found matching '{query}'",
                        "suggestion": "Try searching by first name or department",
                    },
                    message=f"No team member found matching '{query}'",
                    suggestion="Try searching by first name or department",
                )

            return TeamSearchOutput(
                success=True,
                data={"count": len(results), "results": results},
                count=len(results),
                results=results,
            )

        except Exception as e:
            logger.error(f"Team search error: {e}", exc_info=True)
            return TeamSearchOutput(success=False, error=f"Team search failed: {str(e)}")
