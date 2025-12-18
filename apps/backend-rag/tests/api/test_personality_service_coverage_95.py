"""
API Tests for PersonalityService - Coverage 95% Target
Tests PersonalityService methods

Coverage:
- __init__ method
- _build_personality_profiles method
- get_user_personality method
- translate_to_personality method
- get_available_personalities method
- test_personality method
- translate_to_personality_advanced method
- _enhance_with_zantara_model method
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")
os.environ.setdefault("ZANTARA_ORACLE_URL", "https://test.zantara.oracle.cloud/api/generate")
os.environ.setdefault("ORACLE_API_KEY", "test_oracle_api_key")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestPersonalityService:
    """Test PersonalityService methods"""

    def test_init(self):
        """Test PersonalityService initialization"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        assert service.zantara_oracle_url is not None
        assert service.team_members is not None
        assert service.personality_profiles is not None
        assert len(service.personality_profiles) > 0

    def test_build_personality_profiles(self):
        """Test _build_personality_profiles method"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        profiles = service.personality_profiles

        assert "jaksel" in profiles
        assert "zero" in profiles
        assert "professional" in profiles

        # Check jaksel profile
        jaksel = profiles["jaksel"]
        assert jaksel["name"] == "Zantara Jaksel"
        assert jaksel["language"] == "id"
        assert "system_prompt" in jaksel
        assert "team_members" in jaksel

        # Check zero profile
        zero = profiles["zero"]
        assert zero["name"] == "Zantara ZERO"
        assert zero["language"] == "it"

        # Check professional profile
        professional = profiles["professional"]
        assert professional["name"] == "Zantara Professional"
        assert professional["language"] == "en"

    def test_get_user_personality_jaksel(self):
        """Test get_user_personality for Jaksel user"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        # Test with jaksel user (amanda)
        result = service.get_user_personality("amanda@example.com")

        assert "personality_type" in result
        assert "personality" in result
        assert "user" in result
        # Note: actual result depends on team_members data

    def test_get_user_personality_zero(self):
        """Test get_user_personality for Zero user"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        # Test with zero user
        result = service.get_user_personality("zero@example.com")

        assert "personality_type" in result
        assert "personality" in result
        assert "user" in result

    def test_get_user_personality_unknown(self):
        """Test get_user_personality for unknown user"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        result = service.get_user_personality("unknown@example.com")

        assert result["personality_type"] == "professional"
        assert result["personality"]["name"] == "Zantara Professional"
        assert result["user"]["email"] == "unknown@example.com"
        assert result["user"]["name"] == "Guest"

    @pytest.mark.asyncio
    async def test_translate_to_personality_success(self):
        """Test translate_to_personality with successful translation"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Translated response"})

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value.post = AsyncMock(return_value=mock_response)

            result = await service.translate_to_personality(
                "Original Gemini response", "test@example.com", "Original query"
            )

            assert "success" in result
            assert "response" in result
            assert "personality_used" in result

    @pytest.mark.asyncio
    async def test_translate_to_personality_api_failure(self):
        """Test translate_to_personality when API fails"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        mock_response = MagicMock()
        mock_response.status = 500

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value.post = AsyncMock(return_value=mock_response)

            result = await service.translate_to_personality(
                "Original Gemini response", "test@example.com", "Original query"
            )

            assert "success" in result
            # Should fallback to original response
            assert result["response"] == "Original Gemini response"

    @pytest.mark.asyncio
    async def test_translate_to_personality_exception(self):
        """Test translate_to_personality with exception"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        with patch("aiohttp.ClientSession", side_effect=Exception("Connection error")):
            result = await service.translate_to_personality(
                "Original Gemini response", "test@example.com", "Original query"
            )

            assert result["success"] is False
            assert "error" in result
            assert result["response"] == "Original Gemini response"

    def test_get_available_personalities(self):
        """Test get_available_personalities method"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        personalities = service.get_available_personalities()

        assert isinstance(personalities, list)
        assert len(personalities) > 0

        # Check structure
        for personality in personalities:
            assert "id" in personality
            assert "name" in personality
            assert "language" in personality
            assert "style" in personality
            assert "team_count" in personality
            assert "traits" in personality

    @pytest.mark.asyncio
    async def test_test_personality_success(self):
        """Test test_personality with successful test"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Test response"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.post = MagicMock(return_value=mock_post_context)
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session_instance):
            result = await service.test_personality("jaksel", "Test message")

            assert result["success"] is True
            assert "personality" in result
            assert "response" in result

    @pytest.mark.asyncio
    async def test_test_personality_invalid_type(self):
        """Test test_personality with invalid personality type"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        result = await service.test_personality("invalid", "Test message")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_test_personality_api_failure(self):
        """Test test_personality when API fails"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        mock_response = MagicMock()
        mock_response.status = 500

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value.post = AsyncMock(return_value=mock_response)

            result = await service.test_personality("jaksel", "Test message")

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_translate_to_personality_advanced_with_gemini(self):
        """Test translate_to_personality_advanced with Gemini model getter"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        mock_gemini_model = MagicMock()
        mock_gemini_response = MagicMock()
        mock_gemini_response.text = "Gemini translated response"
        mock_gemini_model.generate_content_async = AsyncMock(return_value=mock_gemini_response)

        def mock_model_getter(key):
            return mock_gemini_model

        result = await service.translate_to_personality_advanced(
            "Original Gemini response",
            "test@example.com",
            "Original query",
            gemini_model_getter=mock_model_getter,
        )

        assert result["success"] is True
        assert "response" in result
        assert "personality_used" in result
        assert "model_used" in result

    @pytest.mark.asyncio
    async def test_translate_to_personality_advanced_without_gemini(self):
        """Test translate_to_personality_advanced without Gemini model getter"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Translated response"})

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value.post = AsyncMock(return_value=mock_response)

            result = await service.translate_to_personality_advanced(
                "Original Gemini response",
                "test@example.com",
                "Original query",
                gemini_model_getter=None,
            )

            assert "success" in result
            assert "response" in result

    @pytest.mark.asyncio
    async def test_translate_to_personality_advanced_gemini_error(self):
        """Test translate_to_personality_advanced when Gemini fails"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        def mock_model_getter(key):
            raise Exception("Gemini error")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Fallback response"})

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value.post = AsyncMock(return_value=mock_response)

            result = await service.translate_to_personality_advanced(
                "Original Gemini response",
                "test@example.com",
                "Original query",
                gemini_model_getter=mock_model_getter,
            )

            # Should fallback to original method
            assert "success" in result

    @pytest.mark.asyncio
    async def test_enhance_with_zantara_model_success(self):
        """Test _enhance_with_zantara_model with successful enhancement"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"response": "Enhanced text"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.post = MagicMock(return_value=mock_post_context)
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session_instance):
            personality = service.personality_profiles["jaksel"]
            result = await service._enhance_with_zantara_model("Original text", personality)

            assert result == "Enhanced text"

    @pytest.mark.asyncio
    async def test_enhance_with_zantara_model_failure(self):
        """Test _enhance_with_zantara_model when API fails"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        mock_response = MagicMock()
        mock_response.status = 500

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value.post = AsyncMock(return_value=mock_response)

            personality = service.personality_profiles["jaksel"]
            result = await service._enhance_with_zantara_model("Original text", personality)

            # Should return original text on failure
            assert result == "Original text"

    @pytest.mark.asyncio
    async def test_enhance_with_zantara_model_exception(self):
        """Test _enhance_with_zantara_model with exception"""
        from backend.services.personality_service import PersonalityService

        service = PersonalityService()

        with patch("aiohttp.ClientSession", side_effect=Exception("Connection error")):
            personality = service.personality_profiles["jaksel"]
            result = await service._enhance_with_zantara_model("Original text", personality)

            # Should return original text on exception
            assert result == "Original text"
