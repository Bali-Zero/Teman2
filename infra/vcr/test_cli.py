"""Tests for infra/vcr/cli.py — the shell-callable exit-code contract (R6).

Guilt AND innocence per exit code (scar #3): each of the 5 codes must be
independently producible AND the healthy path must independently produce 0 —
a check that only ever proves "not 0" would pass even if every failure path
collapsed onto the same wrong code.
"""

from __future__ import annotations

import argparse
import dataclasses
import json

from infra.vcr import cli
from infra.vcr.records import (
    CURRENT,
    DRIFTED,
    EXPIRED,
    FAILED,
    FALSE,
    HEALTHY,
    MISSING,
    PRESENT,
    STALE,
    TRUE,
    ClaimContext,
    MaterializedState,
)


def _state(**overrides):
    base = dict(
        seat="claude", context=ClaimContext(host="m5", auth_context="interactive"),
        truth_state=TRUE, freshness_state=CURRENT, coverage_state=PRESENT,
        verifier_state=HEALTHY, reason="ok", observed_at="2026-08-03T12:00:00Z",
    )
    base.update(overrides)
    return MaterializedState(**base)


def test_exit_0_all_healthy():
    assert cli.exit_code_for(_state()) == 0


def test_exit_5_dominates_verifier_drifted_even_if_everything_else_healthy():
    assert cli.exit_code_for(_state(verifier_state=DRIFTED)) == 5


def test_exit_5_dominates_verifier_failed():
    assert cli.exit_code_for(_state(verifier_state=FAILED)) == 5


def test_exit_4_coverage_missing_when_verifier_healthy():
    assert cli.exit_code_for(_state(coverage_state=MISSING, truth_state="UNVERIFIED")) == 4


def test_exit_3_stale_freshness_when_coverage_present():
    assert cli.exit_code_for(_state(freshness_state=STALE)) == 3


def test_exit_3_expired_freshness():
    assert cli.exit_code_for(_state(freshness_state=EXPIRED)) == 3


def test_exit_2_truth_not_true():
    assert cli.exit_code_for(_state(truth_state=FALSE)) == 2


def test_precedence_verifier_beats_freshness_and_truth_simultaneously():
    """A state with MULTIPLE bad axes must still resolve to the verifier
    code (5), not whichever check happens to run first by accident."""
    st = _state(verifier_state=DRIFTED, freshness_state=EXPIRED, truth_state=FALSE,
                coverage_state=MISSING)
    assert cli.exit_code_for(st) == 5


def test_precedence_coverage_beats_freshness_and_truth():
    st = _state(coverage_state=MISSING, freshness_state=EXPIRED, truth_state=FALSE)
    assert cli.exit_code_for(st) == 4


# ---------------------------------------------------------------------------
# _unhealthy_reason() / cmd_findings() — Codex red-team, 2026-08-03: the old
# cmd_findings() reported obs[-1].raw_status (the arsenal_probe raw status
# string, e.g. "LIVE") instead of the derived axes — a verifier-DRIFTED or
# hysteresis-not-yet-confirmed claim could surface as "LIVE" in findings,
# which is EXACTLY the vocabulary the sibling proprioception "arsenal_seats"
# entry's ok_values treats as healthy. This silently defeated the pilot's
# one converted real consumer (R7).
# ---------------------------------------------------------------------------

def test_unhealthy_reason_never_emits_a_raw_arsenal_probe_status_token():
    """Guilt: a verifier-DRIFTED state's reason must name the VERIFIER axis,
    never leak something that could be read as a raw 'LIVE'-shaped status."""
    st = _state(verifier_state=DRIFTED)
    reason = cli._unhealthy_reason(st)
    assert reason == "VERIFIER_DRIFTED"
    assert "LIVE" not in reason


def test_unhealthy_reason_names_every_unhealthy_axis():
    st = _state(verifier_state=DRIFTED, coverage_state=MISSING, freshness_state=EXPIRED,
                truth_state=FALSE)
    reason = cli._unhealthy_reason(st)
    assert "VERIFIER_DRIFTED" in reason
    assert "COVERAGE_MISSING" in reason
    assert "FRESHNESS_EXPIRED" in reason
    assert "TRUTH_FALSE" in reason


def test_unhealthy_reason_truth_false_alone_is_named_truth_not_hidden():
    """Innocence-adjacent: a claim that is unhealthy ONLY because hysteresis
    hasn't confirmed truth=TRUE yet must say so explicitly — this is the
    exact scenario (single new sample not yet debounced) that used to
    report the misleading raw 'LIVE' status."""
    st = _state(truth_state=FALSE)
    reason = cli._unhealthy_reason(st)
    assert reason == "TRUTH_FALSE"


def test_cmd_findings_reports_axis_reason_not_raw_status_end_to_end(monkeypatch, tmp_path, capsys):
    """Integration guilt case: with a REAL claim whose verifier is DRIFTED
    but whose last raw arsenal_probe status was "LIVE", cmd_findings()'s
    JSON output must never contain the bare token "LIVE" — proprioception's
    ok_values=[] for this entry only works if the reported status vocabulary
    never collides with arsenal_probe's own 'healthy-looking' tokens."""
    from infra.vcr.registry import ExpectedClaim

    fake_state = MaterializedState(
        seat="claude", context=ClaimContext(host="m5", auth_context="interactive"),
        truth_state=TRUE, freshness_state=CURRENT, coverage_state=PRESENT,
        verifier_state=DRIFTED, reason="hash mismatch", observed_at="2026-08-03T12:00:00Z",
    )
    monkeypatch.setattr(
        cli, "load_registry",
        lambda: [ExpectedClaim(seat="claude", host="m5", auth_context="interactive",
                                 ttl_s=3600, latency_budget_ms=15000, certified_hash="deadbeef")],
    )
    monkeypatch.setattr(cli.accessor, "local_machine_label", lambda: "m5")
    monkeypatch.setattr(cli.accessor, "get_state", lambda *a, **kw: fake_state)

    rc = cli.cmd_findings(argparse.Namespace(json=True))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["findings"] == [{"seat": "claude", "status": "VERIFIER_DRIFTED"}]
    assert "LIVE" not in json.dumps(out)
