"""
Mata Garuda — BKPM (Ministry of Investment) harvester.

Layer 1 (Harvester). Scans bkpm.go.id news for PMA/investment
regulation updates; publishes to garuda:osint.

GENOME: bkpm_harvester_GENOME.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mata_garuda.agents._goid_base import harvest_goid
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "bkpm_harvester_GENOME.md")
AGENT_NAME = "bkpm_harvester"
SOURCE_DOMAIN = "bkpm.go.id"
LANDING_URL = "https://www.bkpm.go.id/id/publikasi/siaran-pers"
ALLOW_PREFIXES = [
    "https://www.bkpm.go.id/id/publikasi/",
    "https://bkpm.go.id/id/publikasi/",
]


def harvest_bkpm() -> dict[str, Any]:
    """Harvest latest BKPM press releases into garuda:osint."""
    return harvest_goid(
        agent_name=AGENT_NAME,
        source_domain=SOURCE_DOMAIN,
        landing_url=LANDING_URL,
        allow_prefixes=ALLOW_PREFIXES,
    )


@register_agent(name=AGENT_NAME, func_name="get_bkpm_harvester")
def get_bkpm_harvester(model: str = "claude") -> Agent:
    def instructions(context_variables: dict) -> str:
        return """You are the BKPM Harvester for Mata Garuda.

Call harvest_bkpm() once per run. Report case_resolved on publish,
otherwise case_not_resolved with the reason.
OSINT blindato: data flows ONLY to garuda:osint.
"""

    return Agent(
        name=AGENT_NAME,
        model=model,
        instructions=instructions,
        functions=[harvest_bkpm, case_resolved, case_not_resolved],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
