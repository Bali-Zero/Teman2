"""ActionClaimGate — the team-bot's claim-vs-action check.

Closes gc-015 (B4b empirical finding, both serving stacks — llama.cpp AND
Ollama — 18/24 golden suite): the model returned ZERO ``tool_calls`` and
its ``content`` narrated a completed mutation verbatim: "The reminder for
practice PR-3090 has been successfully created and is scheduled for
**Thursday, August 26, 2026 at 14:00** (UTC+8). Let me know if you need
further adjustments! 📅" (see
``docs/plans/2026-08-25-due-bot-live/evidence/14b-ollama-tmpl-golden.json``,
``.results[14]``). The golden case itself expected a NEW ``create_reminder``
call correcting the date (an Indonesian follow-up "eh maaf, maksudku hari
Kamis ya" arriving after the FIRST reminder had already been created) — the
model instead re-asserted the stale reminder as if the correction had been
applied, with no tool call to back that claim.

Nothing in the frozen architecture catches this shape. F4's ID-provenance
rule ("IDs flow only tool->model, never model->tool unverified") and F6's
"the executor calls the CRM with the STORED payload — post-confirmation
text never touches the arguments" both presuppose a tool call EXISTS to
inspect or a payload EXISTS to render from; here there is neither. Left
alone, the runtime relays prose asserting an action to a staff member while
nothing reached the CRM — silent and plausible, because the CRM is left in
exactly the state it would be in had it never been asked.

Rule (orchestrator brief, 2026-08-25): a reply that claims an action
occurred must be DERIVED from what actually executed this turn, never
authored freely alongside it. This is the team-bot analogue of BOT A's
claim-inventory gate (``client_bot/policy/types.py``'s
``GateReason.UNINVENTORIED_REGULATED_STATEMENT`` /
``UNINVENTORIED_NUMERIC_STATEMENT`` — check 6, "fail closed / ABSTAIN"), and
the natural extension of F6's stored-payload rule to the one case F6 does
not cover: zero proposals, pure narration.

Design — two independent factors, ANDed only in the dangerous quadrant:

1. STRUCTURAL FACT (``execution_ok``, supplied by the caller — never
   inferred from text): did a tool actually execute with
   ``ToolResult.ok=True`` THIS turn? Derived from ``ToolDecision`` +
   the executor's outcome, both typed. This factor alone is not a
   heuristic.
2. CONTENT SIGNAL (``_matches_completion_claim``): does ``reply_text``
   assert, in the past/completed tense, that a mutation already happened?
   A CLOSED, reviewed, word-boundary-anchored phrase inventory across
   EN/IT/ID (F8's three working languages) — never a bare substring match
   (cicatrix-superscar.md family #3: "no guardia senza test di innocenza E
   colpevolezza, su entità/intento mai bare-substring"). Deliberately
   narrow: a false NEGATIVE here just means this defense-in-depth layer
   misses a novel phrasing (no regression versus today, where nothing
   catches gc-015 at all); a false POSITIVE blocks an innocent reply, which
   is what ``test_claim_gate.py``'s innocent-case suite exists to catch.

Verdict: BLOCK only where factor 1 is False AND factor 2 is True — nothing
executed, yet the text claims something did. Every other combination is
ALLOW: a real execution grounds any completion language (factor 1 True); a
reply that makes no completion claim is fine on its own terms (factor 2
False) — a clarifying question, a lookup summary, a proposal awaiting
confirmation ("Sto per aprire ... Confermi?", future tense, per F6's own
worked example), or an abstention are all exactly this shape and must never
be blocked.

This module is READ-ONLY / pure — no CRM call, no state. The caller (the
eventual team-bot loop, out of scope here) owns supplying ``execution_ok``
honestly and deciding what happens on BLOCK (retry, a server-authored
fallback message, escalation) — this gate only refuses to certify the
reply, it never rewrites it (mirrors ``FinalDecision``'s own rule: the gate
"never 'fixes' regulatory facts in free text").

KNOWN LIMITATION, measured via composite adversarial testing (not just each
innocent shape tested in isolation — see memory
``a-weaker-test-agrees-with-itself.md``, whose lesson this module's test
suite applies directly): an INFORMATIONAL reply that legitimately describes
a PRE-EXISTING record in past-participle language — "the passport has
already been marked as received for weeks — did you mean a different
practice?" — trips the same pattern family as a genuine gc-015-style false
claim, because nothing in ``reply_text`` alone distinguishes "this just
happened" from "this has long been true". Two of
``test_claim_gate.py``'s composite cases document this measured, not
theoretical, over-block. It is an ACCEPTED v1 trade-off, not an oversight:
the two failure directions are not symmetric-cost. A false BLOCK on an
innocent lookup costs a retry/fallback message — recoverable, and visible
to the caller as a gate decision it can act on. A false ALLOW on a real
gc-015 relays a silent, plausible lie about CRM state directly to a staff
member, with nothing downstream positioned to catch it. Resolving this
precisely would need the turn's routed INTENT (mutation vs. read — Kimi
FM2's deterministic router) as a third input, which this pure gate
deliberately does not have; flagged as follow-up work for whichever part of
the loop owns that router, not built here.

Author: Claude Sonnet 5 (lane B3 — team-bot tool registry)
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .tool_decision import ToolDecision

__all__ = ["ActionClaimGate", "ActionClaimVerdict", "ClaimGateDecision"]


class ActionClaimVerdict(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


# Closed, reviewed inventory — one entry per (language, mutation-verb
# family). Word-boundary anchored (``\b``); every pattern requires a
# PAST/COMPLETED tense marker so a prospective or confirm-asking sentence
# ("Sto per aprire...", "Vuoi che crei...?", "Shall I mark it as
# received?") never matches — those are exactly the innocent shape this
# gate must not block.
_COMPLETION_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        # EN — "has/have been [successfully] <verb>", "I've <verb>ed",
        # "successfully <verb>ed"
        r"\b(?:has|have)\s+been\s+(?:successfully\s+)?"
        r"(?:created|updated|marked|changed|opened|scheduled|set|recorded|cancelled|removed)\b",
        r"\bI(?:'ve| have)\s+(?:successfully\s+)?"
        r"(?:created|updated|marked|changed|opened|scheduled|set|recorded)\b",
        r"\bsuccessfully\s+(?:created|updated|marked|changed|opened|scheduled|recorded)\b",
        # IT — "è stato/a <participio>", "ho <verbo>"
        r"\bè\s+stat[oa]\s+(?:creat[oa]|aggiornat[oa]|segnat[oa]|modificat[oa]|"
        r"apert[oa]|programmat[oa]|registrat[oa]|cancellat[oa])\b",
        r"\bho\s+(?:creato|aggiornato|segnato|modificato|aperto|programmato|registrato)\b",
        # ID — "sudah/telah <verb>", "berhasil <verb>"
        r"\b(?:sudah|telah)\s+(?:dibuat|diperbarui|ditandai|diubah|dibuka|"
        r"dijadwalkan|dicatat|dibatalkan)\b",
        r"\bberhasil\s+(?:dibuat|diperbarui|ditandai|diubah|dibuka|dijadwalkan|dicatat)\b",
    )
)


def _matches_completion_claim(text: str) -> str | None:
    """Return the FIRST matching pattern's source (for the audit reason), or
    ``None`` if ``text`` makes no completion claim."""
    for pattern in _COMPLETION_CLAIM_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


class ClaimGateDecision(BaseModel):
    """What ``ActionClaimGate.evaluate()`` returns."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: ActionClaimVerdict
    matched_pattern: Annotated[str, Field(max_length=300)] | None = None
    reason: Annotated[str, Field(max_length=300)]


