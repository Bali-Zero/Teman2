#!/usr/bin/env python3
"""queue_shepherd.py — Merge-OS v3 Codex F7 disposition: budgeted auto-rearm + stale-run janitor.

WHY THIS EXISTS (Zero GO 2026-08-27). Two failure modes measured live in one night on this
repo's merge queue: (1) merge-queue entries silently drop and auto-merge disarms — 6+ manual
re-arms in one session, #5052 vanished from the queue un-merged; (2) stale Actions runs pile up
in the runner queue — 119 found by hand, `pull_request` runs for superseded PR heads and
`merge_group` runs for dead `gh-readonly-queue` branches that will never build.

GOVERNING SPEC (read before touching this file):
research/operations/2026-08-14-merge-os-v3-research-council.md §5, row "Codex F7 (retry
counter resets)": "durable budget keyed (repo, PR, head SHA), never queue entry; CODE=0
auto-requeue, INFRA<=3/24h, CONFLICT/HEAD_MOVED=none until new head passes smoke, UNKNOWN=
fail-closed; no atomic cross-run store exists in Actions -> if no organic durable store, the
conservative choice is NO autonomous rearm (launchd organ on Pro can own the counter file)."
This script IS that launchd organ; the counter file is `~/logs/queue-shepherd/rearm-budget.json`.

ATTRIBUTION METHOD (agy-F3 disposition, same council doc): attribute an ejection from the PR's
OWN GraphQL timeline (`RemovedFromMergeQueueEvent`), never from a `merge_group` run's `actor`
(always the queue's own service account). `scripts/queue_ejection_attribution.py` already
implements a full historical AUDIT of this signal with its own declared STANDALONE-by-design
note ("duplicated, not imported" — it does not want a coupling with a sibling file that other
PRs are actively editing). This script is a live-action organ, not an audit tool, and follows
the SAME declared convention for the same reason: the small classification heuristic
(`classify_ejection_reason`, `_run_has_infra_signature`) is duplicated here in miniature, not
imported, so this organ never breaks because that audit module's shape changed underneath it
(and vice versa). If that module's heuristic changes, re-check this one too.

TWO INDEPENDENT ACTIONS PER TICK:

(a) RE-ARM (budgeted). A PR counts as "armed by this repo's convention" if its branch is under
    the `agent/` namespace (CLAUDE.md Agent PR Contract §6) OR it carries a `harness/fable-gate`
    (or `harness-floor`) status/check context — the final on-disk gate. Among those, a PR is a
    re-arm CANDIDATE only when it is open, non-draft, currently disarmed (`autoMergeRequest` is
    null AND it holds no `mergeQueueEntry` — per W111, either field alone is ambiguous, see
    `.claude/rules/cicatrix-scars.md` ~line 160; ONLY both-null means truly disarmed) and its
    `mergeStateStatus` is CLEAN/UNSTABLE, or BLOCKED with a green status-check rollup (a required
    review gate blocking merge, not a red check). For each candidate, its most recent
    `RemovedFromMergeQueueEvent` (if any) is classified CODE / INFRA / CONFLICT / MANUAL /
    UNKNOWN. Only INFRA re-arms under budget (<=3 per (PR, head SHA) per rolling 24h, see
    `count_recent_infra_rearms`); CODE, CONFLICT, MANUAL and no-event-found (UNKNOWN) NEVER
    auto-rearm — the last two fail closed with a one-time Telegram alert (deduped per
    (PR, head SHA) so a stuck PR doesn't spam every 10 minutes).

(b) JANITOR (stale-run cancellation). Cancels QUEUED (never in_progress/completed) Actions runs
    that can no longer build anything useful: a `pull_request`-event run whose `head_sha` is not
    the current head of ANY open PR (the PR's head moved — a new run superseded it), or a
    `merge_group`-event run whose `head_branch` (`gh-readonly-queue/main/pr-N-<sha>`) no longer
    exists (the queue already ejected or merged that entry). Liveness is RE-VERIFIED with a
    fresh fetch immediately before each cancel call, not from the list used to build the
    candidate set — a run can go from stale to live (or vice versa) in the seconds a tick takes
    to walk its candidates, and cancelling on a stale READ would be a real mutation on a false
    premise (this repo's own fail-visible discipline, superscar #2/#9).

FAIL-CLOSED DISCIPLINE: any `gh` fetch failure raises (never returns a fabricated empty list —
an empty candidate set must never be confused with "gh api failed"). `--tick` catches such
errors at the top level, logs CANNOT-VERIFY, and exits without having mutated anything.

Kill switch: QUEUE_SHEPHERD_ENABLED=false makes every invocation a no-op that still prints a
receipt line (superscar #2: a mute cron reads as a dead cron with nothing to report — never
let silence be the only signal).

--dry-run (tick only): zero mutations — no `gh pr merge`, no run-cancel, no Telegram send, no
state-file write (mirrors queue_unstick.py's `--dry-run` contract exactly).

Env overrides:
    QUEUE_SHEPHERD_ENABLED       "false"/"0"/"no"/"off" -> no-op (default: on)
    QUEUE_SHEPHERD_REPO          default "Bali-Zero/Teman2"
    QUEUE_SHEPHERD_BUDGET_FILE   default ~/logs/queue-shepherd/rearm-budget.json
    QUEUE_SHEPHERD_ALERTED_FILE  default ~/logs/queue-shepherd/alerted-unknown.json
    QUEUE_SHEPHERD_LOG_FILE      default ~/logs/queue-shepherd.log
    TELEGRAM_OWNER_CHAT_ID       read at send time, never hardcoded in this file (per mandate —
                                 the CI-secret path is for GitHub Actions; a local organ reads
                                 the process env). Missing -> WARN + skip send, never fatal.

Tests: scripts/tests/test_queue_shepherd.py.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

REPO = os.environ.get("QUEUE_SHEPHERD_REPO", "Bali-Zero/Teman2")
BUDGET_FILE = Path(
    os.environ.get(
        "QUEUE_SHEPHERD_BUDGET_FILE", os.path.expanduser("~/logs/queue-shepherd/rearm-budget.json")
    )
)
ALERTED_FILE = Path(
    os.environ.get(
        "QUEUE_SHEPHERD_ALERTED_FILE",
        os.path.expanduser("~/logs/queue-shepherd/alerted-unknown.json"),
    )
)
LOG_FILE = Path(
    os.environ.get("QUEUE_SHEPHERD_LOG_FILE", os.path.expanduser("~/logs/queue-shepherd.log"))
)

# Organism heartbeat sidecar (organ-conformance G2, born 2026-08-27): the organ must prove its
# own liveness every run, on BOTH the success and failure path (superscar #2, esiste != armato —
# a launchd job with KeepAlive/StartInterval "green" tells you nothing about whether its last
# tick actually did anything). Mirrors dlq_autopilot.py's unconditional-heartbeat pattern.
ORGANISM_DIR = Path(os.path.expanduser("~/.organism/last_seen"))
ORGAN_ID = "pro.queue_shepherd"

INFRA_BUDGET_MAX = 3
BUDGET_WINDOW_HOURS = 24
BUDGET_GC_DAYS = 7  # prune (pr,sha) entries older than this so the file never grows unbounded

FABLE_GATE_CONTEXT_NAMES = ("harness/fable-gate", "harness-floor")

EJECTION_CLASSES = ("CODE", "INFRA", "CONFLICT", "MANUAL", "UNKNOWN")

# Same tiny heuristic queue_ejection_attribution.py::INFRA_JOB_NAME_SIGNATURES declares and
# duplicates rather than imports (see module docstring STANDALONE note above).
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

PR_SHA_RE = re.compile(r"pr-(\d+)-([0-9a-f]{40})")

logger = logging.getLogger("queue_shepherd")


def _configure_logging() -> None:
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=5
        )
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream)


# ---------------------------------------------------------------------------
# Pure functions — classification, budget, janitor selection. No I/O. These
# are what scripts/tests/test_queue_shepherd.py exercises directly.
# ---------------------------------------------------------------------------


def classify_ejection_reason(reason_raw: str | None, infra_hint: bool | None) -> str:
    """Map a RemovedFromMergeQueueEvent's raw `reason` (or None if no event was found at all)
    to a declared bucket in EJECTION_CLASSES. Mirrors
    queue_ejection_attribution.py::classify_removal_reason by declared design (duplicated, not
    imported — see module docstring).

    `reason_raw is None` means "no ejection event was found on the PR's timeline at all" — the
    PR looks disarmed right now but this script cannot say why. That is UNKNOWN, not CODE: never
    assume comprehension it does not have.
    """
    if reason_raw is None:
        return "UNKNOWN"
    if reason_raw == "failed_checks":
        if infra_hint is True:
            return "INFRA"
        return "CODE"  # infra_hint False or None — conservative default, never invented INFRA
    if reason_raw == "manual":
        return "MANUAL"
    if reason_raw == "merge_conflict":
        return "CONFLICT"
    return "UNKNOWN"  # a reason string this module has never seen — fail visible, never guessed


def _run_has_infra_signature(run: dict[str, Any], jobs: list[dict[str, Any]]) -> bool:
    """Mirrors queue_ejection_attribution.py::_run_is_infra_flavoured (duplicated, not
    imported — see module docstring). Caller only invokes this for a run that already failed.

    CODE wins over cancelled siblings (refuter round, agy pass, 2026-08-27): a matrix workflow
    with fail-fast cancels every OTHER job the instant one job fails for real. That cancellation
    is a symptom of the real failure, not an infra signal of its own — so a run containing ANY
    job that failed for a non-infra reason is CODE, full stop, even if the fail-fast cascade also
    cancelled its siblings. Only when NO job failed for a real reason do cancelled/timed-out jobs
    (or the run's own cancelled/timed-out conclusion) count as INFRA."""
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue
        name = str(job.get("name") or "").lower()
        if not any(sig in name for sig in INFRA_JOB_NAME_SIGNATURES):
            return False  # a real (non-infra-flavoured) job failure -> CODE, regardless of siblings
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


def is_rearm_candidate(pr: dict[str, Any]) -> bool:
    """Pure gate: is this open PR a re-arm candidate this tick?

    `pr` fields expected: is_draft, head_ref_name, has_fable_gate_status, in_queue,
    auto_merge_enabled, merge_state_status, status_rollup_state.

    W111 guard (`.claude/rules/cicatrix-scars.md` ~line 160): neither `autoMergeRequest` nor
    `mergeQueueEntry`/`isInMergeQueue` ALONE says "armed" — a queued PR has autoMergeRequest
    consumed (null) while carrying mergeQueueEntry; an armed-but-not-yet-queued PR has the
    inverse. Only BOTH null means truly disarmed, which is the only state this organ may act on.
    """
    if pr.get("is_draft"):
        return False
    if pr.get("in_queue") or pr.get("auto_merge_enabled"):
        return False  # already armed or already queued — W111, not our concern
    head_ref = pr.get("head_ref_name") or ""
    if not (head_ref.startswith("agent/") or pr.get("has_fable_gate_status")):
        return False  # not armed by this repo's own convention — never touch a PR we didn't arm
    status = pr.get("merge_state_status")
    if status in ("CLEAN", "UNSTABLE"):
        return True
    if status == "BLOCKED" and pr.get("status_rollup_state") == "SUCCESS":
        return True  # blocked on a review/approval gate, not on a red check
    return False


def _parse_iso(ts: str | None) -> _dt.datetime | None:
    """Returns an AWARE (UTC) datetime, or None. Every real caller compares the result against
    `_now()` (always tz-aware) — a naive result would raise TypeError at comparison time
    (uncaught anywhere between here and `tick()`, i.e. a full tick crash), not at parse time,
    which is why this went unnoticed (refuter round, agy pass, 2026-08-27). GitHub API timestamps
    always carry a Z/offset in practice, but this function must not depend on that being true
    forever (a hand-edited state file, a future API shape) — so a parse that comes back naive is
    coerced to UTC-aware here, once, rather than trusted to every call site."""
    if not ts:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed


def count_recent_infra_rearms(
    budget_state: dict[str, Any], pr_number: int, head_sha: str, now: _dt.datetime
) -> int:
    """Pure: how many INFRA re-arms have already been RECORDED for this exact (PR, head SHA)
    within the trailing BUDGET_WINDOW_HOURS. A head-SHA change is a fresh key with zero prior
    re-arms by construction — this IS the "head moved = reset" rule from the council spec; no
    separate reset code path is needed."""
    key = f"{pr_number}:{head_sha}"
    entry = budget_state.get(key) or {}
    timestamps = entry.get("infra_rearm_timestamps") or []
    cutoff = now - _dt.timedelta(hours=BUDGET_WINDOW_HOURS)
    count = 0
    for ts_raw in timestamps:
        ts = _parse_iso(ts_raw)
        if ts is not None and ts >= cutoff:
            count += 1
    return count


def record_infra_rearm(
    budget_state: dict[str, Any], pr_number: int, head_sha: str, now: _dt.datetime
) -> dict[str, Any]:
    """Pure: returns a NEW budget_state with this re-arm recorded. Never mutates the input dict
    in place (callers own persistence, mirrors dlq_autopilot.py's sweep-and-return contract)."""
    key = f"{pr_number}:{head_sha}"
    new_state = json.loads(json.dumps(budget_state))  # cheap deep copy, JSON-safe by contract
    entry = new_state.setdefault(key, {"infra_rearm_timestamps": []})
    entry["infra_rearm_timestamps"].append(now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    entry["pr_number"] = pr_number
    entry["head_sha"] = head_sha
    entry["last_seen"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return new_state


def gc_budget_state(budget_state: dict[str, Any], now: _dt.datetime) -> dict[str, Any]:
    """Pure: drop (pr, sha) entries whose every recorded timestamp is older than BUDGET_GC_DAYS,
    so the file never grows unbounded across the life of the repo. Never drops an entry that
    still has a timestamp inside the window — GC is a size bound, not a budget bypass."""
    cutoff = now - _dt.timedelta(days=BUDGET_GC_DAYS)
    kept: dict[str, Any] = {}
    for key, entry in budget_state.items():
        timestamps = entry.get("infra_rearm_timestamps") or []
        parsed = [t for t in (_parse_iso(ts) for ts in timestamps) if t is not None]
        if parsed and max(parsed) >= cutoff:
            kept[key] = entry
    return kept


def decide_rearm(
    klass: str, budget_state: dict[str, Any], pr_number: int, head_sha: str, now: _dt.datetime
) -> tuple[bool, str]:
    """Pure decision: (allowed, reason_code). Never mutates budget_state — the caller records a
    successful INFRA re-arm separately via record_infra_rearm, only after the real `gh` call
    (recorded by outcome in production, immediately in tests) succeeds."""
    if klass == "INFRA":
        count = count_recent_infra_rearms(budget_state, pr_number, head_sha, now)
        if count >= INFRA_BUDGET_MAX:
            return False, f"infra_budget_exhausted({count}/{INFRA_BUDGET_MAX})"
        return True, f"infra_budget_ok({count}/{INFRA_BUDGET_MAX})"
    if klass == "CODE":
        return False, "code_never_rearm"
    if klass in ("CONFLICT", "MANUAL"):
        return False, f"{klass.lower()}_no_auto_rearm"
    return False, "unknown_fail_closed"  # UNKNOWN, or any class this module has never seen


def select_stale_pull_request_runs(
    queued_runs: list[dict[str, Any]], live_pr_heads: set[str]
) -> list[dict[str, Any]]:
    """Pure: `pull_request`-event queued runs whose head_sha is not the CURRENT head of any
    open PR. A run whose head_sha IS a live PR head is never selected, however old the run —
    liveness is the only test, never age (a slow runner queue is not this organ's business)."""
    return [
        run
        for run in queued_runs
        if run.get("event") == "pull_request" and run.get("head_sha") not in live_pr_heads
    ]


def select_stale_merge_group_runs(
    queued_runs: list[dict[str, Any]], live_queue_branches: set[str]
) -> list[dict[str, Any]]:
    """Pure: `merge_group`-event queued runs whose head_branch no longer exists as a live
    gh-readonly-queue ref — the queue already ejected or merged that entry."""
    return [
        run
        for run in queued_runs
        if run.get("event") == "merge_group" and run.get("head_branch") not in live_queue_branches
    ]


# ---------------------------------------------------------------------------
# I/O — subprocess + gh wrappers. Monkeypatched wholesale in tests (same seam
# convention as queue_unstick.py / queue_ejection_attribution.py: a module-level
# `_run`, replaced by the test, never a mock library).
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command; never raises. Returns (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


def _gh_graphql(query: str, variables: dict[str, Any], timeout: int = 45) -> dict[str, Any]:
    """Raises RuntimeError on any failure — never returns a fabricated empty structure
    (superscar #2/#9: a failed fetch must never be read as 'nothing to do')."""
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        flag = "-F" if isinstance(value, (int, bool)) else "-f"
        args += [flag, f"{key}={value}"]
    rc, out, err = _run(args, timeout=timeout)
    if rc != 0:
        raise RuntimeError(f"gh api graphql failed rc={rc}: {err.strip()[:500]}")
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"unparseable graphql response: {exc!s}: {out[:300]}") from exc


REARM_CANDIDATES_QUERY = """
query($owner:String!, $repo:String!, $cursor:String) {
  repository(owner:$owner, name:$repo) {
    pullRequests(states:OPEN, first:100, after:$cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        isDraft
        headRefName
        headRefOid
        mergeStateStatus
        autoMergeRequest { enabledAt }
        mergeQueueEntry { state }
        commits(last:1) {
          nodes {
            commit {
              statusCheckRollup { state }
              status { contexts { context } }
              checkSuites(first:20) { nodes { checkRuns(first:20) { nodes { name } } } }
            }
          }
        }
      }
    }
  }
}
"""


def _pr_has_fable_gate_status(node: dict[str, Any]) -> bool:
    commits = (node.get("commits") or {}).get("nodes") or []
    if not commits:
        return False
    commit = commits[0].get("commit") or {}
    contexts = [c.get("context") for c in ((commit.get("status") or {}).get("contexts") or [])]
    if any(ctx in FABLE_GATE_CONTEXT_NAMES for ctx in contexts if ctx):
        return True
    for suite in (commit.get("checkSuites") or {}).get("nodes") or []:
        for run in (suite.get("checkRuns") or {}).get("nodes") or []:
            if run.get("name") in FABLE_GATE_CONTEXT_NAMES:
                return True
    return False


def _normalize_rearm_pr(node: dict[str, Any]) -> dict[str, Any]:
    commits = (node.get("commits") or {}).get("nodes") or []
    rollup_state = None
    if commits:
        rollup_state = ((commits[0].get("commit") or {}).get("statusCheckRollup") or {}).get(
            "state"
        )
    return {
        "number": node["number"],
        "is_draft": bool(node.get("isDraft")),
        "head_ref_name": node.get("headRefName") or "",
        "head_sha": node.get("headRefOid") or "",
        "merge_state_status": node.get("mergeStateStatus"),
        "auto_merge_enabled": bool(node.get("autoMergeRequest")),
        "in_queue": bool(node.get("mergeQueueEntry")),
        "status_rollup_state": rollup_state,
        "has_fable_gate_status": _pr_has_fable_gate_status(node),
    }


def fetch_rearm_candidate_prs(repo: str = REPO) -> list[dict[str, Any]]:
    """Every open PR, normalized + filtered through is_rearm_candidate. Raises on fetch
    failure (see _gh_graphql) — CANNOT-VERIFY must never be read as an empty candidate list."""
    owner, name = repo.split("/", 1)
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        variables: dict[str, Any] = {"owner": owner, "repo": name}
        if cursor:
            variables["cursor"] = cursor
        data = _gh_graphql(REARM_CANDIDATES_QUERY, variables)
        try:
            page = data["data"]["repository"]["pullRequests"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"unexpected graphql shape: {exc}: {json.dumps(data)[:300]}") from exc
        for node in page["nodes"]:
            pr = _normalize_rearm_pr(node)
            if is_rearm_candidate(pr):
                out.append(pr)
        if page["pageInfo"]["hasNextPage"]:
            cursor = page["pageInfo"]["endCursor"]
        else:
            break
    return out


TIMELINE_QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      timelineItems(last:10, itemTypes:[REMOVED_FROM_MERGE_QUEUE_EVENT, ADDED_TO_MERGE_QUEUE_EVENT]) {
        nodes {
          __typename
          ... on RemovedFromMergeQueueEvent { createdAt reason beforeCommit { oid } }
          ... on AddedToMergeQueueEvent { createdAt }
        }
      }
    }
  }
}
"""


def fetch_last_ejection(repo: str, number: int) -> dict[str, Any] | None:
    """The PR's most recent timeline item among Added/Removed-from-merge-queue events, IF it is
    a Removed event (i.e. the PR is not simply sitting freshly-added / never-queued). Returns
    None when the last item is an Added event or there is no such item at all — both cases mean
    "no ejection reason is known", which the caller must treat as UNKNOWN, never as CODE.
    Raises on fetch failure (see _gh_graphql)."""
    owner, name = repo.split("/", 1)
    data = _gh_graphql(TIMELINE_QUERY, {"owner": owner, "repo": name, "number": number})
    try:
        nodes = data["data"]["repository"]["pullRequest"]["timelineItems"]["nodes"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"unexpected graphql shape: {exc}: {json.dumps(data)[:300]}") from exc
    if not nodes:
        return None
    last = nodes[-1]
    if last.get("__typename") != "RemovedFromMergeQueueEvent":
        return None
    return {
        "reason": last.get("reason"),
        "removed_at": last.get("createdAt"),
        "before_commit": (last.get("beforeCommit") or {}).get("oid"),
    }


def fetch_infra_hint(repo: str, number: int, removed_at: str | None) -> bool | None:
    """Best-effort correlation of a failed_checks removal to an INFRA-flavoured job, honest
    about its own gap: this looks at the PR's most recent merge_group runs by branch-name
    prefix (`pr-<number>-`), NOT an exhaustive day-window reconstruction like
    queue_ejection_attribution.py's audit-grade version — that module exists for retrospective
    accuracy across a whole day; this one exists to make ONE re-arm decision right now, and a
    None (unresolved) answer here falls through to the conservative CODE default in
    classify_ejection_reason, never to a guessed INFRA. Returns None on any fetch/parse failure
    or when no correlated run is found — never silently invents True or False."""
    owner, name = repo.split("/", 1)
    rc, out, err = _run(
        [
            "gh", "api",
            f"repos/{owner}/{name}/actions/runs?event=merge_group&per_page=20",
        ],
        timeout=30,
    )
    if rc != 0:
        logger.warning("fetch_infra_hint: gh api runs failed rc=%s err=%s", rc, err.strip()[:200])
        return None
    try:
        runs = json.loads(out).get("workflow_runs") or []
    except json.JSONDecodeError:
        return None
    removed_dt = _parse_iso(removed_at)
    # W111-adjacent fix (refuter round, agy pass, 2026-08-27): a merge_group run's real
    # head_branch is the full `gh-readonly-queue/main/pr-<n>-<sha>` ref, never a bare
    # `pr-<n>-<sha>` — a plain .startswith(f"pr-{number}-") NEVER matches it, so this used to
    # find zero candidates on every call and fall through to the conservative CODE default
    # unconditionally. PR_SHA_RE (module-level, previously unused) is matched anywhere in the
    # ref instead of anchored at position 0, and the captured PR number is compared numerically
    # so it never confuses PR #4 with PR #47.
    candidates = []
    for r in runs:
        match = PR_SHA_RE.search(str(r.get("head_branch") or ""))
        if (
            match
            and int(match.group(1)) == number
            and r.get("conclusion") in ("failure", "cancelled", "timed_out")
        ):
            candidates.append(r)
    if removed_dt is not None:
        candidates = [
            r for r in candidates if (_parse_iso(r.get("created_at")) or removed_dt) <= removed_dt
        ]
    if not candidates:
        return None
    candidates.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    run = candidates[0]
    rc, jobs_out, _err = _run(
        ["gh", "api", f"repos/{owner}/{name}/actions/runs/{run['id']}/jobs?per_page=50"],
        timeout=30,
    )
    jobs: list[dict[str, Any]] = []
    if rc == 0:
        try:
            jobs = json.loads(jobs_out).get("jobs") or []
        except json.JSONDecodeError:
            jobs = []
    return _run_has_infra_signature(run, jobs)


def fetch_open_pr_heads(repo: str = REPO) -> set[str]:
    """Fresh set of CURRENT head SHAs for every open PR — used both to build the stale-run
    candidate set and, separately called again, to re-verify liveness immediately before each
    cancel. Raises on fetch failure."""
    owner, name = repo.split("/", 1)
    query = """
    query($owner:String!, $repo:String!, $cursor:String) {
      repository(owner:$owner, name:$repo) {
        pullRequests(states:OPEN, first:100, after:$cursor) {
          pageInfo { hasNextPage endCursor }
          nodes { headRefOid }
        }
      }
    }
    """
    heads: set[str] = set()
    cursor: str | None = None
    while True:
        variables: dict[str, Any] = {"owner": owner, "repo": name}
        if cursor:
            variables["cursor"] = cursor
        data = _gh_graphql(query, variables)
        try:
            page = data["data"]["repository"]["pullRequests"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"unexpected graphql shape: {exc}") from exc
        for node in page["nodes"]:
            sha = node.get("headRefOid")
            if sha:
                heads.add(sha)
        if page["pageInfo"]["hasNextPage"]:
            cursor = page["pageInfo"]["endCursor"]
        else:
            break
    return heads


def fetch_live_queue_branches(repo: str = REPO) -> set[str]:
    """Fresh set of live `gh-readonly-queue/main/...` ref names, paginated. Raises on fetch
    failure — the caller (run_janitor_pass and the per-run cancel-time recheck) already treats a
    RuntimeError here as CANNOT-VERIFY and cancels NOTHING that tick, so failing loud here is
    what keeps the janitor fail-closed rather than fail-open.

    Paginated (refuter round, agy pass, 2026-08-27): `git/matching-refs` defaults to 30 refs per
    page like every other GitHub REST list endpoint. Un-paginated, a busy merge queue with more
    than 30 live entries would silently drop the tail — and a branch missing from this set reads
    to `select_stale_merge_group_runs` as "already ejected", which cancels a run that is still
    building. Mirrors fetch_queued_runs's page-count loop + safety bound (W97 style)."""
    owner, name = repo.split("/", 1)
    branches: set[str] = set()
    page = 1
    while True:
        rc, out, err = _run(
            [
                "gh", "api",
                f"repos/{owner}/{name}/git/matching-refs/heads/gh-readonly-queue"
                f"?per_page=100&page={page}",
            ],
            timeout=30,
        )
        if rc != 0:
            raise RuntimeError(f"gh api matching-refs failed rc={rc}: {err.strip()[:300]}")
        try:
            refs = json.loads(out)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"unparseable matching-refs response: {exc!s}") from exc
        for ref in refs:
            name_ref = str(ref.get("ref") or "")
            if name_ref.startswith("refs/heads/"):
                branches.add(name_ref[len("refs/heads/"):])
        if len(refs) < 100:
            break
        page += 1
        if page > 20:  # a 2,000-entry live queue is not a realistic shape; a safety bound
            logger.warning("fetch_live_queue_branches: hit page safety bound at page=%s", page)
            break
    return branches


