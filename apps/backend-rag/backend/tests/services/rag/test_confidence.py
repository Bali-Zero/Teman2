"""
Unit Tests for Dynamic Confidence Scoring (Phase 2)

Tests all confidence calculation functions and the ConfidenceBreakdown dataclass.

Author: Nuzantara Team
Date: 2026-02-09
Reference: memory/langgraph-kg-evolution-plan.md (Phase 2)

Test Coverage:
- Chain base score: 3 tests
- Relationship strength: 2 tests
- Recency score: 3 tests
- Multi-source bonus: 2 tests
- Dynamic confidence (composite): 3 tests
- Confidence warning: 2 tests
Total: 15 tests
"""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.rag.confidence import (
    ConfidenceBreakdown,
    calculate_chain_base_score,
    calculate_dynamic_confidence,
    calculate_multi_source_bonus,
    calculate_recency_score,
    calculate_relationship_strength,
    calculate_subgraph_confidence,
    get_confidence_warning,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_state():
    """Sample KGAgentState dict for testing."""
    return {
        "query": "Aprire ristorante e assumere chef straniero",
        "user_context": {"citizenship": "foreign"},
        "current_entities": ["kbli:56101", "visa:e28a"],
        "visited_entities": set(),
        "relationship_chains": [],
        "reasoning_steps": [],
        "confidence_scores": {},
        "intent": None,
        "extracted_entities": [],
        "workflow": None,
        "answer_evidence": [],
        "golden_route_match": None,
        "messages": [],
        "next_step": "",
    }


@pytest.fixture
def rich_chains():
    """Chains with enriched metadata (source_collection, created_at)."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    return [
        [
            {
                "source_entity_id": "kbli:56101",
                "source_name": "Restoran",
                "source_type": "kbli",
                "relationship_type": "REQUIRES",
                "target_entity_id": "doc:nib",
                "target_name": "NIB",
                "target_type": "dokumen",
                "depth": 1,
                "edge_confidence": 0.9,
                "edge_source_collection": "legal_unified_hybrid",
                "target_source_collection": "legal_unified_hybrid",
                "target_created_at": yesterday,
                "edge_created_at": yesterday,
            },
        ],
        [
            {
                "source_entity_id": "kbli:56101",
                "source_name": "Restoran",
                "source_type": "kbli",
                "relationship_type": "ENABLES",
                "target_entity_id": "visa:e28g",
                "target_name": "KITAS E28G",
                "target_type": "visa",
                "depth": 1,
                "edge_confidence": 0.85,
                "edge_source_collection": "visa_oracle",
                "target_source_collection": "visa_oracle",
                "target_created_at": yesterday,
                "edge_created_at": yesterday,
            },
        ],
        [
            {
                "source_entity_id": "visa:e28g",
                "source_name": "KITAS E28G",
                "source_type": "visa",
                "relationship_type": "REQUIRES",
                "target_entity_id": "doc:rptka",
                "target_name": "RPTKA",
                "target_type": "dokumen",
                "depth": 2,
                "edge_confidence": 0.95,
                "edge_source_collection": "tax_genius_hybrid",
                "target_source_collection": "legal_unified_hybrid",
                "target_created_at": now,
                "edge_created_at": now,
            },
        ],
    ]


# ============================================================================
# Chain Base Score Tests (3 tests)
# ============================================================================


class TestChainBaseScore:
    def test_zero_chains(self):
        assert calculate_chain_base_score(0) == 0.0

    def test_moderate_chains(self):
        assert calculate_chain_base_score(5) == 0.6

    def test_many_chains(self):
        assert calculate_chain_base_score(15) == 1.0

    def test_boundary_two_chains(self):
        assert calculate_chain_base_score(2) == 0.4

    def test_boundary_ten_chains(self):
        assert calculate_chain_base_score(10) == 0.8


# ============================================================================
# Relationship Strength Tests (2 tests)
# ============================================================================


class TestRelationshipStrength:
    def test_requires_only(self):
        chains = [[{"relationship_type": "REQUIRES"}], [{"relationship_type": "REQUIRES"}]]
        assert calculate_relationship_strength(chains) == 1.0

    def test_mixed_types(self):
        chains = [
            [{"relationship_type": "REQUIRES"}],  # 1.0
            [{"relationship_type": "ENABLES"}],  # 0.8
            [{"relationship_type": "PART_OF"}],  # 0.5
            [{"relationship_type": "REFERENCES"}],  # 0.3
        ]
        result = calculate_relationship_strength(chains)
        expected = (1.0 + 0.8 + 0.5 + 0.3) / 4.0
        assert abs(result - expected) < 0.001

    def test_empty_chains(self):
        assert calculate_relationship_strength([]) == 0.0


# ============================================================================
# Recency Score Tests (3 tests)
# ============================================================================


class TestRecencyScore:
    def test_recent_data(self):
        """Data from yesterday should have a score very close to 1.0."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        elements = [{"target_created_at": yesterday}]
        score = calculate_recency_score(elements)
        assert score > 0.95  # 1-day-old data should be ~0.996

    def test_old_data(self):
        """Data from 1 year ago should have a low score."""
        one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
        elements = [{"target_created_at": one_year_ago}]
        score = calculate_recency_score(elements)
        assert score < 0.3  # 365 days → ~0.24 with 180-day half-life

    def test_missing_timestamps(self):
        """Elements without timestamps should return neutral 0.5."""
        elements = [{"source_entity_id": "x"}, {"source_entity_id": "y"}]
        score = calculate_recency_score(elements)
        assert score == 0.5


# ============================================================================
# Multi-Source Bonus Tests (2 tests)
# ============================================================================


class TestMultiSourceBonus:
    def test_single_source(self):
        elements = [
            {
                "edge_source_collection": "legal_unified_hybrid",
                "target_source_collection": "legal_unified_hybrid",
            },
        ]
        bonus, count, sources = calculate_multi_source_bonus(elements)
        assert bonus == 0.0
        assert count == 1

    def test_three_sources(self):
        elements = [
            {
                "edge_source_collection": "legal_unified_hybrid",
                "target_source_collection": "visa_oracle",
            },
            {"edge_source_collection": "tax_genius_hybrid"},
        ]
        bonus, count, sources = calculate_multi_source_bonus(elements)
        assert bonus == 0.15
        assert count == 3
        assert set(sources) == {"legal_unified_hybrid", "visa_oracle", "tax_genius_hybrid"}

    def test_no_sources(self):
        elements = [{"source_entity_id": "x"}]
        bonus, count, sources = calculate_multi_source_bonus(elements)
        assert bonus == 0.0
        assert count == 0


# ============================================================================
# Dynamic Confidence (Composite) Tests (3 tests)
# ============================================================================


class TestDynamicConfidence:
    def test_full_state(self, sample_state, rich_chains):
        """Rich state with 3 chains, entities, intent → high confidence."""
        sample_state["relationship_chains"] = rich_chains
        sample_state["confidence_scores"] = {"kbli:56101": 0.9, "visa:e28a": 0.85}
        sample_state["intent"] = "company_setup"

        breakdown = calculate_dynamic_confidence(sample_state)

        assert breakdown.overall > 0.5
        assert breakdown.chain_base == 0.6  # 3 chains
        assert breakdown.intent_clarity_bonus == 1.0
        assert breakdown.unique_source_count == 3  # 3 collections
        assert breakdown.warning_level in ("high", "medium")

    def test_empty_chains(self, sample_state):
        """Empty state → near-zero overall (only neutral recency contributes)."""
        breakdown = calculate_dynamic_confidence(sample_state)
        # 0.10 * 0.5 (recency neutral) = 0.05 — only non-zero factor
        assert breakdown.overall == 0.05
        assert breakdown.chain_base == 0.0
        assert breakdown.warning_level == "very_low"

    def test_backward_compatible(self, sample_state):
        """Old chain format without enriched fields should work."""
        sample_state["relationship_chains"] = [
            [
                {
                    "source_entity_id": "kbli:56101",
                    "source_name": "Restoran",
                    "source_type": "kbli",
                    "relationship_type": "REQUIRES",
                    "target_entity_id": "doc:nib",
                    "target_name": "NIB",
                    "target_type": "dokumen",
                    "depth": 1,
                    # No edge_confidence, no source_collection, no created_at
                },
            ],
        ]
        sample_state["confidence_scores"] = {"kbli:56101": 0.9}
        sample_state["intent"] = "company_setup"

        breakdown = calculate_dynamic_confidence(sample_state)

        # Should still work — missing fields just contribute neutral scores
        assert breakdown.overall > 0.0
        assert breakdown.chain_base == 0.4  # 1 chain
        assert breakdown.recency_score == 0.5  # neutral (no timestamps)
        assert breakdown.multi_source_bonus == 0.0  # no source_collection keys


# ============================================================================
# Confidence Warning Tests (2 tests)
# ============================================================================


class TestConfidenceWarning:
    def test_high(self):
        level, msg = get_confidence_warning(0.85)
        assert level == "high"
        assert "multiple graph paths" in msg.lower()

    def test_very_low(self):
        level, msg = get_confidence_warning(0.20)
        assert level == "very_low"
        assert "professional" in msg.lower()

    def test_medium(self):
        level, msg = get_confidence_warning(0.60)
        assert level == "medium"

    def test_low(self):
        level, msg = get_confidence_warning(0.40)
        assert level == "low"
        assert "professional" in msg.lower()


# ============================================================================
# Subgraph Confidence Tests
# ============================================================================


class TestSubgraphConfidence:
    def test_company_subgraph_with_db(self):
        breakdown = calculate_subgraph_confidence(
            workflow_source="company_subgraph",
            steps_count=5,
            has_db_validation=True,
            unique_sources=1,
        )
        assert breakdown.overall > 0.6
        assert breakdown.entity_confidence_avg == 0.8  # has_db_validation=True
        assert breakdown.warning_level in ("high", "medium")

    def test_property_subgraph_no_db(self):
        breakdown = calculate_subgraph_confidence(
            workflow_source="property_subgraph",
            steps_count=7,
            has_db_validation=False,
            unique_sources=1,
        )
        assert breakdown.entity_confidence_avg == 0.5  # no DB validation
        assert breakdown.overall > 0.4


# ============================================================================
# Serialization Tests
# ============================================================================


class TestSerialization:
    def test_asdict(self):
        """ConfidenceBreakdown should be serializable via asdict."""
        breakdown = ConfidenceBreakdown(
            overall=0.75, warning_level="medium", warning_message="test",
        )
        d = asdict(breakdown)
        assert isinstance(d, dict)
        assert d["overall"] == 0.75
        assert d["unique_sources"] == []
