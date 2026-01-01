"""
Unit tests for feature flags
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.feature_flags import (
    ADVANCED_ANALYTICS_ENABLED,
    COLLECTIVE_MEMORY_ENABLED,
    SKILL_DETECTION_ENABLED,
    TOOL_EXECUTION_ENABLED,
    get_feature_flags,
    should_enable_collective_memory,
    should_enable_skill_detection,
    should_enable_tool_execution,
)


class TestFeatureFlags:
    """Tests for feature flags"""

    def test_should_enable_skill_detection(self):
        """Test skill detection flag"""
        result = should_enable_skill_detection()
        assert isinstance(result, bool)

    def test_should_enable_tool_execution(self):
        """Test tool execution flag"""
        result = should_enable_tool_execution()
        assert isinstance(result, bool)

    def test_should_enable_collective_memory_disabled(self):
        """Test collective memory flag when disabled"""
        with patch("app.feature_flags.COLLECTIVE_MEMORY_ENABLED", False):
            result = should_enable_collective_memory()
            assert result is False

    def test_should_enable_collective_memory_enabled_with_langgraph(self):
        """Test collective memory flag when enabled and langgraph available"""
        with patch("app.feature_flags.COLLECTIVE_MEMORY_ENABLED", True), \
             patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = MagicMock()
            result = should_enable_collective_memory()
            assert result is True

    def test_should_enable_collective_memory_enabled_without_langgraph(self):
        """Test collective memory flag when enabled but langgraph not available"""
        with patch("app.feature_flags.COLLECTIVE_MEMORY_ENABLED", True), \
             patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None
            result = should_enable_collective_memory()
            assert result is False

    def test_get_feature_flags(self):
        """Test getting all feature flags"""
        flags = get_feature_flags()
        assert isinstance(flags, dict)
        assert "skill_detection" in flags
        assert "collective_memory" in flags
        assert "advanced_analytics" in flags
        assert "tool_execution" in flags
        assert all(isinstance(v, bool) for v in flags.values())