def fetch_queued_runs(repo: str = REPO) -> list[dict[str, Any]]:
    """Every currently-QUEUED (never in_progress/completed) Actions run, paginated, normalized
    to {id, event, head_sha, head_branch, name}. Raises on fetch failure."""
    owner, name = repo.split("/", 1)
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        rc, body, err = _run(
            [
                "gh", "api",
                f"repos/{owner}/{name}/actions/runs?status=queued&per_page=100&page={page}",
            ],
            timeout=45,
        )
        if rc != 0:
            raise RuntimeError(f"gh api actions/runs failed rc={rc}: {err.strip()[:300]}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"unparseable actions/runs response: {exc!s}") from exc
        runs = payload.get("workflow_runs") or []
        for run in runs:
            out.append(
                {
                    "id": run.get("id"),
                    "event": run.get("event"),
                    "head_sha": run.get("head_sha"),
                    "head_branch": run.get("head_branch"),
                    "name": run.get("name"),
                }
            )
        if len(runs) < 100:
            break
        page += 1
        if page > 20:  # 2,000 queued runs is not a realistic shape; a safety bound (W97 style)
            logger.warning("fetch_queued_runs: hit page safety bound at page=%s", page)
            break
    return out


def rearm_pr(repo: str, number: int) -> bool:
    """`gh pr merge N --auto` BARE — this repo's merge queue rejects every strategy flag
    (--squash included), per docs/runbooks/merge-queue-discipline.md session discipline."""
    rc, out, err = _run(["gh", "pr", "merge", str(number), "--auto", "--repo", repo], timeout=30)
    if rc != 0:
        logger.warning("rearm_pr(#%s) failed rc=%s out=%s err=%s", number, rc, out.strip()[:200], err.strip()[:200])
        return False
    return True


def cancel_run(repo: str, run_id: int) -> bool:
    owner, name = repo.split("/", 1)
    rc, out, err = _run(
        ["gh", "api", "-X", "POST", f"repos/{owner}/{name}/actions/runs/{run_id}/cancel"],
        timeout=30,
    )
    if rc != 0:
        logger.warning("cancel_run(%s) failed rc=%s err=%s", run_id, rc, err.strip()[:200])
        return False
    return True


def send_telegram(message: str, dedup_key: str = "") -> bool:
    """Delegates to the repo's existing notification gateway (scripts/tg_notify.py — same
    convention scripts/dlq_autopilot.py already uses). The gateway owns token resolution
    (reads TELEGRAM_OWNER_CHAT_ID / bot token from the process env at send time), dedup and
    the daily P0 budget; this function never reads or hardcodes a chat id itself (mandate:
    the GitHub-secret path is for CI, a local organ reads the env — via the gateway).

    Returns whether the send actually succeeded (refuter round, agy pass, 2026-08-27): the
    caller must record `alerted_state` ONLY on a successful send, or a transient gateway/network
    failure on the FIRST attempt permanently swallows the alert — the dedup key would already be
    marked "delivered" for a message nobody ever received."""
    gateway = SCRIPTS_DIR / "tg_notify.py"
    if not gateway.exists():  # HOME-fork copy: fall back to the repo checkout (superscar #1)
        gateway = REPO_ROOT / "scripts" / "tg_notify.py"
    if not gateway.exists():
        logger.warning("send_telegram: tg_notify.py not found, skipping send")
        return False
    cmd = [sys.executable, str(gateway), "--tier", "p0", "--source", "queue-shepherd"]
    if dedup_key:
        cmd += ["--dedup-key", dedup_key]
    cmd += ["--", f"\U0001f9ed QueueShepherd | {message}"]
    rc, _out, err = _run(cmd, timeout=30)
    if rc != 0:
        logger.warning("send_telegram: tg_notify failed rc=%s err=%s", rc, err.strip()[:200])
        return False
    return True


# ---------------------------------------------------------------------------
# State (budget + alerted-dedup) persistence.
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any]:
    """A missing file means "no state yet" -> {} (normal on first run). A file that EXISTS but
    fails to parse (torn write, disk corruption, hand-edit gone wrong) is a different situation
    entirely and must never collapse to the same {} — that is precisely the "budget silently
    resets" bypass the council barred (refuter round, agy pass, 2026-08-27). Raises RuntimeError
    in that case so the caller can fail closed instead of granting a fresh, unlimited budget."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise RuntimeError(f"unreadable state file {path}: {exc!s}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"corrupt/unparseable state file {path}: {exc!s}") from exc


def _save_json(path: Path, data: dict[str, Any]) -> None:
    """Atomic write: write-then-rename so a crash/kill mid-write never leaves a torn file for the
    next `_load_json` to trip over (refuter round, agy pass, 2026-08-27 — same finding as above,
    the other half of the fix). `os.replace` is atomic on the same filesystem, which the tmp file
    is guaranteed to be since it lives in the same parent directory as the real path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


