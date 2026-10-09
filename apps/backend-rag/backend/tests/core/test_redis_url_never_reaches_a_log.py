"""A Redis connection string's password must not survive a log line.

Scar being pinned (2026-10-09): `crm_hgt_handlers` logged `bridge initialized url=%s`
with the full Upstash `REDIS_URL` at INFO. Fly ships app logs to a fleet machine that
archives them; five cleartext occurrences over three days had to be scrubbed by hand.

The cure is the CHANNEL (`backend/core/secret_log_redaction`), not the call site, and
this file proves it: the emitting logger below is the real one, by name, and nothing in
`crm_hgt_handlers.py` was edited.

Judged by guilt AND innocence (superscar #3): CI workflows really do use credential-free
`redis://localhost:6379`, and a redactor that rewrites those is a bug.

The password is synthetic and deliberately not shaped like a real one.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core.secret_log_redaction import (
    SecretRedactionFilter,
    TelegramTokenRedactionFilter,
    install_secret_log_redaction,
    install_telegram_token_redaction,
)

SYNTHETIC_PASSWORD = "not-a-real-password-synthetic"  # noqa: S105
REDIS_URL = f"redis://default:{SYNTHETIC_PASSWORD}@fly-nuzantara-redis.upstash.io:6379"
LEAKING_LOGGER = "backend.services.events.handlers.crm_hgt_handlers"
REAL_MESSAGE = "crm_hgt_handlers: bridge initialized url=%s"

# synthetic-telegram-token
FAKE_TG_TOKEN = "bot7654321098:AAF9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105
TG_SECRET_HALF = "AAF9zZqLmN0pQrStUvWxYz1234567890abc"

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.rendered: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.rendered.append(record.getMessage())


def _record(name: str, msg: str, args: tuple = ()) -> logging.LogRecord:
    return logging.LogRecord(name, logging.INFO, __file__, 1, msg, args, None)


@pytest.fixture
def clean_logging():
    """Own every knob that can silence or double a record (see the Telegram test)."""
    root = logging.getLogger()
    named = [logging.getLogger(n) for n in ("httpx", LEAKING_LOGGER)]
    saved_root = (list(root.handlers), list(root.filters), root.level, root.disabled)
    saved_named = [
        (lg, list(lg.filters), list(lg.handlers), lg.level, lg.propagate, lg.disabled)
        for lg in named
    ]
    saved_disable = logging.root.manager.disable

    logging.disable(logging.NOTSET)
    root.handlers, root.filters = [], []
    root.setLevel(logging.INFO)
    root.disabled = False
    for lg in named:
        lg.filters, lg.handlers = [], []
        lg.setLevel(logging.INFO)
        lg.propagate = True
        lg.disabled = False

    yield root

    root.handlers, root.filters, root.level, root.disabled = saved_root
    logging.root.manager.disable = saved_disable
    for lg, filters, handlers, level, propagate, disabled in saved_named:
        lg.filters, lg.handlers = filters, handlers
        lg.level, lg.propagate, lg.disabled = level, propagate, disabled


class TestGuiltThePasswordDoesNotSurvive:
    def test_the_real_leaking_logger_is_redacted_by_the_root_handler_half(self, clean_logging):
        """The logger nobody listed: only the handler half can reach it. No call-site edit."""
        capture = _Capture()
        clean_logging.addHandler(capture)
        install_secret_log_redaction()

        logging.getLogger(LEAKING_LOGGER).info(REAL_MESSAGE, REDIS_URL)

        assert capture.rendered, "the line must still be logged — we redact, we do not silence"
        (line,) = capture.rendered
        assert SYNTHETIC_PASSWORD not in line
        assert line == (
            "crm_hgt_handlers: bridge initialized "
            "url=redis://default:<redacted>@fly-nuzantara-redis.upstash.io:6379"
        )

    def test_a_named_url_emitting_logger_is_redacted_where_the_record_is_born(self, clean_logging):
        """Handler bolted on the named logger with propagation off: root never sees it."""
        httpx_logger = logging.getLogger("httpx")
        capture = _Capture()
        httpx_logger.addHandler(capture)
        httpx_logger.propagate = False
        install_secret_log_redaction()

        httpx_logger.info("connecting to %s", REDIS_URL)

        (line,) = capture.rendered
        assert SYNTHETIC_PASSWORD not in line
        assert "redis://default:<redacted>@fly-nuzantara-redis.upstash.io:6379" in line

    def test_the_secret_in_args_is_redacted_and_survives_a_re_render(self):
        """%-args: a handler re-renders args later, so msg alone is not enough."""
        record = _record(LEAKING_LOGGER, "bridge initialized url=%s", (REDIS_URL,))
        SecretRedactionFilter().filter(record)

        assert SYNTHETIC_PASSWORD not in record.getMessage()
        assert SYNTHETIC_PASSWORD not in str(record.args)
        assert SYNTHETIC_PASSWORD not in record.msg

    def test_rediss_and_a_missing_username_are_redacted_too(self):
        for url in (
            f"rediss://default:{SYNTHETIC_PASSWORD}@host.example:6380/0",
            f"redis://:{SYNTHETIC_PASSWORD}@host.example:6379",
        ):
            record = _record("x", "url=%s", (url,))
            SecretRedactionFilter().filter(record)
            assert SYNTHETIC_PASSWORD not in record.getMessage()
            assert "<redacted>@host.example" in record.getMessage()

    def test_a_password_with_a_literal_at_sign_leaves_no_tail(self):
        record = _record("x", f"url=redis://default:pa@ss-{SYNTHETIC_PASSWORD}@host.example:6379")
        SecretRedactionFilter().filter(record)
        assert "ss-" not in record.getMessage()
        assert SYNTHETIC_PASSWORD not in record.getMessage()


class TestInnocenceCredentialFreeUrlsAreByteIdentical:
    @pytest.mark.parametrize(
        "original",
        [
            "redis://localhost:6379",
            "redis://127.0.0.1:6379/0",
            "crm_hgt_handlers: bridge initialized url=redis://localhost:6379",
            "REDIS_URL unset, falling back to redis://localhost:6379 for user@example.com",
            "redis cache warmed in 12ms",
            "the word redis alone, and a bot mention, are not secrets",
        ],
    )
    def test_untouched(self, original):
        record = _record(LEAKING_LOGGER, original)
        SecretRedactionFilter().filter(record)
        assert record.msg == original
        assert record.getMessage() == original

    def test_a_credential_free_url_in_args_keeps_its_args(self):
        record = _record(LEAKING_LOGGER, "url=%s", ("redis://localhost:6379",))
        SecretRedactionFilter().filter(record)
        assert record.args == ("redis://localhost:6379",)

    def test_the_filter_never_drops_a_record(self):
        assert SecretRedactionFilter().filter(_record("x", REDIS_URL)) is True

    def test_it_fails_open_when_a_record_cannot_be_rendered(self):
        assert SecretRedactionFilter().filter(_record("x", "%s %s", ("one",))) is True


class TestNoRegressionOnTelegramAndTheOldNames:
    def test_a_telegram_token_is_still_redacted(self):
        record = _record("httpx", "POST https://api.telegram.org/%s/sendMessage", (FAKE_TG_TOKEN,))
        SecretRedactionFilter().filter(record)
        assert TG_SECRET_HALF not in record.getMessage()
        assert "bot7654321098:<redacted>" in record.getMessage()

    def test_both_secrets_on_one_line_are_both_redacted(self):
        record = _record("x", f"{FAKE_TG_TOKEN} and {REDIS_URL}")
        SecretRedactionFilter().filter(record)
        assert TG_SECRET_HALF not in record.getMessage()
        assert SYNTHETIC_PASSWORD not in record.getMessage()

    def test_the_historical_names_are_the_general_ones(self):
        assert TelegramTokenRedactionFilter is SecretRedactionFilter
        assert install_telegram_token_redaction is install_secret_log_redaction

    def test_the_old_installer_now_cures_redis_too(self, clean_logging):
        capture = _Capture()
        clean_logging.addHandler(capture)
        install_telegram_token_redaction()
        logging.getLogger(LEAKING_LOGGER).info(REAL_MESSAGE, REDIS_URL)
        assert SYNTHETIC_PASSWORD not in capture.rendered[0]

    def test_installing_twice_does_not_stack(self, clean_logging):
        clean_logging.addHandler(_Capture())
        install_secret_log_redaction()
        first = len(logging.getLogger("httpx").filters)
        install_secret_log_redaction()
        install_telegram_token_redaction()
        assert len(logging.getLogger("httpx").filters) == first


class TestTheApiProcessInstallsItDeterministically:
    def test_configure_logging_leaves_every_root_handler_redacting(self):
        """The real bootstrap, in a real process, with no Telegram module imported.

        `configure_logging()` clears root's handlers, so an install that happened to run
        earlier (by importing a Telegram sender) is discarded. The redaction therefore
        lives at the END of `configure_logging()`. A subprocess: both global state.
        """
        probe = (
            "import logging\n"
            "from backend.app.setup.logging_config import configure_logging\n"
            "configure_logging()\n"
            "import sys\n"
            "assert not [m for m in sys.modules if 'telegram' in m], 'probe is not telegram-free'\n"
            "root = logging.getLogger()\n"
            "assert root.handlers, 'no root handlers'\n"
            "for h in root.handlers:\n"
            "    assert any(type(f).__name__ == 'SecretRedactionFilter' for f in h.filters), h\n"
            f"logging.getLogger('{LEAKING_LOGGER}').info('{REAL_MESSAGE}', '{REDIS_URL}')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=BACKEND_ROOT.parent,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT.parent), "ENVIRONMENT": "development"},
        )
        assert proc.returncode == 0, f"probe failed: {proc.stderr[-2000:]}"
        combined = proc.stdout + proc.stderr
        assert "bridge initialized" in combined, "the line was never logged — probe is vacuous"
        assert SYNTHETIC_PASSWORD not in combined
        assert "redis://default:<redacted>@" in combined
