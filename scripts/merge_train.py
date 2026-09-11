"""Merge-train coordinator — serialized PR merging for a busy main.

Spec: research/operations/specs/MERGE-TRAIN-coordinator-spec.md (v2,
panel-reviewed 2026-06-12). One-shot tick, invoked by LaunchAgent
com.nuzantara.merge-train every ~180s via scripts/merge_train_run.sh.

Phase 0 (current): DRY-RUN — every mutating action is logged with the
decision it WOULD take, nothing is executed. Flip via the runtime config
file (~/.agent/merge-train.config: {"enabled": true, "dry_run": false}).

Design directive (Antonello 2026-06-12): no human-first alerts — the
state file carries PROGRESS semantics (not just mtime) so the deadman
can detect a zombie train and self-repair (kickstart) before any human
notification.

Usage:
    python3 scripts/merge_train.py            # one tick
    python3 scripts/merge_train.py --status   # print last state, no tick
"""

from __future__ import annotations

import json
import os
import random
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "Balizero1987/Teman2"
AGENT_DIR = Path(os.path.expanduser("~/.agent"))
STATE_PATH = AGENT_DIR / "decisions" / "state" / "merge_train.json"
CONFIG_PATH = AGENT_DIR / "merge-train.config"
LOCK_DIR = AGENT_DIR / "merge-train.lock"
LOCK_STALE_SECONDS = 600
TICK_HARD_TIMEOUT_SECONDS = 150  # < StartInterval (180) so ticks never pile up
OPTOUT_LABEL = "no-train"
REVERT_LABEL = "auto-revert"
SKIP_TTL_API_ERROR_SECONDS = 3600
MAIN_SUITE_WORKFLOW = "tests.yml"
DEPLOY_WORKFLOW = "fly-deploy.yml"

# Human-only blockers we cannot resolve (GraphQL mergeStateStatus values).
_HUMAN_BLOCK_STATES = frozenset({"DIRTY"})


def _now() -> float:
    return time.time()


def _iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or _now(), tz=timezone.utc).isoformat()


def gh(args: list[str], *, timeout: int = 45) -> str:
    """Run gh CLI, raise on failure (caller classifies)."""
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh {args[0]} failed rc={proc.returncode}: {proc.stderr.strip()[:300]}")
    return proc.stdout


def gh_json(args: list[str], *, timeout: int = 45) -> Any:
    return json.loads(gh(args, timeout=timeout) or "null")


# ----------------------------------------------------------------------
# Config / state / lock
# ----------------------------------------------------------------------


def load_config() -> dict[str, Any]:
    """Runtime config — read every tick so toggles are live (spec §10.7)."""
    default = {"enabled": True, "dry_run": True}
    try:
        loaded = json.loads(CONFIG_PATH.read_text())
        return {**default, **loaded}
    except (OSError, ValueError):
        return default


def load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return {}


