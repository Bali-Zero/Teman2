#!/usr/bin/env python3
"""Fase 0 Day 3 driver — Gemini Deep Research across 4 topics + synthesize.

Produces research/sota-social-2026-v1/03_sota_literature.md.

Gate 5 (EOD day 3): ≥30 distinct source URLs, ≥10 mentions of 2025-26.

Run time: 15-25 min for 4 topics (Gemini Deep Research grounded).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

# Backend Settings placeholders
os.environ.setdefault("JWT_SECRET_KEY", "sota-research-local-dev-placeholder-32chars-min-ok")
os.environ.setdefault("API_KEYS", "sota-research-local-placeholder-key")

from backend.services.research.literature_agent import (  # noqa: E402
    LiteratureAgent,
    TOPICS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day3")

OUT = _REPO_ROOT / "research" / "sota-social-2026-v1" / "03_sota_literature.md"


def main() -> int:
    agent = LiteratureAgent(output_dir=OUT.parent)
    bodies: dict[str, str] = {}
    for topic in TOPICS:
        logger.info("researching %s (this may take 3-6 min)...", topic.slug)
        bodies[topic.slug] = agent.research_topic(topic)
        logger.info("  %s done (%d chars)", topic.slug, len(bodies[topic.slug]))

    md = agent.synthesize(bodies)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(md, encoding="utf-8")
    logger.info("wrote %s (%d chars)", OUT, len(md))

    total, recent = agent.count_sources(md)
    logger.info("Gate 5 counts: distinct_urls=%d recent_mentions=%d", total, recent)
    if total < 30 or recent < 10:
        logger.error(
            "Gate 5 FAIL: need ≥30 distinct URLs + ≥10 recent mentions, "
            "got %d URLs / %d recent",
            total, recent,
        )
        return 1
    logger.info("Gate 5 OK: %d URLs / %d recent mentions", total, recent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
