#!/usr/bin/env python3
"""queue_baseline_probe.py — Merge-OS v2 Wave 1 baseline organ (MEASURE ONLY, no behavior change).

Spec: research/operations/2026-08-10-merge-os-v2-submission-system.md §4 "Wave 1 — the
baseline organ (7 days, NO behavior change)". This script changes nothing about how PRs are
gated, merged, or run — it only RECORDS what already happened, once per UTC day, so later
waves (§4 Wave 2+) have a measured denominator instead of a guess (spec §1: "savings claim
... unknown until the baseline organ runs").

Invoked nightly (Pro, 03:40 WITA) by infra/launchagents/wrappers/queue-baseline.sh via the
(not-yet-armed — W81, built≠armed) com.nuzantara.queue-baseline.plist.template. Writes one
record per day to `~/.nuzantara-mq/baseline/YYYY-MM-DD.json`.

WHAT IS RECORDED (spec §4 Wave 1 bullet list, this organ's subset):
  1. billed minutes per PR              -> see "DECLARED ATTRIBUTION RULE" below
  2. queue transit p50/p95              -> auto-merge enabledAt -> mergedAt, PRs merged that day
  3. ejection count BY CLASS and BY AUTHOR CLASS -> heuristic, see "DECLARED EJECTION HEURISTIC"
  4. slot utilization                   -> today's runner-minutes vs a measured weekly-capacity
                                            constant (see WEEKLY_CI_CAPACITY_SLOT_MINUTES)
Heal-drift frequency (also named in spec §4 Wave 1) is NOT recorded by this organ — it is a
property of the heal-as-PR mechanism (spec §2.2), which does not exist yet (Wave 3, BLOCKED
pending isolation proof per spec §7.6). Recording a heal-drift number here would be inventing
data for a mechanism that has never run — out of scope for this PR, not silently dropped.

DECLARED ATTRIBUTION RULE (spec §4, Codex CONFIRMED-DEFECT F6 — verbatim requirement):
  GitHub's Actions billing/usage endpoints report AGGREGATE usage only. "Billed minutes/PR"
  is computed here as: per-run billable minutes via
      GET /repos/{owner}/{repo}/actions/runs/{run_id}/timing
  summed over every run attached to a PR — its own `pull_request`-event runs (via the run's
  own `pull_requests[]` field) PLUS any `merge_group`-event run it was a member of.
  For a `merge_group` run covering N member PRs, this organ picks the EVEN-SPLIT option the
  spec declares acceptable ("divide the merge-group run's billed minutes evenly across its N
  member PRs, or attribute in full to each — either is acceptable, but the rule must be
  written down and applied consistently"): each member PR receives (run minutes / N).
  Membership is extracted best-effort from the merge_group run's `head_branch` and
  `display_title` fields (GitHub's merge_group event does not expose `pull_requests[]`) via
  `extract_merge_group_pr_numbers()`. When membership cannot be derived (regex finds nothing),
  the run's minutes are NEVER dropped — they land in `unattributed_group_minutes`
  (scar family #2 "esiste != armato" / "no silent caps": an empty bucket must mean zero
  activity, never zero because the code gave up quietly).
  A `pull_request`-event run whose own `pull_requests[]` is empty (known GitHub API gap for
  runs triggered from a forked repo) is handled the same way: its minutes land in
  `unattributed_pr_minutes`, never dropped.
  Runs that are neither `pull_request` nor `merge_group` (push/schedule/workflow_dispatch/...)
  are not part of per-PR attribution by construction; their minutes land in
  `other_event_minutes` and still count toward `slot_utilization.runner_minutes_today`.

  TIMING SOURCE: private-repo billing buckets expose non-zero `billable.*.total_ms`; this
  repository is public, so those buckets are present but zero. In that case the same timing
  endpoint exposes `run_duration_ms`, which is used as the effective runner duration and
  recorded under `timing_sources.run_duration`. A run with zero billable milliseconds and no
  duration (for example a skipped run that never started a job) contributes zero under
  `timing_sources.billable_zero_without_duration`. This fallback measures runner consumption,
  not a monetary charge; the source counts in every record keep that distinction explicit.

DECLARED EJECTION HEURISTIC (spec §4 Wave 1 bullet: "heuristic from failed merge_group run
conclusions/log heads — declare the heuristic in the docstring"):
  A merge_group run whose conclusion is one of {"failure", "cancelled", "timed_out"} counts as
  one ejection. Class is assigned from run/job METADATA (never raw log bytes — a deliberate
  simplification: job/step names + conclusions are cheap, reliable, and avoid downloading
  potentially large log blobs on every nightly run):
    1. run conclusion in {"cancelled", "timed_out"}          -> INFRA (GH-level, no test ran
                                                                  to completion)
    2. run conclusion == "failure": fetch the run's jobs (GET .../actions/runs/{id}/jobs);
       any job whose OWN conclusion is cancelled/timed_out, or whose conclusion is "failure"
       AND whose name matches an infra-flavoured signature (setup/checkout/cache/docker/
       runner — see INFRA_JOB_NAME_SIGNATURES) -> INFRA; otherwise -> CODE.
    3. any other conclusion reaching this function is unexpected for an "ejection" and is
       recorded as an error entry, defaulted to CODE (conservative: never silently invented
       as FLAKE).
  FLAKE is a THIRD declared bucket that this Wave-1 heuristic can never populate on its own:
  distinguishing a flaky test from a first-time code failure needs the differential re-run
  verdict from spec §3 ("Differential flake verdict with a valid control"), which is Wave 4
  and does not exist yet. `ejections.by_class.FLAKE` is therefore always 0 here BY
  CONSTRUCTION — an honest declared limitation, not a claim that no flakes occurred.
  Author class (human / agent / bot — Codex F16's split) is resolved from the FIRST derivable
  member PR of an ejected merge_group run (`gh pr view <n> --json author,headRefName`):
  headRefName starting with "agent/" -> agent; author login ending "[bot]" or in a small known
  bot-login allowlist -> bot; else -> human. When no member PR is derivable, the ejection is
  counted under `by_author_class.unknown` (never dropped) and logged as an error entry.

QUEUE TRANSIT (spec §4 Wave 1 + team direction): for every PR merged that UTC day
(`gh pr list --state merged --search "merged:<day>"`), transit minutes = mergedAt minus the
PR's auto-merge enabledAt. `enabledAt` is read via `autoMergeRequest.enabledAt`
(GitHub GraphQL — the same field this repo's merge-queue tooling already reads, cf.
docs/runbooks/merge-queue-discipline.md and scar W111). If GraphQL returns no
`autoMergeRequest` (already merged PRs can lose this field once the auto-merge request
resolves) the PR's number is recorded under `transit_unmeasured_prs` and excluded from the
p50/p95 sample — never guessed, never silently dropped from the record.

SLOT UTILIZATION: `runner_minutes_today` is the sum of EVERY run's billable minutes that day
(attributed + unattributed + other-event) — no extra API calls, it reuses the timing fetched
for attribution. It is compared against a fixed weekly-capacity constant,
WEEKLY_CI_CAPACITY_SLOT_MINUTES, derived from the round-3 system-wide measurement
(research/operations/2026-08-10-queue-acceleration-round3-system-wide.md, "One sentence": "the
two heavy workflows ... ~=97k slot-min/wk ~=48% of total CI capacity", 2026-08-09/10 measurement
window) as 97_000 / 0.48. This is a SNAPSHOT CONSTANT, not re-measured live by this script —
declared here so a future maintainer updates it deliberately if a fresher measurement lands,
rather than this organ silently reporting utilization against a stale denominator forever.

FAIL-VISIBLE (scar family #2, "esiste != armato" — an empty record with exit 0 is forbidden):
every `gh` denial, timeout, or unparseable response is appended to the record's top-level
`errors` array as a plain string. The record is ALWAYS written, even when everything failed —
a day with real zero activity (empty `errors`, zero counts) is a different, legitimate,
positive record; this script never conflates the two. `main()` returns 0 only when `errors`
is empty; any non-empty `errors` list makes the process exit 1 so the wrapper's rc-based
alerting (W101 discipline) sees the failure.

The workflow-runs endpoint is also census-checked: every paginated response's `total_count` is
compared with the number of unique run IDs actually fetched. GitHub's REST docs state the
`actions/runs` endpoint "will return up to 1,000 results" for any query using the `created`
filter (docs.github.com/en/rest/actions/workflow-runs) — confirmed empirically 2026-08-12
(`fetched=1000 reported_total=10269`, ~90% of that day's PRs unattributed). `--paginate`
cannot get past this: the cap is server-side per QUERY, not a client pagination limit, so the
only way past it is to narrow the query itself.

MITIGATION — time-window bisection (see `_fetch_runs_window` / `list_workflow_runs`): whenever
a window's raw fetch hits the documented cap (>= PAGE_CAP items) while its own `total_count`
reports more, the window is split into two equal halves by `created` timestamp and each half is
fetched independently, recursing until every leaf window's fetch is complete. Runs are deduped
by id across sibling windows (dict keyed by run id), so any inclusive-boundary overlap between
adjacent windows costs nothing. Recursion is bounded (`MAX_BISECT_DEPTH`, `MIN_WINDOW_SECONDS`):
a leaf window still short after being split down to that bound is a genuine, reported shortfall
— written to `errors[]` exactly like before, never silently dropped (scar family #2, and W97:
a list consumed as complete must actually be complete). A shortfall NOT explained by the
documented cap (raw fetch below `PAGE_CAP` yet still short of `total_count` — a data anomaly,
not a capacity limit) is reported immediately without attempting to bisect, since a narrower
window cannot return more than a wider one already did in that case.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("queue_baseline_probe")

DEFAULT_REPO = "Bali-Zero/Teman2"
DEFAULT_OUT_DIR = Path.home() / ".nuzantara-mq" / "baseline"
SCHEMA_VERSION = 2

TimingSource = Literal["billable", "run_duration", "billable_zero_without_duration"]

# round-3 system-wide doc, 2026-08-09/10 measurement window (see module docstring). A snapshot
# constant, not re-measured live by this script.
WEEKLY_CI_CAPACITY_SLOT_MINUTES = 97_000.0 / 0.48

INFRA_JOB_NAME_SIGNATURES = (
    "set up job",
    "complete job",
    "checkout",
    "cache",
    "setup-",
    "set up ",
    "docker",
    "runner",
)

BOT_LOGIN_ALLOWLIST = (
    "dependabot[bot]",
    "renovate[bot]",
    "github-actions[bot]",
    "copilot[bot]",
    "codex[bot]",
)

GH_TIMEOUT_LIST_RUNS = 120
GH_TIMEOUT_SHORT = 30

# GitHub REST docs: the `actions/runs` endpoint returns "up to 1,000 results" for any query
# using the `created` filter (docs.github.com/en/rest/actions/workflow-runs) — a server-side
# cap per query, not a client-side pagination limit. Empirically confirmed 2026-08-12
# (fetched=1000 reported_total=10269). A window whose raw fetch reaches this many items while
# total_count reports more MUST be bisected — no amount of extra `--paginate` will get past it.
PAGE_CAP = 1000

# Bisection safety bound (scar W97 — never a silent truncation): a window still short of its
# own total_count after being split this many times is reported as a genuine shortfall in
# errors[], not silently dropped. depth=10 on a 24h day bottoms out at ~84s windows — ample
# for any CI burst this repo has produced to date; MIN_WINDOW_SECONDS is a second, independent
# floor so a pathological clock/interval bug can't recurse below whole-second granularity.
MAX_BISECT_DEPTH = 10
MIN_WINDOW_SECONDS = 1


# ---------------------------------------------------------------------------
# Pure functions (no I/O) — the math this organ exists to get right.
# ---------------------------------------------------------------------------


def extract_merge_group_pr_numbers(run: dict[str, Any]) -> list[int]:
    """Best-effort extraction of member PR numbers from a merge_group run.

    GitHub's merge_group event does not populate `pull_requests[]` (that field is only
    filled in for `pull_request`-event runs). This organ parses two fields instead, declared
    here so a future maintainer does not have to reverse-engineer it:
      1. `head_branch` (merge-queue refs carry `pr-<N>` segments, e.g.
         `gh-readonly-queue/main/pr-1234-<sha>`)
      2. `display_title` (GitHub sometimes synthesizes titles that enumerate member PRs as
         `#N`)
    Numbers found in either are unioned and sorted. An empty result means "not derivable" —
    the caller MUST route those minutes to unattributed_group_minutes, never drop them.
    """
    numbers: set[int] = set()
    for field in ("head_branch", "display_title"):
        text = str(run.get(field) or "")
        numbers.update(int(n) for n in re.findall(r"pr-(\d+)", text))
        numbers.update(int(n) for n in re.findall(r"#(\d+)", text))
    return sorted(numbers)


def percentile(values: list[float], pct: float) -> float | None:
    """Linear-interpolation percentile (numpy 'linear' method), dependency-free.

    Returns None for an empty sample — the caller decides how to render that (never coerced
    to 0.0, which would silently claim "measured, and it was zero").
    """
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ordered[int(k)]
    d0 = ordered[int(f)] * (c - k)
    d1 = ordered[int(c)] * (k - f)
    return d0 + d1


def classify_ejection(run: dict[str, Any], jobs: list[dict[str, Any]]) -> str:
    """Declared heuristic — see module docstring "DECLARED EJECTION HEURISTIC".

    Pure function: takes the run dict and its already-fetched jobs list, returns one of
    "INFRA" / "CODE". Never returns "FLAKE" — see docstring for why that bucket stays 0 in
    Wave 1 by construction.
    """
    conclusion = run.get("conclusion")
    if conclusion in ("cancelled", "timed_out"):
        return "INFRA"
    if conclusion != "failure":
        # Unexpected: caller only invokes this for runs it already believes are ejections.
        # Conservative default, never silently invented as something more specific.
        return "CODE"
    for job in jobs:
        job_conclusion = job.get("conclusion")
        if job_conclusion in ("cancelled", "timed_out"):
            return "INFRA"
        name = str(job.get("name") or "").lower()
        if job_conclusion == "failure" and any(sig in name for sig in INFRA_JOB_NAME_SIGNATURES):
            return "INFRA"
    return "CODE"


def classify_author(head_ref_name: str | None, author_login: str | None) -> str:
    """human / agent / bot split (Codex F16). Pure — no I/O."""
    if head_ref_name and head_ref_name.startswith("agent/"):
        return "agent"
    login = (author_login or "").strip()
    if login.endswith("[bot]") or login in BOT_LOGIN_ALLOWLIST:
        return "bot"
    return "human"


def allocate_run_minutes(
    run: dict[str, Any],
    minutes: float,
    billed_per_pr: dict[str, float],
    unattributed_group_minutes: list[float],
    unattributed_pr_minutes: list[float],
    other_event_minutes: list[float],
) -> None:
    """Apply the declared attribution rule (module docstring) for one run's billable minutes.

    Mutates the four accumulators in place — kept as explicit output params (not a return
    tuple of primitives) so the caller's running totals stay obviously the single source of
    truth across many calls in a loop, rather than re-summed from N tiny return values.
    """
    event = run.get("event")
    if event == "pull_request":
        prs = run.get("pull_requests") or []
        numbers = [str(pr["number"]) for pr in prs if isinstance(pr, dict) and "number" in pr]
        if not numbers:
            unattributed_pr_minutes.append(minutes)
            return
        share = minutes / len(numbers)
        for n in numbers:
            billed_per_pr[n] = billed_per_pr.get(n, 0.0) + share
    elif event == "merge_group":
        numbers = extract_merge_group_pr_numbers(run)
        if not numbers:
            unattributed_group_minutes.append(minutes)
            return
        share = minutes / len(numbers)
        for n in numbers:
            key = str(n)
            billed_per_pr[key] = billed_per_pr.get(key, 0.0) + share
    else:
        other_event_minutes.append(minutes)


# ---------------------------------------------------------------------------
# subprocess boundary — every gh call funnels through _run_gh so tests intercept one shape.
# ---------------------------------------------------------------------------


def _run_gh(cmd: list[str], timeout: int = GH_TIMEOUT_SHORT) -> subprocess.CompletedProcess[str]:
    """The one subprocess boundary this module crosses for `gh` calls.

    Never raises on a non-zero exit — callers judge `.returncode` and `.stdout`/`.stderr`
    separately (stdout != stderr, W104 discipline). May raise `subprocess.TimeoutExpired`;
    callers catch it explicitly so a slow API call degrades to a logged error, not a crash.
    """
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _parse_concatenated_json(text: str) -> list[dict[str, Any]]:
    """Parse zero or more whitespace-separated JSON objects (`gh api --paginate` output).

    `gh api --paginate` on a list endpoint emits one JSON document per page, concatenated on
    stdout — not a single merged array. Returns the list of page-documents; callers combine
    the array field they care about (e.g. `workflow_runs`) across pages themselves.
    """
    decoder = json.JSONDecoder()
    text = text.strip()
    objs: list[dict[str, Any]] = []
    idx = 0
    n = len(text)
    while idx < n:
        while idx < n and text[idx].isspace():
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(text, idx)
        objs.append(obj)
        idx = end
    return objs


# ---------------------------------------------------------------------------
# I/O-fetching functions — each returns (data, errors) and never raises for a normal gh
# failure; a genuinely unexpected exception (TimeoutExpired, OSError) is caught at the call
# site and turned into an error string too.
# ---------------------------------------------------------------------------


def _fetch_runs_window(
    repo: str,
    start: datetime,
    end: datetime,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]], int | None, int, list[str]]:
    """Fetch every page `gh api --paginate` will give us for one `[start, end]` UTC window
    (both ends inclusive, matching GitHub's `created` range-qualifier semantics).

    Pure I/O primitive — does not decide whether the window needs to be split further; that
    decision (and the resulting recursion) belongs to `list_workflow_runs` so this stays a
    single, independently testable fetch. Returns
    `(runs_by_id, runs_without_id, reported_total, raw_item_count, errors)` where
    `raw_item_count` is the number of `workflow_runs` entries actually returned across all
    pages BEFORE dedup — the number PAGE_CAP is measured against, since GitHub's documented
    1,000-result cap is on items served, not on the dedup'd id count a duplicate-emitting page
    could shrink it to (see `_parse_concatenated_json`'s docstring on that duplicate-page
    quirk).
    """
    created_query = f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}..{end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    cmd = [
        "gh", "api", f"repos/{repo}/actions/runs",
        "-X", "GET",
        "-f", f"created={created_query}",
        "-f", "per_page=100",
        "--paginate",
    ]
    errors: list[str] = []
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_LIST_RUNS)
    except subprocess.TimeoutExpired as exc:
        return {}, [], None, 0, [f"list_workflow_runs timeout window={created_query}: {exc}"]
    except OSError as exc:
        return {}, [], None, 0, [f"list_workflow_runs OSError window={created_query}: {exc}"]
    if proc.returncode != 0:
        return {}, [], None, 0, [
            f"list_workflow_runs failed window={created_query} rc={proc.returncode} "
            f"stderr={proc.stderr.strip()[:400]}"
        ]
    try:
        pages = _parse_concatenated_json(proc.stdout)
    except json.JSONDecodeError as exc:
        return {}, [], None, 0, [f"list_workflow_runs bad JSON window={created_query}: {exc}"]

    reported_totals = {
        int(page["total_count"])
        for page in pages
        if isinstance(page.get("total_count"), int)
    }
    reported_total = max(reported_totals) if reported_totals else None
    # The Actions endpoint reports the real total on the first page but can emit zero on
    # later `--paginate` pages. Treat zero as a pagination sentinel when a positive total
    # exists; conflicting positive totals remain fail-visible.
    positive_reported_totals = {total for total in reported_totals if total > 0}
    if len(positive_reported_totals) > 1:
        errors.append(
            "list_workflow_runs inconsistent positive total_count values across pages "
            f"window={created_query}: {sorted(positive_reported_totals)}"
        )
    if reported_total is None:
        errors.append(f"list_workflow_runs response missing integer total_count window={created_query}")

    runs_by_id: dict[int, dict[str, Any]] = {}
    runs_without_id: list[dict[str, Any]] = []
    raw_item_count = 0
    for page in pages:
        for run in page.get("workflow_runs") or []:
            raw_item_count += 1
            run_id = run.get("id") if isinstance(run, dict) else None
            if isinstance(run_id, int):
                runs_by_id[run_id] = run
            elif isinstance(run, dict):
                runs_without_id.append(run)
    return runs_by_id, runs_without_id, reported_total, raw_item_count, errors


def list_workflow_runs(
    repo: str,
    day: date,
) -> tuple[list[dict[str, Any]], int | None, list[str]]:
    """Workflow runs created on `day` (UTC), with an explicit census check.

    Returns `(unique_runs, reported_total, errors)`. `reported_total` is the day's real total
    (from the initial, unsplit day-wide query — bisection never changes what "the day's total"
    means, only how many requests it takes to actually fetch it).

    GitHub's `actions/runs` list endpoint returns "up to 1,000 results" for any query using
    the `created` filter (module docstring) — a cap on the QUERY, so `--paginate` alone cannot
    get past it. Whenever a window's raw fetch hits that cap (`>= PAGE_CAP`) while its own
    `total_count` says there is more, the window is bisected by `created` timestamp and each
    half is fetched independently, recursing until every leaf is fully resolved or the
    recursion bound (`MAX_BISECT_DEPTH` / `MIN_WINDOW_SECONDS`) is hit. A shortfall NOT
    explained by the cap (raw fetch below `PAGE_CAP`, yet still short of `total_count` — e.g. a
    data anomaly) is reported immediately without attempting to bisect: a narrower window
    cannot return more than a wider one already failed to.
    """
    day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1, seconds=-1)  # 23:59:59, inclusive-inclusive range

    runs_by_id: dict[int, dict[str, Any]] = {}
    runs_without_id: list[dict[str, Any]] = []
    errors: list[str] = []
    day_reported_total: list[int | None] = [None]  # set once, from the depth-0 (whole-day) fetch

    def _collect(start: datetime, end: datetime, depth: int) -> None:
        window_runs, window_no_id, reported_total, raw_count, window_errors = _fetch_runs_window(
            repo, start, end
        )
        errors.extend(window_errors)
        if depth == 0:
            day_reported_total[0] = reported_total
        runs_by_id.update(window_runs)
        runs_without_id.extend(window_no_id)

        unique_count = len(window_runs) + len(window_no_id)
        if reported_total is None or unique_count >= reported_total:
            return  # this window is fully accounted for (or totally unknown — nothing more to do)

        if raw_count < PAGE_CAP:
            # Short of total_count but never even reached the documented cap — not a
            # capacity problem, bisecting cannot help. Depth-0 keeps the exact historical
            # message shape (no window suffix) since that IS the whole-day window.
            if depth == 0:
                errors.append(
                    "list_workflow_runs pagination shortfall: "
                    f"fetched={unique_count} reported_total={reported_total}; record is partial"
                )
            else:
                errors.append(
                    "list_workflow_runs pagination shortfall: "
                    f"fetched={unique_count} reported_total={reported_total} "
                    f"window={start.isoformat()}..{end.isoformat()}; record is partial"
                )
            return

        window_seconds = (end - start).total_seconds()
        if depth >= MAX_BISECT_DEPTH or window_seconds <= MIN_WINDOW_SECONDS:
            errors.append(
                "list_workflow_runs pagination shortfall even after bisection: "
                f"fetched={unique_count} reported_total={reported_total} "
                f"window={start.isoformat()}..{end.isoformat()} depth={depth}; "
                "window not further splittable"
            )
            return

        mid = start + (end - start) / 2
        _collect(start, mid, depth + 1)
        _collect(mid, end, depth + 1)

    _collect(day_start, day_end, 0)

    runs = [*runs_by_id.values(), *runs_without_id]
    return runs, day_reported_total[0], errors


def fetch_run_timing_minutes(
    repo: str,
    run_id: int,
) -> tuple[float | None, TimingSource | None, str | None]:
    """GET .../timing -> minutes, declared timing source, and error.

    Non-zero billable buckets win. Public repositories report those buckets as zero, so
    `run_duration_ms` is the declared fallback. If both are zero/absent, the run contributes
    an explicit zero-duration source (the normal shape for a skipped run).
    """
    cmd = ["gh", "api", f"repos/{repo}/actions/runs/{run_id}/timing"]
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_SHORT)
    except subprocess.TimeoutExpired as exc:
        return None, None, f"timing fetch timeout run={run_id}: {exc}"
    except OSError as exc:
        return None, None, f"timing fetch OSError run={run_id}: {exc}"
    if proc.returncode != 0:
        return None, None, (
            f"timing fetch failed run={run_id} rc={proc.returncode} "
            f"stderr={proc.stderr.strip()[:300]}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return None, None, f"timing fetch bad JSON run={run_id}: {exc}"
    billable = payload.get("billable") or {}
    total_ms = 0
    for _os_name, os_data in billable.items():
        if isinstance(os_data, dict):
            total_ms += int(os_data.get("total_ms") or 0)
    if total_ms > 0:
        return total_ms / 60000.0, "billable", None

    run_duration_ms = payload.get("run_duration_ms")
    if isinstance(run_duration_ms, (int, float)) and run_duration_ms >= 0:
        return float(run_duration_ms) / 60000.0, "run_duration", None

    return 0.0, "billable_zero_without_duration", None


def fetch_run_jobs(repo: str, run_id: int) -> tuple[list[dict[str, Any]], str | None]:
    """GET .../actions/runs/{run_id}/jobs -> jobs list (name/conclusion), for ejection class."""
    cmd = ["gh", "api", f"repos/{repo}/actions/runs/{run_id}/jobs", "-f", "per_page=100"]
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_SHORT)
    except subprocess.TimeoutExpired as exc:
        return [], f"jobs fetch timeout run={run_id}: {exc}"
    except OSError as exc:
        return [], f"jobs fetch OSError run={run_id}: {exc}"
    if proc.returncode != 0:
        return [], (
            f"jobs fetch failed run={run_id} rc={proc.returncode} "
            f"stderr={proc.stderr.strip()[:300]}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return [], f"jobs fetch bad JSON run={run_id}: {exc}"
    return payload.get("jobs") or [], None


def fetch_merged_prs(repo: str, day: date) -> tuple[list[dict[str, Any]], list[str]]:
    """PRs merged on `day` (UTC) via GitHub search `merged:<day>`."""
    cmd = [
        "gh", "pr", "list",
        "--repo", repo,
        "--state", "merged",
        "--search", f"merged:{day.isoformat()}",
        "--json", "number,mergedAt,author,headRefName",
        "--limit", "200",
    ]
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_SHORT)
    except subprocess.TimeoutExpired as exc:
        return [], [f"fetch_merged_prs timeout: {exc}"]
    except OSError as exc:
        return [], [f"fetch_merged_prs OSError: {exc}"]
    if proc.returncode != 0:
        return [], [f"fetch_merged_prs failed rc={proc.returncode} stderr={proc.stderr.strip()[:400]}"]
    try:
        prs = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return [], [f"fetch_merged_prs bad JSON: {exc}"]
    if not isinstance(prs, list):
        return [], [f"fetch_merged_prs unexpected payload shape: {type(prs).__name__}"]
    return prs, []


_AUTOMERGE_QUERY = (
    "query($owner:String!,$name:String!,$number:Int!){"
    "repository(owner:$owner,name:$name){"
    "pullRequest(number:$number){autoMergeRequest{enabledAt}}}}"
)


def fetch_automerge_enabled_at(repo: str, pr_number: int) -> tuple[str | None, str | None]:
    """GraphQL autoMergeRequest.enabledAt for one PR. Returns (iso-ts-or-None, error-or-None).

    A None `enabledAt` with no error means "GitHub genuinely has no value" (e.g. the
    auto-merge request already resolved and GitHub stopped exposing it) — the caller routes
    that PR to transit_unmeasured_prs, distinct from an actual fetch error.
    """
    owner, _, name = repo.partition("/")
    cmd = [
        "gh", "api", "graphql",
        "-f", f"query={_AUTOMERGE_QUERY}",
        "-F", f"owner={owner}",
        "-F", f"name={name}",
        "-F", f"number={pr_number}",
    ]
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_SHORT)
    except subprocess.TimeoutExpired as exc:
        return None, f"automerge fetch timeout pr={pr_number}: {exc}"
    except OSError as exc:
        return None, f"automerge fetch OSError pr={pr_number}: {exc}"
    if proc.returncode != 0:
        return None, (
            f"automerge fetch failed pr={pr_number} rc={proc.returncode} "
            f"stderr={proc.stderr.strip()[:300]}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return None, f"automerge fetch bad JSON pr={pr_number}: {exc}"
    try:
        enabled_at = payload["data"]["repository"]["pullRequest"]["autoMergeRequest"]
    except (KeyError, TypeError):
        return None, None
    if not isinstance(enabled_at, dict):
        return None, None
    return enabled_at.get("enabledAt"), None


def fetch_pr_author_info(repo: str, pr_number: int) -> tuple[dict[str, Any] | None, str | None]:
    """gh pr view -> {author:{login}, headRefName} for author-class resolution on ejections."""
    cmd = [
        "gh", "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "author,headRefName",
    ]
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_SHORT)
    except subprocess.TimeoutExpired as exc:
        return None, f"pr view timeout pr={pr_number}: {exc}"
    except OSError as exc:
        return None, f"pr view OSError pr={pr_number}: {exc}"
    if proc.returncode != 0:
        return None, (
            f"pr view failed pr={pr_number} rc={proc.returncode} "
            f"stderr={proc.stderr.strip()[:300]}"
        )
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"pr view bad JSON pr={pr_number}: {exc}"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _empty_record(repo: str, day: date) -> dict[str, Any]:
    """The schema, fully populated with zeros/empties. Every field always present — a test
    ("empty-day record still carries the schema with zeros and empty errors") depends on this
    being the SAME shape whether the day was genuinely quiet or the record is a crash fallback.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "date": day.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": repo,
        "billed_minutes_per_pr": {},
        "unattributed_group_minutes": 0.0,
        "unattributed_pr_minutes": 0.0,
        "other_event_minutes": 0.0,
        "total_runner_minutes": 0.0,
        "timing_sources": {
            "billable": {"runs": 0, "minutes": 0.0},
            "run_duration": {"runs": 0, "minutes": 0.0},
            "billable_zero_without_duration": {"runs": 0, "minutes": 0.0},
        },
        "run_collection": {
            "reported_total": None,
            "fetched": 0,
            "complete": False,
        },
        "queue_transit_minutes": {},
        "queue_transit_p50_minutes": None,
        "queue_transit_p95_minutes": None,
        "transit_unmeasured_prs": [],
        "ejections": {
            "by_class": {"INFRA": 0, "CODE": 0, "FLAKE": 0},
            "by_author_class": {"human": 0, "agent": 0, "bot": 0, "unknown": 0},
            "total": 0,
        },
        "slot_utilization": {
            "runner_minutes_today": 0.0,
            "weekly_capacity_slot_minutes": WEEKLY_CI_CAPACITY_SLOT_MINUTES,
            "daily_capacity_slot_minutes": WEEKLY_CI_CAPACITY_SLOT_MINUTES / 7.0,
            "utilization_pct": 0.0,
        },
        "counts": {
            "runs_seen": 0,
            "merge_group_runs": 0,
            "pull_request_runs": 0,
            "other_runs": 0,
            "prs_merged_today": 0,
        },
        "errors": [],
    }


