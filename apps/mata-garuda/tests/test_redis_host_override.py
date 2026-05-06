"""Tests for GARUDA_REDIS_HOST/PORT env var override in base_worker.redis_cmd.

Background (2026-05-06): Pro and Mini both run local Redis with the same
stream name (garuda:alerts). Sentinel produces alerts on Mini; feeder runs
on Pro reading localhost ⇒ silent split-brain on stream data. The feeder
needs an env-var override to point at Mini's Redis when running on Pro.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock


class TestRedisHostOverride:
    def test_default_no_host_flag(self, monkeypatch):
        """When no env var is set, redis-cli runs with no -h/-p — localhost."""
        monkeypatch.delenv("GARUDA_REDIS_HOST", raising=False)
        monkeypatch.delenv("GARUDA_REDIS_PORT", raising=False)

        from mata_garuda.workers import base_worker

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
            base_worker.redis_cmd("PING")

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0].endswith("redis-cli")
        # No -h flag means default localhost
        assert "-h" not in called_cmd
        assert "-p" not in called_cmd
        assert "PING" in called_cmd

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

    def test_empty_host_treated_as_unset(self, monkeypatch):
        """Empty string GARUDA_REDIS_HOST='' should not inject -h (whitespace too)."""
        monkeypatch.setenv("GARUDA_REDIS_HOST", "")
        monkeypatch.delenv("GARUDA_REDIS_PORT", raising=False)

        from mata_garuda.workers import base_worker

        with patch.object(base_worker.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
            base_worker.redis_cmd("PING")

        called_cmd = mock_run.call_args[0][0]
        assert "-h" not in called_cmd
