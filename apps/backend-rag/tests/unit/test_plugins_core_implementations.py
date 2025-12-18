"""
Unit tests for Core Plugin Implementations (Pricing, Team List, Team Search)
Coverage target: 90%+ for all three plugins
Tests plugin execution, validation, error handling
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from plugins.bali_zero.pricing_plugin import PricingPlugin, PricingQueryInput, PricingQueryOutput
from plugins.team.list_members_plugin import TeamListInput, TeamListOutput, TeamMembersListPlugin
from plugins.team.search_member_plugin import (
    TeamMemberSearchPlugin,
    TeamSearchInput,
    TeamSearchOutput,
)

# ============================================================================
# Tests for PricingPlugin
# ============================================================================


def test_pricing_plugin_metadata():
    """Test PricingPlugin metadata"""
    plugin = PricingPlugin()

    assert plugin.metadata.name == "bali_zero.pricing"
    assert plugin.metadata.version == "1.0.0"
    assert (
        "OFFICIAL" in plugin.metadata.description
        or "official" in plugin.metadata.description.lower()
    )
    assert "pricing" in plugin.metadata.tags
    assert plugin.metadata.requires_auth is False
    assert plugin.metadata.rate_limit == 30


def test_pricing_plugin_schemas():
    """Test PricingPlugin input/output schemas"""
    plugin = PricingPlugin()

    assert plugin.input_schema == PricingQueryInput
    assert plugin.output_schema == PricingQueryOutput


@pytest.mark.asyncio
async def test_pricing_plugin_execute_all_services():
    """Test executing pricing query for all services"""
    plugin = PricingPlugin()

    # Mock the pricing service
    mock_pricing_service = MagicMock()
    mock_pricing_service.loaded = True
    test_data = [{"service": "visa", "price": "100 USD"}]
    mock_pricing_service.get_pricing = MagicMock(return_value=test_data)
    plugin.pricing_service = mock_pricing_service

    input_data = PricingQueryInput(service_type="all")
    result = await plugin.execute(input_data)

    assert result.success is True
    assert result.prices == test_data
    mock_pricing_service.get_pricing.assert_called_once_with("all")


@pytest.mark.asyncio
async def test_pricing_plugin_execute_with_query():
    """Test executing pricing query with search query"""
    plugin = PricingPlugin()

    # Mock the pricing service
    mock_pricing_service = MagicMock()
    mock_pricing_service.loaded = True
    test_search = [{"service": "tourist_visa", "price": "2.300.000 IDR"}]
    mock_pricing_service.search_service = MagicMock(return_value=test_search)
    plugin.pricing_service = mock_pricing_service

    input_data = PricingQueryInput(service_type="visa", query="tourist visa")
    result = await plugin.execute(input_data)

    assert result.success is True
    assert result.prices == test_search
    mock_pricing_service.search_service.assert_called_once_with("tourist visa")


@pytest.mark.asyncio
async def test_pricing_plugin_execute_not_loaded():
    """Test executing pricing query when service not loaded"""
    plugin = PricingPlugin()

    # Mock the pricing service as not loaded
    mock_pricing_service = MagicMock()
    mock_pricing_service.loaded = False
    plugin.pricing_service = mock_pricing_service

    input_data = PricingQueryInput(service_type="visa")
    result = await plugin.execute(input_data)

    assert result.success is False
    assert result.error == "Official prices not loaded"
    assert result.fallback_contact is not None
    assert "info@balizero.com" in result.fallback_contact["email"]


@pytest.mark.asyncio
async def test_pricing_plugin_execute_exception():
    """Test executing pricing query with exception"""
    plugin = PricingPlugin()

    # Mock the pricing service to raise exception
    mock_pricing_service = MagicMock()
    mock_pricing_service.loaded = True
    mock_pricing_service.get_pricing = MagicMock(side_effect=Exception("Test error"))
    plugin.pricing_service = mock_pricing_service

    input_data = PricingQueryInput(service_type="visa")
    result = await plugin.execute(input_data)

    assert result.success is False
    assert "Pricing lookup failed" in result.error
    assert "Test error" in result.error


# ============================================================================
# Tests for TeamMembersListPlugin
# ============================================================================


def test_team_list_plugin_metadata():
    """Test TeamMembersListPlugin metadata"""
    plugin = TeamMembersListPlugin()

    assert plugin.metadata.name == "team.list_members"
    assert plugin.metadata.version == "1.0.0"
    assert (
        "roster" in plugin.metadata.description.lower()
        or "team" in plugin.metadata.description.lower()
    )
    assert "team" in plugin.metadata.tags
    assert plugin.metadata.requires_auth is False


def test_team_list_plugin_schemas():
    """Test TeamMembersListPlugin input/output schemas"""
    plugin = TeamMembersListPlugin()

    assert plugin.input_schema == TeamListInput
    assert plugin.output_schema == TeamListOutput


@pytest.mark.asyncio
async def test_team_list_plugin_execute_all_members():
    """Test executing team list without department filter"""
    plugin = TeamMembersListPlugin()

    # Mock collaborator service
    mock_profile = MagicMock()
    mock_profile.name = "Test User"
    mock_profile.email = "test@example.com"
    mock_profile.role = "Developer"
    mock_profile.department = "Technology"
    mock_profile.expertise_level = "Senior"
    mock_profile.language = "English"
    mock_profile.traits = []
    mock_profile.notes = "Test notes"

    mock_service = MagicMock()
    mock_service.list_members = MagicMock(return_value=[mock_profile])
    mock_service.get_team_stats = MagicMock(return_value={"total": 1})
    plugin.collaborator_service = mock_service

    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is True
    assert result.total_members == 1
    assert len(result.roster) == 1
    assert result.roster[0]["name"] == "Test User"
    assert result.roster[0]["department"] == "Technology"
    assert "Technology" in result.by_department
    mock_service.list_members.assert_called_once_with(None)


@pytest.mark.asyncio
async def test_team_list_plugin_execute_with_department():
    """Test executing team list with department filter"""
    plugin = TeamMembersListPlugin()

    # Mock collaborator service
    mock_profile = MagicMock()
    mock_profile.name = "Tech User"
    mock_profile.email = "tech@example.com"
    mock_profile.role = "Engineer"
    mock_profile.department = "Technology"
    mock_profile.expertise_level = "Mid"
    mock_profile.language = "English"
    mock_profile.traits = []
    mock_profile.notes = ""

    mock_service = MagicMock()
    mock_service.list_members = MagicMock(return_value=[mock_profile])
    mock_service.get_team_stats = MagicMock(return_value={"technology": 1})
    plugin.collaborator_service = mock_service

    input_data = TeamListInput(department="Technology")
    result = await plugin.execute(input_data)

    assert result.success is True
    assert result.total_members == 1
    mock_service.list_members.assert_called_once_with("technology")


@pytest.mark.asyncio
async def test_team_list_plugin_execute_exception():
    """Test executing team list with exception"""
    plugin = TeamMembersListPlugin()

    # Mock collaborator service to raise exception
    mock_service = MagicMock()
    mock_service.list_members = MagicMock(side_effect=Exception("Service error"))
    plugin.collaborator_service = mock_service

    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is False
    assert "Team list failed" in result.error
    assert "Service error" in result.error


# ============================================================================
# Tests for TeamMemberSearchPlugin
# ============================================================================


def test_team_search_plugin_metadata():
    """Test TeamMemberSearchPlugin metadata"""
    plugin = TeamMemberSearchPlugin()

    assert plugin.metadata.name == "team.search_member"
    assert plugin.metadata.version == "1.0.0"
    assert "search" in plugin.metadata.description.lower()
    assert "team" in plugin.metadata.tags
    assert plugin.metadata.requires_auth is False


def test_team_search_plugin_schemas():
    """Test TeamMemberSearchPlugin input/output schemas"""
    plugin = TeamMemberSearchPlugin()

    assert plugin.input_schema == TeamSearchInput
    assert plugin.output_schema == TeamSearchOutput


@pytest.mark.asyncio
async def test_team_search_plugin_validate_valid():
    """Test validating valid search input"""
    plugin = TeamMemberSearchPlugin()

    input_data = TeamSearchInput(query="John")
    result = await plugin.validate(input_data)

    assert result is True


@pytest.mark.asyncio
async def test_team_search_plugin_validate_empty():
    """Test validating empty search input"""
    plugin = TeamMemberSearchPlugin()

    input_data = TeamSearchInput(query="")
    result = await plugin.validate(input_data)

    assert result is False


@pytest.mark.asyncio
async def test_team_search_plugin_validate_whitespace():
    """Test validating whitespace-only search input"""
    plugin = TeamMemberSearchPlugin()

    input_data = TeamSearchInput(query="   ")
    result = await plugin.validate(input_data)

    assert result is False


@pytest.mark.asyncio
async def test_team_search_plugin_execute_found():
    """Test executing search with results found"""
    plugin = TeamMemberSearchPlugin()

    # Mock collaborator service
    mock_profile = MagicMock()
    mock_profile.name = "John Doe"
    mock_profile.email = "john@example.com"
    mock_profile.role = "Developer"
    mock_profile.department = "Technology"
    mock_profile.expertise_level = "Senior"
    mock_profile.language = "English"
    mock_profile.traits = ["python", "golang"]
    mock_profile.notes = "Expert developer"

    mock_service = MagicMock()
    mock_service.search_members = MagicMock(return_value=[mock_profile])
    plugin.collaborator_service = mock_service

    input_data = TeamSearchInput(query="John")
    result = await plugin.execute(input_data)

    assert result.success is True
    assert result.count == 1
    assert len(result.results) == 1
    assert result.results[0]["name"] == "John Doe"
    assert result.results[0]["email"] == "john@example.com"
    mock_service.search_members.assert_called_once_with("john")


@pytest.mark.asyncio
async def test_team_search_plugin_execute_not_found():
    """Test executing search with no results"""
    plugin = TeamMemberSearchPlugin()

    # Mock collaborator service returning empty list
    mock_service = MagicMock()
    mock_service.search_members = MagicMock(return_value=[])
    plugin.collaborator_service = mock_service

    input_data = TeamSearchInput(query="NonExistent")
    result = await plugin.execute(input_data)

    assert result.success is True
    assert result.message is not None
    assert "No team member found" in result.message
    assert result.suggestion is not None
    mock_service.search_members.assert_called_once_with("nonexistent")


@pytest.mark.asyncio
async def test_team_search_plugin_execute_exception():
    """Test executing search with exception"""
    plugin = TeamMemberSearchPlugin()

    # Mock collaborator service to raise exception
    mock_service = MagicMock()
    mock_service.search_members = MagicMock(side_effect=Exception("Search error"))
    plugin.collaborator_service = mock_service

    input_data = TeamSearchInput(query="Test")
    result = await plugin.execute(input_data)

    assert result.success is False
    assert "Team search failed" in result.error
    assert "Search error" in result.error


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_all_plugins_have_unique_names():
    """Test all plugins have unique names"""
    pricing = PricingPlugin()
    team_list = TeamMembersListPlugin()
    team_search = TeamMemberSearchPlugin()

    names = [pricing.metadata.name, team_list.metadata.name, team_search.metadata.name]

    assert len(names) == len(set(names))
    assert "bali_zero.pricing" in names
    assert "team.list_members" in names
    assert "team.search_member" in names


def test_all_plugins_same_version():
    """Test all plugins use same version"""
    pricing = PricingPlugin()
    team_list = TeamMembersListPlugin()
    team_search = TeamMemberSearchPlugin()

    versions = [pricing.metadata.version, team_list.metadata.version, team_search.metadata.version]

    assert all(v == "1.0.0" for v in versions)