def build_record(repo: str, day: date) -> dict[str, Any]:
    """Build one day's baseline record. Never raises — a crash mid-way is caught by the
    caller (main()) and turned into an emergency record carrying the traceback as an error
    entry, never a silent empty-record-with-exit-0.
    """
    record = _empty_record(repo, day)
    errors: list[str] = record["errors"]

    runs, reported_total, run_list_errors = list_workflow_runs(repo, day)
    errors.extend(run_list_errors)
    record["run_collection"] = {
        "reported_total": reported_total,
        "fetched": len(runs),
        "complete": reported_total == len(runs),
    }

    billed_per_pr: dict[str, float] = {}
    unattributed_group: list[float] = []
    unattributed_pr: list[float] = []
    other_event: list[float] = []
    ejectable_runs: list[dict[str, Any]] = []
    pr_run_count = 0
    mg_run_count = 0
    other_run_count = 0

    for run in runs:
        event = run.get("event")
        if event == "pull_request":
            pr_run_count += 1
        elif event == "merge_group":
            mg_run_count += 1
        else:
            other_run_count += 1

        # Ejection status is a property of the run's OWN conclusion, independent of
        # whether its billing timing can be fetched — classified BEFORE the timing
        # `continue`s below so a timing-fetch failure on a failed merge_group run
        # never silently undercounts ejections (the timing gap is still recorded in
        # errors[], but the ejection itself must still be counted).
        if event == "merge_group" and run.get("conclusion") in ("failure", "cancelled", "timed_out"):
            ejectable_runs.append(run)

        run_id = run.get("id")
        if run_id is None:
            errors.append(f"run missing id, skipped: {run.get('name', '?')!r}")
            continue
        minutes, timing_source, timing_error = fetch_run_timing_minutes(repo, run_id)
        if timing_error:
            errors.append(timing_error)
            continue
        if minutes is None or timing_source is None:
            errors.append(f"timing fetch returned incomplete data for run={run_id}, skipped")
            continue
        source_record = record["timing_sources"][timing_source]
        source_record["runs"] += 1
        source_record["minutes"] += minutes
        allocate_run_minutes(run, minutes, billed_per_pr, unattributed_group, unattributed_pr, other_event)

    total_runner_minutes = (
        sum(billed_per_pr.values())
        + sum(unattributed_group)
        + sum(unattributed_pr)
        + sum(other_event)
    )

    record["billed_minutes_per_pr"] = billed_per_pr
    record["unattributed_group_minutes"] = sum(unattributed_group)
    record["unattributed_pr_minutes"] = sum(unattributed_pr)
    record["other_event_minutes"] = sum(other_event)
    record["total_runner_minutes"] = total_runner_minutes
    record["counts"]["runs_seen"] = len(runs)
    record["counts"]["pull_request_runs"] = pr_run_count
    record["counts"]["merge_group_runs"] = mg_run_count
    record["counts"]["other_runs"] = other_run_count

    daily_capacity = WEEKLY_CI_CAPACITY_SLOT_MINUTES / 7.0
    record["slot_utilization"] = {
        "runner_minutes_today": total_runner_minutes,
        "weekly_capacity_slot_minutes": WEEKLY_CI_CAPACITY_SLOT_MINUTES,
        "daily_capacity_slot_minutes": daily_capacity,
        "utilization_pct": (total_runner_minutes / daily_capacity * 100.0) if daily_capacity else 0.0,
    }

    # --- ejections ---
    by_class = {"INFRA": 0, "CODE": 0, "FLAKE": 0}
    by_author: dict[str, int] = {"human": 0, "agent": 0, "bot": 0, "unknown": 0}
    author_cache: dict[int, str] = {}
    for run in ejectable_runs:
        jobs, jobs_error = fetch_run_jobs(repo, run.get("id"))
        if jobs_error:
            errors.append(jobs_error)
        cls = classify_ejection(run, jobs)
        by_class[cls] = by_class.get(cls, 0) + 1

        members = extract_merge_group_pr_numbers(run)
        author_class = "unknown"
        resolved = False
        for pr_number in members:
            if pr_number in author_cache:
                author_class = author_cache[pr_number]
                resolved = True
                break
            info, info_error = fetch_pr_author_info(repo, pr_number)
            if info_error:
                errors.append(info_error)
                continue
            if info is None:
                continue
            author_login = (info.get("author") or {}).get("login")
            head_ref = info.get("headRefName")
            author_class = classify_author(head_ref, author_login)
            author_cache[pr_number] = author_class
            resolved = True
            break
        if not resolved:
            errors.append(
                f"ejection author-class unresolved for merge_group run={run.get('id')} "
                f"(no derivable member PR or all lookups failed)"
            )
        by_author[author_class] = by_author.get(author_class, 0) + 1

    record["ejections"] = {
        "by_class": by_class,
        "by_author_class": by_author,
        "total": sum(by_class.values()),
    }

    # --- queue transit ---
    merged_prs, merged_errors = fetch_merged_prs(repo, day)
    errors.extend(merged_errors)
    record["counts"]["prs_merged_today"] = len(merged_prs)

    transit_minutes: dict[str, float] = {}
    unmeasured: list[int] = []
    for pr in merged_prs:
        number = pr.get("number")
        merged_at = pr.get("mergedAt")
        if number is None or not merged_at:
            errors.append(f"merged PR missing number/mergedAt: {pr!r}")
            continue
        enabled_at, am_error = fetch_automerge_enabled_at(repo, number)
        if am_error:
            errors.append(am_error)
            unmeasured.append(number)
            continue
        if not enabled_at:
            unmeasured.append(number)
            continue
        try:
            t_enabled = datetime.fromisoformat(enabled_at.replace("Z", "+00:00"))
            t_merged = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        except ValueError as exc:
            errors.append(f"unparseable timestamp pr={number}: {exc}")
            unmeasured.append(number)
            continue
        delta_minutes = (t_merged - t_enabled).total_seconds() / 60.0
        if delta_minutes < 0:
            errors.append(
                f"negative transit for pr={number} (enabledAt={enabled_at} > mergedAt={merged_at}), "
                f"excluded from p50/p95, recorded as unmeasured"
            )
            unmeasured.append(number)
            continue
        transit_minutes[str(number)] = delta_minutes

    record["queue_transit_minutes"] = transit_minutes
    record["transit_unmeasured_prs"] = unmeasured
    sample = list(transit_minutes.values())
    record["queue_transit_p50_minutes"] = percentile(sample, 50)
    record["queue_transit_p95_minutes"] = percentile(sample, 95)

    return record


