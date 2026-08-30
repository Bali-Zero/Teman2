"""Guilt+innocence corpus for scripts/ci/check_promotion_readiness.py.

Every behavior of classify(), evaluate(), and main() that has a blocking vs
non-blocking distinction is tested from both sides: a test proving the bad
case is rejected (guilt) and a test proving the adjacent legitimate case is
accepted (innocence).  All I/O is mocked — no real `gh` calls.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import check_promotion_readiness as cpr  # noqa: E402


# ── helpers ─────────────────────────────────────────────────────────────────


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _check_run(
    *,
    name: str,
    status: str = "COMPLETED",
    conclusion: str | None = "SUCCESS",
    completed_at: str = "2026-08-31T00:00:00Z",
    details_url: str = "https://github.com/Bali-Zero/Teman2/runs/1",
) -> dict:
    entry: dict = {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "completedAt": completed_at,
        "detailsUrl": details_url,
    }
    if conclusion is not None:
        entry["conclusion"] = conclusion
    return entry


def _status_context(
    *,
    context: str,
    state: str = "SUCCESS",
    started_at: str = "2026-08-22T10:25:53Z",
    target_url: str = "https://example.com",
) -> dict:
    return {
        "__typename": "StatusContext",
        "context": context,
        "state": state,
        "startedAt": started_at,
        "targetUrl": target_url,
    }


# ── classify() state table ──────────────────────────────────────────────────


def test_classify_checkrun_pass() -> None:
    rollup = [_check_run(name="VOA probe organ tests", conclusion="SUCCESS")]
    v = cpr.classify(rollup, "VOA probe organ tests")
    assert v["state"] == cpr.STATE_PASS
    assert v["blocks"] is False


def test_classify_checkrun_skipped_not_fail() -> None:
    """SKIPPED must be its own non-blocking state, not folded into FAIL."""
    rollup = [_check_run(name="context", conclusion="SKIPPED")]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_SKIPPED
    assert v["blocks"] is False


def test_classify_checkrun_skipped_adjacent_fail() -> None:
    """Guilt: an adjacent non-SUCCESS conclusion (FAILURE) must block."""
    rollup = [_check_run(name="context", conclusion="FAILURE")]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_FAIL
    assert v["blocks"] is True


def test_classify_checkrun_neutral_not_fail() -> None:
    rollup = [_check_run(name="context", conclusion="NEUTRAL")]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_NEUTRAL
    assert v["blocks"] is False


def test_classify_checkrun_neutral_adjacent_fail() -> None:
    rollup = [_check_run(name="context", conclusion="CANCELLED")]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_FAIL
    assert v["blocks"] is True


def test_classify_checkrun_pending_in_progress_blocks() -> None:
    rollup = [_check_run(name="context", status="IN_PROGRESS", conclusion=None)]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_PENDING
    assert v["blocks"] is True


def test_classify_checkrun_pending_queued_blocks() -> None:
    rollup = [_check_run(name="context", status="QUEUED", conclusion=None)]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_PENDING
    assert v["blocks"] is True


def test_classify_checkrun_completed_not_pending() -> None:
    """Innocence: the same context name, once COMPLETED, is no longer PENDING."""
    rollup = [_check_run(name="context", status="COMPLETED", conclusion="SUCCESS")]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_PASS
    assert v["blocks"] is False


def test_classify_fail_conclusions_at_least_three() -> None:
    for conclusion in ("FAILURE", "CANCELLED", "TIMED_OUT"):
        rollup = [_check_run(name="context", conclusion=conclusion)]
        v = cpr.classify(rollup, "context")
        assert v["state"] == cpr.STATE_FAIL, conclusion
        assert v["blocks"] is True, conclusion


def test_classify_fail_closed_on_unrecognized_conclusion() -> None:
    """A made-up conclusion must fail closed (blocking), not be assumed safe."""
    rollup = [_check_run(name="context", conclusion="MYSTERY")]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_FAIL
    assert v["blocks"] is True


def test_classify_status_context_success() -> None:
    rollup = [_status_context(context="Vercel", state="SUCCESS")]
    v = cpr.classify(rollup, "Vercel")
    assert v["state"] == cpr.STATE_PASS
    assert v["blocks"] is False


def test_classify_status_context_pending_blocks() -> None:
    rollup = [_status_context(context="Vercel", state="PENDING")]
    v = cpr.classify(rollup, "Vercel")
    assert v["state"] == cpr.STATE_PENDING
    assert v["blocks"] is True


def test_classify_status_context_failure_blocks() -> None:
    rollup = [_status_context(context="Vercel", state="FAILURE")]
    v = cpr.classify(rollup, "Vercel")
    assert v["state"] == cpr.STATE_FAIL
    assert v["blocks"] is True


def test_classify_status_context_error_blocks() -> None:
    rollup = [_status_context(context="Vercel", state="ERROR")]
    v = cpr.classify(rollup, "Vercel")
    assert v["state"] == cpr.STATE_FAIL
    assert v["blocks"] is True


def test_classify_absent_when_other_contexts_present() -> None:
    """Guilt: a rollup with only OTHER names must report ABSENT for the queried name."""
    rollup = [
        _check_run(name="some-check", conclusion="SUCCESS"),
        _status_context(context="other-status", state="SUCCESS"),
    ]
    v = cpr.classify(rollup, "wanted-context")
    assert v["state"] == cpr.STATE_ABSENT
    assert v["blocks"] is True


def test_classify_not_absent_when_exact_name_present() -> None:
    """Innocence: a rollup WITH the exact context name must NOT be ABSENT."""
    rollup = [_check_run(name="wanted-context", conclusion="SUCCESS")]
    v = cpr.classify(rollup, "wanted-context")
    assert v["state"] != cpr.STATE_ABSENT
    assert v["blocks"] is False


def test_classify_matches_by_job_name_not_workflow_name() -> None:
    """Guilt: an entry whose workflowName differs from name must still match by name."""
    rollup = [
        {
            "__typename": "CheckRun",
            "name": "PR collision check corpus",
            "workflowName": "PR collision check (advisory)",
            "status": "COMPLETED",
            "conclusion": "SUCCESS",
            "completedAt": "2026-08-31T00:00:00Z",
            "detailsUrl": "https://github.com/Bali-Zero/Teman2/runs/1",
        }
    ]
    v = cpr.classify(rollup, "PR collision check corpus")
    assert v["state"] == cpr.STATE_PASS
    assert v["blocks"] is False


def test_classify_mismatch_by_workflow_name_when_name_differs() -> None:
    """Innocence: matching the workflowName instead of name would be wrong."""
    rollup = [
        {
            "__typename": "CheckRun",
            "name": "PR collision check corpus",
            "workflowName": "PR collision check (advisory)",
            "status": "COMPLETED",
            "conclusion": "SUCCESS",
            "completedAt": "2026-08-31T00:00:00Z",
            "detailsUrl": "https://github.com/Bali-Zero/Teman2/runs/1",
        }
    ]
    v = cpr.classify(rollup, "PR collision check (advisory)")
    assert v["state"] == cpr.STATE_ABSENT
    assert v["blocks"] is True


def test_classify_duplicate_entries_prefers_settled() -> None:
    """Two entries with the same name: the settled (COMPLETED/SUCCESS) one wins."""
    rollup = [
        _check_run(name="context", status="IN_PROGRESS", conclusion=None, completed_at="2026-08-31T00:00:00Z"),
        _check_run(name="context", status="COMPLETED", conclusion="SUCCESS", completed_at="2026-08-31T01:00:00Z"),
    ]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_PASS
    assert v["blocks"] is False


def test_classify_duplicate_entries_prefers_settled_pending_wins_if_no_settled() -> None:
    """Guilt-side guard: if neither duplicate is settled, PENDING is returned."""
    rollup = [
        _check_run(name="context", status="QUEUED", conclusion=None, completed_at="2026-08-31T00:00:00Z"),
        _check_run(name="context", status="IN_PROGRESS", conclusion=None, completed_at="2026-08-31T01:00:00Z"),
    ]
    v = cpr.classify(rollup, "context")
    assert v["state"] == cpr.STATE_PENDING
    assert v["blocks"] is True


# ── evaluate() aggregation ──────────────────────────────────────────────────


def test_evaluate_blocked_pr_present_and_clean_pr_absent() -> None:
    prs = [
        {"number": 1, "rollup": [_check_run(name="blocks-me", conclusion="FAILURE")]},
        {"number": 2, "rollup": [_check_run(name="blocks-me", conclusion="SUCCESS")]},
    ]
    report = cpr.evaluate(prs, ["blocks-me"])
    assert report["newly_blocked_prs"] == [1]


def test_evaluate_clean_pr_not_present() -> None:
    """Innocence: a fully passing PR must NOT appear in newly_blocked_prs."""
    prs = [
        {"number": 1, "rollup": [_check_run(name="ctx", conclusion="SUCCESS")]},
        {"number": 2, "rollup": [_check_run(name="ctx", conclusion="SUCCESS")]},
    ]
    report = cpr.evaluate(prs, ["ctx"])
    assert report["newly_blocked_prs"] == []


def test_evaluate_blocked_pr_not_absent() -> None:
    """Guilt: a blocked PR wrongly missing from newly_blocked_prs is a defect."""
    prs = [
        {"number": 1, "rollup": [_check_run(name="ctx", conclusion="FAILURE")]},
    ]
    report = cpr.evaluate(prs, ["ctx"])
    # The assertion below also guards the inverse of the innocence test above:
    # if evaluate ever wrongly omitted a blocked PR, this would fail.
    assert 1 in report["newly_blocked_prs"]


def test_evaluate_per_context_totals_across_multiple_prs() -> None:
    prs = [
        {"number": 1, "rollup": [_check_run(name="A", conclusion="SUCCESS")]},
        {"number": 2, "rollup": [_check_run(name="A", conclusion="FAILURE")]},
        {"number": 3, "rollup": [_check_run(name="B", conclusion="SUCCESS")]},
    ]
    report = cpr.evaluate(prs, ["A", "B"])
    # PR 3 does not have A, so A records one ABSENT count as well.
    assert report["per_context_totals"]["A"] == {
        cpr.STATE_PASS: 1, cpr.STATE_FAIL: 1, cpr.STATE_ABSENT: 1
    }
    assert report["per_context_totals"]["B"] == {
        cpr.STATE_PASS: 1, cpr.STATE_ABSENT: 2
    }


def test_evaluate_any_candidate_blocks_not_all() -> None:
    """A PR is newly-blocked if ANY candidate blocks it, not only if ALL do."""
    prs = [
        {
            "number": 42,
            "rollup": [
                _check_run(name="passes", conclusion="SUCCESS"),
                _check_run(name="fails", conclusion="FAILURE"),
            ],
        }
    ]
    report = cpr.evaluate(prs, ["passes", "fails"])
    assert report["newly_blocked_prs"] == [42]


def test_evaluate_all_candidates_pass_innocence() -> None:
    """Innocence: the sibling guard to `any_candidate_blocks_not_all` — when
    EVERY one of several candidates passes for a PR, it must NOT be
    newly-blocked. (Corrected 2026-08-31, cross-family review agy: this test
    previously reused the any_candidate_blocks_not_all fixture verbatim —
    one candidate FAILING — which duplicated that guilt test under an
    innocence-sounding name instead of covering the actual innocence case.)"""
    prs = [
        {
            "number": 42,
            "rollup": [
                _check_run(name="passes-a", conclusion="SUCCESS"),
                _check_run(name="passes-b", conclusion="SUCCESS"),
            ],
        }
    ]
    report = cpr.evaluate(prs, ["passes-a", "passes-b"])
    assert 42 not in report["newly_blocked_prs"]


# ── main() / CLI exit codes ─────────────────────────────────────────────────


def _make_gh_dispatch(repo: str, prs: list[dict], rollups: dict[int, list[dict]]):
    """Return a fake subprocess.run that services the gh calls main() makes."""
    def fake_run(cmd, **kwargs):
        # cmd is e.g. ["gh", "repo", "view", ...] or ["gh", "pr", "list", ...]
        if cmd == ["gh", "repo", "view", "--json", "nameWithOwner"]:
            return _completed(json.dumps({"nameWithOwner": repo}))
        if cmd[:3] == ["gh", "pr", "list"]:
            return _completed(json.dumps(prs))
        if cmd[:3] == ["gh", "pr", "view"]:
            number = int(cmd[3])
            return _completed(json.dumps({"number": number, "statusCheckRollup": rollups.get(number, [])}))
        raise AssertionError(f"unexpected gh command in fake_run: {cmd}")
    return fake_run


def test_main_blocked_pr_exits_one_with_threshold_zero(monkeypatch, capsys) -> None:
    prs = [{"number": 1, "headRefName": "feature", "headRefOid": "abc", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"}]
    rollups = {1: []}  # candidate ABSENT -> blocks
    monkeypatch.setattr(cpr.subprocess, "run", _make_gh_dispatch("Bali-Zero/Teman2", prs, rollups))
    rc = cpr.main(["--context", "Wanted context", "--max-newly-blocked", "0"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "NOT PROMOTABLE TODAY" in captured.out


def test_main_all_passing_exits_zero(monkeypatch, capsys) -> None:
    prs = [{"number": 1, "headRefName": "feature", "headRefOid": "abc", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"}]
    rollups = {1: [_check_run(name="Wanted context", conclusion="SUCCESS")]}
    monkeypatch.setattr(cpr.subprocess, "run", _make_gh_dispatch("Bali-Zero/Teman2", prs, rollups))
    rc = cpr.main(["--context", "Wanted context"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "PROMOTABLE TODAY" in captured.out


def test_main_threshold_one_allows_one_blocked_pr(monkeypatch) -> None:
    prs = [{"number": 1, "headRefName": "feature", "headRefOid": "abc", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"}]
    rollups = {1: []}
    monkeypatch.setattr(cpr.subprocess, "run", _make_gh_dispatch("Bali-Zero/Teman2", prs, rollups))
    assert cpr.main(["--context", "Wanted context", "--max-newly-blocked", "1"]) == 0


def test_main_threshold_zero_disallows_one_blocked_pr(monkeypatch) -> None:
    prs = [{"number": 1, "headRefName": "feature", "headRefOid": "abc", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"}]
    rollups = {1: []}
    monkeypatch.setattr(cpr.subprocess, "run", _make_gh_dispatch("Bali-Zero/Teman2", prs, rollups))
    assert cpr.main(["--context", "Wanted context", "--max-newly-blocked", "0"]) == 1


def test_main_candidates_file_missing_is_usage_error_no_gh_call(monkeypatch, capsys) -> None:
    """Guilt: a --candidates-file path that does not exist must exit 3 (usage
    error) with no gh call, not propagate an unhandled FileNotFoundError out
    of main() (found by cross-family review, agy, 2026-08-31: the original
    _load_candidates_file call site had no try/except at all, so this input
    produced a Python traceback and exit code 1 instead of the documented
    0/1/2/3 contract)."""
    calls = []

    def recording_run(cmd, **kwargs):
        calls.append(cmd)
        return _completed()

    monkeypatch.setattr(cpr.subprocess, "run", recording_run)
    rc = cpr.main(["--candidates-file", "/nonexistent/does-not-exist.json"])
    captured = capsys.readouterr()
    assert rc == 3
    assert "usage error" in captured.err
    assert calls == []


def test_main_candidates_file_valid_merges_with_context_innocence(monkeypatch) -> None:
    """Innocence: a well-formed --candidates-file (JSON array) merges with
    --context and the run proceeds normally through to a real verdict,
    proving the guilt-side fix above did not also break the working path."""
    prs = [{"number": 1, "headRefName": "feature", "headRefOid": "abc", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"}]
    rollups = {1: [
        _check_run(name="from-flag", conclusion="SUCCESS"),
        _check_run(name="from-file", conclusion="SUCCESS"),
    ]}
    monkeypatch.setattr(cpr.subprocess, "run", _make_gh_dispatch("Bali-Zero/Teman2", prs, rollups))

    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(["from-file"], f)
        path = f.name
    try:
        rc = cpr.main(["--context", "from-flag", "--candidates-file", path])
    finally:
        Path(path).unlink()
    assert rc == 0


def test_main_no_context_exits_three_and_never_calls_gh(monkeypatch, capsys) -> None:
    calls = []
    def recording_run(cmd, **kwargs):
        calls.append(cmd)
        return _completed()
    monkeypatch.setattr(cpr.subprocess, "run", recording_run)
    rc = cpr.main([])
    captured = capsys.readouterr()
    assert rc == 3
    assert "usage error" in captured.err
    assert calls == []


def test_main_negative_threshold_exits_three(monkeypatch, capsys) -> None:
    calls = []
    def recording_run(cmd, **kwargs):
        calls.append(cmd)
        return _completed()
    monkeypatch.setattr(cpr.subprocess, "run", recording_run)
    rc = cpr.main(["--context", "ctx", "--max-newly-blocked", "-1"])
    captured = capsys.readouterr()
    assert rc == 3
    assert "usage error" in captured.err
    assert calls == []


def test_main_empty_pr_list_exits_two_not_zero(monkeypatch, capsys) -> None:
    """The single most important test: zero PRs must NOT read as clean pass."""
    def fake_run(cmd, **kwargs):
        if cmd == ["gh", "repo", "view", "--json", "nameWithOwner"]:
            return _completed(json.dumps({"nameWithOwner": "Bali-Zero/Teman2"}))
        if cmd[:3] == ["gh", "pr", "list"]:
            return _completed(json.dumps([]))
        raise AssertionError(f"unexpected gh command: {cmd}")
    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    rc = cpr.main(["--context", "ctx"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "CANNOT-VERIFY" in captured.err
    assert "ZERO open PRs" in captured.err


def test_main_gh_pr_list_fails_exits_two(monkeypatch, capsys) -> None:
    def fake_run(cmd, **kwargs):
        if cmd == ["gh", "repo", "view", "--json", "nameWithOwner"]:
            return _completed(json.dumps({"nameWithOwner": "Bali-Zero/Teman2"}))
        if cmd[:3] == ["gh", "pr", "list"]:
            return _completed("", returncode=1, stderr="simulated network failure")
        raise AssertionError(f"unexpected gh command: {cmd}")
    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    rc = cpr.main(["--context", "ctx"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "CANNOT-VERIFY" in captured.err


def test_main_one_pr_view_fails_among_others_exits_two(monkeypatch, capsys) -> None:
    prs = [
        {"number": 1, "headRefName": "a", "headRefOid": "a1", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"},
        {"number": 2, "headRefName": "b", "headRefOid": "b1", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/2"},
    ]

    def fake_run(cmd, **kwargs):
        if cmd == ["gh", "repo", "view", "--json", "nameWithOwner"]:
            return _completed(json.dumps({"nameWithOwner": "Bali-Zero/Teman2"}))
        if cmd[:3] == ["gh", "pr", "list"]:
            return _completed(json.dumps(prs))
        if cmd[:3] == ["gh", "pr", "view"]:
            number = int(cmd[3])
            if number == 2:
                return _completed("", returncode=1, stderr="simulated PR view failure")
            return _completed(json.dumps({"number": number, "statusCheckRollup": [_check_run(name="ctx", conclusion="SUCCESS")]}))
        raise AssertionError(f"unexpected gh command: {cmd}")

    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    rc = cpr.main(["--context", "ctx"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "CANNOT-VERIFY" in captured.err
    assert "PR #2" in captured.err


def test_main_fetch_failed_pr_excluded_from_report_not_phantom_absent(monkeypatch, capsys) -> None:
    """Guilt: a PR whose rollup fetch failed must NOT be silently classified
    as ABSENT/blocked in the printed table, per_context_totals, or
    newly_blocked_prs — that would misattribute an unmeasured PR as a real
    negative finding. Found by cross-family review (kimi-code/k3,
    2026-08-31): the old `rollups.get(number, [])` fallback fed a failed PR
    to evaluate() with an empty rollup, indistinguishable from a genuine
    ABSENT. Innocence half: the PR that DID fetch successfully and passes is
    still correctly reported (proving the fix didn't also break the working
    path) — folded into this same test via --json for precise, non-brittle
    structural assertions rather than parsing the human-readable table."""
    prs = [
        {"number": 1, "headRefName": "a", "headRefOid": "a1", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"},
        {"number": 2, "headRefName": "b", "headRefOid": "b1", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/2"},
    ]

    def fake_run(cmd, **kwargs):
        if cmd == ["gh", "repo", "view", "--json", "nameWithOwner"]:
            return _completed(json.dumps({"nameWithOwner": "Bali-Zero/Teman2"}))
        if cmd[:3] == ["gh", "pr", "list"]:
            return _completed(json.dumps(prs))
        if cmd[:3] == ["gh", "pr", "view"]:
            number = int(cmd[3])
            if number == 2:
                return _completed("", returncode=1, stderr="simulated PR view failure")
            return _completed(json.dumps({"number": number, "statusCheckRollup": [_check_run(name="ctx", conclusion="SUCCESS")]}))
        raise AssertionError(f"unexpected gh command: {cmd}")

    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    rc = cpr.main(["--context", "ctx", "--json"])
    captured = capsys.readouterr()
    assert rc == 2
    payload = json.loads(captured.out[captured.out.find("{"):])
    # Innocence: PR 1 fetched and passed -> correctly counted.
    assert payload["prs_examined"] == 2
    assert payload["per_context_totals"]["ctx"] == {cpr.STATE_PASS: 1}
    # Guilt-side proof: PR 2's fetch failure must NOT manufacture a phantom
    # ABSENT/blocked row for it anywhere in the report.
    assert 2 not in payload["newly_blocked_prs"]
    assert all(row["pr"] != 2 for row in payload["rows"])
    assert list(payload["fetch_failures"].keys()) == ["2"]
    assert "simulated PR view failure" in payload["fetch_failures"]["2"]


def test_main_json_output_on_success(monkeypatch, capsys) -> None:
    prs = [{"number": 1, "headRefName": "feature", "headRefOid": "abc", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"}]
    rollups = {1: [_check_run(name="ctx", conclusion="SUCCESS")]}
    monkeypatch.setattr(cpr.subprocess, "run", _make_gh_dispatch("Bali-Zero/Teman2", prs, rollups))
    rc = cpr.main(["--context", "ctx", "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    json_start = captured.out.find("{")
    assert json_start != -1
    payload = json.loads(captured.out[json_start:])
    assert payload["exit"] == 0
    assert payload["fetch_failures"] == {}
    assert payload["newly_blocked_count"] == 0
    assert payload["prs_examined"] == 1


# ── never touch gh run / actions/runs boundary ──────────────────────────────


def test_never_calls_gh_run_or_actions_runs_api(monkeypatch) -> None:
    """Mandate trap #1: every subprocess invocation must be
    ["gh", "pr", ...] or ["gh", "repo", ...]; never ["gh", "run", ...] and
    never an "actions/runs" API endpoint."""
    prs = [
        {"number": 1, "headRefName": "a", "headRefOid": "a1", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"},
        {"number": 2, "headRefName": "b", "headRefOid": "b1", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/2"},
    ]
    rollups = {
        1: [_check_run(name="ctx", conclusion="SUCCESS")],
        2: [_check_run(name="ctx", conclusion="FAILURE")],
    }
    captured_calls = []

    def fake_run(cmd, **kwargs):
        captured_calls.append(list(cmd))
        if cmd == ["gh", "repo", "view", "--json", "nameWithOwner"]:
            return _completed(json.dumps({"nameWithOwner": "Bali-Zero/Teman2"}))
        if cmd[:3] == ["gh", "pr", "list"]:
            return _completed(json.dumps(prs))
        if cmd[:3] == ["gh", "pr", "view"]:
            number = int(cmd[3])
            return _completed(json.dumps({"number": number, "statusCheckRollup": rollups.get(number, [])}))
        raise AssertionError(f"unexpected gh command: {cmd}")

    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    cpr.main(["--context", "ctx"])

    assert captured_calls, "expected at least repo view + pr list + pr view calls"
    for call in captured_calls:
        assert call[0] == "gh", f"non-gh call leaked: {call}"
        assert call[1] in ("repo", "pr"), f"forbidden gh subcommand in {call}"
        assert call[1] != "run", f"gh run leaked: {call}"
        joined = " ".join(call)
        assert "actions/runs" not in joined, f"actions/runs API path leaked: {call}"


# ── retry behavior of _gh_run / _gh_json ────────────────────────────────────


def test_gh_run_retry_succeeds_on_second_attempt(monkeypatch) -> None:
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(cmd, timeout=1)
        return _completed(json.dumps({"ok": True}))

    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    result = cpr._gh_run(["pr", "view", "1"], timeout=1, retries=2, backoff=0.01)
    assert json.loads(result) == {"ok": True}
    assert len(calls) == 2


def test_gh_run_retry_exhausted_raises_cannot_verify(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=1)
    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    with pytest.raises(cpr.CannotVerify):
        cpr._gh_run(["pr", "view", "1"], timeout=1, retries=2, backoff=0.01)


def test_gh_json_retry_exhausted_raises_cannot_verify(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=1)
    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    with pytest.raises(cpr.CannotVerify):
        cpr._gh_json(["pr", "view", "1"], timeout=1, retries=2, backoff=0.01)


def test_gh_json_non_json_output_raises_cannot_verify(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        return _completed("this is not json")
    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    with pytest.raises(cpr.CannotVerify):
        cpr._gh_json(["pr", "view", "1"], timeout=1, retries=1, backoff=0.01)


# ── malformed CLI args exit 3, never argparse's hardcoded 2 ────────────────
# Found by cross-family review (codex-gpt-5.6-sol, 2026-08-31): bare
# argparse.ArgumentParser always calls sys.exit(2) on a parse error,
# indistinguishable from this script's own CANNOT-VERIFY code.


def test_main_malformed_cli_type_exits_three_not_two(capsys) -> None:
    """Guilt: a --max-newly-blocked value that fails its type=int conversion
    must exit 3 (usage error), never argparse's hardcoded 2."""
    rc = cpr.main(["--context", "ctx", "--max-newly-blocked", "nope"])
    captured = capsys.readouterr()
    assert rc == 3
    assert "usage error" in captured.err


