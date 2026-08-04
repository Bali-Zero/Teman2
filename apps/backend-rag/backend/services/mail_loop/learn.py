"""The learning half: diff our draft against what Zero actually sent.

Zero chose not to archive mail on our side, which removes the obvious training
corpus. The substitute is the Sent folder: on the next run we look for the reply
that actually went out, compare it to the draft we had proposed, and keep the
DIFFERENCE as a lesson. The mail itself is never stored.

Two deliberate design choices:

  1. The signals are computed LOCALLY and deterministically (opening line
     changed, hedging added, an amount removed, length delta, sign-off). No mail
     body is shipped anywhere to produce them, and they are unit-testable
     without a mailbox or an LLM.

  2. Only the SIGNALS — never the client's words — become a lesson. A signal is
     a statement about form ("you removed the price and pointed at the team"),
     so the resulting sentence carries no client data by construction, and
     `style.append` still redacts and fail-closes on top of that.

Matching a draft to its sent counterpart is done on the thread/message id that
Zoho hands back, with a subject+recipient fallback. When we cannot match with
confidence we learn NOTHING: a lesson attributed to the wrong thread is worse
than a missing lesson, because it is indistinguishable from a real one later.
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Hedging vocabulary per language. Entity-ish, boundary-matched — a substring
# matcher here would count "team" inside "esteem" (superscar #3 applies to
# signal extraction exactly as it applies to routing).
_HEDGES: dict[str, tuple[str, ...]] = {
    "en": ("we will confirm", "subject to", "please note", "typically",
           "in principle", "our team will", "to be confirmed", "depends on"),
    "it": ("verifichiamo", "salvo", "di norma", "in linea di principio",
           "il team", "da confermare", "dipende da"),
    "id": ("akan kami cek", "pada umumnya", "tergantung", "tim kami",
           "menunggu konfirmasi"),
    "ru": ("уточним", "как правило", "зависит от", "наша команда"),
}

_AMOUNT_RE = re.compile(r"(?<![\w])(?:Rp|IDR|USD|EUR|\$|€)\s?[\d.,]{4,}", re.I)
# Handoff = the reply points at a colleague instead of answering. Note the
# possessives: "our team will send the quotation" is the most natural English
# phrasing of a handoff and an earlier version of this pattern missed it, which
# the corpus caught. Boundary-anchored throughout — "ari" must not fire inside
# the Indonesian "hari", and "adit" must not fire inside "additional".
_TEAM_HANDOFF_RE = re.compile(
    r"(?<![\w])(?:"
    r"krisna|adit|subhi|veronika|ari"
    r"|(?:our|the|my|nostro|il)\s+team"
    r"|tim\s+kami|nostra\s+squadra|наша\s+команда"
    r")(?![\w])",
    re.I,
)
_QUESTION_RE = re.compile(r"\?")


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _first_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", stripped)
    return parts[0].strip()


def _count_hedges(text: str, language: str) -> int:
    vocab = _HEDGES.get(language, ()) + _HEDGES["en"]
    low = text.lower()
    total = 0
    for phrase in set(vocab):
        pattern = re.compile(
            r"(?<![\w])" + r"\s+".join(re.escape(p) for p in phrase.split()) + r"(?![\w])"
        )
        total += len(pattern.findall(low))
    return total


@dataclass(frozen=True)
class Signals:
    """Structural difference between a draft and what was actually sent."""

    word_delta: int
    opening_rewritten: bool
    hedges_delta: int
    amount_removed: bool
    amount_added: bool
    handoff_added: bool
    questions_delta: int
    similarity: float

    @property
    def is_meaningful(self) -> bool:
        """Whether the diff carries a habit worth recording.

        A near-identical send teaches nothing, and a total rewrite teaches
        nothing usable either: at that point the draft was not adjusted, it was
        discarded, and the reason lives outside the text.
        """
        if self.similarity >= 0.97:
            return False
        if self.similarity <= 0.25:
            return False
        return any(
            (
                abs(self.word_delta) >= 15,
                self.opening_rewritten,
                abs(self.hedges_delta) >= 1,
                self.amount_removed,
                self.amount_added,
                self.handoff_added,
                abs(self.questions_delta) >= 1,
            )
        )


def extract_signals(draft: str, sent: str, *, language: str = "en") -> Signals:
    """Compare draft vs sent. Pure function, no I/O, no LLM."""
    draft_words = _words(draft)
    sent_words = _words(sent)
    similarity = difflib.SequenceMatcher(None, draft_words, sent_words).ratio()

    draft_amounts = bool(_AMOUNT_RE.search(draft))
    sent_amounts = bool(_AMOUNT_RE.search(sent))

    return Signals(
        word_delta=len(sent_words) - len(draft_words),
        opening_rewritten=(
            _first_sentence(draft).lower() != _first_sentence(sent).lower()
        ),
        hedges_delta=_count_hedges(sent, language) - _count_hedges(draft, language),
        amount_removed=draft_amounts and not sent_amounts,
        amount_added=sent_amounts and not draft_amounts,
        handoff_added=(
            bool(_TEAM_HANDOFF_RE.search(sent))
            and not bool(_TEAM_HANDOFF_RE.search(draft))
        ),
        questions_delta=len(_QUESTION_RE.findall(sent))
        - len(_QUESTION_RE.findall(draft)),
        similarity=round(similarity, 3),
    )


def phrase_lesson(signals: Signals, *, intent: str, language: str) -> str | None:
    """Turn signals into one sentence, or None when there is nothing to say.

    Deterministic on purpose. An LLM could phrase this more elegantly, but then
    the only persisted artefact of the whole system would be non-reproducible,
    and a wrong lesson is indistinguishable from a right one once written down.
    """
    if not signals.is_meaningful:
        return None

    notes: list[str] = []

    if signals.amount_removed:
        notes.append(
            "you removed the figure from the draft — do not quote prices, "
            "point at the official pricing or the team instead"
        )
    if signals.amount_added:
        notes.append(
            "you added a figure the draft had withheld — this lane can state "
            "the published number directly"
        )
    if signals.handoff_added:
        notes.append("you handed the thread to a named colleague rather than answering")
    if signals.hedges_delta >= 1:
        notes.append(
            "you hedged more than the draft did — be more cautious in this lane"
        )
    elif signals.hedges_delta <= -1:
        notes.append(
            "you cut the draft's hedging — state the stable facts of this lane "
            "plainly instead of deferring"
        )
    if signals.opening_rewritten:
        notes.append("you rewrote the opening line — the draft's opener is not yours")
    if signals.word_delta <= -15:
        notes.append(f"you cut it much shorter ({signals.word_delta} words)")
    elif signals.word_delta >= 15:
        notes.append(f"you expanded it (+{signals.word_delta} words)")
    if signals.questions_delta >= 1:
        notes.append("you asked the client a clarifying question the draft omitted")

    if not notes:
        return None

    return f"[{intent}/{language}] " + "; ".join(notes) + "."


@dataclass(frozen=True)
class MatchCandidate:
    """A sent message we might pair with a draft we wrote."""

    message_id: str
    thread_id: str | None
    subject: str
    to: tuple[str, ...]
    body: str


def match_sent(
    *,
    draft_thread_id: str | None,
    draft_subject: str,
    draft_to: tuple[str, ...],
    candidates: list[MatchCandidate],
) -> MatchCandidate | None:
    """Pair a draft with the mail that actually went out.

    Confidence ladder, and it stops rather than guessing:
      1. same thread id — decisive.
      2. same normalised subject AND an overlapping recipient.
      3. nothing. Returning None means we skip learning for this thread.

    Subject alone is deliberately NOT enough: "Re: KITAS" is a subject Zero
    writes to a dozen different people in a week, and a lesson attributed to the
    wrong thread cannot be told apart from a real one after the fact.
    """
    if draft_thread_id:
        for cand in candidates:
            if cand.thread_id and cand.thread_id == draft_thread_id:
                return cand

    def norm_subject(value: str) -> str:
        out = value.strip().lower()
        out = re.sub(r"^(re|fw|fwd|r)\s*:\s*", "", out)
        return re.sub(r"\s+", " ", out)

    want_subject = norm_subject(draft_subject)
    want_to = {addr.lower() for addr in draft_to}
    if not want_subject or not want_to:
        return None

    matches = [
        cand
        for cand in candidates
        if norm_subject(cand.subject) == want_subject
        and want_to & {addr.lower() for addr in cand.to}
    ]
    if len(matches) == 1:
        return matches[0]

    if matches:
        logger.info(
            "learn: %d sent candidates share subject+recipient, refusing to "
            "guess which one answers this draft",
            len(matches),
        )
    return None
