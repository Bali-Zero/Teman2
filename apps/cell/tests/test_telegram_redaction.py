"""cell.utils.telegram_redaction keeps the Telegram bot token out of CELL's
own logs.

Born 2026-09-27: `organism.stderr.log` carried the bot token in the clear 35
times. Root cause: httpx logs every request's full URL at INFO
(``HTTP Request: POST <url> "..."``), Telegram puts the bot token in the URL
PATH, and `cell/main.py` runs `logging.basicConfig(level=logging.INFO)` before
anything else — so every `TelegramAlerter.send()` call (successful or not)
put the token in the log. `TelegramAlerter`'s own
`except Exception as e: logger.error(f"...: {e}")` is a second path (an
`httpx.HTTPStatusError`'s `str()` also embeds the URL).
"""
from __future__ import annotations

import logging

from cell.utils.telegram_redaction import install_telegram_token_redaction

FAKE_TOKEN = "bot" + "7654321098" + ":" + "AA" + "F9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105 — synthetic, assembled at runtime so no token-shaped literal exists in the tree
FAKE_SECRET = "AAF9zZqLmN0pQrStUvWxYz1234567890abc"


class TestInstallOnHttpxLogger:
    def test_httpx_info_line_with_token_is_redacted(self, caplog):
        install_telegram_token_redaction()
        httpx_logger = logging.getLogger("httpx")

        with caplog.at_level(logging.INFO):
            httpx_logger.info(
                f'HTTP Request: POST https://tg-bot-api.example/{FAKE_TOKEN}/sendMessage "HTTP/1.1 200 OK"'
            )

        assert FAKE_SECRET not in caplog.text
        assert "<redacted>" in caplog.text

    def test_idempotent_double_install_does_not_duplicate_filters(self):
        install_telegram_token_redaction()
        install_telegram_token_redaction()
        httpx_logger = logging.getLogger("httpx")
        assert sum(
            1 for f in httpx_logger.filters if getattr(f, "_cell_telegram_token_redaction", False)
        ) == 1


class TestBackstopOnRootHandler:
    def test_alerter_style_exception_message_is_redacted_via_root_handler(self, caplog):
        """Reproduces TelegramAlerter's own failure path: an arbitrary logger
        name (not one of the known httpx/httpcore loggers) logging a message
        that embeds the token — must still be caught by the root-handler
        backstop."""
        install_telegram_token_redaction()
        alerter_logger = logging.getLogger("cell.telegram")

        with caplog.at_level(logging.ERROR):
            alerter_logger.error(
                f"Telegram send failed: Client error '401 Unauthorized' for url "
                f"'https://tg-bot-api.example/{FAKE_TOKEN}/sendMessage'"
            )

        assert FAKE_SECRET not in caplog.text
        assert "<redacted>" in caplog.text

    def test_message_without_a_token_passes_through_unchanged(self, caplog):
        install_telegram_token_redaction()
        alerter_logger = logging.getLogger("cell.telegram")

        with caplog.at_level(logging.ERROR):
            alerter_logger.error("Telegram send failed: connection refused")

        assert "connection refused" in caplog.text
        assert "<redacted>" not in caplog.text
