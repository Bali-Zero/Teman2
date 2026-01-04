"""
Unit tests for ZantaraTools
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.zantara_tools import ZantaraTools


@pytest.fixture
def mock_pricing_service():
    """Mock pricing service"""
    service = MagicMock()
    service.loaded = True
    service.get_pricing = MagicMock(return_value={"visa": {"price": 100}})
    service.search_service = MagicMock(return_value={"service": "test"})
    return service


@pytest.fixture
def mock_collaborator_service():
    """Mock collaborator service"""
    service = MagicMock()
    service.search_members = MagicMock(return_value=[])
    service.list_members = MagicMock(return_value=[])
    service.get_team_stats = MagicMock(return_value={"total": 0})
    return service


@pytest.fixture
def zantara_tools(mock_pricing_service, mock_collaborator_service):
    """Create ZantaraTools instance"""
    with (
        patch("services.misc.zantara_tools.get_pricing_service", return_value=mock_pricing_service),
        patch(
            "services.misc.zantara_tools.CollaboratorService",
            return_value=mock_collaborator_service,
        ),
    ):
        return ZantaraTools()


class TestZantaraTools:
    """Tests for ZantaraTools"""

    def test_init(self, zantara_tools):
        """Test initialization"""
        assert zantara_tools.pricing_service is not None
        assert zantara_tools.collaborator_service is not None

    @pytest.mark.asyncio
    async def test_execute_tool_get_pricing(self, zantara_tools, mock_pricing_service):
        """Test executing get_pricing tool"""
        result = await zantara_tools.execute_tool("get_pricing", {"service_type": "visa"})
        assert result["success"] is True
        assert "data" in result
        mock_pricing_service.get_pricing.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_get_pricing_with_query(self, zantara_tools, mock_pricing_service):
        """Test executing get_pricing tool with query"""
        result = await zantara_tools.execute_tool(
            "get_pricing", {"service_type": "visa", "query": "test"}
        )
        assert result["success"] is True
        mock_pricing_service.search_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_get_pricing_not_loaded(self, zantara_tools, mock_pricing_service):
        """Test executing get_pricing when prices not loaded"""
        mock_pricing_service.loaded = False
        result = await zantara_tools.execute_tool("get_pricing", {"service_type": "visa"})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_tool_search_team_member(self, zantara_tools, mock_collaborator_service):
        """Test executing search_team_member tool"""
        result = await zantara_tools.execute_tool("search_team_member", {"query": "test"})
        assert result["success"] is True
        mock_collaborator_service.search_members.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_get_team_members_list(
        self, zantara_tools, mock_collaborator_service
    ):
        """Test executing get_team_members_list tool"""
        result = await zantara_tools.execute_tool("get_team_members_list", {})
        assert result["success"] is True
        mock_collaborator_service.list_members.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, zantara_tools):
        """Test executing unknown tool"""
        result = await zantara_tools.execute_tool("unknown_tool", {})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_tool_exception(self, zantara_tools, mock_pricing_service):
        """Test executing tool with exception"""
        mock_pricing_service.get_pricing.side_effect = Exception("Test error")
        result = await zantara_tools.execute_tool("get_pricing", {"service_type": "visa"})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_team_member_empty_query(self, zantara_tools):
        """Test search_team_member with empty query"""
        result = await zantara_tools.execute_tool("search_team_member", {"query": ""})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_team_member_with_results(self, zantara_tools, mock_collaborator_service):
        """Test search_team_member with results"""
        mock_profile = MagicMock()
        mock_profile.name = "Test User"
        mock_profile.email = "test@example.com"
        mock_profile.role = "Developer"
        mock_profile.department = "Tech"
        mock_profile.expertise_level = "Senior"
        mock_profile.language = "English"
        mock_profile.notes = "Test notes"
        mock_profile.traits = ["helpful", "friendly"]
        mock_collaborator_service.search_members.return_value = [mock_profile]

        result = await zantara_tools.execute_tool("search_team_member", {"query": "test"})
        assert result["success"] is True
        assert result["data"]["count"] == 1
        assert len(result["data"]["results"]) == 1

    @pytest.mark.asyncio
    async def test_get_team_members_list_with_department(
        self, zantara_tools, mock_collaborator_service
    ):
        """Test get_team_members_list with department filter"""
        mock_profile = MagicMock()
        mock_profile.name = "Test User"
        mock_profile.email = "test@example.com"
        mock_profile.role = "Developer"
        mock_profile.department = "Tech"
        mock_profile.expertise_level = "Senior"
        mock_profile.language = "English"
        mock_profile.traits = []
        mock_profile.notes = ""
        mock_collaborator_service.list_members.return_value = [mock_profile]
        mock_collaborator_service.get_team_stats.return_value = {"total": 1}

        result = await zantara_tools.execute_tool("get_team_members_list", {"department": "Tech"})
        assert result["success"] is True
        assert result["data"]["total_members"] == 1

    def test_get_tool_definitions(self, zantara_tools):
        """Test get_tool_definitions"""
        tools = zantara_tools.get_tool_definitions()
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert any(tool["name"] == "get_pricing" for tool in tools)

    def test_get_tool_definitions_with_admin(self, zantara_tools):
        """Test get_tool_definitions (parameter is ignored but method accepts it)"""
        # The method signature has _include_admin_tools but it's ignored
        tools = zantara_tools.get_tool_definitions()
        assert isinstance(tools, list)
