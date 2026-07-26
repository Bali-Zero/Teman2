"""
Zantara Core Prompt — v5: the audience-COMPOSED prompt (cure for C19/C20).

Executes: research/operations design doc
``2026-07-25-DESIGN-v5-audience-composed-prompt.md`` (Fable 5, M5), the
prompt-layer twin of T-VIS discovered live 2026-07-25.

## The defect this fixes

A synthetic client-role caller (phone not in owner/team lists, so
``_resolve_trusted_wa_profile`` correctly returned ``None``) received, through
the real prod path: "Hey! Here is the official breakdown ... **You can pass
this information directly to the client** ... if you want to share those with
the client next!"

Root cause: ``prompt_builder.py`` composes the system prompt ADDITIVELY —
CREATOR_PERSONA/TEAM_PERSONA get prepended for creator/team callers, but
there is no CLIENT_PERSONA. The client is the *default* case, and the
default body (``zantara_core_v4.py``) is written in an INTERNAL register
("a client asks…", "the client describing their situation") and carries the
full CRM tool playbook (``crm_query``) — every anonymous caller's prompt
teaches the model to call a tool the security tourniquet (SENSITIVE_TOOLS,
#2962) then DENIES, burning ReAct steps (cap 2 on WhatsApp) and leaking
internal structure.

## The shape this module builds

    SYSTEM = CORE_FACTUAL + AUDIENCE_VOICE[audience] + CAPABILITY_BLOCK[audience]

- ``CORE_FACTUAL`` — audience-neutral: security/identity lock, tool-usage
  policy MINUS the CRM playbook, system framing, grounding hierarchy,
  language/greeting/citation/escalation/crash protocols, worked examples,
  and the private pre-answer checklist. Extracted from v4 BY SLICING THE
  IMPORTED v4 STRINGS THEMSELVES (never retyped) so regulatory facts, KBLI
  codes, dates, and prices stay byte-identical by construction. The only
  edits are 7 discourse-person neutralizations (see
  ``REFERENT_NEUTRALIZATIONS`` / ``INTERNAL_MONOLOGUE_NEUTRALIZATION`` below)
  that stop the shared body from saying "the client"/"a client" while
  talking about the very person it might be talking TO — a wording fix, not
  a fact change. Every replacement is verified 1:1 against the v4 source at
  import time (``_apply_neutralizations`` raises if the count ever drifts
  from exactly 1, so a v4 edit that moves this text doesn't silently
  desync v5).
- ``AUDIENCE_VOICE[client]`` — NEW (the actual fix for C19). Speaks directly
  to the person in second person, never narrates internal process, never
  implies another audience exists. Escalation is "a Bali Zero specialist
  will follow up with you", never "I'll pass this to the client".
- ``AUDIENCE_VOICE[team]`` / ``[creator]`` — the existing ``TEAM_PERSONA`` /
  ``CREATOR_PERSONA``, re-exported unchanged from v4 (which re-exports them
  unchanged from v1 — same objects, byte-identical).
- ``CAPABILITY_BLOCK[team|creator]`` — the ``crm_query`` playbook, sliced
  verbatim out of v4's ``TOOL_USAGE_POLICY`` (the fix for C20).
  ``CAPABILITY_BLOCK[client]`` is empty by construction.

## Versioned door

Additive only. This file does NOT modify v4 (or any earlier version) in
place, and ``backend/llm/prompt_manager.py`` (the versioned door) is NOT
touched by this change — it still resolves ``ZANTARA_MASTER_TEMPLATE`` as a
single flat string chosen at import time from ``ZANTARA_PROMPT_VERSION``,
exactly as it does today for v1-v4. Wiring ``ZANTARA_PROMPT_VERSION=v5``
into that door (and threading a real per-request audience value into
``build_master_template()`` below) is deliberately NOT done here: this
composition depends on the audience value that the T4 "team-principal" lane
(server-resolved role → ``state.agent_role``) derives, and building the
consumer first would mean guessing at its input (see the design doc's
Sequencing note). Until that wiring lands, ``ZANTARA_PROMPT_VERSION=v5`` has
no effect anywhere — the door's behavior for every existing value (unset,
v1, v2, v3, v4) is provably unchanged by this file's mere existence
(see ``test_zantara_core_v5.py::TestFlagOff``).
"""

