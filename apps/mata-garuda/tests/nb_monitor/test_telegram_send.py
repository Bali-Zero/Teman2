"""Tests for nb_monitor.telegram_send."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mata_garuda.scripts.nb_monitor.telegram_send import send_telegram


def _ctx_mgr(resp):
    cm = MagicMock()
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm


def test_send_telegram_returns_true_on_success():
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = b'{"ok": true}'
    with patch("urllib.request.urlopen", return_value=_ctx_mgr(fake_resp)):
        ok = send_telegram(bot_token="t", chat_id="123", text="hi")
    assert ok is True


def test_send_telegram_returns_false_on_non_2xx():
    fake_resp = MagicMock()
    fake_resp.status = 401
    fake_resp.read.return_value = b'{"ok": false}'
    with patch("urllib.request.urlopen", return_value=_ctx_mgr(fake_resp)):
        ok = send_telegram(bot_token="t", chat_id="123", text="hi")
    assert ok is False


def test_send_telegram_returns_false_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        ok = send_telegram(bot_token="t", chat_id="123", text="hi")
    assert ok is False


def test_send_telegram_skips_when_bot_token_empty():
    """Empty token -> don't even attempt the call. Returns False, no exception."""
    with patch("urllib.request.urlopen") as mocked:
        ok = send_telegram(bot_token="", chat_id="123", text="hi")
    assert ok is False
    mocked.assert_not_called()