class ActionClaimGate:
    """Stateless. Safe to share across requests — no I/O, no instance state."""

    @staticmethod
    def evaluate(
        reply_text: str,
        *,
        tool_decision: ToolDecision,
        execution_ok: bool,
    ) -> ClaimGateDecision:
        """
        Args:
            reply_text: the text about to be sent to the staff member THIS
                turn — either the decision-turn's own ``raw_content`` (when
                no tool was called; gc-015's exact case) or a later,
                separate final-answer generation (Kimi FM5's "the
                final-answer step is a separate, unconstrained generation
                that only receives structured tool results").
            tool_decision: this turn's parsed ``ToolDecision``. Only its
                ``proposed_a_tool_call`` shape informs the reason string —
                the verdict itself never re-derives ``execution_ok`` from
                it, because deciding to CALL a tool does not mean the call
                SUCCEEDED (denied by RBAC, CRM 4xx/5xx, an expired
                confirmation, ...); the caller must supply that fact.
            execution_ok: True iff a tool call — from this turn's decision,
                or an earlier confirmed proposal being executed now —
                actually completed with ``ToolResult.ok=True`` THIS turn.
                Never inferred here from ``tool_decision`` or from text.
        """
        if execution_ok:
            return ClaimGateDecision(
                verdict=ActionClaimVerdict.ALLOW,
                reason="a tool executed successfully this turn; any completion language is grounded",
            )

        matched = _matches_completion_claim(reply_text)
        if matched is None:
            return ClaimGateDecision(
                verdict=ActionClaimVerdict.ALLOW,
                reason="reply makes no completion claim (question, lookup, proposal, or abstention)",
            )

        if tool_decision.proposed_a_tool_call:
            assert tool_decision.selected_tool is not None  # narrows for mypy/readers
            what_happened = (
                f"proposed tool '{tool_decision.selected_tool.tool_name}' but it did not "
                "execute successfully"
            )
        else:
            what_happened = "proposed NO tool call at all"

        return ClaimGateDecision(
            verdict=ActionClaimVerdict.BLOCK,
            matched_pattern=matched,
            reason=(
                f"reply claims a completed action while the model {what_happened} — "
                "reply is not derived from execution"
            ),
        )
