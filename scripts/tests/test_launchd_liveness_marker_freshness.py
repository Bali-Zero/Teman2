"""TAC-2 A2 (2026-07-05): W84 marker freshness gate.

A failure marker in a log that has not been written for > MARKER_FRESH_SEC is
archaeology: honoring it kept an already-cured (TCC re-granted) job reported
DEAD-* indefinitely, because a cured job never appends to its err-log again and
the stale "Operation not permitted" tail survives forever.

Contract under test (_log_has_failure_marker):
  - marker in a FRESH log  -> returned (live failure, must alarm)
  - marker in a STALE log  -> ignored (cured organ, must clear)
  - stale log NEVER hides a fresh one (per-file gating, not global newest)
"""
from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "launchd_liveness_detector.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("launchd_liveness_detector", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write_log(path: Path, line: str, age_sec: float) -> None:
    path.write_text(line + "\n", encoding="utf-8")
    ts = time.time() - age_sec
    os.utime(path, (ts, ts))


MARKER_LINE = "bash: /Users/x/nuzantara/scripts/lib/heartbeat.sh: Operation not permitted"


def test_fresh_marker_is_reported(tmp_path: Path) -> None:
    mod = _load_module()
    log = tmp_path / "job.err"
    _write_log(log, MARKER_LINE, age_sec=3600)  # 1h old — live failure
    assert mod._log_has_failure_marker([log]) is not None


def test_stale_marker_is_ignored(tmp_path: Path) -> None:
    mod = _load_module()
    log = tmp_path / "job.err"
    _write_log(log, MARKER_LINE, age_sec=mod.MARKER_FRESH_SEC + 3600)  # cured era
    assert mod._log_has_failure_marker([log]) is None


def test_per_file_gating_fresh_log_still_wins(tmp_path: Path) -> None:
    """A stale err-log must not mask a DIFFERENT log with a fresh marker."""
    mod = _load_module()
    stale = tmp_path / "old.err"
    fresh = tmp_path / "new.err"
    _write_log(stale, MARKER_LINE, age_sec=mod.MARKER_FRESH_SEC + 7200)
    _write_log(fresh, MARKER_LINE, age_sec=60)
    assert mod._log_has_failure_marker([stale, fresh]) is not None


def test_env_override_widens_window(tmp_path: Path, monkeypatch) -> None:
    """W84_MARKER_FRESH_SEC is read at import time — a wider window re-honors
    an older marker (operator can tune during an incident post-mortem)."""
    monkeypatch.setenv("W84_MARKER_FRESH_SEC", str(10 * 24 * 3600))
    mod = _load_module()
    log = tmp_path / "job.err"
    _write_log(log, MARKER_LINE, age_sec=5 * 24 * 3600)  # 5d: stale at 48h, fresh at 10d
    assert mod._log_has_failure_marker([log]) is not None
