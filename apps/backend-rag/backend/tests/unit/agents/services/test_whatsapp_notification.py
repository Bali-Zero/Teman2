"""
Unit tests for WhatsAppNotificationService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from agents.services.whatsapp_notification import WhatsAppNotificationService


@pytest.fixture
def whatsapp_service():
    """Create WhatsAppNotificationService instance"""
    return WhatsAppNotificationService(
        twilio_sid="test_sid",
        twilio_token="test_token",
        whatsapp_number="+1234567890"
    )


class TestWhatsAppNotificationService:
    """Tests for WhatsAppNotificationService"""

    def test_init(self):
        """Test initialization"""
        service = WhatsAppNotificationService(
            twilio_sid="test_sid",
            twilio_token="test_token",
            whatsapp_number="+1234567890"
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
        
        with patch("agents.services.whatsapp_notification.Client", return_value=mock_client), \
             patch("asyncio.get_event_loop") as mock_loop, \
             patch("asyncio.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_message
            
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
        
        with patch("agents.services.whatsapp_notification.Client", return_value=mock_client), \
             patch("asyncio.get_event_loop") as mock_loop, \
             patch("asyncio.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_message
            
            # Phone without +
            result = await whatsapp_service.send_message("1234567890", "Test message")
            assert result == "test_sid_123"
            # Verify phone was formatted with +
            mock_client.messages.create.assert_called_once()
            call_args = mock_client.messages.create.call_args
            assert "+1234567890" in str(call_args)

    @pytest.mark.asyncio
    async def test_send_message_retry(self, whatsapp_service):
        """Test sending message with retry"""
        mock_message = MagicMock()
        mock_message.sid = "test_sid_123"
        
        mock_client = MagicMock()
        # First call fails, second succeeds
        mock_client.messages.create = MagicMock(side_effect=[Exception("Error"), mock_message])
        
        with patch("agents.services.whatsapp_notification.Client", return_value=mock_client), \
             patch("asyncio.get_event_loop") as mock_loop, \
             patch("asyncio.run_in_executor") as mock_executor, \
             patch("asyncio.sleep") as mock_sleep:
            # Mock executor to fail first, then succeed
            call_count = 0
            async def mock_executor_func(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Error")
                return mock_message
            
            mock_executor.side_effect = mock_executor_func
            
            result = await whatsapp_service.send_message("+1234567890", "Test message", max_retries=3)
            assert result == "test_sid_123"

    @pytest.mark.asyncio
    async def test_send_message_timeout(self, whatsapp_service):
        """Test sending message with timeout"""
        import asyncio
        
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock()
        
        with patch("agents.services.whatsapp_notification.Client", return_value=mock_client), \
             patch("asyncio.get_event_loop") as mock_loop, \
             patch("asyncio.run_in_executor") as mock_executor, \
             patch("asyncio.wait_for") as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError()
            
            result = await whatsapp_service.send_message("+1234567890", "Test message", timeout=0.1)
            assert result is None

    @pytest.mark.asyncio
    async def test_send_message_error(self, whatsapp_service):
        """Test sending message with error"""
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(side_effect=Exception("Error"))
        
        with patch("agents.services.whatsapp_notification.Client", return_value=mock_client), \
             patch("asyncio.get_event_loop") as mock_loop, \
             patch("asyncio.run_in_executor") as mock_executor, \
             patch("asyncio.sleep") as mock_sleep:
            mock_executor.side_effect = Exception("Error")
            
            result = await whatsapp_service.send_message("+1234567890", "Test message", max_retries=1)
            assert result is None

