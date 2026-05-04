#!/usr/bin/env python3
"""Mata Garuda — NLM Feeder Stream runner.

Hourly cron-safe batch runner. Consumes garuda:enriched and routes items
to domain-matched NB-INTEL notebooks (Immigration / Tax / Regulation /
Press / AIResearch).

Counterpart to run_sentinel_py.py (which feeds only NB-INTEL-AIResearch
via KB-scan mode). This one closes the gap for the other 4 NB-INTEL.

Layer 3 Nexus.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.config import NLM_FEEDER_BATCH_SIZE, NLM_FEEDER_SLEEP_BETWEEN_S
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.nlm_feeder import run_nlm_feeder_from_stream


def main() -> int:
    kb = KnowledgeBase()
    try:
        stats = run_nlm_feeder_from_stream(
            kb,
            max_items=NLM_FEEDER_BATCH_SIZE,
            sleep_s=NLM_FEEDER_SLEEP_BETWEEN_S,
        )
    finally:
        kb.close()

    print(json.dumps({"agent": "nlm_feeder_stream", "stats": stats}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
