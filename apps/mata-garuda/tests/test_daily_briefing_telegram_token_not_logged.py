"""daily_briefing_agent's Telegram sender never puts the bot token in a log.

Born 2026-09-27: Pro's `com.matagaruda.daily-briefing` job logged its bot
token in cleartext in daily-briefing.error.log. Root cause, measured: the old
`_send_telegram` built the curl argv as
`["curl", ..., f"https://api.telegram.org/bot{token}/sendMessage", ...]` and
caught any exception with `logger.error(f"...: {e}")` — a
`subprocess.TimeoutExpired`'s own `str()` embeds the full argv it was given,
token included. The fix moves the token out of argv entirely (a private `-K`
config file) and masks any residual token-shaped substring via
`mask_tg_token`. Guilt below reproduces the ORIGINAL exception shape (a
`TimeoutExpired` built from the real argv `_send_telegram` hands to
`subprocess.run`) to prove the fix holds even if the argv construction
regresses.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from mata_garuda.agents import daily_briefing_agent as dba
from mata_garuda.config import mask_tg_token

FAKE_TOKEN = "bot7654321098:AAF9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105


class TestMaskTgToken:
    def test_masks_known_shape(self):
        masked = mask_tg_token(f"https://api.telegram.org/{FAKE_TOKEN}/sendMessage")
        assert "AAF9zZqLmN0pQrStUvWxYz1234567890abc" not in masked
        assert "<redacted>" in masked

    def test_passthrough_when_absent(self):
        assert mask_tg_token("no secret here") == "no secret here"

    def test_empty_is_noop(self):
        assert mask_tg_token("") == ""


class TestSendTelegramGuilt:
    """Guilt: force the exact failure shapes that used to leak, assert the
    fake token substring appears in NO captured log line."""

    def test_timeout_exception_never_logs_the_token(self, monkeypatch, caplog):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        # Reproduce the ORIGINAL bug's exact exception: a TimeoutExpired
        # whose str() embeds an argv that (pre-fix) carried the token.
        legacy_argv_with_token = [
            "curl", "-s", f"https://api.telegram.org/{FAKE_TOKEN}/sendMessage",
        ]
        with patch.object(
            dba.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(cmd=legacy_argv_with_token, timeout=15),
        ), caplog.at_level("ERROR"):
            ok = dba._send_telegram("hello", dry_run=False)

        assert ok is False
        assert "AAF9zZqLmN0pQrStUvWxYz1234567890abc" not in caplog.text
        assert FAKE_TOKEN not in caplog.text

    def test_current_argv_never_contains_the_token(self, monkeypatch):
        """The real (post-fix) call: the token must not be a member of argv
        at all, independent of any logging path."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        captured = {}

        def _fake_run(argv, **kwargs):
            captured["argv"] = argv
            return MagicMock(stdout='{"ok":true}\n200')

        with patch.object(dba.subprocess, "run", side_effect=_fake_run):
            ok = dba._send_telegram("hello", dry_run=False)

        assert ok is True
        assert not any(FAKE_TOKEN in str(a) for a in captured["argv"])

    def test_401_never_logs_the_token(self, monkeypatch, caplog):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        body = (
            '{"ok":false,"error_code":401,'
            f'"description":"bot {FAKE_TOKEN} unauthorized"}}\n401'
        )
        with patch.object(
            dba.subprocess, "run", return_value=MagicMock(stdout=body),
        ), caplog.at_level("ERROR"):
            ok = dba._send_telegram("hello", dry_run=False)

        assert ok is False
        assert "credential_rejected (401)" in caplog.text
        assert FAKE_TOKEN not in caplog.text


class TestSendTelegramInnocence:
    def test_200_ok_returns_true_and_logs_nothing(self, monkeypatch, caplog):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(
            dba.subprocess, "run",
            return_value=MagicMock(stdout='{"ok":true,"result":{}}\n200'),
        ), caplog.at_level("ERROR"):
            ok = dba._send_telegram("hello", dry_run=False)

        assert ok is True
        assert caplog.text == ""

    def test_dry_run_never_calls_subprocess(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(dba.subprocess, "run") as m_run:
            ok = dba._send_telegram("hello", dry_run=True)
        assert ok is True
        m_run.assert_not_called()

    def test_missing_token_returns_false_without_calling_subprocess(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        with patch.object(dba.subprocess, "run") as m_run:
            ok = dba._send_telegram("hello", dry_run=False)
        assert ok is False
        m_run.assert_not_called()
