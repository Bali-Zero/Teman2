#!/usr/bin/env python3
"""Mata Garuda — Regulation Alert runner (LaunchAgent-invoked, every 30m).

See `mata_garuda/agents/regulation_alert_agent.py` for the actual logic.

Usage:
    python scripts/run_regulation_alert.py [--dry-run] [--max-items N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.regulation_alert_agent import run_regulation_alert


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-items", type=int, default=20)
    args = p.parse_args()

    stats = run_regulation_alert(
        dry_run=args.dry_run,
        max_items=args.max_items,
    )
    print(f"[run_regulation_alert] stats: {stats}")
    return 0 if stats.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
