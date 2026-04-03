"""Tests for Naga report writer — tier-appropriate Markdown generation.

Covers flash / deep / exhaustive tiers, evidence bars, gap reporting,
and graceful handling of empty claims.
"""

from __future__ import annotations

import pytest

from backend.core.claims.models import ClaimRecord
from backend.services.naga.synthesis.report_writer import (
    _evidence_status_bar,
    _format_claim,
    generate_report,
)

# ---------------------------------------------------------------------------
# Fixtures — reusable claim sets
# ---------------------------------------------------------------------------


def _make_claim(
    *,
    claim_id: str = "C001",
    text: str = "Indonesia requires KITAS for work permits",
    category: str = "LEGAL_CHANGE",
    confidence_class: str = "VERIFIED",
    confidence_score: float = 0.85,
    source_ids: list[str] | None = None,
    geographic_scope: str = "NATIONAL",
    affected_visa_types: list[str] | None = None,
    flags: dict | None = None,
) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        claim_text=text,
        category=category,
        confidence_class=confidence_class,
        confidence_score=confidence_score,
        source_ids=source_ids or ["src-1", "src-2"],
        extracted="2026-04-03",
        geographic_scope=geographic_scope,
        affected_visa_types=affected_visa_types or [],
        flags=flags or {},
    )


@pytest.fixture()
def verified_claim() -> ClaimRecord:
    return _make_claim()


@pytest.fixture()
def provisional_claim() -> ClaimRecord:
    return _make_claim(
        claim_id="C002",
        text="Processing time for E33A reduced to 5 days",
        confidence_class="PROVISIONAL",
        confidence_score=0.65,
        source_ids=["src-3"],
    )


@pytest.fixture()
def low_claim() -> ClaimRecord:
    return _make_claim(
        claim_id="C003",
        text="Unverified rumour about fee waiver for investors",
        confidence_class="LOW",
        confidence_score=0.30,
        source_ids=["src-4"],
    )


@pytest.fixture()
def mixed_claims(
    verified_claim: ClaimRecord,
    provisional_claim: ClaimRecord,
    low_claim: ClaimRecord,
) -> list[ClaimRecord]:
    return [verified_claim, provisional_claim, low_claim]


@pytest.fixture()
def evidence_map() -> dict:
    return {
        "data_points": [
            {"label": "KITAS processing", "value": "5 business days"},
            {"label": "PMA minimum capital", "value": "IDR 10B"},
        ],
        "gaps": ["No official source for fee waiver claim"],
    }


# ---------------------------------------------------------------------------
# Flash tier tests
# ---------------------------------------------------------------------------


class TestFlashReport:
    """Flash report must be short (1-3 paragraphs, under 2000 chars)."""

    def test_flash_report_short(
        self, mixed_claims: list[ClaimRecord], evidence_map: dict
    ) -> None:
        report = generate_report(
            query="KITAS requirements 2026",
            tier="flash",
            claims=mixed_claims,
            evidence_map=evidence_map,
        )
        assert len(report) < 2000

    def test_flash_report_contains_claims(
        self, verified_claim: ClaimRecord, provisional_claim: ClaimRecord
    ) -> None:
        report = generate_report(
            query="KITAS requirements 2026",
            tier="flash",
            claims=[verified_claim, provisional_claim],
            evidence_map={},
        )
        # Must include text of trustworthy claims
        assert "Indonesia requires KITAS for work permits" in report
        assert "Processing time for E33A reduced to 5 days" in report

    def test_flash_report_notes_contested(
        self, low_claim: ClaimRecord
    ) -> None:
        report = generate_report(
            query="Fee waiver",
            tier="flash",
            claims=[low_claim],
            evidence_map={},
        )
        assert "low" in report.lower() or "contested" in report.lower()


# ---------------------------------------------------------------------------
# Deep tier tests
# ---------------------------------------------------------------------------


