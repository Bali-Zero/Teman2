#!/usr/bin/env python3
"""Mata Garuda — NLM Feeder Stream runner (alerts + enriched).

Hourly cron-safe batch runner. Consumes BOTH `garuda:alerts` (high-quality
+ topic-enriched, primary source for multi-NB routing) and
`garuda:enriched` (raw, only items whose source maps to ai_research via
_SOURCE_TO_DOMAIN). Routes items to domain-matched NB-INTEL notebooks
(Immigration / Tax / Regulation / Press / AIResearch).

Counterpart to run_sentinel_py.py (which feeds only NB-INTEL-AIResearch
via legacy KB-scan mode). This runner closes the gap for the other 4
NB-INTEL by consuming the alerts stream that scorer.py populates with
topic classifications.

Layer 3 Nexus.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.config import NLM_FEEDER_BATCH_SIZE, NLM_FEEDER_SLEEP_BETWEEN_S
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.nlm_feeder import (
    run_nlm_feeder_from_alerts,
    run_nlm_feeder_from_stream,
)


def main() -> int:
    kb = KnowledgeBase()
    try:
        # Primary: alerts stream (topic-enriched, business-relevant).
        alerts_stats = run_nlm_feeder_from_alerts(
            kb,
            max_items=NLM_FEEDER_BATCH_SIZE,
            sleep_s=NLM_FEEDER_SLEEP_BETWEEN_S,
        )
        # Secondary: enriched stream (catches arxiv/rss items the
        # alerts stream may have skipped because they didn't reach
        # SCORE_SIGNAL threshold). Source-based inference handles them.
        enriched_stats = run_nlm_feeder_from_stream(
            kb,
            max_items=NLM_FEEDER_BATCH_SIZE,
            sleep_s=NLM_FEEDER_SLEEP_BETWEEN_S,
        )
    finally:
        kb.close()

    print(json.dumps(
        {
            "agent": "nlm_feeder_stream",
            "alerts": alerts_stats,
            "enriched": enriched_stats,
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
