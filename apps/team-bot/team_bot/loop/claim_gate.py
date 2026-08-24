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

ROUND 2 (B6c adversarial-fixture run, same day, relayed by the orchestrator
with independent reproduction before forwarding): 21/26 false ALLOWs
against 63 fixtures. Three distinct, orthogonal defects, all in the
Italian inventory — fixed here, defense-in-depth scope unchanged:

- **F1 — gender/number agreement, half-implemented.** The auxiliary
  charclass already accepted feminine (``stat[oa]``/``stat[ie]``); the
  PARTICIPLE charclass did not (``aggiornat[oi]`` has no ``-a``/``-e``).
  ``pratica`` — the CRM's central object — is grammatically feminine, so
  "la pratica è stata aggiornata" was invisible while "il documento è
  stato aggiornato" (identical construction, masculine) was caught. Fixed
  by completing the alternation to all four endings (o/a/i/e) via a SINGLE
  shared stem list (``_IT_PARTICIPLE_STEMS``) reused by both the passive
  and the "ho/abbiamo" active pattern — the defect was exactly these two
  patterns carrying the same vocabulary independently and drifting out of
  sync; a shared fragment makes that drift structurally harder to
  reintroduce, not just patched once.
- **F2 — ASCII apostrophe.** The passive pattern required the literal
  ``è``; the ordinary mobile-keyboard substitution ``e'`` (no accented
  key) defeated it regardless of gender. Folded in ``_normalize`` —
  narrowly, only a standalone ``e'`` token, since that substitution is
  never anything other than "è" in practice.
- **F3 — negation-blindness (false BLOCK direction, fixed after F1/F2 per
  instruction, not skipped).** ``.search()`` matches "ho aggiornato"
  inside "non ho aggiornato" just as readily as inside a genuine claim.
  A bot that cannot say "I did not manage to update it" without being
  blocked has lost the ability to report its own failures. Fixed with a
  bounded look-back over the words immediately preceding a match (see
  ``_preceded_by_negation``) — not a lookbehind (Python's ``re`` lookbehind
  is fixed-width only; these negators vary in length across three
  languages) and not an unbounded scan (which would wrongly swallow a
  genuine claim followed by an unrelated "not" clause later in the same
  sentence).

Explicitly NOT done: extending the charclass fix "reflexively" beyond what
row-by-row verification supports. All eight IT participle stems in this
list were checked individually against the o/a/i/e alternation before
widening (none are irregular beyond ``apert-``, which still follows the
same four-way pattern) — this is a verified grammatical completion, not a
blind charclass expansion. B6c's fixtures (feminine guilty cases,
masculine controls, the apostrophe case, and the three negation cases) are
added as permanent regression tests so a later edit that breaks agreement,
folding, or the negation guard goes red.

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


_ASCII_E_GRAVE = re.compile(r"\be'(?=\s|$|[.,;:!?])", re.IGNORECASE)


