"""
Mata Garuda — Fitness Tracker.

Track success/failure rate per agent over a rolling window.
If fitness degrades after a GENOME mutation, auto-revert.

Storage: feedback/{agent_name}_fitness.jsonl (one JSON line per run).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from mata_garuda.runtime.genome import revert_last_mutation

logger = logging.getLogger("mata_garuda.runtime")

FEEDBACK_DIR = Path(__file__).parent.parent.parent / "feedback"
WINDOW_SIZE = 10  # Number of recent runs to consider
DEGRADATION_THRESHOLD = 0.3  # If success rate drops below this, auto-revert


def _fitness_path(agent_name: str) -> Path:
    """Get fitness JSONL path for an agent."""
    FEEDBACK_DIR.mkdir(exist_ok=True)
    safe_name = agent_name.lower().replace(" ", "_").replace("-", "_")
    return FEEDBACK_DIR / f"{safe_name}_fitness.jsonl"


def record_run(agent_name: str, success: bool, mutation_version: int = 0) -> None:
    """Record a single run outcome.

    Args:
        agent_name: Agent display name
        success: True if case_resolved, False if case_not_resolved
        mutation_version: Current GENOME mutation count
    """
    path = _fitness_path(agent_name)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "success": success,
        "mutation_version": mutation_version,
    }
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    logger.info(
        f"[fitness] Recorded {'success' if success else 'failure'} "
        f"for {agent_name} (v{mutation_version})"
    )


def get_recent_runs(agent_name: str, window: int = WINDOW_SIZE) -> list[dict]:
    """Get the last N run records for an agent."""
    path = _fitness_path(agent_name)
    if not path.exists():
        return []

    lines = path.read_text().strip().split("\n")
    records = []
    for line in lines[-window:]:
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def get_success_rate(agent_name: str, window: int = WINDOW_SIZE) -> Optional[float]:
    """Calculate success rate over the last N runs.

    Returns:
        Float 0.0-1.0, or None if no runs recorded
    """
    runs = get_recent_runs(agent_name, window)
    if not runs:
        return None

    successes = sum(1 for r in runs if r.get("success"))
    return successes / len(runs)


def get_mutation_version(agent_name: str) -> int:
    """Get current mutation version from the most recent fitness record."""
    runs = get_recent_runs(agent_name, window=1)
    if runs:
        return runs[-1].get("mutation_version", 0)
    return 0


def check_and_auto_revert(agent_name: str) -> bool:
    """Check if fitness degraded after last mutation. Auto-revert if so.

    Logic:
    - Get runs at current mutation version
    - If enough runs (>= 3) and success rate < DEGRADATION_THRESHOLD
    - Then revert last GENOME mutation

    Returns:
        True if auto-revert was triggered
    """
    runs = get_recent_runs(agent_name)
    if len(runs) < 3:
        return False

    current_version = runs[-1].get("mutation_version", 0)
    if current_version == 0:
        return False  # No mutations to revert

    # Get runs at current version
    current_runs = [r for r in runs if r.get("mutation_version") == current_version]
    if len(current_runs) < 3:
        return False  # Not enough data at this version

    success_rate = sum(1 for r in current_runs if r.get("success")) / len(current_runs)

    if success_rate < DEGRADATION_THRESHOLD:
        logger.warning(
            f"[fitness] {agent_name} fitness degraded to {success_rate:.0%} "
            f"at mutation v{current_version}. Auto-reverting."
        )
        reverted = revert_last_mutation(agent_name)
        if reverted:
            # Record the revert as a special entry
            path = _fitness_path(agent_name)
            entry = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "event": "auto_revert",
                "from_version": current_version,
                "success_rate_at_revert": round(success_rate, 2),
            }
            with open(path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        return reverted

    return False


def get_fitness_summary(agent_name: str) -> str:
    """Human-readable fitness summary for an agent."""
    rate = get_success_rate(agent_name)
    runs = get_recent_runs(agent_name)
    version = get_mutation_version(agent_name)

    if rate is None:
        return f"{agent_name}: no runs recorded"

    total = len(runs)
    return (
        f"{agent_name}: {rate:.0%} success rate "
        f"(last {total} runs, mutation v{version})"
    )
