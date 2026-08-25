"""compose_reply — the PRIMARY control for the gc-015 defect class. Read
``loop/claim_gate.py``'s "STATUS CHANGE" section first: that module is now
defense-in-depth ONLY, because a detector over free text is structurally a
weaker reading of "a reply that claims an action occurred must be derived
from what actually executed" no matter how wide its pattern inventory grows.

This module is the alternative: a CONSTRUCTION that cannot lie, rather than
a detector that tries to catch every way it might. In the action domain
(``TurnIntent.MUTATION``), the model's free-text ``content`` is never the
reply — it is either replaced outright by a template rendered from a
structured outcome (``outcomes.py``), or, if nothing structured exists to
template from at all, replaced by a fixed, server-authored fallback
sentence. There is no code path in the mutation branch that returns
``model_content`` as-is; that is what makes the lie unconstructible instead
of merely undetected.

``TurnIntent`` — CONSUMPTION CONTRACT for F4's not-yet-built deterministic
intent router (Kimi FM2). This module is written and tested against the
contract below; nothing in this repo currently PRODUCES a ``TurnIntent`` for
a live turn (F4's router is not built — same stub-shape as F7's
``principal_id`` in ``models.py`` and F9's ``leader_epoch`` in ``store.py``:
a field this unit consumes, not generates). Wiring a live caller into this
module is out of scope here; this is the contract that caller must satisfy.

``ReadChainOutcome`` — the 4th template (orchestrator ruling, directive #1
§2 follow-up, same day): the gap flagged when ``loop/turn_plan.py`` and
``loop/loop_detector.py`` were built. Before this, a read/search chain that
ended WITHOUT the model ever reaching a ``FinalAnswer`` or proposing a
mutation — because ``turn_plan.try_append_read_step`` returned
``ReadStepOutcome.BUDGET_EXHAUSTED``, or ``loop_detector.detect_stuck_loop``
returned ``stuck=True`` — fell through to ``TurnIntent.READ_OR_NONE`` with
``model_content=None``, landing on the generic ``_CLAIM_GATE_BLOCKED_
FALLBACK`` template. That template is worded for a DIFFERENT fact (an
``ActionClaimGate`` BLOCK — "I want to make sure I get this right") and
reports the wrong reason for what actually happened. The orchestrator's
ruling, verbatim: "Falling through to `_CLAIM_GATE_BLOCKED_FALLBACK` means
telling a team member 'blocked' when the truth is 'I ran out of steps'.
Those are different facts and the person acts differently on each: one
means *the tool refused you*, the other means *ask me again more
narrowly*." This whole mandate has been an argument against systems that
report the wrong reason for what happened; this closes that defect in the
one place a human actually reads it. Deliberately a NEW, purpose-built,
two-member contract type owned by THIS module — mirroring ``TurnIntent``'s
own "consumption contract, not yet produced by a live caller" status —
rather than importing ``loop.turn_plan.ReadStepOutcome`` directly, because
that enum's third member (``APPENDED``) has no meaning here at all: a
chain that appended successfully never reaches ``compose_reply`` in the
first place, so a contract scoped to exactly the two terminal, unresolved
reasons is more honest than reusing a producer-side enum with an
unreachable branch this module would have to guard against.

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from team_bot.loop.claim_gate import ActionClaimGate, ActionClaimVerdict
from team_bot.loop.execution_record import ExecutionRecord
from team_bot.loop.tool_decision import ToolDecision

from .models import PendingAction
from .outcomes import DEFAULT_LOCALE, ConfirmationOutcome, Locale, render_outcome

__all__ = ["ComposedReply", "ReadChainOutcome", "TurnIntent", "compose_reply"]


class TurnIntent(StrEnum):
    """F4's (not-yet-built) deterministic router's classification of THIS
    turn — the contract this module consumes. See module docstring: no live
    producer exists yet."""

    MUTATION = "mutation"  # this turn is proposing/confirming/executing/cancelling a tool
    READ_OR_NONE = "read_or_none"  # a lookup, a question, small talk, or an abstention


class ReadChainOutcome(StrEnum):
    """Why a read/search chain ended WITHOUT the model ever reaching a
    ``FinalAnswer`` or proposing a mutation this turn. See module
    docstring's "4th template" section for why this is a fresh, narrow
    contract rather than a re-import of ``loop.turn_plan.ReadStepOutcome``.
    """

    BUDGET_EXHAUSTED = "budget_exhausted"  # loop.turn_plan.ReadStepOutcome.BUDGET_EXHAUSTED
    STUCK_LOOP = "stuck_loop"  # loop.loop_detector.detect_stuck_loop(...).stuck is True


# The one FIXED, server-authored, localized sentence used when
# TurnIntent.MUTATION is true but there is nothing structured to template
# from at all (gc-015's exact shape: no confirmation_outcome, no
# execution_record — the model narrated a mutation that never touched F6).
# Never model content, never formatted with any model-supplied value.
_NOTHING_STRUCTURED_FALLBACK: dict[Locale, str] = {
    Locale.EN: "I wasn't able to complete that automatically — could you confirm the request again?",
    Locale.IT: "Non sono riuscito a completarlo automaticamente — puoi confermare di nuovo la richiesta?",
    Locale.ID: "Saya belum bisa menyelesaikannya secara otomatis — bisakah Anda mengonfirmasi permintaan lagi?",
}

# The generic clarifying template used when TurnIntent.READ_OR_NONE's
# model_content is itself BLOCKed by ActionClaimGate as a last-resort net
# (see compose_reply's branch 3). Same status as the fallback above: fixed,
# server-authored, never model content.
_CLAIM_GATE_BLOCKED_FALLBACK: dict[Locale, str] = {
    Locale.EN: "I want to make sure I get this right — could you tell me a bit more about what you need?",
    Locale.IT: "Voglio essere sicuro di aver capito bene — puoi darmi qualche dettaglio in più su cosa ti serve?",
    Locale.ID: "Saya ingin memastikan saya memahami dengan benar — bisakah Anda memberi sedikit detail lagi tentang apa yang Anda butuhkan?",
}

# The 4th template (see module docstring). Deliberately DISTINCT text per
# ReadChainOutcome member, not one generic sentence shared by both — this
# fix exists precisely to stop collapsing different true causes into one
# reported reason, so it must not repeat that exact mistake at a smaller
# scale by merging its own two causes back together.
_READ_CHAIN_UNRESOLVED_TEMPLATES: dict[ReadChainOutcome, dict[Locale, str]] = {
    ReadChainOutcome.BUDGET_EXHAUSTED: {
        Locale.EN: (
            "I searched but couldn't finish within my usual number of steps — could you "
            "narrow the request (e.g. a specific client or practice ID)?"
        ),
        Locale.IT: (
            "Ho cercato ma non sono riuscito a concludere entro il numero di passaggi "
            "consentito — puoi restringere la richiesta (es. un ID cliente o pratica specifico)?"
        ),
        Locale.ID: (
            "Saya sudah mencari tetapi belum selesai dalam jumlah langkah yang biasa — "
            "bisakah Anda mempersempit permintaan (mis. ID klien atau praktik tertentu)?"
        ),
    },
    ReadChainOutcome.STUCK_LOOP: {
        Locale.EN: (
            "I seem to be repeating the same search without making progress — could you "
            "rephrase or narrow the request?"
        ),
        Locale.IT: (
            "Sembra che stia ripetendo la stessa ricerca senza fare progressi — puoi "
            "riformulare o restringere la richiesta?"
        ),
        Locale.ID: (
            "Sepertinya saya mengulangi pencarian yang sama tanpa kemajuan — bisakah Anda "
            "mengubah kata-kata atau mempersempit permintaan?"
        ),
    },
}


class ComposedReply(BaseModel):
    """What ``compose_reply`` returns. ``source`` names WHERE ``text`` came
    from — the field the gc-015 regression test asserts on, since the bug
    class this module closes is precisely "the reply's source was
    unaccountably the model's own free text in the action domain"."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    source: Literal["template", "fallback", "model_content"]


