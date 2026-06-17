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
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.config import NLM_FEEDER_BATCH_SIZE, NLM_FEEDER_SLEEP_BETWEEN_S
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.base_worker import redis_cmd
from mata_garuda.workers.nlm_feeder import (
    run_nlm_feeder_from_alerts,
    run_nlm_feeder_from_stream,
)

logger = logging.getLogger("mata_garuda.scripts.nlm_feeder_stream")


def main() -> int:
    # Preflight redis reachability — anti-silent-starvation (Mythos-P3,
    # 2026-06-14). base_worker.stream_read_new swallows a redis-cli
    # timeout as `[ERROR] -> []`, so a feeder pointed at an UNREACHABLE
    # redis reports a clean processed:0/fed:0 indefinitely — a connection
    # failure is indistinguishable from "no new items". This masked a
    # 33-day starvation (GARUDA_REDIS_HOST pinned to a down Mini while
    # 3144 items piled up on Pro localhost). Fail LOUD here so the 0/0/0
    # can never masquerade as healthy-idle: exit non-zero + an explicit
    # error JSON the sentinel/log-monitor can see.
    host = (os.environ.get("GARUDA_REDIS_HOST") or "").strip() or "127.0.0.1"
    ping = redis_cmd("PING", timeout=5)
    if ping != "PONG":
        logger.error(
            "nlm_feeder_stream: redis UNREACHABLE at host=%s (PING -> %r) "
            "— aborting; refusing to report 0/0/0 as healthy-idle",
            host, ping,
        )
        print(json.dumps(
            {"agent": "nlm_feeder_stream", "error": "redis_unreachable",
             "host": host, "ping": ping},
            ensure_ascii=False,
        ))
        return 3

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
