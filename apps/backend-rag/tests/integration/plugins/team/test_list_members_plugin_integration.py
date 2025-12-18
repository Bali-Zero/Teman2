"""
Integration Tests for TeamMembersListPlugin
Tests team member listing with real dependencies
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestTeamMembersListPluginIntegration:
    """Comprehensive integration tests for TeamMembersListPlugin"""

    @pytest_asyncio.fixture
    async def mock_collaborator_service(self):
        """Create mock collaborator service"""
        from services.collaborator_service import CollaboratorProfile

        mock_service = MagicMock()
        mock_service.list_members = MagicMock(
            return_value=[
                CollaboratorProfile(
                    name="John Doe",
                    email="john@example.com",
                    role="Developer",
                    department="technology",
                    expertise_level="senior",
                    language="en",
                    traits=["technical", "analytical"],
                    notes="Senior developer",
                ),
                CollaboratorProfile(
                    name="Jane Smith",
                    email="jane@example.com",
                    role="Designer",
                    department="creative",
                    expertise_level="mid",
                    language="en",
                    traits=["creative", "visual"],
                    notes="UI/UX designer",
                ),
            ]
        )
        mock_service.get_team_stats = MagicMock(
            return_value={"total": 2, "by_department": {"technology": 1, "creative": 1}}
        )
        return mock_service

    @pytest_asyncio.fixture
    async def plugin(self, mock_collaborator_service):
        """Create TeamMembersListPlugin instance"""
        from plugins.team.list_members_plugin import TeamMembersListPlugin

        return TeamMembersListPlugin(collaborator_service=mock_collaborator_service)

    def test_initialization(self, plugin):
        """Test plugin initialization"""
        assert plugin is not None
        assert plugin.collaborator_service is not None

    def test_metadata(self, plugin):
        """Test plugin metadata"""
        metadata = plugin.metadata

        assert metadata is not None
        assert metadata.name == "team.list_members"
        assert metadata.version == "1.0.0"
        assert "team" in metadata.tags

    @pytest.mark.asyncio
    async def test_execute_all_members(self, plugin):
        """Test executing plugin to get all members"""
        from plugins.team.list_members_plugin import TeamListInput

        input_data = TeamListInput()
        result = await plugin.execute(input_data)

        assert result is not None
        assert result.success is True
        assert result.total_members == 2
        assert result.roster is not None
        assert len(result.roster) == 2

    @pytest.mark.asyncio
    async def test_execute_filter_by_department(self, plugin):
        """Test executing plugin filtered by department"""
        from plugins.team.list_members_plugin import TeamListInput

        input_data = TeamListInput(department="technology")
        result = await plugin.execute(input_data)

        assert result is not None
        assert result.success is True
        assert "by_department" in result.data

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, plugin):
        """Test error handling in plugin execution"""
        from plugins.team.list_members_plugin import TeamListInput

        # Mock service to raise exception
        plugin.collaborator_service.list_members = MagicMock(side_effect=Exception("Service error"))

        input_data = TeamListInput()
        result = await plugin.execute(input_data)

        assert result is not None
        assert result.success is False
        assert "error" in result.data or result.error is not None

    def test_input_schema(self, plugin):
        """Test input schema"""
        from plugins.team.list_members_plugin import TeamListInput

        assert plugin.input_schema == TeamListInput

    def test_output_schema(self, plugin):
        """Test output schema"""
        from plugins.team.list_members_plugin import TeamListOutput

        assert plugin.output_schema == TeamListOutput
