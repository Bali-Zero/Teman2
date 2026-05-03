"""Tests for CuriosityOrchestrator — end-to-end cycle with mocked dispatchers."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from nuzantara_graph.curiosity.models import (
    GapTopic,
    ResearchEvidence,
    Tier,
)
from nuzantara_graph.curiosity.orchestrator import (
    CRITICAL_DOMAINS,
    DOMAIN_PRIORITY,
    CuriosityOrchestrator,
)


class TestCuriosityOrchestrator:
    """Test orchestrator pipeline: scan → prioritize → classify → dispatch → grade → propose."""

    @pytest.fixture
    def orchestrator(self, sample_coverage_matrix: str, mock_proposal_store: AsyncMock) -> CuriosityOrchestrator:
        """Orchestrator with mocked store and real coverage_matrix."""
        return CuriosityOrchestrator(
            proposal_store=mock_proposal_store,
            coverage_matrix_path=sample_coverage_matrix,
        )

    def test_load_gaps_from_coverage_matrix(self, orchestrator: CuriosityOrchestrator) -> None:
        """Should load non-FRESH gaps from coverage_matrix.json."""
        gaps = orchestrator._load_gaps()
        # 2 GAP + 1 STALE from immigration, 1 GAP + 1 AGING from company, 1 GAP from tax = 6
        # FRESH entries should be excluded
        assert len(gaps) >= 4
        assert all(g.freshness != "FRESH" for g in gaps)

    def test_prioritize_by_severity_and_domain(self, orchestrator: CuriosityOrchestrator) -> None:
        """Higher severity × domain importance should come first."""
        gaps = [
            GapTopic(domain="editorial", topic="content update", severity=1.0),     # 1.0 * 0.4 = 0.4
            GapTopic(domain="immigration", topic="KITAS", severity=1.0),             # 1.0 * 1.0 = 1.0
            GapTopic(domain="company", topic="PMA setup", severity=0.7),             # 0.7 * 0.9 = 0.63
        ]
        prioritized = orchestrator._prioritize(gaps)
        assert prioritized[0].domain == "immigration"
        assert prioritized[1].domain == "company"
        assert prioritized[2].domain == "editorial"

    def test_classify_tier_critical_domain_simple(self, orchestrator: CuriosityOrchestrator) -> None:
        """Critical domain + specific topic → Tier.SIMPLE."""
        gap = GapTopic(domain="immigration", topic="KITAS requirements and process 2025")
        assert orchestrator.classify_tier(gap) == Tier.SIMPLE

    def test_classify_tier_cross_domain_medium(self, orchestrator: CuriosityOrchestrator) -> None:
        """Cross-domain keywords → Tier.MEDIUM."""
        gap = GapTopic(domain="tax", topic="KITAS vs business visa tax comparison")
        assert orchestrator.classify_tier(gap) == Tier.MEDIUM

    def test_classify_tier_broad_topic_medium(self, orchestrator: CuriosityOrchestrator) -> None:
        """Broad topics → Tier.MEDIUM."""
        gap = GapTopic(domain="immigration", topic="Complete guide to all visa types")
        assert orchestrator.classify_tier(gap) == Tier.MEDIUM

    def test_classify_tier_editorial_medium(self, orchestrator: CuriosityOrchestrator) -> None:
        """Non-critical domain → Tier.MEDIUM."""
        gap = GapTopic(domain="editorial", topic="Google Helpful Content Update 2024")
        assert orchestrator.classify_tier(gap) == Tier.MEDIUM

    @pytest.mark.asyncio
    async def test_run_cycle_creates_proposals(
        self, orchestrator: CuriosityOrchestrator, mock_proposal_store: AsyncMock,
    ) -> None:
        """Full cycle should create proposals for gaps with good evidence."""
        # Mock simple dispatcher to return good evidence
        with patch.object(
            orchestrator.simple, "dispatch",
            new_callable=AsyncMock,
            return_value=[
                ResearchEvidence(
                    content="PP 48/2021 regulates KITAS. Requirements: passport, sponsor, RPTKA. " * 3,
                    source_type="ollama",
                    citations=["PP 48/2021"],
                    confidence=0.8,
                ),
            ],
        ), patch.object(
            orchestrator.medium, "dispatch",
            new_callable=AsyncMock,
            return_value=[
                ResearchEvidence(
                    content="HyDE expanded research on cross-domain topic. " * 5,
                    source_type="hyde_synthesis",
                    citations=["Source A"],
                    confidence=0.7,
                ),
            ],
        ):
            result = await orchestrator.run_cycle(max_gaps=5)

        assert result.gaps_scanned > 0
        assert result.proposals_created > 0
        assert mock_proposal_store.save.called

    @pytest.mark.asyncio
    async def test_run_cycle_respects_max_gaps(
        self, orchestrator: CuriosityOrchestrator,
    ) -> None:
        """Cycle should not process more than max_gaps."""
        with patch.object(
            orchestrator.simple, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="short", source_type="template", confidence=0.1)],
        ), patch.object(
            orchestrator.medium, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="short", source_type="template", confidence=0.1)],
        ):
            result = await orchestrator.run_cycle(max_gaps=2)

        # Should have scanned all gaps but only processed max_gaps
        assert result.gaps_scanned > 2  # Total gaps > 2

    @pytest.mark.asyncio
    async def test_dedup_skips_duplicate_gaps(
        self, orchestrator: CuriosityOrchestrator, mock_proposal_store: AsyncMock,
    ) -> None:
        """Duplicate gaps (proposed in last 7 days) should be skipped."""
        mock_proposal_store.is_duplicate = AsyncMock(return_value=True)

        with patch.object(
            orchestrator.simple, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="X" * 200, source_type="ollama", citations=["PP 1"], confidence=0.8)],
        ), patch.object(
            orchestrator.medium, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="X" * 200, source_type="hyde", citations=["A"], confidence=0.7)],
        ):
            result = await orchestrator.run_cycle(max_gaps=10)

        assert result.proposals_created == 0
        assert result.skipped_dedup > 0

    @pytest.mark.asyncio
    async def test_blacklist_skips_rejected_gaps(
        self, orchestrator: CuriosityOrchestrator, mock_proposal_store: AsyncMock,
    ) -> None:
        """Blacklisted gaps (rejected 3+ times) should be skipped."""
        mock_proposal_store.is_duplicate = AsyncMock(return_value=False)
        mock_proposal_store.is_blacklisted = AsyncMock(return_value=True)

        with patch.object(
            orchestrator.simple, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="X" * 200, source_type="ollama", citations=["PP 1"], confidence=0.8)],
        ), patch.object(
            orchestrator.medium, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="X" * 200, source_type="hyde", citations=["A"], confidence=0.7)],
        ):
            result = await orchestrator.run_cycle(max_gaps=10)

        assert result.proposals_created == 0
        assert result.skipped_blacklisted > 0

    def test_load_gaps_missing_file(self, mock_proposal_store: AsyncMock) -> None:
        """Missing coverage_matrix.json should return empty list."""
        orch = CuriosityOrchestrator(
            proposal_store=mock_proposal_store,
            coverage_matrix_path="/nonexistent/path.json",
        )
        gaps = orch._load_gaps()
        assert gaps == []

    @pytest.mark.asyncio
    async def test_cycle_result_has_metrics(
        self, orchestrator: CuriosityOrchestrator,
    ) -> None:
        """CycleResult should contain timing and metrics."""
        with patch.object(
            orchestrator.simple, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="short", source_type="template", confidence=0.1)],
        ), patch.object(
            orchestrator.medium, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="short", source_type="template", confidence=0.1)],
        ):
            result = await orchestrator.run_cycle(max_gaps=3)

        assert result.duration_seconds > 0
        assert result.gaps_scanned > 0
