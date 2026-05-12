"""Telegram notify is best-effort: never raises, swallows network errors."""
from unittest.mock import patch
from backend.services.canva_renderer_v2._telegram import send_telegram


def test_send_telegram_success(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    with patch("urllib.request.urlopen") as mock_open:
        send_telegram("hello world")
        assert mock_open.called
        url = mock_open.call_args[0][0]
        assert "api.telegram.org" in url


def test_send_telegram_swallows_network_error(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        send_telegram("hello")  # MUST NOT raise


def test_send_telegram_no_token_silent(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with patch("urllib.request.urlopen") as mock_open:
        send_telegram("hello")
        assert not mock_open.called
