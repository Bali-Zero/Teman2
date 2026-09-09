#!/usr/bin/env python3
"""flaky_harvest.py — MEASURE-ONLY flaky-test harvester for the CI merge queue.

WHAT THIS IS: Lane 5 of Zero's 2026-09-10 queue-time mandate (R4 of
research/operations/2026-08-28-beyond-sota-ci-merge-queue-ship-pipeline.md). It compares the
SAME job across a PR's `pull_request` run and its `merge_group` (merge-queue) run(s) on the
`tests.yml` workflow, and across repeated `merge_group` re-entries of the same PR head, to find
jobs whose conclusion flips (success in one, failure in the other) with no code change between
them — a flake candidate.

THIS SCRIPT NEVER QUARANTINES ANYTHING. No test is skipped, no job is disabled, no PR is
touched. It only reads `gh run list` / `gh run view` / `gh api .../logs` and renders a report.
The quarantine thresholds a future tool might apply (>=5 failures on >=50 runs, a 2% suite cap,
an expiry window) are Zero's decision, not this script's — the report header says so explicitly,
every run, so a reader never mistakes "measured" for "acted on".

THE SHA IN THE QUEUE REF IS NOT THE PR'S HEAD COMMIT — measured live 2026-09-10 against
Bali-Zero/Teman2, not assumed. `gh-readonly-queue/main/pr-<N>-<sha>` looks like it should encode
PR <N>'s queued head commit, but GitHub's merge queue stacks entries: `<sha>` is the SYNTHETIC
head sha of the entry immediately ahead of <N> in the queue, not <N>'s own commit. Chain observed
live: pr-6058's ref carries 603f1f76..., which is exactly pr-6057's merge_group run's own
headSha; pr-6057's ref carries fd79262f..., which is pr-6059's merge_group headSha; and so on.
Pairing on that embedded sha against a `pull_request` run's headSha therefore matches almost
nothing (see `find_matching_pr_run`'s docstring for the numbers from the first live run).
This script instead extracts the PR NUMBER from the ref name (`pr-(\\d+)-`), asks `gh pr view
<N>` for the PR's real `headRefOid`, and matches THAT against `pull_request`-event runs' own
headSha. That is the only sha this repo's API surface offers that both a `pull_request` run and
its PR's merge_group entry agree on.

Tests: scripts/ci/test_flaky_harvest.py — pure functions only (parsing/pairing/classification/
rendering), no live `gh` calls; the live path is exercised by running this script for real
(the report this PR ships in `docs/reports/flaky-harvest/` IS that proof).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_REPO = "Bali-Zero/Teman2"
DEFAULT_WORKFLOW = "tests.yml"
DEFAULT_DAYS = 7
# Measured live 2026-09-10: `gh run list`/`gh api .../runs` both hard-cap at 1000 results
# regardless of a higher -L or --paginate — confirmed via the API's own `total_count` (1115)
# vs. what page 11 onward actually returns (empty) for the exact same query. 1000 is therefore
# the real ceiling, not a tunable choice; raising this constant would not fetch more.
DEFAULT_RUN_LIMIT = 1000
DEFAULT_MAX_WORKERS = 8
DEFAULT_TOP_N = 20
COMPARABLE_CONCLUSIONS = {"success", "failure"}
QUEUE_REF_RE = re.compile(r"^gh-readonly-queue/[^/]+/pr-(\d+)-")
# GitHub Actions job logs prefix EVERY line with an ISO-8601 timestamp
# (`2026-09-09T17:33:10.6329802Z `) — measured live 2026-09-10 against real job logs. A bare
# `^FAILED` anchor never matches a real pytest `FAILED tests/...` line in that log, only a
# synthetic/test-fixture one without the prefix. The timestamp segment is optional so tests can
# use bare lines.
FAILED_LINE_RE = re.compile(r"^(?:\S+Z\s+)?FAILED\s+(\S+)")

# Thresholds a future quarantine tool MIGHT apply. Not applied here — see module docstring and
# the report header. Kept as named constants (not inline numbers) so a future PR that wires
# quarantine points at ONE place, and this script's own report can quote them verbatim.
THRESHOLD_MIN_FAILURES = 5
THRESHOLD_MIN_RUNS = 50
THRESHOLD_SUITE_CAP_PCT = 2
THRESHOLD_EXPIRY_NOTE = "no expiry policy defined yet"


class GhError(RuntimeError):
    """A `gh` invocation failed or timed out. Callers count these, never guess a value."""


# ---------------------------------------------------------------------------
# gh wire — the only functions that touch the network. Everything below this
# section is pure and covered by scripts/ci/test_flaky_harvest.py.
# ---------------------------------------------------------------------------


def run_gh(args: list[str], *, timeout: int = 60, raw: bool = False) -> Any:
    """Run a `gh` command, return parsed JSON (or raw text if raw=True). Raises GhError on any
    non-zero exit, timeout, or JSON decode failure — callers must catch this and COUNT the
    failure, never fabricate a value in its place (superscar #6)."""
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise GhError(f"gh {' '.join(args)} timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise GhError(f"gh {' '.join(args)} rc={proc.returncode}: {proc.stderr.strip()[:300]}")
    if raw:
        return proc.stdout
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"gh {' '.join(args)} returned non-JSON output") from exc


def cache_path(cache_dir: Path, name: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / name


def fetch_workflow_runs(
    repo: str,
    workflow: str,
    limit: int,
    cache_dir: Path,
    gh: Callable = run_gh,
    days: int | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """All runs for `workflow`, newest first, server-side filtered to `--created >=<cutoff
    date>` when `days` is given. The `--created` filter matters, not just cosmetics: at this
    repo's CI volume a 7-day window can hold MORE than the 1000-result API ceiling (measured:
    1115 runs on 2026-09-10 for a 7-day tests.yml query), so without a date filter the newest
    1000 results silently under-cover the requested window from the OLD end. `--created` still
    can't beat the 1000 cap on a truly high-volume week, but it prevents client-side -L alone
    from truncating harder than necessary. Cached raw (unfiltered further) under cache_dir so a
    re-run of this script (or a human) can inspect exactly what the API returned this harvest."""
    fields = "databaseId,event,headSha,headBranch,conclusion,status,createdAt,url"
    args = ["run", "list", "--repo", repo, "--workflow", workflow, "--json", fields, "-L", str(limit)]
    if days is not None:
        cutoff_date = ((now or datetime.now(timezone.utc)) - timedelta(days=days)).date().isoformat()
        args += ["--created", f">={cutoff_date}"]
    data = gh(args)
    cache_path(cache_dir, f"runs_{workflow}.json").write_text(json.dumps(data, indent=2))
    return data


def fetch_pr_head_sha(repo: str, number: int, cache_dir: Path, gh: Callable = run_gh) -> str | None:
    """The PR's REAL head commit (its own `pull_request`-event sha), not the queue ref's
    embedded sha (see module docstring). None means unreadable — count it, don't guess."""
    cp = cache_path(cache_dir, f"pr_{number}.json")
    if cp.exists():
        try:
            return json.loads(cp.read_text()).get("headRefOid")
        except json.JSONDecodeError:
            pass
    try:
        data = gh(["pr", "view", str(number), "--repo", repo, "--json", "headRefOid,number"])
    except GhError:
        return None
    cp.write_text(json.dumps(data))
    return data.get("headRefOid")


def fetch_run_jobs(repo: str, run_id: int, cache_dir: Path, gh: Callable = run_gh) -> list[dict]:
    cp = cache_path(cache_dir, f"jobs_{run_id}.json")
    if cp.exists():
        try:
            return json.loads(cp.read_text())
        except json.JSONDecodeError:
            pass
    try:
        data = gh(["run", "view", str(run_id), "--repo", repo, "--json", "jobs"])
    except GhError:
        return []
    jobs = data.get("jobs", [])
    cp.write_text(json.dumps(jobs))
    return jobs


def fetch_job_failed_tests(
    repo: str, job_id: int, cache_dir: Path, gh: Callable = run_gh
) -> list[str]:
    """Grep `FAILED ` lines out of a failing job's log and return the test ids that follow.

    `--allow-escape-sequences` is required, not cosmetic: measured live 2026-09-10, `gh api
    .../logs` on a colorized log (Playwright, npm audit — anything with ANSI codes) exits 1 with
    "the response contains terminal escape sequences" UNLESS this flag is passed, while a plain
    log (no ANSI codes) succeeds either way. Omitting it does not fail loudly — every colorized
    job's log silently came back empty, understating real coverage. GhError propagates to the
    caller here (unlike the other fetch_* helpers) precisely so that failure gets COUNTED
    (harvest()'s gh_errors) instead of read as "genuinely no failing test id in this log", which
    a caught-and-swallowed exception would indistinguishably produce."""
    cp = cache_path(cache_dir, f"log_{job_id}.txt")
    if cp.exists():
        text = cp.read_text(errors="replace")
    else:
        text = gh(
            ["api", "--allow-escape-sequences", f"repos/{repo}/actions/jobs/{job_id}/logs"],
            raw=True,
            timeout=120,
        )
        cp.write_text(text)
    return extract_failed_test_ids(text)


# ---------------------------------------------------------------------------
# Pure logic — unit-tested directly, no network.
# ---------------------------------------------------------------------------


def extract_pr_number_from_queue_ref(head_branch: str) -> int | None:
    """`gh-readonly-queue/main/pr-6058-<sha>` -> 6058. None if head_branch isn't a queue ref."""
    m = QUEUE_REF_RE.match(head_branch)
    return int(m.group(1)) if m else None


def extract_failed_test_ids(log_text: str) -> list[str]:
    """`FAILED tests/test_foo.py::test_bar - AssertionError: ...` -> "tests/test_foo.py::test_bar".
    Order-preserving, one id per matching line."""
    return [m.group(1) for line in log_text.splitlines() if (m := FAILED_LINE_RE.match(line))]


def within_window(created_at: str, cutoff: datetime) -> bool:
    ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return ts >= cutoff


def filter_runs(runs: list[dict], days: int, now: datetime | None = None) -> list[dict]:
    """Keep only completed pull_request/merge_group runs inside the last `days` days."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    return [
        r
        for r in runs
        if r.get("event") in ("pull_request", "merge_group")
        and r.get("status") == "completed"
        and r.get("createdAt")
        and within_window(r["createdAt"], cutoff)
    ]


def index_pr_runs_by_sha(runs: list[dict]) -> dict[str, list[dict]]:
    by_sha: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        if r.get("event") == "pull_request":
            by_sha[r["headSha"]].append(r)
    return dict(by_sha)


def group_merge_group_runs_by_pr(runs: list[dict]) -> dict[int, list[dict]]:
    by_pr: dict[int, list[dict]] = defaultdict(list)
    for r in runs:
        if r.get("event") != "merge_group":
            continue
        n = extract_pr_number_from_queue_ref(r.get("headBranch", ""))
        if n is not None:
            by_pr[n].append(r)
    for runs_for_pr in by_pr.values():
        runs_for_pr.sort(key=lambda r: r["createdAt"])
    return dict(by_pr)


def find_matching_pr_run(pr_runs_by_sha: dict[str, list[dict]], head_sha: str | None) -> dict | None:
    """The `pull_request` run whose OWN headSha equals the PR's real head commit. If several
    (reruns), the latest by createdAt is the run of record."""
    if head_sha is None:
        return None
    candidates = pr_runs_by_sha.get(head_sha)
    if not candidates:
        return None
    return max(candidates, key=lambda r: r["createdAt"])


@dataclass
class PairResult:
    """One (run_a, run_b) comparison, same PR, same job name."""

    job_name: str
    kind: str  # "pr_vs_queue" | "queue_reentry"
    run_a_id: int
    run_b_id: int
    conclusion_a: str
    conclusion_b: str
    category: str  # "flake_candidate" | "real_red" | "both_success" | "not_comparable"
    failing_run_id: int | None = None
    failing_job_id: int | None = None


def classify_job_pair(name: str, job_a: dict, job_b: dict, run_a_id: int, run_b_id: int, kind: str) -> PairResult:
    ca, cb = job_a.get("conclusion", ""), job_b.get("conclusion", "")
    if ca not in COMPARABLE_CONCLUSIONS or cb not in COMPARABLE_CONCLUSIONS:
        category = "not_comparable"
        failing_run, failing_job = None, None
    elif ca == "success" and cb == "success":
        category = "both_success"
        failing_run, failing_job = None, None
    elif ca == "failure" and cb == "failure":
        category = "real_red"
        failing_run, failing_job = None, None
    else:
        category = "flake_candidate"
        if ca == "failure":
            failing_run, failing_job = run_a_id, job_a.get("databaseId")
        else:
            failing_run, failing_job = run_b_id, job_b.get("databaseId")
    return PairResult(
        job_name=name,
        kind=kind,
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        conclusion_a=ca,
        conclusion_b=cb,
        category=category,
        failing_run_id=failing_run,
        failing_job_id=failing_job,
    )


def pair_jobs(
    jobs_a: list[dict], jobs_b: list[dict], run_a_id: int, run_b_id: int, kind: str
) -> list[PairResult]:
    """Match jobs present in BOTH runs by exact name and classify each pair."""
    by_name_b = {j["name"]: j for j in jobs_b}
    results = []
    for job_a in jobs_a:
        job_b = by_name_b.get(job_a["name"])
        if job_b is None:
            continue
        results.append(classify_job_pair(job_a["name"], job_a, job_b, run_a_id, run_b_id, kind))
    return results


@dataclass
class JobStats:
    candidates: int = 0
    observations: int = 0
    real_red: int = 0
    run_ids: list[int] = field(default_factory=list)


def aggregate(pairs: list[PairResult]) -> dict[str, JobStats]:
    stats: dict[str, JobStats] = defaultdict(JobStats)
    for p in pairs:
        if p.category == "not_comparable":
            continue
        s = stats[p.job_name]
        s.observations += 1
        if p.category == "flake_candidate":
            s.candidates += 1
            s.run_ids.extend([p.run_a_id, p.run_b_id])
        elif p.category == "real_red":
            s.real_red += 1
    return dict(stats)


# ---------------------------------------------------------------------------
# Live harvest — orchestrates the gh wire + pure logic above.
# ---------------------------------------------------------------------------


@dataclass
class HarvestResult:
    repo: str
    workflow: str
    days: int
    generated_at: str
    total_runs_scanned: int
    pr_runs: int
    merge_group_runs: int
    unique_prs_in_queue: int
    prs_unreadable: int
    prs_no_matching_pr_run: int
    pairs: list[PairResult]
    stats: dict[str, JobStats]
    failed_test_counts: Counter
    gh_errors: int
    raw_runs_fetched: int = 0
    effective_days_covered: float | None = None
    window_truncated: bool = False


def compute_effective_coverage(all_runs: list[dict], limit: int, now: datetime) -> tuple[float | None, bool]:
    """How many days back the fetched (pre-filter) runs actually reach, and whether the fetch
    hit the API's hard result ceiling — i.e. the requested window may be under-covered from the
    OLD end. None if there are no runs to measure from."""
    dates = [r["createdAt"] for r in all_runs if r.get("createdAt")]
    if not dates:
        return None, False
    earliest = min(datetime.fromisoformat(d.replace("Z", "+00:00")) for d in dates)
    effective_days = (now - earliest).total_seconds() / 86400
    truncated = len(all_runs) >= limit
    return round(effective_days, 1), truncated


def harvest(
    repo: str,
    workflow: str,
    days: int,
    limit: int,
    cache_dir: Path,
    max_workers: int,
    gh: Callable = run_gh,
) -> HarvestResult:
    now = datetime.now(timezone.utc)
    all_runs = fetch_workflow_runs(repo, workflow, limit, cache_dir, gh=gh, days=days, now=now)
    effective_days_covered, window_truncated = compute_effective_coverage(all_runs, limit, now)
    runs = filter_runs(all_runs, days, now=now)
    pr_runs = [r for r in runs if r["event"] == "pull_request"]
    mg_runs = [r for r in runs if r["event"] == "merge_group"]

    pr_runs_by_sha = index_pr_runs_by_sha(runs)
    mg_by_pr = group_merge_group_runs_by_pr(mg_runs)

    gh_errors = 0
    prs_unreadable = 0
    prs_no_match = 0
    head_sha_by_pr: dict[int, str | None] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {
            pool.submit(fetch_pr_head_sha, repo, n, cache_dir, gh): n for n in mg_by_pr
        }
        for fut in as_completed(futs):
            n = futs[fut]
            try:
                head_sha_by_pr[n] = fut.result()
            except Exception:
                head_sha_by_pr[n] = None
                gh_errors += 1
            if head_sha_by_pr[n] is None:
                prs_unreadable += 1

    # Build the pair worklist: (kind, run_a, run_b) needing job comparisons.
    job_fetch_ids: set[int] = set()
    pending_pairs: list[tuple[str, dict, dict]] = []
    for n, mg_list in mg_by_pr.items():
        head_sha = head_sha_by_pr.get(n)
        pr_run = find_matching_pr_run(pr_runs_by_sha, head_sha)
        if pr_run is None and head_sha is not None:
            prs_no_match += 1
        if pr_run is not None:
            for mg_run in mg_list:
                pending_pairs.append(("pr_vs_queue", pr_run, mg_run))
                job_fetch_ids.add(pr_run["databaseId"])
                job_fetch_ids.add(mg_run["databaseId"])
        for i in range(len(mg_list) - 1):
            pending_pairs.append(("queue_reentry", mg_list[i], mg_list[i + 1]))
            job_fetch_ids.add(mg_list[i]["databaseId"])
            job_fetch_ids.add(mg_list[i + 1]["databaseId"])

    jobs_by_run: dict[int, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {
            pool.submit(fetch_run_jobs, repo, rid, cache_dir, gh): rid for rid in job_fetch_ids
        }
        for fut in as_completed(futs):
            rid = futs[fut]
            try:
                jobs_by_run[rid] = fut.result()
            except Exception:
                jobs_by_run[rid] = []
                gh_errors += 1

    all_pairs: list[PairResult] = []
    for kind, run_a, run_b in pending_pairs:
        ja = jobs_by_run.get(run_a["databaseId"], [])
        jb = jobs_by_run.get(run_b["databaseId"], [])
        all_pairs.extend(pair_jobs(ja, jb, run_a["databaseId"], run_b["databaseId"], kind))

    stats = aggregate(all_pairs)

    # Pull failing-job logs for flake candidates only, capped so a bad week doesn't storm the API.
    failing_ids = {
        (p.failing_run_id, p.failing_job_id)
        for p in all_pairs
        if p.category == "flake_candidate" and p.failing_job_id is not None
    }
    failed_test_counts: Counter = Counter()
    LOG_FETCH_CAP = 60
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {
            pool.submit(fetch_job_failed_tests, repo, job_id, cache_dir, gh): job_id
            for _, job_id in list(failing_ids)[:LOG_FETCH_CAP]
        }
        for fut in as_completed(futs):
            try:
                for tid in fut.result():
                    failed_test_counts[tid] += 1
            except Exception:
                gh_errors += 1

    return HarvestResult(
        repo=repo,
        workflow=workflow,
        days=days,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        total_runs_scanned=len(runs),
        pr_runs=len(pr_runs),
        merge_group_runs=len(mg_runs),
        unique_prs_in_queue=len(mg_by_pr),
        prs_unreadable=prs_unreadable,
        prs_no_matching_pr_run=prs_no_match,
        pairs=all_pairs,
        stats=stats,
        failed_test_counts=failed_test_counts,
        gh_errors=gh_errors,
        raw_runs_fetched=len(all_runs),
        effective_days_covered=effective_days_covered,
        window_truncated=window_truncated,
    )


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------


def render_markdown(r: HarvestResult, top_n: int = DEFAULT_TOP_N) -> str:
    lines: list[str] = []
    lines.append(f"# Flaky-test harvest — {r.repo} / {r.workflow}")
    lines.append("")
    lines.append(f"Generated: {r.generated_at} · window: last {r.days} days")
    lines.append("")
    lines.append(
        f"**Quarantine thresholds (>= {THRESHOLD_MIN_FAILURES} failures on >= "
        f"{THRESHOLD_MIN_RUNS} runs, {THRESHOLD_SUITE_CAP_PCT}% suite cap, "
        f"{THRESHOLD_EXPIRY_NOTE}) are NOT applied — owner ruling pending.** "
        "This is a measurement report only: no test was skipped, no job disabled, no PR touched."
    )
    lines.append("")
    lines.append("## Pairing method (read this before the numbers)")
    lines.append("")
    lines.append(
        "The queue ref `gh-readonly-queue/main/pr-<N>-<sha>` does NOT carry PR <N>'s own head "
        "commit — GitHub's merge queue stacks entries, so `<sha>` is the synthetic head of the "
        "entry ahead of <N> in the queue. Pairing on that sha against a `pull_request` run's "
        "headSha was measured live and matches almost nothing. This report instead extracts the "
        "PR NUMBER from the ref, resolves the PR's real head via `gh pr view`, and matches that "
        "against `pull_request`-event runs' own headSha."
    )
    lines.append("")
    if r.window_truncated:
        lines.append(
            f"**Window coverage finding:** requested {r.days} days, but `gh`'s workflow-run "
            f"listing hard-caps at {r.raw_runs_fetched} results (confirmed live: the API's own "
            "`total_count` exceeded what page-by-page fetching actually returns) — at this "
            f"repo's CI volume that only reaches back **{r.effective_days_covered} days**, not "
            f"{r.days}. Everything below is honest about that smaller window, not a silent "
            "under-count."
        )
        lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    lines.append(f"| Runs scanned (pull_request + merge_group, completed) | {r.total_runs_scanned} |")
    lines.append(f"| `pull_request` runs | {r.pr_runs} |")
    lines.append(f"| `merge_group` runs | {r.merge_group_runs} |")
    lines.append(f"| Unique PRs seen in the queue | {r.unique_prs_in_queue} |")
    lines.append(f"| PRs unreadable via `gh pr view` | {r.prs_unreadable} |")
    lines.append(f"| PRs with no matching `pull_request` run in window | {r.prs_no_matching_pr_run} |")
    pr_vs_queue = sum(1 for p in r.pairs if p.kind == "pr_vs_queue")
    reentry = sum(1 for p in r.pairs if p.kind == "queue_reentry")
    lines.append(f"| Job-pair comparisons: pr_vs_queue | {pr_vs_queue} |")
    lines.append(f"| Job-pair comparisons: queue_reentry | {reentry} |")
    total_candidates = sum(s.candidates for s in r.stats.values())
    total_real_red = sum(s.real_red for s in r.stats.values())
    lines.append(f"| Flake candidates (conclusion flipped, no diff) | {total_candidates} |")
    lines.append(f"| Real reds (failed in both runs — not a flake) | {total_real_red} |")
    lines.append(f"| gh call errors (counted, not guessed) | {r.gh_errors} |")
    lines.append("")

    if r.prs_no_matching_pr_run and r.unique_prs_in_queue:
        pct = 100 * r.prs_no_matching_pr_run / r.unique_prs_in_queue
        lines.append(
            f"**Finding:** {r.prs_no_matching_pr_run}/{r.unique_prs_in_queue} "
            f"({pct:.0f}%) of queued PRs had no `pull_request` run with a matching headSha "
            "inside the 7-day window (older run, rerun-without-cache-hit, or the run itself "
            "fell outside the window). That is a finding about window coverage, not a script bug."
        )
        lines.append("")

    lines.append("## Flake candidates by job")
    lines.append("")
    if not r.stats:
        lines.append("No comparable job pairs found this window.")
    else:
        lines.append("| Job | Candidates | Observations | Real reds | Run ids |")
        lines.append("|---|---|---|---|---|")
        for name, s in sorted(r.stats.items(), key=lambda kv: kv[1].candidates, reverse=True):
            if s.candidates == 0:
                continue
            ids = ", ".join(str(i) for i in s.run_ids[:8])
            if len(s.run_ids) > 8:
                ids += f", … (+{len(s.run_ids) - 8})"
            lines.append(f"| {name} | {s.candidates} | {s.observations} | {s.real_red} | {ids} |")
        if not any(s.candidates for s in r.stats.values()):
            lines.append("| _(none — every comparable pair was consistent)_ | 0 | | | |")
    lines.append("")

    lines.append(f"## Top {top_n} failing test ids on flake-candidate runs")
    lines.append("")
    if not r.failed_test_counts:
        lines.append(
            "No test ids extracted — no flake-candidate log matched a `FAILED ` line this "
            "window (or none could be fetched). This usually means the candidates above are "
            "JOB-level failures — an external service error, a container/setup step, or an "
            "aggregator job like `Test Summary` — rather than a specific pytest/Playwright "
            "assertion; open the job list above and read the run's own log for the actual "
            "cause. That is itself a finding about this window's flake granularity, not an "
            "extraction bug."
        )
    else:
        lines.append("| Test id | Occurrences |")
        lines.append("|---|---|")
        for tid, count in r.failed_test_counts.most_common(top_n):
            lines.append(f"| `{tid}` | {count} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mailbox delivery — mirrors scripts/queue_stall_notify.py::send_notification's fleet_mail.sh
# argv shape.
# ---------------------------------------------------------------------------


def send_to_mailbox(
    summary: str, *, host: str, key: str, ttl_hours: int, repo_root: Path = REPO_ROOT
) -> tuple[bool, str]:
    fleet_mail = repo_root / "scripts" / "fleet_mail.sh"
    if not fleet_mail.is_file():
        return False, f"fleet_mail.sh not found at {fleet_mail}"
    proc = subprocess.run(
        ["bash", str(fleet_mail), host, "broadcast", "--key", key, "--ttl", str(ttl_hours), summary],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return False, f"mailbox send FAILED rc={proc.returncode}: {proc.stderr.strip()[:300]}"
    return True, proc.stdout.strip() or "sent"


def build_mailbox_summary(r: HarvestResult) -> str:
    # datetime.now() (LOCAL, not UTC) deliberately, matching main()'s own report-path default:
    # this fleet's cron convention is WITA (this repo's machines run their system clock in
    # WITA — verified live, `date +%Z` on this box), and a harvest that runs near midnight UTC
    # is already the next WITA day. Using UTC here would name the mailbox's own Report: line
    # after a file the write step (same local-date rule) did NOT actually produce.
    total_candidates = sum(s.candidates for s in r.stats.values())
    top_jobs = sorted(r.stats.items(), key=lambda kv: kv[1].candidates, reverse=True)
    top_jobs = [n for n, s in top_jobs if s.candidates > 0][:3]
    jobs_note = f" top: {', '.join(top_jobs)}" if top_jobs else ""
    return (
        f"flaky-harvest: {r.days}d window, {r.total_runs_scanned} runs scanned, "
        f"{total_candidates} flake candidates across {len(r.stats)} jobs.{jobs_note} "
        "Thresholds NOT applied — owner ruling pending. Report: "
        f"docs/reports/flaky-harvest/{datetime.now():%Y-%m-%d}.md"
    )


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2] if __doc__ else "flaky_harvest")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--limit", type=int, default=DEFAULT_RUN_LIMIT)
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument(
        "--cache-dir",
        default=os.path.join(os.environ.get("TMPDIR", "/tmp"), "flaky_harvest"),
    )
    parser.add_argument("--output", default=None, help="markdown output path (default: docs/reports/flaky-harvest/<date>.md)")
    parser.add_argument("--no-write", action="store_true", help="print to stdout only, do not write the report file")
    parser.add_argument("--no-mailbox", action="store_true", help="skip the fleet-mailbox broadcast")
    parser.add_argument("--mailbox-host", default=os.environ.get("FLAKY_HARVEST_MAILBOX_HOST", "pro"))
    parser.add_argument("--mailbox-key", default="flaky-harvest:weekly")
    parser.add_argument("--mailbox-ttl-hours", type=int, default=192)
    args = parser.parse_args(argv)

    cache_dir = Path(args.cache_dir)
    try:
        result = harvest(
            args.repo, args.workflow, args.days, args.limit, cache_dir, args.max_workers
        )
    except GhError as exc:
        print(f"flaky_harvest: FAILED to fetch runs: {exc}", file=sys.stderr)
        return 1

    report = render_markdown(result, top_n=args.top_n)
    print(report)

    if not args.no_write:
        out_path = Path(args.output) if args.output else (
            REPO_ROOT / "docs" / "reports" / "flaky-harvest" / f"{datetime.now():%Y-%m-%d}.md"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report)
        print(f"flaky_harvest: wrote {out_path}", file=sys.stderr)

    if not args.no_mailbox:
        summary = build_mailbox_summary(result)
        ok, detail = send_to_mailbox(
            summary, host=args.mailbox_host, key=args.mailbox_key, ttl_hours=args.mailbox_ttl_hours
        )
        print(f"flaky_harvest: mailbox {'OK' if ok else 'FAILED'}: {detail}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
