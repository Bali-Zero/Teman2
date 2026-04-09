"""
Mata Garuda — AI Twitter/X Harvester Agent.

Searches for AI researcher activity on X/Twitter via Exa MCP (or Brave).
Layer: harvester (Layer 1).
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.scraper_tools import check_regulation_source
from mata_garuda.tools.stream_tools import stream_info, stream_length, stream_publish
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "ai_twitter_harvester_GENOME.md")


@register_agent(name="AI Twitter Harvester", func_name="get_ai_twitter_harvester")
def get_ai_twitter_harvester(model: str = "claude") -> Agent:
    """Searches for AI research trends on X/Twitter via web search."""

    def instructions(context_variables: dict) -> str:
        return """You are the AI Twitter Harvester for Mata Garuda.

Since direct X/Twitter API access is broken (CRC), you use web search
to find recent AI research discussions from X/Twitter.

WORKFLOW:
1. Use check_regulation_source to verify connectivity
2. Manually construct search queries about AI research trends
3. For each finding, call stream_publish: title, url, source="x_twitter", content=summary
4. Store notable trends in KB (type="pattern")
5. Call case_resolved with summary

NOTE: This is a placeholder harvester. In production, it will use Exa MCP
web_search_exa with domain filter x.com for targeted AI researcher monitoring.

CONSTRAINTS:
- Maximum 10 items per run
- Focus on: AI researchers, new model releases, benchmark results
- Source attribution required for every item
- NEVER export outside Mata Garuda
"""

    return Agent(
        name="AI Twitter Harvester",
        model=model,
        instructions=instructions,
        functions=[
            check_regulation_source,
            stream_publish, stream_length, stream_info,
            kb_search, kb_store, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="harvester",
    )
