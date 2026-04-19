#!/usr/bin/env python3
"""
Mata Garuda — Public Channel runner.

Usage:
    cd ~/Desktop/nuzantara/apps/mata-garuda
    source .venv/bin/activate
    python scripts/run_public_channel.py

Safe in DRY-RUN if TELEGRAM_PUBLIC_CHANNEL_ID is not set.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.public_channel_publisher import run_public_channel_cycle


def main() -> int:
    result = run_public_channel_cycle()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
