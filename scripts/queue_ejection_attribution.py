#!/usr/bin/env python3
"""queue_ejection_attribution.py — Merge-OS v3 agy-F3 disposition: ejection attribution from
the PR's own timeline (not the merge_group run's actor).

Spec: research/operations/2026-08-14-merge-os-v3-research-council.md §5, row "agy-F3
(author-class unmeasurable)" — "DISSOLVED — wrong observation point: attribute from the PR
timeline, not merge_group.actor; GraphQL `RemovedFromMergeQueueEvent` carries
pullRequest/actor/enqueuer/beforeCommit/reason; episodes keyed (PR, head SHA, enqueue ts)."

WHY THE OLD OBSERVATION POINT WAS WRONG: every `merge_group` workflow run's `actor` is
`github-actions[bot]` (or similar) — the merge queue's own service account, never the PR's
human/agent author. Attributing ejections from that field always lands in "bot", which is
useless for the human/agent/bot split the baseline organ wants (Codex F16). The PR's own
GraphQL timeline carries the real author and the real removal event — verified live against
this repo 2026-08-14 (`gh api graphql` introspection + real PRs #4181, #4153, #4131, ...).

STANDALONE BY DESIGN: this module does NOT import from or modify `scripts/queue_baseline_probe.py`
(a sibling PR is in flight on that file — #4185, the pagination fix). It duplicates the small
set of pure helpers it needs (`classify_author`, the INFRA job-name-signature heuristic) rather
than coupling to that module. Wiring this organ's output into the baseline organ's nightly
record is a declared follow-up PR, not part of this one.

DISCOVERY METHOD (declared, with a known coverage gap — never silently assumed complete):
this module has no way to ask GitHub "which PRs had a RemovedFromMergeQueueEvent on day X" —
no REST/GraphQL endpoint indexes timeline events by date. It therefore builds a CANDIDATE set
of PR numbers as the union of:
  1. every PR number extractable from a `merge_group`-event workflow run's `head_branch`
     created that UTC day (regex `pr-(\\d+)-([0-9a-f]{40})`, same pattern the baseline organ
     uses) — regardless of that run's conclusion;
  2. every PR merged that UTC day (`gh pr list --state merged --search merged:<day>`), to
     catch a PR that was ejected earlier the same day and later merged.
For each candidate, the PR's FULL timeline of `ADDED_TO_MERGE_QUEUE_EVENT` /
`REMOVED_FROM_MERGE_QUEUE_EVENT` items is fetched and every `RemovedFromMergeQueueEvent` whose
own `createdAt` falls on the target day becomes an episode.
KNOWN GAP (verified live 2026-08-14 against PR #4131's `merge_conflict` episode, which has NO
associated merge_group run at all — GitHub's queue rejects a conflicting entry before any
check starts): a PR ejected by `manual` or `merge_conflict` that triggers no merge_group run
that day AND is not merged/re-queued-with-a-run that same day is invisible to this discovery
method. This is a declared limitation of "candidate discovery", not of the timeline reading
itself (which is exhaustive once a PR is a candidate) — recorded in `discovery.method` on every
record so a reader always sees the boundary, never infers false completeness.

REMOVAL-REASON MAPPING (declared, `reason` is a plain GraphQL `String`, not an enum — GitHub
can add new values at any time without a schema change; verified via introspection 2026-08-14
that `RemovedFromMergeQueueEvent.reason` has no enum type to enumerate). Every reason value
this repo's own history has produced (grepped across 38 historical merge_group PRs, 2026-08-14):
  "merged"         -> NOT an ejection at all (the normal successful dequeue) — counted under
                      `successful_dequeues`, excluded from `ejections`.
  "manual"         -> MANUAL
  "merge_conflict" -> CONFLICT
  "failed_checks"  -> needs a second signal to split INFRA vs CODE (the reason string alone
                      doesn't say which). CORRELATION METHOD, revised after a live discrepancy
                      (2026-08-14, real PRs #4153/#4154): a first attempt keyed strictly on
                      (pr_number, `beforeCommit.oid` == the run's `head_branch` SHA) missed
                      real ejections — the run named `pr-4153-4d937e99...` turned out to carry
                      the SHA that PR #4154's OWN `beforeCommit.oid` reported, not PR #4153's.
                      This repo's merge queue batches multiple PRs per attempt; the run's
                      `head_branch` names one representative PR while its embedded SHA is the
                      batch's speculative test commit, which need not equal any single member
                      PR's own `beforeCommit.oid`. Exact-SHA correlation is therefore
                      unreliable here. The declared, honest-best-effort method instead
                      correlates by PR NUMBER ONLY, picking the failing run(s) (a `failure`/
                      `cancelled`/`timed_out` conclusion) for that PR number with the LATEST
                      `created_at` at or before the episode's `removed_at` (all required-check
                      runs for one queue attempt share the same `created_at`, so this recovers
                      the exact attempt's row-set without needing the SHA at all). If ANY of
                      those runs has a job classified INFRA (mirrors
                      queue_baseline_probe.py's own INFRA_JOB_NAME_SIGNATURES heuristic,
                      duplicated here by declared design — see STANDALONE note above) -> INFRA;
                      else -> CODE. If no correlated failing run is found at all (e.g. outside
                      the day's fetched window) -> CODE (the same conservative default the
                      probe uses for an unresolvable classification), with the gap written to
                      errors[] — never silently invented as INFRA.
  anything else    -> UNKNOWN, with the raw reason string preserved verbatim in errors[] (fail
                      visible — a reason this module has never seen must never be silently
                      dropped or guessed into an existing bucket).
`HEAD_MOVED` is a declared bucket name for a reason this repo's own history has not yet
produced (GitHub's queue does eject a PR whose head commit changed underneath it, but no
occurrence has been observed here to learn the actual string) — it stays 0 by construction
until a real occurrence teaches this module the string; that occurrence would currently land in
UNKNOWN with a visible error rather than being silently miscounted, which is the point.

RE-ENTRY EPISODES: a PR can enter/leave the queue multiple times (observed live: PR #4131 did
so 3 times in one day). Episodes are keyed by POSITION in the PR's own chronologically-ordered
timeline — an Added event is paired with the next Removed event that follows it — so a
re-entry with the IDENTICAL (author, head SHA) as a prior episode is still a distinct episode,
never collapsed. An Added with no following Removed in the fetched window (PR still actively
queued, or a pagination boundary) is never guessed into a fabricated episode — it lands in
`episodes_unresolved`, the same declared-never-dropped principle as the baseline probe's
`transit_unmeasured_prs`.

FAIL-VISIBLE (mirrors queue_baseline_probe.py's contract): every `gh` denial, timeout, or
unparseable response is appended to `errors[]`. The record is ALWAYS written, even when
everything failed. `main()` returns 0 only when `errors` is empty.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("queue_ejection_attribution")

DEFAULT_REPO = "Bali-Zero/Teman2"
DEFAULT_OUT_DIR = Path.home() / ".nuzantara-mq" / "ejections"
SCHEMA_VERSION = 1

GH_TIMEOUT_LIST_RUNS = 90
GH_TIMEOUT_SHORT = 30

# Same server-side cap queue_baseline_probe.py documents (docs.github.com/en/rest/actions/
# workflow-runs: "up to 1,000 results" for a `created`-filtered query). merge_group-event
# volume for one day is far smaller than the all-events volume that motivated that module's
# bisection fix (observed: tens to low hundreds/day here) — a single non-bisected fetch is
# declared sufficient for THIS module today; the shortfall is still fail-visible (never
# silent) so a future day dense enough to hit the cap is caught, not hidden.
PAGE_CAP = 1000

# Mirrors scripts/queue_baseline_probe.py::INFRA_JOB_NAME_SIGNATURES by declared design (same
# heuristic, applied here to a failed_checks removal's correlated run rather than a
# merge_group run's own classification). Duplicated, not imported — see STANDALONE note in the
# module docstring. If that list changes, this one should be re-checked too.
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

# "merged" is the normal successful dequeue, not an ejection.
NOT_AN_EJECTION_REASONS = frozenset({"merged"})

# Declared reason -> local bucket map. "failed_checks" is deliberately absent here — it needs
# the run-correlation signal (see classify_removal_reason) and is handled specially.
REASON_CLASS_MAP = {
    "manual": "MANUAL",
    "merge_conflict": "CONFLICT",
}

EJECTION_CLASSES = ("CODE", "INFRA", "CONFLICT", "HEAD_MOVED", "MANUAL", "UNKNOWN")

PR_SHA_RE = re.compile(r"pr-(\d+)-([0-9a-f]{40})")

MAX_TIMELINE_PAGES = 10  # safety bound — a PR queued >1,000 times in its life is not a
# realistic shape for this repo; hitting this is itself a fail-visible signal (errors[]),
# never a silent truncation (scar W97).


# ---------------------------------------------------------------------------
# Pure functions (no I/O).
# ---------------------------------------------------------------------------


def classify_author(head_ref_name: str | None, author_login: str | None) -> str:
    """human / agent / bot split (Codex F16). Pure — no I/O. Identical rule to
    queue_baseline_probe.py::classify_author (duplicated by declared design, see module
    docstring STANDALONE note): branch namespace wins over login, since an agent-authored PR
    is what this repo's own convention (agent/<host>/<lane>/...) declares it to be regardless
    of which GitHub account pushed it.
    """
    if head_ref_name and head_ref_name.startswith("agent/"):
        return "agent"
    login = (author_login or "").strip()
    if login.endswith("[bot]") or login in BOT_LOGIN_ALLOWLIST:
        return "bot"
    return "human"


def classify_removal_reason(reason_raw: str | None, infra_hint: bool | None) -> str:
    """Map a RemovedFromMergeQueueEvent's raw `reason` string to a declared local bucket.

    `infra_hint` is only consulted for `reason_raw == "failed_checks"`: True/False when a
    correlated merge_group run's jobs resolved a flavor, None when no correlated run could be
    found (caller still returns "CODE" — the conservative default — but MUST also write the
    correlation gap to errors[]; this function only returns the bucket, it never fabricates
    visibility on its own).

    Never returns a class outside EJECTION_CLASSES; an unmapped raw reason returns "UNKNOWN"
    — the caller is responsible for also logging the raw string to errors[] (this pure
    function has no I/O and cannot itself be fail-visible).
    """
    if reason_raw == "failed_checks":
        if infra_hint is True:
            return "INFRA"
        return "CODE"  # infra_hint False or None — conservative default, never invented INFRA
    mapped = REASON_CLASS_MAP.get(reason_raw) if reason_raw is not None else None
    return mapped if mapped is not None else "UNKNOWN"


def _run_is_infra_flavoured(run: dict[str, Any], jobs: list[dict[str, Any]]) -> bool:
    """Mirrors queue_baseline_probe.py::classify_ejection's INFRA branch, applied to a run
    already known to have failed/been cancelled/timed out (the caller only invokes this for
    such runs — this function does not itself check `run.get("conclusion")` against success).
    """
    if run.get("conclusion") in ("cancelled", "timed_out"):
        return True
    for job in jobs:
        job_conclusion = job.get("conclusion")
        if job_conclusion in ("cancelled", "timed_out"):
            return True
        name = str(job.get("name") or "").lower()
        if job_conclusion == "failure" and any(sig in name for sig in INFRA_JOB_NAME_SIGNATURES):
            return True
    return False


def select_correlated_failing_runs(
    candidate_runs: list[dict[str, Any]],
    removed_at: str | None,
) -> list[dict[str, Any]]:
    """Among a PR's merge_group runs that day, pick the failing run(s) most plausibly
    responsible for one specific failed_checks removal.

    Correlates by PR NUMBER + TIME, never by SHA (see module docstring's failed_checks
    CORRELATION METHOD note — exact-SHA correlation was tried first and found unreliable
    against this repo's own batched-queue behavior). Picks the failing run(s) — conclusion in
    failure/cancelled/timed_out — with the LATEST `created_at` at or before `removed_at`; all
    required-check runs for one queue attempt share the same `created_at`, so this recovers
    the exact attempt's row-set. Returns `[]` (never guessed) if `removed_at` is missing/
    unparseable, or no failing run's `created_at` is resolvable and at-or-before it.
    """
    if not removed_at:
        return []
    try:
        removed_dt = datetime.fromisoformat(str(removed_at).replace("Z", "+00:00"))
    except ValueError:
        return []
    dated: list[tuple[datetime, dict[str, Any]]] = []
    for run in candidate_runs:
        if run.get("conclusion") not in ("failure", "cancelled", "timed_out"):
            continue
        try:
            created_dt = datetime.fromisoformat(str(run.get("created_at")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if created_dt <= removed_dt:
            dated.append((created_dt, run))
    if not dated:
        return []
    latest_ts = max(dt for dt, _run in dated)
    return [run for dt, run in dated if dt == latest_ts]


def extract_pr_shas_from_head_branch(head_branch: str | None) -> tuple[int, str] | None:
    """`gh-readonly-queue/main/pr-<N>-<40-hex-sha>` -> (N, sha). None if the pattern isn't
    present (a run that isn't a merge-queue member run for a single PR)."""
    match = PR_SHA_RE.search(str(head_branch or ""))
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def _flatten_timeline_node(node: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one raw GraphQL timelineItems node. Returns None for a __typename outside
    the two requested by the query's `itemTypes` filter — should not happen, but a schema
    surprise must degrade to "ignored", never raise.
    """
    typename = node.get("__typename")
    if typename == "AddedToMergeQueueEvent":
        return {"kind": "added", "created_at": node.get("createdAt")}
    if typename == "RemovedFromMergeQueueEvent":
        before_commit = node.get("beforeCommit")
        oid = before_commit.get("oid") if isinstance(before_commit, dict) else None
        return {
            "kind": "removed",
            "created_at": node.get("createdAt"),
            "reason": node.get("reason"),
            "before_commit_oid": oid,
        }
    return None


def pair_queue_episodes(flat_nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pairs sequential Added -> Removed timeline nodes (GitHub returns timelineItems in
    chronological order) into episodes, keyed by POSITION — never by (author, head SHA)
    identity, since a re-entry can legitimately repeat both (module docstring RE-ENTRY note).

    Returns (episodes, unresolved_added). An episode is `{"enqueued_at": ..., **removed_node}`
    — `enqueued_at` is None when a Removed event has no preceding unpaired Added in the
    fetched window (never guessed). `unresolved_added` holds every Added event with no
    following Removed before the next Added or the end of the fetched timeline (e.g. still
    actively queued) — never silently dropped.
    """
    episodes: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    pending_added: dict[str, Any] | None = None
    for node in flat_nodes:
        if node["kind"] == "added":
            if pending_added is not None:
                unresolved.append(pending_added)
            pending_added = node
        else:
            if pending_added is None:
                episodes.append({"enqueued_at": None, **node})
            else:
                episodes.append({"enqueued_at": pending_added["created_at"], **node})
                pending_added = None
    if pending_added is not None:
        unresolved.append(pending_added)
    return episodes, unresolved


def _is_on_day(iso_ts: str | None, day: date) -> bool:
    if not iso_ts:
        return False
    try:
        parsed = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.astimezone(timezone.utc).date() == day


# ---------------------------------------------------------------------------
# subprocess boundary
# ---------------------------------------------------------------------------


def _run_gh(cmd: list[str], timeout: int = GH_TIMEOUT_SHORT) -> subprocess.CompletedProcess[str]:
    """The one subprocess boundary this module crosses for `gh` calls. Never raises on a
    non-zero exit — callers judge `.returncode` and `.stdout`/`.stderr` separately (W104
    discipline: stdout != stderr). May raise `subprocess.TimeoutExpired`; callers catch it.
    """
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------------------
# I/O-fetching functions
# ---------------------------------------------------------------------------


def list_merge_group_runs_for_day(
    repo: str,
    day: date,
) -> tuple[list[dict[str, Any]], int | None, list[str]]:
    """merge_group-event workflow runs created on `day` (UTC) — the seed for candidate PR
    discovery AND the source of run-level data for failed_checks INFRA/CODE correlation.

    Single non-bisected fetch (see module docstring PAGE_CAP note) — still fail-visible if it
    falls short: `errors` carries a shortfall entry, never a silent partial-as-complete list.
    """
    created_query = f"{day.isoformat()}..{day.isoformat()}"
    cmd = [
        "gh", "api", f"repos/{repo}/actions/runs",
        "-X", "GET",
        "-f", "event=merge_group",
        "-f", f"created={created_query}",
        "-f", "per_page=100",
        "--paginate",
    ]
    errors: list[str] = []
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_LIST_RUNS)
    except subprocess.TimeoutExpired as exc:
        return [], None, [f"list_merge_group_runs_for_day timeout: {exc}"]
    except OSError as exc:
        return [], None, [f"list_merge_group_runs_for_day OSError: {exc}"]
    if proc.returncode != 0:
        return [], None, [
            f"list_merge_group_runs_for_day failed rc={proc.returncode} "
            f"stderr={proc.stderr.strip()[:400]}"
        ]
    decoder = json.JSONDecoder()
    text = proc.stdout.strip()
    pages: list[dict[str, Any]] = []
    idx, n = 0, len(text)
    try:
        while idx < n:
            while idx < n and text[idx].isspace():
                idx += 1
            if idx >= n:
                break
            obj, end = decoder.raw_decode(text, idx)
            pages.append(obj)
            idx = end
    except json.JSONDecodeError as exc:
        return [], None, [f"list_merge_group_runs_for_day bad JSON: {exc}"]

    reported_totals = {
        int(page["total_count"]) for page in pages if isinstance(page.get("total_count"), int)
    }
    reported_total = max(reported_totals) if reported_totals else None
    positive = {t for t in reported_totals if t > 0}
    if len(positive) > 1:
        errors.append(
            f"list_merge_group_runs_for_day inconsistent positive total_count values: {sorted(positive)}"
        )
    if reported_total is None:
        errors.append("list_merge_group_runs_for_day response missing integer total_count")

    runs_by_id: dict[int, dict[str, Any]] = {}
    for page in pages:
        for run in page.get("workflow_runs") or []:
            run_id = run.get("id") if isinstance(run, dict) else None
            if isinstance(run_id, int):
                runs_by_id[run_id] = run
    runs = list(runs_by_id.values())
    if reported_total is not None and len(runs) < reported_total:
        errors.append(
            "list_merge_group_runs_for_day pagination shortfall (never bisected in this "
            f"module — see PAGE_CAP note): fetched={len(runs)} reported_total={reported_total}; "
            "candidate discovery and failed_checks correlation are partial for this day"
        )
    return runs, reported_total, errors


def fetch_run_jobs(repo: str, run_id: int) -> tuple[list[dict[str, Any]], str | None]:
    """GET .../actions/runs/{run_id}/jobs -> jobs list, for the failed_checks INFRA/CODE
    correlation. Mirrors queue_baseline_probe.py::fetch_run_jobs (duplicated, see STANDALONE)."""
    # `-X GET` is NOT redundant here: `gh api` defaults to POST once any `-f`/`-F` param is
    # present, and a POST to this endpoint 404s — verified live 2026-08-14 (queue_baseline_probe.py's
    # sibling fetch_run_jobs carries the identical latent bug; flagged for that module
    # separately, not fixed here per the standalone-PR mandate).
    cmd = ["gh", "api", f"repos/{repo}/actions/runs/{run_id}/jobs", "-X", "GET", "-f", "per_page=100"]
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_SHORT)
    except subprocess.TimeoutExpired as exc:
        return [], f"jobs fetch timeout run={run_id}: {exc}"
    except OSError as exc:
        return [], f"jobs fetch OSError run={run_id}: {exc}"
    if proc.returncode != 0:
        return [], f"jobs fetch failed run={run_id} rc={proc.returncode} stderr={proc.stderr.strip()[:300]}"
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return [], f"jobs fetch bad JSON run={run_id}: {exc}"
    return payload.get("jobs") or [], None


def fetch_merged_pr_numbers_for_day(repo: str, day: date) -> tuple[list[int], list[str]]:
    """PR numbers merged on `day` (UTC) — the second candidate-discovery source (module
    docstring DISCOVERY METHOD)."""
    cmd = [
        "gh", "pr", "list",
        "--repo", repo,
        "--state", "merged",
        "--search", f"merged:{day.isoformat()}",
        "--json", "number",
        "--limit", "200",
    ]
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_SHORT)
    except subprocess.TimeoutExpired as exc:
        return [], [f"fetch_merged_pr_numbers_for_day timeout: {exc}"]
    except OSError as exc:
        return [], [f"fetch_merged_pr_numbers_for_day OSError: {exc}"]
    if proc.returncode != 0:
        return [], [
            f"fetch_merged_pr_numbers_for_day failed rc={proc.returncode} "
            f"stderr={proc.stderr.strip()[:400]}"
        ]
    try:
        prs = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return [], [f"fetch_merged_pr_numbers_for_day bad JSON: {exc}"]
    if not isinstance(prs, list):
        return [], [f"fetch_merged_pr_numbers_for_day unexpected payload shape: {type(prs).__name__}"]
    numbers = [pr["number"] for pr in prs if isinstance(pr, dict) and "number" in pr]
    return numbers, []


