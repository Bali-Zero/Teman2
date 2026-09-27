"""Every mata-garuda Telegram sender that migrated to
`mata_garuda.tools.tg_tools.curl_send` (2026-09-27 tg-token-log-hygiene fix +
its rework) wraps it the same way. The deep guilt/innocence coverage of the
send itself lives in test_tg_tools_curl_send.py; this file only checks each wrapper's own
contract: chunking (daily_briefing), dry-run/missing-token short-circuits,
and that a failure reason from `curl_send` reaches the logger/return value
unchanged (never re-derived from raw exception/body text at the wrapper
level, which is what caused the original leak before these were reduced to
thin wrappers).

`sentinel_actor.py` migrated too (same call shape as the others below) but is
not covered here: its module-level `from cell_core.types import ...` import
fails in this dev environment (`cell_core` is not installed), the same gap
that already excludes test_sentinel_cell.py/test_run_sentinel_cell.py from
local collection — verified instead by `python3 -m py_compile` and manual
code review.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

_PACKAGE_PATH = Path(__file__).resolve().parents[1]
if str(_PACKAGE_PATH) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PATH))

from mata_garuda.agents import daily_briefing_agent as dba  # noqa: E402
from mata_garuda.agents import regulation_alert_agent as raa  # noqa: E402
from mata_garuda.tools import tg_public_tools  # noqa: E402
from mata_garuda.tools import tg_tools  # noqa: E402
from scripts import run_ai_digest  # noqa: E402

FAKE_TOKEN = "bot" + "7654321098" + ":" + "AA" + "F9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105 — synthetic, assembled at runtime so no token-shaped literal exists in the tree


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


class TestTgToolsSendTgAlert:
    def test_missing_token_never_calls_curl_send(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        with patch.object(tg_tools, "curl_send") as m:
            result = tg_tools.send_tg_alert("hi")
        assert "not set" in result
        m.assert_not_called()

    def test_success_reports_success_and_preserves_markdown_parse_mode(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(tg_tools, "curl_send", return_value=(True, "")) as m:
            result = tg_tools.send_tg_alert("hi")
        assert "[SUCCESS]" in result
        assert m.call_args.kwargs.get("extra_fields") == {"parse_mode": "Markdown"}

    def test_failure_reports_reason_never_the_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(tg_tools, "curl_send", return_value=(False, "credential_rejected (401)")):
            result = tg_tools.send_tg_alert("hi")
        assert "credential_rejected (401)" in result
        assert FAKE_TOKEN not in result


class TestTgPublicToolsSendPost:
    def test_missing_token_never_calls_curl_send(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        with patch.object(tg_public_tools, "curl_send") as m:
            result = tg_public_tools.send_tg_public_post("hi")
        assert "not set" in result
        m.assert_not_called()

    def test_unconfigured_channel_is_dry_run_and_never_calls_curl_send(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        monkeypatch.delenv("TELEGRAM_PUBLIC_CHANNEL_ID", raising=False)
        with patch.object(tg_public_tools, "curl_send") as m:
            result = tg_public_tools.send_tg_public_post("hi")
        assert "DRY-RUN" in result
        m.assert_not_called()

    def test_success_preserves_markdown_and_preview_fields(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "-100123")
        with patch.object(tg_public_tools, "curl_send", return_value=(True, "")) as m:
            result = tg_public_tools.send_tg_public_post("hi")
        assert "[SUCCESS]" in result
        assert m.call_args.kwargs.get("extra_fields") == {
            "parse_mode": "Markdown", "disable_web_page_preview": "false",
        }

    def test_failure_reports_reason_never_the_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "-100123")
        with patch.object(
            tg_public_tools, "curl_send", return_value=(False, "credential_rejected (401)"),
        ):
            result = tg_public_tools.send_tg_public_post("hi")
        assert "credential_rejected (401)" in result
        assert FAKE_TOKEN not in result


class TestRunAiDigestSendTelegram:
    def test_missing_token_never_calls_curl_send(self, monkeypatch, capsys):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        with patch.object(run_ai_digest, "curl_send") as m:
            ok = run_ai_digest.send_telegram("hi")
        assert ok is False
        m.assert_not_called()

    def test_success_returns_true(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(run_ai_digest, "curl_send", return_value=(True, "")):
            ok = run_ai_digest.send_telegram("hi")
        assert ok is True

    def test_failure_prints_the_reason_never_the_token(self, monkeypatch, capsys):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
        with patch.object(
            run_ai_digest, "curl_send", return_value=(False, "credential_rejected (401)"),
        ):
            ok = run_ai_digest.send_telegram("hi")
        assert ok is False
        out = capsys.readouterr().out
        assert "credential_rejected (401)" in out
        assert FAKE_TOKEN not in out
