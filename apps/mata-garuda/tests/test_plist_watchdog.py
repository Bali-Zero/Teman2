"""Tests for the mata_garuda plist auto-heal watchdog (solo-assenza boundary).

Verifies the SAFE boundary the operator approved: heal only vanished jobs,
never touch a loaded-but-diverged one (could be an operator edit), never
storm (circuit breaker).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mata_garuda.workers import plist_watchdog as pw


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated dirs + a fake launchctl. Returns handles to drive scenarios."""
    la = tmp_path / "LaunchAgents"
    snap = tmp_path / "snapshot"
    org = tmp_path / "organism"
    la.mkdir(); snap.mkdir(); org.mkdir()
    monkeypatch.setattr(pw, "LA_DIR", la)
    monkeypatch.setattr(pw, "SNAPSHOT_DIR", snap)
    monkeypatch.setattr(pw, "LEDGER", org / "heal.ledger.json")
    # heartbeat dir under this org too
    monkeypatch.setattr(pw.Path, "home", classmethod(lambda cls: tmp_path))

    known: set[str] = set()
    bootstrapped: list[str] = []
    monkeypatch.setattr(pw, "_launchctl_knows", lambda label: label in known)

    def fake_heal(label, snapshot):
        # simulate a successful reinstall: copy file + mark known
        (la / snapshot.name).write_bytes(snapshot.read_bytes())
        known.add(label)
        bootstrapped.append(label)
        return True, "reinstalled+bootstrapped"
    monkeypatch.setattr(pw, "_heal", fake_heal)

    def add_snapshot(name: str, content: bytes = b"<plist>x</plist>"):
        (snap / f"com.matagaruda.{name}.plist").write_bytes(content)

    def make_live(name: str, content: bytes = b"<plist>x</plist>", known_too=True):
        (la / f"com.matagaruda.{name}.plist").write_bytes(content)
        if known_too:
            known.add(f"com.matagaruda.{name}")

    return type("Env", (), dict(
        la=la, snap=snap, known=known, bootstrapped=bootstrapped,
        add_snapshot=staticmethod(add_snapshot), make_live=staticmethod(make_live),
    ))


def test_present_and_known_is_noop(env):
    """A job that exists on disk AND launchctl knows → NOT healed."""
    env.add_snapshot("alpha")
    env.make_live("alpha")            # present + known
    assert pw.main() == 0
    assert env.bootstrapped == []      # nothing reinstalled


def test_vanished_is_healed(env):
    """Snapshot exists but job absent from disk → reinstalled + bootstrapped."""
    env.add_snapshot("beta")           # no live file → vanished
    assert pw.main() == 0
    assert "com.matagaruda.beta" in env.bootstrapped
    assert (env.la / "com.matagaruda.beta.plist").exists()


def test_present_but_unknown_is_healed(env):
    """On disk but launchctl doesn't know it (dropped by reboot) → healed."""
    env.add_snapshot("gamma")
    env.make_live("gamma", known_too=False)   # present, NOT known
    assert pw.main() == 0
    assert "com.matagaruda.gamma" in env.bootstrapped


def test_diverged_is_report_only_never_touched(env):
    """Loaded+known but live content != snapshot → REPORTED, file NOT overwritten."""
    env.add_snapshot("delta", content=b"<plist>SNAPSHOT</plist>")
    env.make_live("delta", content=b"<plist>OPERATOR-EDIT</plist>")  # present+known+diverged
    assert pw.main() == 0
    assert env.bootstrapped == []      # never healed
    # the operator's live content is preserved untouched
    assert (env.la / "com.matagaruda.delta.plist").read_bytes() == b"<plist>OPERATOR-EDIT</plist>"


def test_circuit_breaker_stops_storm(env, monkeypatch):
    """A label that keeps vanishing is healed at most MAX_HEALS_PER_WINDOW times."""
    monkeypatch.setattr(pw, "MAX_HEALS_PER_WINDOW", 3)
    env.add_snapshot("epsilon")
    # each run: remove live + forget known so it looks vanished again
    for i in range(5):
        (env.la / "com.matagaruda.epsilon.plist").unlink(missing_ok=True)
        env.known.discard("com.matagaruda.epsilon")
        pw.main()
    # healed at most 3 times despite 5 vanish cycles
    heals = env.bootstrapped.count("com.matagaruda.epsilon")
    assert heals == 3, f"expected 3 heals (breaker), got {heals}"


