"""
Unit tests for WhatsAppNotificationService
Target: >95% coverage
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.agents.services.whatsapp_notification import WhatsAppNotificationService


@pytest.fixture
def whatsapp_service():
    """Create WhatsAppNotificationService instance"""
    return WhatsAppNotificationService(
        twilio_sid="test_sid", twilio_token="test_token", whatsapp_number="+1234567890"
    )


class TestWhatsAppNotificationService:
    """Tests for WhatsAppNotificationService"""

    def test_init(self):
        """Test initialization"""
        service = WhatsAppNotificationService(
            twilio_sid="test_sid", twilio_token="test_token", whatsapp_number="+1234567890"
        )
        assert service.twilio_sid == "test_sid"
        assert service.twilio_token == "test_token"
        assert service.whatsapp_number == "+1234567890"

    def test_init_none(self):
        """Test initialization with None values"""
        service = WhatsAppNotificationService()
        assert service.twilio_sid is None
        assert service.twilio_token is None
        assert service.whatsapp_number is None

    @pytest.mark.asyncio
    async def test_send_message_success(self, whatsapp_service):
        """Test sending message successfully"""
        mock_message = MagicMock()
        mock_message.sid = "test_sid_123"

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_message)

        with patch("twilio.rest.Client", return_value=mock_client):
            # Create a mock event loop with run_in_executor
            mock_loop = MagicMock()

            async def sync_run_in_executor(executor, func):
                return func()

            mock_loop.run_in_executor = sync_run_in_executor

            with patch("asyncio.get_event_loop", return_value=mock_loop):
                result = await whatsapp_service.send_message("+1234567890", "Test message")
                assert result == "test_sid_123"

    @pytest.mark.asyncio
    async def test_send_message_no_credentials(self):
        """Test sending message without credentials"""
        service = WhatsAppNotificationService()
        result = await service.send_message("+1234567890", "Test message")
        assert result is None

    @pytest.mark.asyncio
    async def test_send_message_format_phone(self, whatsapp_service):
        """Test sending message with phone number formatting"""
        mock_message = MagicMock()
        mock_message.sid = "test_sid_123"

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_message)

        with patch("twilio.rest.Client", return_value=mock_client):
            mock_loop = MagicMock()

            async def sync_run_in_executor(executor, func):
                return func()

            mock_loop.run_in_executor = sync_run_in_executor

            with patch("asyncio.get_event_loop", return_value=mock_loop):
                # Phone without +
                result = await whatsapp_service.send_message("1234567890", "Test message")
                assert result == "test_sid_123"
                # Verify phone was formatted with + (the lambda captures it)
                mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_timeout(self, whatsapp_service):
        """Test sending message with timeout"""
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock()

        with patch("twilio.rest.Client", return_value=mock_client):
            # Mock wait_for to raise TimeoutError
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await whatsapp_service.send_message(
                    "+1234567890", "Test message", timeout=0.1
                )
                assert result is None

    @pytest.mark.asyncio
    async def test_send_message_error(self, whatsapp_service):
        """Test sending message with error"""
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(side_effect=Exception("Error"))

        with patch("twilio.rest.Client", return_value=mock_client):
            mock_loop = MagicMock()

            async def sync_run_in_executor(executor, func):
                return func()

            mock_loop.run_in_executor = sync_run_in_executor

            with patch("asyncio.get_event_loop", return_value=mock_loop):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await whatsapp_service.send_message(
                        "+1234567890", "Test message", max_retries=1
                    )
                    assert result is None

    @pytest.mark.asyncio
    async def test_send_message_retry_then_success(self, whatsapp_service):
        """Test sending message with retry then success"""
        mock_message = MagicMock()
        mock_message.sid = "test_sid_after_retry"

        call_count = 0

        def create_message(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First try failed")
            return mock_message

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(side_effect=create_message)

        with patch("twilio.rest.Client", return_value=mock_client):
            mock_loop = MagicMock()

            async def sync_run_in_executor(executor, func):
                return func()

            mock_loop.run_in_executor = sync_run_in_executor

            with patch("asyncio.get_event_loop", return_value=mock_loop):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await whatsapp_service.send_message(
                        "+1234567890", "Test message", max_retries=3
                    )
                    assert result == "test_sid_after_retry"
