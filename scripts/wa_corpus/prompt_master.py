"""The grounded prompt-master (v5, winner of the query-lab) + recap validator.

Selected by query_lab.py over real Surya chats (Alexandre / Johanna / Fabio):
two-level structure = HEADLINE + a GENERAL RECAP from several points of view +
SPECIFIC POINTS, all source-grounded with verbatim citations. On the lab it
scored full recall (5/5 ground-truth facts on Alexandre) with zero
hallucinations and stayed under 2000 chars.

Note (lab finding): NLM is non-deterministic about populating structured
`references` — the SAME prompt on the SAME source returned 0 citations on one
run and 8 on the next. The query-runner therefore RETRIES when references come
back empty (a recap without traceable citations cannot pass the HITL check).
"""
from __future__ import annotations

# Section markers used by recap_is_valid (and by the recap consumer to split it).
REQUIRED_SECTIONS = (
    "HEADLINE",
    "GENERAL RECAP",
    "SPECIFIC POINTS",
)

PROMPT_MASTER = """You are a Bali Zero case analyst reviewing ONE WhatsApp conversation \
between a team member and a single client/lead.

HARD RULES (most important first):
1. Use ONLY this source. Quote the exact source text verbatim for every fact.
2. If a fact is absent, write "not mentioned" — never infer or invent.
3. Output in ENGLISH. Keep the whole answer under 2000 characters.
4. Cover ONLY this one client; if the chat mixes many clients, say so and stop.

Structure the answer exactly like this:

**HEADLINE**: one sentence — the single most important thing about this client right now.

GENERAL RECAP — one or two sentences from each point of view:
- Operational: which service/case is in progress and where it stands.
- Relationship: the client's tone, satisfaction, engagement (note any request to meet/call).
- Commercial: paying client or lead; any upsell/cross-sell or churn signal.
- Risk: anything time-critical, a complaint, or a blocker.

SPECIFIC POINTS — one line each, "not mentioned" if absent:
- Company / entity
- Service / case type
- Deadlines or dates
- Amounts / payments
- Documents requested or pending
- Next concrete action (who must do what)
- Last contact & topic"""


def recap_is_valid(recap: str) -> bool:
    """Structural check: all top-level section markers present in the recap."""
    upper = recap.upper()
    return all(sec in upper for sec in REQUIRED_SECTIONS)