def compose_reply(
    *,
    turn_intent: TurnIntent,
    model_content: str | None,
    confirmation_outcome: ConfirmationOutcome | None,
    action: PendingAction | None,
    execution_record: ExecutionRecord | None = None,
    tool_decision: ToolDecision | None = None,
    read_chain_outcome: ReadChainOutcome | None = None,
    locale: Locale = DEFAULT_LOCALE,
) -> ComposedReply:
    """Decide what the staff member actually sees this turn.

    Branch order matters and is exhaustive:

    1. ``confirmation_outcome`` provided -> render it from
       ``outcomes.render_outcome`` (``source="template"``). This is F6's own
       state machine reporting what just happened (propose/confirm/execute/
       cancel) — the strongest possible grounding, so it always wins
       regardless of ``turn_intent`` or what the model said.
    2. Else, ``read_chain_outcome`` provided -> render the matching 4th
       template (``source="template"``, see module docstring). This is a
       DEFINITIVE, structurally-known termination reason — the loop itself
       stopped the chain, independent of anything ``model_content`` says —
       so it wins over branches 3/4 the same way an ``execution_record``
       wins in branch 3. Raises ``ValueError`` if paired with
       ``TurnIntent.MUTATION``: a chain that ended via budget exhaustion or
       a stuck-loop verdict never reached a mutation proposal this turn by
       construction, so that combination is a caller contract violation,
       not a real turn shape to render text for.
    3. Else, ``turn_intent == TurnIntent.MUTATION`` -> the reply is ALWAYS
       composed from structure, NEVER from ``model_content``:
       - ``execution_record`` present -> a short grounded sentence stating
         success or failure, built from the record's own ``ok`` field
         (``source="template"``).
       - Nothing structured at all (no outcome, no record — gc-015's exact
         shape) -> the fixed fallback sentence (``source="fallback"``).
    4. Else (``TurnIntent.READ_OR_NONE``) -> ``model_content`` is the reply,
       but only after passing ``ActionClaimGate`` as a last-resort net
       (``source="model_content"`` on ALLOW). On BLOCK, fall back to the
       generic clarifying template (``source="fallback"``) — this is the one
       place this module still depends on the (deliberately imperfect,
       defense-in-depth-only) text detector, for exactly the case
       ``claim_gate.py``'s docstring names as its remaining job: a turn the
       upstream router misclassified as READ_OR_NONE when it should have
       been MUTATION.

    ``tool_decision`` is required only for branch 4's ``ActionClaimGate``
    call (that gate's own signature needs it to phrase its BLOCK reason) —
    branches 1, 2, and 3 never touch it.
    """
    if confirmation_outcome is not None:
        return ComposedReply(
            text=render_outcome(confirmation_outcome, action, locale), source="template"
        )

    if read_chain_outcome is not None:
        if turn_intent == TurnIntent.MUTATION:
            raise ValueError(
                "read_chain_outcome and TurnIntent.MUTATION are contradictory — a chain that "
                "ended via budget exhaustion or a stuck-loop verdict never proposed a "
                "mutation this turn"
            )
        return ComposedReply(
            text=_READ_CHAIN_UNRESOLVED_TEMPLATES[read_chain_outcome][locale], source="template"
        )

    if turn_intent == TurnIntent.MUTATION:
        if execution_record is not None:
            return ComposedReply(text=_render_execution_record(execution_record, locale), source="template")
        return ComposedReply(text=_NOTHING_STRUCTURED_FALLBACK[locale], source="fallback")

    # TurnIntent.READ_OR_NONE
    if model_content is None:
        return ComposedReply(text=_CLAIM_GATE_BLOCKED_FALLBACK[locale], source="fallback")

    if tool_decision is None:
        raise ValueError("tool_decision is required for TurnIntent.READ_OR_NONE (ActionClaimGate needs it)")

    verdict = ActionClaimGate.evaluate(
        model_content, tool_decision=tool_decision, execution_record=execution_record
    )
    if verdict.verdict == ActionClaimVerdict.BLOCK:
        return ComposedReply(text=_CLAIM_GATE_BLOCKED_FALLBACK[locale], source="fallback")

    return ComposedReply(text=model_content, source="model_content")


