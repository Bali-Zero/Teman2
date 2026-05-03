"""
Mata Garuda — GitHub Trending Harvester Agent.

Fetches trending AI/ML repos from GitHub API and publishes to garuda:raw.
Layer: harvester (Layer 1).
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.github_tools import fetch_github_trending
from mata_garuda.tools.stream_tools import stream_info, stream_length, stream_publish
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "github_trending_harvester_GENOME.md")


@register_agent(name="GitHub Trending Harvester", func_name="get_github_trending_harvester")
def get_github_trending_harvester(model: str = "claude") -> Agent:
    """Fetches trending AI/ML repos from GitHub and publishes to garuda:raw."""

    def instructions(context_variables: dict) -> str:
        return """You are the GitHub Trending Harvester for Mata Garuda.

WORKFLOW:
1. Call fetch_github_trending with topics "machine-learning,artificial-intelligence,llm,rag"
2. For each repo, call stream_publish: title=repo_name, url, source="github", content=description
3. Store repos with 1000+ stars as KB facts
4. Call case_resolved with summary

CONSTRAINTS:
- Maximum 10 repos per run
- Only repos with activity in last 24h
- GitHub API: 60 req/h unauth (sufficient)
- NEVER export outside Mata Garuda
"""

    return Agent(
        name="GitHub Trending Harvester",
        model=model,
        instructions=instructions,
        functions=[
            fetch_github_trending, stream_publish, stream_length, stream_info,
            kb_search, kb_store, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="harvester",
    )
