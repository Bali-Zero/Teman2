"""
Mata Garuda — Kemlu (Ministry of Foreign Affairs) harvester.

Layer 1 (Harvester). Scans kemlu.go.id news for treaty / bilateral
announcements impacting visa & business relations.
Publishes to garuda:osint.

GENOME: kemlu_harvester_GENOME.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mata_garuda.agents._goid_base import harvest_goid
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "kemlu_harvester_GENOME.md")
AGENT_NAME = "kemlu_harvester"
SOURCE_DOMAIN = "kemlu.go.id"
LANDING_URL = "https://kemlu.go.id/portal/id/list/berita"
ALLOW_PREFIXES = [
    "https://kemlu.go.id/portal/id/read/",
    "https://www.kemlu.go.id/portal/id/read/",
]


def harvest_kemlu() -> dict[str, Any]:
    """Harvest latest Kemlu news items into garuda:osint."""
    return harvest_goid(
        agent_name=AGENT_NAME,
        source_domain=SOURCE_DOMAIN,
        landing_url=LANDING_URL,
        allow_prefixes=ALLOW_PREFIXES,
    )


@register_agent(name=AGENT_NAME, func_name="get_kemlu_harvester")
def get_kemlu_harvester(model: str = "claude") -> Agent:
    def instructions(context_variables: dict) -> str:
        return """You are the Kemlu Harvester for Mata Garuda.

Call harvest_kemlu() once per run. Report case_resolved on publish,
otherwise case_not_resolved with the reason.
OSINT blindato: data flows ONLY to garuda:osint.
"""

    return Agent(
        name=AGENT_NAME,
        model=model,
        instructions=instructions,
        functions=[harvest_kemlu, case_resolved, case_not_resolved],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
