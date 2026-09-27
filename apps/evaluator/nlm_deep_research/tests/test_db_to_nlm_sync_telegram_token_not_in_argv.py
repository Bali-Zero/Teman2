"""db_to_nlm_sync._send_telegram_alert never puts the bot token in curl's argv.

This call site was already log-safe (its `except Exception:` logs a static
string, never `{e}`) but still built curl's argv with the token as a URL
literal — `ps`/`/proc` visible. Measured 2026-09-27 alongside the
apps/mata-garuda and infra/eventbus siblings that had the log-leaking shape
of the same underlying pattern.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.evaluator.nlm_deep_research import db_to_nlm_sync

FAKE_TOKEN = "bot" + "7654321098" + ":" + "AA" + "F9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105 — synthetic, assembled at runtime so no token-shaped literal exists in the tree


class TestSendTelegramAlert:
    def test_missing_token_never_calls_subprocess(self, monkeypatch):
        monkeypatch.setattr(db_to_nlm_sync, "TG_BOT_TOKEN", "")
        with patch.object(db_to_nlm_sync.subprocess, "run") as m:
            db_to_nlm_sync._send_telegram_alert("hi")
        m.assert_not_called()

    def test_real_argv_never_contains_the_token(self, monkeypatch):
        monkeypatch.setattr(db_to_nlm_sync, "TG_BOT_TOKEN", FAKE_TOKEN)
        monkeypatch.setattr(db_to_nlm_sync, "TG_CHAT_ID", "12345")
        captured = {}

        def _fake_run(argv, **kwargs):
            captured["argv"] = argv
            return MagicMock(returncode=0)

        with patch.object(db_to_nlm_sync.subprocess, "run", side_effect=_fake_run):
            db_to_nlm_sync._send_telegram_alert("hi")

        assert not any(FAKE_TOKEN in str(a) for a in captured["argv"])

    def test_config_file_is_cleaned_up(self, monkeypatch):
        monkeypatch.setattr(db_to_nlm_sync, "TG_BOT_TOKEN", FAKE_TOKEN)
        monkeypatch.setattr(db_to_nlm_sync, "TG_CHAT_ID", "12345")
        seen = {}

        def _fake_run(argv, **kwargs):
            import os
            cfg_path = argv[argv.index("-K") + 1]
            seen["path"] = cfg_path
            assert os.path.exists(cfg_path)
            return MagicMock(returncode=0)

        with patch.object(db_to_nlm_sync.subprocess, "run", side_effect=_fake_run):
            db_to_nlm_sync._send_telegram_alert("hi")

        import os
        assert not os.path.exists(seen["path"])

    def test_subprocess_exception_never_raises(self, monkeypatch):
        """Guilt-adjacent: this function's contract is fire-and-forget — a
        raised exception must not propagate to the caller."""
        monkeypatch.setattr(db_to_nlm_sync, "TG_BOT_TOKEN", FAKE_TOKEN)
        monkeypatch.setattr(db_to_nlm_sync, "TG_CHAT_ID", "12345")
        with patch.object(db_to_nlm_sync.subprocess, "run", side_effect=OSError("boom")):
            result = db_to_nlm_sync._send_telegram_alert("hi")
        assert result is None  # returned cleanly instead of propagating OSError
