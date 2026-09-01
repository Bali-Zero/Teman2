#!/usr/bin/env python3
"""queue_stall_classifier.py — a REPORTER, never an actuator. Squad-S disposition on issue
#5316 (comment 02:32), item 2.

WHY THIS EXISTS: the night of 2026-08-30/31, this repo's merge queue never stalled for a
mechanical reason — nothing was ejected, nothing needed a rerun. It stalled on JUDGEMENT: a
missing gate verdict, red checks needing diagnosis. Those are exactly the moves a bot must not
make on its own — rerunning a red check replays a stale merge ref (W111,
`docs/scars/cicatrix-scars.md`), and posting a gate verdict with no independent reader is
self-grading. `scripts/queue_shepherd.py` already owns the two things a bot MAY safely do
(budgeted re-arm, stale-run cancellation). This script owns the third thing: naming WHY a PR is
stuck, so a human (or the next gate session) knows where to look, without ever touching the PR.

THIS SCRIPT NEVER MUTATES ANYTHING — no `gh pr merge`, no `gh run rerun`, no commit status, no
`gh pr edit/comment/review/close`, no run-cancel. It only reads and prints. Enforced by this
module's own test suite as a static AST proof over its source (mirrors
scripts/tests/test_harness_gate_read.py's own self-protecting scan), not just by inspection.

CLOSED CAUSE SET (one label per stalled PR, in this PRECEDENCE order — see classify_stall()'s
own docstring for why this order and not another):
    1. conflict              — mergeStateStatus == DIRTY, RE-VERIFIED with a fresh fetch
    2. gate-verdict-missing  — the required "Harness floor recompute" check is red and no
                                harness/fable-gate verdict has EVER been posted on the real head
                                sha (process, not code)
    3. required-check-red    — any other red required check, including a REAL posted
                                REWORK/BLOCK fable-gate verdict (a judgment already exists)
    4. not-armed              — W111 guard: BOTH autoMergeRequest and mergeQueueEntry are null
    5. queued-and-advancing  — armed/queued, no known blocker; may simply be slow
Plus, per-PR, "CANNOT-VERIFY" when a network call fails for that PR specifically — never a
guess, and never a silent skip (queue_shepherd.py's own fail-visible convention).

CORRECTNESS TRAPS THIS SCRIPT RESPECTS (each already measured, live, in this repo):

  (a) `gh pr view --json` has NO `mergeQueueEntry` field at all — every field this script needs
      (mergeStateStatus, autoMergeRequest, mergeQueueEntry, statusCheckRollup, checkSuites) is
      read via `gh api graphql`, mirroring queue_shepherd.py's own REARM_CANDIDATES_QUERY.

  (b) `autoMergeRequest: null` ALONE never means "not armed" — a queued PR has it consumed
      (null) while it still holds a `mergeQueueEntry` (W111,
      `docs/scars/cicatrix-scars.md` ~line 160). `not-armed` requires BOTH null.

  (c) A DIRTY `mergeStateStatus` read minutes ago can already be wrong — the fleet-watch
      "queue_unstick" mailbox this SAME session observed live carries multiple entries reading
      "PR #NNNN is DIRTY ... conflicting files: none (merge-tree found no conflict at probe
      time)". `conflict` is therefore never assigned from the bulk-discovery read: a candidate
      whose bulk `mergeStateStatus == "DIRTY"` gets ONE extra, immediate, single-PR re-fetch
      (fetch_fresh_merge_state) before the verdict is finalized.

  (d) checkSuites PAGINATION: a real PR in this repo (#4569, measured live 2026-08-31) carries
      38 check suites / 59 check runs — "Harness floor recompute" was suite #30. A naive
      `checkSuites(first:20)` (the size queue_shepherd.py's OWN REARM_CANDIDATES_QUERY uses for
      an unrelated, lower-stakes lookup) would silently never find it on a PR shaped like this
      one, misreading "not found" as "gate not applicable" when it is really "gate hiding past
      page 1". CHECK_SUITES_PAGE_SIZE is sized at 100 (>2.5x that measurement, not a guess), and
      `fetch_check_runs_flat` explicitly detects truncation (totalCount > fetched nodes, at
      EITHER the suite or the per-suite checkRuns level) and reports it — a truncated "not
      found" downgrades that PR's row to CANNOT-VERIFY rather than silently defaulting to
      required-check-red, which would make the table lie about the single most common cause.

  (e) The `harness/fable-gate` verdict is read the SAME way scripts/ci/harness_gate_read.py
      itself reads it — the combined `commits/{sha}/status` REST endpoint for the literal
      context string `harness/fable-gate` — NOT by fetching/grepping the job's raw run log for
      the string `harness_gate_read: PENDING`. Both signals are provably equivalent
      (harness_gate_read.py::decide(): `state is None` IS the PENDING case, verbatim), and the
      REST read is far cheaper and does not require resolving a job/run id at all.
      `read_fable_gate_state` below duplicates that function's logic rather than importing it —
      same STANDALONE-by-design convention queue_shepherd.py and
      queue_ejection_attribution.py already declare for this family of small independent
      organs (a coupling would mean an edit to the CI gate script could silently change this
      read-only reporter's classification, and vice versa).

  (f) A network failure for one PR must never be silently skipped nor guessed — it is reported
      as CANNOT-VERIFY for that PR and the run continues for the rest. A network failure on the
      TOP-LEVEL open-PR fetch fails the whole run loudly (non-zero exit, no table at all).

  (g) "A check that passes having examined nothing is the exact esiste!=armato defect class"
      (mandate, verbatim) — if the top-level fetch returns ZERO open PRs total (implausible for
      an active repo), main() exits non-zero and says so, rather than printing a clean empty
      table. This is deliberately checked against the RAW open-PR count, before the
      draft/age filters — a genuinely empty STALL set (nothing old enough to report) is a
      legitimate, calm, exit-0 outcome; an empty RAW fetch is not.

  (h) TWO checkRuns can share the exact name "Harness floor recompute" on the SAME commit — a
      `workflow_dispatch` rerun of the gate lands in a DIFFERENT check suite than the original
      `pull_request` run (Agent PR Contract rule 3), so a naive first-match lookup is
      order-dependent on GraphQL's unspecified checkSuites ordering and can misclassify in
      EITHER direction (found by an independent second-opinion review, kimi-code/k3,
      2026-08-31). `find_named_check_conclusion` returns AMBIGUOUS_CHECK_CONCLUSION when
      matches disagree, and `_classify_one` reads that as CANNOT-VERIFY rather than guessing —
      the same discipline already applied to a truncated fetch in trap (d). The same review
      also found `RED_CHECK_CONCLUSIONS` omitted `TIMED_OUT` — a genuine gate-rejection shape
      (a required job that overran its timeout is exactly as rejected as one that failed
      outright) that the original exclusion comment never actually named as deliberate; it is
      now included alongside FAILURE.

AGE: measured from `createdAt` (PR open time), never `updatedAt` — an `updatedAt` bump from an
unrelated event (a comment, a label, a rebase) would silently drop a genuinely-stalled PR from
the very report that exists to catch it. DEFAULT_MIN_AGE_MINUTES=30 is 3x
queue_shepherd.py's own 10-minute tick cadence: long enough that ordinary CI/queue churn
resolves itself, short enough to catch a same-night stall.

Tests: scripts/tests/test_queue_stall_classifier.py.
"""

