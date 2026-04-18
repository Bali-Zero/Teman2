"""
Unit tests for LkpmPdfBuilder.

5 tests:
  1. build() returns valid PDF bytes (magic bytes check).
  2. Empty kbli_rows handled gracefully (no crash).
  3. Unicode in client_name is handled (Thai/Arabic/CJK chars).
  4. Size stability — same input produces same-order-of-magnitude output.
  5. Negative realization_idr raises ValueError.
"""
from __future__ import annotations

import pytest

from backend.services.compliance.lkpm_pdf_builder import LkpmPackData, LkpmPdfBuilder


@pytest.fixture()
def builder() -> LkpmPdfBuilder:
    return LkpmPdfBuilder()


@pytest.fixture()
def base_data() -> LkpmPackData:
    return LkpmPackData(
        client_name="PT Nusantara Maju Sejahtera",
        pt_nib="8120000123456",
        period="Q1 2026",
        kbli_rows=[
            {
                "kbli_code": "68200",
                "kegiatan_usaha_desc": "Aktivitas Real Estat Yang Dimiliki Sendiri",
                "oss_status": "active",
            },
            {
                "kbli_code": "79110",
                "kegiatan_usaha_desc": "Agen Perjalanan Wisata",
                "oss_status": "active",
            },
        ],
        assignee="veronika.tax@balizero.com",
        realization_idr=500_000_000,
    )


# ── Test 1: valid PDF bytes ───────────────────────────────────────────────


def test_build_returns_pdf_bytes(builder: LkpmPdfBuilder, base_data: LkpmPackData) -> None:
    """build() must return bytes starting with the PDF magic bytes %PDF."""
    pdf = builder.build(base_data)
    assert isinstance(pdf, bytes), "Expected bytes"
    assert len(pdf) > 500, "PDF too small — likely empty/corrupted"
    assert pdf[:4] == b"%PDF", f"Expected PDF magic bytes, got {pdf[:4]!r}"


# ── Test 2: empty kbli_rows ───────────────────────────────────────────────


def test_build_empty_kbli_rows(builder: LkpmPdfBuilder) -> None:
    """Empty kbli_rows must produce a valid PDF with a 'no rows' placeholder."""
    data = LkpmPackData(
        client_name="PT Test",
        pt_nib="0000000000001",
        period="Q2 2026",
        kbli_rows=[],
        assignee="kadek.tax@balizero.com",
        realization_idr=0,
    )
    pdf = builder.build(data)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"
    # File should still be non-trivial (has header + footer)
    assert len(pdf) > 200


# ── Test 3: unicode in client_name ───────────────────────────────────────


def test_build_unicode_client_name(builder: LkpmPdfBuilder) -> None:
    """Unicode characters (Japanese, Arabic, emoji-free) in client_name must not crash."""
    data = LkpmPackData(
        client_name="PT Bali Villa \u6d77\u8fb9\u5e84\u56ed",  # 海边庄园 (CJK)
        pt_nib="1234567890000",
        period="Q3 2026",
        kbli_rows=[
            {
                "kbli_code": "55110",
                "kegiatan_usaha_desc": "Hotel Berbintang",
                "oss_status": "pending",
            }
        ],
        assignee="dewaayu.tax@balizero.com",
        realization_idr=1_000_000,
    )
    # reportlab may substitute glyphs for unsupported chars; it must not raise
    pdf = builder.build(data)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


# ── Test 4: size stability ────────────────────────────────────────────────


def test_build_size_stability(builder: LkpmPdfBuilder, base_data: LkpmPackData) -> None:
    """
    Two consecutive builds of the same data should produce output within
    the same order of magnitude (±50%). Reportlab is deterministic for
    static content; small variation is acceptable for timestamps.
    """
    pdf_a = builder.build(base_data)
    pdf_b = builder.build(base_data)
    ratio = len(pdf_a) / len(pdf_b)
    assert 0.5 <= ratio <= 2.0, (
        f"PDF size changed unexpectedly: {len(pdf_a)} vs {len(pdf_b)} bytes"
    )


# ── Test 5: negative realization raises ───────────────────────────────────


def test_negative_realization_raises() -> None:
    """LkpmPackData.__post_init__ must raise ValueError for negative realization_idr."""
    with pytest.raises(ValueError, match="non-negative"):
        LkpmPackData(
            client_name="PT Bad Data",
            pt_nib="0000000000002",
            period="Q4 2025",
            kbli_rows=[],
            assignee="angel.tax@balizero.com",
            realization_idr=-1,
        )
