"""
Unit tests for PersonalityService
Tests personality service functionality
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


class TestPersonalityService:
    """Unit tests for PersonalityService"""

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    def test_personality_service_init(self):
        """Test PersonalityService initialization"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        assert service is not None
        assert hasattr(service, "personality_profiles")

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    def test_personality_profiles(self):
        """Test personality profiles exist"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        assert isinstance(service.personality_profiles, dict)
        assert len(service.personality_profiles) > 0

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    def test_jaksel_personality(self):
        """Test Jaksel personality profile"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        assert "jaksel" in service.personality_profiles
        profile = service.personality_profiles["jaksel"]
        assert isinstance(profile, dict)
        assert "name" in profile or "style" in profile

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    def test_get_user_personality_unknown_user(self):
        """Test get_user_personality with unknown user"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        result = service.get_user_personality("unknown@example.com")

        assert result["personality_type"] == "professional"
        assert result["user"]["email"] == "unknown@example.com"
        assert result["user"]["name"] == "Guest"

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS")
    def test_get_user_personality_jaksel_user(self, mock_team_members):
        """Test get_user_personality with Jaksel user"""
        mock_team_members.return_value = [
            {"id": "amanda", "email": "amanda@example.com", "name": "Amanda"}
        ]
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        service.team_members = [{"id": "amanda", "email": "amanda@example.com", "name": "Amanda"}]

        result = service.get_user_personality("amanda@example.com")

        assert result["personality_type"] == "jaksel"
        assert result["user"]["id"] == "amanda"

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS")
    def test_get_user_personality_zero_user(self, mock_team_members):
        """Test get_user_personality with ZERO user"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        service.team_members = [{"id": "zero", "email": "zero@example.com", "name": "Zero"}]

        result = service.get_user_personality("zero@example.com")

        assert result["personality_type"] == "zero"
        assert result["user"]["id"] == "zero"

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS")
    def test_get_user_personality_professional_user(self, mock_team_members):
        """Test get_user_personality with professional user"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        service.team_members = [{"id": "zainal", "email": "zainal@example.com", "name": "Zainal"}]

        result = service.get_user_personality("zainal@example.com")

        assert result["personality_type"] == "professional"
        assert result["user"]["id"] == "zainal"

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS")
    def test_get_user_personality_case_insensitive(self, mock_team_members):
        """Test get_user_personality is case insensitive"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        service.team_members = [{"id": "amanda", "email": "amanda@example.com", "name": "Amanda"}]

        result = service.get_user_personality("AMANDA@EXAMPLE.COM")

        assert result["personality_type"] == "jaksel"
        assert result["user"]["email"].lower() == "amanda@example.com"

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    def test_get_available_personalities(self):
        """Test get_available_personalities"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        personalities = service.get_available_personalities()

        assert isinstance(personalities, list)
        assert len(personalities) > 0
        assert all("id" in p for p in personalities)
        assert all("name" in p for p in personalities)
        assert all("language" in p for p in personalities)

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_translate_to_personality_success(self, mock_session_class):
        """Test translate_to_personality successful translation"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock aiohttp response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Personalized response"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock session.post()
        mock_post = MagicMock(return_value=mock_response)
        mock_session_instance = MagicMock()
        mock_session_instance.post = mock_post
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.translate_to_personality(
            "Gemini response", "unknown@example.com", "Original query"
        )

        assert result["success"] is True
        assert "response" in result
        assert "personality_used" in result

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_translate_to_personality_api_failure(self, mock_session_class):
        """Test translate_to_personality when API fails"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock aiohttp response with error
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock session.post()
        mock_post = MagicMock(return_value=mock_response)
        mock_session_instance = MagicMock()
        mock_session_instance.post = mock_post
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.translate_to_personality(
            "Gemini response", "unknown@example.com", "Original query"
        )

        assert result["success"] is True
        assert result["response"] == "Gemini response"  # Fallback to original

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_translate_to_personality_exception(self, mock_session_class):
        """Test translate_to_personality with exception"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock exception
        mock_session_class.side_effect = Exception("Network error")

        result = await service.translate_to_personality(
            "Gemini response", "unknown@example.com", "Original query"
        )

        assert result["success"] is False
        assert "error" in result
        assert result["response"] == "Gemini response"  # Fallback

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_test_personality_success(self, mock_session_class):
        """Test test_personality successful"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock aiohttp response (nested async with pattern)
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Test response"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock session.post() for nested async with
        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=None)
        mock_post = MagicMock(return_value=mock_post_cm)

        # Mock session instance
        mock_session_instance = MagicMock()
        mock_session_instance.post = mock_post
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)

        # Mock ClientSession class
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.test_personality("jaksel", "Test message")

        assert result["success"] is True
        assert "response" in result

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    async def test_test_personality_invalid_type(self):
        """Test test_personality with invalid type"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        result = await service.test_personality("invalid", "Test message")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_test_personality_api_failure(self, mock_session_class):
        """Test test_personality with API failure"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock aiohttp response with error (nested async with pattern)
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock session.post() for nested async with
        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=None)
        mock_post = MagicMock(return_value=mock_post_cm)

        # Mock session instance
        mock_session_instance = MagicMock()
        mock_session_instance.post = mock_post
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)

        # Mock ClientSession class
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.test_personality("jaksel", "Test message")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_translate_to_personality_advanced_no_getter(self, mock_session_class):
        """Test translate_to_personality_advanced without model getter"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock aiohttp response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Personalized response"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock session.post()
        mock_post = MagicMock(return_value=mock_response)
        mock_session_instance = MagicMock()
        mock_session_instance.post = mock_post
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.translate_to_personality_advanced(
            "Gemini response", "unknown@example.com", "Original query"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_translate_to_personality_advanced_with_getter(self, mock_session):
        """Test translate_to_personality_advanced with model getter"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock Gemini model
        mock_gemini_model = AsyncMock()
        mock_gemini_response = MagicMock()
        mock_gemini_response.text = "Gemini translated response"
        mock_gemini_model.generate_content_async = AsyncMock(return_value=mock_gemini_response)

        def mock_getter(key):
            return mock_gemini_model

        result = await service.translate_to_personality_advanced(
            "Gemini response",
            "unknown@example.com",
            "Original query",
            gemini_model_getter=mock_getter,
        )

        assert result["success"] is True
        assert "gemini-pro" in result["model_used"]

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_translate_to_personality_advanced_gemini_error(self, mock_session_class):
        """Test translate_to_personality_advanced when Gemini fails"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock Gemini model that raises exception
        def mock_getter(key):
            raise Exception("Gemini error")

        # Mock aiohttp response for fallback
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Fallback response"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock session.post()
        mock_post = MagicMock(return_value=mock_response)
        mock_session_instance = MagicMock()
        mock_session_instance.post = mock_post
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.translate_to_personality_advanced(
            "Gemini response",
            "unknown@example.com",
            "Original query",
            gemini_model_getter=mock_getter,
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_enhance_with_zantara_model_success(self, mock_session_class):
        """Test _enhance_with_zantara_model successful"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock aiohttp response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Enhanced text"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock session.post()
        mock_post = MagicMock(return_value=mock_response)
        mock_session_instance = MagicMock()
        mock_session_instance.post = mock_post
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

        personality = service.personality_profiles["jaksel"]
        result = await service._enhance_with_zantara_model("Original text", personality)

        assert result == "Enhanced text"

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_enhance_with_zantara_model_failure(self, mock_session_class):
        """Test _enhance_with_zantara_model with failure"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock aiohttp response with error
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock session.post()
        mock_post = MagicMock(return_value=mock_response)
        mock_session_instance = MagicMock()
        mock_session_instance.post = mock_post
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

        personality = service.personality_profiles["jaksel"]
        result = await service._enhance_with_zantara_model("Original text", personality)

        assert result == "Original text"  # Fallback to original

    @pytest.mark.asyncio
    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    @patch("aiohttp.ClientSession")
    async def test_enhance_with_zantara_model_exception(self, mock_session_class):
        """Test _enhance_with_zantara_model with exception"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()

        # Mock exception
        mock_session_class.side_effect = Exception("Network error")

        personality = service.personality_profiles["jaksel"]
        result = await service._enhance_with_zantara_model("Original text", personality)

        assert result == "Original text"  # Fallback to original

    @patch("backend.services.misc.personality_service.TEAM_MEMBERS", [])
    def test_build_personality_profiles_structure(self):
        """Test _build_personality_profiles structure"""
        from backend.services.misc.personality_service import PersonalityService

        service = PersonalityService()
        profiles = service.personality_profiles

        assert "jaksel" in profiles
        assert "zero" in profiles
        assert "professional" in profiles

        # Check profile structure
        for profile_id, profile in profiles.items():
            assert "name" in profile
            assert "language" in profile
            assert "style" in profile
            assert "system_prompt" in profile
            assert "team_members" in profile
            assert "traits" in profile
