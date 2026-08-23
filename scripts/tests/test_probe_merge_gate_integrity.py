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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "merge_gate_integrity"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _shift_iso(ts: str, seconds: int) -> str:
    """Return `ts` moved FORWARD by `seconds`, in the same Z-suffixed form."""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) + timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


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


# ---------------------------------------------------------------------------
# S12/C1 — "skipped" satisfies branch protection, so it must not be a finding.
#
# Measured 2026-08-23: PR #4654 (docs-only) LANDED on main with four of the 27
# required contexts concluding "skipped" in its merge_group run. A second lane
# independently observed the same on pr-4658 the same morning. Before this,
# every path-filtered merge produced a false VIOLATION — and because the
# workflow's exit-code capture was also broken, it surfaced as 26 consecutive
# CANNOT-VERIFY reds instead. Both directions are pinned here: skipped passes,
# and NOTHING ELSE was widened along with it (superscar #3).
# ---------------------------------------------------------------------------


def _set_conclusion(fx: dict[str, Any], ctx: str, conclusion: str) -> None:
    """Set every job carrying this context name to `conclusion`, reproducing
    the timestamps GitHub really emits for that conclusion.

    The skipped shape is MEASURED, not invented, and it is stranger than the
    obvious guess. Live jobs on merge commit b72f1885f (2026-08-23):

        {"name": "Bandit Python Security", "conclusion": "skipped",
         "started_at": "2026-08-23T09:42:22Z",
         "completed_at": "2026-08-23T09:42:21Z"}

    completed_at is ONE SECOND BEFORE started_at — duration -1s, not 0. A test
    that used started_at == completed_at would pass while pinning a shape
    production never produces; worse, it would leave the negative-duration
    path (the "phantom result" finding) unexercised on exactly the input that
    reaches it in the real world."""
    for job in fx["merge_group_jobs"]:
        if job["name"] == ctx:
            job["conclusion"] = conclusion
            if conclusion == "skipped":
                completed = job["completed_at"]
                job["started_at"] = _shift_iso(completed, seconds=1)


def test_skipped_required_context_is_not_a_finding():
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    _set_conclusion(fx, victim, "skipped")
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is True, f"skipped must satisfy the gate, findings={result['findings']}"
    assert victim in result["skipped_contexts"], "a skipped context must still be REPORTED, just not as a finding"


def test_skipped_context_survives_the_negative_duration_rule():
    """A real skipped job completes BEFORE it starts (measured: -1s). The
    phantom-result rule must not fire on it — otherwise the cure just moves
    the false positive one line down instead of removing it. This is the
    single most load-bearing test of the three C1 defects, because a naive
    'skipped passes' that still ran the duration check would have kept ~26
    reds a day while looking fixed."""
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    _set_conclusion(fx, victim, "skipped")
    for job in fx["merge_group_jobs"]:
        if job["name"] == victim:
            assert job["started_at"] > job["completed_at"], (
                "fixture no longer reproduces the measured skipped shape "
                "(completed_at before started_at)"
            )
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert not any("phantom" in f for f in result["findings"]), result["findings"]
    assert result["clean"] is True, result["findings"]


def test_docs_only_merge_shape_four_skipped_contexts_is_clean():
    """The exact measured #4654 shape — four required contexts skipped at once."""
    fx = _clean_fixture()
    victims = fx["required_contexts"][:4]
    for ctx in victims:
        _set_conclusion(fx, ctx, "skipped")
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is True, result["findings"]
    assert sorted(result["skipped_contexts"]) == sorted(victims)


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "action_required", "neutral", None])
def test_no_other_conclusion_was_widened_along_with_skipped(conclusion):
    """GUILT, one case per conclusion. `neutral` is in this list deliberately:
    it is widely said to satisfy required checks too, but it was NOT measured
    on this repo, so it stays a finding. A future lane that measures it may
    move it — by adding evidence, not by assuming symmetry."""
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    _set_conclusion(fx, victim, conclusion)
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is False, f"conclusion={conclusion!r} must still be a finding"
    assert victim not in result["skipped_contexts"]


def test_skipped_does_not_substitute_for_a_missing_job():
    """A context with NO merge_group job at all is still caught — the skipped
    allowance must not degrade into 'absence is fine'."""
    fx = _clean_fixture()
    victim = fx["required_contexts"][0]
    fx["merge_group_jobs"] = [j for j in fx["merge_group_jobs"] if j["name"] != victim]
    result = probe.evaluate(fx["merge_group_jobs"], fx["required_contexts"], fx["merged_at"])
    assert result["clean"] is False
    assert any(victim in f and "never evaluated" in f for f in result["findings"])


# ---------------------------------------------------------------------------
# S12/C1 — required-context source: live API first, checked-in snapshot second,
# CANNOT-VERIFY if both fail. Never an empty list (that would be fail-OPEN).
# ---------------------------------------------------------------------------


def test_snapshot_file_is_present_and_non_empty():
    """The fallback is only a fallback if it exists. Pins the file this probe
    now depends on in CI."""
    names, generated_at = probe._required_contexts_from_snapshot(str(REPO_ROOT))
    assert len(names) >= 20, f"snapshot looks truncated: {len(names)} contexts"
    assert all(isinstance(n, str) and n for n in names)
    assert generated_at and generated_at != "unknown", (
        "the snapshot must carry its own generation date — it is what makes the "
        "declared drift risk visible in a run log instead of invisible"
    )


def test_api_is_preferred_when_it_answers(monkeypatch):
    monkeypatch.setattr(
        probe, "_gh_api_json",
        lambda path: {"required_status_checks": {"contexts": ["Only From API"]}},
    )
    contexts, source = probe.fetch_required_contexts("o/r", str(REPO_ROOT))
    assert contexts == ["Only From API"]
    assert source == "api"


def test_snapshot_is_used_when_the_api_is_denied(monkeypatch):
    """The real CI shape: GITHUB_TOKEN cannot be granted `administration`, so
    branches/main/protection raises. Before this fallback that raise WAS the
    26-reds-a-day bug."""
    def _denied(path):
        raise RuntimeError("gh api ... failed (rc=1): HTTP 403 Resource not accessible by integration")

    monkeypatch.setattr(probe, "_gh_api_json", _denied)
    contexts, source = probe.fetch_required_contexts("o/r", str(REPO_ROOT))
    assert len(contexts) >= 20
    assert source.startswith("snapshot:")


def test_empty_api_contexts_falls_through_rather_than_passing_vacuously(monkeypatch):
    """An empty required list would make EVERY commit vacuously clean — a
    fail-OPEN detector. It must fall through to the snapshot, not be used."""
    monkeypatch.setattr(
        probe, "_gh_api_json",
        lambda path: {"required_status_checks": {"contexts": []}},
    )
    contexts, source = probe.fetch_required_contexts("o/r", str(REPO_ROOT))
    assert contexts, "empty API result must never be accepted as the required list"
    assert source.startswith("snapshot:")


def test_both_sources_failing_raises_cannot_verify(monkeypatch, tmp_path):
    def _denied(path):
        raise RuntimeError("HTTP 403")

    monkeypatch.setattr(probe, "_gh_api_json", _denied)
    with pytest.raises(RuntimeError) as exc:
        probe.fetch_required_contexts("o/r", str(tmp_path))  # no snapshot here
    assert "could not determine required contexts" in str(exc.value)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