# ---------------------------------------------------------------------------
# Tick orchestration.
# ---------------------------------------------------------------------------


def _enabled() -> bool:
    return os.environ.get("QUEUE_SHEPHERD_ENABLED", "true").strip().lower() not in (
        "false", "0", "no", "off",
    )


def run_rearm_pass(dry_run: bool, now: _dt.datetime) -> int:
    """Returns count of PRs re-armed. Loads/saves budget+alerted state unless dry_run.

    Fail-closed on state corruption (refuter round, agy pass, 2026-08-27): a torn/corrupt budget
    file must NEVER be read as "no re-arms recorded yet" — that silently grants a fresh
    INFRA_BUDGET_MAX allowance, exactly the bypass the council barred. `_load_json` now raises on
    a parse failure (vs. a simply-missing file, which is normal and returns {}); this pass treats
    that as CANNOT-VERIFY and re-arms NOTHING this tick, same posture as a `gh` fetch failure."""
    try:
        budget_state = {} if dry_run else _load_json(BUDGET_FILE)
        alerted_state = {} if dry_run else _load_json(ALERTED_FILE)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY rearm/alert state: %s", exc)
        return 0
    budget_state = gc_budget_state(budget_state, now)

    try:
        candidates = fetch_rearm_candidate_prs(REPO)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY rearm candidates: %s", exc)
        return 0

    rearmed = 0
    for pr in candidates:
        number = pr["number"]
        head_sha = pr["head_sha"]
        try:
            ejection = fetch_last_ejection(REPO, number)
        except RuntimeError as exc:
            logger.error("PR #%s: CANNOT-VERIFY ejection timeline: %s", number, exc)
            continue
        reason_raw = ejection["reason"] if ejection else None
        infra_hint: bool | None = None
        if reason_raw == "failed_checks":
            try:
                infra_hint = fetch_infra_hint(
                    REPO, number, ejection.get("removed_at") if ejection else None
                )
            except RuntimeError as exc:
                logger.warning("PR #%s: infra_hint fetch failed: %s", number, exc)
        klass = classify_ejection_reason(reason_raw, infra_hint)
        allowed, why = decide_rearm(klass, budget_state, number, head_sha, now)
        logger.info(
            "PR #%s head=%s class=%s allowed=%s (%s)", number, head_sha[:8], klass, allowed, why
        )
        alert_key = f"{number}:{head_sha}"
        if not allowed:
            if klass == "UNKNOWN" and not dry_run and not alerted_state.get(alert_key):
                sent = send_telegram(
                    f"PR #{number} looks disarmed (head {head_sha[:8]}) with no readable "
                    f"ejection reason — fail-closed, no auto-rearm. Needs a human look.",
                    dedup_key=f"queue-shepherd-unknown-{alert_key}",
                )
                if sent:  # only a DELIVERED alert may be dedup-suppressed on future ticks
                    alerted_state[alert_key] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            continue
        if dry_run:
            logger.info("[dry-run] would run: gh pr merge %s --auto", number)
            rearmed += 1
            continue
        if rearm_pr(REPO, number):
            budget_state = record_infra_rearm(budget_state, number, head_sha, now)
            alerted_state.pop(alert_key, None)  # a live re-arm supersedes any stale alert
            rearmed += 1

    if not dry_run:
        _save_json(BUDGET_FILE, budget_state)
        _save_json(ALERTED_FILE, alerted_state)
    return rearmed