from __future__ import annotations

import argparse
import collections
import datetime as _dt
import json
import logging
import subprocess
import sys
from typing import Any

REPO_DEFAULT = "Bali-Zero/Teman2"
DEFAULT_MIN_AGE_MINUTES = 30
MAX_PAGES = 20  # safety bound on open-PR pagination — a 2,000-open-PR repo is not a realistic
# shape here (W97-style bound, mirrors queue_shepherd.py's own fetch_queued_runs/
# fetch_live_queue_branches page bounds); hitting it WITHOUT exhausting pagination raises
# (see fetch_open_prs) rather than looping forever OR silently returning a partial board.

HARNESS_FLOOR_CHECK_NAME = "Harness floor recompute"  # the required WORKFLOW JOB name, from
# .github/workflows/harness-floor.yml's own `name:` key — confirmed live via
# research/operations/2026-08-21-fable-gate-required-promotion.md and a live `gh api` pull
# against PR #4569 (2026-08-31).
FABLE_GATE_STATUS_CONTEXT = "harness/fable-gate"  # duplicated from
# scripts/ci/harness_gate_read.py::CONTEXT — see module docstring trap (e).

CHECK_SUITES_PAGE_SIZE = 100  # see module docstring trap (d) — measured live 2026-08-31: a
# real PR here carries 38 check suites.
CHECK_RUNS_PAGE_SIZE = 20  # every suite sampled live carries exactly 1 checkRun; generous
# headroom for a matrix job.

