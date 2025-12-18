"""
Unit tests for TeamMembersListPlugin
Coverage target: 95%+ for list_members_plugin.py
Tests plugin initialization, metadata, schemas, execution, and error handling
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.plugins import PluginCategory
from plugins.team.list_members_plugin import (
    TeamListInput,
    TeamListOutput,
    TeamMembersListPlugin,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_collaborator_profile():
    """Create a mock CollaboratorProfile"""
    profile = Mock()
    profile.name = "John Doe"
    profile.email = "john.doe@balizero.com"
    profile.role = "Senior Developer"
    profile.department = "Technology"
    profile.expertise_level = "senior"
    profile.language = "English"
    profile.traits = ["analytical", "detail-oriented"]
    profile.notes = "Expert in backend systems"
    return profile


@pytest.fixture
def mock_collaborator_service(mock_collaborator_profile):
    """Create a mock CollaboratorService"""
    service = MagicMock()
    service.list_members = MagicMock(return_value=[mock_collaborator_profile])
    service.get_team_stats = MagicMock(
        return_value={
            "total": 1,
            "departments": {"Technology": 1},
            "languages": {"English": 1},
        }
    )
    return service


@pytest.fixture
def plugin_with_mock_service(mock_collaborator_service):
    """Create TeamMembersListPlugin with mocked service"""
    return TeamMembersListPlugin(collaborator_service=mock_collaborator_service)


# ============================================================================
# Test Models - TeamListInput
# ============================================================================


def test_team_list_input_no_department():
    """Test TeamListInput creation without department filter"""
    input_data = TeamListInput()
    assert input_data.department is None


def test_team_list_input_with_department():
    """Test TeamListInput creation with department filter"""
    input_data = TeamListInput(department="Technology")
    assert input_data.department == "Technology"


def test_team_list_input_field_metadata():
    """Test TeamListInput field has proper metadata"""
    schema = TeamListInput.model_json_schema()
    assert "properties" in schema
    assert "department" in schema["properties"]
    assert "description" in schema["properties"]["department"]
    assert "filter by department" in schema["properties"]["department"]["description"]


# ============================================================================
# Test Models - TeamListOutput
# ============================================================================


def test_team_list_output_creation():
    """Test TeamListOutput creation with all fields"""
    output = TeamListOutput(
        success=True,
        total_members=5,
        by_department={"Technology": [{"name": "John"}]},
        roster=[{"name": "John"}],
        stats={"total": 5},
    )
    assert output.success is True
    assert output.total_members == 5
    assert "Technology" in output.by_department
    assert len(output.roster) == 1
    assert output.stats["total"] == 5


def test_team_list_output_optional_fields():
    """Test TeamListOutput with optional fields as None"""
    output = TeamListOutput(success=True)
    assert output.success is True
    assert output.total_members is None
    assert output.by_department is None
    assert output.roster is None
    assert output.stats is None


def test_team_list_output_error_state():
    """Test TeamListOutput in error state"""
    output = TeamListOutput(success=False, error="Service unavailable")
    assert output.success is False
    assert output.error == "Service unavailable"
    assert output.total_members is None


# ============================================================================
# Test Plugin Initialization
# ============================================================================


def test_plugin_init_default():
    """Test plugin initialization with default CollaboratorService"""
    plugin = TeamMembersListPlugin()
    assert plugin.collaborator_service is not None
    assert hasattr(plugin.collaborator_service, "list_members")
    assert hasattr(plugin.collaborator_service, "get_team_stats")


def test_plugin_init_with_config():
    """Test plugin initialization with config"""
    config = {"test_key": "test_value"}
    plugin = TeamMembersListPlugin(config=config)
    assert plugin.config == config
    assert plugin.collaborator_service is not None


def test_plugin_init_with_mock_service(mock_collaborator_service):
    """Test plugin initialization with injected service"""
    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    assert plugin.collaborator_service == mock_collaborator_service


def test_plugin_init_with_both_config_and_service(mock_collaborator_service):
    """Test plugin initialization with both config and service"""
    config = {"custom": "config"}
    plugin = TeamMembersListPlugin(config=config, collaborator_service=mock_collaborator_service)
    assert plugin.config == config
    assert plugin.collaborator_service == mock_collaborator_service


# ============================================================================
# Test Plugin Metadata
# ============================================================================


def test_plugin_metadata_name(plugin_with_mock_service):
    """Test plugin metadata name"""
    metadata = plugin_with_mock_service.metadata
    assert metadata.name == "team.list_members"


def test_plugin_metadata_version(plugin_with_mock_service):
    """Test plugin metadata version"""
    metadata = plugin_with_mock_service.metadata
    assert metadata.version == "1.0.0"


def test_plugin_metadata_description(plugin_with_mock_service):
    """Test plugin metadata description"""
    metadata = plugin_with_mock_service.metadata
    assert "Bali Zero team roster" in metadata.description
    assert "department" in metadata.description.lower()


def test_plugin_metadata_category(plugin_with_mock_service):
    """Test plugin metadata category"""
    metadata = plugin_with_mock_service.metadata
    assert metadata.category == PluginCategory.AUTH


def test_plugin_metadata_tags(plugin_with_mock_service):
    """Test plugin metadata tags"""
    metadata = plugin_with_mock_service.metadata
    assert "team" in metadata.tags
    assert "roster" in metadata.tags
    assert "list" in metadata.tags
    assert "members" in metadata.tags


def test_plugin_metadata_auth_requirement(plugin_with_mock_service):
    """Test plugin does not require authentication"""
    metadata = plugin_with_mock_service.metadata
    assert metadata.requires_auth is False


def test_plugin_metadata_estimated_time(plugin_with_mock_service):
    """Test plugin estimated execution time"""
    metadata = plugin_with_mock_service.metadata
    assert metadata.estimated_time == 0.5


def test_plugin_metadata_rate_limit(plugin_with_mock_service):
    """Test plugin rate limit"""
    metadata = plugin_with_mock_service.metadata
    assert metadata.rate_limit == 30


def test_plugin_metadata_allowed_models(plugin_with_mock_service):
    """Test plugin allowed models"""
    metadata = plugin_with_mock_service.metadata
    assert "haiku" in metadata.allowed_models
    assert "sonnet" in metadata.allowed_models
    assert "opus" in metadata.allowed_models


def test_plugin_metadata_legacy_handler(plugin_with_mock_service):
    """Test plugin legacy handler key"""
    metadata = plugin_with_mock_service.metadata
    assert metadata.legacy_handler_key == "get_team_members_list"


# ============================================================================
# Test Plugin Schemas
# ============================================================================


def test_plugin_input_schema(plugin_with_mock_service):
    """Test plugin input schema property"""
    assert plugin_with_mock_service.input_schema == TeamListInput


def test_plugin_output_schema(plugin_with_mock_service):
    """Test plugin output schema property"""
    assert plugin_with_mock_service.output_schema == TeamListOutput


# ============================================================================
# Test Plugin Execute - Success Cases
# ============================================================================


@pytest.mark.asyncio
async def test_execute_no_department_filter(plugin_with_mock_service, mock_collaborator_service):
    """Test execute without department filter returns all members"""
    input_data = TeamListInput()
    result = await plugin_with_mock_service.execute(input_data)

    # Verify result success
    assert result.success is True
    assert result.error is None

    # Verify service was called correctly
    mock_collaborator_service.list_members.assert_called_once_with(None)
    mock_collaborator_service.get_team_stats.assert_called_once()

    # Verify result data
    assert result.total_members == 1
    assert len(result.roster) == 1
    assert result.roster[0]["name"] == "John Doe"
    assert result.roster[0]["email"] == "john.doe@balizero.com"
    assert result.roster[0]["role"] == "Senior Developer"
    assert result.roster[0]["department"] == "Technology"


@pytest.mark.asyncio
async def test_execute_with_department_filter(plugin_with_mock_service, mock_collaborator_service):
    """Test execute with department filter"""
    input_data = TeamListInput(department="Technology")
    result = await plugin_with_mock_service.execute(input_data)

    # Verify result success
    assert result.success is True

    # Verify service was called with lowercase department
    mock_collaborator_service.list_members.assert_called_once_with("technology")

    # Verify result data
    assert result.total_members == 1
    assert "Technology" in result.by_department


@pytest.mark.asyncio
async def test_execute_with_uppercase_department(
    plugin_with_mock_service, mock_collaborator_service
):
    """Test execute with uppercase department converts to lowercase"""
    input_data = TeamListInput(department="TECHNOLOGY")
    result = await plugin_with_mock_service.execute(input_data)

    # Verify service was called with lowercase department
    mock_collaborator_service.list_members.assert_called_once_with("technology")
    assert result.success is True


@pytest.mark.asyncio
async def test_execute_with_whitespace_department(
    plugin_with_mock_service, mock_collaborator_service
):
    """Test execute with department having whitespace strips it"""
    input_data = TeamListInput(department="  Technology  ")
    result = await plugin_with_mock_service.execute(input_data)

    # Verify service was called with stripped lowercase department
    mock_collaborator_service.list_members.assert_called_once_with("technology")
    assert result.success is True


# ============================================================================
# Test Plugin Execute - Roster Building
# ============================================================================


@pytest.mark.asyncio
async def test_execute_roster_contains_all_fields(
    plugin_with_mock_service, mock_collaborator_profile
):
    """Test roster contains all expected profile fields"""
    input_data = TeamListInput()
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    roster_member = result.roster[0]

    # Verify all fields are included
    assert roster_member["name"] == mock_collaborator_profile.name
    assert roster_member["email"] == mock_collaborator_profile.email
    assert roster_member["role"] == mock_collaborator_profile.role
    assert roster_member["department"] == mock_collaborator_profile.department
    assert roster_member["expertise_level"] == mock_collaborator_profile.expertise_level
    assert roster_member["language"] == mock_collaborator_profile.language
    assert roster_member["traits"] == mock_collaborator_profile.traits
    assert roster_member["notes"] == mock_collaborator_profile.notes


@pytest.mark.asyncio
async def test_execute_multiple_members(mock_collaborator_service):
    """Test execute with multiple team members"""
    # Create multiple mock profiles
    profile1 = Mock()
    profile1.name = "Alice"
    profile1.email = "alice@balizero.com"
    profile1.role = "Designer"
    profile1.department = "Creative"
    profile1.expertise_level = "senior"
    profile1.language = "English"
    profile1.traits = ["creative"]
    profile1.notes = "UI/UX expert"

    profile2 = Mock()
    profile2.name = "Bob"
    profile2.email = "bob@balizero.com"
    profile2.role = "Developer"
    profile2.department = "Technology"
    profile2.expertise_level = "mid"
    profile2.language = "English"
    profile2.traits = ["analytical"]
    profile2.notes = "Backend specialist"

    mock_collaborator_service.list_members.return_value = [profile1, profile2]
    mock_collaborator_service.get_team_stats.return_value = {
        "total": 2,
        "departments": {"Creative": 1, "Technology": 1},
    }

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is True
    assert result.total_members == 2
    assert len(result.roster) == 2
    assert result.roster[0]["name"] == "Alice"
    assert result.roster[1]["name"] == "Bob"


# ============================================================================
# Test Plugin Execute - Department Grouping
# ============================================================================


@pytest.mark.asyncio
async def test_execute_grouping_by_department(mock_collaborator_service):
    """Test members are correctly grouped by department"""
    # Create profiles with different departments
    tech_profile = Mock()
    tech_profile.name = "Tech User"
    tech_profile.email = "tech@balizero.com"
    tech_profile.role = "Engineer"
    tech_profile.department = "Technology"
    tech_profile.expertise_level = "senior"
    tech_profile.language = "English"
    tech_profile.traits = []
    tech_profile.notes = ""

    creative_profile = Mock()
    creative_profile.name = "Creative User"
    creative_profile.email = "creative@balizero.com"
    creative_profile.role = "Designer"
    creative_profile.department = "Creative"
    creative_profile.expertise_level = "mid"
    creative_profile.language = "English"
    creative_profile.traits = []
    creative_profile.notes = ""

    mock_collaborator_service.list_members.return_value = [tech_profile, creative_profile]

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is True
    assert "Technology" in result.by_department
    assert "Creative" in result.by_department
    assert len(result.by_department["Technology"]) == 1
    assert len(result.by_department["Creative"]) == 1
    assert result.by_department["Technology"][0]["name"] == "Tech User"
    assert result.by_department["Creative"][0]["name"] == "Creative User"


@pytest.mark.asyncio
async def test_execute_multiple_members_same_department(mock_collaborator_service):
    """Test multiple members in the same department are grouped together"""
    # Create two profiles in Technology department
    profile1 = Mock()
    profile1.name = "Engineer 1"
    profile1.email = "eng1@balizero.com"
    profile1.role = "Backend Engineer"
    profile1.department = "Technology"
    profile1.expertise_level = "senior"
    profile1.language = "English"
    profile1.traits = []
    profile1.notes = ""

    profile2 = Mock()
    profile2.name = "Engineer 2"
    profile2.email = "eng2@balizero.com"
    profile2.role = "Frontend Engineer"
    profile2.department = "Technology"
    profile2.expertise_level = "mid"
    profile2.language = "English"
    profile2.traits = []
    profile2.notes = ""

    mock_collaborator_service.list_members.return_value = [profile1, profile2]

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is True
    assert "Technology" in result.by_department
    assert len(result.by_department["Technology"]) == 2
    assert result.by_department["Technology"][0]["name"] == "Engineer 1"
    assert result.by_department["Technology"][1]["name"] == "Engineer 2"


@pytest.mark.asyncio
async def test_execute_empty_roster(mock_collaborator_service):
    """Test execute with no team members"""
    mock_collaborator_service.list_members.return_value = []
    mock_collaborator_service.get_team_stats.return_value = {"total": 0, "departments": {}}

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is True
    assert result.total_members == 0
    assert len(result.roster) == 0
    assert result.by_department == {}


# ============================================================================
# Test Plugin Execute - Team Stats
# ============================================================================


@pytest.mark.asyncio
async def test_execute_includes_team_stats(plugin_with_mock_service, mock_collaborator_service):
    """Test execute includes team statistics"""
    input_data = TeamListInput()
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    assert result.stats is not None
    assert result.stats["total"] == 1
    assert "departments" in result.stats
    assert "languages" in result.stats


@pytest.mark.asyncio
async def test_execute_stats_in_data_field(plugin_with_mock_service):
    """Test execute includes stats in data field as well"""
    input_data = TeamListInput()
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    assert result.data is not None
    assert "stats" in result.data
    assert result.data["stats"] == result.stats


# ============================================================================
# Test Plugin Execute - Output Structure
# ============================================================================


@pytest.mark.asyncio
async def test_execute_output_has_all_fields(plugin_with_mock_service):
    """Test execute output contains all expected fields"""
    input_data = TeamListInput()
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True

    # Check direct fields
    assert result.total_members is not None
    assert result.by_department is not None
    assert result.roster is not None
    assert result.stats is not None

    # Check data dictionary
    assert result.data is not None
    assert "total_members" in result.data
    assert "by_department" in result.data
    assert "roster" in result.data
    assert "stats" in result.data


@pytest.mark.asyncio
async def test_execute_data_matches_direct_fields(plugin_with_mock_service):
    """Test data dictionary matches direct output fields"""
    input_data = TeamListInput()
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    assert result.data["total_members"] == result.total_members
    assert result.data["by_department"] == result.by_department
    assert result.data["roster"] == result.roster
    assert result.data["stats"] == result.stats


# ============================================================================
# Test Plugin Execute - Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_execute_list_members_exception(mock_collaborator_service):
    """Test execute handles exception from list_members"""
    mock_collaborator_service.list_members.side_effect = Exception("Database connection failed")

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is False
    assert result.error is not None
    assert "Team list failed" in result.error
    assert "Database connection failed" in result.error


@pytest.mark.asyncio
async def test_execute_get_team_stats_exception(
    mock_collaborator_service, mock_collaborator_profile
):
    """Test execute handles exception from get_team_stats"""
    mock_collaborator_service.list_members.return_value = [mock_collaborator_profile]
    mock_collaborator_service.get_team_stats.side_effect = Exception("Stats calculation failed")

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is False
    assert "Team list failed" in result.error
    assert "Stats calculation failed" in result.error


@pytest.mark.asyncio
async def test_execute_generic_exception(mock_collaborator_service):
    """Test execute handles generic unexpected exception"""
    mock_collaborator_service.list_members.side_effect = RuntimeError("Unexpected error")

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is False
    assert "Team list failed" in result.error
    assert "Unexpected error" in result.error


@pytest.mark.asyncio
async def test_execute_attribute_error_in_profile(mock_collaborator_service):
    """Test execute handles profiles with missing attributes"""
    bad_profile = Mock()
    bad_profile.name = "Bad Profile"
    # Missing other required attributes
    del bad_profile.email

    mock_collaborator_service.list_members.return_value = [bad_profile]

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput()
    result = await plugin.execute(input_data)

    assert result.success is False
    assert "Team list failed" in result.error


# ============================================================================
# Test Plugin Execute - Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_execute_with_none_department(plugin_with_mock_service, mock_collaborator_service):
    """Test execute with explicitly None department"""
    input_data = TeamListInput(department=None)
    result = await plugin_with_mock_service.execute(input_data)

    assert result.success is True
    mock_collaborator_service.list_members.assert_called_once_with(None)


@pytest.mark.asyncio
async def test_execute_with_empty_string_department(mock_collaborator_service):
    """Test execute with empty string department"""
    mock_collaborator_service.list_members.return_value = []
    mock_collaborator_service.get_team_stats.return_value = {"total": 0}

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput(department="")
    result = await plugin.execute(input_data)

    # Empty string after strip() becomes empty, but not None
    assert result.success is True
    mock_collaborator_service.list_members.assert_called_once_with("")


@pytest.mark.asyncio
async def test_execute_with_special_characters_in_department(mock_collaborator_service):
    """Test execute with special characters in department name"""
    mock_collaborator_service.list_members.return_value = []
    mock_collaborator_service.get_team_stats.return_value = {"total": 0}

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput(department="R&D")
    result = await plugin.execute(input_data)

    assert result.success is True
    mock_collaborator_service.list_members.assert_called_once_with("r&d")


@pytest.mark.asyncio
async def test_execute_with_mixed_case_department(mock_collaborator_service):
    """Test execute normalizes mixed case department names"""
    mock_collaborator_service.list_members.return_value = []
    mock_collaborator_service.get_team_stats.return_value = {"total": 0}

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput(department="TeChnOLoGy")
    result = await plugin.execute(input_data)

    assert result.success is True
    mock_collaborator_service.list_members.assert_called_once_with("technology")


# ============================================================================
# Test Plugin Integration
# ============================================================================


def test_plugin_is_instantiable():
    """Test plugin can be instantiated without errors"""
    plugin = TeamMembersListPlugin()
    assert plugin is not None


def test_plugin_has_required_methods():
    """Test plugin has all required plugin methods"""
    plugin = TeamMembersListPlugin()
    assert hasattr(plugin, "metadata")
    assert hasattr(plugin, "input_schema")
    assert hasattr(plugin, "output_schema")
    assert hasattr(plugin, "execute")


def test_plugin_metadata_is_callable(plugin_with_mock_service):
    """Test metadata property is callable and returns PluginMetadata"""
    metadata = plugin_with_mock_service.metadata
    assert metadata is not None
    assert hasattr(metadata, "name")
    assert hasattr(metadata, "version")
    assert hasattr(metadata, "description")


# ============================================================================
# Test Logging
# ============================================================================


@pytest.mark.asyncio
async def test_execute_logs_department_filter(plugin_with_mock_service, caplog):
    """Test execute logs the department filter being used"""
    import logging

    caplog.set_level(logging.DEBUG)

    input_data = TeamListInput(department="Technology")
    await plugin_with_mock_service.execute(input_data)

    # Check that debug log was created
    assert any("Team list" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_execute_logs_error_on_exception(mock_collaborator_service, caplog):
    """Test execute logs error when exception occurs"""
    import logging

    caplog.set_level(logging.ERROR)

    mock_collaborator_service.list_members.side_effect = Exception("Test error")

    plugin = TeamMembersListPlugin(collaborator_service=mock_collaborator_service)
    input_data = TeamListInput()
    await plugin.execute(input_data)

    # Check that error was logged
    assert any(record.levelname == "ERROR" for record in caplog.records)
    assert any("Team list error" in record.message for record in caplog.records)
