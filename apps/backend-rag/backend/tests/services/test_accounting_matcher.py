"""Tests for the reconciliation matcher (pure logic, no DB).

Covers the panel-mandated behavior: exact match, PPh23-net detection, partial
and overpayment signals, fuzzy name boost, date-window gate, ranking, and the
critical "nothing plausible -> empty" contract (no phantom matches).
"""

from __future__ import annotations

from datetime import date

from backend.services.accounting.matcher import (
    OpenInvoice,
    rank_candidates,
)


def _inv(invoice_id: int, amount: int, name: str, gen: date | None = None, pph: int = 0) -> OpenInvoice:
    return OpenInvoice(
        invoice_id=invoice_id,
        practice_id=invoice_id * 10,
        client_name=name,
        amount_idr=amount,
        generated_at=gen,
        pph_expected_idr=pph,
    )


class TestExactMatch:
    def test_exact_amount_is_top_candidate(self) -> None:
        invs = [_inv(1, 4_000_000, "Dina Bishibekova"), _inv(2, 9_000_000, "John Smith")]
        out = rank_candidates(
            transfer_amount_idr=4_000_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="DINA B",
            open_invoices=invs,
        )
        assert out
        assert out[0].invoice_id == 1
        assert "exact amount match" in out[0].reasons[0]
        assert out[0].confidence >= 0.7

    def test_within_tolerance_still_exact(self) -> None:
        out = rank_candidates(
            transfer_amount_idr=4_000_500,  # 500 IDR noise
            transfer_date=date(2026, 6, 25),
            payer_memo="",
            open_invoices=[_inv(1, 4_000_000, "X")],
        )
        assert out and "exact amount match" in out[0].reasons[0]


class TestPPh23:
    def test_net_of_pph23_detected(self) -> None:
        # gross 10M, B2B withholds 2% -> transfer 9.8M
        out = rank_candidates(
            transfer_amount_idr=9_800_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="PT KLIEN",
            open_invoices=[_inv(1, 10_000_000, "PT Klien")],
        )
        assert out
        assert out[0].likely_withheld is True
        assert any("PPh23" in r for r in out[0].reasons)


class TestPartialAndOverpay:
    def test_partial_payment_low_confidence(self) -> None:
        out = rank_candidates(
            transfer_amount_idr=5_000_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="",
            open_invoices=[_inv(1, 12_500_000, "X")],
        )
        assert out and out[0].confidence < 0.5
        assert any("partial" in r for r in out[0].reasons)

    def test_overpayment_flagged(self) -> None:
        out = rank_candidates(
            transfer_amount_idr=20_000_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="",
            open_invoices=[_inv(1, 5_000_000, "X")],
        )
        assert out and any("exceeds" in r for r in out[0].reasons)


class TestNameBoost:
    def test_name_match_boosts_confidence(self) -> None:
        # two invoices, same exact amount; payer name should break the tie
        invs = [_inv(1, 4_000_000, "Marina Pinyaylova"), _inv(2, 4_000_000, "Klaus Mueller")]
        out = rank_candidates(
            transfer_amount_idr=4_000_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="MARINA PINYAYLOVA",
            open_invoices=invs,
        )
        assert out[0].invoice_id == 1
        assert out[0].confidence > out[1].confidence


class TestDateWindow:
    def test_outside_window_penalized(self) -> None:
        old = _inv(1, 4_000_000, "X", gen=date(2026, 1, 1))
        out = rank_candidates(
            transfer_amount_idr=4_000_000,
            transfer_date=date(2026, 6, 25),  # ~175 days later
            payer_memo="",
            open_invoices=[old],
        )
        assert out and any("date window" in r for r in out[0].reasons)
        assert out[0].confidence < 0.7  # halved from exact 0.7


class TestNoPhantom:
    def test_tiny_transfer_below_partial_floor_no_candidate(self) -> None:
        # 50k vs 3M = 1.6% < 10% MIN_PARTIAL_FRACTION -> noise, not surfaced.
        out = rank_candidates(
            transfer_amount_idr=50_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="ZZZ",
            open_invoices=[_inv(1, 3_000_000, "X")],
        )
        assert out == []

    def test_meaningful_partial_is_candidate(self) -> None:
        # 50% deposit IS a plausible installment -> surfaced, low confidence.
        out = rank_candidates(
            transfer_amount_idr=1_500_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="X",
            open_invoices=[_inv(1, 3_000_000, "X")],
        )
        assert out and any("partial" in r for r in out[0].reasons)

    def test_empty_invoices_empty_result(self) -> None:
        out = rank_candidates(
            transfer_amount_idr=4_000_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="X",
            open_invoices=[],
        )
        assert out == []


class TestZeroAmountGuard:
    """D6: a zero/non-positive transfer or zero-amount invoice must NEVER
    phantom-match as 'exact' (0 == 0 within tolerance would otherwise score 0.7)."""

    def test_zero_transfer_no_candidate(self) -> None:
        # A 0 IDR "transfer" against a real invoice is not a payment.
        out = rank_candidates(
            transfer_amount_idr=0,
            transfer_date=date(2026, 6, 25),
            payer_memo="X",
            open_invoices=[_inv(1, 4_000_000, "X")],
        )
        assert out == []

    def test_zero_amount_invoice_no_phantom_exact(self) -> None:
        # The dangerous case: transfer 0 against a 0-amount invoice would match
        # "exact" (abs(0) <= tolerance) without the guard. Must stay empty.
        out = rank_candidates(
            transfer_amount_idr=0,
            transfer_date=date(2026, 6, 25),
            payer_memo="X",
            open_invoices=[_inv(1, 0, "X")],
        )
        assert out == []

    def test_negative_transfer_no_candidate(self) -> None:
        # A debit (money out) should never be offered as an invoice payment.
        out = rank_candidates(
            transfer_amount_idr=-4_000_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="X",
            open_invoices=[_inv(1, 4_000_000, "X")],
        )
        assert out == []

    def test_zero_amount_invoice_ignored_real_transfer_other_matches(self) -> None:
        # A 0-amount junk invoice is skipped, but a real invoice still matches.
        invs = [_inv(1, 0, "Junk Row"), _inv(2, 4_000_000, "Real Client")]
        out = rank_candidates(
            transfer_amount_idr=4_000_000,
            transfer_date=date(2026, 6, 25),
            payer_memo="REAL CLIENT",
            open_invoices=invs,
        )
        assert out and out[0].invoice_id == 2
        assert all(c.invoice_id != 1 for c in out)