def run_janitor_pass(dry_run: bool) -> int:
    """Returns count of runs cancelled."""
    try:
        queued_runs = fetch_queued_runs(REPO)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY queued runs: %s", exc)
        return 0

    try:
        live_heads = fetch_open_pr_heads(REPO)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY open PR heads: %s", exc)
        return 0
    try:
        live_branches = fetch_live_queue_branches(REPO)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY live queue branches: %s", exc)
        return 0

    stale = select_stale_pull_request_runs(queued_runs, live_heads) + select_stale_merge_group_runs(
        queued_runs, live_branches
    )

    cancelled = 0
    for run in stale:
        # Re-verify liveness AT CANCEL TIME with a fresh fetch — never trust the list above,
        # which may already be stale by the time this specific run is reached (mandate: "not
        # from a stale list").
        try:
            if run["event"] == "pull_request":
                still_stale = run["head_sha"] not in fetch_open_pr_heads(REPO)
            else:
                still_stale = run["head_branch"] not in fetch_live_queue_branches(REPO)
        except RuntimeError as exc:
            logger.warning("run %s: CANNOT-VERIFY at cancel-time recheck, skipping: %s", run["id"], exc)
            continue
        if not still_stale:
            logger.info("run %s (%s): became live between discovery and cancel, skipping", run["id"], run.get("name"))
            continue
        if dry_run:
            logger.info("[dry-run] would cancel run %s (%s, event=%s)", run["id"], run.get("name"), run["event"])
            cancelled += 1
            continue
        if cancel_run(REPO, run["id"]):
            logger.info("cancelled stale run %s (%s, event=%s)", run["id"], run.get("name"), run["event"])
            cancelled += 1
    return cancelled


