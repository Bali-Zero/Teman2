"""
Mata Garuda — AI Newsletter/RSS Harvester Agent.

Fetches AI newsletter content from RSS feeds (The Batch, Import AI, TLDR, PapersWithCode).
Layer: harvester (Layer 1).
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.feed_tools import fetch_rss_feed, fetch_multiple_feeds
from mata_garuda.tools.stream_tools import stream_info, stream_length, stream_publish
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "ai_newsletter_harvester_GENOME.md")


@register_agent(name="AI Newsletter Harvester", func_name="get_ai_newsletter_harvester")
def get_ai_newsletter_harvester(model: str = "claude") -> Agent:
    """Fetches AI newsletter content from RSS feeds."""

    def instructions(context_variables: dict) -> str:
        return """You are the AI Newsletter Harvester for Mata Garuda.

WORKFLOW:
1. Call fetch_multiple_feeds with the feed URLs from your GENOME
2. For each item, call stream_publish: title, url, source="rss_newsletter", content=description
3. Store key insights in KB
4. Call case_resolved with summary

FEEDS:
- https://www.deeplearning.ai/the-batch/feed/ (The Batch - Andrew Ng)
- https://jack-clark.net/feed/ (Import AI)
- https://tldr.tech/ai/rss (TLDR AI)
- https://paperswithcode.com/latest/feed (Papers With Code)

CONSTRAINTS:
- Maximum 5 items per feed, 4 feeds = max 20 items total
- If a feed is unreachable: skip it, continue with others
- NEVER export outside Mata Garuda
"""

    return Agent(
        name="AI Newsletter Harvester",
        model=model,
        instructions=instructions,
        functions=[
            fetch_rss_feed, fetch_multiple_feeds,
            stream_publish, stream_length, stream_info,
            kb_search, kb_store, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="harvester",
    )
