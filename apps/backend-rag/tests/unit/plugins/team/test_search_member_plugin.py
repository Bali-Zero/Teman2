"""
Unit tests for TeamMemberSearchPlugin
Tests team member search plugin functionality with 95%+ coverage
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from plugins.team.search_member_plugin import (
    TeamMemberSearchPlugin,
    TeamSearchInput,
    TeamSearchOutput,
)

from services.collaborator_service import CollaboratorProfile

# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def mock_collaborator_profile():
    """Create a mock collaborator profile"""
    return CollaboratorProfile(
        id="test-001",
        email="dea.mahendra@balizero.com",
        name="Dea Mahendra",
        role="Senior Developer",
        department="Engineering",
        team="Backend",
        language="id",
        languages=["id", "en"],
        expertise_level="senior",
        age=28,
        religion="Hindu",
        traits=["analytical", "detail-oriented"],
        notes="Excellent backend developer",
        pin="1234",
        location="Bali",
        emotional_preferences={"tone": "professional"},
        relationships=[{"type": "manager", "name": "Zero"}],
    )


@pytest.fixture
def mock_collaborator_service(mock_collaborator_profile):
    """Create a mock collaborator service"""
    service = MagicMock()
    service.search_members = MagicMock(return_value=[mock_collaborator_profile])
    return service


@pytest.fixture
def plugin_with_mock_service(mock_collaborator_service):
    """Create plugin with mocked collaborator service"""
    return TeamMemberSearchPlugin(collaborator_service=mock_collaborator_service)


# ============================================================================
# Tests for TeamSearchInput Model
# ============================================================================


def test_team_search_input_creation():
    """Test creating TeamSearchInput with valid data"""
    input_data = TeamSearchInput(query="Dea")
    assert input_data.query == "Dea"


def test_team_search_input_required_field():
    """Test TeamSearchInput requires query field"""
    with pytest.raises(Exception):  # Pydantic validation error
        TeamSearchInput()


def test_team_search_input_empty_query():
    """Test TeamSearchInput accepts empty string"""
    input_data = TeamSearchInput(query="")
    assert input_data.query == ""


def test_team_search_input_whitespace_query():
    """Test TeamSearchInput accepts whitespace"""
    input_data = TeamSearchInput(query="   ")
    assert input_data.query == "   "


# ============================================================================
# Tests for TeamSearchOutput Model
# ============================================================================


def test_team_search_output_creation():
    """Test creating TeamSearchOutput with results"""
    output = TeamSearchOutput(
        success=True,
        data={"count": 1, "results": [{"name": "Dea"}]},
        count=1,
        results=[{"name": "Dea"}],
    )
    assert output.success is True
    assert output.count == 1
    assert len(output.results) == 1


def test_team_search_output_no_results():
    """Test creating TeamSearchOutput with no results"""
    output = TeamSearchOutput(
        success=True,
        data={"message": "No team member found"},
        message="No team member found",
        suggestion="Try searching by first name",
    )
    assert output.success is True
    assert output.message == "No team member found"
    assert output.suggestion == "Try searching by first name"


def test_team_search_output_error():
    """Test creating TeamSearchOutput with error"""
    output = TeamSearchOutput(success=False, error="Search failed")
    assert output.success is False
    assert output.error == "Search failed"


def test_team_search_output_optional_fields():
    """Test TeamSearchOutput optional fields default to None"""
    output = TeamSearchOutput(success=True, data={})
    assert output.count is None
    assert output.results is None
    assert output.message is None
    assert output.suggestion is None


# ============================================================================
# Tests for TeamMemberSearchPlugin Initialization
# ============================================================================


def test_plugin_initialization_default():
    """Test plugin initialization with default collaborator service"""
    with patch("plugins.team.search_member_plugin.CollaboratorService") as mock_service_class:
        mock_service_class.return_value = MagicMock()
        plugin = TeamMemberSearchPlugin()

        assert plugin is not None
        assert plugin.collaborator_service is not None
        mock_service_class.assert_called_once()


def test_plugin_initialization_with_service(mock_collaborator_service):
    """Test plugin initialization with injected collaborator service"""
    plugin = TeamMemberSearchPlugin(collaborator_service=mock_collaborator_service)

    assert plugin is not None
    assert plugin.collaborator_service == mock_collaborator_service


def test_plugin_initialization_with_config(mock_collaborator_service):
    """Test plugin initialization with config"""
    config = {"test_key": "test_value"}
    plugin = TeamMemberSearchPlugin(config=config, collaborator_service=mock_collaborator_service)

    assert plugin.config == config
    assert plugin.collaborator_service == mock_collaborator_service


def test_plugin_initialization_no_config(mock_collaborator_service):
    """Test plugin initialization without config defaults to empty dict"""
    plugin = TeamMemberSearchPlugin(config=None, collaborator_service=mock_collaborator_service)

    assert plugin.config == {}


# ============================================================================
# Tests for Plugin Metadata Property
# ============================================================================


def test_plugin_metadata(plugin_with_mock_service):
    """Test plugin metadata returns correct values"""
    metadata = plugin_with_mock_service.metadata

    assert metadata.name == "team.search_member"
    assert metadata.version == "1.0.0"
    assert metadata.description == "Search for a Bali Zero team member by name"
    assert metadata.requires_auth is False
    assert metadata.estimated_time == 0.3
    assert metadata.rate_limit == 60


def test_plugin_metadata_category(plugin_with_mock_service):
    """Test plugin metadata category"""
    from core.plugins import PluginCategory

    metadata = plugin_with_mock_service.metadata
    assert metadata.category == PluginCategory.AUTH


def test_plugin_metadata_tags(plugin_with_mock_service):
    """Test plugin metadata tags"""
    metadata = plugin_with_mock_service.metadata

    assert "team" in metadata.tags
    assert "search" in metadata.tags
    assert "member" in metadata.tags
    assert "contact" in metadata.tags


def test_plugin_metadata_allowed_models(plugin_with_mock_service):
    """Test plugin metadata allowed models"""
    metadata = plugin_with_mock_service.metadata

    assert "haiku" in metadata.allowed_models
    assert "sonnet" in metadata.allowed_models
    assert "opus" in metadata.allowed_models


def test_plugin_metadata_legacy_handler_key(plugin_with_mock_service):
    """Test plugin metadata legacy handler key"""
    metadata = plugin_with_mock_service.metadata

    assert metadata.legacy_handler_key == "search_team_member"


# ============================================================================
# Tests for Plugin Schema Properties
# ============================================================================


def test_plugin_input_schema(plugin_with_mock_service):
    """Test plugin input schema property"""
    schema = plugin_with_mock_service.input_schema

    assert schema == TeamSearchInput


def test_plugin_output_schema(plugin_with_mock_service):
    """Test plugin output schema property"""
    schema = plugin_with_mock_service.output_schema

    assert schema == TeamSearchOutput


# ============================================================================
# Tests for Plugin Validate Method
# ============================================================================


@pytest.mark.asyncio
async def test_validate_valid_query(plugin_with_mock_service):
    """Test validation with valid query"""
    input_data = TeamSearchInput(query="Dea")

    result = await plugin_with_mock_service.validate(input_data)

    assert result is True


@pytest.mark.asyncio
async def test_validate_empty_query(plugin_with_mock_service):
    """Test validation with empty query returns False"""
    input_data = TeamSearchInput(query="")

    result = await plugin_with_mock_service.validate(input_data)

    assert result is False


@pytest.mark.asyncio
async def test_validate_whitespace_query(plugin_with_mock_service):
    """Test validation with whitespace-only query returns False"""
    input_data = TeamSearchInput(query="   ")

    result = await plugin_with_mock_service.validate(input_data)

    assert result is False


@pytest.mark.asyncio
async def test_validate_whitespace_with_text(plugin_with_mock_service):
    """Test validation with query containing text and whitespace"""
    input_data = TeamSearchInput(query="  Dea  ")

    result = await plugin_with_mock_service.validate(input_data)

    assert result is True


@pytest.mark.asyncio
async def test_validate_single_character_query(plugin_with_mock_service):
    """Test validation with single character query"""
    input_data = TeamSearchInput(query="D")

    result = await plugin_with_mock_service.validate(input_data)

    assert result is True


# ============================================================================
# Tests for Plugin Execute Method - Success Cases
# ============================================================================


@pytest.mark.asyncio
async def test_execute_with_results(plugin_with_mock_service, mock_collaborator_profile):
    """Test execute with search results found"""
    input_data = TeamSearchInput(query="Dea")

    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    assert result.count == 1
    assert len(result.results) == 1
    assert result.results[0]["name"] == "Dea Mahendra"
    assert result.results[0]["email"] == "dea.mahendra@balizero.com"
    assert result.results[0]["role"] == "Senior Developer"
    assert result.results[0]["department"] == "Engineering"
    assert result.results[0]["expertise_level"] == "senior"
    assert result.results[0]["language"] == "id"
    assert result.results[0]["traits"] == ["analytical", "detail-oriented"]
    assert result.results[0]["notes"] == "Excellent backend developer"


@pytest.mark.asyncio
async def test_execute_query_lowercased_and_stripped(plugin_with_mock_service):
    """Test execute properly lowercases and strips query"""
    input_data = TeamSearchInput(query="  DEA  ")

    await plugin_with_mock_service.execute(input_data)

    plugin_with_mock_service.collaborator_service.search_members.assert_called_once_with("dea")


@pytest.mark.asyncio
async def test_execute_multiple_results(plugin_with_mock_service):
    """Test execute with multiple search results"""
    profile1 = CollaboratorProfile(
        id="001",
        email="dev1@test.com",
        name="Developer One",
        role="Dev",
        department="Engineering",
        team="Backend",
        language="en",
    )
    profile2 = CollaboratorProfile(
        id="002",
        email="dev2@test.com",
        name="Developer Two",
        role="Dev",
        department="Engineering",
        team="Backend",
        language="en",
    )

    plugin_with_mock_service.collaborator_service.search_members.return_value = [profile1, profile2]

    input_data = TeamSearchInput(query="developer")
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    assert result.count == 2
    assert len(result.results) == 2
    assert result.results[0]["name"] == "Developer One"
    assert result.results[1]["name"] == "Developer Two"


@pytest.mark.asyncio
async def test_execute_data_field_contains_results(
    plugin_with_mock_service, mock_collaborator_profile
):
    """Test execute data field contains count and results"""
    input_data = TeamSearchInput(query="Dea")

    result = await plugin_with_mock_service.execute(input_data)

    assert "count" in result.data
    assert "results" in result.data
    assert result.data["count"] == 1
    assert len(result.data["results"]) == 1


# ============================================================================
# Tests for Plugin Execute Method - No Results
# ============================================================================


@pytest.mark.asyncio
async def test_execute_no_results(plugin_with_mock_service):
    """Test execute when no results found"""
    plugin_with_mock_service.collaborator_service.search_members.return_value = []

    input_data = TeamSearchInput(query="NonexistentPerson")
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    assert result.message == "No team member found matching 'nonexistentperson'"
    assert result.suggestion == "Try searching by first name or department"


@pytest.mark.asyncio
async def test_execute_no_results_data_field(plugin_with_mock_service):
    """Test execute no results includes message and suggestion in data"""
    plugin_with_mock_service.collaborator_service.search_members.return_value = []

    input_data = TeamSearchInput(query="test")
    result = await plugin_with_mock_service.execute(input_data)

    assert "message" in result.data
    assert "suggestion" in result.data
    assert result.data["message"] == "No team member found matching 'test'"
    assert result.data["suggestion"] == "Try searching by first name or department"


@pytest.mark.asyncio
async def test_execute_empty_list_results(plugin_with_mock_service):
    """Test execute with empty list from search"""
    plugin_with_mock_service.collaborator_service.search_members.return_value = []

    input_data = TeamSearchInput(query="xyz")
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    assert result.count is None
    assert result.results is None
    assert result.message is not None


# ============================================================================
# Tests for Plugin Execute Method - Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_execute_service_exception(plugin_with_mock_service):
    """Test execute handles service exceptions"""
    plugin_with_mock_service.collaborator_service.search_members.side_effect = Exception(
        "Database connection failed"
    )

    input_data = TeamSearchInput(query="Dea")
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is False
    assert "Team search failed" in result.error
    assert "Database connection failed" in result.error


@pytest.mark.asyncio
async def test_execute_service_runtime_error(plugin_with_mock_service):
    """Test execute handles runtime errors"""
    plugin_with_mock_service.collaborator_service.search_members.side_effect = RuntimeError(
        "Unexpected error"
    )

    input_data = TeamSearchInput(query="test")
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is False
    assert "Team search failed" in result.error


@pytest.mark.asyncio
async def test_execute_service_value_error(plugin_with_mock_service):
    """Test execute handles value errors"""
    plugin_with_mock_service.collaborator_service.search_members.side_effect = ValueError(
        "Invalid query format"
    )

    input_data = TeamSearchInput(query="test")
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is False
    assert "Team search failed" in result.error
    assert "Invalid query format" in result.error


@pytest.mark.asyncio
async def test_execute_service_attribute_error(plugin_with_mock_service):
    """Test execute handles attribute errors from malformed profiles"""
    plugin_with_mock_service.collaborator_service.search_members.side_effect = AttributeError(
        "'NoneType' object has no attribute 'name'"
    )

    input_data = TeamSearchInput(query="test")
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is False
    assert "Team search failed" in result.error


@pytest.mark.asyncio
async def test_execute_logs_debug_on_search(plugin_with_mock_service):
    """Test execute logs debug message with query"""
    input_data = TeamSearchInput(query="Dea")

    with patch("plugins.team.search_member_plugin.logger") as mock_logger:
        await plugin_with_mock_service.execute(input_data)

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "Team search" in call_args
        assert "query=dea" in call_args


@pytest.mark.asyncio
async def test_execute_logs_error_on_exception(plugin_with_mock_service):
    """Test execute logs error on exception"""
    plugin_with_mock_service.collaborator_service.search_members.side_effect = Exception(
        "Test error"
    )

    input_data = TeamSearchInput(query="test")

    with patch("plugins.team.search_member_plugin.logger") as mock_logger:
        await plugin_with_mock_service.execute(input_data)

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "Team search error" in call_args


# ============================================================================
# Tests for Profile Data Transformation
# ============================================================================


@pytest.mark.asyncio
async def test_execute_profile_field_mapping(plugin_with_mock_service, mock_collaborator_profile):
    """Test execute correctly maps all profile fields to result"""
    input_data = TeamSearchInput(query="Dea")

    result = await plugin_with_mock_service.execute(input_data)

    profile_dict = result.results[0]
    assert profile_dict["name"] == mock_collaborator_profile.name
    assert profile_dict["email"] == mock_collaborator_profile.email
    assert profile_dict["role"] == mock_collaborator_profile.role
    assert profile_dict["department"] == mock_collaborator_profile.department
    assert profile_dict["expertise_level"] == mock_collaborator_profile.expertise_level
    assert profile_dict["language"] == mock_collaborator_profile.language
    assert profile_dict["traits"] == mock_collaborator_profile.traits
    assert profile_dict["notes"] == mock_collaborator_profile.notes


@pytest.mark.asyncio
async def test_execute_profile_with_minimal_fields(plugin_with_mock_service):
    """Test execute with profile containing minimal fields"""
    minimal_profile = CollaboratorProfile(
        id="minimal",
        email="minimal@test.com",
        name="Minimal User",
        role="User",
        department="Test",
        team="Test",
        language="en",
    )

    plugin_with_mock_service.collaborator_service.search_members.return_value = [minimal_profile]

    input_data = TeamSearchInput(query="minimal")
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    profile_dict = result.results[0]
    assert profile_dict["name"] == "Minimal User"
    assert profile_dict["email"] == "minimal@test.com"
    assert profile_dict["traits"] == []
    assert profile_dict["notes"] is None


# ============================================================================
# Tests for Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_execute_with_special_characters_in_query(plugin_with_mock_service):
    """Test execute handles special characters in query"""
    input_data = TeamSearchInput(query="O'Brien")

    result = await plugin_with_mock_service.execute(input_data)

    plugin_with_mock_service.collaborator_service.search_members.assert_called_once_with("o'brien")


@pytest.mark.asyncio
async def test_execute_with_unicode_query(plugin_with_mock_service):
    """Test execute handles unicode characters"""
    input_data = TeamSearchInput(query="José")

    result = await plugin_with_mock_service.execute(input_data)

    plugin_with_mock_service.collaborator_service.search_members.assert_called_once_with("josé")


@pytest.mark.asyncio
async def test_execute_with_numbers_in_query(plugin_with_mock_service):
    """Test execute handles numbers in query"""
    input_data = TeamSearchInput(query="Dev123")

    result = await plugin_with_mock_service.execute(input_data)

    plugin_with_mock_service.collaborator_service.search_members.assert_called_once_with("dev123")


# ============================================================================
# Integration-style Tests
# ============================================================================


@pytest.mark.asyncio
async def test_full_workflow_with_results(plugin_with_mock_service, mock_collaborator_profile):
    """Test full workflow: validate -> execute with results"""
    input_data = TeamSearchInput(query="Dea")

    # Validate
    is_valid = await plugin_with_mock_service.validate(input_data)
    assert is_valid is True

    # Execute
    result = await plugin_with_mock_service.execute(input_data)
    assert result.success is True
    assert result.count == 1


@pytest.mark.asyncio
async def test_full_workflow_invalid_input(plugin_with_mock_service):
    """Test full workflow: validate fails -> should not execute"""
    input_data = TeamSearchInput(query="")

    # Validate
    is_valid = await plugin_with_mock_service.validate(input_data)
    assert is_valid is False

    # In real usage, execute would not be called if validation fails
    # But we can still test that execute handles empty query gracefully


@pytest.mark.asyncio
async def test_plugin_metadata_compatibility():
    """Test plugin metadata is compatible with plugin registry"""
    from core.plugins import PluginCategory, PluginMetadata

    with patch("plugins.team.search_member_plugin.CollaboratorService"):
        plugin = TeamMemberSearchPlugin()
        metadata = plugin.metadata

        # Verify metadata is a PluginMetadata instance
        assert isinstance(metadata, PluginMetadata)

        # Verify category is a valid PluginCategory
        assert isinstance(metadata.category, PluginCategory)

        # Verify version format
        assert isinstance(metadata.version, str)
        version_parts = metadata.version.split(".")
        assert len(version_parts) == 3


@pytest.mark.asyncio
async def test_plugin_can_be_called_multiple_times(plugin_with_mock_service):
    """Test plugin can be executed multiple times"""
    input_data1 = TeamSearchInput(query="Dea")
    input_data2 = TeamSearchInput(query="Zero")

    result1 = await plugin_with_mock_service.execute(input_data1)
    result2 = await plugin_with_mock_service.execute(input_data2)

    assert result1.success is True
    assert result2.success is True
    assert plugin_with_mock_service.collaborator_service.search_members.call_count == 2