def _emergency_record(repo: str, day: date, exc: BaseException) -> dict[str, Any]:
    record = _empty_record(repo, day)
    record["errors"].append(
        f"FATAL uncaught exception while building record: {exc!r}\n"
        f"{traceback.format_exc()}"
    )
    return record


def write_record(out_dir: Path, record: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{record['date']}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    tmp_path.replace(out_path)  # atomic on the same filesystem
    return out_path


def write_pointer(out_dir: Path, record: dict[str, Any], record_path: Path) -> Path:
    """A small side file naming the just-written record, so the wrapper (and any consumer)
    can find "the latest run's date/path" without recomputing "yesterday UTC" itself — one
    computation of the date, not two (scar family #9: two writers of one derived fact drift).
    """
    pointer_path = out_dir / ".last-run-pointer.json"
    pointer = {
        "date": record["date"],
        "record_path": str(record_path),
        "errors_count": len(record["errors"]),
        "written_at_utc": record["generated_at_utc"],
    }
    tmp_path = pointer_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(pointer, indent=2, sort_keys=True) + "\n")
    tmp_path.replace(pointer_path)
    return pointer_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo, default %(default)s")
    parser.add_argument(
        "--date",
        default=None,
        help="UTC day to probe, YYYY-MM-DD (default: yesterday UTC)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="directory for daily records, default %(default)s",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="DEBUG-level logging",
    )
    return parser.parse_args(argv)


def _resolve_day(date_arg: str | None) -> date:
    if date_arg:
        return date.fromisoformat(date_arg)
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )

    day = _resolve_day(args.date)
    out_dir = Path(args.out_dir)

    try:
        record = build_record(args.repo, day)
    except Exception as exc:  # noqa: BLE001 — deliberate: this is the last-resort guard that
        # keeps the "never an empty record with exit 0" contract even on a bug in this script.
        logger.exception("uncaught exception building record for %s", day.isoformat())
        record = _emergency_record(args.repo, day, exc)

    out_path = write_record(out_dir, record)
    write_pointer(out_dir, record, out_path)

    n_errors = len(record["errors"])
    if n_errors:
        logger.warning("wrote %s with %d error(s) — see errors[] in the record", out_path, n_errors)
        for err in record["errors"]:
            logger.warning("  - %s", err.splitlines()[0] if err else err)
    else:
        logger.info(
            "wrote %s — runs=%d prs_merged=%d ejections=%d runner_minutes=%.1f",
            out_path,
            record["counts"]["runs_seen"],
            record["counts"]["prs_merged_today"],
            record["ejections"]["total"],
            record["total_runner_minutes"],
        )

    return 1 if n_errors else 0


if __name__ == "__main__":
    sys.exit(main())
