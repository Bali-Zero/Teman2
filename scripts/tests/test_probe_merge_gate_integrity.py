"""probe_merge_gate_integrity.py must catch the real PR #3227 shape and must
never accuse a real, healthy merge-queue merge.

TRAUMA (PENDING-ARMS idx~49, 2026-08-21). PR #3227 merged into `main` with 19
of 25 required checks not green — but the 2026-08-08 ledger update that tried
to explain WHY blamed a merge-queue mechanism that did not exist until 2h29m
AFTER this PR merged. The real mechanism, measured: every check-suite for the
merge landed 2-3 seconds BEFORE the merge decision, so nothing the gate could
have looked at had finished computing. This probe detects that shape after the
fact (passive), rather than a canary that would provoke it on live `main`
(the team-lead's explicit instruction: detect, never provoke).

Guilt fixture: the real #3227 merge commit — zero merge_group runs exist for
it (recorded live via `gh api`, see the fixture's own `_comment`).
Innocence fixture: the real #4464 merge commit (2026-08-20, under the CURRENT
merge-queue regime) — 46 real merge_group jobs, all `success`, covering all 27
required contexts by exact name, one of which ("Test Summary") completed 1s
AFTER the recorded merge timestamp — which is exactly why a grace window
exists at all: without it, this genuinely clean merge would have been a false
positive (superscar #3, guard-over-match).
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "merge_gate_integrity"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "probe_merge_gate_integrity", _SCRIPTS / "probe_merge_gate_integrity.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


probe = _load_module()


def _load_fixture(name: str) -> dict[str, Any]:
    with open(_FIXTURES / name) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Guilt: the historical #3227 incident this tool was built to catch.
# ---------------------------------------------------------------------------


def test_guilt_3227_flags_no_gate_evidence():
    fx = _load_fixture("guilt_3227.json")
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is False
    assert result["merge_group_job_count"] == 0
    assert len(result["findings"]) == 1
    assert "no merge_group workflow runs found" in result["findings"][0]


def test_guilt_3227_cli_exits_nonzero(capsys):
    fx_path = str(_FIXTURES / "guilt_3227.json")
    rc = probe.main(["--fixture", fx_path])
    assert rc == 1
    out = capsys.readouterr().out
    assert "VIOLATION" in out


# ---------------------------------------------------------------------------
# Innocence: a real, healthy merge under the current merge-queue regime.
# ---------------------------------------------------------------------------


def test_innocence_4464_is_clean():
    fx = _load_fixture("innocence_4464.json")
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is True
    assert result["findings"] == []
    assert result["merge_group_job_count"] == 46


def test_innocence_4464_cli_exits_zero():
    fx_path = str(_FIXTURES / "innocence_4464.json")
    rc = probe.main(["--fixture", fx_path])
    assert rc == 0


def test_innocence_real_1s_overshoot_on_a_non_required_job_does_not_taint_the_verdict():
    """The real fixture already contains a 1s-after-merge completion: the
    'Test Summary' job. It happens NOT to be one of the 27 required contexts
    on this repo (aggregator/summary jobs sit alongside the required ones,
    not in place of them) — so it does not by itself prove the grace window
    is exercised. This pins that specific, measured fact instead of assuming
    it: a required-context probe must never be tripped by timing on a
    non-required job, no matter how it completes."""
    fx = _load_fixture("innocence_4464.json")
    ts_job = next(j for j in fx["merge_group_jobs"] if j["name"] == "Test Summary")
    assert ts_job["completed_at"] > fx["merged_at"], "fixture no longer exercises the overshoot case it was recorded for"
    assert "Test Summary" not in fx["required_contexts"], "fixture assumption changed — Test Summary is now required"

    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"], grace_seconds=0)
    assert result["clean"] is True


def test_grace_window_covers_a_required_context_synthetically_reproducing_the_measured_overshoot():
    """Applies the SAME measured pattern (a job completing 1s after
    merged_at — real, just not on a required context in this fixture) to an
    ACTUAL required context, so the grace window is proven load-bearing on
    the class of job it exists to protect, not merely on a summary job the
    evaluator never looks at."""
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    for j in fx["merge_group_jobs"]:
        if j["name"] == victim:
            j["completed_at"] = "2026-08-20T20:25:04Z"  # merged_at + 1s, the measured overshoot

    with_grace = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert with_grace["clean"] is True

    strict = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"], grace_seconds=0)
    assert strict["clean"] is False
    assert any(victim in f for f in strict["findings"])


# ---------------------------------------------------------------------------
# Mutation-style corpus: take the clean fixture and break ONE property at a
# time. Each mutation must turn the verdict red — a mutant that survives means
# this rule is decorative, not enforced (W95/W116 family).
# ---------------------------------------------------------------------------


def _clean_fixture() -> dict[str, Any]:
    return copy.deepcopy(_load_fixture("innocence_4464.json"))


def test_mutation_missing_required_context_is_caught():
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    fx["merge_group_jobs"] = [j for j in fx["merge_group_jobs"] if j["name"] != victim]
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is False
    assert any(victim in f and "never evaluated" in f for f in result["findings"])


def test_mutation_failed_required_context_is_caught():
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    for j in fx["merge_group_jobs"]:
        if j["name"] == victim:
            j["conclusion"] = "failure"
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is False
    assert any(victim in f and "failure" in f for f in result["findings"])


def test_mutation_zero_duration_job_is_caught():
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    for j in fx["merge_group_jobs"]:
        if j["name"] == victim:
            j["started_at"] = j["completed_at"]
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is False
    assert any(victim in f and "duration" in f for f in result["findings"])


def test_mutation_job_completed_far_after_merge_is_caught():
    """Reproduces the #3227 SHAPE at the timing-rule level, not just the
    zero-jobs level: a required context whose job finishes minutes after the
    merge, the way #3227's checks finished ~24 minutes late."""
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    for j in fx["merge_group_jobs"]:
        if j["name"] == victim:
            j["completed_at"] = "2026-08-20T20:49:03Z"  # 24 minutes after merged_at
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is False
    assert any(victim in f and "after the merge decision" in f for f in result["findings"])


