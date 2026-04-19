"""
Mata Garuda — Intel Scraper bridge agent.

Layer 1 (Harvester). Bridges 609 curated sources from
apps/bali-intel-scraper/ into Mata Garuda's garuda:raw stream without
touching the scraper itself. Reads the locally-persisted
published_articles.json.

GENOME: intel_scraper_bridge_GENOME.md
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from mata_garuda.config import STREAM_RAW
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.intel_scraper_tools import (
    filter_recent,
    read_published_articles,
)
from mata_garuda.types import Agent
from mata_garuda.workers.base_worker import stream_publish as stream_publish_redis

logger = logging.getLogger("mata_garuda.agents.intel_scraper_bridge")

GENOME_FILE = str(Path(__file__).parent / "intel_scraper_bridge_GENOME.md")
AGENT_NAME = "intel_scraper_bridge"
DEFAULT_WINDOW_HOURS = 24
DEFAULT_MAX_ITEMS = 50


def bridge_intel_scraper(
    window_hours: int = DEFAULT_WINDOW_HOURS,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> dict[str, Any]:
    """Publish recent bali-intel-scraper articles to garuda:raw.

    Returns {"case_resolved": bool, "published": int, "reason": str}.
    """
    articles = read_published_articles()
    if not articles:
        return {
            "case_resolved": False,
            "published": 0,
            "reason": "published_articles.json missing or empty",
        }

    since = (datetime.now() - timedelta(hours=window_hours)).isoformat(
        timespec="seconds"
    )
    recent = filter_recent(articles, since)
    if not recent:
        return {
            "case_resolved": False,
            "published": 0,
            "reason": f"no items newer than {since}",
        }

    recent = recent[:max_items]
    published = 0
    failures = 0
    for art in recent:
        url = art.get("url", "")
        title = art.get("title", "") or url
        src = art.get("source") or _infer_source(url)
        fields = {
            "title": title[:300],
            "url": url,
            "source": src,
            "source_type": "intel_scraper",
            "source_agent": AGENT_NAME,
            "content": "",
            "agent": AGENT_NAME,
            "timestamp": art.get("published_at")
            or datetime.now().isoformat(timespec="seconds"),
        }
        msg_id = stream_publish_redis(STREAM_RAW, fields)
        if isinstance(msg_id, str) and not msg_id.startswith("[ERROR]"):
            published += 1
        else:
            failures += 1
            logger.warning("publish failed for %s: %s", url, msg_id)

    if published == 0:
        return {
            "case_resolved": False,
            "published": 0,
            "reason": f"all {failures} publish attempts failed",
        }

    return {
        "case_resolved": True,
        "published": published,
        "failures": failures,
        "reason": "",
    }


def _infer_source(url: str) -> str:
    """Cheap domain extraction without urllib dependency cost."""
    if "://" in url:
        tail = url.split("://", 1)[1]
    else:
        tail = url
    return tail.split("/", 1)[0].lower() or "unknown"


@register_agent(name=AGENT_NAME, func_name="get_intel_scraper_bridge")
def get_intel_scraper_bridge(model: str = "claude") -> Agent:
    """Harvester agent that republishes bali-intel-scraper output."""

    def instructions(context_variables: dict) -> str:
        return """You are the Intel Scraper Bridge agent for Mata Garuda.

Your mission: each run, call bridge_intel_scraper() to forward the
latest curated articles from apps/bali-intel-scraper/ into garuda:raw.

CONSTRAINTS (from GENOME.md):
- Read-only consumer of published_articles.json — never mutate it
- Window: last 24h by default (override via window_hours)
- Max 50 items per run
- NEVER export OSINT data outside Mata Garuda
- Source marker: source_agent=intel_scraper_bridge

ERROR HANDLING:
- File missing → case_not_resolved with reason
- No recent items → case_not_resolved (not an error, informational)
- Stream publish failures → counted, agent only fails if ALL failed
"""

    return Agent(
        name=AGENT_NAME,
        model=model,
        instructions=instructions,
        functions=[bridge_intel_scraper, case_resolved, case_not_resolved],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
