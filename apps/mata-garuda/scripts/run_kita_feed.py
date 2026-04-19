#!/usr/bin/env python3
"""Mata Garuda — Kita Feed Generator runner."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.kita_feed_generator import run_kita_feed_cycle


def main() -> int:
    result = run_kita_feed_cycle()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