_TIMELINE_QUERY = (
    "query($owner:String!,$name:String!,$number:Int!,$cursor:String){"
    "repository(owner:$owner,name:$name){"
    "pullRequest(number:$number){"
    "author{login} headRefName "
    "timelineItems(first:100,after:$cursor,itemTypes:[ADDED_TO_MERGE_QUEUE_EVENT,"
    "REMOVED_FROM_MERGE_QUEUE_EVENT]){"
    "pageInfo{hasNextPage endCursor} "
    "nodes{__typename "
    "... on AddedToMergeQueueEvent{createdAt} "
    "... on RemovedFromMergeQueueEvent{createdAt reason beforeCommit{oid}}"
    "}}}}}"
)


def fetch_pr_timeline(
    repo: str,
    pr_number: int,
) -> tuple[list[dict[str, Any]], str | None, str | None, list[str]]:
    """Full (paginated) ADDED/REMOVED_FROM_MERGE_QUEUE_EVENT timeline for one PR.

    Returns (raw_nodes, author_login, head_ref_name, errors). `author_login`/`head_ref_name`
    are read once, from the first page (a GraphQL connection re-serves the same parent object
    on every page — reading it more than once would just be wasted parsing, not a shape risk).
    """
    owner, _, name = repo.partition("/")
    nodes: list[dict[str, Any]] = []
    author_login: str | None = None
    head_ref_name: str | None = None
    errors: list[str] = []
    cursor: str | None = None

    for _page_num in range(MAX_TIMELINE_PAGES):
        cmd = [
            "gh", "api", "graphql",
            "-f", f"query={_TIMELINE_QUERY}",
            "-F", f"owner={owner}",
            "-F", f"name={name}",
            "-F", f"number={pr_number}",
        ]
        if cursor:
            cmd += ["-F", f"cursor={cursor}"]
        try:
            proc = _run_gh(cmd, timeout=GH_TIMEOUT_SHORT)
        except subprocess.TimeoutExpired as exc:
            errors.append(f"timeline fetch timeout pr={pr_number}: {exc}")
            return nodes, author_login, head_ref_name, errors
        except OSError as exc:
            errors.append(f"timeline fetch OSError pr={pr_number}: {exc}")
            return nodes, author_login, head_ref_name, errors
        if proc.returncode != 0:
            errors.append(
                f"timeline fetch failed pr={pr_number} rc={proc.returncode} "
                f"stderr={proc.stderr.strip()[:300]}"
            )
            return nodes, author_login, head_ref_name, errors
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"timeline fetch bad JSON pr={pr_number}: {exc}")
            return nodes, author_login, head_ref_name, errors
        try:
            pr_obj = payload["data"]["repository"]["pullRequest"]
        except (KeyError, TypeError):
            errors.append(f"timeline fetch missing pullRequest pr={pr_number}: {str(payload)[:300]}")
            return nodes, author_login, head_ref_name, errors
        if pr_obj is None:
            errors.append(f"timeline fetch pr={pr_number}: PR not found (deleted/inaccessible?)")
            return nodes, author_login, head_ref_name, errors

        if author_login is None:
            author_login = (pr_obj.get("author") or {}).get("login")
            head_ref_name = pr_obj.get("headRefName")

        timeline = pr_obj.get("timelineItems") or {}
        nodes.extend(timeline.get("nodes") or [])
        page_info = timeline.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            return nodes, author_login, head_ref_name, errors
        cursor = page_info.get("endCursor")
        if not cursor:
            errors.append(f"timeline fetch pr={pr_number}: hasNextPage true but no endCursor")
            return nodes, author_login, head_ref_name, errors

    errors.append(
        f"timeline fetch pr={pr_number}: hit MAX_TIMELINE_PAGES={MAX_TIMELINE_PAGES} without "
        "exhausting pagination — record partial for this PR"
    )
    return nodes, author_login, head_ref_name, errors


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _empty_record(repo: str, day: date) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "date": day.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": repo,
        "discovery": {
            "method": (
                "candidate PR numbers = merge_group-event workflow run PR numbers for the day "
                "UNION same-day-merged PR numbers (module docstring 'DISCOVERY METHOD' declares "
                "the known coverage gap: a manual/merge_conflict ejection with no merge_group "
                "run and no same-day merge is invisible to this method)"
            ),
            "candidate_prs_from_merge_group_runs": 0,
            "candidate_prs_from_merged_list": 0,
            "candidate_prs_total": 0,
            "merge_group_run_collection": {"reported_total": None, "fetched": 0, "complete": False},
        },
        "episodes": [],
        "episodes_unresolved": [],
        "successful_dequeues": 0,
        "ejections": {
            "by_class": {cls: 0 for cls in EJECTION_CLASSES},
            "by_author_class": {"human": 0, "agent": 0, "bot": 0, "unknown": 0},
            "total": 0,
        },
        "counts": {
            "candidate_prs_scanned": 0,
            "timeline_items_seen": 0,
        },
        "errors": [],
    }