RED_ROLLUP_STATES = ("FAILURE", "ERROR")
RED_CHECK_CONCLUSIONS = ("FAILURE", "TIMED_OUT")  # deliberately narrow: CANCELLED/NEUTRAL/
# SKIPPED/ACTION_REQUIRED are not "the gate rejected you" shapes, they are closer to
# infra-hiccup or not-yet-run — left to the generic status_rollup_state check rather than
# folded in here. TIMED_OUT IS a gate-rejection shape (a required job that overran its
# timeout-minutes is exactly as rejected as one that failed outright) and was a genuine
# omission from the original exclusion list, not a deliberate one — found by an independent
# second-opinion review (kimi-code/k3, 2026-08-31): the comment named 4 excluded conclusions
# and never mentioned this 5th real conclusion value at all.

#: Sentinel returned by find_named_check_conclusion() when more than one checkRun named
#: HARNESS_FLOOR_CHECK_NAME exists on the same commit with DIFFERING conclusions — never a
#: real GitHub conclusion string, so `AMBIGUOUS_CHECK_CONCLUSION in RED_CHECK_CONCLUSIONS` is
#: always False by construction (an ambiguous read must never accidentally read as "green").
AMBIGUOUS_CHECK_CONCLUSION = "__AMBIGUOUS_DUPLICATE_CHECK_RUN_NAME__"

STALL_CAUSES = (
    "gate-verdict-missing",
    "required-check-red",
    "conflict",
    "not-armed",
    "queued-and-advancing",
)
CANNOT_VERIFY = "CANNOT-VERIFY"


# ---------------------------------------------------------------------------
# Pure functions — no I/O. What scripts/tests/test_queue_stall_classifier.py exercises directly.
# ---------------------------------------------------------------------------


def _parse_iso(ts: str | None) -> _dt.datetime | None:
    """Returns an aware (UTC) datetime, or None. Duplicated from queue_shepherd.py::_parse_iso
    (same STANDALONE-by-design convention — see module docstring trap (e))."""
    if not ts:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed


def is_stall_candidate(pr: dict[str, Any], now: _dt.datetime, min_age_minutes: int) -> bool:
    """Pure gate: is this open, non-draft PR (with an already-resolved `created_at` — the
    caller filters an unparseable one out BEFORE this point, surfaced as its own CANNOT-VERIFY
    row rather than silently guessed here) old enough to be a stall candidate?

    Age is measured from `created_at` (PR open time), deliberately never `updatedAt` — see
    module docstring AGE section. Drafts are excluded upstream (never mergeable by design, so
    never "stalled" by this classifier's definition) — this function does not re-check
    `is_draft` itself, single responsibility."""
    age = now - pr["created_at"]
    return age >= _dt.timedelta(minutes=min_age_minutes)


def find_named_check_conclusion(check_runs: list[dict[str, Any]], name: str) -> str | None:
    """Pure: returns the `conclusion` of the checkRun literally named `name` among an
    already-flattened list of {"name":..., "conclusion":...} dicts, or None if absent.
    Case-sensitive exact match — "Harness floor recompute" is a GitHub Actions job NAME, not a
    pattern to fuzz-match (guard-over-match discipline, superscar #3: a loose match here could
    silently pick up an unrelated job and misclassify the whole PR).

    MORE THAN ONE checkRun can legitimately carry this exact name on the SAME commit: the
    Agent PR Contract's own rule 3 documents that a `workflow_dispatch` rerun of the same job
    lands in a DIFFERENT check suite than the original `pull_request` run, on the same sha —
    so `fetch_check_runs_flat`'s flattened list can contain two (or more) entries named
    "Harness floor recompute" with potentially different conclusions (found by an independent
    second-opinion review, kimi-code/k3, 2026-08-31). Picking the textually-first one by list
    order — which is what this function did before that review — is order-dependent on
    GraphQL's unspecified checkSuites ordering, and can go wrong in BOTH directions: a stale
    FAILURE found first while the latest rerun is green fabricates a gate-verdict-missing; a
    stale SUCCESS found first while the latest run is red demotes a real gate-verdict-missing
    into required-check-red — exactly the swallow this module's docstring says must never
    happen. When every match agrees there is nothing to disambiguate and that shared
    conclusion is returned as before (the common case, unaffected). When matches DISAGREE,
    this returns AMBIGUOUS_CHECK_CONCLUSION rather than guessing off list order — the caller
    (_classify_one) must read that as CANNOT-VERIFY, the same discipline already applied to a
    truncated fetch."""
    conclusions = {run.get("conclusion") for run in check_runs if run.get("name") == name}
    if not conclusions:
        return None
    if len(conclusions) > 1:
        return AMBIGUOUS_CHECK_CONCLUSION
    return conclusions.pop()


