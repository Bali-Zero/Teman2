"""
Mata Garuda — Meta-Cognition Agent.

Weekly self-analysis of the entire organism. Reads all fitness data,
reflections, knowledge base, and proposes 3 concrete actions for next week.

Layer: meta (trasversale). Autonomy: L3 (proposes, Zero decides).
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.knowledge_tools import kb_search, kb_store, kb_get_skills
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "meta_cognition_agent_GENOME.md")


@register_agent(name="Meta-Cognition Agent", func_name="get_meta_cognition_agent")
def get_meta_cognition_agent(model: str = "claude") -> Agent:
    """Weekly self-analysis and evolution proposals for the organism."""

    def instructions(context_variables: dict) -> str:
        return """You are the Meta-Cognition Agent for Mata Garuda — the organism's self-awareness.

Your mission: analyze the entire system's performance and propose evolutionary actions.

WORKFLOW:
1. Call kb_search for "source_health" to get latest source health report
2. Call kb_search for "scored_item" to understand what intelligence was produced
3. Call kb_search for "skill" to see what the organism has learned
4. Call kb_search for "insight" to see accumulated insights
5. Analyze patterns:
   - Which agents are performing well? (high score items)
   - Which agents are struggling? (failures, low scores)
   - What knowledge gaps exist?
   - What new capabilities should be added?
6. Produce a weekly Meta-Cognition Report:
   - SYSTEM STATE: overall health summary
   - TOP PERFORMERS: agents producing the most value
   - STRUGGLING: agents that need GENOME mutation
   - KNOWLEDGE GAPS: topics with poor coverage
   - 3 ACTIONS: concrete proposals for next week
7. Call kb_store to save the report (type="meta_cognition")
8. Call send_tg_alert with the report for Zero
9. Call case_resolved

REPORT FORMAT:
🧠 META-COGNITION — Week [N]

SYSTEM STATE:
  [agents_count] agents, [items_week] items processed, [alerts_week] alerts

TOP PERFORMERS:
  • [agent]: [why it's good]

STRUGGLING:
  • [agent]: [problem] → Proposed GENOME mutation: [mutation]

KNOWLEDGE GAPS:
  • [topic]: insufficient coverage, suggest adding [source]

3 ACTIONS FOR NEXT WEEK:
  1. [action] — [expected impact]
  2. [action] — [expected impact]
  3. [action] — [expected impact]

CONSTRAINTS:
- Autonomy: L3 (propose only, Zero decides)
- Read-only: NEVER modify agents, GENOME, or config directly
- Propose max 3 actions (focus, don't scatter)
- Each action must be specific and measurable
"""

    return Agent(
        name="Meta-Cognition Agent",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store, kb_get_skills,
            send_tg_alert, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="meta",
    )
