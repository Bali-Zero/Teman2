#!/usr/bin/env python3
"""Mata Garuda — Weekly Digest runner (LaunchAgent-invoked, Sun 08:00 WITA)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.weekly_digest_agent import run_weekly_digest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-claude", action="store_true")
    args = p.parse_args()

    stats = run_weekly_digest(
        dry_run=args.dry_run,
        use_claude=not args.no_claude,
    )
    print(f"[run_weekly_digest] stats: {stats}")
    return 0 if stats.get("tg_ok") else 1


if __name__ == "__main__":
    sys.exit(main())
