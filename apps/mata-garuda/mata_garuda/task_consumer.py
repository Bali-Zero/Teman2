"""
Mata Garuda — Task Consumer.

Reads research/enrichment tasks from a Redis stream and dispatches
appropriate MG agents. Tasks are generic — the consumer does not know
or care where they originate.

Usage:
    python -m mata_garuda.task_consumer              # one-shot
    python -m mata_garuda.task_consumer --dry-run    # show without dispatch
    python -m mata_garuda.task_consumer --stats      # show stream stats

Designed to run via LaunchAgent or manually after gap detection.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from mata_garuda.tools.task_tools import (
    TASK_STREAM,
    TaskRequest,
    _parse_task_entries,
    _redis_cmd,
    ack_task,
    ensure_task_group,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("task-consumer")

# Log dispatch decisions
LOG_DIR = Path(__file__).parent.parent / "logs"
DISPATCH_LOG = LOG_DIR / "task_dispatch.jsonl"


# ── Dispatch Table ──
# Maps (gap_type, attribute_prefix) → action
# Actions: "dispatch:<agent_name>" | "skip" | "log_only"
#
# This table grows as MG gains more agents.
# v1: most tasks are log_only since we have limited agents.

DISPATCH_TABLE: list[tuple[str, str, str]] = [
    # gap_type,     attribute contains,    action
    ("missing_attribute", "nip",             "log_only"),     # needs OSINT scrape (future NIP Finder agent)
    ("missing_attribute", "lhkpn",           "log_only"),     # needs LHKPN scraper (future)
    ("missing_attribute", "angkatan",        "log_only"),     # needs bio scraper (future)
    ("missing_relation",  "WORKS_AT",        "log_only"),     # needs roster cross-ref (future)
    ("missing_relation",  "officials_struktur", "log_only"),  # needs org chart scraper (future)
    ("missing_relation",  "procurement_link", "log_only"),    # needs LPSE scraper (future)
    ("missing_relation",  "officials_or_documents", "log_only"),  # orphan org
    ("stale_attribute",   "profile",         "log_only"),     # needs profile refresher (future)
]


def match_dispatch(task: TaskRequest) -> str:
    """Find the dispatch action for a task."""
    for gap_type, attr_pattern, action in DISPATCH_TABLE:
        if task.gap_type == gap_type and attr_pattern in task.attribute:
            return action
    return "log_only"


def log_dispatch(task: TaskRequest, action: str, result: str = "") -> None:
    """Append dispatch decision to audit log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "request_id": task.request_id,
        "entity": f"{task.entity_type}/{task.entity_name}",
        "gap_type": task.gap_type,
        "attribute": task.attribute,
        "priority": task.priority,
        "action": action,
        "result": result,
    }
    with open(DISPATCH_LOG, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_tasks(count: int = 50) -> list[TaskRequest]:
    """Read new tasks from the stream."""
    raw = _redis_cmd(
        "XREADGROUP", "GROUP", "mata-garuda-tasks", "mg-worker-1",
        "COUNT", str(count),
        "STREAMS", TASK_STREAM, ">"
    )
    if raw.startswith("[ERROR]") or not raw or raw == "(nil)":
        return []
    return _parse_task_entries(raw)


def dispatch_task(task: TaskRequest, dry_run: bool = False) -> str:
    """Dispatch a single task to the appropriate handler."""
    action = match_dispatch(task)

    if action == "skip":
        return "skipped"

    if action.startswith("dispatch:"):
        agent_name = action.split(":", 1)[1]
        if dry_run:
            return f"would dispatch to {agent_name}"

        # Import here to avoid circular imports
        from mata_garuda.registry import registry
        import mata_garuda.agents  # noqa: F401 — trigger registration

        agent_info = None
        for name, info in registry.agents_info.items():
            if name == agent_name or info.func_name == agent_name:
                agent_info = info
                break

        if agent_info is None:
            return f"agent {agent_name} not found"

        # Build query from task fields
        query = (
            f"Research task: find {task.attribute} for "
            f"{task.entity_type} '{task.entity_name}'"
        )
        if task.entity_nip:
            query += f" (NIP: {task.entity_nip})"

        # Run via the loop
        from mata_garuda.runtime.loop import run_agent_loop
        agent = agent_info.func(model="claude")
        response = run_agent_loop(agent=agent, query=query)

        # Check if case was resolved
        ctx = response.context_variables
        if ctx.get("case_resolved"):
            return "dispatched:resolved"
        elif ctx.get("case_not_resolved"):
            return f"dispatched:not_resolved ({ctx.get('not_resolved_reason', '')})"
        else:
            return "dispatched:unknown_outcome"

    # log_only
    return "logged"


def main():
    parser = argparse.ArgumentParser(description="Task consumer: task stream → agent dispatch")
    parser.add_argument("--dry-run", action="store_true", help="Show tasks without dispatching")
    parser.add_argument("--stats", action="store_true", help="Show stream statistics")
    parser.add_argument("--count", type=int, default=50, help="Max tasks to read (default: 50)")
    args = parser.parse_args()

    if args.stats:
        length = _redis_cmd("XLEN", TASK_STREAM)
        groups = _redis_cmd("XINFO", "GROUPS", TASK_STREAM)
        print(f"Task stream: {TASK_STREAM}")
        print(f"Length: {length}")
        print(f"Groups:\n{groups}")
        return

    ensure_task_group()
    tasks = read_tasks(count=args.count)

    if not tasks:
        logger.info("No new tasks in stream")
        return

    # Sort by priority
    tasks.sort(key=lambda t: t.priority)
    logger.info(f"Read {len(tasks)} tasks (priority range: {tasks[0].priority}-{tasks[-1].priority})")

    # Counters
    stats: dict[str, int] = {}

    for task in tasks:
        result = dispatch_task(task, dry_run=args.dry_run)
        action = match_dispatch(task)

        if args.dry_run:
            print(
                f"  [{task.priority}] {task.entity_type}/{task.entity_name}: "
                f"{task.gap_type} → {task.attribute} | {result}"
            )
        else:
            log_dispatch(task, action, result)
            ack_task(task.msg_id)

        stats[action] = stats.get(action, 0) + 1

    logger.info(f"Dispatch summary: {json.dumps(stats)}")

    if not args.dry_run:
        logger.info(f"All {len(tasks)} tasks ACKed and logged to {DISPATCH_LOG}")


if __name__ == "__main__":
    main()