# EN-only by design: this sentence is built from an ExecutionRecord alone
# (tool_name + ok), independent of any PendingAction/outcome — MUTATION
# turns whose execution happened outside F6's PendingAction flow (an R1
# direct tool call, ExecutionSource.DIRECT_R1) have no ConfirmationOutcome
# to render from outcomes.py at all, so this is the one server-authored
# template in this module that lives outside that file. Localized the same
# way as everything else in this module — not left to the model.
_EXECUTION_RECORD_TEMPLATES: dict[bool, dict[Locale, str]] = {
    True: {
        Locale.EN: "Done — {tool} completed.",
        Locale.IT: "Fatto — {tool} completato.",
        Locale.ID: "Selesai — {tool} telah diselesaikan.",
    },
    False: {
        Locale.EN: "That didn't complete — {tool} failed. Could you confirm the request again?",
        Locale.IT: "Non è andato a buon fine — {tool} ha fallito. Puoi confermare di nuovo la richiesta?",
        Locale.ID: "Itu tidak berhasil — {tool} gagal. Bisakah Anda mengonfirmasi permintaan lagi?",
    },
}


def _render_execution_record(record: ExecutionRecord, locale: Locale) -> str:
    return _EXECUTION_RECORD_TEMPLATES[record.ok][locale].format(tool=record.tool_name)
