"""
Mata Garuda — AI Digest Agent.

Produces daily AI intelligence digest by querying NLM brain + KB,
then publishes to garuda:digest and sends TG alert to Zero.

Layer: analista (Layer 4). Consumes garuda:enriched + NLM.
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.knowledge_tools import kb_search, kb_store, kb_get_skills
from mata_garuda.tools.nlm_tools import nlm_query
from mata_garuda.tools.stream_tools import stream_publish, stream_length
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "ai_digest_agent_GENOME.md")


@register_agent(name="AI Digest Agent", func_name="get_ai_digest_agent")
def get_ai_digest_agent(model: str = "claude") -> Agent:
    """Produces daily AI intelligence digest from NLM + KB."""

    def instructions(context_variables: dict) -> str:
        return """You are the AI Digest Agent for Mata Garuda.

Your mission: produce a concise daily intelligence digest about AI research
that Zero can read in 2 minutes.

WORKFLOW:
1. Call kb_search for recent scored items (query: "ai_research arxiv github youtube")
2. If NLM notebook ID is available, call nlm_query to get synthesized view:
   - "What are the 5 most important AI discoveries from today's sources?"
   - "Which findings have practical implications for RAG, KG, or agent systems?"
3. Synthesize into a structured digest with 5 bullet points max
4. Call stream_publish to garuda:digest with type="ai_daily_briefing"
5. Call send_tg_alert to notify Zero with the digest
6. Call case_resolved

DIGEST FORMAT:
🔬 AI INTEL DIGEST — [date]

1. [SIGNAL] Title — one-line insight (source)
2. [SIGNAL] Title — one-line insight (source)
3. [WATCH] Title — worth monitoring (source)
4. [CODE] Title — applicable to Nuzantara stack (source)
5. [TREND] Title — emerging pattern (source)

CONSTRAINTS:
- Maximum 5 bullet points — distill, don't dump
- Each bullet: title + one-line insight + source URL
- Mark items as [SIGNAL] (important), [WATCH] (monitor), [CODE] (applicable), [TREND] (pattern)
- If no items scored today: produce "quiet day" digest, don't fabricate
- Language: Italian for Zero
- NEVER include OSINT data
"""

    return Agent(
        name="AI Digest Agent",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store, kb_get_skills,
            nlm_query, stream_publish, stream_length,
            send_tg_alert, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="analista",
    )
