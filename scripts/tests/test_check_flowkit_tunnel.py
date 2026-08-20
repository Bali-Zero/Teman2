"""Tests for check_flowkit_tunnel — the FlowKit SSH tunnel liveness probe.

Born 2026-08-21: the launchd job com.balizero.flowkit-pro-tunnel existed and
even self-recovered from a multi-day Tailscale flap, but had zero heartbeat,
zero proprioception coverage, zero alert (scar family #2, Esiste!=Armato).
This module gives it a heartbeat sidecar wired into the existing
~/.organism/last_seen/ ecosystem so the NEXT outage is loud, not silent.

Contract (guilt + innocence, per cicatrix-superscar #3 antidote):
  - GUILT: no plist -> NOT_CONFIGURED (never an alarm; M5-only organ).
  - GUILT: plist present but no PID in `launchctl list` -> DOWN.
  - GUILT: PID reported by launchctl but `ps -p <pid>` finds nothing -> DOWN
    (never trust launchctl's word alone -- W104: judge the reply).
  - GUILT: PID alive but the forwarded HTTP port is unreachable -> DOWN.
  - INNOCENCE: PID alive AND the forwarded port answers (even a 404/500 IS a
    live reply through the tunnel) -> LIVE.
  - `launchctl list`'s STATUS column is never consulted at all -- only the
    PID column plus two independent real checks (ps, HTTP).
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from check_flowkit_tunnel import (  # noqa: E402
    DOWN,
    LIVE,
    NOT_CONFIGURED,
    check,
    write_heartbeat,
)


def _cp(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_guilt_not_configured_when_no_plist():
    result = check(plist_exists=lambda: False)
    assert result["status"] == NOT_CONFIGURED
    assert result["healthy"] is True  # not an alarm on a machine that never runs this job


def test_guilt_down_when_no_pid_in_launchctl_list():
    result = check(
        plist_exists=lambda: True,
        launchctl_pid_fn=lambda label: None,
    )
    assert result["status"] == DOWN
    assert result["healthy"] is False
    assert "not running" in result["evidence"]


def test_guilt_down_when_pid_reported_but_process_actually_dead():
    """The exact gotcha this organ exists for: launchctl SAYS a PID, but the
    process is not real. Never trust launchctl's word alone."""
    result = check(
        plist_exists=lambda: True,
        launchctl_pid_fn=lambda label: 99999,
        pid_alive_fn=lambda pid: False,
    )
    assert result["status"] == DOWN
    assert result["healthy"] is False
    assert "99999" in result["evidence"]
    assert "no live process" in result["evidence"]


def test_guilt_down_when_pid_alive_but_port_unreachable():
    result = check(
        plist_exists=lambda: True,
        launchctl_pid_fn=lambda label: 12345,
        pid_alive_fn=lambda pid: True,
        http_probe_fn=lambda url, timeout: (False, "Connection refused"),
    )
    assert result["status"] == DOWN
    assert result["healthy"] is False
    assert "Connection refused" in result["evidence"]


def test_innocence_live_when_pid_alive_and_port_answers():
    result = check(
        plist_exists=lambda: True,
        launchctl_pid_fn=lambda label: 12345,
        pid_alive_fn=lambda pid: True,
        http_probe_fn=lambda url, timeout: (True, "HTTP 404"),
    )
    assert result["status"] == LIVE
    assert result["healthy"] is True
    assert "12345" in result["evidence"]


def test_innocence_live_even_on_http_error_status():
    """A 404/500 through the tunnel IS a live reply -- only a connection-level
    failure (refused/timeout) is DOWN, never an HTTP status code."""
    result = check(
        plist_exists=lambda: True,
        launchctl_pid_fn=lambda label: 12345,
        pid_alive_fn=lambda pid: True,
        http_probe_fn=lambda url, timeout: (True, "HTTP 500"),
    )
    assert result["status"] == LIVE


def test_launchctl_pid_never_reads_the_status_column():
    """The exact live gotcha (2026-08-21): `launchctl list` showed PID 99968
    alongside a STALE status "255" from a prior failed attempt while the
    tunnel was healthy and running for 2h20m. _launchctl_pid must extract
    the PID column only and never even look at column 2."""
    from check_flowkit_tunnel import _launchctl_pid

    stdout = "99968\t255\tcom.balizero.flowkit-pro-tunnel\n69445\t-9\tcom.apple.WorkflowKit.ShortcutsViewService\n"
    pid = _launchctl_pid("com.balizero.flowkit-pro-tunnel", run=lambda cmd: _cp(0, stdout=stdout))
    assert pid == 99968


def test_launchctl_pid_dash_means_not_running():
    stdout = "-\t78\tcom.balizero.flowkit-pro-tunnel\n"
    from check_flowkit_tunnel import _launchctl_pid

    pid = _launchctl_pid("com.balizero.flowkit-pro-tunnel", run=lambda cmd: _cp(0, stdout=stdout))
    assert pid is None


def test_heartbeat_not_written_for_not_configured(tmp_path, monkeypatch):
    import check_flowkit_tunnel as mod

    monkeypatch.setattr(mod, "HEARTBEAT_DIR", tmp_path)
    result = {"organ": "flowkit_tunnel", "status": NOT_CONFIGURED, "healthy": True, "evidence": "no plist"}
    path = write_heartbeat(result, machine="pro")
    assert not path.exists(), "NOT_CONFIGURED must never write a sidecar on a foreign machine"


def test_heartbeat_written_ok_when_live(tmp_path, monkeypatch):
    import check_flowkit_tunnel as mod

    monkeypatch.setattr(mod, "HEARTBEAT_DIR", tmp_path)
    result = {"organ": "flowkit_tunnel", "status": LIVE, "healthy": True, "evidence": "PID 1 alive, HTTP 404"}
    path = write_heartbeat(result, machine="m5")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["status"] == "ok"
    assert data["degraded"] is False
    assert data["organ"] == "m5.flowkit_tunnel"


def test_heartbeat_written_error_when_down(tmp_path, monkeypatch):
    import check_flowkit_tunnel as mod

    monkeypatch.setattr(mod, "HEARTBEAT_DIR", tmp_path)
    result = {"organ": "flowkit_tunnel", "status": DOWN, "healthy": False, "evidence": "unreachable"}
    path = write_heartbeat(result, machine="m5")
    data = json.loads(path.read_text())
    assert data["status"] == "error"
    assert data["degraded"] is True


def test_heartbeat_feeds_organism_stale_detector_as_unhealthy_when_down(tmp_path, monkeypatch):
    """End-to-end wiring proof: a DOWN heartbeat, once written, is picked up
    by organism_stale_detector.scan_sidecars_status as unhealthy -- this is
    what makes the next outage loud instead of silent."""
    import check_flowkit_tunnel as mod

    monkeypatch.setattr(mod, "HEARTBEAT_DIR", tmp_path)
    result = {"organ": "flowkit_tunnel", "status": DOWN, "healthy": False, "evidence": "unreachable"}
    write_heartbeat(result, machine="m5")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from organism_stale_detector import scan_sidecars_status

    findings = scan_sidecars_status(str(tmp_path), now=time.time(), host="air-m5")
    assert len(findings) == 1
    assert findings[0].organ_id == "m5.flowkit_tunnel"
    assert findings[0].kind == "unhealthy"
