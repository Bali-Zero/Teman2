"""
Mata Garuda — arXiv Harvester Agent.

Fetches latest AI/ML papers from arXiv and publishes to garuda:raw.
Layer: harvester (Layer 1). Lamarckian-enabled.
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.arxiv_tools import fetch_arxiv_papers
from mata_garuda.tools.stream_tools import stream_info, stream_length, stream_publish
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "arxiv_harvester_GENOME.md")


@register_agent(name="ArXiv Harvester", func_name="get_arxiv_harvester")
def get_arxiv_harvester(model: str = "claude") -> Agent:
    """Fetches latest AI/ML papers from arXiv and publishes to garuda:raw."""

    def instructions(context_variables: dict) -> str:
        return """You are the ArXiv Harvester agent for Mata Garuda intelligence hub.

Your mission: fetch the latest AI/ML papers from arXiv and publish key findings to garuda:raw.

WORKFLOW:
1. Call fetch_arxiv_papers with categories "cs.AI,cs.CL,cs.LG,cs.IR" and max_results=20
2. For each paper, call stream_publish with title, url, source="arxiv", and content=abstract
3. Call kb_store for any particularly notable papers (type="fact", source="arxiv")
4. Call stream_length to verify items were published
5. Call case_resolved with summary

CONSTRAINTS (from GENOME.md):
- Categories: cs.AI, cs.CL, cs.LG, cs.IR
- Maximum 20 papers per run
- Content = abstract only (no PDF download)
- Always include arXiv URL in stream_publish
- NEVER export data outside Mata Garuda
"""

    return Agent(
        name="ArXiv Harvester",
        model=model,
        instructions=instructions,
        functions=[
            fetch_arxiv_papers, stream_publish, stream_length, stream_info,
            kb_search, kb_store, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="harvester",
    )