def classify_stall(
    *,
    merge_state_status: str | None,
    status_rollup_state: str | None,
    auto_merge_enabled: bool,
    in_queue: bool,
    harness_floor_red: bool,
    fable_gate_posted: bool | None,
) -> str:
    """Pure decision tree, the SINGLE source of truth for the 5-bucket closed STALL_CAUSES set —
    every caller reaches its verdict by calling this function exactly once; no branch anywhere
    else in this module re-derives "conflict" or "gate-verdict-missing" independently (avoids
    the exact drift risk two parallel copies of a decision tree would create).

    PRECEDENCE (deliberate — a PR can match more than one signal at once):
      1. conflict             — a structural git conflict blocks everything else regardless of
                                 CI outcome; diagnosing checks first would be wasted motion.
      2. gate-verdict-missing — the most specific, most actionable signal, checked BEFORE the
                                 generic red-check bucket so it is never swallowed by it (the
                                 whole reason this classifier exists — team-lead mandate:
                                 "classify it correctly or the table lies about the single most
                                 common cause tonight").
      3. required-check-red   — any other red required check, INCLUDING a genuinely-posted
                                 REWORK/BLOCK fable-gate verdict (harness_floor_red True but
                                 fable_gate_posted also True) — a real judgment already exists;
                                 the PR needs code changes, not a rerun or a new verdict.
      4. not-armed             — W111 guard: BOTH auto_merge_enabled and in_queue must be
                                 false; `autoMergeRequest: null` ALONE never implies not-armed.
      5. queued-and-advancing — default: armed/queued, no known blocker; may simply be slow.

    Never returns CANNOT-VERIFY — an I/O failure is decided by the caller BEFORE this function
    is ever invoked for a given PR."""
    if merge_state_status == "DIRTY":
        return "conflict"
    if harness_floor_red and fable_gate_posted is False:
        return "gate-verdict-missing"
    if status_rollup_state in RED_ROLLUP_STATES:
        return "required-check-red"
    if not auto_merge_enabled and not in_queue:
        return "not-armed"
    return "queued-and-advancing"


def _describe_cause(
    cause: str,
    pr: dict[str, Any],
    fable_gate_state: str | None,
) -> str:
    """Human-readable one-liner for the markdown table. Not itself part of the decision tree —
    classify_stall() already decided; this only explains the decision."""
    if cause == "conflict":
        return "mergeStateStatus=DIRTY (re-verified fresh, not a stale read)"
    if cause == "gate-verdict-missing":
        return (
            f"'{HARNESS_FLOOR_CHECK_NAME}' is red and no {FABLE_GATE_STATUS_CONTEXT} verdict "
            f"has ever been posted on {pr['head_sha'][:8]} — mirrors harness_gate_read.py's own "
            "PENDING case; process, not a code defect"
        )
    if cause == "required-check-red":
        if fable_gate_state == "success":
            # CONFIRMED finding (gpt-5.6-sol, 2026-08-31): a stale red "Harness floor recompute"
            # run whose gate verdict has ALREADY been posted as success (harness_gate_read.py's
            # own documented #4543 shape — the verdict landed after that run finished) is a
            # RERUN situation, not a code defect — saying "it is not success" here would be
            # false, since the posted state literally IS success.
            return (
                f"statusCheckRollup={pr['status_rollup_state']}; {FABLE_GATE_STATUS_CONTEXT}="
                "'success' was ALREADY posted — the check run itself is stale (landed before "
                "the verdict did, per harness_gate_read.py's documented #4543 shape); needs "
                "`gh run rerun <original pull_request run>`, not a code fix "
                "(docs/runbooks/merge-queue-discipline.md §6septies)"
            )
        if fable_gate_state is not None:
            return (
                f"statusCheckRollup={pr['status_rollup_state']}; "
                f"{FABLE_GATE_STATUS_CONTEXT}={fable_gate_state!r} "
                "(a real verdict was posted and it is not success)"
            )
        return f"statusCheckRollup={pr['status_rollup_state']}"
    if cause == "not-armed":
        return "autoMergeRequest=null and mergeQueueEntry=null (W111: both, not either)"
    return (
        f"mergeQueueEntry={'present' if pr['in_queue'] else 'absent'} "
        f"autoMergeRequest={'enabled' if pr['auto_merge_enabled'] else 'disabled'} "
        f"statusCheckRollup={pr['status_rollup_state']}"
    )


