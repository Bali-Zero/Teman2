#!/usr/bin/env python3
"""Unit 3 — Autonomous nightly consumer (queue -> headless modus session).

Design spec: docs/superpowers/specs/2026-07-12-modus-autonomous-loop-design.md

Drains `pending` + `class=green` tasks from the D2.3 escalation queue
(scripts/sentinel_lib/escalations.py) and would launch a headless `claude`
session (Opus director + modus skill) inside a dedicated agent_start.py
worktree for each one.

Hard invariants (do not relax without a new spec):
  - Kill switch MODUS_AUTOLOOP_ENABLED defaults to FALSE. No-op until an
    operator flips it explicitly (scar #2 — never silently self-arm).
  - Single-machine guard (scar #10 split-brain): only the queue's writer
    machine (escalations._current_machine()) may drain it. An explicit
    MODUS_AUTOLOOP_MACHINE override lets an operator pin execution to a
    specific machine name; mismatch => graceful exit 0.
  - Hard cap K per run (default 5, MODUS_AUTOLOOP_MAX): never process more;
    always LOG how many were skipped by the cap, never silently truncate
    (scar #2).
  - DRY-RUN by default (MODUS_AUTOLOOP_DRYRUN defaults true): logs the
    intended launch, spawns nothing. Only an explicit "false" builds (and
    logs) the spawn argv via _spawn_session — which itself never execs;
    real process spawning is a separate, deliberately-not-built step.
  - Never-cascade final gate (HARD, spec §3): a quota-dead Fable window at
    the final gate must route to defer_task(), never to a weaker model.
  - Fail-open: any read/import error is logged and the process exits 0 —
    this must never crash the launchd job (scar #2 esiste≠armato).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("modus_autoloop")

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Env-var contract (all default-conservative; see module docstring)
# ---------------------------------------------------------------------------

ENV_ENABLED = "MODUS_AUTOLOOP_ENABLED"      # default "false"  — kill switch
ENV_MACHINE = "MODUS_AUTOLOOP_MACHINE"      # default unset    — optional machine pin
ENV_MAX = "MODUS_AUTOLOOP_MAX"              # default "5"      — hard cap K per run
ENV_DRYRUN = "MODUS_AUTOLOOP_DRYRUN"        # default "true"   — no-spawn safety


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def is_enabled() -> bool:
    """Kill switch. Defaults to disabled — must be explicitly flipped true."""
    return _truthy(os.environ.get(ENV_ENABLED, "false"))


def is_dry_run() -> bool:
    """Spawn-safety switch. Defaults to enabled (dry-run)."""
    return _truthy(os.environ.get(ENV_DRYRUN, "true"))


def get_cap() -> int:
    """Hard cap K on green tasks processed per run. Default 5."""
    raw = os.environ.get(ENV_MAX, "5")
    try:
        cap = int(raw)
    except ValueError:
        logger.warning("%s=%r is not an int, falling back to default 5", ENV_MAX, raw)
        return 5
    return cap if cap > 0 else 5


def _current_machine() -> str:
    """Delegate to the queue's own writer-machine resolver (single source of truth)."""
    from sentinel_lib import escalations  # local import: keep module import-safe if package moves

    return escalations._current_machine()


