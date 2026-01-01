"""
Unit tests for PriorityOverrideService
Target: >95% coverage
"""

import sys
from pathlib import Path
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.priority_override import PriorityOverrideService


@pytest.fixture
def priority_override():
    """Create PriorityOverrideService instance"""
    return PriorityOverrideService()


class TestPriorityOverrideService:
    """Tests for PriorityOverrideService"""

    def test_init(self, priority_override):
        """Test initialization"""
        assert priority_override is not None
        assert len(priority_override.identity_patterns) > 0
        assert len(priority_override.team_patterns) > 0

    def test_check_priority_overrides_identity(self, priority_override):
        """Test checking priority override for identity query"""
        result = priority_override.check_priority_overrides("chi sono io")
        assert result == "bali_zero_team"

    def test_check_priority_overrides_team(self, priority_override):
        """Test checking priority override for team query"""
        result = priority_override.check_priority_overrides("chi lavora nel team")
        assert result == "bali_zero_team"

    def test_check_priority_overrides_founder(self, priority_override):
        """Test checking priority override for founder query"""
        result = priority_override.check_priority_overrides("chi è il fondatore")
        assert result == "bali_zero_team"

    def test_check_priority_overrides_backend_services(self, priority_override):
        """Test checking priority override for backend services query"""
        result = priority_override.check_priority_overrides("quali sono gli endpoint disponibili")
        assert result == "zantara_books"

    def test_check_priority_overrides_no_override(self, priority_override):
        """Test checking priority override when no override needed"""
        result = priority_override.check_priority_overrides("what is visa")
        assert result is None

    def test_is_identity_query(self, priority_override):
        """Test detecting identity query"""
        assert priority_override.is_identity_query("chi sono io") is True
        assert priority_override.is_identity_query("who am i") is True
        assert priority_override.is_identity_query("what is visa") is False

    def test_is_team_query(self, priority_override):
        """Test detecting team query"""
        assert priority_override.is_team_query("chi lavora nel team") is True
        assert priority_override.is_team_query("team members") is True
        assert priority_override.is_team_query("what is visa") is False

    def test_is_backend_services_query(self, priority_override):
        """Test detecting backend services query"""
        assert priority_override.is_backend_services_query("quali endpoint sono disponibili") is True
        assert priority_override.is_backend_services_query("api documentation") is True
        assert priority_override.is_backend_services_query("what is visa") is False
