"""Tests for launchagent-state-bridge's profile-monitor TCP probe (2026-09-27).

Follow-up to PR #7436 (fix(profile-monitor): bind the checkout wrapper to the
tailnet, not 0.0.0.0). That PR's gate left a superscar #2 (Esiste≠Armato) gap
open: BRIDGED_LABELS' `pro.profile_monitor_wrapper` entry only reads
launchctl's PID column, so a wrapper stuck retrying an EADDRNOTAVAIL bind
(process alive, port never opened — see wrapper.py's `_serve_with_bind_retry`)
still reports "ok". A dead-in-the-water process with a healthy-looking PID
was exactly proprioception's organs_heartbeat blind spot the whole 10-family
cicatrix doctrine names #2 for.

Fix under test: a new `TcpProbe(organ_id="pro.profile_monitor_wrapper",
host="100.107.22.111", port=9099)` in BRIDGED_TCP_PROBES, deliberately sharing
the SAME organ_id as the BridgedLaunchAgent entry. `write_receipts()` runs
BRIDGED_LABELS first and BRIDGED_TCP_PROBES second against the same
`last_seen/<organ_id>.json` path, so whichever check runs last decides the
receipt that lands. This test drives `write_receipts()` end to end (not the
two probes in isolation, which scripts/tests/test_launchagent_state_bridge_tcp_retry.py
already covers) with a live PID and a closed port.

Contract (guilt + innocence):
  - GUILT: launchctl reports a live PID for com.balizero.profile-monitor-wrapper
    AND the TCP probe cannot connect -> the FINAL written receipt for
    pro.profile_monitor_wrapper.json is status="failed", not "ok".
  - INNOCENCE: same live PID, TCP probe connects -> status="ok" (the fix does
    not turn a genuinely healthy wrapper red).
  - INNOCENCE: no PID at all (label not loaded) -> status="failed" regardless
    of the TCP probe (already true before this change; pinned so the ordering
    doesn't accidentally flip it to "ok").

The module name is loaded via importlib (hyphenated filename), mirroring
test_launchagent_state_bridge_host_guard.py / _tcp_retry.py / _ollama_label.py.
"""
from __future__ import annotations

import importlib.util
import os
import socket
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

LABEL = "com.balizero.profile-monitor-wrapper"
ORGAN_ID = "pro.profile_monitor_wrapper"
EXPECTED_HOST = "100.107.22.111"
EXPECTED_PORT = 9099


@pytest.fixture()
def bridge(monkeypatch):
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    spec = importlib.util.spec_from_file_location(
        "launchagent_state_bridge_profile_monitor_tcp",
        os.path.join(_SCRIPTS_DIR, "launchagent-state-bridge.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # dataclasses + `from __future__ import annotations` resolves string
    # annotations via sys.modules[cls.__module__] — the module must be
    # registered there before exec_module() runs the class bodies.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    # Keep the guilt/innocence cases fast: TcpProbe's default retry_delay
    # (1.0s x 2 retries) would otherwise cost ~2s of real sleep per failing
    # case for no signal this test cares about.
    monkeypatch.setattr(mod.time, "sleep", lambda _seconds: None)
    return mod


class TestProbeDeclared:
    def test_tcp_probe_entry_exists(self, bridge):
        matches = [p for p in bridge.BRIDGED_TCP_PROBES if p.organ_id == ORGAN_ID]
        assert len(matches) == 1, (
            f"expected exactly one BRIDGED_TCP_PROBES entry for {ORGAN_ID!r}, "
            f"found {len(matches)}"
        )

    def test_tcp_probe_targets_pro_tailscale_ip_and_9099(self, bridge):
        entry = next(p for p in bridge.BRIDGED_TCP_PROBES if p.organ_id == ORGAN_ID)
        assert entry.host == EXPECTED_HOST
        assert entry.port == EXPECTED_PORT

    def test_daemon_entry_still_present_and_shares_the_organ_id(self, bridge):
        """The fix layers ON TOP of the existing PID check, it does not
        replace it — losing this entry would silently drop process-liveness
        coverage (a crashed process with a somehow-still-open port would
        then read "ok")."""
        matches = [e for e in bridge.BRIDGED_LABELS if e.organ_id == ORGAN_ID]
        assert len(matches) == 1
        assert matches[0].label == LABEL


class TestWriteReceiptsCombinedVerdict:
    def _launchctl_agents_with_live_pid(self) -> dict:
        return {LABEL: {"pid": 998, "exit_code": 0}}

    def test_guilt_live_pid_closed_port_is_not_green(self, bridge, tmp_path, monkeypatch):
        def refuse_connect(addr, timeout):
            raise OSError("connection refused")

        monkeypatch.setattr(socket, "create_connection", refuse_connect)

        receipts = bridge.write_receipts(
            self._launchctl_agents_with_live_pid(),
            last_seen_dir=tmp_path / "last_seen",
            legacy_state_dir=None,
            host="Nuzantara",
        )

        organ_receipts = [r for r in receipts if r["organ_id"] == ORGAN_ID]
        # Both the daemon check and the TCP probe wrote a receipt for this
        # organ_id; the TCP probe's runs second and its file write is what
        # actually lands on disk.
        assert len(organ_receipts) == 2
        on_disk = json_load(tmp_path / "last_seen" / f"{ORGAN_ID}.json")
        assert on_disk["status"] == "failed", (
            "a live PID with a closed port must not read as ok — this is "
            "exactly the EADDRNOTAVAIL-retry-loop blind spot this probe "
            "exists to close"
        )

    def test_innocence_live_pid_open_port_is_ok(self, bridge, tmp_path, monkeypatch):
        class FakeConn:
            def close(self):
                pass

        def accept_connect(addr, timeout):
            return FakeConn()

        monkeypatch.setattr(socket, "create_connection", accept_connect)

        bridge.write_receipts(
            self._launchctl_agents_with_live_pid(),
            last_seen_dir=tmp_path / "last_seen",
            legacy_state_dir=None,
            host="Nuzantara",
        )

        on_disk = json_load(tmp_path / "last_seen" / f"{ORGAN_ID}.json")
        assert on_disk["status"] == "ok"

    def test_no_pid_but_something_answers_9099_the_tcp_probe_still_wins(
        self, bridge, tmp_path, monkeypatch
    ):
        """Documents a KNOWN, accepted trade-off of the last-write-wins
        design, not a requirement: the daemon check alone would write
        "failed" ("label not loaded") for a dead process, but the TCP probe
        runs after it and overwrites with its own verdict regardless of PID
        state. In practice nothing else legitimately binds Pro's 9099, so a
        successful connect here would itself mean the checkout endpoint is
        reachable — arguably still "ok" for downstream consumers. This test
        pins that this is the CURRENT, deliberate behavior so a future
        reordering of the two loops in write_receipts() changes it on
        purpose, not silently.
        """
        class FakeConn:
            def close(self):
                pass

        monkeypatch.setattr(socket, "create_connection", lambda addr, timeout: FakeConn())

        bridge.write_receipts(
            {},  # label not in launchctl output at all
            last_seen_dir=tmp_path / "last_seen",
            legacy_state_dir=None,
            host="Nuzantara",
        )

        on_disk = json_load(tmp_path / "last_seen" / f"{ORGAN_ID}.json")
        assert on_disk["status"] == "ok"


def json_load(path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))