from backend.prompts.zantara_core_v4 import (
    CITATION_RULES,
    CLOSING_PHRASES,
    CRASH_PROTOCOL,
    CREATOR_PERSONA,
    ESCALATION_PROTOCOL,
    GREETING_RULES,
    KNOWLEDGE_GOVERNANCE,
    LANGUAGE_PROTOCOL,
    SECURITY_BOUNDARY,
    SYSTEM_INSTRUCTIONS,
    TEAM_PERSONA,
    WORKED_EXAMPLES,
    today_wita_string,  # noqa: F401 — re-exported, same date-injection mechanism as v4
)
from backend.prompts.zantara_core_v4 import (
    INTERNAL_MONOLOGUE as _INTERNAL_MONOLOGUE_V4,
)
from backend.prompts.zantara_core_v4 import (
    TOOL_USAGE_POLICY as _TOOL_USAGE_POLICY_V4,
)

# ---------------------------------------------------------------------------
# STEP 1 — mechanically split TOOL_USAGE_POLICY (v4) into its audience-neutral
# body and its team/creator-only CRM capability block. Both halves are SLICES
# of the imported v4 string (never retyped), so fidelity to v4 is structural,
# not a matter of careful transcription.
# ---------------------------------------------------------------------------

_CRM_SECTION_MARKER = "**📊 CRM DATABASE (crm_query) — LIVE CLIENT DATA**"
_TOOL_USAGE_POLICY_CLOSE_TAG = "</tool_usage_policy>"

_crm_start = _TOOL_USAGE_POLICY_V4.index(_CRM_SECTION_MARKER)
_crm_close = _TOOL_USAGE_POLICY_V4.index(_TOOL_USAGE_POLICY_CLOSE_TAG, _crm_start)

# The CRM playbook, exactly as v4 wrote it (no wrapping tag of its own in
# v4 either — it was markdown prose inside the parent <tool_usage_policy>
# tag). Team/creator capability only — this is the C20 fix.
CRM_CAPABILITY_BLOCK: str = _TOOL_USAGE_POLICY_V4[_crm_start:_crm_close].rstrip()

_tool_usage_policy_head = _TOOL_USAGE_POLICY_V4[:_crm_start].rstrip()


# ---------------------------------------------------------------------------
# STEP 2 — neutralize the 7 "a/the client" third-person-interlocutor phrases
# in the shared (audience-neutral) body. C19: "a client asks…", "the client
# describing…" — wording the model would say while ALREADY talking to that
# very client. Every entry is a discourse-person edit (who is being referred
# to), NEVER a fact edit — no regulation name/date/KBLI code/URL/price is
# touched. `_apply_neutralizations` asserts each old substring occurs
# EXACTLY ONCE before replacing it, so any future v4 edit that moves or
# rewords this text fails loudly here instead of silently desyncing v5.
# ---------------------------------------------------------------------------

REFERENT_NEUTRALIZATIONS: tuple[tuple[str, str], ...] = (
    (
        "do NOT assume which one applies to a client without asking:**",
        "do NOT assume which one applies without asking first:**",
    ),
    (
        "BPS correspondence table. The client did not need to do anything, and most companies are",
        "BPS correspondence table. Nothing needed to be done in that case, and most companies are",
    ),
    (
        "the 2020→2025 transition moved the\n     client's registered activity to a different risk level",
        "the 2020→2025 transition moved the\n     registered activity to a different risk level",
    ),
    (
        "**When a client asks about their KBLI migration status**: ask what their current NIB/OSS",
        "**When asked about KBLI migration status**: ask what the current NIB/OSS",
    ),
    (
        "without the client describing their situation",
        "without them describing their situation",
    ),
    (
        'If a client asks "55193 or 55203?", answer',
        'If asked "55193 or 55203?", answer',
    ),
)

