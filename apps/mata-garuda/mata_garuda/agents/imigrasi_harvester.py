"""
Mata Garuda — Imigrasi (Directorate General of Immigration) harvester.

Layer 1 (Harvester). Scans imigrasi.go.id news landing page, publishes
new links to garuda:osint.

GENOME: imigrasi_harvester_GENOME.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mata_garuda.agents._goid_base import harvest_goid
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "imigrasi_harvester_GENOME.md")
AGENT_NAME = "imigrasi_harvester"
SOURCE_DOMAIN = "imigrasi.go.id"
LANDING_URL = "https://www.imigrasi.go.id/berita/"
ALLOW_PREFIXES = [
    "https://www.imigrasi.go.id/berita/",
    "https://imigrasi.go.id/berita/",
]


def harvest_imigrasi() -> dict[str, Any]:
    """Harvest latest imigrasi.go.id news items into garuda:osint."""
    return harvest_goid(
        agent_name=AGENT_NAME,
        source_domain=SOURCE_DOMAIN,
        landing_url=LANDING_URL,
        allow_prefixes=ALLOW_PREFIXES,
    )


@register_agent(name=AGENT_NAME, func_name="get_imigrasi_harvester")
def get_imigrasi_harvester(model: str = "claude") -> Agent:
    def instructions(context_variables: dict) -> str:
        return """You are the Imigrasi Harvester for Mata Garuda.

Call harvest_imigrasi() once per run. Report case_resolved if items
were published, otherwise case_not_resolved with the reason.
OSINT blindato: data flows ONLY to garuda:osint.
"""

    return Agent(
        name=AGENT_NAME,
        model=model,
        instructions=instructions,
        functions=[harvest_imigrasi, case_resolved, case_not_resolved],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
