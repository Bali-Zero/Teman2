"""mata_garuda.tools.tg_tools.curl_send never puts the bot token in argv or in
whatever it returns for a caller to log.

Born 2026-09-27: Pro's `com.matagaruda.daily-briefing` and
`com.matagaruda.reg-alert.30min` jobs each had their own copy of the same
bug — curl's argv built with the bot API host as a URL literal (the real
host is kept out of this file per scripts/lint_tg_direct_senders.py; a
placeholder is used below, since `mask_tg_token` matches by token SHAPE and
never needs the host), caught by a broad
`except Exception as e: logger.error(f"...: {e}")`. A
`subprocess.TimeoutExpired`'s own `str()` embeds the full argv it was
constructed with, so a slow curl — no HTTP round-trip needed — put the token
in daily-briefing.error.log (once) and reg-alert.error.log (39x, on its
30-minute schedule). `curl_send` is the single fix for both call sites.

2026-09-27 (later same day): `curl_send` moved from the standalone
`mata_garuda/tg_curl.py` into `mata_garuda/tools/tg_tools.py`, which was
already grandfathered by scripts/lint_tg_direct_senders.py — every other
mata-garuda call site now imports it from there, and this file (formerly
`test_tg_curl.py`) moved with it.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from mata_garuda.tools import tg_tools
from mata_garuda.config import mask_tg_token

FAKE_TOKEN = "bot" + "7654321098" + ":" + "AA" + "F9zZqLmN0pQrStUvWxYz1234567890abc"  # noqa: S105 — synthetic, assembled at runtime so no token-shaped literal exists in the tree
FAKE_SECRET = "AAF9zZqLmN0pQrStUvWxYz1234567890abc"


class TestMaskTgToken:
    def test_masks_known_shape(self):
        masked = mask_tg_token(f"https://tg-bot-api.example/{FAKE_TOKEN}/sendMessage")
        assert FAKE_SECRET not in masked
        assert "<redacted>" in masked

    def test_passthrough_when_absent(self):
        assert mask_tg_token("no secret here") == "no secret here"

    def test_empty_is_noop(self):
        assert mask_tg_token("") == ""


class TestCurlSendGuilt:
    """Guilt: force the exact failure shapes that used to leak, assert the
    fake token/secret substring appears in NEITHER the return value NOR the
    argv `subprocess.run` is called with."""

    def test_timeout_exception_reason_never_contains_the_token(self):
        # Reproduce the ORIGINAL bug's exact exception: a TimeoutExpired whose
        # str() embeds an argv that (pre-fix, at either old call site) carried
        # the token as a URL literal.
        legacy_argv_with_token = [
            "curl", "-s", f"https://tg-bot-api.example/{FAKE_TOKEN}/sendMessage",
        ]
        with patch.object(
            tg_tools.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(cmd=legacy_argv_with_token, timeout=15),
        ):
            ok, reason = tg_tools.curl_send(FAKE_TOKEN, "8847435604", "hello")

        assert ok is False
        assert FAKE_SECRET not in reason
        assert FAKE_TOKEN not in reason

    def test_real_argv_never_contains_the_token(self):
        """The actual (post-fix) call: the token must not be a member of argv
        at all, independent of any logging/return-value path."""
        captured = {}

        def _fake_run(argv, **kwargs):
            captured["argv"] = argv
            return MagicMock(stdout='{"ok":true}\n200')

        with patch.object(tg_tools.subprocess, "run", side_effect=_fake_run):
            ok, reason = tg_tools.curl_send(FAKE_TOKEN, "8847435604", "hello")

        assert ok is True
        assert reason == ""
        assert not any(FAKE_TOKEN in str(a) for a in captured["argv"])
        assert not any(FAKE_SECRET in str(a) for a in captured["argv"])

    def test_401_reason_never_contains_the_token(self):
        body = (
            '{"ok":false,"error_code":401,'
            f'"description":"bot {FAKE_TOKEN} unauthorized"}}\n401'
        )
        with patch.object(tg_tools.subprocess, "run", return_value=MagicMock(stdout=body)):
            ok, reason = tg_tools.curl_send(FAKE_TOKEN, "8847435604", "hello")

        assert ok is False
        assert reason == "credential_rejected (401)"
        assert FAKE_TOKEN not in reason

    def test_generic_failure_body_is_masked(self):
        body = f'{{"ok":false,"description":"blocked by bot {FAKE_TOKEN}"}}\n400'
        with patch.object(tg_tools.subprocess, "run", return_value=MagicMock(stdout=body)):
            ok, reason = tg_tools.curl_send(FAKE_TOKEN, "8847435604", "hello")

        assert ok is False
        assert FAKE_SECRET not in reason
        assert "<redacted>" in reason


class TestCurlSendInnocence:
    def test_200_ok_returns_true_empty_reason(self):
        with patch.object(
            tg_tools.subprocess, "run",
            return_value=MagicMock(stdout='{"ok":true,"result":{}}\n200'),
        ):
            ok, reason = tg_tools.curl_send(FAKE_TOKEN, "8847435604", "hello")
        assert ok is True
        assert reason == ""

    def test_config_file_is_cleaned_up(self, tmp_path):
        seen_paths = []

        def _fake_run(argv, **kwargs):
            cfg_path = argv[argv.index("-K") + 1]
            seen_paths.append(cfg_path)
            import os
            assert os.path.exists(cfg_path)
            return MagicMock(stdout='{"ok":true}\n200')

        with patch.object(tg_tools.subprocess, "run", side_effect=_fake_run):
            tg_tools.curl_send(FAKE_TOKEN, "8847435604", "hello")

        import os
        assert not os.path.exists(seen_paths[0])