# INTERNAL_MONOLOGUE's recall-check lists example TRIGGER PHRASES a caller
# might say — "the client we discussed" only makes sense from a team member
# talking about a third party, and reads as self-referential nonsense (or,
# worse, a third-person leak) if the interlocutor IS that client. Same
# discourse-person fix, same verification discipline.
INTERNAL_MONOLOGUE_NEUTRALIZATION: tuple[str, str] = (
    '"the client we discussed"',
    '"the case we discussed"',
)


def _apply_neutralizations(text: str, replacements: tuple[tuple[str, str], ...]) -> str:
    """Apply each (old, new) substring replacement exactly once, or raise.

    Fail LOUD (not silently no-op) if a v4 edit ever moves/rewords one of
    these phrases out from under us — a stale replacement is worse than no
    replacement, because it would look like the C19 fix still applies when
    it has quietly stopped covering the real text.
    """
    result = text
    for old, new in replacements:
        occurrences = result.count(old)
        if occurrences != 1:
            raise ValueError(
                f"Expected exactly 1 occurrence of {old!r} in the v4 source "
                f"this rewrite depends on, found {occurrences}. The referent "
                "neutralization in zantara_core_v5.py has desynced from "
                "zantara_core_v4.py — re-derive the replacement before "
                "trusting this module."
            )
        result = result.replace(old, new, 1)
    return result


_TOOL_USAGE_POLICY_CORE: str = (
    _apply_neutralizations(_tool_usage_policy_head, REFERENT_NEUTRALIZATIONS)
    + "\n"
    + _TOOL_USAGE_POLICY_CLOSE_TAG
)

INTERNAL_MONOLOGUE: str = _apply_neutralizations(
    _INTERNAL_MONOLOGUE_V4, (INTERNAL_MONOLOGUE_NEUTRALIZATION,)
)


# ---------------------------------------------------------------------------
# CORE_FACTUAL — audience-neutral. Everything true regardless of who asks:
# grounding + citation rules, the abstain/escalation behavioural contract,
# KBLI/visa/tax domain guidance (TOOL_USAGE_POLICY minus CRM), the
# PricingTool-only rule, {today_wita}, and the worked examples. Same runtime
# placeholder mechanism as v1-v4 ({today_wita}/{user_memory}/{rag_results}/
# {query}, filled by prompt_builder.py's `_safe_template_fill` via plain
# substring replacement — NOT `.format()`, for the same reason documented
# there: WORKED_EXAMPLES embeds illustrative JSON braces).
# ---------------------------------------------------------------------------

CORE_FACTUAL: str = f"""\
<date_context>
Today's date: {{today_wita}}
</date_context>

{SECURITY_BOUNDARY}

{_TOOL_USAGE_POLICY_CORE}

{SYSTEM_INSTRUCTIONS}

{KNOWLEDGE_GOVERNANCE}

{LANGUAGE_PROTOCOL}

{GREETING_RULES}

{CITATION_RULES}

{ESCALATION_PROTOCOL}

{CRASH_PROTOCOL}

{CLOSING_PHRASES}

{WORKED_EXAMPLES}

<user_memory>
{{user_memory}}
</user_memory>

<verified_data>
{{rag_results}}
</verified_data>

<query_context>
User Query: {{query}}
</query_context>

{INTERNAL_MONOLOGUE}"""


# ---------------------------------------------------------------------------
# AUDIENCE_VOICE — who you're talking to and how you address them.
# ---------------------------------------------------------------------------

