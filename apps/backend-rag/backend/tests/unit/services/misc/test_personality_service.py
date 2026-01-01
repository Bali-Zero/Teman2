"""
Unit tests for PersonalityService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.personality_service import PersonalityService


@pytest.fixture
def personality_service():
    """Create PersonalityService instance"""
    with patch("services.misc.personality_service.TEAM_MEMBERS", []):
        return PersonalityService()


class TestPersonalityService:
    """Tests for PersonalityService"""

    def test_init(self):
        """Test initialization"""
        with patch("services.misc.personality_service.TEAM_MEMBERS", []):
            service = PersonalityService()
            assert service.personality_profiles is not None

    def test_get_user_personality(self, personality_service):
        """Test getting user personality"""
        with patch("services.misc.personality_service.TEAM_MEMBERS", [
            {"id": "test1", "email": "test@example.com", "name": "Test", "traits": []}
        ]):
            service = PersonalityService()
            personality = service.get_user_personality("test@example.com")
            assert personality is not None
            assert "personality" in personality

    def test_get_user_personality_default(self, personality_service):
        """Test getting default personality"""
        personality = personality_service.get_user_personality("unknown@example.com")
        assert personality is not None
        assert "personality" in personality

    def test_get_available_personalities(self, personality_service):
        """Test getting available personalities"""
        personalities = personality_service.get_available_personalities()
        assert isinstance(personalities, list)
        assert len(personalities) > 0
