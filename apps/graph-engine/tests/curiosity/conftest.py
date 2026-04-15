"""Shared fixtures for Curiosity Loop tests."""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from nuzantara_graph.curiosity.models import (
    GapTopic,
    GradeResult,
    KGProposal,
    ProposalType,
    ResearchEvidence,
    Tier,
)


@pytest.fixture
def sample_gaps() -> list[GapTopic]:
    """10 gap topics spanning 5 domains."""
    return [
        GapTopic(domain="immigration", topic="KITAS requirements and process 2025", freshness="GAP", severity=1.0),
        GapTopic(domain="immigration", topic="KITAP eligibility and conversion from KITAS", freshness="GAP", severity=1.0),
        GapTopic(domain="company", topic="PT PMA setup requirements 2025", freshness="GAP", severity=1.0),
        GapTopic(domain="company", topic="OSS-RBA online registration process", freshness="STALE", severity=0.7),
        GapTopic(domain="tax", topic="PPh 21 rates and calculation for expats", freshness="GAP", severity=1.0),
        GapTopic(domain="tax", topic="CoreTax system migration 2025", freshness="STALE", severity=0.7),
        GapTopic(domain="property", topic="HGB title for foreigners in Indonesia", freshness="GAP", severity=1.0),
        GapTopic(domain="property", topic="RTRW zoning regulations Bali 2024", freshness="AGING", severity=0.3),
        GapTopic(domain="operations", topic="UMR/UMK Bali minimum wage 2025", freshness="GAP", severity=1.0),
        GapTopic(domain="editorial", topic="Google Helpful Content Update 2024", freshness="GAP", severity=1.0),
    ]


@pytest.fixture
def good_evidence() -> list[ResearchEvidence]:
    """Evidence that should pass grading (score >= 0.60)."""
    return [
        ResearchEvidence(
            content="KITAS (Kartu Izin Tinggal Terbatas) is regulated under PP 48/2021 and "
                    "Permenkumham No. 22 Tahun 2023. The application requires: valid passport, "
                    "sponsor letter from Indonesian entity, RPTKA approval from Kemnaker, "
                    "and telex from Dirjen Imigrasi. Processing time: 5-7 working days after "
                    "submission at Kantor Imigrasi. Government fee (PNBP): Rp 2,000,000 for "
                    "1-year KITAS. Renewal must be filed 30 days before expiry.",
            source_type="ollama",
            citations=["PP 48/2021", "Permenkumham No. 22/2023"],
            confidence=0.8,
        ),
    ]


@pytest.fixture
def weak_evidence() -> list[ResearchEvidence]:
    """Evidence that should NOT pass grading (score < 0.60)."""
    return [
        ResearchEvidence(
            content="KITAS info.",  # Too short
            source_type="template",
            confidence=0.1,
        ),
    ]


@pytest.fixture
def marginal_evidence() -> list[ResearchEvidence]:
    """Evidence in the grey zone (0.15 - 0.60)."""
    return [
        ResearchEvidence(
            content="KITAS requires a valid passport and sponsor letter. "
                    "Processing takes about a week.",
            source_type="ollama",
            citations=[],
            confidence=0.4,
        ),
    ]


@pytest.fixture
def sample_coverage_matrix(tmp_path) -> str:
    """Create a temporary coverage_matrix.json for testing."""
    matrix = {
        "immigration": {
            "label": "Immigration & Visa",
            "coverage": {
                "KITAS requirements and process 2025": "GAP",
                "KITAP eligibility and conversion from KITAS": "GAP",
                "B211A visa digital nomad Indonesia": "STALE",
            },
            "coverage_updated": "2026-04-12T11:00:43.714604+00:00",
            "health_pct": 0.0,
            "gap_pct": 100.0,
        },
        "company": {
            "label": "Company Setup & KBLI",
            "coverage": {
                "PT PMA setup requirements 2025": "GAP",
                "OSS-RBA online registration process": "AGING",
            },
            "coverage_updated": "2026-04-12T11:01:24.886607+00:00",
            "health_pct": 0.0,
            "gap_pct": 100.0,
        },
        "tax": {
            "label": "Tax & Fiscal",
            "coverage": {
                "PPh 21 rates and calculation for expats": "GAP",
                "CoreTax system migration 2025": "FRESH",
            },
            "coverage_updated": "2026-04-12T11:02:05.929217+00:00",
            "health_pct": 50.0,
            "gap_pct": 50.0,
        },
    }

    path = tmp_path / "coverage_matrix.json"
    with open(path, "w") as f:
        json.dump(matrix, f)

    return str(path)


@pytest.fixture
def mock_proposal_store() -> AsyncMock:
    """Mock KGProposalStore for testing orchestrator without DB."""
    store = AsyncMock()
    store.save = AsyncMock(return_value="test-proposal-id")
    store.is_duplicate = AsyncMock(return_value=False)
    store.is_blacklisted = AsyncMock(return_value=False)
    store.expire_stale = AsyncMock(return_value=0)
    store.list_proposals = AsyncMock(return_value=[])
    store.get_proposal = AsyncMock(return_value=None)
    store.stats = AsyncMock(return_value={
        "status_counts": {},
        "pending_by_domain": {},
        "total": 0,
        "ontological_density": 2.247,
        "node_count": 108068,
        "edge_count": 242827,
    })
    return store


@pytest.fixture
def sample_proposal() -> KGProposal:
    """A valid proposal for testing."""
    return KGProposal(
        proposal_id="test-proposal-001",
        gap_id="immigration:KITAS requirements and process 2025",
        domain="immigration",
        proposal_type=ProposalType.NODE,
        tier=Tier.SIMPLE,
        node_label="KITAS requirements and process 2025",
        node_type="Immigration",
        node_properties={
            "description": "KITAS regulated under PP 48/2021...",
            "gap_origin": True,
            "citations": ["PP 48/2021"],
        },
        evidence_sources=[{
            "content": "KITAS is...",
            "source_type": "ollama",
            "citations": ["PP 48/2021"],
            "confidence": 0.8,
        }],
        self_rag_score=0.72,
        research_method="curiosity_tier1_simple",
    )