# ---------------------------------------------------------------------------
# I/O — subprocess + gh wrappers. Read-only by construction (see module docstring + this
# module's own AST-scan tests): every call below is a `gh api graphql` QUERY (never a
# `mutation`) or a plain `gh api <path>` GET, never a write verb.
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command; never raises. Returns (rc, stdout, stderr). Duplicated boundary shape
    from queue_shepherd.py::_run (STANDALONE-by-design, see module docstring trap (e))."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


def _gh_graphql(query: str, variables: dict[str, Any], timeout: int = 45) -> dict[str, Any]:
    """Raises RuntimeError on any failure — never returns a fabricated empty structure. Every
    literal argv this builds is `["gh", "api", "graphql", "-f", "query=<a query{...} string>",
    ...]` — `-f`/`-F` here pass a READ-ONLY GraphQL *query* operation (never `mutation`), the
    same shape queue_shepherd.py's own `_gh_graphql` already uses for read-only work."""
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


OPEN_PRS_QUERY = """
query($owner:String!, $repo:String!, $cursor:String) {
  repository(owner:$owner, name:$repo) {
    pullRequests(states:OPEN, first:100, after:$cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        isDraft
        headRefOid
        createdAt
        mergeStateStatus
        autoMergeRequest { enabledAt }
        mergeQueueEntry { state }
        commits(last:1) { nodes { commit { statusCheckRollup { state } } } }
      }
    }
  }
}
"""


def _normalize_open_pr(node: dict[str, Any]) -> dict[str, Any]:
    # CONFIRMED finding (gpt-5.6-sol, 2026-08-31): an OPEN PR always has >=1 commit in real
    # git/GitHub — `commits(last:1)` returning zero nodes for one is an anomalous GraphQL
    # response shape (a transient API glitch, never a legitimate "commit-less PR"), not a
    # normal absence. Silently defaulting status_rollup_state to None here let such a PR fall
    # through to not-armed/queued-and-advancing instead of being flagged — `commits_missing`
    # lets _classify_one surface it as CANNOT-VERIFY instead.
    commits = (node.get("commits") or {}).get("nodes") or []
    commits_missing = not commits
    rollup_state = None
    if commits:
        rollup_state = ((commits[0].get("commit") or {}).get("statusCheckRollup") or {}).get("state")
    return {
        "number": node["number"],
        "title": node.get("title") or "",
        "is_draft": bool(node.get("isDraft")),
        "head_sha": node.get("headRefOid") or "",
        "created_at": _parse_iso(node.get("createdAt")),
        "merge_state_status": node.get("mergeStateStatus"),
        "auto_merge_enabled": bool(node.get("autoMergeRequest")),
        "in_queue": bool(node.get("mergeQueueEntry")),
        "commits_missing": commits_missing,
        "status_rollup_state": rollup_state,
    }


def fetch_open_prs(repo: str) -> list[dict[str, Any]]:
    """Every open PR, normalized, lightweight (no checkSuites — see module docstring trap (d)
    for why that lookup is deferred to a per-candidate fetch instead). Raises on fetch failure
    — CANNOT-VERIFY must never be read as an empty PR list."""
    owner, name = repo.split("/", 1)
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    for _page in range(MAX_PAGES):
        variables: dict[str, Any] = {"owner": owner, "repo": name}
        if cursor:
            variables["cursor"] = cursor
        data = _gh_graphql(OPEN_PRS_QUERY, variables)
        try:
            page = data["data"]["repository"]["pullRequests"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"unexpected graphql shape: {exc}: {json.dumps(data)[:300]}") from exc
        for node in page["nodes"]:
            out.append(_normalize_open_pr(node))
        if not page["pageInfo"]["hasNextPage"]:
            return out
        cursor = page["pageInfo"]["endCursor"]
    # CONFIRMED finding (gpt-5.6-sol, 2026-08-31): unlike queue_shepherd.py's OWN MAX_PAGES
    # bounds (fetch_queued_runs/fetch_live_queue_branches), which warn-and-return-partial
    # because a later cancel-time recheck independently re-verifies liveness before acting, an
    # incomplete PR list HERE has no such safety net — it would silently under-report
    # `examined_total` and let main() exit 0 on a board that looks clean only because part of
    # it was never fetched. Raising turns this into the SAME loud, non-zero top-level failure
    # this module already gives an outright `gh` error (module docstring trap (g)).
    raise RuntimeError(
        f"fetch_open_prs: hit MAX_PAGES={MAX_PAGES} without exhausting pagination — "
        f"{len(out)} PR(s) fetched, more remain; refusing to report a partial board as complete"
    )