def _normalize(text: str) -> str:
    """NFKC-normalize and fold the handful of Unicode/ASCII punctuation
    substitutions a phone keyboard actually produces (curly
    apostrophes/quotes, en/em dashes, and — B6c F2 — the missing-accented-
    key substitution "e'" for "è") to what the existing patterns were
    always meant to match. This is hygiene, not widening — it makes
    EXISTING patterns match what they were always meant to match, rather
    than adding new phrasings to catch. The "e'" -> "è" fold is narrowly
    scoped to a standalone token (word boundary before "e", apostrophe
    immediately after, then whitespace/punctuation/end) because that
    substitution is never anything else in Italian text — it is not a
    general "any e followed by an apostrophe" rule."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = (
        normalized.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )
    return _ASCII_E_GRAVE.sub("è", normalized)


# Exact-match (not a substring search) — an emoji-only reply asserting
# completion with nothing executed is as much a claim as any sentence.
_COMPLETION_ONLY_EMOJI = frozenset({"✅", "✔️", "✔", "👍", "☑️", "☑"})

# Shared IT past-participle stems — used by BOTH the passive ("è stato
# aggiornato") and active ("ho aggiornato") patterns below. Defined ONCE
# and reused, deliberately: B6c's F1 finding was exactly these two patterns
# carrying the same eight-verb vocabulary independently, and one of the two
# copies drifting to masculine-only endings while the other did not. All
# eight are regular in the o/a/i/e (m.sg/f.sg/m.pl/f.pl) alternation —
# checked individually, not assumed — including "apert-" (aprire's
# irregular stem, but still a regular o/a/i/e alternation from that stem).
_IT_PARTICIPLE_STEMS: tuple[str, ...] = (
    "creat",
    "aggiornat",
    "segnat",
    "modificat",
    "apert",
    "programmat",
    "registrat",
    "cancellat",
)
_IT_PARTICIPLE_ALTERNATION = "|".join(f"{stem}[oaie]" for stem in _IT_PARTICIPLE_STEMS)

# Closed, reviewed inventory. DELIBERATELY NOT exhaustive — see the module
# docstring's STATUS CHANGE section: this is defense-in-depth, and chasing
# every natural rephrasing is the anti-pattern the orchestrator ruled
# against. Modest widening applied here (bare past tense with an explicit
# subject, plural EN/IT forms, an informal ID contraction, and — B6c round
# 2 — completed IT gender/number agreement) closes the clearest,
# lowest-risk gaps found so far; it does not attempt every remaining one.
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
        # IT — "è stato/a <participio>" (singular) / "sono stati/e <participio>"
        # (plural) — participle now agrees in gender/number (B6c F1).
        rf"\b(?:è\s+stat[oa]|sono\s+stat[ie])\s+(?:{_IT_PARTICIPLE_ALTERNATION})\b",
        # IT — "ho/abbiamo <verbo>" — same stem/agreement fragment as above,
        # not a second independently-maintained copy (B6c F1's root cause).
        rf"\b(?:ho|abbiamo)\s+(?:{_IT_PARTICIPLE_ALTERNATION})\b",
        # ID — "sudah/telah/udah <verb>" (udah = informal contraction of sudah)
        r"\b(?:sudah|telah|udah)\s+(?:dibuat|diperbarui|ditandai|diubah|dibuka|"
        r"dijadwalkan|dicatat|dibatalkan)\b",
        # ID — "berhasil <verb>"
        r"\bberhasil\s+(?:dibuat|diperbarui|ditandai|diubah|dibuka|dijadwalkan|dicatat)\b",
    )
)


# B6c F3: negation-blindness. A bounded look-back over the words IMMEDIATELY
# preceding a match — not a lookbehind (Python's `re` lookbehind is
# fixed-width only; these negators vary in length across three languages)
# and not an unbounded "contains a negator anywhere" scan (which would
# wrongly swallow a genuine claim followed by an unrelated "not" clause
# later in the same sentence, e.g. "I've created the reminder, not the
# invoice" is still a real claim — its "not" is AFTER the match, outside
# this window by construction).
_NEGATORS = frozenset({"not", "never", "non", "tidak", "belum"})
_NEGATION_WINDOW_WORDS = 3


def _preceded_by_negation(text: str, match_start: int) -> bool:
    """``text`` must already be ``_normalize``'d. Checks only the words
    strictly before ``match_start`` — a negator appearing after the match
    never counts."""
    preceding_words = re.findall(r"\S+", text[:match_start])[-_NEGATION_WINDOW_WORDS:]
    for word in preceding_words:
        stripped = word.strip(".,;:!?\"'").lower()
        if stripped in _NEGATORS or stripped.endswith("n't"):
            return True
    return False


def _matches_completion_claim(text: str) -> str | None:
    """Return the FIRST matching pattern's source (for the audit reason), or
    ``None`` if ``text`` makes no completion claim. Operates on the
    normalized form. A match preceded (within a short window) by a negator
    is not a completion claim at all — see ``_preceded_by_negation``."""
    normalized = _normalize(text)
    if normalized.strip() in _COMPLETION_ONLY_EMOJI:
        return "emoji-only completion"
    for pattern in _COMPLETION_CLAIM_PATTERNS:
        match = pattern.search(normalized)
        if match is not None and not _preceded_by_negation(normalized, match.start()):
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
