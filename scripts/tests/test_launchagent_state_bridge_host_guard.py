"""Tests for launchagent-state-bridge's host-residency guard (2026-07-10).

Root cause this pins shut: BRIDGED_LABELS is a fixed list of ~90 Pro-only
launchd job labels (com.balizero.*, com.nuzantara.*, homebrew.mxcl.*). An
ad-hoc `--json` diagnostic run on Mini (2026-07-09 21:27, evidence
/tmp/launchagent-state-bridge-mini.{json,err}) executed happily off-host:
`launchctl list` succeeded locally, every Pro-only label was legitimately
absent there, and build_receipt() wrote "label not loaded" -> status=failed
for all ~90 of them into ~/.organism/last_seen/ — surfaced the next session
by proprioception's organs_heartbeat probe as a 78-organ P1 false alarm.

Contract (guilt + innocence, per cicatrix-superscar #2/#10 antidote):
  - GUILT: running off the resident host writes NO receipts (main() no-ops,
    exit 0 — a diagnostic mistake must not corrupt state, but also must not
    look like a hard failure to a caller).
  - INNOCENCE: running ON the resident host, or with --allow-off-host,
    writes receipts exactly as before the guard existed.
  - running_on_resident_host() is case-insensitive and considers only the
    first dot-separated label (handles "Nuzantara.local" style nodenames),
    mirroring organism_stale_detector.py's _core_organs_expected_here().

The module name is loaded via importlib (hyphenated filename), mirroring
test_dlq_corpse_sweep_organism.py.
"""
import importlib.util
import os
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def bridge():
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    spec = importlib.util.spec_from_file_location(
        "launchagent_state_bridge_host_guard",
        os.path.join(_SCRIPTS_DIR, "launchagent-state-bridge.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # dataclasses + `from __future__ import annotations` resolves string
    # annotations via sys.modules[cls.__module__] — the module must be
    # registered there before exec_module() runs the class bodies.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestRunningOnResidentHost:
    def test_exact_match(self, bridge):
        assert bridge.running_on_resident_host("nuzantara") is True

    def test_case_insensitive(self, bridge):
        assert bridge.running_on_resident_host("Nuzantara") is True

    def test_first_label_only(self, bridge):
        """A hostname with a domain suffix still matches on the first label."""
        assert bridge.running_on_resident_host("Nuzantara.local") is True

    def test_mini_is_not_resident(self, bridge):
        assert bridge.running_on_resident_host("mini-pro2") is False

    def test_air_m5_is_not_resident(self, bridge):
        assert bridge.running_on_resident_host("Air-M5") is False


class TestMainHostGuard:
    """main() must not touch launchctl or ~/.organism/last_seen/ off-host."""

    def test_off_host_writes_no_receipts(self, bridge, tmp_path, monkeypatch):
        monkeypatch.setattr(bridge, "running_on_resident_host", lambda *_: False)
        launchctl_file = tmp_path / "launchctl.txt"
        launchctl_file.write_text("1234\t0\tcom.balizero.qdrant.daemon\n")
        last_seen = tmp_path / "last_seen"

        rc = bridge.main([
            "--launchctl-file", str(launchctl_file),
            "--last-seen-dir", str(last_seen),
            "--no-legacy",
        ])

        assert rc == 0
        assert not last_seen.exists() or list(last_seen.iterdir()) == []

    def test_on_host_writes_receipts(self, bridge, tmp_path, monkeypatch):
        monkeypatch.setattr(bridge, "running_on_resident_host", lambda *_: True)
        monkeypatch.setattr(bridge, "BRIDGED_TCP_PROBES", ())  # no real network I/O
        launchctl_file = tmp_path / "launchctl.txt"
        launchctl_file.write_text("1234\t0\tcom.balizero.qdrant.daemon\n")
        last_seen = tmp_path / "last_seen"

        rc = bridge.main([
            "--launchctl-file", str(launchctl_file),
            "--last-seen-dir", str(last_seen),
            "--no-legacy",
        ])

        assert rc == 0
        written = {p.name for p in last_seen.iterdir()}
        assert "infra.qdrant_pro.json" in written

    def test_allow_off_host_overrides_guard(self, bridge, tmp_path, monkeypatch):
        monkeypatch.setattr(bridge, "running_on_resident_host", lambda *_: False)
        monkeypatch.setattr(bridge, "BRIDGED_TCP_PROBES", ())  # no real network I/O
        launchctl_file = tmp_path / "launchctl.txt"
        launchctl_file.write_text("1234\t0\tcom.balizero.qdrant.daemon\n")
        last_seen = tmp_path / "last_seen"

        rc = bridge.main([
            "--launchctl-file", str(launchctl_file),
            "--last-seen-dir", str(last_seen),
            "--no-legacy",
            "--allow-off-host",
        ])

        assert rc == 0
        written = {p.name for p in last_seen.iterdir()}
        assert "infra.qdrant_pro.json" in written


class TestPostPublishPollerDaemonReceipt:
    """post-publish-poller must be bridged by pid-liveness, not exit code.

    2026-07-18: with daemon=False the receipt read launchctl's sticky
    "last exit code" column (=1 after any past restart) and reported
    status=failed while ps proved the poller alive and opening PRs.
    Guilt+innocence per cicatrix family #3.
    """

    def _spec(self, bridge):
        specs = [s for s in bridge.BRIDGED_LABELS
                 if s.label == "com.balizero.post-publish-poller"]
        assert len(specs) == 1
        return specs[0]

    def test_flag_is_daemon(self, bridge):
        assert self._spec(bridge).daemon is True

    def test_alive_with_sticky_exit_is_ok(self, bridge):
        """Innocence: live pid + stale exit 1 → ok (the 2026-07-18 case)."""
        spec = self._spec(bridge)
        receipt = bridge.build_receipt(
            spec,
            {spec.label: {"pid": 61606, "exit_code": 1}},
            now=1_700_000_000,
            host="pro",
        )
        assert receipt["status"] == "ok"

    def test_dead_daemon_is_failed(self, bridge):
        """Guilt: no pid → failed, even with exit_code 0."""
        spec = self._spec(bridge)
        receipt = bridge.build_receipt(
            spec,
            {spec.label: {"pid": None, "exit_code": 0}},
            now=1_700_000_000,
            host="pro",
        )
        assert receipt["status"] == "failed"