FRESH_MERGE_STATE_QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) { mergeStateStatus }
  }
}
"""


def fetch_fresh_merge_state(repo: str, number: int) -> str | None:
    """A SECOND, single-PR, immediate fetch of ONLY mergeStateStatus — module docstring trap
    (c). Raises on failure; the caller treats that as CANNOT-VERIFY for this PR, never as
    'still DIRTY' nor 'not DIRTY'."""
    owner, name = repo.split("/", 1)
    data = _gh_graphql(FRESH_MERGE_STATE_QUERY, {"owner": owner, "repo": name, "number": number})
    try:
        pr = data["data"]["repository"]["pullRequest"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"unexpected graphql shape: {exc}: {json.dumps(data)[:300]}") from exc
    if pr is None:
        raise RuntimeError(f"PR #{number} not found on fresh re-check (closed/merged mid-run?)")
    return pr.get("mergeStateStatus")


CHECK_RUNS_QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      commits(last:1) {
        nodes {
          commit {
            checkSuites(first:100) {
              totalCount
              nodes { checkRuns(first:20) { totalCount nodes { name conclusion } } }
            }
          }
        }
      }
    }
  }
}
"""


def fetch_check_runs_flat(repo: str, number: int) -> tuple[list[dict[str, Any]], bool]:
    """Returns (flattened [{"name":..,"conclusion":..}], truncated). `truncated` is True when
    EITHER the checkSuites page or ANY individual suite's checkRuns page did not fit the
    fetched window (module docstring trap (d)) — CHECK_SUITES_PAGE_SIZE/CHECK_RUNS_PAGE_SIZE
    are sized against a LIVE measurement, not a guess, but a future PR could still exceed them;
    the caller must never read a truncated 'not found' as a reliable absence. Raises on fetch
    failure."""
    owner, name = repo.split("/", 1)
    data = _gh_graphql(CHECK_RUNS_QUERY, {"owner": owner, "repo": name, "number": number})
    try:
        pr = data["data"]["repository"]["pullRequest"]
        if pr is None:
            raise RuntimeError(f"PR #{number} not found (closed/merged mid-run?)")
        commit_nodes = pr["commits"]["nodes"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"unexpected graphql shape: {exc}: {json.dumps(data)[:300]}") from exc
    if not commit_nodes:
        # CONFIRMED finding (gpt-5.6-sol, 2026-08-31): an open PR always has >=1 commit for real
        # — an empty commits.nodes here is an anomalous GraphQL response, not "no check runs".
        # Raising (-> CANNOT-VERIFY at the caller) beats silently returning ([], False), which
        # would let a possibly-red gate hide behind a data anomaly instead of being flagged.
        raise RuntimeError(f"PR #{number}: commits.nodes empty on an open PR (anomalous response)")
    suites = (commit_nodes[0].get("commit") or {}).get("checkSuites") or {}
    suite_nodes = suites.get("nodes") or []
    truncated = (suites.get("totalCount") or 0) > len(suite_nodes)
    flat: list[dict[str, Any]] = []
    for suite in suite_nodes:
        runs = suite.get("checkRuns") or {}
        run_nodes = runs.get("nodes") or []
        if (runs.get("totalCount") or 0) > len(run_nodes):
            truncated = True
        for run in run_nodes:
            flat.append({"name": run.get("name"), "conclusion": run.get("conclusion")})
    return flat, truncated


