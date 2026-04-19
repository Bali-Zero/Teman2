#!/usr/bin/env python3
"""Mata Garuda — NLM Expander runner (LaunchAgent-invoked, Sun 09:00 WITA)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.nlm_expander_agent import run_nlm_expander


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--proposal-threshold", type=int, default=50)
    args = p.parse_args()

    stats = run_nlm_expander(
        dry_run=args.dry_run,
        proposal_threshold=args.proposal_threshold,
    )
    print(f"[run_nlm_expander] stats: {stats}")
    return 0 if stats.get("tg_ok") else 1


if __name__ == "__main__":
    sys.exit(main())
