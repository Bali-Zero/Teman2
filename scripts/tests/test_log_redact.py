"""Unit tests for scripts/_log_redact.py (Mythos-P3 token-leak suppression)."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "_log_redact", SCRIPTS_DIR / "_log_redact.py"
)
_log_redact = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_log_redact)

# A fake Telegram bot token (35-char suffix), never a real one.
_FAKE = "bot123456789:" + ("A" * 35)


def test_redacting_filter_scrubs_token_in_message():
    f = _log_redact.RedactingFilter()
    rec = logging.LogRecord(
        "httpx", logging.INFO, __file__, 1,
        f"HTTP Request: GET https://api.telegram.org/{_FAKE}/getUpdates",
        None, None,
    )
    assert f.filter(rec) is True
    msg = rec.getMessage()
    assert "<REDACTED_BOT_TOKEN>" in msg
    assert "A" * 35 not in msg


def test_redacting_filter_scrubs_token_in_args():
    f = _log_redact.RedactingFilter()
    rec = logging.LogRecord(
        "x", logging.WARNING, __file__, 1, "send failed for %s", (_FAKE,), None
    )
    assert f.filter(rec) is True
    assert "<REDACTED_BOT_TOKEN>" in rec.getMessage()


def test_clean_message_untouched():
    f = _log_redact.RedactingFilter()
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "nothing secret here", None, None)
    f.filter(rec)
    assert rec.getMessage() == "nothing secret here"


def test_silence_http_access_logs():
    _log_redact.silence_http_access_logs()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def test_install_is_idempotent():
    root = logging.getLogger()
    _log_redact.install_secret_redaction()
    _log_redact.install_secret_redaction()
    assert sum(isinstance(x, _log_redact.RedactingFilter) for x in root.filters) == 1
