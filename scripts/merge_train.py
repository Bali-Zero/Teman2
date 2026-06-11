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


def order_queue(prs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """FIFO by PR number, with the auto-revert priority lane at the head
    (spec §10.1). Opt-out label excluded entirely."""
    eligible = [
        p
        for p in prs
        if p.get("autoMergeRequest")
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
    failed_required: list[str],
    rerolled_already: bool,
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

    if failed_required:
        if not rerolled_already:
            return Decision("reroll_failed", pr=n, reason="red_checks_first_seen",
                            details={"failed": failed_required})
        return Decision(
            "comment_and_skip",
            pr=n,
            reason="red_checks",
            details={"comment": (
                "merge-train: required checks failed twice on this head — "
                "fix and push to re-enter the queue."
            ), "failed": failed_required},
        )

    if state == "BEHIND":
        return Decision("update_branch", pr=n, reason="behind")

    if state == "UNKNOWN":
        return Decision("wait", pr=n, reason="merge_state_recalculating")

    # BLOCKED with no failed required checks = checks still running (or
    # human-review policy, which auto-merge will hold anyway) → wait.
    # CLEAN/HAS_HOOKS/UNSTABLE → GitHub's own auto-merge completes it.
    return Decision("wait" if state == "BLOCKED" else "none", pr=n, reason=state.lower())


# ----------------------------------------------------------------------
# GitHub interactions (side-effect layer)
# ----------------------------------------------------------------------


def fetch_queue() -> list[dict[str, Any]]:
    return gh_json([
        "pr", "list", "--repo", REPO, "--state", "open", "--limit", "100",
        "--json", "number,labels,autoMergeRequest",
    ])


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


def failed_required_checks(detail: dict[str, Any], required: set[str]) -> list[str]:
    """Only REQUIRED contexts count (spec §10.3 / Codex 15)."""
    out = []
    for c in detail.get("statusCheckRollup") or []:
        name = c.get("name") or c.get("context") or ""
        conclusion = (c.get("conclusion") or c.get("state") or "").upper()
        if name in required and conclusion == "FAILURE":
            out.append(name)
    return sorted(set(out))


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


def reroll_failed_runs(number: int, head_sha: str) -> list[int]:
    """Re-run the exact failed run IDs attached to this head (Codex 13)."""
    runs = gh_json([
        "api",
        f"repos/{REPO}/actions/runs?head_sha={head_sha}&status=completed&per_page=50",
    ])
    rerolled = []
    for r in runs.get("workflow_runs", []):
        if r.get("conclusion") == "failure":
            try:
                gh(["run", "rerun", str(r["id"]), "--repo", REPO, "--failed"])
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

    queue = order_queue(fetch_queue())
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
    failed = failed_required_checks(detail, required)
    reroll_key = f"reroll:{n}:{detail['headRefOid']}"
    rerolled_already = reroll_key in prev.get("rerolls", {})

    decision = decide_head(
        detail,
        main_green=main_suite_green(),
        deploy_in_flight=deploy_in_flight(),
        is_revert=is_revert,
        failed_required=failed,
        rerolled_already=rerolled_already,
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
