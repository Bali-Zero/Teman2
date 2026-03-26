"""Tests for Telegram alerter."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from cell.effectors.telegram import TelegramAlerter

@pytest.mark.asyncio
async def test_telegram_send_alert():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client.post = AsyncMock(return_value=mock_response)
    alerter = TelegramAlerter(client=mock_client, bot_token="test", chat_id="123")
    result = await alerter.send("Test alert")
    assert result is True
    mock_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_telegram_send_failure():
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("Network error"))
    alerter = TelegramAlerter(client=mock_client, bot_token="test", chat_id="123")
    result = await alerter.send("Test alert")
    assert result is False
