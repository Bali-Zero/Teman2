"""
SEO Guardian — LEARN
======================
Extracts patterns from measured actions in memory.jsonl.
Updates patterns.json with statistical rules.

Usage:
    python seo_guardian_learn.py           # extract patterns
    python seo_guardian_learn.py --status  # show current patterns
"""

import argparse
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[SEO Learn] %(levelname)s: %(message)s")

AGENT_DIR = Path.home() / ".openclaw" / "workspace" / "autonomous" / "seo-guardian"
MEMORY_PATH = AGENT_DIR / "memory.jsonl"
PATTERNS_PATH = AGENT_DIR / "patterns.json"
STATE_PATH = AGENT_DIR / "state.json"

MIN_SAMPLES = 5
CONFIDENCE_THRESHOLD = 0.7


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def extract_patterns(entries: list[dict]) -> list[dict]:
    """Extract statistical patterns from measured actions."""
    # Group by action type
    by_action: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        if entry.get("measured") and not entry.get("dry_run"):
            by_action[entry.get("action", "unknown")].append(entry)

    patterns = []
    for action_type, actions in by_action.items():
        if len(actions) < MIN_SAMPLES:
            logger.info("Skipping %s: only %d samples (need %d)", action_type, len(actions), MIN_SAMPLES)
            continue

        # Calculate success rate
        successes = sum(1 for a in actions if a.get("result", {}).get("success"))
        success_rate = successes / len(actions)

        pattern = {
            "action": action_type,
            "sample_size": len(actions),
            "success_rate": round(success_rate, 2),
            "confidence": round(min(success_rate, len(actions) / (MIN_SAMPLES * 2)), 2),
            "first_seen": min(a.get("timestamp", "") for a in actions),
            "last_seen": max(a.get("timestamp", "") for a in actions),
            "extracted_at": datetime.now().isoformat(),
        }

        if pattern["confidence"] >= CONFIDENCE_THRESHOLD:
            pattern["recommendation"] = "continue"
        else:
            pattern["recommendation"] = "review"

        patterns.append(pattern)
        logger.info(
            "Pattern: %s — %d samples, %.0f%% success, confidence=%.2f → %s",
            action_type, len(actions), success_rate * 100,
            pattern["confidence"], pattern["recommendation"],
        )

    return patterns


def run_learn() -> dict:
    """Main learn loop."""
    entries = load_jsonl(MEMORY_PATH)
    measured = [e for e in entries if e.get("measured")]

    if not measured:
        logger.info("No measured actions to learn from")
        return {"status": "no_data", "total_entries": len(entries), "measured": 0}

    patterns = extract_patterns(entries)

    # Save patterns
    with open(PATTERNS_PATH, "w") as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)

    # Update state
    state = {}
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            state = json.load(f)
    state["last_learn_run"] = datetime.now().isoformat()
    state["patterns_count"] = len(patterns)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    return {
        "status": "completed",
        "total_entries": len(entries),
        "measured_entries": len(measured),
        "patterns_extracted": len(patterns),
        "patterns": patterns,
    }


def print_status() -> None:
    patterns = []
    if PATTERNS_PATH.exists():
        with open(PATTERNS_PATH) as f:
            patterns = json.load(f)

    print(f"\n=== SEO Guardian Learned Patterns ===")
    if not patterns:
        print("No patterns extracted yet (need 5+ measured samples per action type)")
    else:
        for p in patterns:
            print(f"  {p['action']}: {p['sample_size']} samples, "
                  f"{p['success_rate']*100:.0f}% success, "
                  f"confidence={p['confidence']:.2f} → {p['recommendation']}")
    print(f"=====================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Guardian — LEARN")
    parser.add_argument("--status", action="store_true", help="Show current patterns")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    result = run_learn()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
