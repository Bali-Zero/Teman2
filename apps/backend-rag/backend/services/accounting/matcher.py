"""Reconciliation matcher — propose invoice candidates for an incoming transfer.

Pure logic, no DB: given one bank credit and a list of open invoices, rank
candidate matches. The accountant always makes the final call (manual confirm).

Panel decision (Gemini+DeepSeek+Codex unanimous): NO subset-sum. Subset-sum
"generates plausible lies" with PPh23 withholding, bank fees, and partial
payments. Instead:
  - exact amount (± tolerance) within a date window  -> high confidence
  - amount net of expected PPh23 (gross - 2%)         -> "likely withheld" hint
  - rapidfuzz on payer name vs client name            -> name hint (never auto)
Multi-invoice payments: the accountant manually multi-selects (deterministic),
handled at the service layer — NOT guessed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from rapidfuzz import fuzz

# Default Indonesian B2B PPh23 withholding rate (2%).
PPH23_RATE = 0.02
# Amount tolerance for "exact" match (rounding / sub-rupiah noise), in IDR.
EXACT_TOLERANCE_IDR = 1_000
# How many days around the transfer date an invoice is still a plausible match.
DATE_WINDOW_DAYS = 60
# rapidfuzz name score (0-100) below which we don't even surface a name hint.
NAME_HINT_FLOOR = 60.0
# A "partial payment" smaller than this fraction of the invoice is noise, not a
# plausible installment — don't surface it (avoids spamming the review screen
# with a tiny transfer "matching" every large open invoice).
MIN_PARTIAL_FRACTION = 0.10


@dataclass(frozen=True)
class OpenInvoice:
    """The subset of invoice/practice fields the matcher needs."""

    invoice_id: int
    practice_id: int
    client_name: str
    amount_idr: int
    generated_at: date | None = None
    pph_expected_idr: int = 0


@dataclass
class MatchCandidate:
    """A ranked candidate match for a bank transfer."""

    invoice_id: int
    practice_id: int
    client_name: str
    invoice_amount_idr: int
    confidence: float  # 0.0 - 1.0
    reasons: list[str] = field(default_factory=list)
    amount_delta_idr: int = 0  # transfer - invoice (negative = transfer is less)
    likely_withheld: bool = False


def _amount_signals(transfer_idr: int, inv: OpenInvoice) -> tuple[float, list[str], int, bool]:
    """Score the amount relationship. Returns (score, reasons, delta, withheld)."""
    reasons: list[str] = []
    delta = transfer_idr - inv.amount_idr

    # Exact (within tolerance)
    if abs(delta) <= EXACT_TOLERANCE_IDR:
        reasons.append("exact amount match")
        return 0.7, reasons, delta, False

    # Net of expected PPh23: a B2B client transfers gross - 2% (or the
    # explicitly-recorded pph_expected). transfer ~= amount - withholding.
    expected_wh = inv.pph_expected_idr or round(inv.amount_idr * PPH23_RATE)
    net_expected = inv.amount_idr - expected_wh
    if abs(transfer_idr - net_expected) <= EXACT_TOLERANCE_IDR:
        reasons.append(f"matches amount net of PPh23 (withheld ~{expected_wh:,} IDR)")
        return 0.6, reasons, delta, True

    # Partial payment: transfer is a meaningful fraction less than the invoice.
    # Below MIN_PARTIAL_FRACTION it's noise, not a plausible installment.
    if inv.amount_idr * MIN_PARTIAL_FRACTION <= transfer_idr < inv.amount_idr:
        reasons.append("possible partial payment (transfer < invoice)")
        return 0.2, reasons, delta, False

    # Overpayment / lump sum that exceeds this single invoice.
    if transfer_idr > inv.amount_idr + EXACT_TOLERANCE_IDR:
        reasons.append("transfer exceeds this invoice (overpayment or covers several)")
        return 0.15, reasons, delta, False

    return 0.0, reasons, delta, False


def _date_in_window(transfer_date: date, inv: OpenInvoice) -> bool:
    if inv.generated_at is None:
        return True  # unknown -> don't penalize
    return abs((transfer_date - inv.generated_at).days) <= DATE_WINDOW_DAYS


def _name_score(payer_memo: str, client_name: str) -> float:
    """0-100 fuzzy score between the bank memo and the client name."""
    if not payer_memo or not client_name:
        return 0.0
    # token_set_ratio is robust to word order / extra tokens in bank memos.
    return float(fuzz.token_set_ratio(payer_memo.lower(), client_name.lower()))


def rank_candidates(
    *,
    transfer_amount_idr: int,
    transfer_date: date,
    payer_memo: str,
    open_invoices: list[OpenInvoice],
    limit: int = 5,
) -> list[MatchCandidate]:
    """Rank open invoices as candidate matches for one incoming transfer.

    Confidence blends amount signal (primary) with name similarity (secondary)
    and a date-window gate. Returns the top `limit`, highest confidence first.
    Empty list means nothing plausible — the transfer stays 'unmatched'.
    """
    candidates: list[MatchCandidate] = []

    for inv in open_invoices:
        amount_score, reasons, delta, withheld = _amount_signals(transfer_amount_idr, inv)
        if amount_score <= 0.0:
            continue  # no amount relationship at all -> not a candidate

        name = _name_score(payer_memo, inv.client_name)
        in_window = _date_in_window(transfer_date, inv)

        # Blend: amount is primary (up to 0.7), name adds up to 0.25, date gates.
        confidence = amount_score
        if name >= NAME_HINT_FLOOR:
            confidence += (name / 100.0) * 0.25
            reasons.append(f"payer name ~ client ({name:.0f}%)")
        if not in_window:
            confidence *= 0.5
            reasons.append("outside 60-day date window")

        confidence = round(min(confidence, 1.0), 3)
        candidates.append(
            MatchCandidate(
                invoice_id=inv.invoice_id,
                practice_id=inv.practice_id,
                client_name=inv.client_name,
                invoice_amount_idr=inv.amount_idr,
                confidence=confidence,
                reasons=reasons,
                amount_delta_idr=delta,
                likely_withheld=withheld,
            )
        )

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[:limit]
