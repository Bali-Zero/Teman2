"""
Unit tests for PersonalityService
Tests personality service functionality
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestPersonalityService:
    """Unit tests for PersonalityService"""

    @patch("backend.services.personality_service.TEAM_MEMBERS", [])
    def test_personality_service_init(self):
        """Test PersonalityService initialization"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()
        assert service is not None
        assert hasattr(service, "personality_profiles")

    @patch("backend.services.personality_service.TEAM_MEMBERS", [])
    def test_personality_profiles(self):
        """Test personality profiles exist"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()
        assert isinstance(service.personality_profiles, dict)
        assert len(service.personality_profiles) > 0

    @patch("backend.services.personality_service.TEAM_MEMBERS", [])
    def test_jaksel_personality(self):
        """Test Jaksel personality profile"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()
        assert "jaksel" in service.personality_profiles
        profile = service.personality_profiles["jaksel"]
        assert isinstance(profile, dict)
        assert "name" in profile or "style" in profile
