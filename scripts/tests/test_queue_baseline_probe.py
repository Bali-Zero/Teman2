"""Tests for scripts/queue_baseline_probe.py — Merge-OS v2 Wave 1 baseline organ.

Module is imported via importlib.util.spec_from_file_location (not a package import)
because scripts/ is a flat bag of standalone tools, not a Python package (mirrors
scripts/tests/test_arsenal_probe.py / test_home_fork_stale_side_attribution.py).

NO network anywhere in this file. Every `gh` invocation is intercepted at the real
subprocess boundary the module crosses — `monkeypatch.setattr(qbp.subprocess, "run",
fake_run)` — per scar W114 ("the fake belongs at the boundary the REAL code crosses",
not at a hand-rolled wrapper one layer up that could itself drift from the real call
shape). `fake_run` pattern-matches on the exact argv the module builds.

Three scenarios required by the Wave-1 mandate (research/operations/
2026-08-10-merge-os-v2-submission-system.md §4):
  1. attribution math on a fixture day — 2 PR runs + 1 merge_group run of 3 members
     (even split) + 1 merge_group run with undecipherable membership (unattributed).
  2. an empty day still carries the FULL schema, zeros everywhere, errors == [].
  3. an API-denial fixture proves the silent-empty-on-failure case is IMPOSSIBLE —
     errors[] is populated and main()'s exit code is non-zero, while the record is
     still written to disk (never skipped).
Plus a handful of pure-function unit tests for the sub-mechanisms those three
scenarios lean on (guilt+innocence per scar family #3 where the function is a
classifier).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "queue_baseline_probe.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("queue_baseline_probe", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


qbp = _load_module()


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _mk_run(
    run_id: int,
    event: str,
    conclusion: str = "success",
    pull_requests: list[dict] | None = None,
    head_branch: str | None = None,
    display_title: str | None = None,
) -> dict:
    return {
        "id": run_id,
        "event": event,
        "conclusion": conclusion,
        "pull_requests": pull_requests or [],
        "head_branch": head_branch,
        "display_title": display_title,
    }


def _proc(cmd: list[str], rc: int, out: str, err: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(cmd, rc, out, err)


def _assert_explicit_get(cmd: list[str]) -> None:
    """`gh api` silently switches its default method to POST the instant any `-f`/`-F`
    field is present, unless `-X`/`--method` overrides it — every `-f`/`-F`-bearing `gh api`
    REST call this module makes MUST carry an explicit `-X GET` (regression coverage for the
    real-API 404 `fetch_run_jobs()` hit live 2026-08-14 on `.../actions/runs/{id}/jobs` before
    this flag was added — third instance of this class found the same day, after
    scripts/suite_growth_probe.py and scripts/queue_ejection_attribution.py; see PR
    description). A fake that stayed silent on a missing `-X GET` would never have caught
    that — a real subprocess call did, and this assertion is what keeps it caught without
    needing the network again.

    EXCLUDED BY DESIGN: `gh api graphql` calls (`fetch_automerge_enabled_at`) — GraphQL is
    POST BY PROTOCOL (queries and variables travel in the POST body), not a missing flag;
    asserting `-X GET` there would be wrong, not a fix.
    """
    if "graphql" in cmd:
        return
    has_f = "-f" in cmd or "-F" in cmd
    if has_f:
        assert "-X" in cmd, f"gh api call has -f but no explicit -X GET: {cmd}"
        idx = cmd.index("-X")
        assert cmd[idx + 1] == "GET", f"gh api call's -X is not GET: {cmd}"


def _guarded(fake):
    """Wrap a fake `subprocess.run` replacement so EVERY test in this file gets the
    `_assert_explicit_get` regression pin for free, regardless of which ad-hoc `fake_run` it
    defines — a class-audit fix that lived in only one test's fixture would leave every other
    call-site's future regression uncaught (scar family #3: a guard that only covers the one
    instance it was written for is a guard that will miss the next one)."""

    def wrapped(cmd, **kwargs):  # noqa: ANN001, ANN003
        _assert_explicit_get(cmd)
        return fake(cmd, **kwargs)

    return wrapped


def _make_fake_gh(
    repo: str,
    runs: list[dict],
    timing_ms_by_id: dict[int, int],
    run_duration_ms_by_id: dict[int, int] | None = None,
    reported_run_total: int | None = None,
    merged_prs: list[dict] | None = None,
    jobs_by_id: dict[int, list[dict]] | None = None,
    pr_view_by_number: dict[int, dict] | None = None,
    automerge_by_pr: dict[int, str] | None = None,
):
    """Builds a `subprocess.run`-compatible fake that answers every `gh` shape this
    module issues, matched by exact argv content (the real shapes the module builds).
    """
    merged_prs = merged_prs if merged_prs is not None else []
    run_duration_ms_by_id = run_duration_ms_by_id or {}
    reported_run_total = len(runs) if reported_run_total is None else reported_run_total
    jobs_by_id = jobs_by_id or {}
    pr_view_by_number = pr_view_by_number or {}
    automerge_by_pr = automerge_by_pr or {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003 — mirrors subprocess.run's own loose signature
        assert cmd[0] == "gh", f"unexpected non-gh subprocess call: {cmd}"
        if cmd[1] == "api" and len(cmd) > 2 and cmd[2] == f"repos/{repo}/actions/runs":
            return _proc(
                cmd,
                0,
                json.dumps({"total_count": reported_run_total, "workflow_runs": runs}),
            )
        if cmd[1] == "api" and len(cmd) > 2 and cmd[2].endswith("/timing"):
            run_id = int(cmd[2].split("/")[-2])
            if run_id not in timing_ms_by_id:
                return _proc(cmd, 1, "", f"404 run {run_id} not found")
            payload = {"billable": {"UBUNTU": {"total_ms": timing_ms_by_id[run_id]}}}
            if run_id in run_duration_ms_by_id:
                payload["run_duration_ms"] = run_duration_ms_by_id[run_id]
            return _proc(cmd, 0, json.dumps(payload))
        if cmd[1] == "api" and len(cmd) > 2 and cmd[2].endswith("/jobs"):
            run_id = int(cmd[2].split("/")[-2])
            return _proc(cmd, 0, json.dumps({"jobs": jobs_by_id.get(run_id, [])}))
        if cmd[1] == "pr" and cmd[2] == "list":
            return _proc(cmd, 0, json.dumps(merged_prs))
        if cmd[1] == "pr" and cmd[2] == "view":
            number = int(cmd[3])
            info = pr_view_by_number.get(number)
            if info is None:
                return _proc(cmd, 1, "", f"404 pr {number}")
            return _proc(cmd, 0, json.dumps(info))
        if cmd[1] == "api" and len(cmd) > 2 and cmd[2] == "graphql":
            number = None
            for i, tok in enumerate(cmd):
                if tok == "-F" and cmd[i + 1].startswith("number="):
                    number = int(cmd[i + 1].split("=", 1)[1])
            enabled_at = automerge_by_pr.get(number)
            payload = {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "autoMergeRequest": ({"enabledAt": enabled_at} if enabled_at else None)
                        }
                    }
                }
            }
            return _proc(cmd, 0, json.dumps(payload))
        raise AssertionError(f"unexpected gh invocation in fixture: {cmd}")

    return fake_run


def _fail_everything(cmd, **kwargs):  # noqa: ANN001, ANN003
    assert cmd[0] == "gh"
    return _proc(cmd, 1, "", "HTTP 403: API rate limit exceeded for installation")


def test_list_workflow_runs_reports_server_side_pagination_shortfall(monkeypatch):
    runs = [_mk_run(1, "push"), _mk_run(2, "pull_request")]
    fake = _make_fake_gh(
        qbp.DEFAULT_REPO,
        runs,
        timing_ms_by_id={},
        reported_run_total=17_648,
    )
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    fetched, reported_total, errors = qbp.list_workflow_runs(
        qbp.DEFAULT_REPO,
        date(2026, 8, 9),
    )

    assert [run["id"] for run in fetched] == [1, 2]
    assert reported_total == 17_648
    assert errors == [
        "list_workflow_runs pagination shortfall: "
        "fetched=2 reported_total=17648; record is partial"
    ]


def test_list_workflow_runs_combines_all_pages_and_deduplicates_ids(monkeypatch):
    pages = [
        {"total_count": 3, "workflow_runs": [_mk_run(1, "push"), _mk_run(2, "push")]},
        # The live endpoint can emit zero after reporting the real total on page one.
        {"total_count": 0, "workflow_runs": [_mk_run(2, "push"), _mk_run(3, "push")]},
    ]

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        return _proc(cmd, 0, "".join(json.dumps(page) for page in pages))

    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake_run))
    fetched, reported_total, errors = qbp.list_workflow_runs(
        qbp.DEFAULT_REPO,
        date(2026, 8, 9),
    )

    assert [run["id"] for run in fetched] == [1, 2, 3]
    assert reported_total == 3
    assert errors == []


def _parse_created_window(cmd: list[str]) -> tuple[datetime, datetime]:
    """Recover the `[start, end]` UTC window `list_workflow_runs` sent, for fakes that need
    to answer differently per window (the bisection tests below) rather than ignoring `cmd`
    like the fixtures above.
    """
    for i, tok in enumerate(cmd):
        if tok == "-f" and cmd[i + 1].startswith("created="):
            value = cmd[i + 1].split("=", 1)[1]
            start_s, end_s = value.split("..")
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            return (
                datetime.strptime(start_s, fmt).replace(tzinfo=timezone.utc),
                datetime.strptime(end_s, fmt).replace(tzinfo=timezone.utc),
            )
    raise AssertionError(f"no created= filter found in cmd: {cmd}")


def test_list_workflow_runs_bisects_past_the_1000_result_cap(monkeypatch):
    """Guilt: a day with 2,500 runs (real GitHub caps `created`-filtered queries at 1,000,
    per docs.github.com/en/rest/actions/workflow-runs) must still yield ALL of them, with an
    empty pagination error — recovered via recursive time-window bisection, not a single
    `--paginate` call.
    """
    day = date(2026, 8, 12)
    total_runs = 2500
    day_start = datetime(2026, 8, 12, tzinfo=timezone.utc)
    # Evenly spread across the day so each bisection level's two halves split ~evenly.
    step_seconds = 86400 / total_runs
    all_runs = [
        (i + 1, day_start + timedelta(seconds=i * step_seconds)) for i in range(total_runs)
    ]

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        assert cmd[0] == "gh"
        assert cmd[2] == f"repos/{qbp.DEFAULT_REPO}/actions/runs"
        start, end = _parse_created_window(cmd)
        matched = [(rid, ts) for rid, ts in all_runs if start <= ts <= end]
        capped = matched[: qbp.PAGE_CAP]  # GitHub's real server-side behavior: total_count is
        # honest, the served items are capped.
        payload = {
            "total_count": len(matched),
            "workflow_runs": [_mk_run(rid, "push") for rid, _ts in capped],
        }
        return _proc(cmd, 0, json.dumps(payload))

    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake_run))
    fetched, reported_total, errors = qbp.list_workflow_runs(qbp.DEFAULT_REPO, day)

    assert reported_total == total_runs
    assert sorted(run["id"] for run in fetched) == list(range(1, total_runs + 1))
    assert errors == []


def test_list_workflow_runs_gives_up_visibly_when_even_bisection_cannot_resolve(monkeypatch):
    """Guilt (safety bound): a pathologically dense day that STILL reports more than
    PAGE_CAP at every window, all the way down to the recursion bound, must never loop
    forever and must never claim completeness — errors[] stays non-empty and main()'s exit
    code is non-zero (W101 discipline), never a silent partial-as-complete record.
    """
    day = date(2026, 8, 12)
    monkeypatch.setattr(qbp, "MAX_BISECT_DEPTH", 3)  # keep the test fast; still exercises the
    # real recursive code path and the real fail-visible guard.

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        assert cmd[0] == "gh"
        if cmd[2] == f"repos/{qbp.DEFAULT_REPO}/actions/runs":
            # Every window, no matter how narrow, reports far more than it can serve.
            payload = {
                "total_count": 999_999,
                "workflow_runs": [_mk_run(i, "push") for i in range(qbp.PAGE_CAP)],
            }
            return _proc(cmd, 0, json.dumps(payload))
        raise AssertionError(f"unexpected gh invocation: {cmd}")

    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake_run))
    fetched, reported_total, errors = qbp.list_workflow_runs(qbp.DEFAULT_REPO, day)

    assert reported_total == 999_999
    assert len(fetched) < reported_total
    assert errors != []
    assert any("even after bisection" in e for e in errors)


def test_list_workflow_runs_gives_up_end_to_end_via_main_nonzero_exit(tmp_path, monkeypatch):
    """Same pathological-density scenario as above, exercised through main() end to end:
    the record is still written (never skipped), but the wrapper's rc-based alerting must
    see the failure (W101 discipline) — never a green run silently sitting on a partial day.
    """
    day = date(2026, 8, 12)
    monkeypatch.setattr(qbp, "MAX_BISECT_DEPTH", 2)

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        assert cmd[0] == "gh"
        if cmd[1] == "api" and len(cmd) > 2 and cmd[2] == f"repos/{qbp.DEFAULT_REPO}/actions/runs":
            payload = {"total_count": 999_999, "workflow_runs": [_mk_run(i, "push") for i in range(qbp.PAGE_CAP)]}
            return _proc(cmd, 0, json.dumps(payload))
        if cmd[1] == "api" and len(cmd) > 2 and cmd[2].endswith("/timing"):
            return _proc(cmd, 1, "", "not needed for this test")
        if cmd[1] == "pr" and cmd[2] == "list":
            return _proc(cmd, 0, json.dumps([]))
        raise AssertionError(f"unexpected gh invocation: {cmd}")

    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake_run))
    out_dir = tmp_path / "baseline"
    rc = qbp.main(["--repo", qbp.DEFAULT_REPO, "--date", day.isoformat(), "--out-dir", str(out_dir)])

    assert rc == 1
    record_path = out_dir / f"{day.isoformat()}.json"
    assert record_path.exists()
    on_disk = json.loads(record_path.read_text())
    assert on_disk["errors"] != []
    assert on_disk["run_collection"]["complete"] is False


def test_list_workflow_runs_innocence_below_cap_is_not_bisected(monkeypatch):
    """Innocence: a window whose raw fetch stays below PAGE_CAP is never split, regardless
    of how narrow the theoretical windows would be — single-window behavior is unchanged
    from before bisection existed (mirrors
    test_list_workflow_runs_combines_all_pages_and_deduplicates_ids but pinned explicitly
    against PAGE_CAP so a future change to that constant can't silently make this drift).
    """
    day = date(2026, 8, 12)
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        calls.append(cmd)
        payload = {"total_count": 42, "workflow_runs": [_mk_run(i, "push") for i in range(42)]}
        return _proc(cmd, 0, json.dumps(payload))

    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake_run))
    fetched, reported_total, errors = qbp.list_workflow_runs(qbp.DEFAULT_REPO, day)

    assert len(calls) == 1  # exactly one window fetched — no bisection attempted
    assert reported_total == 42
    assert len(fetched) == 42
    assert errors == []


def test_public_repo_timing_falls_back_to_run_duration_ms(monkeypatch):
    fake = _make_fake_gh(
        qbp.DEFAULT_REPO,
        runs=[],
        timing_ms_by_id={7001: 0},
        run_duration_ms_by_id={7001: 90_000},
    )
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    minutes, source, error = qbp.fetch_run_timing_minutes(qbp.DEFAULT_REPO, 7001)

    assert minutes == pytest.approx(1.5)
    assert source == "run_duration"
    assert error is None


def test_nonzero_billable_timing_wins_over_run_duration(monkeypatch):
    fake = _make_fake_gh(
        qbp.DEFAULT_REPO,
        runs=[],
        timing_ms_by_id={7002: 120_000},
        run_duration_ms_by_id={7002: 600_000},
    )
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    minutes, source, error = qbp.fetch_run_timing_minutes(qbp.DEFAULT_REPO, 7002)

    assert minutes == pytest.approx(2.0)
    assert source == "billable"
    assert error is None


# ---------------------------------------------------------------------------
# 1. Attribution math — 2 PR runs + 1 merge_group of 3 members (even split) +
#    1 merge_group with undecipherable membership (unattributed_group_minutes).
# ---------------------------------------------------------------------------


def test_attribution_even_split_and_unattributed_group_minutes(monkeypatch):
    day = date(2026, 8, 9)
    runs = [
        _mk_run(1001, "pull_request", pull_requests=[{"number": 100}]),
        _mk_run(1002, "pull_request", pull_requests=[{"number": 200}]),
        _mk_run(
            1003,
            "merge_group",
            head_branch="gh-readonly-queue/main/pr-100-abc123",
            display_title="Merge group: #100, #200, #300 into main",
        ),
        _mk_run(
            1004,
            "merge_group",
            head_branch="gh-readonly-queue/main/deadbeefdeadbeef00000000",
            display_title="Merge group into main",
        ),
    ]
    timing_ms = {1001: 40 * 60_000, 1002: 20 * 60_000, 1003: 30 * 60_000, 1004: 15 * 60_000}
    fake = _make_fake_gh(qbp.DEFAULT_REPO, runs, timing_ms, merged_prs=[])
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    record = qbp.build_record(qbp.DEFAULT_REPO, day)

    assert record["errors"] == []
    # PR 100 and 200 each get their own PR-run minutes PLUS an even 1/3 share of the
    # 3-member merge_group run (30 / 3 = 10 each); PR 300 only exists via the group.
    assert record["billed_minutes_per_pr"] == {
        "100": pytest.approx(40.0 + 10.0),
        "200": pytest.approx(20.0 + 10.0),
        "300": pytest.approx(10.0),
    }
    # The second merge_group run's membership is NOT derivable (no pr-N / #N anywhere)
    # — its minutes must land here, never be dropped (scar family #2, no silent caps).
    assert record["unattributed_group_minutes"] == pytest.approx(15.0)
    assert record["unattributed_pr_minutes"] == pytest.approx(0.0)
    assert record["total_runner_minutes"] == pytest.approx(40.0 + 20.0 + 30.0 + 15.0)
    assert record["timing_sources"]["billable"] == {"runs": 4, "minutes": 105.0}
    assert record["run_collection"] == {
        "reported_total": 4,
        "fetched": 4,
        "complete": True,
    }
    assert record["counts"]["runs_seen"] == 4
    assert record["counts"]["pull_request_runs"] == 2
    assert record["counts"]["merge_group_runs"] == 2


def test_pull_request_run_with_empty_pull_requests_field_is_unattributed_not_dropped(monkeypatch):
    """Known GitHub API gap: a `pull_request`-event run from a forked repo can carry
    an empty `pull_requests[]`. That must not silently vanish — it goes to
    unattributed_pr_minutes, distinct from the merge_group bucket.
    """
    day = date(2026, 8, 9)
    runs = [_mk_run(2001, "pull_request", pull_requests=[])]
    fake = _make_fake_gh(qbp.DEFAULT_REPO, runs, {2001: 12 * 60_000}, merged_prs=[])
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    record = qbp.build_record(qbp.DEFAULT_REPO, day)

    assert record["errors"] == []
    assert record["billed_minutes_per_pr"] == {}
    assert record["unattributed_pr_minutes"] == pytest.approx(12.0)
    assert record["unattributed_group_minutes"] == pytest.approx(0.0)


def test_ejection_counted_even_when_its_own_timing_fetch_fails(monkeypatch):
    """An ejected merge_group run's minutes may be unattributable (timing fetch 404s),
    but that must NEVER silently undercount the ejection itself — only the billing
    minutes have a gap, and that gap is separately visible in errors[].
    """
    day = date(2026, 8, 9)
    runs = [
        _mk_run(
            5001,
            "merge_group",
            conclusion="failure",
            head_branch="gh-readonly-queue/main/pr-500-abc123",
        )
    ]
    fake = _make_fake_gh(
        qbp.DEFAULT_REPO,
        runs,
        timing_ms_by_id={},  # 5001 deliberately absent -> timing fetch fails
        merged_prs=[],
        jobs_by_id={5001: [{"name": "Backend Tests (Python)", "conclusion": "failure"}]},
        pr_view_by_number={500: {"author": {"login": "someone"}, "headRefName": "fix/x"}},
    )
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    record = qbp.build_record(qbp.DEFAULT_REPO, day)

    assert record["ejections"]["total"] == 1
    assert record["ejections"]["by_class"]["CODE"] == 1
    assert record["ejections"]["by_author_class"]["human"] == 1
    # The timing gap for run 5001 is visible, not swallowed.
    assert any("timing fetch failed" in e or "404" in e for e in record["errors"])
    assert record["billed_minutes_per_pr"] == {}


def test_ejection_infra_classification_reaches_real_jobs_fetch_boundary(monkeypatch):
    """Reconciliation guilt-test (post-2026-08-14 `-X GET` fix): the INFRA branch of
    `classify_ejection` was NEVER dead as a pure function (see
    `test_classify_ejection_failed_run_with_setup_job_failure_is_infra` below) — it was dead
    end-to-end, because `fetch_run_jobs` 404'd on every real call before this fix and
    `build_record` always saw an empty jobs list. `_guarded()` (module-level in this test
    file) makes every fixture in this file assert the real `gh api` argv is 404-safe — this
    test additionally proves that, once real, the jobs data actually reaches and flips the
    classification (not just that the call shape is correct in isolation). Uses the SAME
    real day (2026-08-12) and the SAME infra-flavoured job name ("Set up job") verified live
    against this repo's actual PR #4127 second ejection episode
    (scripts/queue_ejection_attribution.py's own dry-run independently found this INFRA
    ejection via the PR-timeline path the same day) — not a hypothetical fixture.
    """
    day = date(2026, 8, 12)
    runs = [
        _mk_run(
            6001,
            "merge_group",
            conclusion="failure",
            head_branch="gh-readonly-queue/main/pr-4127-abc123",
        )
    ]
    fake = _make_fake_gh(
        qbp.DEFAULT_REPO,
        runs,
        timing_ms_by_id={6001: 5 * 60_000},
        merged_prs=[],
        jobs_by_id={6001: [{"name": "Set up job", "conclusion": "failure"}]},
        pr_view_by_number={4127: {"author": {"login": "Balizero1987"}, "headRefName": "agent/air-m5/ops/x"}},
    )
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))

    record = qbp.build_record(qbp.DEFAULT_REPO, day)

    assert record["ejections"]["total"] == 1
    assert record["ejections"]["by_class"]["INFRA"] == 1
    assert record["ejections"]["by_class"]["CODE"] == 0
    assert record["ejections"]["by_author_class"]["agent"] == 1


def test_non_pr_non_merge_group_run_counts_toward_slot_utilization_only(monkeypatch):
    day = date(2026, 8, 9)
    runs = [_mk_run(3001, "schedule")]
    fake = _make_fake_gh(qbp.DEFAULT_REPO, runs, {3001: 5 * 60_000}, merged_prs=[])
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    record = qbp.build_record(qbp.DEFAULT_REPO, day)

    assert record["errors"] == []
    assert record["billed_minutes_per_pr"] == {}
    assert record["other_event_minutes"] == pytest.approx(5.0)
    assert record["slot_utilization"]["runner_minutes_today"] == pytest.approx(5.0)


def test_public_repo_duration_fallback_populates_runner_minutes(monkeypatch):
    day = date(2026, 8, 9)
    runs = [_mk_run(3002, "schedule")]
    fake = _make_fake_gh(
        qbp.DEFAULT_REPO,
        runs,
        timing_ms_by_id={3002: 0},
        run_duration_ms_by_id={3002: 5 * 60_000},
        merged_prs=[],
    )
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    record = qbp.build_record(qbp.DEFAULT_REPO, day)

    assert record["errors"] == []
    assert record["other_event_minutes"] == pytest.approx(5.0)
    assert record["total_runner_minutes"] == pytest.approx(5.0)
    assert record["timing_sources"]["run_duration"] == {"runs": 1, "minutes": 5.0}


# ---------------------------------------------------------------------------
# 2. Empty-day record still carries the schema with zeros and empty errors.
# ---------------------------------------------------------------------------


def test_empty_day_record_carries_full_schema_with_zeros(monkeypatch):
    day = date(2026, 8, 9)
    fake = _make_fake_gh(qbp.DEFAULT_REPO, runs=[], timing_ms_by_id={}, merged_prs=[])
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    record = qbp.build_record(qbp.DEFAULT_REPO, day)

    assert record["errors"] == []
    assert record["date"] == day.isoformat()
    assert record["billed_minutes_per_pr"] == {}
    assert record["unattributed_group_minutes"] == 0.0
    assert record["unattributed_pr_minutes"] == 0.0
    assert record["other_event_minutes"] == 0.0
    assert record["total_runner_minutes"] == 0.0
    assert record["timing_sources"] == {
        "billable": {"runs": 0, "minutes": 0.0},
        "run_duration": {"runs": 0, "minutes": 0.0},
        "billable_zero_without_duration": {"runs": 0, "minutes": 0.0},
    }
    assert record["run_collection"] == {
        "reported_total": 0,
        "fetched": 0,
        "complete": True,
    }
    assert record["queue_transit_minutes"] == {}
    assert record["queue_transit_p50_minutes"] is None
    assert record["queue_transit_p95_minutes"] is None
    assert record["transit_unmeasured_prs"] == []
    assert record["ejections"] == {
        "by_class": {"INFRA": 0, "CODE": 0, "FLAKE": 0},
        "by_author_class": {"human": 0, "agent": 0, "bot": 0, "unknown": 0},
        "total": 0,
    }
    assert record["counts"] == {
        "runs_seen": 0,
        "merge_group_runs": 0,
        "pull_request_runs": 0,
        "other_runs": 0,
        "prs_merged_today": 0,
    }
    assert record["slot_utilization"]["runner_minutes_today"] == 0.0
    assert record["slot_utilization"]["weekly_capacity_slot_minutes"] == pytest.approx(
        qbp.WEEKLY_CI_CAPACITY_SLOT_MINUTES
    )


def test_empty_day_end_to_end_via_main_writes_file_and_exits_zero(tmp_path, monkeypatch):
    day = date(2026, 8, 9)
    fake = _make_fake_gh(qbp.DEFAULT_REPO, runs=[], timing_ms_by_id={}, merged_prs=[])
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(fake))
    out_dir = tmp_path / "baseline"
    rc = qbp.main(["--repo", qbp.DEFAULT_REPO, "--date", day.isoformat(), "--out-dir", str(out_dir)])

    assert rc == 0
    record_path = out_dir / f"{day.isoformat()}.json"
    assert record_path.exists()
    on_disk = json.loads(record_path.read_text())
    assert on_disk["errors"] == []
    assert on_disk["counts"]["runs_seen"] == 0
    pointer = json.loads((out_dir / ".last-run-pointer.json").read_text())
    assert pointer["date"] == day.isoformat()
    assert pointer["errors_count"] == 0


# ---------------------------------------------------------------------------
# 3. API-denial fixture — silent-empty-on-failure must be IMPOSSIBLE.
# ---------------------------------------------------------------------------


def test_api_denial_produces_record_with_errors_never_silent(monkeypatch):
    day = date(2026, 8, 9)
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(_fail_everything))
    record = qbp.build_record(qbp.DEFAULT_REPO, day)

    # Guilt: under total API denial, an empty errors[] must be IMPOSSIBLE.
    assert record["errors"] != []
    assert all(isinstance(e, str) and e.strip() for e in record["errors"])
    # The schema is still fully present (never a partial/malformed record).
    assert record["billed_minutes_per_pr"] == {}
    assert record["counts"]["runs_seen"] == 0


def test_api_denial_end_to_end_via_main_nonzero_exit_but_record_on_disk(tmp_path, monkeypatch):
    day = date(2026, 8, 9)
    monkeypatch.setattr(qbp.subprocess, "run", _guarded(_fail_everything))
    out_dir = tmp_path / "baseline"
    rc = qbp.main(["--repo", qbp.DEFAULT_REPO, "--date", day.isoformat(), "--out-dir", str(out_dir)])

    # Fail-visible (W101 discipline): the wrapper's rc-based alerting depends on this.
    assert rc == 1
    record_path = out_dir / f"{day.isoformat()}.json"
    assert record_path.exists(), "the record must be written even when everything failed"
    on_disk = json.loads(record_path.read_text())
    assert on_disk["errors"] != []


# ---------------------------------------------------------------------------
# Pure-function unit tests — the mechanisms the three scenarios above lean on.
# ---------------------------------------------------------------------------


def test_extract_merge_group_pr_numbers_from_head_branch():
    run = _mk_run(1, "merge_group", head_branch="gh-readonly-queue/main/pr-4821-abcdef0123")
    assert qbp.extract_merge_group_pr_numbers(run) == [4821]


def test_extract_merge_group_pr_numbers_from_display_title():
    run = _mk_run(1, "merge_group", display_title="Merge #10, #20 and #30 into main")
    assert qbp.extract_merge_group_pr_numbers(run) == [10, 20, 30]


def test_extract_merge_group_pr_numbers_innocence_no_numbers_anywhere():
    run = _mk_run(1, "merge_group", head_branch="gh-readonly-queue/main/deadbeef", display_title="Merge group into main")
    assert qbp.extract_merge_group_pr_numbers(run) == []


def test_percentile_p50_p95_linear_interpolation():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert qbp.percentile(values, 50) == pytest.approx(5.5)
    assert qbp.percentile(values, 95) == pytest.approx(9.55)


def test_percentile_empty_is_none_never_zero():
    assert qbp.percentile([], 50) is None


def test_classify_ejection_cancelled_run_is_infra():
    run = _mk_run(1, "merge_group", conclusion="cancelled")
    assert qbp.classify_ejection(run, jobs=[]) == "INFRA"


def test_classify_ejection_failed_run_with_setup_job_failure_is_infra():
    run = _mk_run(1, "merge_group", conclusion="failure")
    jobs = [{"name": "Set up job", "conclusion": "failure"}, {"name": "pytest", "conclusion": "skipped"}]
    assert qbp.classify_ejection(run, jobs) == "INFRA"


def test_classify_ejection_innocence_failed_run_with_ordinary_test_failure_is_code():
    run = _mk_run(1, "merge_group", conclusion="failure")
    jobs = [{"name": "Backend Tests (Python)", "conclusion": "failure"}]
    assert qbp.classify_ejection(run, jobs) == "CODE"


def test_classify_author_agent_branch_wins_over_login():
    assert qbp.classify_author("agent/air-m5/ops/x", "some-human") == "agent"


def test_classify_author_bot_login():
    assert qbp.classify_author("dependabot/npm_and_yarn/foo", "dependabot[bot]") == "bot"


def test_classify_author_innocence_ordinary_human():
    assert qbp.classify_author("fix/typo", "antonellosiano") == "human"
