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


# --- peers config tripwire: the watch is MUTUAL (2026-08-14) ----------------
# Genesis: Mini dark 2026-08-10→12 (its own application firewall) with zero
# alarms — only mini-pro2 watched pro, nobody watched mini. This pins the
# real config so a future edit cannot silently drop one direction.

def test_real_peers_config_watch_is_mutual():
    peers = json.loads(
        (REPO / "infra" / "fleet-watch" / "peers.json").read_text()
    )
    mini_watches = {p["name"] for p in peers.get("mini-pro2", [])}
    pro_watches = {p["name"] for p in peers.get("nuzantara", [])}
    assert "pro" in mini_watches, "mini-pro2 no longer watches pro"
    assert "mini" in pro_watches, "nuzantara (Pro) no longer watches mini"
    (mini_entry,) = [p for p in peers["nuzantara"] if p["name"] == "mini"]
    assert mini_entry["tailscale_host"] == "mini-pro2"
    assert mini_entry["ssh_alias"] == "mini"


# --- re-escalation ladder (2026-08-17) --------------------------------------
# Genesis: the Mini was dark 2026-08-14 18:16 → 2026-08-17 12:27 (Internet
# Sharing had claimed its Wi-Fi card, so it could never associate). fleet_watch
# did its job at minute 30 — "mini DARK 30m -> p0 (sent)" — and then logged
# "mini dark 236762s" for ~65 hours without another word, because one bool
# said "already alerted". Guilt below is that exact silence.

H = 3600.0


def dark_state(seconds_dark, **over):
    entry = {"dark_since": NOW - seconds_dark, "alerted": True,
             "alert_stage": 1, "last_ok": None}
    entry.update(over)
    return {"pro": entry}


def test_no_repeat_between_rungs_is_still_quiet():
    # innocence: 90 minutes dark, first alert already out → nothing new.
    state, _, spy = run_tick(dark_state(1.5 * H), ts=False, ssh=False)
    assert spy.calls == []
    assert state["pro"]["alert_stage"] == 1


def test_re_escalates_at_six_hours():
    state, _, spy = run_tick(dark_state(6 * H), ts=False, ssh=False)
    assert [c[0] for c in spy.calls] == ["p0"]
    assert "STILL DARK" in spy.calls[0][2]
    assert state["pro"]["alert_stage"] == 2
    # and then goes quiet again until the next rung
    _, _, spy2 = run_tick(state, ts=False, ssh=False)
    assert spy2.calls == []


def test_re_escalates_at_24h_then_daily():
    assert fw.due_alert_stage(24 * H) == 3
    assert fw.due_alert_stage(48 * H) == 4
    assert fw.due_alert_stage(72 * H) == 5


def test_the_65h_silence_cannot_happen_again():
    """The literal scar: 236762s dark after one alert must NOT be silent."""
    state, _, spy = run_tick(dark_state(236762), ts=False, ssh=False)
    assert spy.calls, "65h of dark produced no alarm — W107/W116 all over again"
    assert spy.calls[0][0] == "p0"


def test_skipped_rungs_collapse_to_one_message():
    # The watcher itself was down across several rungs: stage jumps 1 -> 5,
    # and that must be ONE message, not a burst of four.
    state, _, spy = run_tick(dark_state(72 * H), ts=False, ssh=False)
    assert len(spy.calls) == 1
    assert state["pro"]["alert_stage"] == 5


def test_dedup_key_is_per_stage():
    # The gateway dedups on this key for 6h; a constant key would swallow
    # every re-alert and the ladder would be decorative.
    s1, _, spy1 = run_tick(dark_state(1 * H, alert_stage=0, alerted=False),
                           ts=False, ssh=False)
    s2, _, spy2 = run_tick(dark_state(6 * H), ts=False, ssh=False)
    assert spy1.calls[0][1] != spy2.calls[0][1]
    assert spy1.calls[0][1].endswith(":s1")
    assert spy2.calls[0][1].endswith(":s2")


def test_legacy_state_without_alert_stage_still_escalates():
    # State files written before this change carry only `alerted: True`.
    legacy = {"pro": {"dark_since": NOW - 6 * H, "alerted": True,
                      "last_ok": None}}
    state, _, spy = run_tick(legacy, ts=False, ssh=False)
    assert [c[0] for c in spy.calls] == ["p0"]
    assert state["pro"]["alert_stage"] == 2


def test_legacy_state_is_not_re_alerted_from_scratch():
    """Innocence twin of the test above — and the one with teeth.

    Reading `alerted: True` as stage 0 would re-send the TRANSITION alert to
    every peer already dark when this ships. The escalation test cannot see
    that (a p0 fires either way); only silence below the next rung can.
    """
    legacy = {"pro": {"dark_since": NOW - 1.5 * H, "alerted": True,
                      "last_ok": None}}
    _, _, spy = run_tick(legacy, ts=False, ssh=False)
    assert spy.calls == [], "legacy state replayed the first alert"


def test_recovery_from_a_re_escalated_dark_still_resets():
    state, _, spy = run_tick(dark_state(30 * H, alert_stage=4),
                             ts=True, ssh=True)
    assert [c[0] for c in spy.calls] == ["digest"]
    assert state["pro"]["alert_stage"] == 0
    assert state["pro"]["dark_since"] is None


def test_below_threshold_is_stage_zero():
    assert fw.due_alert_stage(0) == 0
    assert fw.due_alert_stage(fw.DARK_AFTER_S - 1) == 0
    assert fw.due_alert_stage(fw.DARK_AFTER_S) == 1