def _machine_guard_ok() -> bool:
    """Scar #10 split-brain guard.

    If MODUS_AUTOLOOP_MACHINE is set, it must match the queue's writer
    machine for THIS host; mismatch => this host is not authorized to
    drain the queue => graceful exit.
    """
    pinned = os.environ.get(ENV_MACHINE)
    if not pinned:
        return True
    try:
        current = _current_machine()
    except Exception as exc:  # noqa: BLE001 — fail-open, never crash the job
        logger.warning("machine guard: could not resolve current machine (%s); refusing to run", exc)
        return False
    if pinned != current:
        logger.info(
            "machine guard: MODUS_AUTOLOOP_MACHINE=%s != resolved machine=%s -> graceful exit",
            pinned,
            current,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Green-class gate (Unit 2, external module — imported defensively)
# ---------------------------------------------------------------------------


def _is_green(task: dict[str, Any]) -> bool:
    """Delegate to Unit 2's is_green(task) -> (bool, reason).

    Unit 2 (scripts/modus_green_gate.py) may not exist yet when this module
    is exercised standalone (sibling task) or in unit tests — treat any
    import/call failure as "not green" (fail-closed on the safety gate,
    fail-open on the process exit code).
    """
    try:
        from modus_green_gate import is_green  # local import: optional sibling module
    except ImportError:
        logger.warning("modus_green_gate not importable — treating task as not-green (fail-closed)")
        return False
    try:
        verdict = is_green(task)
        return bool(verdict[0])
    except Exception as exc:  # noqa: BLE001 — a broken gate must never crash the consumer
        logger.warning("is_green() raised for job=%s: %s (treating as not-green)", task.get("job"), exc)
        return False


# ---------------------------------------------------------------------------
# Queue read + filter
# ---------------------------------------------------------------------------


def _read_pending_green_tasks() -> list[dict[str, Any]]:
    """Read the queue, filter to pending + green. Fail-open on read errors."""
    from sentinel_lib import escalations

    try:
        pending = escalations.read_all_escalations(include_resolved=False)
    except Exception as exc:  # noqa: BLE001 — never crash the launchd job on a read error
        logger.error("read_all_escalations() failed: %s (treating as empty queue)", exc)
        return []

    green: list[dict[str, Any]] = []
    for task in pending:
        if task.get("status") != "pending":
            continue
        if task.get("class") != "green":
            continue
        if not _is_green(task):
            continue
        green.append(task)
    return green


def _apply_cap(tasks: list[dict[str, Any]], cap: int) -> tuple[list[dict[str, Any]], int]:
    """Split into (to_process, skipped_count). Never silently truncate (scar #2)."""
    to_process = tasks[:cap]
    skipped = len(tasks) - len(to_process)
    return to_process, skipped


# ---------------------------------------------------------------------------
# Spawn (dry-run gated) + defer
# ---------------------------------------------------------------------------


def _worktree_path_for(job: str) -> Path:
    return REPO_ROOT / ".worktrees" / f"autoloop-{job}"


def _spawn_session(task: dict[str, Any]) -> list[str]:
    """Build (but do not execute) the headless modus session argv.

    Constructs the `agent_start.py` worktree provisioning step conceptually
    and the `claude` headless invocation (Opus director + modus skill +
    mandate) as an argv list. This function is a pure builder — it never
    calls subprocess/os.exec. Real process spawning is a deliberately
    separate, not-yet-built step (see module docstring); tests must never
    call this expecting side effects.
    """
    job = str(task.get("job", "unknown-job"))
    mandate = str(task.get("mandate", ""))
    worktree = _worktree_path_for(job)

    argv = [
        "claude",
        "--model",
        "opus",
        "--print",
        "--dangerously-skip-permissions",  # headless unattended run inside its own worktree only
        f"Invoke skill modus. Mandate: {mandate}. Task job={job}. "
        f"Worktree: {worktree}. Final gate is Fable and must never cascade to a "
        "weaker model; if the Fable window is quota-dead at the final gate, "
        "leave the task deferred instead of degrading.",
    ]
    logger.info("would launch: %s in worktree %s", job, worktree)
    return argv


def defer_task(job: dict[str, Any] | str) -> None:
    """Record a task as 'deferred' (never 'resolved') when the final gate is quota-dead.

    Implements the never-cascade invariant (spec §3.1/§3): a dead Fable
    window at the final gate must never be routed to a weaker model. The
    task stays in the queue as deferred so it resurfaces next run instead
    of being silently dropped or falsely marked resolved.
    """
    from sentinel_lib import escalations

    job_id = job.get("job") if isinstance(job, dict) else job
    escalations.write_escalation(
        {
            "job": job_id,
            "status": "deferred",
            "reason": "final_gate_quota_dead",
            "note": (
                "Fable final-gate window was quota-dead at execution time. "
                "Never-cascade invariant: routed to deferred, NOT downgraded "
                "to a weaker model. Will resurface for a future run."
            ),
            "deferred_at": time.time(),
        }
    )
    logger.info("deferred job=%s (final gate quota-dead, never-cascade invariant)", job_id)


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------


def run() -> int:
    """Entry point. Always returns 0 on the fail-open paths (kill switch,
    machine guard, read errors) — a non-zero exit is reserved for genuine
    top-level unexpected exceptions, which are still logged, not raised,
    so the launchd job never crash-loops.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s modus_autoloop: %(message)s",
    )

    try:
        if not is_enabled():
            logger.info("disabled (%s is not truthy) — exiting", ENV_ENABLED)
            return 0

        if not _machine_guard_ok():
            return 0

        cap = get_cap()
        dry_run = is_dry_run()

        tasks = _read_pending_green_tasks()
        to_process, skipped = _apply_cap(tasks, cap)

        logger.info(
            "queue: %d green pending, cap=%d, processing=%d, skipped_by_cap=%d",
            len(tasks),
            cap,
            len(to_process),
            skipped,
        )
        if skipped:
            logger.info(
                "%d green task(s) skipped by cap this run — will remain pending for next run",
                skipped,
            )

        for task in to_process:
            job = task.get("job", "unknown-job")
            if dry_run:
                worktree = _worktree_path_for(str(job))
                logger.info("would launch: %s in worktree %s (dry-run, no spawn)", job, worktree)
                continue
            argv = _spawn_session(task)
            logger.info("built spawn argv for job=%s (not executed by this build): %s", job, argv)

        return 0
    except Exception:  # noqa: BLE001 — fail-open: never crash the launchd job
        logger.exception("modus_autoloop: unexpected error, failing open (exit 0)")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    return run()


if __name__ == "__main__":
    sys.exit(main())