def _write_heartbeat(status: str, metadata: dict[str, Any]) -> None:
    """Unconditional organism heartbeat sidecar — never raises (a heartbeat write must never
    break the run it is reporting on). Atomic write via tmp+replace, same pattern as
    dlq_autopilot.py's organ heartbeat."""
    try:
        ORGANISM_DIR.mkdir(parents=True, exist_ok=True)
        organ_path = ORGANISM_DIR / f"{ORGAN_ID}.json"
        organ_tmp = organ_path.with_suffix(f".json.tmp.{os.getpid()}")
        organ_tmp.write_text(
            json.dumps(
                {
                    "ts": time.time(),
                    "status": status,
                    "organ_id": ORGAN_ID,
                    "metadata": metadata,
                }
            )
        )
        organ_tmp.replace(organ_path)
    except Exception as exc:  # noqa: BLE001 — heartbeat must never break the run
        logger.warning("organ heartbeat emit failed: %s", exc)


def tick(dry_run: bool) -> int:
    if not _enabled():
        logger.info("QUEUE_SHEPHERD_ENABLED=false — no-op tick (receipt line, superscar #2)")
        # G5: a kill-switched organ is alive-but-idle, not silent — write an explicit
        # disabled heartbeat so the staleness monitor never mistakes this for a dead
        # organ (agy cross-family review, PR #5071: "disabled state is ambiguous").
        _write_heartbeat("disabled", {"reason": "QUEUE_SHEPHERD_ENABLED=false"})
        return 0
    now = _now()
    try:
        rearmed = run_rearm_pass(dry_run, now)
        cancelled = run_janitor_pass(dry_run)
    except Exception as exc:  # noqa: BLE001 — G2: heartbeat the failure path too, then re-raise
        _write_heartbeat("error", {"error": str(exc), "dry_run": dry_run})
        raise
    logger.info(
        "tick complete: rearmed=%s cancelled=%s dry_run=%s", rearmed, cancelled, dry_run
    )
    _write_heartbeat("ok", {"rearmed": rearmed, "cancelled": cancelled, "dry_run": dry_run})
    return 0


