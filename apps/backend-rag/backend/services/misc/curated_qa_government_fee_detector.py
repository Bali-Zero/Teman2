"""Pre-ingest FACT-scan: does this answer state a GOVERNMENT FEE FIGURE to a client?

WHY (cycle 359, measured on real WhatsApp delivery 2026-09-01)
--------------------------------------------------------------
Zero's standing ruling (2026-07-17, re-ruled 2026-09-01) is **one all-inclusive
client-facing price** — never a PNBP-versus-service-fee split. The bot broke it
on questions 11 and 14 of the cycle-359 battery, and the cause was not the
prompt: **the corpus teaches the split.** Two live `curated_qa` points answered
"how much does the Investor KITAS cost" with the government fee alone, and one
of them stated the doctrine outright — *"We always keep these two costs
distinct"*. Their source file has never existed in this repo, so deleting the
points fixes today and nothing else: the next harvest can regenerate them.

This module is the thing that survives the deletion.

WHAT IT SCANS FOR — the FACT, never a phrasing
-----------------------------------------------
The overnight sweep that preceded this gate reported "5 offenders, 808 scanned,
1 residual" and was falsely reassuring: it searched the phrasings someone had
catalogued (*"we always show the two figures separately"*) and missed *"We
always keep these two costs distinct"* — the same teaching, different words.
W82, under-match. So this scans for the FACT: **a government-fee token and a
money figure in the same answer.** A rewording cannot escape it, because the
fee and the figure are what the offence is made of.

WHAT IT DELIBERATELY DOES NOT DO — decide
------------------------------------------
Measured on the live collection (808 points, 2026-09-03):

| shape | count | verdict |
|---|---|---|
| no government-fee token | 758 | passes, untouched |
| government-fee token, **no** money figure | 27 | passes — and these are the model answers: *"rather than quote a figure that may age, ask our team"* |
| government-fee token **and** a money figure | 23 | **refused unless reviewed** |

Of those 23, **9 are genuine offenders** and 14 are compliant answers that
happen to name a figure — *"one all-inclusive price that already contains the
statutory PNBP, so you will never be asked to pay a government fee on top"*.

A proximity rule was calibrated against those 9 and **rejected on its numbers**:
at every window from 40 to 160 characters it caught at most 8 of 9 while
blocking 11 to 13 compliant rows. There is no lexical rule that separates
"the government charges X, we charge Y" from "our X already includes the
government charge" — the difference is semantic. So this gate does not pretend
to: it is **high-recall (9 of 9) and refuse-by-default**, and a row that
genuinely must state a government figure carries an explicit per-row marker
saying a human looked at it. One field, once, on 2.8% of the corpus, in
exchange for making the silent regeneration of the offence impossible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.services.misc.curated_qa_pricing_detector import has_price_content

# Government-fee vocabulary, in the four languages this corpus is written in.
# Every term names the SAME entity — a charge levied by the Indonesian state —
# which is what makes this a fact scan and not a phrase list: an author who
# rewords the sentence still has to name the fee.
_GOVERNMENT_FEE_RE = re.compile(
    r"""
      \bPNBP\b
    | penerimaan\s+negara\s+bukan\s+pajak
    | government\s+(?:issuance\s+|processing\s+)?fee
    | governmental\s+fee
    | government\s+(?:tariff|charge)
    | official\s+government
    | official\s+fee
    | state\s+fee
    | biaya\s+(?:pemerintah|negara|resmi|imigrasi|visa)
    | tarif\s+(?:resmi|pemerintah)
    | immigration\s+fee
    | visa\s+fee
    | tassa\s+governativa
    | spese\s+governative
    """,
    re.IGNORECASE | re.VERBOSE,
)

# The per-row escape hatch. A corpus row that must state a government figure —
# the all-inclusive explainers do, legitimately — sets this to True AND gives a
# note. Both are required: a bare boolean is a checkbox, a note is a claim
# someone made and can be held to.
REVIEW_FLAG_FIELD = "government_fee_reviewed"
REVIEW_NOTE_FIELD = "government_fee_review_note"


@dataclass(frozen=True)
class GovernmentFeeFinding:
    """What the scan saw. `states_a_figure` is the gating fact."""

    tokens: tuple[str, ...]
    states_a_figure: bool


def scan_government_fee(answer: str | None) -> GovernmentFeeFinding | None:
    """Return what the answer says about government fees, or None if nothing.

    Pure, no I/O. `None` means the text names no government fee at all — the
    overwhelming majority (758 of 808 measured).
    """
    if not answer:
        return None
    tokens = tuple(sorted({m.group(0).lower() for m in _GOVERNMENT_FEE_RE.finditer(answer)}))
    if not tokens:
        return None
    return GovernmentFeeFinding(tokens=tokens, states_a_figure=has_price_content(answer))


def row_is_refused(row: dict) -> str | None:
    """Return the refusal reason for a corpus row, or None to let it through.

    The gate: an answer that names a government fee AND states a money figure
    is refused, unless the row carries BOTH the review flag and a non-empty
    review note.
    """
    answer = row.get("answer")
    finding = scan_government_fee(answer if isinstance(answer, str) else None)
    if finding is None or not finding.states_a_figure:
        return None

    reviewed = row.get(REVIEW_FLAG_FIELD) is True
    note = row.get(REVIEW_NOTE_FIELD)
    if reviewed and isinstance(note, str) and note.strip():
        return None

    return (
        "states a government-fee figure to a client "
        f"(tokens: {', '.join(finding.tokens)}) without "
        f"{REVIEW_FLAG_FIELD}=true and a non-empty {REVIEW_NOTE_FIELD}. "
        "Zero's ruling is ONE all-inclusive client-facing price — never a "
        "PNBP-versus-service-fee split (2026-07-17, re-ruled 2026-09-01)."
    )
