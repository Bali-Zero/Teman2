#!/usr/bin/env python3
"""Mata Garuda — WR2 Bridge Publisher runner."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.wr2_bridge_publisher import run_wr2_bridge_cycle


def main() -> int:
    result = run_wr2_bridge_cycle()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