def test_main_unrecognized_flag_exits_three_not_two(capsys) -> None:
    """Guilt (the harder case): argparse's 'unrecognized arguments' path
    calls self.error() directly, bypassing exit_on_error entirely — verified
    empirically to still need the ArgumentParser subclass override, not just
    exit_on_error=False."""
    rc = cpr.main(["--context", "ctx", "--this-flag-does-not-exist", "x"])
    captured = capsys.readouterr()
    assert rc == 3
    assert "usage error" in captured.err


def test_main_valid_cli_args_still_parse_innocence(monkeypatch) -> None:
    """Innocence: the _UsageErrorParser override must not break normal
    parsing of well-formed arguments."""
    prs = [{"number": 1, "headRefName": "feature", "headRefOid": "abc", "isDraft": False, "baseRefName": "main", "url": "https://github.com/Bali-Zero/Teman2/pull/1"}]
    rollups = {1: [_check_run(name="ctx", conclusion="SUCCESS")]}
    monkeypatch.setattr(cpr.subprocess, "run", _make_gh_dispatch("Bali-Zero/Teman2", prs, rollups))
    assert cpr.main(["--context", "ctx", "--max-newly-blocked", "0"]) == 0


# ── --base is passed to `gh pr list` itself, not only filtered in Python ───


