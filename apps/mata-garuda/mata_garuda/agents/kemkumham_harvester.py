"""
Mata Garuda — Kemkumham (Ministry of Law & Human Rights) harvester.

Layer 1 (Harvester). Scans kemenkumham.go.id news for legal
regulation updates. Publishes to garuda:osint.

GENOME: kemkumham_harvester_GENOME.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mata_garuda.agents._goid_base import harvest_goid
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "kemkumham_harvester_GENOME.md")
AGENT_NAME = "kemkumham_harvester"
SOURCE_DOMAIN = "kemenkumham.go.id"
# Official domain since 2024 is kemenkumham.go.id (old kemkumham.go.id
# 301s to it); landing page lists berita items.
LANDING_URL = "https://www.kemenkumham.go.id/berita"
ALLOW_PREFIXES = [
    "https://www.kemenkumham.go.id/berita/",
    "https://kemenkumham.go.id/berita/",
]


def harvest_kemkumham() -> dict[str, Any]:
    """Harvest latest Kemkumham news items into garuda:osint."""
    return harvest_goid(
        agent_name=AGENT_NAME,
        source_domain=SOURCE_DOMAIN,
        landing_url=LANDING_URL,
        allow_prefixes=ALLOW_PREFIXES,
    )


@register_agent(name=AGENT_NAME, func_name="get_kemkumham_harvester")
def get_kemkumham_harvester(model: str = "claude") -> Agent:
    def instructions(context_variables: dict) -> str:
        return """You are the Kemkumham Harvester for Mata Garuda.

Call harvest_kemkumham() once per run. Report case_resolved on publish,
otherwise case_not_resolved with the reason.
OSINT blindato: data flows ONLY to garuda:osint.
"""

    return Agent(
        name=AGENT_NAME,
        model=model,
        instructions=instructions,
        functions=[harvest_kemkumham, case_resolved, case_not_resolved],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
