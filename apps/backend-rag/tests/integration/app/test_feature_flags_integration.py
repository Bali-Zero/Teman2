"""
Integration Tests for Feature Flags
Tests feature flag configuration and checking
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestFeatureFlagsIntegration:
    """Comprehensive integration tests for feature flags"""

    def test_should_enable_skill_detection(self):
        """Test skill detection flag"""
        from app.feature_flags import should_enable_skill_detection

        result = should_enable_skill_detection()
        assert isinstance(result, bool)

    def test_should_enable_collective_memory_with_langgraph(self):
        """Test collective memory flag when langgraph is available"""
        from app.feature_flags import should_enable_collective_memory

        with patch("app.feature_flags.COLLECTIVE_MEMORY_ENABLED", True):
            with patch("importlib.util.find_spec", return_value=MagicMock()):
                result = should_enable_collective_memory()
                assert isinstance(result, bool)

    def test_should_enable_collective_memory_without_langgraph(self):
        """Test collective memory flag when langgraph is not available"""
        from app.feature_flags import should_enable_collective_memory

        with patch("app.feature_flags.COLLECTIVE_MEMORY_ENABLED", True):
            with patch("importlib.util.find_spec", return_value=None):
                result = should_enable_collective_memory()
                assert result is False

    def test_should_enable_collective_memory_disabled(self):
        """Test collective memory flag when disabled"""
        from app.feature_flags import should_enable_collective_memory

        with patch("app.feature_flags.COLLECTIVE_MEMORY_ENABLED", False):
            result = should_enable_collective_memory()
            assert result is False

    def test_should_enable_tool_execution(self):
        """Test tool execution flag"""
        from app.feature_flags import should_enable_tool_execution

        result = should_enable_tool_execution()
        assert isinstance(result, bool)

    def test_get_feature_flags(self):
        """Test getting all feature flags"""
        from app.feature_flags import get_feature_flags

        flags = get_feature_flags()

        assert isinstance(flags, dict)
        assert "skill_detection" in flags
        assert "collective_memory" in flags
        assert "advanced_analytics" in flags
        assert "tool_execution" in flags
        assert all(isinstance(v, bool) for v in flags.values())
