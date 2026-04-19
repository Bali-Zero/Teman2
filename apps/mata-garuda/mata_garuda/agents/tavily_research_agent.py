"""
Mata Garuda — Tavily research agent (retrieval-only external API).

Layer 1 (Harvester). Runs a rotating pool of queries against Tavily's
research API and publishes hits to garuda:raw.

GENOME: tavily_research_agent_GENOME.md
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mata_garuda.config import STREAM_RAW
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.tavily_tools import run_tavily_search
from mata_garuda.types import Agent
from mata_garuda.workers.base_worker import stream_publish as stream_publish_redis

logger = logging.getLogger("mata_garuda.agents.tavily_research_agent")

GENOME_FILE = str(Path(__file__).parent / "tavily_research_agent_GENOME.md")
AGENT_NAME = "tavily_research_agent"

DEFAULT_QUERIES = [
    "Indonesia business regulations 2026",
    "Bali property law foreigners",
    "Indonesia digital nomad visa",
    "Jakarta foreign investment incentives",
    "Indonesia company setup PT PMA requirements",
]


def run_tavily_batch(queries: list[str] | None = None) -> dict[str, Any]:
    """Execute a batch of Tavily queries and publish hits to garuda:raw."""
    if queries is None:
        queries = DEFAULT_QUERIES

    ts = datetime.now().isoformat(timespec="seconds")
    published = 0
    failures = 0
    last_reason = ""
    for q in queries:
        res = run_tavily_search(q)
        if not res.get("ok"):
            failures += 1
            last_reason = res.get("reason", "unknown")
            continue
        for hit in res["results"][:10]:
            url = hit.get("url") or ""
            title = hit.get("title") or url or "(untitled)"
            if not url:
                continue
            fields = {
                "title": title[:300],
                "url": url,
                "source": "tavily.com",
                "source_type": "tavily",
                "source_agent": AGENT_NAME,
                "content": (hit.get("content") or "")[:500],
                "agent": AGENT_NAME,
                "timestamp": ts,
                "query": q,
            }
            msg_id = stream_publish_redis(STREAM_RAW, fields)
            if isinstance(msg_id, str) and not msg_id.startswith("[ERROR]"):
                published += 1

    if published == 0:
        return {
            "case_resolved": False,
            "published": 0,
            "reason": last_reason or "no queries returned results",
        }
    return {
        "case_resolved": True,
        "published": published,
        "failures": failures,
        "reason": "",
    }


@register_agent(name=AGENT_NAME, func_name="get_tavily_research_agent")
def get_tavily_research_agent(model: str = "claude") -> Agent:
    def instructions(context_variables: dict) -> str:
        return """You are the Tavily Research Agent for Mata Garuda.

Call run_tavily_batch() to run the default query pool against Tavily
and publish results to garuda:raw. Retrieval-only — Tavily API used
for search, never for LLM generation.

ERROR HANDLING:
- TAVILY_API_KEY missing → case_not_resolved with reason
- All queries fail → case_not_resolved with last reason
"""

    return Agent(
        name=AGENT_NAME,
        model=model,
        instructions=instructions,
        functions=[run_tavily_batch, case_resolved, case_not_resolved],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
