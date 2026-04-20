#!/usr/bin/env python3
"""Mata Garuda — WR Topic Agent runner (Wed/Sat 08:00 WITA)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.wr_topic_agent import run_wr_topic_agent


def main() -> int:
    result = run_wr_topic_agent()
    print(f"[run_wr_topic] stats: {json.dumps(result, default=str)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
