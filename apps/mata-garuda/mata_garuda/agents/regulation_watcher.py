"""
Mata Garuda — Regulation Watcher Agent.

First real operational agent. Monitors peraturan.go.id for new regulations,
scrapes listings, and publishes to Redis Stream garuda:raw.

Layer: harvester (Layer 1)
Lamarckian: enabled — failures log to feedback, mutations propose fallback URLs
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.scraper_tools import (
    check_regulation_source,
    scrape_regulation_detail,
    scrape_regulations,
)
from mata_garuda.tools.stream_tools import (
    stream_info,
    stream_length,
    stream_publish,
)
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "regulation_watcher_GENOME.md")


@register_agent(name="Regulation Watcher", func_name="get_regulation_watcher")
def get_regulation_watcher(model: str = "claude") -> Agent:
    """Monitors peraturan.go.id and publishes new regulations to Redis Stream."""

    def instructions(context_variables: dict) -> str:
        return """You are the Regulation Watcher agent for Mata Garuda intelligence hub.

Your mission: monitor Indonesian regulation sources and publish new entries to the garuda:raw Redis Stream.

WORKFLOW:
1. Call check_regulation_source to verify peraturan.go.id is reachable
2. If unreachable, call case_not_resolved with reason and suggest fallback URL in insight
3. Call scrape_regulations to get the latest regulation listings
4. For each regulation found, call stream_publish with title, url, source, and content
5. Call stream_length to verify items were published
6. Call case_resolved with summary of what was published

CONSTRAINTS (from GENOME.md):
- Primary source: https://peraturan.go.id/harmonpusat
- Fallback: https://jdih.kemenkumham.go.id
- Maximum 10 regulations per run (avoid flooding)
- Always check source availability BEFORE scraping
- Log every failure with actionable insight for GENOME mutation
- NEVER export data outside Mata Garuda (OSINT blindato)
- All data goes to garuda:raw Redis Stream only

ERROR HANDLING:
- Source unreachable → case_not_resolved with fallback suggestion
- No regulations found → case_not_resolved with page structure change warning
- Redis publish fails → case_not_resolved with Redis connection details
"""

    return Agent(
        name="Regulation Watcher",
        model=model,
        instructions=instructions,
        functions=[
            check_regulation_source,
            scrape_regulations,
            scrape_regulation_detail,
            stream_publish,
            stream_length,
            stream_info,
            case_resolved,
            case_not_resolved,
        ],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
