"""
Unit tests for NurturingMessageService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from agents.services.nurturing_message import NurturingMessageService


@pytest.fixture
def nurturing_message_service():
    """Create NurturingMessageService instance"""
    with patch("agents.services.nurturing_message.ZANTARA_AVAILABLE", True):
        return NurturingMessageService()


@pytest.fixture
def mock_ai_client():
    """Mock AI client"""
    client = MagicMock()
    client.generate_text = AsyncMock(return_value="Test message")
    return client


class TestNurturingMessageService:
    """Tests for NurturingMessageService"""

    def test_init(self):
        """Test initialization"""
        with patch("agents.services.nurturing_message.ZANTARA_AVAILABLE", True):
            service = NurturingMessageService()
            assert service is not None

    def test_init_with_ai_client(self, mock_ai_client):
        """Test initialization with AI client"""
        service = NurturingMessageService(ai_client=mock_ai_client)
        assert service.ai_client == mock_ai_client

    def test_init_no_zantara(self):
        """Test initialization without Zantara"""
        with patch("agents.services.nurturing_message.ZANTARA_AVAILABLE", False):
            service = NurturingMessageService()
            assert service.ai_client is None

    @pytest.mark.asyncio
    async def test_generate_message(self, mock_ai_client):
        """Test generating message"""
        service = NurturingMessageService(ai_client=mock_ai_client)

        client_data = {
            "name": "Test Client",
            "segment": "VIP",
            "ltv_score": 85,
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": 5,
            "total_interactions": 10,
            "practice_count": 2,
            "sentiment_score": 80,
        }

        with (
            patch("agents.services.nurturing_message.detect_language", return_value="it"),
            patch(
                "agents.services.nurturing_message.get_language_instruction", return_value="Italian"
            ),
        ):
            message = await service.generate_message(client_data)
            assert message == "Test message"
            mock_ai_client.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_message_no_ai_client(self):
        """Test generating message without AI client"""
        with patch("agents.services.nurturing_message.ZANTARA_AVAILABLE", False):
            service = NurturingMessageService()

            client_data = {"name": "Test Client", "segment": "VIP"}

            message = await service.generate_message(client_data)
            assert isinstance(message, str)
            assert len(message) > 0

    @pytest.mark.asyncio
    async def test_generate_message_timeout(self, mock_ai_client):
        """Test generating message with timeout"""
        import asyncio

        service = NurturingMessageService(ai_client=mock_ai_client)

        mock_ai_client.generate_text = AsyncMock(side_effect=asyncio.TimeoutError())

        client_data = {"name": "Test Client", "segment": "VIP"}

        with (
            patch("agents.services.nurturing_message.detect_language", return_value="it"),
            patch(
                "agents.services.nurturing_message.get_language_instruction", return_value="Italian"
            ),
        ):
            message = await service.generate_message(client_data, timeout=0.1)
            assert isinstance(message, str)
            assert len(message) > 0

    @pytest.mark.asyncio
    async def test_generate_message_error(self, mock_ai_client):
        """Test generating message with error"""
        service = NurturingMessageService(ai_client=mock_ai_client)

        mock_ai_client.generate_text = AsyncMock(side_effect=Exception("AI error"))

        client_data = {"name": "Test Client", "segment": "VIP"}

        with (
            patch("agents.services.nurturing_message.detect_language", return_value="it"),
            patch(
                "agents.services.nurturing_message.get_language_instruction", return_value="Italian"
            ),
        ):
            message = await service.generate_message(client_data)
            assert isinstance(message, str)
            assert len(message) > 0

    def test_build_prompt(self, mock_ai_client):
        """Test building prompt"""
        service = NurturingMessageService(ai_client=mock_ai_client)

        client_data = {
            "name": "Test Client",
            "segment": "VIP",
            "ltv_score": 85,
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": 5,
            "total_interactions": 10,
            "practice_count": 2,
            "sentiment_score": 80,
            "notes": "Test notes",
        }

        with (
            patch("agents.services.nurturing_message.detect_language", return_value="it"),
            patch(
                "agents.services.nurturing_message.get_language_instruction", return_value="Italian"
            ),
        ):
            prompt = service._build_prompt(client_data)
            assert isinstance(prompt, str)
            assert "Test Client" in prompt
            assert "VIP" in prompt

    def test_generate_fallback_message(self, mock_ai_client):
        """Test generating fallback message"""
        service = NurturingMessageService(ai_client=mock_ai_client)

        client_data = {"name": "Test Client", "segment": "VIP"}

        message = service._generate_fallback_message(client_data)
        assert isinstance(message, str)
        assert len(message) > 0

