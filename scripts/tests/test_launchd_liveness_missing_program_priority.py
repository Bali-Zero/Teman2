"""Healer tick 2026-07-18: `_classify()` branch ORDER bug — `not prog_exists`
was checked AFTER the `exit_code not in (0, None)` branch, so a job whose
program is MISSING and whose LastExitStatus is also non-zero (launchd can't
posix_spawn a path that doesn't exist) was misclassified FAILING-HONESTLY
instead of ARMED-TO-NOTHING.

Real finding the same day: `com.matagaruda.kg-query-api`, `last_exit=78`
(posix_spawn fail), `program=/Users/nuzantara/scripts/mini-infra/kg-query-api-
wrapper.sh` — INESISTENTE on Pro. Detector's JSON that day:
`{"verdict": "FAILING-HONESTLY", "program_exists": false}` — a missing
program IS the root cause of the non-zero exit, and ARMED-TO-NOTHING is
strictly more informative (it names the actual defect) than the generic
"non-zero, no marker, no recovery proof" catch-all.

Contract under test (_classify): `not prog_exists` is now evaluated BEFORE
the exit_code triage branch.
  - guilt: prog_exists=False + non-zero exit (no marker) -> ARMED-TO-NOTHING
    (was FAILING-HONESTLY before the fix)
  - innocence 1: prog_exists=True + non-zero exit + no marker + short
    uptime -> stays FAILING-HONESTLY (unaffected — the program DOES exist,
    ARMED-TO-NOTHING must not fire)
  - innocence 2: prog_exists=False + exit 0/None -> stays ARMED-TO-NOTHING
    (the pre-fix behavior for this shape, unchanged by the reorder)
  - innocence 3: a launch-failure marker still outranks the reorder — a
    proven DEAD-GREEN/DEAD-NONZERO shape is untouched even when the program
    is also missing (marker checks stay ABOVE the moved prog_exists check)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "launchd_liveness_detector.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("launchd_liveness_detector", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_missing_program_wins_over_nonzero_exit_no_marker():
    """Guilt: the real kg-query-api shape (last_exit=78, program missing,
    no failure marker in the log) must classify ARMED-TO-NOTHING, not
    FAILING-HONESTLY."""
    mod = _load_module()
    verdict = mod._classify(
        status={"LastExitStatus": 78, "PID": None},
        marker=None, prog_exists=False,
        uptime_sec=None,
    )
    assert verdict == "ARMED-TO-NOTHING"


def test_missing_program_wins_even_with_a_live_pid_and_long_uptime():
    """Guilt (2nd shape): a missing program must win even when a PID/uptime
    combo would otherwise have qualified for RECOVERED — ARMED-TO-NOTHING
    is evaluated first now, RECOVERED never gets a chance to fire."""
    mod = _load_module()
    verdict = mod._classify(
        status={"LastExitStatus": 78, "PID": 12345},
        marker=None, prog_exists=False,
        uptime_sec=999999,
    )
    assert verdict == "ARMED-TO-NOTHING"


def test_existing_program_with_nonzero_exit_stays_failing_honestly():
    """Innocence: when the program DOES exist, a non-zero exit with no
    marker and short uptime is unaffected by the reorder."""
    mod = _load_module()
    verdict = mod._classify(
        status={"LastExitStatus": 78, "PID": 12345},
        marker=None, prog_exists=True,
        uptime_sec=60,
    )
    assert verdict == "FAILING-HONESTLY"


def test_missing_program_with_clean_exit_still_armed_to_nothing():
    """Innocence: exit_code in (0, None) + missing program was ALREADY
    ARMED-TO-NOTHING before this fix — the reorder must not change this
    shape's outcome, only how it's reached."""
    mod = _load_module()
    assert mod._classify(
        status={"LastExitStatus": 0, "PID": 12345},
        marker=None, prog_exists=False,
        uptime_sec=10,
    ) == "ARMED-TO-NOTHING"
    assert mod._classify(
        status={"LastExitStatus": None, "PID": None},
        marker=None, prog_exists=False,
        uptime_sec=None,
    ) == "ARMED-TO-NOTHING"


def test_marker_still_outranks_missing_program():
    """Innocence: a proven launch-failure marker (DEAD-GREEN/DEAD-NONZERO)
    stays on top of the branch order even when the program is ALSO missing
    — the marker checks were not moved."""
    mod = _load_module()
    assert mod._classify(
        status={"LastExitStatus": 0, "PID": 12345},
        marker="bash: /x/y: Operation not permitted", prog_exists=False,
        uptime_sec=999999,
    ) == "DEAD-GREEN"
    assert mod._classify(
        status={"LastExitStatus": 1, "PID": 12345},
        marker="bash: /x/y: Operation not permitted", prog_exists=False,
        uptime_sec=999999,
    ) == "DEAD-NONZERO"
