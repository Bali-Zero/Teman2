"""fleet_watch verdict + state-machine tests (guilt AND innocence)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location(
    "fleet_watch", REPO / "scripts" / "fleet_watch.py"
)
fw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fw)

PEER = [{"name": "pro", "tailscale_host": "nuzantara", "ssh_alias": "pro"}]
NOW = 1_800_000_000.0


class NotifySpy:
    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, tier: str, key: str, text: str) -> str:
        self.calls.append((tier, key, text))
        return "sent"


def run_tick(state, ts, ssh, now=NOW):
    spy = NotifySpy()
    state, probes = fw.tick(
        PEER, state, now,
        ts_check=lambda _h: ts,
        ssh_check=lambda _a: ssh,
        notify=spy,
    )
    return state, probes, spy


# --- innocence: healthy peer never alerts ---------------------------------

def test_online_peer_no_alert_and_probes_counted():
    state, probes, spy = run_tick({}, ts=True, ssh=True)
    assert spy.calls == []
    assert probes == 2
    assert state["pro"]["dark_since"] is None


def test_one_signal_alive_is_still_ok():
    # Tailscale flaps but ssh answers: no dark verdict (family #8 tolerance).
    state, _, spy = run_tick({}, ts=False, ssh=True)
    assert spy.calls == []
    assert state["pro"]["dark_since"] is None


# --- guilt: dark peer alerts once per transition ---------------------------

def test_fresh_dark_below_threshold_no_alert_yet():
    state, _, spy = run_tick({}, ts=False, ssh=False)
    assert spy.calls == []
    assert state["pro"]["dark_since"] == NOW
    assert state["pro"]["alerted"] is False


def test_dark_past_threshold_fires_p0_once():
    state = {"pro": {"dark_since": NOW - 3600, "alerted": False, "last_ok": None}}
    state, _, spy = run_tick(state, ts=False, ssh=False)
    assert [c[0] for c in spy.calls] == ["p0"]
    assert "fleet:pro-dark:" in spy.calls[0][1]
    assert state["pro"]["alerted"] is True

    # second tick while still dark: no repeat (state remembers)
    state, _, spy2 = run_tick(state, ts=False, ssh=False)
    assert spy2.calls == []


def test_recovery_after_alert_sends_digest_and_resets():
    state = {"pro": {"dark_since": NOW - 7200, "alerted": True, "last_ok": None}}
    state, _, spy = run_tick(state, ts=True, ssh=False)
    assert [c[0] for c in spy.calls] == ["digest"]
    assert "recovered" in spy.calls[0][1]
    assert state["pro"]["alerted"] is False
    assert state["pro"]["dark_since"] is None


# --- W84 blind guard --------------------------------------------------------

def test_unprobeable_counts_zero_probes():
    state, probes, spy = run_tick({}, ts=None, ssh=None)
    assert probes == 0
    assert spy.calls == []
    # dark_since must NOT start ticking on blindness
    assert state["pro"]["dark_since"] is None


# --- structured tailscale parse (W82: no substring) -------------------------

def test_check_tailscale_parses_online_bool():
    payload = json.dumps(
        {"Peer": {"k1": {"HostName": "nuzantara", "Online": True}}}
    )

    def fake_run(cmd, timeout):
        return subprocess.CompletedProcess(cmd, 0, stdout=payload, stderr="")

    assert fw.check_tailscale("nuzantara", run=fake_run) is True


def test_check_tailscale_peer_missing_is_offline_not_unknown():
    payload = json.dumps({"Peer": {"k1": {"HostName": "other", "Online": True}}})

    def fake_run(cmd, timeout):
        return subprocess.CompletedProcess(cmd, 0, stdout=payload, stderr="")

    assert fw.check_tailscale("nuzantara", run=fake_run) is False


def test_check_tailscale_cli_missing_is_unknown():
    def fake_run(cmd, timeout):
        raise OSError("no such file")

    assert fw.check_tailscale("nuzantara", run=fake_run) is None


# --- node guard (family #10) ------------------------------------------------

def test_main_exits_0_on_unassigned_node(monkeypatch, tmp_path):
    monkeypatch.setattr(fw.socket, "gethostname", lambda: "some-other-box.local")
    rc = fw.main()
    assert rc == 0