def test_fetch_open_prs_passes_base_to_gh(monkeypatch) -> None:
    """Guilt-adjacent verification: --base must appear in the real `gh pr
    list` argv (found by cross-family review, codex-gpt-5.6-sol,
    2026-08-31: a Python-side-only filter lets --limit bound the WRONG
    universe when other-base PRs exist)."""
    captured_cmd = {}

    def fake_run(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        return _completed(json.dumps([]))

    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    cpr.fetch_open_prs("Bali-Zero/Teman2", "main", timeout=1, retries=1, backoff=0.01)
    cmd = captured_cmd["cmd"]
    assert "--base" in cmd
    assert cmd[cmd.index("--base") + 1] == "main"


# ── statusCheckRollup page-size guard (mandate trap: silent truncation) ────


def test_fetch_pr_rollup_at_page_size_raises_cannot_verify(monkeypatch) -> None:
    """Guilt: a rollup landing AT the known GraphQL page size (100) must be
    treated as possibly-truncated, never trusted as complete."""
    big_rollup = [_check_run(name=f"ctx-{i}", conclusion="SUCCESS") for i in range(100)]

    def fake_run(cmd, **kwargs):
        return _completed(json.dumps({"number": 1, "statusCheckRollup": big_rollup}))

    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    with pytest.raises(cpr.CannotVerify):
        cpr.fetch_pr_rollup("Bali-Zero/Teman2", 1, timeout=1, retries=1, backoff=0.01)


def test_fetch_pr_rollup_below_page_size_innocence(monkeypatch) -> None:
    """Innocence: a rollup just under the page size (99 entries) is trusted
    normally — the guard must not over-match on ordinary large PRs."""
    rollup = [_check_run(name=f"ctx-{i}", conclusion="SUCCESS") for i in range(99)]

    def fake_run(cmd, **kwargs):
        return _completed(json.dumps({"number": 1, "statusCheckRollup": rollup}))

    monkeypatch.setattr(cpr.subprocess, "run", fake_run)
    result = cpr.fetch_pr_rollup("Bali-Zero/Teman2", 1, timeout=1, retries=1, backoff=0.01)
    assert len(result) == 99


# ── format_totals()'s verdict must not lie when fetches failed ─────────────


def test_format_totals_fetch_failures_overrides_promotable_verdict() -> None:
    """Guilt: a run with zero blocked PRs among the measured ones, but 1+
    fetch failures, must NOT print 'verdict: PROMOTABLE TODAY' — that would
    misattribute an incomplete sweep as a clean one (found by cross-family
    review, codex-gpt-5.6-sol, 2026-08-31)."""
    report = {"rows": [], "newly_blocked_prs": [], "per_context_totals": {"ctx": {}}}
    text = cpr.format_totals(
        report, ["ctx"], prs_examined=2, max_newly_blocked=0,
        already_required=[], fetch_failures_count=1,
    )
    verdict_line = next(line for line in text.splitlines() if line.startswith("verdict:"))
    assert "PROMOTABLE TODAY" not in verdict_line
    assert "CANNOT-VERIFY" in verdict_line


def test_format_totals_zero_fetch_failures_innocence() -> None:
    """Innocence: with zero fetch failures (the default), the verdict line
    is exactly the pre-existing PROMOTABLE/NOT PROMOTABLE computation,
    unaffected by the new parameter."""
    report = {"rows": [], "newly_blocked_prs": [], "per_context_totals": {"ctx": {}}}
    text = cpr.format_totals(
        report, ["ctx"], prs_examined=2, max_newly_blocked=0, already_required=[],
    )
    assert "verdict: PROMOTABLE TODAY" in text


# ── load_already_required() ─────────────────────────────────────────────────


def test_load_already_required_well_formed_file(tmp_path: Path) -> None:
    path = tmp_path / "contexts.json"
    path.write_text(json.dumps({
        "contexts": [
            {"name": "Beta"},
            {"name": "Alpha"},
            {"name": "Alpha"},  # duplicate must be deduplicated
        ]
    }))
    assert cpr.load_already_required(path) == ["Alpha", "Beta"]


def test_load_already_required_missing_file_returns_empty() -> None:
    assert cpr.load_already_required(Path("/nonexistent/path/contexts.json")) == []


def test_load_already_required_malformed_json_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "contexts.json"
    path.write_text("{not valid json")
    assert cpr.load_already_required(path) == []


def test_load_already_required_missing_contexts_key_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "contexts.json"
    path.write_text(json.dumps({"other": [1, 2, 3]}))
    assert cpr.load_already_required(path) == []


def test_load_already_required_non_string_name_does_not_raise(tmp_path: Path) -> None:
    """Guilt: valid JSON with a non-string `name` (e.g. a bare number) used
    to reach `sorted({...})` over a set mixing str and int, raising an
    unhandled TypeError — breaking this function's own docstring promise
    'NEVER raises' on a file that IS valid JSON. Found by cross-family
    review (codex-gpt-5.6-sol, 2026-08-31). The malformed entry is dropped;
    well-formed string names alongside it are still returned (innocence
    folded into the same fixture, since a real contexts.json is one file
    with a mix of good and bad entries, not two separate scenarios)."""
    path = tmp_path / "contexts.json"
    path.write_text(json.dumps({"contexts": [{"name": "ctx"}, {"name": 1}]}))
    assert cpr.load_already_required(path) == ["ctx"]
