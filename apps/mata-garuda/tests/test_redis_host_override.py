"""Tests for GARUDA_REDIS_HOST/PORT env var override in base_worker.redis_cmd.

Background (2026-05-06): Pro and Mini both run local Redis with the same
stream name (garuda:alerts). Sentinel produces alerts on Mini; feeder runs
on Pro reading localhost ⇒ silent split-brain on stream data. The feeder
needs an env-var override to point at Mini's Redis when running on Pro.

Stage 1 single-writer cure (2026-06-29, spec mata-garuda-stage1-single-writer):
canonical Redis = Pro. The silent localhost fallback is replaced by an EXPLICIT
canonical default (CLAUDE.md Pro = workhorse H24, producers + PG sweeper live there).
When GARUDA_REDIS_HOST is unset, redis_cmd targets GARUDA_CANONICAL_REDIS_HOST.
On Pro this resolves to itself; off-Pro it stops the silent split-brain. An explicit
GARUDA_REDIS_HOST still overrides (e.g. to point at a future replica). Setting the
canonical to "" / "localhost" / "127.0.0.1" (the on-Pro / opt-out case) omits -h.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock


class TestRedisHostOverride:
    def test_default_uses_canonical_host(self, monkeypatch):
        """No GARUDA_REDIS_HOST → fall back to the explicit canonical (Pro), not silent localhost."""
        monkeypatch.delenv("GARUDA_REDIS_HOST", raising=False)
        monkeypatch.delenv("GARUDA_REDIS_PORT", raising=False)
        monkeypatch.setenv("GARUDA_CANONICAL_REDIS_HOST", "pro.tail-canonical.ts.net")

        from mata_garuda.workers import base_worker

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
            base_worker.redis_cmd("PING")

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0].endswith("redis-cli")
        assert "-h" in called_cmd
        assert called_cmd[called_cmd.index("-h") + 1] == "pro.tail-canonical.ts.net"
        assert "PING" in called_cmd

    def test_canonical_localhost_omits_host_flag(self, monkeypatch):
        """On Pro itself (or opt-out), canonical=localhost/127.0.0.1/'' → no -h flag."""
        from mata_garuda.workers import base_worker

        for canonical in ("", "localhost", "127.0.0.1"):
            monkeypatch.delenv("GARUDA_REDIS_HOST", raising=False)
            monkeypatch.delenv("GARUDA_REDIS_PORT", raising=False)
            monkeypatch.setenv("GARUDA_CANONICAL_REDIS_HOST", canonical)

            with patch.object(base_worker.subprocess, "run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
                base_worker.redis_cmd("PING")

            called_cmd = mock_run.call_args[0][0]
            assert "-h" not in called_cmd, f"canonical={canonical!r} should omit -h"
            assert "PING" in called_cmd

    def test_explicit_host_overrides_canonical(self, monkeypatch):
        """GARUDA_REDIS_HOST always wins over the canonical default (e.g. a replica)."""
        monkeypatch.setenv("GARUDA_REDIS_HOST", "replica.ts.net")
        monkeypatch.setenv("GARUDA_CANONICAL_REDIS_HOST", "pro.tail-canonical.ts.net")
        monkeypatch.delenv("GARUDA_REDIS_PORT", raising=False)

        from mata_garuda.workers import base_worker

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
            base_worker.redis_cmd("PING")

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[called_cmd.index("-h") + 1] == "replica.ts.net"

    def test_host_env_var_injects_h_flag(self, monkeypatch):
        """GARUDA_REDIS_HOST=foo.bar adds '-h foo.bar' before the command args."""
        monkeypatch.setenv("GARUDA_REDIS_HOST", "100.93.236.6")
        monkeypatch.delenv("GARUDA_REDIS_PORT", raising=False)

        from mata_garuda.workers import base_worker

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
            base_worker.redis_cmd("XLEN", "garuda:alerts")

        called_cmd = mock_run.call_args[0][0]
        assert "-h" in called_cmd
        h_idx = called_cmd.index("-h")
        assert called_cmd[h_idx + 1] == "100.93.236.6"
        # XLEN args still present after the flag
        assert "XLEN" in called_cmd
        assert "garuda:alerts" in called_cmd

    def test_port_env_var_injects_p_flag(self, monkeypatch):
        """GARUDA_REDIS_PORT=6380 adds '-p 6380' to the args."""
        monkeypatch.setenv("GARUDA_REDIS_HOST", "mini.tail461666.ts.net")
        monkeypatch.setenv("GARUDA_REDIS_PORT", "6380")

        from mata_garuda.workers import base_worker

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
            base_worker.redis_cmd("PING")

        called_cmd = mock_run.call_args[0][0]
        assert "-h" in called_cmd
        assert "-p" in called_cmd
        p_idx = called_cmd.index("-p")
        assert called_cmd[p_idx + 1] == "6380"

    def test_port_without_host_is_ignored(self, monkeypatch):
        """Setting only PORT without HOST is invalid — fall back to localhost.

        We don't synthesize a partial -p without -h since redis-cli would
        connect to localhost on the custom port, which is rarely intentional.
        Better to require both or neither — keep the contract explicit.
        """
        monkeypatch.delenv("GARUDA_REDIS_HOST", raising=False)
        monkeypatch.setenv("GARUDA_REDIS_PORT", "6380")

        from mata_garuda.workers import base_worker

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
            base_worker.redis_cmd("PING")

        called_cmd = mock_run.call_args[0][0]
        # Without HOST, port flag is dropped — localhost default
        assert "-p" not in called_cmd
        assert "-h" not in called_cmd

    def test_empty_host_falls_back_to_canonical(self, monkeypatch):
        """Empty/whitespace GARUDA_REDIS_HOST falls through to the canonical default."""
        monkeypatch.setenv("GARUDA_REDIS_HOST", "  ")
        monkeypatch.delenv("GARUDA_REDIS_PORT", raising=False)
        monkeypatch.setenv("GARUDA_CANONICAL_REDIS_HOST", "pro.tail-canonical.ts.net")

        from mata_garuda.workers import base_worker

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
            base_worker.redis_cmd("PING")

        called_cmd = mock_run.call_args[0][0]
        assert "-h" in called_cmd
        assert called_cmd[called_cmd.index("-h") + 1] == "pro.tail-canonical.ts.net"


class TestRedisCliPath:
    """Stage 1: redis-cli must resolve to an absolute path so cron/non-login shells
    (stripped PATH) stop failing mutely. This is the 'watchdog unarmed' bug — verified
    live on Pro 2026-06-29 (redis-cli not in PATH → FileNotFoundError)."""

    def test_redis_cli_resolves_absolute_when_found(self, monkeypatch):
        from mata_garuda.workers import base_worker

        monkeypatch.setattr(base_worker.shutil, "which", lambda _: "/opt/homebrew/bin/redis-cli")
        assert base_worker._resolve_redis_cli() == "/opt/homebrew/bin/redis-cli"

    def test_redis_cli_falls_back_to_known_paths(self, monkeypatch):
        from mata_garuda.workers import base_worker
        import os

        monkeypatch.setattr(base_worker.shutil, "which", lambda _: None)
        # pretend the homebrew path exists on disk
        real_exists = os.path.exists
        monkeypatch.setattr(
            base_worker.os.path, "exists",
            lambda p: p == "/opt/homebrew/bin/redis-cli" or real_exists(p),
        )
        assert base_worker._resolve_redis_cli() == "/opt/homebrew/bin/redis-cli"

    def test_redis_cli_last_resort_is_bare_name(self, monkeypatch):
        """If nothing resolves, fall back to bare 'redis-cli' (don't crash at import)."""
        from mata_garuda.workers import base_worker

        monkeypatch.setattr(base_worker.shutil, "which", lambda _: None)
        monkeypatch.setattr(base_worker.os.path, "exists", lambda _: False)
        assert base_worker._resolve_redis_cli() == "redis-cli"


class TestRedisAuth:
    """Stage 1 cutover (2026-06-29): the canonical Pro Redis is exposed on the
    Tailscale interface and therefore REQUIRES a password. base_worker must pass
    it via the REDISCLI_AUTH env var — NOT as `-a <pw>` on the command line, which
    would leak the secret into `ps`/argv (cicatrix #4: secret in the clear)."""

    def test_password_passed_via_env_not_argv(self, monkeypatch):
        from mata_garuda.workers import base_worker

        monkeypatch.setenv("GARUDA_REDIS_PASSWORD", "s3cr3t-pw")
        monkeypatch.setenv("GARUDA_REDIS_HOST", "nuzantara.tail461666.ts.net")

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="PONG", stderr="")
            base_worker.redis_cmd("PING")

        # password must NOT appear anywhere in the argv
        called_cmd = mock_run.call_args[0][0]
        assert "s3cr3t-pw" not in called_cmd
        assert "-a" not in called_cmd
        # it must be passed through the subprocess env as REDISCLI_AUTH
        passed_env = mock_run.call_args.kwargs.get("env")
        assert passed_env is not None, "redis_cmd must pass an explicit env when a password is set"
        assert passed_env.get("REDISCLI_AUTH") == "s3cr3t-pw"

    def test_no_password_no_env_override(self, monkeypatch):
        from mata_garuda.workers import base_worker

        monkeypatch.delenv("GARUDA_REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("GARUDA_REDIS_HOST", raising=False)
        monkeypatch.delenv("GARUDA_CANONICAL_REDIS_HOST", raising=False)

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="PONG", stderr="")
            base_worker.redis_cmd("PING")

        # no password set → no REDISCLI_AUTH injected (env stays None or lacks the key)
        passed_env = mock_run.call_args.kwargs.get("env")
        if passed_env is not None:
            assert "REDISCLI_AUTH" not in passed_env