class TestDeepReport:
    """Deep report needs structured sections and evidence bar."""

    def test_deep_report_has_sections(
        self, mixed_claims: list[ClaimRecord], evidence_map: dict
    ) -> None:
        report = generate_report(
            query="KITAS processing changes",
            tier="deep",
            claims=mixed_claims,
            evidence_map=evidence_map,
        )
        assert "# Research Report:" in report
        assert "## Executive Summary" in report
        assert "## Contradictions and Uncertainty" in report
        assert "## Research Limitations" in report

    def test_deep_report_shows_evidence_bar(
        self, mixed_claims: list[ClaimRecord], evidence_map: dict
    ) -> None:
        report = generate_report(
            query="KITAS processing changes",
            tier="deep",
            claims=mixed_claims,
            evidence_map=evidence_map,
        )
        assert "VERIFIED:" in report
        assert "PROVISIONAL:" in report
        assert "LOW:" in report

    def test_deep_report_metadata(
        self, mixed_claims: list[ClaimRecord], evidence_map: dict
    ) -> None:
        report = generate_report(
            query="test query",
            tier="deep",
            claims=mixed_claims,
            evidence_map=evidence_map,
            sources_count=5,
            duration_ms=1234,
        )
        assert "5 sources" in report
        assert "1234" in report or "1.2" in report  # raw or formatted


# ---------------------------------------------------------------------------
# Exhaustive tier tests
# ---------------------------------------------------------------------------


class TestExhaustiveReport:
    """Exhaustive report adds appendix and data points on top of deep."""

    def test_exhaustive_report_has_appendix(
        self, mixed_claims: list[ClaimRecord], evidence_map: dict
    ) -> None:
        report = generate_report(
            query="KITAS processing changes",
            tier="exhaustive",
            claims=mixed_claims,
            evidence_map=evidence_map,
        )
        assert "## Appendix: Low-Confidence Claims" in report
        assert "Unverified rumour about fee waiver" in report

    def test_exhaustive_report_has_data_points(
        self, mixed_claims: list[ClaimRecord], evidence_map: dict
    ) -> None:
        report = generate_report(
            query="Capital requirements",
            tier="exhaustive",
            claims=mixed_claims,
            evidence_map=evidence_map,
        )
        assert "## Key Data Points" in report
        assert "IDR 10B" in report

    def test_exhaustive_includes_deep_sections(
        self, mixed_claims: list[ClaimRecord], evidence_map: dict
    ) -> None:
        report = generate_report(
            query="test",
            tier="exhaustive",
            claims=mixed_claims,
            evidence_map=evidence_map,
        )
        assert "## Executive Summary" in report
        assert "## Contradictions and Uncertainty" in report
        assert "## Research Limitations" in report


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Graceful handling of empty inputs and gap reporting."""

    def test_report_handles_no_claims(self) -> None:
        report = generate_report(
            query="Unknown topic",
            tier="deep",
            claims=[],
            evidence_map={},
        )
        assert report  # not empty
        assert "no verifiable claims" in report.lower() or "no claims" in report.lower()

    def test_report_includes_gaps(
        self, verified_claim: ClaimRecord
    ) -> None:
        gaps = ["No primary source for fee data", "Regulatory gazette not yet published"]
        report = generate_report(
            query="Fee analysis",
            tier="deep",
            claims=[verified_claim],
            evidence_map={},
            gaps=gaps,
        )
        assert "No primary source for fee data" in report
        assert "Regulatory gazette not yet published" in report

    def test_report_gaps_from_evidence_map(
        self, verified_claim: ClaimRecord, evidence_map: dict
    ) -> None:
        """Gaps embedded in evidence_map are also surfaced."""
        report = generate_report(
            query="Fee analysis",
            tier="deep",
            claims=[verified_claim],
            evidence_map=evidence_map,
        )
        assert "No official source for fee waiver claim" in report


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    """Unit tests for _evidence_status_bar and _format_claim."""

    def test_evidence_status_bar_counts(
        self, mixed_claims: list[ClaimRecord]
    ) -> None:
        bar = _evidence_status_bar(mixed_claims)
        assert "VERIFIED: 1" in bar
        assert "PROVISIONAL: 1" in bar
        assert "LOW: 1" in bar

    def test_evidence_status_bar_empty(self) -> None:
        bar = _evidence_status_bar([])
        assert "VERIFIED: 0" in bar
        assert "PROVISIONAL: 0" in bar
        assert "LOW: 0" in bar

    def test_format_claim_includes_fields(
        self, verified_claim: ClaimRecord
    ) -> None:
        line = _format_claim(verified_claim, index=1)
        assert "1." in line or "[1]" in line
        assert "VERIFIED" in line
        assert "2 sources" in line or "2 source" in line
        assert "Indonesia requires KITAS" in line
