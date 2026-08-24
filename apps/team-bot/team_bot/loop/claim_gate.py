"""ActionClaimGate — DEFENSE-IN-DEPTH ONLY. The primary control lives in
``confirmation/reply_composer.py::compose_reply`` (see that module's
docstring). This module is downgraded from primary to secondary control by
explicit orchestrator ruling — read the "STATUS CHANGE" section below
before touching either the signature or the pattern inventory.

---

Originally written to close gc-015 (B4b empirical finding, both serving
stacks, 18/24 golden suite): the model returned ZERO tool_calls and its
content narrated a completed mutation ("The reminder ... has been
successfully created ..."). Nothing in F4/F6 catches this shape at the
schema level — both presuppose a tool call or a stored payload exists to
inspect; here there is neither.

STATUS CHANGE (orchestrator ruling, same day, via a fenced cross-family
refuter run against the FIRST version of this module):

The refuter reproduced 16/16 false ALLOWs against realistic rephrasings of
the exact same lie gc-015 told — simple past ("The reminder was created"),
bare declaratives ("Reminder created"), an emoji alone ("✅"), plural forms
("Abbiamo aggiornato", "We have created"), a curly apostrophe defeating
"I've", informal Indonesian ("udah dibuat" vs "sudah dibuat"), and a verb
present in one language's PASSIVE list but absent from the same language's
ACTIVE list ("cancellato"). It caught exactly the ONE string this module's
inventory was built from and missed every natural neighbor of it.

This is memory ``a-weaker-test-agrees-with-itself.md``'s lesson one level
up: composite-testing the INNOCENT side (this module's own prior round)
found a real false BLOCK — good, kept work. But the GUILTY fixtures were
never composite-tested against an adversary, because they were the
phrasings this module's author had in mind while writing the inventory, so
they could not falsify it. Same instrument bias, one layer higher.

The orchestrator's ruling: enumerating natural-language phrasings is an
unbounded arms race — every widening that closes one false ALLOW risks a
new false BLOCK, with no terminating condition. The rule this module was
built to enforce — "a reply that claims an action occurred must be DERIVED
from what actually executed, never authored freely alongside it" — asked
for a CONSTRUCTION that cannot lie, and a detector over free text is
structurally a weaker reading of that rule no matter how wide the
inventory grows.

The fix is `compose_reply` (confirmation/reply_composer.py): when a turn's
ROUTED INTENT is a mutation and nothing executed, the reply is composed
from the STRUCTURED outcome — a template, a re-proposal, or an explicit
"not done" — and never touches the model's `content` at all. Free text
never gets a chance to assert an action in the first place; there is
nothing here to detect because the lie was never constructible.

THIS MODULE'S ROLE NOW: a defense-in-depth net for whatever
`compose_reply` cannot yet cover — most concretely, any turn its
(not-yet-built) upstream intent router misclassifies as
`TurnIntent.READ_OR_NONE` when it should have been `MUTATION`. Its
false-negative rate (documented, deliberately not chased to zero — widening
it further is the anti-pattern this ruling names) is NO LONGER load-bearing
on its own; it is one more layer behind the structural fix, not the thing
standing between a model's prose and a staff member.

``execution_ok: bool`` is GONE. The refuter's second finding: an
unvalidated ``bool`` parameter on a plain function is not runtime-checked
by Python — passing the STRING ``"false"`` is truthy and silently ALLOWed.
Replaced with ``execution_record: ExecutionRecord | None`` (see
``loop/execution_record.py``): either a REAL, typed record constructed by
the one place execution actually happens, or ``None``. There is no
truthy/falsy string left to smuggle through — the type itself is the fix.

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .execution_record import ExecutionRecord
from .tool_decision import ToolDecision

__all__ = ["ActionClaimGate", "ActionClaimVerdict", "ClaimGateDecision"]


class ActionClaimVerdict(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


def _normalize(text: str) -> str:
    """NFKC-normalize and fold the handful of Unicode punctuation variants
    a phone keyboard actually produces (curly apostrophes/quotes, en/em
    dashes) to their ASCII equivalents before matching. This is hygiene,
    not widening — it makes the EXISTING patterns match what they were
    always meant to match, rather than adding new phrasings to catch."""
    normalized = unicodedata.normalize("NFKC", text)
    return (
        normalized.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )


# Exact-match (not a substring search) — an emoji-only reply asserting
# completion with nothing executed is as much a claim as any sentence.
_COMPLETION_ONLY_EMOJI = frozenset({"✅", "✔️", "✔", "👍", "☑️", "☑"})

# Closed, reviewed inventory. DELIBERATELY NOT exhaustive — see the module
# docstring's STATUS CHANGE section: this is defense-in-depth, and chasing
# every natural rephrasing is the anti-pattern the orchestrator ruled
# against. Modest widening applied here (bare past tense with an explicit
# subject, plural EN/IT forms, an informal ID contraction) closes the
# clearest, lowest-risk gaps the refuter found; it does not attempt the
# other twelve.
_COMPLETION_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        # EN — "has/have been [successfully] <verb>"
        r"\b(?:has|have)\s+been\s+(?:successfully\s+)?"
        r"(?:created|updated|marked|changed|opened|scheduled|set|recorded|cancelled|removed)\b",
        # EN — "I've/I have/we've/we have <verb>ed" (active voice with an
        # explicit subject pronoun — covers both the contraction and the
        # full auxiliary, and both singular and plural subjects).
        r"\b(?:I|we)(?:'ve| have)\s+(?:successfully\s+)?"
        r"(?:created|updated|marked|changed|opened|scheduled|set|recorded|cancelled)\b",
        # EN — "successfully <verb>ed"
        r"\bsuccessfully\s+(?:created|updated|marked|changed|opened|scheduled|recorded)\b",
        # EN — bare simple past with an explicit subject pronoun, no
        # auxiliary: "I created", "we marked" — NOT a bare "X was created"
        # (that composite shape is the documented, accepted false-block
        # trade-off from the prior round; requiring the subject pronoun
        # keeps this addition narrow rather than reopening that over-block).
        r"\b(?:I|we)\s+(?:created|updated|marked|changed|opened|scheduled|set|recorded|cancelled)\b",
        # IT — "è stato/a <participio>" (singular) / "sono stati/e <participio>" (plural)
        r"\b(?:è\s+stat[oa]|sono\s+stat[ie])\s+(?:creat[oi]|aggiornat[oi]|segnat[oi]|"
        r"modificat[oi]|apert[oi]|programmat[oi]|registrat[oi]|cancellat[oi])\b",
        # IT — "ho/abbiamo <verbo>"
        r"\b(?:ho|abbiamo)\s+(?:creato|aggiornato|segnato|modificato|aperto|programmato|"
        r"registrato|cancellato)\b",
        # ID — "sudah/telah/udah <verb>" (udah = informal contraction of sudah)
        r"\b(?:sudah|telah|udah)\s+(?:dibuat|diperbarui|ditandai|diubah|dibuka|"
        r"dijadwalkan|dicatat|dibatalkan)\b",
        # ID — "berhasil <verb>"
        r"\bberhasil\s+(?:dibuat|diperbarui|ditandai|diubah|dibuka|dijadwalkan|dicatat)\b",
    )
)


def _matches_completion_claim(text: str) -> str | None:
    """Return the FIRST matching pattern's source (for the audit reason), or
    ``None`` if ``text`` makes no completion claim. Operates on the
    normalized form."""
    normalized = _normalize(text)
    if normalized.strip() in _COMPLETION_ONLY_EMOJI:
        return "emoji-only completion"
    for pattern in _COMPLETION_CLAIM_PATTERNS:
        if pattern.search(normalized):
            return pattern.pattern
    return None


class ClaimGateDecision(BaseModel):
    """What ``ActionClaimGate.evaluate()`` returns."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: ActionClaimVerdict
    matched_pattern: Annotated[str, Field(max_length=300)] | None = None
    reason: Annotated[str, Field(max_length=300)]


class ActionClaimGate:
    """Stateless. Safe to share across requests — no I/O, no instance state.

    DEFENSE-IN-DEPTH ONLY — see module docstring. Callers that can supply an
    upstream ``TurnIntent`` classification should prefer
    ``confirmation/reply_composer.py::compose_reply``, which never lets
    ``reply_text`` reach the user unfiltered in the action domain at all.
    This class exists for the path that classification does not (yet, or
    ever) cover.
    """

    @staticmethod
    def evaluate(
        reply_text: str,
        *,
        tool_decision: ToolDecision,
        execution_record: ExecutionRecord | None,
    ) -> ClaimGateDecision:
        """
        Args:
            reply_text: the text about to be sent to the staff member THIS
                turn.
            tool_decision: this turn's parsed ``ToolDecision``. Only its
                ``proposed_a_tool_call`` shape informs the reason string —
                the verdict never re-derives groundedness from it.
            execution_record: proof (see ``loop/execution_record.py``) that
                a tool executed THIS turn with ``ok=True``, or ``None`` if
                nothing did. There is no bare bool left to accept here —
                the refuter's finding that a truthy string could silently
                ALLOW is closed by construction, not by validation.
        """
        if execution_record is not None and execution_record.ok:
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
