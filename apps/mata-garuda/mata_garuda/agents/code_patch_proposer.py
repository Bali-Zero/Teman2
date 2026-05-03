"""
Mata Garuda — Code Patch Proposer Agent.

When an AI paper/repo has high nuzantara_relevance, proposes a code patch
for the Nuzantara monorepo. Patch is STAGED (Option B) — Zero applies manually.

Layer: analista (Layer 4). Trigger: garuda:alerts with ai_research topic.
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.tools.stream_tools import stream_publish
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "code_patch_proposer_GENOME.md")

PATCH_DIR = Path("/tmp/mata_garuda_patches")


@register_agent(name="Code Patch Proposer", func_name="get_code_patch_proposer")
def get_code_patch_proposer(model: str = "claude") -> Agent:
    """Proposes code patches for Nuzantara based on AI research findings."""

    def instructions(context_variables: dict) -> str:
        return """You are the Code Patch Proposer for Mata Garuda.

Your mission: when you find AI research that could improve the Nuzantara codebase,
draft a concrete patch proposal and notify Zero.

WORKFLOW:
1. Call kb_search for recent high-score AI items (query: "retrieval rag embedding agent")
2. For each relevant finding, analyze: "How could this improve Nuzantara?"
3. Draft a patch proposal in markdown:
   - What paper/repo inspired this
   - Which Nuzantara file(s) would change
   - What the change would look like (pseudocode diff)
   - Expected improvement
4. Call kb_store to save the proposal (type="patch_proposal")
5. Call send_tg_alert to notify Zero with the proposal summary
6. Call case_resolved

PATCH PROPOSAL FORMAT:
🔧 PATCH PROPOSAL — [date]

Paper/Repo: [title] ([url])
Target: apps/backend-rag/backend/services/rag/hybrid_search.py
Change: [one paragraph describing the modification]
Expected: [one sentence on expected improvement]

Stored in: /tmp/mata_garuda_patches/[id].md

CONSTRAINTS:
- NEVER apply patches directly — Option B (staged, Zero applies)
- NEVER modify Nuzantara code — only propose
- Patch files go to /tmp/mata_garuda_patches/ only
- Only propose patches with clear, measurable improvements
- If no relevant findings: case_resolved with "no patches today"
- Autonomy: L2 (proposes, Zero decides)
"""

    return Agent(
        name="Code Patch Proposer",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store,
            stream_publish, send_tg_alert,
            case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="analista",
    )
