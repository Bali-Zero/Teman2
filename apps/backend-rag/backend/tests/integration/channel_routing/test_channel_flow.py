"""
Integration test: Channel message routing flow.

Tests the end-to-end flow from raw webhook → channel adapter → normalized message
for Telegram and WhatsApp channels.
"""


import pytest

from backend.channels.base import ChannelMessage, ChannelResponse

# --- Telegram Channel Flow ---


class TestTelegramChannelFlow:
    """Integration tests for Telegram message flow."""

    @pytest.fixture
    def telegram_adapter(self):
        from backend.channels.telegram.adapter import TelegramChannelAdapter

        return TelegramChannelAdapter(
            {"bot_token": "test_token", "max_message_length": 4096}
        )

    @pytest.mark.asyncio
    async def test_telegram_text_message_flow(self, telegram_adapter):
        """Full flow: Telegram webhook → ChannelMessage."""
        raw_event = {
            "update_id": 99999,
            "message": {
                "message_id": 100,
                "from": {"id": 413539912, "first_name": "Zero", "username": "balizero"},
                "chat": {"id": 413539912, "type": "private"},
                "date": 1711900000,
                "text": "Quanto costa aprire una PT PMA?",
            },
        }

        msg = await telegram_adapter.receive_message(raw_event)

        assert isinstance(msg, ChannelMessage)
        assert msg.channel == "telegram"
        assert msg.user_id == "413539912"
        assert msg.text == "Quanto costa aprire una PT PMA?"
        assert "tg_session_" in msg.session_id

    @pytest.mark.asyncio
    async def test_telegram_photo_message_flow(self, telegram_adapter):
        """Telegram photo messages should extract file_id as media."""
        raw_event = {
            "update_id": 100000,
            "message": {
                "message_id": 101,
                "from": {"id": 12345, "first_name": "Test"},
                "chat": {"id": 12345, "type": "private"},
                "date": 1711900001,
                "text": "",
                "photo": [
                    {"file_id": "small_id", "width": 90, "height": 90},
                    {"file_id": "large_id", "width": 800, "height": 600},
                ],
            },
        }

        msg = await telegram_adapter.receive_message(raw_event)

        assert isinstance(msg, ChannelMessage)
        assert msg.media is not None
        assert any("large_id" in m for m in msg.media)

    @pytest.mark.asyncio
    async def test_telegram_empty_update(self, telegram_adapter):
        """Telegram update without message field should be handled gracefully."""
        raw_event = {"update_id": 100001}

        msg = await telegram_adapter.receive_message(raw_event)

        assert msg.user_id == "unknown"
        assert msg.text == ""


# --- WhatsApp Channel Flow ---


class TestWhatsAppChannelFlow:
    """Integration tests for WhatsApp message flow."""

    @pytest.fixture
    def whatsapp_adapter(self):
        from backend.channels.whatsapp.adapter import WhatsAppChannelAdapter

        return WhatsAppChannelAdapter(
            {
                "access_token": "test_token",
                "phone_number_id": "111222333",
                "max_message_length": 1600,
            }
        )

    @pytest.mark.asyncio
    async def test_whatsapp_text_message_flow(self, whatsapp_adapter):
        """Full flow: WhatsApp webhook → ChannelMessage."""
        raw_event = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "6281234567890",
                                        "id": "wamid.HBg123",
                                        "timestamp": "1711900000",
                                        "type": "text",
                                        "text": {"body": "I need help with my visa"},
                                    }
                                ],
                                "contacts": [
                                    {"profile": {"name": "Jane Smith"}}
                                ],
                            }
                        }
                    ]
                }
            ],
        }

        msg = await whatsapp_adapter.receive_message(raw_event)

        assert isinstance(msg, ChannelMessage)
        assert msg.channel == "whatsapp"
        assert msg.user_id == "whatsapp_6281234567890"
        assert msg.text == "I need help with my visa"
        assert msg.metadata["sender_name"] == "Jane Smith"

    @pytest.mark.asyncio
    async def test_whatsapp_status_webhook_no_crash(self, whatsapp_adapter):
        """Status-only webhooks (no messages) should not crash."""
        raw_event = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [
                                    {
                                        "id": "wamid.xyz",
                                        "status": "read",
                                        "timestamp": "1711900000",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ],
        }

        msg = await whatsapp_adapter.receive_message(raw_event)

        assert msg.text == ""
        assert msg.user_id == "unknown"


# --- Cross-Channel Tests ---


class TestCrossChannel:
    """Tests that verify channel-agnostic behavior."""

    def test_channel_message_format_consistent(self):
        """All channels should produce ChannelMessage with same required fields."""
        telegram_msg = ChannelMessage(
            user_id="telegram_123",
            session_id="tg_session_123",
            text="Hello from Telegram",
            channel="telegram",
        )

        whatsapp_msg = ChannelMessage(
            user_id="whatsapp_628",
            session_id="wa_session_628",
            text="Hello from WhatsApp",
            channel="whatsapp",
        )

        for msg in [telegram_msg, whatsapp_msg]:
            assert hasattr(msg, "user_id")
            assert hasattr(msg, "session_id")
            assert hasattr(msg, "text")
            assert hasattr(msg, "channel")
            assert hasattr(msg, "media")
            assert hasattr(msg, "metadata")

    def test_channel_response_format_consistent(self):
        """ChannelResponse should be usable across all channels."""
        response = ChannelResponse(
            text="PT PMA costs Rp 20,000,000",
            sources=[{"title": "Pricing", "confidence": 0.9}],
        )

        assert response.text
        assert response.sources is not None
        assert len(response.sources) == 1