def build_record(repo: str, day: date) -> dict[str, Any]:
    """Build one day's ejection-attribution record. Never raises — a crash mid-way is caught
    by the caller (main()) and turned into an emergency record carrying the traceback."""
    record = _empty_record(repo, day)
    errors: list[str] = record["errors"]

    mg_runs, mg_reported_total, mg_errors = list_merge_group_runs_for_day(repo, day)
    errors.extend(mg_errors)
    record["discovery"]["merge_group_run_collection"] = {
        "reported_total": mg_reported_total,
        "fetched": len(mg_runs),
        "complete": mg_reported_total == len(mg_runs),
    }

    runs_by_pr_number: dict[int, list[dict[str, Any]]] = {}
    candidate_from_runs: set[int] = set()
    for run in mg_runs:
        parsed = extract_pr_shas_from_head_branch(run.get("head_branch"))
        if parsed is None:
            continue
        pr_number, _sha = parsed  # SHA not used for correlation — see module docstring
        candidate_from_runs.add(pr_number)
        runs_by_pr_number.setdefault(pr_number, []).append(run)

    merged_numbers, merged_errors = fetch_merged_pr_numbers_for_day(repo, day)
    errors.extend(merged_errors)

    candidate_prs = sorted(candidate_from_runs | set(merged_numbers))
    record["discovery"]["candidate_prs_from_merge_group_runs"] = len(candidate_from_runs)
    record["discovery"]["candidate_prs_from_merged_list"] = len(set(merged_numbers))
    record["discovery"]["candidate_prs_total"] = len(candidate_prs)
    record["counts"]["candidate_prs_scanned"] = len(candidate_prs)

    episodes: list[dict[str, Any]] = []
    unresolved_out: list[dict[str, Any]] = []
    successful_dequeues = 0
    by_class = {cls: 0 for cls in EJECTION_CLASSES}
    by_author: dict[str, int] = {"human": 0, "agent": 0, "bot": 0, "unknown": 0}
    timeline_items_seen = 0
    infra_job_cache: dict[int, bool] = {}

    for pr_number in candidate_prs:
        raw_nodes, author_login, head_ref_name, pr_errors = fetch_pr_timeline(repo, pr_number)
        errors.extend(pr_errors)
        timeline_items_seen += len(raw_nodes)

        flat_nodes = []
        for node in raw_nodes:
            flat = _flatten_timeline_node(node)
            if flat is None:
                errors.append(f"pr={pr_number}: unrecognized timelineItems __typename {node.get('__typename')!r}")
                continue
            flat_nodes.append(flat)

        day_episodes, day_unresolved = pair_queue_episodes(flat_nodes)
        author_class = classify_author(head_ref_name, author_login)

        for added in day_unresolved:
            if _is_on_day(added.get("created_at"), day):
                unresolved_out.append(
                    {"pr_number": pr_number, "enqueued_at": added.get("created_at")}
                )

        for ep in day_episodes:
            if not _is_on_day(ep.get("created_at"), day):
                continue
            reason_raw = ep.get("reason")

            if reason_raw in NOT_AN_EJECTION_REASONS:
                successful_dequeues += 1
                continue

            infra_hint: bool | None = None
            if reason_raw == "failed_checks":
                candidate_runs = runs_by_pr_number.get(pr_number, [])
                failing_runs = select_correlated_failing_runs(candidate_runs, ep.get("created_at"))
                if not failing_runs:
                    errors.append(
                        f"failed_checks reason for pr={pr_number} "
                        f"removed_at={ep.get('created_at')}: no matching failing merge_group "
                        "run found for INFRA/CODE correlation, defaulted to CODE"
                    )
                    infra_hint = None
                else:
                    infra_hint = False
                    for run in failing_runs:
                        run_id = run.get("id")
                        if run_id in infra_job_cache:
                            is_infra = infra_job_cache[run_id]
                        else:
                            jobs, jobs_error = fetch_run_jobs(repo, run_id)
                            if jobs_error:
                                errors.append(jobs_error)
                            is_infra = _run_is_infra_flavoured(run, jobs)
                            infra_job_cache[run_id] = is_infra
                        if is_infra:
                            infra_hint = True
            elif reason_raw not in REASON_CLASS_MAP:
                errors.append(
                    f"unmapped removal reason={reason_raw!r} for pr={pr_number} "
                    f"removed_at={ep.get('created_at')}"
                )

            bucket = classify_removal_reason(reason_raw, infra_hint)
            by_class[bucket] = by_class.get(bucket, 0) + 1
            by_author[author_class] = by_author.get(author_class, 0) + 1

            episodes.append(
                {
                    "pr_number": pr_number,
                    "author_login": author_login,
                    "author_class": author_class,
                    "head_sha": ep.get("before_commit_oid"),
                    "enqueued_at": ep.get("enqueued_at"),
                    "removed_at": ep.get("created_at"),
                    "reason_raw": reason_raw,
                    "reason_class": bucket,
                }
            )

    record["episodes"] = episodes
    record["episodes_unresolved"] = unresolved_out
    record["successful_dequeues"] = successful_dequeues
    record["ejections"] = {
        "by_class": by_class,
        "by_author_class": by_author,
        "total": sum(by_class.values()),
    }
    record["counts"]["timeline_items_seen"] = timeline_items_seen

    return record