def report() -> int:
    try:
        budget_state = _load_json(BUDGET_FILE)
    except RuntimeError as exc:
        logger.error("%s", exc)
        print(f"budget file: {BUDGET_FILE} — CORRUPT, cannot parse ({exc})")
        budget_state = {}
    try:
        alerted_state = _load_json(ALERTED_FILE)
    except RuntimeError as exc:
        logger.error("%s", exc)
        print(f"alerted file: {ALERTED_FILE} — CORRUPT, cannot parse ({exc})")
        alerted_state = {}
    print(f"queue_shepherd report — repo={REPO} enabled={_enabled()}")
    print(f"budget file: {BUDGET_FILE} ({'exists' if BUDGET_FILE.exists() else 'missing'})")
    print(f"  tracked (pr,sha) keys: {len(budget_state)}")
    now = _now()
    for key, entry in sorted(budget_state.items()):
        count = count_recent_infra_rearms(
            budget_state, entry.get("pr_number", 0), entry.get("head_sha", ""), now
        )
        print(f"    {key}: {count}/{INFRA_BUDGET_MAX} infra rearms in last {BUDGET_WINDOW_HOURS}h")
    print(f"alerted (UNKNOWN, undelivered-until-resolved) keys: {len(alerted_state)}")
    for key, ts in sorted(alerted_state.items()):
        print(f"    {key}: alerted at {ts}")
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        print(f"last log lines ({LOG_FILE}):")
        for line in lines[-10:]:
            print(f"    {line}")
    else:
        print(f"log file not found yet: {LOG_FILE}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tick", action="store_true", help="run one shepherd tick (cron entry)")
    parser.add_argument("--report", action="store_true", help="print state, budget, last actions")
    parser.add_argument("--dry-run", action="store_true", help="tick only: zero mutations")
    args = parser.parse_args(argv)

    if args.report:
        return report()
    if args.tick:
        return tick(dry_run=args.dry_run)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
