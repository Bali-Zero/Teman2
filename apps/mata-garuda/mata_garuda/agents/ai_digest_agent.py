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
from mata_garuda.tools.stream_tools import stream_publish, stream_length, stream_read
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "ai_digest_agent_GENOME.md")


@register_agent(name="AI Digest Agent", func_name="get_ai_digest_agent")
def get_ai_digest_agent(model: str = "claude") -> Agent:
    """Produces daily AI intelligence digest from NLM + KB."""

    def instructions(context_variables: dict) -> str:
        return """You are the AI Digest Agent for Mata Garuda.

Your mission: produce a concise daily intelligence digest about AI research
that Zero can read in 2 minutes. You MUST use ONLY real data from tools.

CRITICAL RULE: NEVER invent, fabricate, or hallucinate any paper, repo, or link.
If a tool returns no results, say "no data" — do NOT make up results.

WORKFLOW:
1. Call kb_search with query "SCORE" to find scored items (they contain TITLE, SCORE, URL, CONTENT)
2. Call kb_search with query "arxiv" to find harvested arXiv papers
3. Call kb_search with query "github" to find harvested repos
4. Call stream_read with stream="garuda:enriched" and count=20 to get raw items from Redis
5. From ALL these real results, select the top 5 most relevant for Nuzantara (RAG, KG, agents, business)
6. Write the digest using ONLY titles and URLs you found in the tool results
7. Call stream_publish to garuda:digest
8. Call send_tg_alert with the digest text
9. Call case_resolved

DIGEST FORMAT:
🔬 AI INTEL DIGEST — [date]

1. [TAG] EXACT title from tool results — one-line insight
   → EXACT URL from tool results

Tags: [SIGNAL] important, [CODE] applicable to Nuzantara, [WATCH] monitor, [TREND] pattern

CONSTRAINTS:
- Maximum 5 bullet points
- EVERY title and URL must come from a tool result — NEVER fabricate
- If no items found: produce "quiet day" digest honestly
- Language: Italian for Zero
- NEVER include OSINT data
"""

    return Agent(
        name="AI Digest Agent",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store, kb_get_skills,
            nlm_query, stream_read, stream_publish, stream_length,
            send_tg_alert, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="analista",
    )