def _emergency_record(repo: str, day: date, exc: BaseException) -> dict[str, Any]:
    record = _empty_record(repo, day)
    record["errors"].append(
        f"FATAL uncaught exception while building record: {exc!r}\n{traceback.format_exc()}"
    )
    return record


def write_record(out_dir: Path, record: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{record['date']}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    tmp_path.replace(out_path)
    return out_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo, default %(default)s")
    parser.add_argument("--date", default=None, help="UTC day to probe, YYYY-MM-DD (default: yesterday UTC)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="directory for daily records")
    parser.add_argument("--verbose", action="store_true", help="DEBUG-level logging")
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
    except Exception as exc:  # noqa: BLE001 — last-resort guard, mirrors queue_baseline_probe.py
        logger.exception("uncaught exception building record for %s", day.isoformat())
        record = _emergency_record(args.repo, day, exc)

    out_path = write_record(out_dir, record)

    n_errors = len(record["errors"])
    if n_errors:
        logger.warning("wrote %s with %d error(s) — see errors[] in the record", out_path, n_errors)
        for err in record["errors"]:
            logger.warning("  - %s", err.splitlines()[0] if err else err)
    else:
        logger.info(
            "wrote %s — candidates=%d episodes=%d ejections=%d successful_dequeues=%d",
            out_path,
            record["counts"]["candidate_prs_scanned"],
            len(record["episodes"]),
            record["ejections"]["total"],
            record["successful_dequeues"],
        )

    return 1 if n_errors else 0


if __name__ == "__main__":
    sys.exit(main())
