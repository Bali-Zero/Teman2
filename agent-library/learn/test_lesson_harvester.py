#!/usr/bin/env python3
"""test_lesson_harvester.py — falsifiable gate tests for the P7 shadow harvester.

The harvester is the SAFE half of the LEARN loop: it generates PROPOSALS only,
never applies. These tests pin the four gates the slice promises:

  G1 — objective anchor: a lesson without a verifiable external event (commit /
       PR / run / test / exit) is REJECTED, not trained on.
  G2 — proposal ≠ application: the report structurally declares zero enforcement;
       there is no code path that activates a rule.
  G3 — reversibility / kill-switch: LESSON_HARVESTER_OFF=1 → no-op.
  G4 — recurrence threshold: a pattern under 3 distinct occurrences stays
       consultive (never becomes a mechanical/hook candidate).

Plus: idempotence of the shadow report (--check), determinism, and that the
checked-in proposals artifact is in sync.

Run: PYTHONPATH=agent-library/learn pytest agent-library/learn/test_lesson_harvester.py -q
(stdlib + pytest only; no network, no PII, no DB, no LLM).
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

import lesson_harvester as h

REPO_ROOT = h.REPO_ROOT
SCRIPT = REPO_ROOT / "agent-library" / "learn" / "lesson_harvester.py"


# --------------------------------------------------------------- G1 anchor --
def test_g1_commit_sha_is_anchor():
    s = h.Scar("x", "**Reference**: commit 6206f0cf4 fixed it.")
    assert s.has_anchor is True


def test_g1_pr_number_is_anchor():
    s = h.Scar("x", "shipped in PR #1018, merged clean.")
    assert s.has_anchor is True


def test_g1_ci_run_is_anchor():
    s = h.Scar("x", "CI run 26915762002 job 79404910575 failed.")
    assert s.has_anchor is True


def test_g1_failing_test_is_anchor():
    s = h.Scar("x", "test_performance_monitor.py:311 asserted 2 == 1.")
    assert s.has_anchor is True


def test_g1_prose_only_is_not_anchor():
    s = h.Scar("x", "**Reference**: discovered during a vibe check, no event cited.")
    assert s.has_anchor is False


def test_g1_unanchored_scar_is_rejected():
    scars = [h.Scar("only-prose", "a feeling that something is off")]
    rep = h.harvest(scars)
    assert rep["totals"]["rejected_no_anchor"] == 1
    assert rep["totals"]["mechanical_candidates"] == 0


# ----------------------------------------------------------- G4 recurrence --
def test_g4_three_distinct_scars_is_recurring():
    scars = [
        h.Scar("a W99", "PR #1 ... W99"),
        h.Scar("b W99", "run 123456 ... W99"),
        h.Scar("c W99", "commit abcdef0 ... W99"),
    ]
    rep = h.harvest(scars)
    assert rep["recurring_patterns"]["w_numbers"].get("W99") == 3
    assert rep["totals"]["mechanical_candidates"] == 3


def test_g4_two_occurrences_is_not_recurring():
    scars = [
        h.Scar("a W88", "PR #1 ... W88"),
        h.Scar("b W88", "run 222222 ... W88"),
    ]
    rep = h.harvest(scars)
    assert "W88" not in rep["recurring_patterns"]["w_numbers"]
    assert rep["totals"]["mechanical_candidates"] == 0
    assert rep["totals"]["consultive"] == 2


def test_g4_single_occurrence_routes_consultive():
    scars = [h.Scar("lone W11", "PR #2 ... W11")]
    rep = h.harvest(scars)
    titles = {r["title"] for r in rep["mechanical_candidates"]}
    assert "lone W11" not in titles
    assert any(r["title"] == "lone W11" for r in rep["consultive"])


# --------------------------------------------------------- G2 no-enforce --
def test_g2_report_declares_zero_enforcement():
    rep = h.build_report()
    assert rep["_enforcement"] == "none"
    assert rep["_mode"] == "shadow"


def test_g2_no_enforcement_sinks_in_source():
    """Structural guard: proposal ≠ application is enforced BY CONSTRUCTION.
    The harvester's only file-write targets must be its own proposal artifacts
    (OUT_JSON / OUT_MD), and it must spawn no subprocess that could mutate state.
    (We check write SINKS, not prose: the docstring legitimately *describes* the
    no-enforcement guarantee, so a substring match on 'settings.json' would be a
    false positive — the real invariant is where writes actually go.)"""
    import re as _re

    src = SCRIPT.read_text(encoding="utf-8")

    # Every `<x>.write_text(` call must target OUT_JSON or OUT_MD — nothing else.
    write_targets = set(_re.findall(r"(\w+)\.write_text\(", src))
    allowed = {"OUT_JSON", "OUT_MD"}
    assert write_targets <= allowed, (
        f"unexpected write sink(s): {write_targets - allowed}"
    )

    # No state-mutating spawn: the harvester proposes, it does not run anything.
    for forbidden in ("subprocess.", "os.system(", "os.replace(", "shutil."):
        assert forbidden not in src, (
            f"harvester must not call {forbidden} (no enforcement power)"
        )


# --------------------------------------------------------- G3 kill-switch --
def test_g3_kill_switch_noop(monkeypatch):
    monkeypatch.setenv("LESSON_HARVESTER_OFF", "1")
    rc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "LESSON_HARVESTER_OFF": "1"},
    )
    assert rc.returncode == 0
    assert "DISABLED" in rc.stdout


# ------------------------------------------------------- idempotence / sync --
def test_self_test_passes():
    assert h._self_test() == 0


def test_generation_deterministic():
    a = h.render_json(h.build_report())
    b = h.render_json(h.build_report())
    assert a == b


def test_checked_in_report_in_sync():
    rc = h.check_report(h.build_report())
    assert rc == 0, "checked-in lesson-proposals artifact is stale — regenerate"


def test_check_cli_exit_zero():
    rc = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0


def test_real_ledger_parses_without_error():
    rep = h.build_report()
    assert rep["totals"]["scars_scanned"] >= 1
    # every classified scar is in exactly one bucket
    t = rep["totals"]
    assert (
        t["mechanical_candidates"] + t["consultive"] + t["rejected_no_anchor"]
        == t["scars_scanned"]
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
