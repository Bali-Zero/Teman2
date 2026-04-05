"""
Unit tests for WhatsAppChannelAdapter.

Tests message parsing, response formatting, and edge cases
for WhatsApp Business API webhooks.
"""


import pytest

from backend.channels.base import ChannelMessage
from backend.channels.whatsapp.adapter import WhatsAppChannelAdapter


@pytest.fixture
def whatsapp_config():
    """Create WhatsApp configuration for testing."""
    return {
        "access_token": "test_access_token_123",
        "phone_number_id": "111222333444",
        "business_account_id": "biz_123",
        "max_message_length": 1600,
    }


@pytest.fixture
def whatsapp_adapter(whatsapp_config):
    """Create WhatsAppChannelAdapter instance."""
    return WhatsAppChannelAdapter(whatsapp_config)


def test_whatsapp_adapter_init(whatsapp_config):
    """Test WhatsAppChannelAdapter initialization."""
    adapter = WhatsAppChannelAdapter(whatsapp_config)

    assert adapter.channel_name == "whatsapp"
    assert adapter.max_message_length == 1600
    assert adapter.whatsapp_config.access_token == "test_access_token_123"
    assert adapter.whatsapp_config.phone_number_id == "111222333444"


@pytest.mark.asyncio
async def test_receive_message_text(whatsapp_adapter):
    """Test parsing WhatsApp text message webhook."""
    webhook = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "6281234567890",
                                    "id": "wamid.abc123",
                                    "timestamp": "1711900000",
                                    "type": "text",
                                    "text": {"body": "How much does a KITAS cost?"},
                                }
                            ],
                            "contacts": [
                                {"profile": {"name": "John Doe"}}
                            ],
                        }
                    }
                ]
            }
        ],
    }

    msg = await whatsapp_adapter.receive_message(webhook)

    assert isinstance(msg, ChannelMessage)
    assert msg.user_id == "whatsapp_6281234567890"
    assert msg.session_id == "wa_session_6281234567890"
    assert msg.text == "How much does a KITAS cost?"
    assert msg.channel == "whatsapp"
    assert msg.metadata["sender_name"] == "John Doe"
    assert msg.metadata["message_type"] == "text"


@pytest.mark.asyncio
async def test_receive_message_no_messages(whatsapp_adapter):
    """Test handling webhook with no messages (e.g., status update)."""
    webhook = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {"id": "wamid.abc", "status": "delivered"}
                            ]
                        }
                    }
                ]
            }
        ],
    }

    msg = await whatsapp_adapter.receive_message(webhook)

    assert msg.user_id == "unknown"
    assert msg.text == ""
    assert msg.channel == "whatsapp"


@pytest.mark.asyncio
async def test_receive_message_empty_entry(whatsapp_adapter):
    """Test handling webhook with empty entry array."""
    webhook = {"object": "whatsapp_business_account", "entry": [{}]}

    msg = await whatsapp_adapter.receive_message(webhook)

    assert msg.user_id == "unknown"
    assert msg.text == ""


@pytest.mark.asyncio
async def test_receive_message_no_contact_name(whatsapp_adapter):
    """Test handling message without contact profile name."""
    webhook = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "628999",
                                    "id": "wamid.xyz",
                                    "timestamp": "1711900000",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                }
                            ],
                            "contacts": [],
                        }
                    }
                ]
            }
        ],
    }

    msg = await whatsapp_adapter.receive_message(webhook)

    assert msg.text == "Hello"
    assert msg.metadata["sender_name"] is None
