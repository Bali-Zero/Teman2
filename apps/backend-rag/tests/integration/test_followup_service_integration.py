"""
Integration tests for FollowupService
Tests follow-up task creation and management
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestFollowupServiceIntegration:
    """Integration tests for FollowupService"""

    def test_followup_service_init(self):
        """Test FollowupService initialization"""
        from services.followup_service import FollowupService

        service = FollowupService()
        assert service is not None

    def test_generate_followups(self):
        """Test generating follow-up questions"""
        with patch("llm.zantara_ai_client.ZantaraAIClient") as mock_zantara:
            mock_zantara_instance = MagicMock()
            mock_zantara_instance.generate_response = AsyncMock(
                return_value="Follow-up question 1\nFollow-up question 2"
            )
            mock_zantara.return_value = mock_zantara_instance

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.generate_followups(
                query="test query",
                response="test response",
                topic="business",
            )

            assert isinstance(result, list)

    def test_get_topic_based_followups(self):
        """Test getting topic-based follow-up questions"""
        from services.followup_service import FollowupService

        service = FollowupService()
        result = service.get_topic_based_followups(
            _query="test query",
            _response="test response",
            topic="business",
            language="en",
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_generate_dynamic_followups_with_ai_success(self):
        """Ensure dynamic follow-ups are generated when AI client is available"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.chat_async = AsyncMock(
                return_value={"text": "1. First?\n2. Second?\n3. Third?"}
            )
            mock_client.return_value = mock_instance

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.get_followups(
                query="Hello, can you help with taxes?",
                response="Sure, here are details.",
                use_ai=True,
                conversation_context="Context",
            )

            assert result[:2] == ["First?", "Second?"]
            assert len(result) <= 3
            mock_instance.chat_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_dynamic_followups_parse_fallback(self):
        """Fallback to topic-based followups when AI output is not parseable"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.chat_async = AsyncMock(return_value={"text": "No numbers here"})
            mock_client.return_value = mock_instance

            from services.followup_service import FollowupService

            service = FollowupService()
            with patch.object(
                service, "get_topic_based_followups", wraps=service.get_topic_based_followups
            ) as fallback:
                result = await service.get_followups(
                    query="Tell me about immigration permits",
                    response="Here is info",
                    use_ai=True,
                )

                fallback.assert_called_once()
                assert len(result) > 0

    @pytest.mark.asyncio
    async def test_followups_without_ai_client(self):
        """Gracefully fall back when AI client cannot be initialized"""
        with patch("services.followup_service.ZantaraAIClient", side_effect=Exception("boom")):
            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.get_followups(
                query="How do I register a company?",
                response="Steps are...",
                use_ai=True,
            )

            assert len(result) > 0
            assert all(isinstance(item, str) for item in result)

    def test_language_and_topic_detection_integration(self):
        """Detect Italian + tax topic and return localized followups"""
        with patch("services.followup_service.ZantaraAIClient", side_effect=Exception("skip ai")):
            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.get_topic_based_followups(
                _query="Ciao, ho un problema con le tasse aziendali",
                _response="",
                topic=service.detect_topic_from_query(
                    "Ciao, ho un problema con le tasse aziendali"
                ),
                language=service.detect_language_from_query(
                    "Ciao, ho un problema con le tasse aziendali"
                ),
            )

            assert any("tasse" in item.lower() or "fiscali" in item.lower() for item in result)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_health_check_flags_ai_availability(self):
        """health_check should reflect AI availability"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance

            from services.followup_service import FollowupService

            service = FollowupService()
            health = await service.health_check()

            assert health["status"] == "healthy"
            assert health["ai_available"] is True
            assert health["features"]["dynamic_generation"] is True
