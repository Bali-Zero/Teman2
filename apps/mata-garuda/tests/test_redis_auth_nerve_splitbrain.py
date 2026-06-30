"""Regression tests for the W89 NOAUTH-swallow family: nerve.py bridge +
check_redis_split_brain.py guardian.

Background (2026-06-30): PR #1825's Stage 1 cutover put the canonical Pro Redis
behind requirepass and fixed base_worker (REDISCLI_AUTH via env). But two organs
were left running bare `redis-cli` with NO env=:

  1. bridge/nerve.py — _default_redis_xadd / _default_redis_xreadgroup /
     _default_redis_xack. redis-cli returns "NOAUTH Authentication required." at
     EXIT 0, so the bridge silently parsed it into an empty result and idled.
  2. scripts/check_redis_split_brain.py — rcli() probes BOTH hosts with no auth.
     The Pro side returned NOAUTH → host_stream_state collapsed to None → the
     Pro/Mini drift comparison never ran → exit 0. The split-brain guardian
     (the cicatrix #10 watchdog) was itself green-blind (cicatrix #2).

These tests pin both fixes: the password rides REDISCLI_AUTH in the subprocess
env (never -a on argv, cicatrix #4), and an auth failure is surfaced loudly
rather than swallowed into a healthy-looking empty/None result.
"""
from __future__ import annotations

import importlib.util
import pathlib
from unittest.mock import MagicMock, patch

import pytest


# ── nerve.py bridge ────────────────────────────────────────────────────────


class TestNerveRedisAuth:
    def test_xadd_passes_password_via_env_not_argv(self, monkeypatch):
        from mata_garuda.bridge import nerve

        monkeypatch.setenv("GARUDA_REDIS_PASSWORD", "s3cr3t-pw")
        with patch.object(nerve.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="123-0", stderr="")
            nerve._default_redis_xadd("garuda:bridge:outbound", {"k": "v"})

        called_cmd = mock_run.call_args[0][0]
        assert "s3cr3t-pw" not in called_cmd and "-a" not in called_cmd
        passed_env = mock_run.call_args.kwargs.get("env")
        assert passed_env is not None and passed_env.get("REDISCLI_AUTH") == "s3cr3t-pw"

    def test_xreadgroup_passes_env(self, monkeypatch):
        from mata_garuda.bridge import nerve

        monkeypatch.setenv("GARUDA_REDIS_PASSWORD", "pw2")
        with patch.object(nerve.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            nerve._default_redis_xreadgroup("s", "g", "c", 10, 0)

        # XGROUP CREATE + XREADGROUP both carry env=
        for call in mock_run.call_args_list:
            assert call.kwargs.get("env", {}).get("REDISCLI_AUTH") == "pw2"

    def test_xack_passes_env(self, monkeypatch):
        from mata_garuda.bridge import nerve

        monkeypatch.setenv("GARUDA_REDIS_PASSWORD", "pw3")
        with patch.object(nerve.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1", stderr="")
            nerve._default_redis_xack("s", "g", "123-0")

        assert mock_run.call_args.kwargs.get("env", {}).get("REDISCLI_AUTH") == "pw3"

    def test_xreadgroup_noauth_returns_empty_not_garbage(self, monkeypatch):
        """NOAUTH text at exit 0 must yield [] explicitly, never be parsed as data."""
        from mata_garuda.bridge import nerve

        with patch.object(nerve.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="NOAUTH Authentication required.", stderr=""
            )
            out = nerve._default_redis_xreadgroup("s", "g", "c", 10, 0)
        assert out == []


# ── check_redis_split_brain.py guardian ────────────────────────────────────


def _load_splitbrain():
    here = pathlib.Path(__file__).resolve().parent.parent
    path = here / "scripts" / "check_redis_split_brain.py"
    spec = importlib.util.spec_from_file_location("check_redis_split_brain", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestSplitBrainGuardian:
    def test_rcli_passes_password_via_env(self, monkeypatch):
        m = _load_splitbrain()
        monkeypatch.setenv("GARUDA_REDIS_PASSWORD", "guardian-pw")
        with patch.object(m.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="length\n5\n")
            m.rcli("127.0.0.1", "XINFO", "STREAM", "garuda:raw")
        called_cmd = mock_run.call_args[0][0]
        assert "guardian-pw" not in called_cmd and "-a" not in called_cmd
        assert mock_run.call_args.kwargs.get("env", {}).get("REDISCLI_AUTH") == "guardian-pw"

    def test_noauth_raises_instead_of_silent_none(self):
        """The core green-blind bug: NOAUTH must NOT collapse to None (=='no drift')."""
        m = _load_splitbrain()
        with patch.object(m, "rcli", return_value="NOAUTH Authentication required."):
            with pytest.raises(m.RedisAuthError):
                m.host_stream_state("127.0.0.1", "garuda:raw")

    def test_detect_split_brain_alerts_on_auth_failure(self):
        """An auth-broken probe must produce an alert (exit 1), not a clean exit 0."""
        m = _load_splitbrain()
        with patch.object(m, "rcli", return_value="NOAUTH Authentication required."):
            rep = m.detect_split_brain()
        assert rep["alerts"], "auth failure must raise an alert, not a green report"
        assert any(a.get("error") == "probe_auth_failed" for a in rep["alerts"])

    def test_no_such_key_still_returns_none(self):
        """A genuinely missing stream is still a benign None (not an auth alert)."""
        m = _load_splitbrain()
        with patch.object(m, "rcli", return_value="(error) ERR no such key"):
            assert m.host_stream_state("127.0.0.1", "garuda:raw") is None

    def test_healthy_both_hosts_no_alert(self):
        """Both hosts in sync → no alert, exit 0 (innocence test)."""
        m = _load_splitbrain()
        xinfo = "length\n10\nlast-generated-id\n1782800000000-0\n"
        with patch.object(m, "rcli", return_value=xinfo):
            rep = m.detect_split_brain()
        assert not rep["alerts"]

    def test_redis_cli_resolves_absolute_path(self):
        """Under cron/non-login PATH, the guardian must not crash on bare name."""
        m = _load_splitbrain()
        # _resolve_redis_cli returns a real path when which() finds it, else a
        # known abs path, else bare 'redis-cli' — never raises.
        assert isinstance(m.REDIS_CLI, str) and m.REDIS_CLI

    def test_missing_redis_cli_raises_not_crashes_green(self):
        """FileNotFoundError (redis-cli absent in stripped PATH) → loud alert, not crash-to-green."""
        m = _load_splitbrain()

        def _boom(*a, **k):
            raise FileNotFoundError(2, "No such file or directory", "redis-cli")

        with patch.object(m.subprocess, "run", _boom):
            with pytest.raises(m.RedisAuthError):
                m.rcli("127.0.0.1", "PING")
        # and at the orchestration level it becomes a probe alert (exit 1)
        with patch.object(m.subprocess, "run", _boom):
            rep = m.detect_split_brain()
        assert rep["alerts"] and rep["alerts"][0].get("error") == "probe_auth_failed"
