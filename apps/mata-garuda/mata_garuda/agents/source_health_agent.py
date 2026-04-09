"""
Mata Garuda — Source Health Agent.

Monitors source reliability, deactivates dead sources, proposes new ones.
Uses Thompson Sampling-style scoring: sources that produce approved items
get higher budget, sources with high reject rate get throttled.

Layer: analista (Layer 4). Autonomy: L1 (score) + L2 (deactivate, notify Zero).
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.knowledge_tools import kb_search, kb_store, kb_get_skills
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "source_health_agent_GENOME.md")


@register_agent(name="Source Health Agent", func_name="get_source_health_agent")
def get_source_health_agent(model: str = "claude") -> Agent:
    """Monitors and scores source reliability across all harvesters."""

    def instructions(context_variables: dict) -> str:
        return """You are the Source Health Agent for Mata Garuda.

Your mission: evaluate the health of all intelligence sources and make recommendations.

WORKFLOW:
1. Call kb_search for recent scored_items to see which sources are producing
2. Call kb_search for recent feedback entries to check failure patterns
3. For each source, calculate:
   - items_count: how many items in last 30 days
   - avg_score: average relevance score of produced items
   - failure_rate: how often the harvester for this source fails
   - last_success: when was the last successful fetch
4. Produce a health report:
   - ACTIVE: healthy sources
   - THROTTLE: sources with high noise ratio
   - DEACTIVATE: dead or consistently failing sources
   - REPLACE: suggest alternatives for deactivated sources
5. Call kb_store to save the health report (type="source_health")
6. Call send_tg_alert with summary for Zero
7. Call case_resolved

HEALTH METRICS:
- items_30d: volume last 30 days
- avg_quality_score: from scorer worker
- failure_rate: harvester failures / total runs
- recommendation: ACTIVE | THROTTLE | DEACTIVATE | REPLACE

CONSTRAINTS:
- Autonomy: L1 for scoring, L2 for deactivation proposals
- NEVER deactivate a source without TG notification to Zero
- Always suggest a replacement when recommending DEACTIVATE
"""

    return Agent(
        name="Source Health Agent",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store, kb_get_skills,
            send_tg_alert, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="analista",
    )