AUDIENCE_VOICE_CLIENT: str = """\
### IDENTITY: ZANTARA (CLIENT MODE)
**You are talking directly to a Bali Zero client or prospect.**
You are their AI consultant at Bali Zero — the person they are chatting with
right now, not a colleague describing their case to someone else.

**RELATIONSHIP:**
- You are their point of contact for visas, PT PMA, tax, and legal matters in
  Indonesia.
- Speak to THEM, in the second person ("you", "your case"). Never refer to
  the person you are answering in the third person, and never phrase an
  answer as something to be relayed or passed along to them by somebody
  else — they ARE the one reading this.
- Never reveal that Zantara operates in other modes for team members or the
  founder, and never mention internal tools, the CRM, or colleagues by name.

**OPERATIONAL PROTOCOLS:**
1.  **ANSWER THEM DIRECTLY:** Give the answer now, to them, in this message —
    do not describe what a customer in their situation "would be told."
2.  **NO INTERNAL PROCESS NARRATION:** Never narrate internal steps out loud
    ("let me check our database", "I'll run a query"). Just answer, or say
    the case needs verification with the team.
3.  **ESCALATION IS HUMAN-TO-HUMAN:** When a case needs a human, say a Bali
    Zero specialist will follow up with them directly (via WhatsApp/email).
4.  **SALES-AWARE BUT HONEST:** You can mention relevant Bali Zero services,
    but only real prices from the pricing tool — never invented figures.

**TONE:**
- Warm, professional, reassuring. Second person throughout.
- No engineering jargon, no internal architecture, no mention of other
  Zantara modes or audiences."""

AUDIENCE_VOICE_TEAM: str = TEAM_PERSONA

AUDIENCE_VOICE_CREATOR: str = CREATOR_PERSONA


# ---------------------------------------------------------------------------
# CAPABILITY_BLOCK — tool playbooks. Team/creator only; client is empty by
# construction (the C20 fix: no anonymous caller's prompt should teach the
# model to call a tool the security tourniquet will then deny).
# ---------------------------------------------------------------------------

CAPABILITY_BLOCK_CLIENT: str = ""
CAPABILITY_BLOCK_TEAM: str = CRM_CAPABILITY_BLOCK
CAPABILITY_BLOCK_CREATOR: str = CRM_CAPABILITY_BLOCK


_AUDIENCE_VOICE: dict[str, str] = {
    "client": AUDIENCE_VOICE_CLIENT,
    "team": AUDIENCE_VOICE_TEAM,
    "creator": AUDIENCE_VOICE_CREATOR,
}

_CAPABILITY_BLOCK: dict[str, str] = {
    "client": CAPABILITY_BLOCK_CLIENT,
    "team": CAPABILITY_BLOCK_TEAM,
    "creator": CAPABILITY_BLOCK_CREATOR,
}

VALID_AUDIENCES: tuple[str, ...] = ("client", "team", "creator")


def build_master_template(audience: str) -> str:
    """Compose the v5 system-prompt template for one audience.

    SYSTEM = CORE_FACTUAL + AUDIENCE_VOICE[audience] + CAPABILITY_BLOCK[audience]

    (CHANNEL_OVERLAY — e.g. WhatsApp's plain-text/short-form stripping — is
    applied separately by prompt_builder.py, exactly as it already is for
    v1-v4; this function only builds the audience-composed master template
    those overlays get applied to.)

    Args:
        audience: One of "client" / "team" / "creator". Any other value
            (unset, unknown, typo) is treated as "client" — fail SAFE
            toward the audience with the fewest capabilities and the most
            locked-down voice. This mirrors today's default behaviour
            (prompt_builder.py: "client / unknown: nothing prepended,
            nothing removed" — client IS the default case).

    Returns:
        The composed template string, still containing the runtime
        placeholders {today_wita}/{user_memory}/{rag_results}/{query} for
        the caller to fill (same mechanism as v1-v4's ZANTARA_MASTER_TEMPLATE
        — plain substring replacement, not str.format()).
    """
    key = audience if audience in _AUDIENCE_VOICE else "client"
    voice = _AUDIENCE_VOICE[key]
    capability = _CAPABILITY_BLOCK[key]

    sections = [
        f"\n# ZANTARA V6 SYSTEM PROMPT (v5 — audience-composed: {key})\n",
        CORE_FACTUAL,
        voice,
    ]
    if capability:
        sections.append(f"<team_capabilities>\n{capability}\n</team_capabilities>")

    return "\n\n".join(sections)
