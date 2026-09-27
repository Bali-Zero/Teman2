"""eventbus.meta_dispatcher.curl_send never puts the bot token in argv.

`meta_dispatcher.py` and `research_sentinel.py` each had their own copy of
the same bug as apps/mata-garuda's daily-briefing/reg-alert senders: curl's
argv carried the bot token as a URL literal, and a broad
`except Exception as e:` logged it via `%`-formatting (renders the same as an
f-string for a token embedded in `str(e)`). Measured 2026-09-27.

Later the same day, `curl_send` moved from the standalone `eventbus/_tg_curl.py`
into `eventbus/meta_dispatcher.py` (already grandfathered by
scripts/lint_tg_direct_senders.py) — `research_sentinel.py` now imports it
from there, `_tg_curl.py` is gone, and this file (formerly `test_tg_curl.py`)
moved with it. The merge also added a one-line failure log (no token, no
body) in place of the previous silent `return False` — covered below.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eventbus import meta_dispatcher  # noqa: E402

FAKE_TOKEN = "bot" + "7654321098" + ":" + "AA" + "F9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105 — synthetic, assembled at runtime so no token-shaped literal exists in the tree
FAKE_SECRET = "AAF9zZqLmN0pQrStUvWxYz1234567890abc"


class TestMaskTgToken:
    def test_masks_known_shape(self):
        masked = meta_dispatcher.mask_tg_token(f"https://tg-bot-api.example/{FAKE_TOKEN}/sendMessage")
        assert FAKE_SECRET not in masked
        assert "<redacted>" in masked

    def test_passthrough_when_absent(self):
        assert meta_dispatcher.mask_tg_token("no secret here") == "no secret here"


class TestCurlSendGuilt:
    def test_timeout_exception_argv_never_reaches_a_return_value(self):
        # curl_send only returns bool here (eventbus callers are best-effort),
        # so the guilt is that the exception itself must not propagate at all.
        legacy_argv_with_token = [
            "curl", "-sf", f"https://tg-bot-api.example/{FAKE_TOKEN}/sendMessage",
        ]
        with patch.object(
            meta_dispatcher.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(cmd=legacy_argv_with_token, timeout=10),
        ):
            ok = meta_dispatcher.curl_send(FAKE_TOKEN, "12345", "hello")
        assert ok is False

    def test_timeout_exception_failure_log_never_contains_the_token(self, caplog):
        # Guilt for the new one-line failure log added 2026-09-27: it must
        # never carry the token, even though the exception it replaces did.
        legacy_argv_with_token = [
            "curl", "-sf", f"https://tg-bot-api.example/{FAKE_TOKEN}/sendMessage",
        ]
        with caplog.at_level("WARNING", logger="meta-dispatcher"):
            with patch.object(
                meta_dispatcher.subprocess, "run",
                side_effect=subprocess.TimeoutExpired(cmd=legacy_argv_with_token, timeout=10),
            ):
                meta_dispatcher.curl_send(FAKE_TOKEN, "12345", "hello")

        rendered = "\n".join(r.getMessage() for r in caplog.records)
        assert FAKE_TOKEN not in rendered
        assert FAKE_SECRET not in rendered

    def test_nonzero_exit_failure_log_never_contains_the_token(self, caplog):
        with caplog.at_level("WARNING", logger="meta-dispatcher"):
            with patch.object(meta_dispatcher.subprocess, "run", return_value=MagicMock(returncode=1)):
                meta_dispatcher.curl_send(FAKE_TOKEN, "12345", "hello")

        rendered = "\n".join(r.getMessage() for r in caplog.records)
        assert FAKE_TOKEN not in rendered
        assert FAKE_SECRET not in rendered

    def test_real_argv_never_contains_the_token(self):
        captured = {}

        def _fake_run(argv, **kwargs):
            captured["argv"] = argv
            return MagicMock(returncode=0)

        with patch.object(meta_dispatcher.subprocess, "run", side_effect=_fake_run):
            ok = meta_dispatcher.curl_send(FAKE_TOKEN, "12345", "hello")

        assert ok is True
        assert not any(FAKE_TOKEN in str(a) for a in captured["argv"])
        assert not any(FAKE_SECRET in str(a) for a in captured["argv"])


class TestCurlSendInnocence:
    def test_success_returns_true(self):
        with patch.object(meta_dispatcher.subprocess, "run", return_value=MagicMock(returncode=0)):
            assert meta_dispatcher.curl_send(FAKE_TOKEN, "12345", "hello") is True

    def test_nonzero_exit_returns_false(self):
        with patch.object(meta_dispatcher.subprocess, "run", return_value=MagicMock(returncode=1)):
            assert meta_dispatcher.curl_send(FAKE_TOKEN, "12345", "hello") is False

    def test_config_file_is_cleaned_up(self):
        seen = {}

        def _fake_run(argv, **kwargs):
            import os
            cfg_path = argv[argv.index("-K") + 1]
            seen["path"] = cfg_path
            assert os.path.exists(cfg_path)
            return MagicMock(returncode=0)

        with patch.object(meta_dispatcher.subprocess, "run", side_effect=_fake_run):
            meta_dispatcher.curl_send(FAKE_TOKEN, "12345", "hello")

        import os
        assert not os.path.exists(seen["path"])