def read_fable_gate_state(repo: str, sha: str) -> tuple[str | None, str | None]:
    """Mirrors scripts/ci/harness_gate_read.py::read_fable_gate_state (duplicated, not
    imported — module docstring trap (e)), with ONE deliberate divergence found by an
    independent cross-family review (gpt-5.6-sol, 2026-08-31): the combined-status endpoint
    defaults to 30 results per page, and harness_gate_read.py itself does not paginate it — a
    context sitting past page 1 would read as 'never posted' there. This copy requests
    `per_page=100` AND checks the response's own `total_count` against what was actually
    fetched; a truncated response (more statuses exist than were returned) raises RuntimeError
    rather than risking a false 'never posted' -> misclassified gate-verdict-missing (this
    repo's own live commit today carries exactly 1 status, so the practical risk is low, but
    the check costs nothing and the mandate is explicit: never guess).

    Returns (state, description) for the harness/fable-gate context on `sha`, or (None, None)
    if never posted (and the response was NOT truncated). Raises RuntimeError on a genuine
    fetch failure — the caller must treat that as CANNOT-VERIFY, never as 'no verdict'
    (cicatrix W88/W106: 'could not verify' is never 'verified absent')."""
    rc, out, err = _run(
        ["gh", "api", f"repos/{repo}/commits/{sha}/status?per_page=100"], timeout=30
    )
    if rc != 0:
        raise RuntimeError(f"gh api commits/{sha}/status failed rc={rc}: {err.strip()[:300]}")
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"commits/{sha}/status returned unparseable JSON: {exc}") from exc
    statuses = data.get("statuses") if isinstance(data, dict) else None
    if not isinstance(statuses, list):
        raise RuntimeError(f"commits/{sha}/status response missing a 'statuses' array: {str(data)[:300]}")
    for entry in statuses:
        if isinstance(entry, dict) and entry.get("context") == FABLE_GATE_STATUS_CONTEXT:
            return entry.get("state"), entry.get("description")
    total_count = data.get("total_count") if isinstance(data, dict) else None
    if isinstance(total_count, int) and total_count > len(statuses):
        raise RuntimeError(
            f"commits/{sha}/status truncated (total_count={total_count}, fetched={len(statuses)}) "
            f"and {FABLE_GATE_STATUS_CONTEXT!r} was not among the fetched page — cannot reliably "
            "conclude it was never posted"
        )
    return None, None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _classify_one(repo: str, pr: dict[str, Any], now: _dt.datetime) -> dict[str, Any]:
    """I/O-driven per-PR classification. Every early return here is a CANNOT-VERIFY for an I/O
    failure ONLY — the actual cause verdict is always produced by exactly one call to
    classify_stall() at the end, never re-derived inline (see that function's own docstring)."""
    number = pr["number"]
    age_minutes = int((now - pr["created_at"]).total_seconds() // 60)
    base = {"number": number, "title": pr.get("title", ""), "age_minutes": age_minutes}

    if pr.get("commits_missing"):
        # CONFIRMED finding (gpt-5.6-sol, 2026-08-31) — see _normalize_open_pr's own comment.
        return {
            **base, "cause": CANNOT_VERIFY,
            "detail": "commits.nodes was empty on an open PR (anomalous GraphQL response) — "
            "statusCheckRollup cannot be trusted, refusing to guess",
        }

    merge_state_status = pr["merge_state_status"]
    if merge_state_status == "DIRTY":
        try:
            merge_state_status = fetch_fresh_merge_state(repo, number)
        except RuntimeError as exc:
            return {**base, "cause": CANNOT_VERIFY, "detail": f"fresh mergeStateStatus re-check failed: {exc}"}

    harness_floor_red = False
    fable_gate_state: str | None = None
    fable_gate_posted: bool | None = None
    if pr["status_rollup_state"] in RED_ROLLUP_STATES:
        try:
            check_runs, truncated = fetch_check_runs_flat(repo, number)
        except RuntimeError as exc:
            return {**base, "cause": CANNOT_VERIFY, "detail": f"checkSuites fetch failed: {exc}"}
        conclusion = find_named_check_conclusion(check_runs, HARNESS_FLOOR_CHECK_NAME)
        if conclusion is None and truncated:
            return {
                **base,
                "cause": CANNOT_VERIFY,
                "detail": (
                    f"statusCheckRollup={pr['status_rollup_state']} but the "
                    f"'{HARNESS_FLOOR_CHECK_NAME}' check run could not be reliably located — "
                    "checkSuites/checkRuns pagination truncated before reaching it (see module "
                    "docstring trap (d)); silently reading 'not found' as 'not the gate' here "
                    "would risk misclassifying a possible gate-verdict-missing as "
                    "required-check-red"
                ),
            }
        if conclusion == AMBIGUOUS_CHECK_CONCLUSION:
            # CONFIRMED finding (kimi-code/k3, 2026-08-31): two checkRuns named
            # HARNESS_FLOOR_CHECK_NAME on the same commit (a workflow_dispatch rerun landing
            # in a different check suite, Agent PR Contract rule 3) disagreed on conclusion —
            # see find_named_check_conclusion's own docstring for why guessing off list order
            # is never safe here.
            return {
                **base,
                "cause": CANNOT_VERIFY,
                "detail": (
                    f"statusCheckRollup={pr['status_rollup_state']} but more than one "
                    f"'{HARNESS_FLOOR_CHECK_NAME}' check run exists on {pr['head_sha'][:8]} "
                    "with DIFFERING conclusions (a workflow_dispatch rerun lands in a separate "
                    "check suite on the same commit, per the Agent PR Contract's own rule 3) — "
                    "refusing to guess which one is current"
                ),
            }
        harness_floor_red = conclusion in RED_CHECK_CONCLUSIONS
        if harness_floor_red:
            try:
                fable_gate_state, _description = read_fable_gate_state(repo, pr["head_sha"])
            except RuntimeError as exc:
                return {
                    **base, "cause": CANNOT_VERIFY,
                    "detail": f"{FABLE_GATE_STATUS_CONTEXT} status read failed: {exc}",
                }
            fable_gate_posted = fable_gate_state is not None

    cause = classify_stall(
        merge_state_status=merge_state_status,
        status_rollup_state=pr["status_rollup_state"],
        auto_merge_enabled=pr["auto_merge_enabled"],
        in_queue=pr["in_queue"],
        harness_floor_red=harness_floor_red,
        fable_gate_posted=fable_gate_posted,
    )
    return {**base, "cause": cause, "detail": _describe_cause(cause, pr, fable_gate_state)}


def build_report(repo: str, now: _dt.datetime, min_age_minutes: int) -> dict[str, Any]:
    """Returns a report dict — never raises (a top-level fetch failure is recorded in
    `fetch_error`, never an uncaught exception). `examined_total` is the RAW open-PR count
    (before draft/age filtering) — see module docstring trap (g) for why main() gates its
    loud-failure check on THIS field, not on len(rows)."""
    report: dict[str, Any] = {
        "repo": repo,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "min_age_minutes": min_age_minutes,
        "examined_total": 0,
        "excluded_drafts": 0,
        "rows": [],
        "fetch_error": None,
    }
    try:
        prs = fetch_open_prs(repo)
    except RuntimeError as exc:
        report["fetch_error"] = str(exc)
        return report

    report["examined_total"] = len(prs)
    for pr in prs:
        if pr["is_draft"]:
            report["excluded_drafts"] += 1
            continue
        if pr["created_at"] is None:
            report["rows"].append(
                {
                    "number": pr["number"],
                    "title": pr.get("title", ""),
                    "age_minutes": None,
                    "cause": CANNOT_VERIFY,
                    "detail": "createdAt missing/unparseable from GraphQL response",
                }
            )
            continue
        if not is_stall_candidate(pr, now, min_age_minutes):
            continue
        report["rows"].append(_classify_one(repo, pr, now))
    return report


def render_table(report: dict[str, Any]) -> str:
    """Pure: markdown, ready to paste into a PR body."""
    lines = [
        f"# Stall classification — {report['repo']} "
        f"(min_age={report['min_age_minutes']}m, generated {report['generated_at']})",
        "",
    ]
    if report.get("fetch_error"):
        lines.append(f"CANNOT-VERIFY: top-level open-PR fetch failed: {report['fetch_error']}")
        return "\n".join(lines)

    lines.append(
        f"examined {report['examined_total']} open PR(s) total "
        f"({report['excluded_drafts']} draft, excluded)."
    )
    rows = report["rows"]
    if not rows:
        lines.append(
            f"0 PR(s) older than {report['min_age_minutes']}m and non-draft — nothing to classify."
        )
        return "\n".join(lines)

    lines.append("")
    lines.append("| PR | Age (m) | Cause | Detail |")
    lines.append("|---|---|---|---|")
    for row in sorted(rows, key=lambda r: r["number"]):
        detail = str(row["detail"]).replace("|", "\\|")
        age = row["age_minutes"] if row["age_minutes"] is not None else "?"
        lines.append(f"| #{row['number']} | {age} | {row['cause']} | {detail} |")

    causes_seen = collections.Counter(r["cause"] for r in rows)
    lines.append("")
    lines.append("Summary: " + ", ".join(f"{k}={v}" for k, v in sorted(causes_seen.items())))
    return "\n".join(lines)


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else "")
    parser.add_argument("--repo", default=REPO_DEFAULT, help="owner/repo, default %(default)s")
    parser.add_argument(
        "--min-age-minutes", type=int, default=DEFAULT_MIN_AGE_MINUTES,
        help="only classify open, non-draft PRs at least this old (default %(default)s)",
    )
    parser.add_argument("--json", action="store_true", help="emit the raw report as JSON instead of a markdown table")
    args = parser.parse_args(argv)

    now = _now()
    report = build_report(args.repo, now, args.min_age_minutes)

    if args.json:
        print(json.dumps(report, default=str, indent=2, sort_keys=True))
    else:
        print(render_table(report))

    if report.get("fetch_error"):
        return 1
    if report["examined_total"] == 0:
        print(
            f"\nCANNOT-VERIFY: examined 0 open PRs total in {args.repo} — implausible for an "
            "active repo; treating as a failed/incomplete fetch, never as a clean board "
            "(superscar #2, exists != armed).",
            file=sys.stderr,
        )
        return 1
    if any(row["cause"] == CANNOT_VERIFY for row in report["rows"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
