#!/usr/bin/env python3
"""Mata Garuda — Intel Scraper Bridge runner.

Cron-safe batch runner (no Claude CLI reasoning loop). Calls the
deterministic bridge function directly and prints a JSON result.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.intel_scraper_bridge import bridge_intel_scraper


def main() -> int:
    result = bridge_intel_scraper()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("case_resolved", False) else 0
    # NOTE: we return 0 even on "no_recent_items" because the Lamarckian
    # case_not_resolved is informational, not an error, per GENOME.md.


if __name__ == "__main__":
    sys.exit(main())