def test_ledger_persisted(env):
    env.add_snapshot("zeta")
    pw.main()
    led = json.loads((pw.LEDGER).read_text())
    assert "com.matagaruda.zeta" in led
    assert len(led["com.matagaruda.zeta"]) == 1


# ── host-pins (cicatrix family #10 — active-active split-brain) ────────────


def _write_pins(pw, snap_dir: Path, pins: dict) -> None:
    (snap_dir / "host-pins.json").write_text(json.dumps(pins))


def test_pinned_label_wrong_host_is_skipped_not_healed(env, monkeypatch):
    """Label pinned to mini-pro2, this host is 'Nuzantara' → NOT healed,
    report contains SKIP with the pin + this-host detail."""
    _write_pins(pw, env.snap, {"com.matagaruda.kg-query-api": ["mini-pro2"]})
    monkeypatch.setattr(pw.socket, "gethostname", lambda: "Nuzantara")
    env.add_snapshot("kg-query-api")   # vanished (no live file) → would-be heal
    assert pw.main() == 0
    assert env.bootstrapped == []
    assert "com.matagaruda.kg-query-api" not in [
        h.split(":")[0] for h in env.bootstrapped
    ]


def test_pinned_label_wrong_host_report_contains_skip(env, monkeypatch, capsys):
    _write_pins(pw, env.snap, {"com.matagaruda.kg-query-api": ["mini-pro2"]})
    monkeypatch.setattr(pw.socket, "gethostname", lambda: "Nuzantara")
    env.add_snapshot("kg-query-api")
    pw.main()
    out = capsys.readouterr().out
    assert "SKIP com.matagaruda.kg-query-api" in out
    assert "mini-pro2" in out
    assert "nuzantara" in out  # normalized current host


def test_pinned_label_matching_host_heals_normally(env, monkeypatch):
    """Label pinned to mini-pro2, this host normalizes to 'mini-pro2'
    (from 'Mini-Pro2.local') → heals normally."""
    _write_pins(pw, env.snap, {"com.matagaruda.kg-query-api": ["mini-pro2"]})
    monkeypatch.setattr(pw.socket, "gethostname", lambda: "Mini-Pro2.local")
    env.add_snapshot("kg-query-api")
    assert pw.main() == 0
    assert "com.matagaruda.kg-query-api" in env.bootstrapped


def test_unpinned_label_heals_as_today(env, monkeypatch):
    """A label absent from host-pins.json heals exactly like before pinning."""
    _write_pins(pw, env.snap, {"com.matagaruda.kg-query-api": ["mini-pro2"]})
    monkeypatch.setattr(pw.socket, "gethostname", lambda: "Nuzantara")
    env.add_snapshot("some-other-job")   # NOT in the pins file
    assert pw.main() == 0
    assert "com.matagaruda.some-other-job" in env.bootstrapped


def test_missing_host_pins_file_heals_as_today(env, monkeypatch, capsys):
    """No host-pins.json at all (SNAPSHOT_DIR/host-pins.json absent) → fail-open,
    behavior identical to pre-pin (heals), plus a report line."""
    assert not (env.snap / "host-pins.json").exists()
    monkeypatch.setattr(pw.socket, "gethostname", lambda: "Nuzantara")
    env.add_snapshot("kg-query-api")
    assert pw.main() == 0
    assert "com.matagaruda.kg-query-api" in env.bootstrapped
    out = capsys.readouterr().out
    assert "host-pins: unreadable" in out


def test_malformed_host_pins_file_fails_open(env, monkeypatch, capsys):
    """host-pins.json exists but is not valid JSON → fail-open, same as missing."""
    (env.snap / "host-pins.json").write_text("{not valid json,,,")
    monkeypatch.setattr(pw.socket, "gethostname", lambda: "Nuzantara")
    env.add_snapshot("kg-query-api")
    assert pw.main() == 0
    assert "com.matagaruda.kg-query-api" in env.bootstrapped
    out = capsys.readouterr().out
    assert "host-pins: unreadable" in out
