"""daily_briefing_agent and regulation_alert_agent each wrap
`mata_garuda.tg_curl.curl_send` for their own `_send_telegram`. The deep
guilt/innocence coverage of the send itself lives in test_tg_curl.py; this
file only checks each wrapper's own contract: chunking (daily_briefing),
dry-run/missing-token short-circuits, and that a failure reason from
`curl_send` reaches the logger unchanged (never re-derived from raw
exception/body text at the wrapper level, which is what caused the original
leak in both files before they were reduced to thin wrappers).
"""
from __future__ import annotations

from unittest.mock import patch

from mata_garuda.agents import daily_briefing_agent as dba
from mata_garuda.agents import regulation_alert_agent as raa

FAKE_TOKEN = "bot7654321098:AAF9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105


class TestDailyBriefingSendTelegram:
    def test_dry_run_never_calls_curl_send(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(dba, "curl_send") as m:
            ok = dba._send_telegram("hello", dry_run=True)
        assert ok is True
        m.assert_not_called()

    def test_missing_token_never_calls_curl_send(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        with patch.object(dba, "curl_send") as m:
            ok = dba._send_telegram("hello", dry_run=False)
        assert ok is False
        m.assert_not_called()

    def test_chunks_long_text_and_sends_each_chunk(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        long_text = "x" * (dba.TG_MAX_CHARS * 2 + 10)
        with patch.object(dba, "curl_send", return_value=(True, "")) as m:
            ok = dba._send_telegram(long_text, dry_run=False)
        assert ok is True
        assert m.call_count == 3

    def test_one_failed_chunk_fails_overall_and_logs_the_reason_verbatim(self, monkeypatch, caplog):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(
            dba, "curl_send", return_value=(False, "credential_rejected (401)"),
        ), caplog.at_level("ERROR"):
            ok = dba._send_telegram("hello", dry_run=False)
        assert ok is False
        assert "credential_rejected (401)" in caplog.text
        assert FAKE_TOKEN not in caplog.text


class TestRegulationAlertSendTelegram:
    def test_dry_run_never_calls_curl_send(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(raa, "curl_send") as m:
            ok = raa._send_telegram("alert text", dry_run=True)
        assert ok is True
        m.assert_not_called()

    def test_missing_token_never_calls_curl_send(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        with patch.object(raa, "curl_send") as m:
            ok = raa._send_telegram("alert text", dry_run=False)
        assert ok is False
        m.assert_not_called()

    def test_success_returns_true(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(raa, "curl_send", return_value=(True, "")):
            ok = raa._send_telegram("alert text", dry_run=False)
        assert ok is True

    def test_failure_logs_the_reason_verbatim_never_the_token(self, monkeypatch, caplog):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(
            raa, "curl_send", return_value=(False, "credential_rejected (401)"),
        ), caplog.at_level("ERROR"):
            ok = raa._send_telegram("alert text", dry_run=False)
        assert ok is False
        assert "credential_rejected (401)" in caplog.text
        assert FAKE_TOKEN not in caplog.text
