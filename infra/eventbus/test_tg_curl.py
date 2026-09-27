"""eventbus._tg_curl.curl_send never puts the bot token in argv.

`meta_dispatcher.py` and `research_sentinel.py` each had their own copy of
the same bug as apps/mata-garuda's daily-briefing/reg-alert senders: curl's
argv carried the bot token as a URL literal, and a broad
`except Exception as e:` logged it via `%`-formatting (renders the same as an
f-string for a token embedded in `str(e)`). Measured 2026-09-27.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eventbus import _tg_curl  # noqa: E402

FAKE_TOKEN = "bot7654321098:AAF9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105
FAKE_SECRET = "AAF9zZqLmN0pQrStUvWxYz1234567890abc"


class TestMaskTgToken:
    def test_masks_known_shape(self):
        masked = _tg_curl.mask_tg_token(f"https://tg-bot-api.example/{FAKE_TOKEN}/sendMessage")
        assert FAKE_SECRET not in masked
        assert "<redacted>" in masked

    def test_passthrough_when_absent(self):
        assert _tg_curl.mask_tg_token("no secret here") == "no secret here"


class TestCurlSendGuilt:
    def test_timeout_exception_argv_never_reaches_a_return_value(self):
        # curl_send only returns bool here (eventbus callers are best-effort),
        # so the guilt is that the exception itself must not propagate at all.
        legacy_argv_with_token = [
            "curl", "-sf", f"https://tg-bot-api.example/{FAKE_TOKEN}/sendMessage",
        ]
        with patch.object(
            _tg_curl.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(cmd=legacy_argv_with_token, timeout=10),
        ):
            ok = _tg_curl.curl_send(FAKE_TOKEN, "12345", "hello")
        assert ok is False

    def test_real_argv_never_contains_the_token(self):
        captured = {}

        def _fake_run(argv, **kwargs):
            captured["argv"] = argv
            return MagicMock(returncode=0)

        with patch.object(_tg_curl.subprocess, "run", side_effect=_fake_run):
            ok = _tg_curl.curl_send(FAKE_TOKEN, "12345", "hello")

        assert ok is True
        assert not any(FAKE_TOKEN in str(a) for a in captured["argv"])
        assert not any(FAKE_SECRET in str(a) for a in captured["argv"])


class TestCurlSendInnocence:
    def test_success_returns_true(self):
        with patch.object(_tg_curl.subprocess, "run", return_value=MagicMock(returncode=0)):
            assert _tg_curl.curl_send(FAKE_TOKEN, "12345", "hello") is True

    def test_nonzero_exit_returns_false(self):
        with patch.object(_tg_curl.subprocess, "run", return_value=MagicMock(returncode=1)):
            assert _tg_curl.curl_send(FAKE_TOKEN, "12345", "hello") is False

    def test_config_file_is_cleaned_up(self):
        seen = {}

        def _fake_run(argv, **kwargs):
            import os
            cfg_path = argv[argv.index("-K") + 1]
            seen["path"] = cfg_path
            assert os.path.exists(cfg_path)
            return MagicMock(returncode=0)

        with patch.object(_tg_curl.subprocess, "run", side_effect=_fake_run):
            _tg_curl.curl_send(FAKE_TOKEN, "12345", "hello")

        import os
        assert not os.path.exists(seen["path"])
