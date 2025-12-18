"""
Unit tests for ZantaraTools
Tests Zantara tools functionality
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestZantaraTools:
    """Unit tests for ZantaraTools"""

    @pytest.fixture
    def mock_pricing_service(self):
        """Create mock pricing service"""
        mock = MagicMock()
        mock.get_pricing = MagicMock(return_value={"visa": {"price": 100}})
        return mock

    @pytest.fixture
    def mock_collaborator_service(self):
        """Create mock collaborator service"""
        mock = MagicMock()
        mock.list_members = AsyncMock(return_value=[])
        mock.search_members = AsyncMock(return_value=[])
        return mock

    def test_zantara_tools_init(self):
        """Test ZantaraTools initialization"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab.return_value = MagicMock()

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            assert tools is not None
            assert tools.pricing_service is not None
            assert tools.collaborator_service is not None

    @pytest.mark.asyncio
    async def test_execute_tool_get_pricing(self):
        """Test executing get_pricing tool"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_pricing = MagicMock()
            mock_pricing.get_pricing = MagicMock(return_value={"visa": {"price": 100}})
            mock_get_pricing.return_value = mock_pricing
            mock_collab.return_value = MagicMock()

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("get_pricing", {"service_type": "visa"})

            assert isinstance(result, dict)
            assert "success" in result or "visa" in result

    @pytest.mark.asyncio
    async def test_execute_tool_search_team_member(self):
        """Test executing search_team_member tool"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab_instance = MagicMock()
            mock_collab_instance.search_members = AsyncMock(return_value=[{"name": "John"}])
            mock_collab.return_value = mock_collab_instance

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("search_team_member", {"query": "John"})

            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self):
        """Test executing unknown tool"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab.return_value = MagicMock()

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("unknown_tool", {})

            assert isinstance(result, dict)
            assert result.get("success") is False

    # ============================================================================
    # Expanded Tests
    # ============================================================================

    @pytest.mark.asyncio
    async def test_execute_tool_get_pricing_with_query(self):
        """Test get_pricing tool with search query"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_pricing = MagicMock()
            mock_pricing.loaded = True
            mock_pricing.search_service = MagicMock(return_value={"visa": {"price": 100}})
            mock_get_pricing.return_value = mock_pricing
            mock_collab.return_value = MagicMock()

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool(
                "get_pricing", {"service_type": "visa", "query": "long-stay"}
            )

            assert isinstance(result, dict)
            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_execute_tool_get_pricing_not_loaded(self):
        """Test get_pricing when prices not loaded"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_pricing = MagicMock()
            mock_pricing.loaded = False
            mock_get_pricing.return_value = mock_pricing
            mock_collab.return_value = MagicMock()

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("get_pricing", {"service_type": "visa"})

            assert isinstance(result, dict)
            assert result.get("success") is False
            assert "fallback_contact" in result

    @pytest.mark.asyncio
    async def test_execute_tool_get_pricing_error(self):
        """Test get_pricing handles errors gracefully"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_pricing = MagicMock()
            mock_pricing.loaded = True
            mock_pricing.get_pricing = MagicMock(side_effect=Exception("Pricing error"))
            mock_get_pricing.return_value = mock_pricing
            mock_collab.return_value = MagicMock()

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("get_pricing", {"service_type": "visa"})

            assert isinstance(result, dict)
            assert result.get("success") is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_tool_search_team_member_empty_query(self):
        """Test search_team_member with empty query"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab.return_value = MagicMock()

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("search_team_member", {"query": ""})

            assert isinstance(result, dict)
            assert result.get("success") is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_tool_search_team_member_no_results(self):
        """Test search_team_member with no results"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab_instance = MagicMock()
            mock_collab_instance.search_members = MagicMock(return_value=[])
            mock_collab.return_value = mock_collab_instance

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("search_team_member", {"query": "nonexistent"})

            assert isinstance(result, dict)
            assert result.get("success") is True
            assert "message" in result.get("data", {})

    @pytest.mark.asyncio
    async def test_execute_tool_get_team_members_list(self):
        """Test get_team_members_list tool"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab_instance = MagicMock()
            mock_collab_instance.list_members = MagicMock(return_value=[])
            mock_collab_instance.get_team_stats = MagicMock(return_value={"total": 0})
            mock_collab.return_value = mock_collab_instance

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("get_team_members_list", {})

            assert isinstance(result, dict)
            assert result.get("success") is True
            assert "data" in result
            assert "total_members" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_tool_get_team_members_list_with_department(self):
        """Test get_team_members_list with department filter"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab_instance = MagicMock()
            mock_collab_instance.list_members = MagicMock(return_value=[])
            mock_collab_instance.get_team_stats = MagicMock(return_value={"total": 0})
            mock_collab.return_value = mock_collab_instance

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("get_team_members_list", {"department": "technology"})

            assert isinstance(result, dict)
            assert result.get("success") is True
            mock_collab_instance.list_members.assert_called_with("technology")

    @pytest.mark.asyncio
    async def test_execute_tool_error_handling(self):
        """Test execute_tool handles exceptions gracefully"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab_instance = MagicMock()
            mock_collab_instance.search_members = MagicMock(side_effect=Exception("Service error"))
            mock_collab.return_value = mock_collab_instance

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            result = await tools.execute_tool("search_team_member", {"query": "test"})

            assert isinstance(result, dict)
            assert result.get("success") is False
            assert "error" in result

    def test_get_tool_definitions(self):
        """Test get_tool_definitions returns correct structure"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab.return_value = MagicMock()

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            definitions = tools.get_tool_definitions()

            assert isinstance(definitions, list)
            assert len(definitions) >= 3
            tool_names = [t["name"] for t in definitions]
            assert "get_pricing" in tool_names
            assert "search_team_member" in tool_names
            assert "get_team_members_list" in tool_names

    def test_get_tool_definitions_structure(self):
        """Test tool definitions have correct structure"""
        with (
            patch("backend.services.zantara_tools.get_pricing_service") as mock_get_pricing,
            patch("backend.services.zantara_tools.CollaboratorService") as mock_collab,
        ):
            mock_get_pricing.return_value = MagicMock()
            mock_collab.return_value = MagicMock()

            from backend.services.zantara_tools import ZantaraTools

            tools = ZantaraTools()
            definitions = tools.get_tool_definitions()

            for tool in definitions:
                assert "name" in tool
                assert "description" in tool
                assert "input_schema" in tool
                assert "type" in tool["input_schema"]
                assert "properties" in tool["input_schema"]

    def test_get_zantara_tools_singleton(self):
        """Test get_zantara_tools returns singleton"""
        from backend.services.zantara_tools import get_zantara_tools

        tools1 = get_zantara_tools()
        tools2 = get_zantara_tools()

        assert tools1 is tools2 or "error" in result
