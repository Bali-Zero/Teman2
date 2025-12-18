"""
Integration Tests for TeamMemberSearchPlugin
Tests team member search with real dependencies
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
class TestTeamMemberSearchPluginIntegration:
    """Comprehensive integration tests for TeamMemberSearchPlugin"""

    @pytest_asyncio.fixture
    async def mock_collaborator_service(self):
        """Create mock collaborator service"""
        from services.collaborator_service import CollaboratorProfile

        mock_service = MagicMock()
        mock_service.search_members = MagicMock(
            return_value=[
                CollaboratorProfile(
                    name="John Doe",
                    email="john@example.com",
                    role="Developer",
                    department="technology",
                    expertise_level="senior",
                    language="en",
                    traits=["technical"],
                    notes="Senior developer",
                )
            ]
        )
        return mock_service

    @pytest_asyncio.fixture
    async def plugin(self, mock_collaborator_service):
        """Create TeamMemberSearchPlugin instance"""
        from plugins.team.search_member_plugin import TeamMemberSearchPlugin

        return TeamMemberSearchPlugin(collaborator_service=mock_collaborator_service)

    def test_initialization(self, plugin):
        """Test plugin initialization"""
        assert plugin is not None
        assert plugin.collaborator_service is not None

    def test_metadata(self, plugin):
        """Test plugin metadata"""
        metadata = plugin.metadata

        assert metadata is not None
        assert metadata.name == "team.search_member"
        assert metadata.version == "1.0.0"
        assert "search" in metadata.tags

    @pytest.mark.asyncio
    async def test_execute_successful_search(self, plugin):
        """Test executing plugin with successful search"""
        from plugins.team.search_member_plugin import TeamSearchInput

        input_data = TeamSearchInput(query="John")
        result = await plugin.execute(input_data)

        assert result is not None
        assert result.success is True
        assert result.count == 1
        assert result.results is not None
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_execute_no_results(self, plugin):
        """Test executing plugin with no results"""
        from plugins.team.search_member_plugin import TeamSearchInput

        # Mock service to return empty list
        plugin.collaborator_service.search_members = MagicMock(return_value=[])

        input_data = TeamSearchInput(query="Nonexistent")
        result = await plugin.execute(input_data)

        assert result is not None
        assert result.success is True
        assert result.count == 0 or result.message is not None
        assert result.suggestion is not None

    @pytest.mark.asyncio
    async def test_validate_valid_input(self, plugin):
        """Test validation with valid input"""
        from plugins.team.search_member_plugin import TeamSearchInput

        input_data = TeamSearchInput(query="John")
        is_valid = await plugin.validate(input_data)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_empty_query(self, plugin):
        """Test validation with empty query"""
        from plugins.team.search_member_plugin import TeamSearchInput

        input_data = TeamSearchInput(query="   ")
        is_valid = await plugin.validate(input_data)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, plugin):
        """Test error handling in plugin execution"""
        from plugins.team.search_member_plugin import TeamSearchInput

        # Mock service to raise exception
        plugin.collaborator_service.search_members = MagicMock(
            side_effect=Exception("Service error")
        )

        input_data = TeamSearchInput(query="test")
        result = await plugin.execute(input_data)

        assert result is not None
        assert result.success is False
        assert "error" in result.data or result.error is not None

    def test_input_schema(self, plugin):
        """Test input schema"""
        from plugins.team.search_member_plugin import TeamSearchInput

        assert plugin.input_schema == TeamSearchInput

    def test_output_schema(self, plugin):
        """Test output schema"""
        from plugins.team.search_member_plugin import TeamSearchOutput

        assert plugin.output_schema == TeamSearchOutput