def write_state(state: dict[str, Any]) -> None:
    """Atomic write: temp + rename (spec §10.3 / Codex 20)."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(tmp, STATE_PATH)


def acquire_lock() -> bool:
    """mkdir-based single-instance lock (macOS has no flock(1), spec §10.7).

    A stale lock (older than LOCK_STALE_SECONDS) is stolen — a hung tick
    must not stop the train forever.
    """
    try:
        LOCK_DIR.mkdir(parents=True, exist_ok=False)
        (LOCK_DIR / "pid").write_text(str(os.getpid()))
        return True
    except FileExistsError:
        try:
            age = _now() - LOCK_DIR.stat().st_mtime
        except OSError:
            return False
        if age > LOCK_STALE_SECONDS:
            release_lock()
            try:
                LOCK_DIR.mkdir(parents=True, exist_ok=False)
                (LOCK_DIR / "pid").write_text(str(os.getpid()))
                return True
            except FileExistsError:
                return False
        return False


def release_lock() -> None:
    try:
        (LOCK_DIR / "pid").unlink(missing_ok=True)
        LOCK_DIR.rmdir()
    except OSError:
        pass


# ----------------------------------------------------------------------
# Pure decision logic (unit-tested)
# ----------------------------------------------------------------------


@dataclass
class Decision:
    action: str  # pause|wait|update_branch|reroll_failed|skiplist|none|comment_and_skip
    pr: int | None = None
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def order_queue(
    prs: list[dict[str, Any]], *, in_queue_numbers: set[int]
) -> list[dict[str, Any]]:
    """FIFO by PR number, with the auto-revert priority lane at the head
    (spec §10.1). Opt-out label excluded entirely.

    Eligibility answers "is this PR under active management?" —
    `autoMergeRequest` non-null OR the PR's number is in `in_queue_numbers`
    (GitHub's own merge-queue entries, the positive probe). `in_queue_numbers`
    is required, not optional with an empty-set default: `autoMergeRequest`
    ALONE used to gate this (pre-2026-08-30) and that was the bug — the field
    reads null in (at least) three different states: a PR the queue has
    ACCEPTED (the request is CONSUMED, not disarmed), a PR the queue EJECTED,
    and a PR genuinely never armed. The old code treated all three as "not
    eligible", silently dropping exactly the PRs deepest in the lifecycle
    this coordinator exists to babysit — measured live on PR #5275
    (`autoMergeRequest: null` simultaneously with `mergeQueueEntry
    {state: QUEUED, position: 3}`) and the false re-arm alarms on #4756/
    #5012. A required parameter with no default means a caller that forgets
    to pass a real snapshot gets a loud TypeError, not a silent reversion to
    the old, wrong, autoMergeRequest-only reading. `mergeQueueEntry` and
    `isInMergeQueue` are GraphQL-only — not in `gh pr list`/`gh pr view
    --json`'s field list (verified live against the gh CLI) — so
    `in_queue_numbers` comes from a raw GraphQL `mergeQueue(branch:"main")
    {entries}` snapshot (`fetch_queue_membership()` below), the same shape
    scripts/queue_doctor.py and scripts/ci/queue_rearm.sh already use for
    the identical cross-check."""
    eligible = [
        p
        for p in prs
        if (p.get("autoMergeRequest") or p["number"] in in_queue_numbers)
        and OPTOUT_LABEL not in {lbl["name"] for lbl in p.get("labels", [])}
    ]
    reverts = sorted(
        (p for p in eligible if REVERT_LABEL in {lbl["name"] for lbl in p.get("labels", [])}),
        key=lambda p: p["number"],
    )
    normal = sorted(
        (p for p in eligible if REVERT_LABEL not in {lbl["name"] for lbl in p.get("labels", [])}),
        key=lambda p: p["number"],
    )
    return reverts + normal


def skiplist_active(skiplist: dict[str, Any], pr: int, head_sha: str) -> bool:
    """Skiplist keys are pr:sha:reason — cleared by a NEW push (different
    sha). api_error entries additionally expire on TTL (spec §10.3)."""
    for key, entry in skiplist.items():
        try:
            k_pr, k_sha, k_reason = key.split(":", 2)
        except ValueError:
            continue
        if int(k_pr) != pr or k_sha != head_sha:
            continue
        if k_reason == "api_error":
            if _now() - entry.get("ts", 0) < SKIP_TTL_API_ERROR_SECONDS:
                return True
            continue
        return True
    return False


def decide_head(
    head: dict[str, Any],
    *,
    main_green: bool,
    deploy_in_flight: bool,
    is_revert: bool,
    blocking_required: dict[str, str],
    rerolled_already: bool,
    missing_required: list[str] | None = None,
    update_for_missing_already: bool = False,
) -> Decision:
    """The core decision for the queue head. Pure function.

    head: {number, mergeStateStatus, headRefOid}
    """
    n = head["number"]
    state = (head.get("mergeStateStatus") or "UNKNOWN").upper()

    # Red-main pause: normal PRs freeze; only the revert lane moves (§10.1).
    if not main_green and not is_revert:
        return Decision("pause", reason="main_red")
    if deploy_in_flight:
        return Decision("pause", reason="fly_deploy_in_flight")

    if state in _HUMAN_BLOCK_STATES:
        return Decision(
            "comment_and_skip",
            pr=n,
            reason="conflicts",
            details={"comment": (
                "merge-train: this PR conflicts with main — resolve and push "
                "to re-enter the queue."
            )},
        )

    if blocking_required:
        if not rerolled_already:
            return Decision("reroll_failed", pr=n, reason="red_checks_first_seen",
                            details={"blocking": blocking_required})
        states = ", ".join(f"{name}: {state}" for name, state in sorted(blocking_required.items()))
        return Decision(
            "comment_and_skip",
            pr=n,
            reason="red_checks",
            details={"comment": (
                "merge-train: required checks are still blocking this head after a "
                f"retry — {states} — fix (or, for a stuck run, re-trigger it) and "
                "push to re-enter the queue."
            ), "blocking": blocking_required},
        )

    if state == "BEHIND":
        return Decision("update_branch", pr=n, reason="behind")

    # Head-of-line trap (seen live on #994, 2026-06-12): branch protection
    # gained new required workflows AFTER this PR's last push, so they never
    # ran on this head — BLOCKED forever with zero failures. One
    # update-branch re-triggers everything on a fresh merge commit. Only one
    # attempt per PR: if contexts are still missing after that, the workflow
    # name/path-filter itself is broken (W69 trap #1) — human problem.
    if missing_required and state == "BLOCKED":
        if not update_for_missing_already:
            return Decision("update_branch", pr=n, reason="missing_required_contexts",
                            details={"missing": missing_required})
        return Decision(
            "comment_and_skip",
            pr=n,
            reason="missing_required_persistent",
            details={"comment": (
                "merge-train: required contexts never started on this head even "
                "after an update-branch — check branch-protection contexts vs "
                "workflow names/path filters, then push to re-enter the queue."
            ), "missing": missing_required},
        )

    if state == "UNKNOWN":
        return Decision("wait", pr=n, reason="merge_state_recalculating")

    # BLOCKED with nothing in blocking_required = every required context is
    # OK or still progressing (or human-review policy, which auto-merge will
    # hold anyway) → wait. CLEAN/HAS_HOOKS/UNSTABLE → GitHub's own
    # auto-merge completes it.
    return Decision("wait" if state == "BLOCKED" else "none", pr=n, reason=state.lower())


# ----------------------------------------------------------------------
# GitHub interactions (side-effect layer)
# ----------------------------------------------------------------------


def fetch_queue() -> list[dict[str, Any]]:
    return gh_json([
        "pr", "list", "--repo", REPO, "--state", "open", "--limit", "100",
        "--json", "number,labels,autoMergeRequest",
    ])


_MERGE_QUEUE_QUERY = (
    "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){"
    'mergeQueue(branch:"main"){entries(first:100){nodes{pullRequest{number}}}}}}'
)


def fetch_queue_membership() -> set[int]:
    """PR numbers GitHub's native merge queue currently holds — the positive
    probe `order_queue()` needs (2026-08-30 fix). `mergeQueueEntry` and
    `isInMergeQueue` are GraphQL-only, absent from `gh pr list`/`gh pr view
    --json`'s field list, so this is a raw `gh api graphql` call on the
    branch-level snapshot — the same shape scripts/queue_doctor.py and
    scripts/ci/queue_rearm.sh already use for the identical cross-check.
    Raises like every other fetch_* here (RuntimeError/TimeoutExpired) —
    the caller must fail closed, never treat a failed probe as an empty
    queue (W104: never fabricate a zero)."""
    owner, name = REPO.split("/", 1)
    data = gh_json([
        "api", "graphql",
        "-f", f"query={_MERGE_QUEUE_QUERY}",
        "-f", f"owner={owner}",
        "-f", f"name={name}",
    ])
    repo = ((data or {}).get("data") or {}).get("repository") or {}
    entries = ((repo.get("mergeQueue") or {}).get("entries") or {}).get("nodes") or []
    return {
        e["pullRequest"]["number"]
        for e in entries
        if e and e.get("pullRequest") and isinstance(e["pullRequest"].get("number"), int)
    }


def fetch_head_detail(number: int) -> dict[str, Any]:
    return gh_json([
        "pr", "view", str(number), "--repo", REPO,
        "--json", "number,mergeStateStatus,headRefOid,statusCheckRollup",
    ])


def required_contexts() -> set[str]:
    data = gh_json([
        "api", f"repos/{REPO}/branches/main/protection/required_status_checks",
    ])
    return set(data.get("contexts", []))


# Task #40 (2026-07-26): PR #3146 sat armed 12h because its required context
# "P6 parallelize-hypothesis falsifiable gates" went CANCELLED — a terminal
# state the old `failed_required_checks` (below, now replaced) never named,
# because it enumerated exactly one bad state (FAILURE). That was the THIRD
# state in one night to block a PR invisibly: FAILURE (red, the one everyone
# checks for) -> MISSING (zero-check trap, a calm list of green third-party
# checks) -> CANCELLED (greyed, reads like "hasn't finished", never retried).
# Each was invisible to the detector built for the one before it. The cure
# is to stop enumerating bad states — the list is open-ended and its next
# member costs another stuck PR to discover — and instead enumerate the
# required contexts and demand SUCCESS/NEUTRAL/SKIPPED, treating anything
# else (named or not) as blocking. Fail-closed on the unknown state, exactly
# as every other guard in this repo does.
_OK_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
_PROGRESSING_STATES = frozenset({"QUEUED", "IN_PROGRESS", "PENDING"})


def _rollup_state(entry: dict[str, Any]) -> str:
    """The one authoritative state string for a statusCheckRollup entry.

    `statusCheckRollup` mixes two GraphQL types in one array and they
    disagree about which field is authoritative — reading `.conclusion`
    first is the trap (a still-running CheckRun carries `conclusion: ""`,
    an empty string, not null, so a naive `.conclusion or .state` fallback
    silently returns "" instead of falling through). Branch on the type
    FIRST, verified live against real rollup entries on this repo's open
    PRs (2026-07-26):
      - StatusContext (e.g. Vercel): `status` is absent/None, `conclusion`
        is absent too — the real value lives in `.state`.
      - CheckRun, still running: `status` is QUEUED/IN_PROGRESS, `conclusion`
        is the empty string — the real value is `.status` itself.
      - CheckRun, completed: `status` is COMPLETED — the real value is
        `.conclusion` (SUCCESS/FAILURE/CANCELLED/NEUTRAL/SKIPPED/TIMED_OUT/
        ACTION_REQUIRED/STALE/...).
    """
    status = entry.get("status")
    if status is None:
        return (entry.get("state") or "").upper()
    if status != "COMPLETED":
        return status.upper()
    return (entry.get("conclusion") or "").upper()


def blocking_required_checks(detail: dict[str, Any], required: set[str]) -> dict[str, str]:
    """Required contexts present on this head whose state is neither OK
    (SUCCESS/NEUTRAL/SKIPPED) nor progressing (QUEUED/IN_PROGRESS/PENDING).
    Returns {name: literal_state}, so a state this function has never seen
    named still shows up — fail-closed, not fail-silent. Contexts with NO
    rollup entry at all are a DIFFERENT case (the zero-check trap) and stay
    the job of `missing_required_contexts` below."""
    out: dict[str, str] = {}
    for c in detail.get("statusCheckRollup") or []:
        name = c.get("name") or c.get("context") or ""
        if name not in required:
            continue
        state = _rollup_state(c)
        if state in _OK_CONCLUSIONS or state in _PROGRESSING_STATES:
            continue
        out[name] = state
    return out


def missing_required_contexts(detail: dict[str, Any], required: set[str]) -> list[str]:
    """Required contexts with NO rollup entry at all on this head (the
    workflow never started — e.g. protection gained new required checks
    after the PR's last push). Distinct from blocking_required_checks."""
    present = {
        c.get("name") or c.get("context") or ""
        for c in detail.get("statusCheckRollup") or []
    }
    return sorted(required - present)


def main_suite_green() -> bool:
    """Latest completed run of the main suite on main. A still-running run
    counts as green (the previous conclusion governs red-main mode only
    when a failure is CONFIRMED)."""
    runs = gh_json([
        "api",
        f"repos/{REPO}/actions/workflows/{MAIN_SUITE_WORKFLOW}/runs"
        "?branch=main&status=completed&per_page=1",
    ])
    items = runs.get("workflow_runs", [])
    if not items:
        return True
    return items[0].get("conclusion") != "failure"


def deploy_in_flight() -> bool:
    runs = gh_json([
        "api",
        f"repos/{REPO}/actions/workflows/{DEPLOY_WORKFLOW}/runs"
        "?branch=main&status=in_progress&per_page=1",
    ])
    return bool(runs.get("workflow_runs"))


def update_branch(number: int, expected_head_sha: str) -> bool:
    """REST update-branch with expected_head_sha (spec §10.3). 202=queued.
    Returns False on 422 (head moved — retry next tick)."""
    try:
        gh([
            "api", "-X", "PUT",
            f"repos/{REPO}/pulls/{number}/update-branch",
            "-f", f"expected_head_sha={expected_head_sha}",
        ])
        return True
    except RuntimeError as exc:
        if "422" in str(exc):
            return False
        raise


# REST Actions API conclusion values are lowercase (GraphQL's are upper).
# Same inversion as blocking_required_checks above, at this layer: name the
# OK set, treat everything else on a completed run as reroll-worthy —
# task #40 exists because the PREVIOUS version of this function named only
# "failure" and silently ignored a CANCELLED run for twelve hours.
_OK_CONCLUSIONS_REST = frozenset({"success", "neutral", "skipped"})

# Task #40 follow-up (team-lead review, 2026-07-26): rerolling blindly risks
# an unbounded rerun loop that #3146 never exposed because it was rare
# (12h stuck, one PR). The SAME night, main alone showed 15 of its last 20
# push-runs CANCELLED — on this repo, cancelled-with-a-newer-successor
# (concurrency `cancel-in-progress: true` superseding an outdated run) is
# the DOMINANT, self-healing case, not the exception. Two independent caps:
MAX_RERUN_ATTEMPTS = 2  # per-run cap: belt-and-braces if guard 1 has a hole.


def reroll_failed_runs(number: int, head_sha: str) -> list[int]:
    """Re-run the LATEST non-OK run per workflow attached to this head
    (Codex 13, widened by task #40, guarded by task #40's follow-up).

    Guard 1 — supersede-vs-stuck: `actions/runs?head_sha=` can return
    MULTIPLE runs of the SAME workflow for the SAME sha (a relabel or
    duplicate trigger creates a new run without retiring the old one).
    Rerunning an OLD run that already has a newer sibling for the same
    workflow is pure waste — the older run is what a concurrency-group
    supersede-cancel is SUPPOSED to produce, not a stuck state — and could
    fight that sibling's own concurrency group. Group by `workflow_id`,
    keep only the run with the highest `run_number` (the latest one for
    this sha); anything not the latest is presumed superseded and is never
    touched, rerun-worthy conclusion or not. If the latest run for a
    workflow is still `status != "completed"`, it is progressing — leave
    it alone (that is `blocking_required_checks`'s PROGRESSING case, not
    ours to act on).

    Guard 2 — attempt cap: even a correct guard 1 does not prove a rerun
    will not itself land in the same non-OK state again (a genuinely
    flaky/misconfigured workflow). Refuse past `MAX_RERUN_ATTEMPTS`
    (`run_attempt` on the run object, incremented by `gh run rerun` itself)
    so a hole in guard 1 terminates into a report instead of spinning —
    `decide_head`'s reroll-once-per-(pr,sha) skiplist already surfaces the
    remaining blocking state to a human on the next tick regardless.

    `--failed` (re-run only the failed jobs) is kept for an actual
    `failure` conclusion — proven, minimizes cost. Anything else
    (cancelled/timed_out/action_required/stale/unrecognized) gets a full
    rerun with no `--failed` flag: a run with zero jobs marked "failed"
    (e.g. everything CANCELLED) has nothing for `--failed` to select, and
    a full rerun is exactly the fix verified live on PR #3146
    (`POST .../actions/runs/<id>/rerun`, the REST equivalent of this call).
    """
    runs = gh_json([
        "api",
        f"repos/{REPO}/actions/runs?head_sha={head_sha}&per_page=100",
    ])

    latest_by_workflow: dict[Any, dict[str, Any]] = {}
    for r in runs.get("workflow_runs", []):
        wf = r.get("workflow_id")
        cur = latest_by_workflow.get(wf)
        if cur is None or r.get("run_number", 0) > cur.get("run_number", 0):
            latest_by_workflow[wf] = r

    rerolled = []
    for r in latest_by_workflow.values():
        if r.get("status") != "completed":
            continue  # latest for this workflow is still progressing
        conclusion = (r.get("conclusion") or "").lower()
        if conclusion in _OK_CONCLUSIONS_REST:
            continue
        if r.get("run_attempt", 1) > MAX_RERUN_ATTEMPTS:
            continue
        cmd = ["run", "rerun", str(r["id"]), "--repo", REPO]
        if conclusion == "failure":
            cmd.append("--failed")
        try:
            gh(cmd)
            rerolled.append(r["id"])
        except RuntimeError:
            pass
    return rerolled


def comment_once(number: int, body: str, state: dict[str, Any]) -> None:
    """One comment per (pr, head_sha, reason) — the skiplist key guards it,
    so this is only called when the entry is first created."""
    gh(["pr", "comment", str(number), "--repo", REPO, "--body", body])


# ----------------------------------------------------------------------
# Tick
# ----------------------------------------------------------------------


def run_tick() -> dict[str, Any]:
    cfg = load_config()
    prev = load_state()
    skiplist: dict[str, Any] = prev.get("skiplist", {})
    state: dict[str, Any] = {
        "ts": _iso(),
        "enabled": cfg["enabled"],
        "dry_run": cfg["dry_run"],
        "auth_ok": None,
        "queue_depth": 0,
        "head_pr": None,
        "head_since": prev.get("head_since"),
        "last_successful_action_ts": prev.get("last_successful_action_ts"),
        "last_decision": None,
        "skiplist": skiplist,
    }

    if not cfg["enabled"]:
        state["last_decision"] = {"action": "disabled"}
        return state

    # Auth preflight — feeds liveness semantics (spec §10.4).
    try:
        gh(["api", "user", "--jq", ".login"], timeout=20)
        state["auth_ok"] = True
    except (RuntimeError, subprocess.TimeoutExpired):
        state["auth_ok"] = False
        state["last_decision"] = {"action": "abort", "reason": "auth_failed"}
        return state

    # Positive-probe preflight (2026-08-30 fix): order_queue()'s eligibility
    # test needs to know who GitHub's queue currently holds, because
    # autoMergeRequest alone cannot tell "accepted" apart from "ejected"/
    # "never armed". A failed probe here must fail closed, exactly like the
    # auth preflight above — silently falling back to an empty set would
    # readmit the exact bug this fetch exists to close (W104: never
    # fabricate a zero).
    try:
        in_queue_numbers = fetch_queue_membership()
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        state["last_decision"] = {
            "action": "abort",
            "reason": "queue_membership_probe_failed",
            "details": {"error": str(exc)[:200]},
        }
        return state

    queue = order_queue(fetch_queue(), in_queue_numbers=in_queue_numbers)
    state["queue_depth"] = len(queue)
    if not queue:
        state["head_pr"] = None
        state["head_since"] = None
        state["last_decision"] = {"action": "idle", "reason": "empty_queue"}
        return state

    # Head selection: first not-skiplisted candidate.
    head_summary = None
    detail = None
    for cand in queue:
        d = fetch_head_detail(cand["number"])
        if skiplist_active(skiplist, cand["number"], d["headRefOid"]):
            continue
        head_summary, detail = cand, d
        break
    if head_summary is None:
        state["last_decision"] = {"action": "idle", "reason": "all_skiplisted"}
        return state

    n = head_summary["number"]
    if state.get("head_pr") != n or prev.get("head_pr") != n:
        state["head_since"] = _iso()
    state["head_pr"] = n

    is_revert = REVERT_LABEL in {lbl["name"] for lbl in head_summary.get("labels", [])}
    required = required_contexts()
    blocking = blocking_required_checks(detail, required)
    reroll_key = f"reroll:{n}:{detail['headRefOid']}"
    rerolled_already = reroll_key in prev.get("rerolls", {})
    missing = missing_required_contexts(detail, required)
    missing_key = f"missing_update:{n}"
    state["missing_updates"] = prev.get("missing_updates", {})
    if not missing:
        state["missing_updates"].pop(missing_key, None)

    decision = decide_head(
        detail,
        main_green=main_suite_green(),
        deploy_in_flight=deploy_in_flight(),
        is_revert=is_revert,
        blocking_required=blocking,
        rerolled_already=rerolled_already,
        missing_required=missing,
        update_for_missing_already=missing_key in state["missing_updates"],
    )
    state["last_decision"] = {
        "action": decision.action, "pr": decision.pr, "reason": decision.reason,
        **({"details": decision.details} if decision.details else {}),
    }
    state["rerolls"] = prev.get("rerolls", {})

    if cfg["dry_run"]:
        print(f"[merge-train DRY-RUN] {json.dumps(state['last_decision'])}")
        return state

    # --- enforcing mode ---
    try:
        if decision.action == "update_branch":
            ok = update_branch(n, detail["headRefOid"])
            if ok:
                state["last_successful_action_ts"] = _iso()
                if decision.reason == "missing_required_contexts":
                    state["missing_updates"][missing_key] = {"ts": _now()}
            else:
                state["last_decision"]["result"] = "head_moved_422_retry"
        elif decision.action == "reroll_failed":
            ids = reroll_failed_runs(n, detail["headRefOid"])
            state["rerolls"][reroll_key] = {"ts": _now(), "run_ids": ids}
            state["last_successful_action_ts"] = _iso()
        elif decision.action == "comment_and_skip":
            key = f"{n}:{detail['headRefOid']}:{decision.reason}"
            if key not in skiplist:
                comment_once(n, decision.details["comment"], state)
                skiplist[key] = {"ts": _now()}
            state["last_successful_action_ts"] = _iso()
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        key = f"{n}:{detail['headRefOid']}:api_error"
        skiplist[key] = {"ts": _now(), "error": str(exc)[:200]}
        state["last_decision"]["result"] = f"api_error: {str(exc)[:120]}"

    return state


def main() -> int:
    if "--status" in sys.argv:
        print(json.dumps(load_state(), indent=2))
        return 0

    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("tick timeout")))
    signal.alarm(TICK_HARD_TIMEOUT_SECONDS)
    time.sleep(random.uniform(0, 30))  # jitter — desync from sibling 180s crons

    if not acquire_lock():
        print("[merge-train] lock held, skipping tick")
        return 0
    try:
        state = run_tick()
        write_state(state)
        print(f"[merge-train] tick ok: {json.dumps(state['last_decision'])} "
              f"queue={state['queue_depth']} dry_run={state['dry_run']}")
        return 0
    except TimeoutError:
        print("[merge-train] tick hard-timeout", file=sys.stderr)
        return 1
    except Exception as exc:  # state must reflect the crash, never silent
        try:
            write_state({"ts": _iso(), "crash": str(exc)[:300]})
        except OSError:
            pass
        print(f"[merge-train] tick crashed: {exc}", file=sys.stderr)
        return 1
    finally:
        signal.alarm(0)
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