def test_mutation_dropping_the_timing_check_entirely_would_be_caught():
    """Guard against a future edit that deletes the completed_dt > deadline
    branch outright: replay the same fixture with an absurdly generous grace
    window (equivalent to disabling the timing rule) and confirm the ONLY
    thing keeping this fixture clean at grace=0 was that specific branch."""
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    for j in fx["merge_group_jobs"]:
        if j["name"] == victim:
            j["completed_at"] = "2026-08-20T20:49:03Z"
    disabled_timing = probe.evaluate(
        fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"], grace_seconds=10**9
    )
    assert disabled_timing["clean"] is True, "sanity: a huge grace window should mask the late completion"
    enforced = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert enforced["clean"] is False


# ---------------------------------------------------------------------------
# Robustness: retries/re-queues can produce duplicate job names for the same
# run set — must resolve to the LATEST completed one, never crash, never
# silently prefer an in-progress duplicate over a completed result.
# ---------------------------------------------------------------------------


def test_duplicate_job_names_resolve_to_latest_completed():
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    stale = None
    for j in fx["merge_group_jobs"]:
        if j["name"] == victim:
            stale = copy.deepcopy(j)
            break
    assert stale is not None
    stale["conclusion"] = "failure"
    stale["completed_at"] = "2026-08-20T19:00:00Z"  # earlier, and failing
    fx["merge_group_jobs"].append(stale)

    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is True, "the later, successful duplicate must win over an earlier failing one"


def test_in_progress_duplicate_never_masks_a_missing_completed_result():
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    fx["merge_group_jobs"] = [j for j in fx["merge_group_jobs"] if j["name"] != victim]
    fx["merge_group_jobs"].append(
        {"name": victim, "status": "in_progress", "conclusion": None, "started_at": fx["merged_at"], "completed_at": None}
    )
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is False
    assert any(victim in f and "never evaluated" in f for f in result["findings"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
