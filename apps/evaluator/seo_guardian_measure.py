"""
SEO Guardian — MEASURE
========================
Compares pre/post metrics for actions logged in memory.jsonl.
Updates each action entry with measured results.

Usage:
    python seo_guardian_measure.py           # measure pending actions
    python seo_guardian_measure.py --status  # show measurement status
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[SEO Measure] %(levelname)s: %(message)s")

PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENT_DIR = Path.home() / ".openclaw" / "workspace" / "autonomous" / "seo-guardian"
MEMORY_PATH = AGENT_DIR / "memory.jsonl"
STATE_PATH = AGENT_DIR / "state.json"


def load_memory() -> list[dict]:
    if not MEMORY_PATH.exists():
        return []
    entries = []
    with open(MEMORY_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def save_memory(entries: list[dict]) -> None:
    with open(MEMORY_PATH, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_pending_measurements(entries: list[dict], min_age_hours: int = 48) -> list[int]:
    """Find entries that are old enough to measure but haven't been measured yet."""
    cutoff = datetime.now() - timedelta(hours=min_age_hours)
    pending = []
    for i, entry in enumerate(entries):
        if entry.get("measured"):
            continue
        if entry.get("dry_run") and entry.get("result", {}).get("type") in ("logged_for_review", "pending_confirmation"):
            continue  # Skip dry-run/pending entries
        ts = entry.get("timestamp")
        if ts:
            action_time = datetime.fromisoformat(ts)
            if action_time < cutoff:
                pending.append(i)
    return pending


async def measure_indexing_action(entry: dict) -> dict:
    """Measure the impact of an indexing submission action."""
    # Check current indexing state
    indexing_state_path = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"
    if indexing_state_path.exists():
        with open(indexing_state_path) as f:
            state = json.load(f)
        return {
            "measured_at": datetime.now().isoformat(),
            "current_submitted": state.get("total_submitted", 0),
            "current_failed": len(state.get("failed", [])),
            "success": True,
        }
    return {"measured_at": datetime.now().isoformat(), "success": False, "reason": "state file not found"}


async def measure_action(entry: dict) -> dict | None:
    """Route measurement to the appropriate handler."""
    action = entry.get("action", "")
    if action == "submit_indexing_batch":
        return await measure_indexing_action(entry)
    if action == "report_anomaly":
        # Reports don't need measurement
        return {"measured_at": datetime.now().isoformat(), "success": True, "type": "report_no_measurement"}
    # Default: mark as measured with no data
    return {"measured_at": datetime.now().isoformat(), "success": True, "type": "no_measurement_available"}


async def run_measure() -> dict:
    """Main measurement loop."""
    entries = load_memory()
    pending = get_pending_measurements(entries)

    if not pending:
        logger.info("No actions pending measurement")
        return {"status": "no_pending", "total_entries": len(entries)}

    logger.info("Measuring %d actions (of %d total)", len(pending), len(entries))
    measured_count = 0

    for idx in pending:
        entry = entries[idx]
        measurement = await measure_action(entry)
        if measurement:
            entry["measured"] = True
            entry["measurement"] = measurement
            measured_count += 1
            logger.info("Measured: %s → %s", entry.get("action"), measurement.get("type", "OK"))

    save_memory(entries)

    # Update state
    state: dict[str, Any] = {}
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            state = json.load(f)
    state["last_measure_run"] = datetime.now().isoformat()
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    return {"status": "completed", "measured": measured_count, "total_entries": len(entries)}


def print_status() -> None:
    entries = load_memory()
    measured = sum(1 for e in entries if e.get("measured"))
    unmeasured = sum(1 for e in entries if not e.get("measured") and not e.get("dry_run"))
    dry_run = sum(1 for e in entries if e.get("dry_run"))

    print(f"\n=== SEO Guardian Measurement Status ===")
    print(f"Total actions:   {len(entries)}")
    print(f"Measured:        {measured}")
    print(f"Pending:         {unmeasured}")
    print(f"Dry-run (skip):  {dry_run}")
    print(f"=======================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Guardian — MEASURE")
    parser.add_argument("--status", action="store_true", help="Show measurement status")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    result = asyncio.run(run_measure())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
