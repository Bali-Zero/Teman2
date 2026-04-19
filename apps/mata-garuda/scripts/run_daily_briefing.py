#!/usr/bin/env python3
"""Mata Garuda — Daily Briefing runner (LaunchAgent-invoked).

Runs every morning at 07:00 WITA. See
`mata_garuda/agents/daily_briefing_agent.py` for the actual logic.

Usage:
    python scripts/run_daily_briefing.py [--dry-run] [--no-claude-tldr]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.daily_briefing_agent import run_daily_briefing


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Don't send to Telegram, just print")
    p.add_argument("--no-claude-tldr", action="store_true",
                   help="Skip Claude CLI TL;DR (faster, fallback only)")
    args = p.parse_args()

    stats = run_daily_briefing(
        dry_run=args.dry_run,
        use_claude_tldr=not args.no_claude_tldr,
    )
    print(f"[run_daily_briefing] stats: {stats}")
    return 0 if stats.get("tg_ok") else 1


if __name__ == "__main__":
    sys.exit(main())
