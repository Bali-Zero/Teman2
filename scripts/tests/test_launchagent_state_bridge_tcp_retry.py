"""Tests for launchagent-state-bridge's TCP-probe retry (2026-08-18, healer tick).

Root cause this pins shut: `build_tcp_receipt()` (cicatrix family #8 —
"azioni puntuali non protette da retry") did a single `socket.create_connection`
attempt and reported "failed" on the first OSError. The organ_id it drives,
`infra.eventbus_redis_mini`, is probed cross-host (this bridge runs resident on
Pro, reaching Mini's Tailscale IP on port 6379) — an ordinary transient
network flap there produced a P1 `organs_heartbeat` DIVERGED finding in
proprioception even though a probe moments later (or from Mini itself)
succeeded instantly. Measured live 2026-08-18: the sidecar recorded
"tcp connect failed: timed out" at 09:05:36 WITA while three consecutive
local connects from Mini to the same host:port each completed in ~1ms.

Contract (guilt + innocence, per cicatrix-superscar #8 antidote: "azioni
puntuali avvolte in retry-loop con backoff"):
  - GUILT: every attempt fails -> status="failed", last_error names the
    attempt count, and `sleep` is invoked between attempts (not a busy spin).
  - INNOCENCE: the first attempt fails but a later attempt succeeds ->
    status="ok", no failure surfaces.
  - The default retries/timeout stay small (worst case ~9s) so the cron
    wrapper does not itself become a hang risk.

The module name is loaded via importlib (hyphenated filename), mirroring
test_launchagent_state_bridge_host_guard.py.
"""
import importlib.util
import os
import socket
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def bridge():
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    spec = importlib.util.spec_from_file_location(
        "launchagent_state_bridge_tcp_retry",
        os.path.join(_SCRIPTS_DIR, "launchagent-state-bridge.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestBuildTcpReceiptRetry:
    def test_guilt_all_attempts_fail_reports_failed(self, bridge, monkeypatch):
        calls = {"connect": 0, "sleep": []}

        def fake_create_connection(addr, timeout):
            calls["connect"] += 1
            raise OSError("connection refused")

        monkeypatch.setattr(socket, "create_connection", fake_create_connection)
        spec = bridge.TcpProbe(
            organ_id="infra.eventbus_redis_mini",
            host="100.93.236.6",
            port=6379,
            retries=2,
            retry_delay_seconds=0,
        )
        receipt = bridge.build_tcp_receipt(
            spec, now=123, host="Nuzantara", sleep=lambda s: calls["sleep"].append(s)
        )

        assert receipt["status"] == "failed"
        assert calls["connect"] == 3  # 1 initial + 2 retries
        assert calls["sleep"] == [0, 0]  # slept BETWEEN attempts, not before/after
        assert "3 attempts" in receipt["last_error"]
        assert "connection refused" in receipt["last_error"]

    def test_innocence_first_attempt_fails_second_succeeds(self, bridge, monkeypatch):
        attempts = {"n": 0}

        class FakeConn:
            def close(self):
                pass

        def fake_create_connection(addr, timeout):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise OSError("timed out")
            return FakeConn()

        monkeypatch.setattr(socket, "create_connection", fake_create_connection)
        spec = bridge.TcpProbe(
            organ_id="infra.eventbus_redis_mini",
            host="100.93.236.6",
            port=6379,
            retries=2,
            retry_delay_seconds=0,
        )
        receipt = bridge.build_tcp_receipt(
            spec, now=123, host="Nuzantara", sleep=lambda s: None
        )

        assert receipt["status"] == "ok"
        assert "last_error" not in receipt
        assert attempts["n"] == 2  # stopped retrying once it succeeded

    def test_innocence_first_attempt_succeeds_no_retry(self, bridge, monkeypatch):
        calls = {"connect": 0, "sleep": 0}

        class FakeConn:
            def close(self):
                pass

        def fake_create_connection(addr, timeout):
            calls["connect"] += 1
            return FakeConn()

        monkeypatch.setattr(socket, "create_connection", fake_create_connection)
        spec = bridge.TcpProbe(
            organ_id="infra.eventbus_redis_mini", host="100.93.236.6", port=6379
        )
        receipt = bridge.build_tcp_receipt(
            spec,
            now=123,
            host="Nuzantara",
            sleep=lambda s: calls.__setitem__("sleep", calls["sleep"] + 1),
        )

        assert receipt["status"] == "ok"
        assert calls["connect"] == 1
        assert calls["sleep"] == 0

    def test_default_retries_bound_worst_case_wall_clock(self, bridge):
        spec = bridge.TcpProbe(
            organ_id="infra.eventbus_redis_mini", host="100.93.236.6", port=6379
        )
        worst_case_seconds = (spec.retries + 1) * spec.timeout_seconds + (
            spec.retries * spec.retry_delay_seconds
        )
        assert worst_case_seconds <= 15, (
            "a cron wrapper's TCP probe must not become a multi-minute hang risk"
        )
