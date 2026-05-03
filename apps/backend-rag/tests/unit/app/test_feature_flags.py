"""
Unit tests for app.feature_flags module
"""

from unittest.mock import MagicMock, patch

from backend.app.feature_flags import (
    ADVANCED_ANALYTICS_ENABLED,
    SKILL_DETECTION_ENABLED,
    TOOL_EXECUTION_ENABLED,
    get_feature_flags,
    should_enable_collective_memory,
    should_enable_skill_detection,
    should_enable_tool_execution,
)


class TestShouldEnableSkillDetection:
    """Tests for should_enable_skill_detection function"""

    def test_returns_skill_detection_enabled_value(self):
        """Test that function returns the SKILL_DETECTION_ENABLED value"""
        result = should_enable_skill_detection()
        assert isinstance(result, bool)
        assert result == SKILL_DETECTION_ENABLED

    @patch("backend.app.feature_flags.SKILL_DETECTION_ENABLED", True)
    def test_returns_true_when_enabled(self):
        """Test that function returns True when skill detection is enabled"""
        result = should_enable_skill_detection()
        assert result is True

    @patch("backend.app.feature_flags.SKILL_DETECTION_ENABLED", False)
    def test_returns_false_when_disabled(self):
        """Test that function returns False when skill detection is disabled"""
        result = should_enable_skill_detection()
        assert result is False


class TestShouldEnableCollectiveMemory:
    """Tests for should_enable_collective_memory function"""

    @patch("backend.app.feature_flags.COLLECTIVE_MEMORY_ENABLED", False)
    def test_returns_false_when_disabled(self):
        """Test that function returns False when collective memory is disabled"""
        result = should_enable_collective_memory()
        assert result is False

    @patch("backend.app.feature_flags.COLLECTIVE_MEMORY_ENABLED", True)
    @patch("importlib.util.find_spec")
    def test_returns_true_when_enabled_and_langgraph_available(self, mock_find_spec):
        """Test that function returns True when enabled and langgraph is available"""
        mock_find_spec.return_value = MagicMock()  # langgraph available
        result = should_enable_collective_memory()
        assert result is True
        mock_find_spec.assert_called_once_with("langgraph")

    @patch("backend.app.feature_flags.COLLECTIVE_MEMORY_ENABLED", True)
    @patch("importlib.util.find_spec")
    def test_returns_false_when_enabled_but_langgraph_unavailable(self, mock_find_spec):
        """Test that function returns False when enabled but langgraph is not available"""
        mock_find_spec.return_value = None  # langgraph not available
        result = should_enable_collective_memory()
        assert result is False

    @patch("backend.app.feature_flags.COLLECTIVE_MEMORY_ENABLED", True)
    @patch("importlib.util.find_spec")
    def test_returns_false_on_import_error(self, mock_find_spec):
        """Test that function returns False on ImportError"""
        mock_find_spec.side_effect = ImportError("Module not found")
        result = should_enable_collective_memory()
        assert result is False


class TestShouldEnableToolExecution:
    """Tests for should_enable_tool_execution function"""

    def test_returns_tool_execution_enabled_value(self):
        """Test that function returns the TOOL_EXECUTION_ENABLED value"""
        result = should_enable_tool_execution()
        assert isinstance(result, bool)
        assert result == TOOL_EXECUTION_ENABLED

    @patch("backend.app.feature_flags.TOOL_EXECUTION_ENABLED", True)
    def test_returns_true_when_enabled(self):
        """Test that function returns True when tool execution is enabled"""
        result = should_enable_tool_execution()
        assert result is True

    @patch("backend.app.feature_flags.TOOL_EXECUTION_ENABLED", False)
    def test_returns_false_when_disabled(self):
        """Test that function returns False when tool execution is disabled"""
        result = should_enable_tool_execution()
        assert result is False


class TestGetFeatureFlags:
    """Tests for get_feature_flags function"""

    def test_returns_dict_with_all_flags(self):
        """Test that function returns a dictionary with all feature flags"""
        result = get_feature_flags()
        assert isinstance(result, dict)
        assert "skill_detection" in result
        assert "collective_memory" in result
        assert "advanced_analytics" in result
        assert "tool_execution" in result

    def test_skill_detection_flag_matches_enabled_value(self):
        """Test that skill_detection flag matches SKILL_DETECTION_ENABLED"""
        result = get_feature_flags()
        assert result["skill_detection"] == SKILL_DETECTION_ENABLED

    def test_advanced_analytics_flag_matches_enabled_value(self):
        """Test that advanced_analytics flag matches ADVANCED_ANALYTICS_ENABLED"""
        result = get_feature_flags()
        assert result["advanced_analytics"] == ADVANCED_ANALYTICS_ENABLED

    def test_tool_execution_flag_matches_enabled_value(self):
        """Test that tool_execution flag matches TOOL_EXECUTION_ENABLED"""
        result = get_feature_flags()
        assert result["tool_execution"] == TOOL_EXECUTION_ENABLED

    @patch("backend.app.feature_flags.should_enable_collective_memory")
    def test_collective_memory_flag_calls_helper_function(self, mock_helper):
        """Test that collective_memory flag calls should_enable_collective_memory"""
        mock_helper.return_value = True
        result = get_feature_flags()
        assert result["collective_memory"] is True
        mock_helper.assert_called_once()

    def test_all_flags_are_boolean(self):
        """Test that all flags in the dictionary are boolean values"""
        result = get_feature_flags()
        for flag_name, flag_value in result.items():
            assert isinstance(flag_value, bool), (
                f"Flag {flag_name} should be boolean, got {type(flag_value)}"
            )
