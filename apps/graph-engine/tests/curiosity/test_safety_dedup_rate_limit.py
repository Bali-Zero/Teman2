"""Tests for safety mechanisms: dedup, rate limits, blacklist, expiry."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from nuzantara_graph.curiosity.models import (
    GapTopic,
    ResearchEvidence,
)
from nuzantara_graph.curiosity.orchestrator import (
    MAX_GAPS_PER_CYCLE,
    CuriosityOrchestrator,
)


class TestRateLimiting:
    """Test cycle-level rate limiting (MAX_GAPS_PER_CYCLE)."""

    def test_max_gaps_constant_is_20(self) -> None:
        """MAX_GAPS_PER_CYCLE must be 20 (safety limit)."""
        assert MAX_GAPS_PER_CYCLE == 20

    @pytest.mark.asyncio
    async def test_cycle_respects_max_gaps_limit(
        self, sample_coverage_matrix: str, mock_proposal_store: AsyncMock,
    ) -> None:
        """Even with 50+ gaps, cycle should process at most max_gaps."""
        orch = CuriosityOrchestrator(
            proposal_store=mock_proposal_store,
            coverage_matrix_path=sample_coverage_matrix,
        )

        # Track how many times dispatch is called
        dispatch_count = 0
        original_process = orch._process_gap

        async def counting_process(gap, result):
            nonlocal dispatch_count
            dispatch_count += 1
            return await original_process(gap, result)

        with patch.object(orch, "_process_gap", side_effect=counting_process), \
             patch.object(
                 orch.simple, "dispatch",
                 new_callable=AsyncMock,
                 return_value=[ResearchEvidence(content="short", source_type="t", confidence=0.1)],
             ), \
             patch.object(
                 orch.medium, "dispatch",
                 new_callable=AsyncMock,
                 return_value=[ResearchEvidence(content="short", source_type="t", confidence=0.1)],
             ):
            await orch.run_cycle(max_gaps=3)

        assert dispatch_count <= 3


class TestDedupMechanism:
    """Test dedup: same gap proposed twice should be skipped."""

    @pytest.mark.asyncio
    async def test_dedup_prevents_duplicate_proposals(
        self, sample_coverage_matrix: str,
    ) -> None:
        """Second proposal for same gap_id should be skipped."""
        store = AsyncMock()
        store.save = AsyncMock(return_value="id")
        store.expire_stale = AsyncMock(return_value=0)

        # First call: not duplicate. Subsequent: duplicate
        store.is_duplicate = AsyncMock(side_effect=[False, True, True, True, True])
        store.is_blacklisted = AsyncMock(return_value=False)

        orch = CuriosityOrchestrator(
            proposal_store=store,
            coverage_matrix_path=sample_coverage_matrix,
        )

        with patch.object(
            orch.simple, "dispatch",
            new_callable=AsyncMock,
            return_value=[
                ResearchEvidence(
                    content="Detailed content " * 10,
                    source_type="ollama",
                    citations=["PP 1"],
                    confidence=0.8,
                ),
            ],
        ), patch.object(
            orch.medium, "dispatch",
            new_callable=AsyncMock,
            return_value=[
                ResearchEvidence(
                    content="HyDE content " * 10,
                    source_type="hyde",
                    citations=["A"],
                    confidence=0.7,
                ),
            ],
        ):
            result = await orch.run_cycle(max_gaps=5)

        # Only the first non-duplicate gap should create a proposal
        assert result.proposals_created <= 1
        assert result.skipped_dedup >= 1


class TestBlacklist:
    """Test blacklist: gaps rejected 3+ times should be skipped."""

    @pytest.mark.asyncio
    async def test_blacklisted_gaps_are_skipped(
        self, sample_coverage_matrix: str,
    ) -> None:
        """Gaps blacklisted (3+ rejections) should not be processed."""
        store = AsyncMock()
        store.save = AsyncMock(return_value="id")
        store.expire_stale = AsyncMock(return_value=0)
        store.is_duplicate = AsyncMock(return_value=False)
        store.is_blacklisted = AsyncMock(return_value=True)  # All blacklisted

        orch = CuriosityOrchestrator(
            proposal_store=store,
            coverage_matrix_path=sample_coverage_matrix,
        )

        with patch.object(
            orch.simple, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="X" * 200, source_type="ollama", citations=["PP 1"], confidence=0.8)],
        ), patch.object(
            orch.medium, "dispatch",
            new_callable=AsyncMock,
            return_value=[ResearchEvidence(content="X" * 200, source_type="hyde", citations=["A"], confidence=0.7)],
        ):
            result = await orch.run_cycle(max_gaps=10)

        assert result.proposals_created == 0
        assert result.skipped_blacklisted > 0


class TestGracefulDegradation:
    """Test graceful degradation when components fail."""

    @pytest.mark.asyncio
    async def test_cycle_completes_with_dispatcher_errors(
        self, sample_coverage_matrix: str, mock_proposal_store: AsyncMock,
    ) -> None:
        """Cycle should complete even if all dispatchers fail."""
        orch = CuriosityOrchestrator(
            proposal_store=mock_proposal_store,
            coverage_matrix_path=sample_coverage_matrix,
        )

        with patch.object(
            orch.simple, "dispatch",
            new_callable=AsyncMock,
            side_effect=Exception("Ollama down"),
        ), patch.object(
            orch.medium, "dispatch",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            result = await orch.run_cycle(max_gaps=5)

        # Should complete without crashing — dispatch failures are caught
        # inside _dispatch() and return empty evidence, so the grader abstains.
        # This IS graceful degradation: no crash, no proposals, no errors
        # propagated to cycle level.
        assert result.gaps_scanned > 0
        assert result.proposals_created == 0

    @pytest.mark.asyncio
    async def test_cycle_completes_with_store_expire_failure(
        self, sample_coverage_matrix: str,
    ) -> None:
        """Cycle should complete even if expire_stale() fails."""
        store = AsyncMock()
        store.save = AsyncMock(return_value="id")
        store.is_duplicate = AsyncMock(return_value=False)
        store.is_blacklisted = AsyncMock(return_value=False)
        store.expire_stale = AsyncMock(side_effect=Exception("DB connection lost"))

        orch = CuriosityOrchestrator(
            proposal_store=store,
            coverage_matrix_path=sample_coverage_matrix,
        )

        with patch.object(
            orch.simple, "dispatch",
            new_callable=AsyncMock,
            return_value=[
                ResearchEvidence(
                    content="Valid content " * 10,
                    source_type="ollama",
                    citations=["PP 1"],
                    confidence=0.8,
                ),
            ],
        ), patch.object(
            orch.medium, "dispatch",
            new_callable=AsyncMock,
            return_value=[
                ResearchEvidence(
                    content="HyDE content " * 10,
                    source_type="hyde",
                    citations=["A"],
                    confidence=0.7,
                ),
            ],
        ):
            # Should not raise even though expire_stale fails
            result = await orch.run_cycle(max_gaps=5)

        assert result.gaps_scanned > 0
