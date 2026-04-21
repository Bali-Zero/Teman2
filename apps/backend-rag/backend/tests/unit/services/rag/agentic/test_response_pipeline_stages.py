"""
Wave 3 unit tests for ResponsePipeline sub-machine.

Scope: `backend/services/rag/agentic/pipeline.py`.
Focus: per-stage contracts + pipeline-level invariants (I-P1..I-P7) from
RESPONSE_PIPELINE.md. Each test keyed to a stage or invariant ID.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.pipeline import (
    CitationStage,
    FormatStage,
    PipelineStage,
    PostProcessingStage,
    ResponsePipeline,
    VerificationStage,
    create_default_pipeline,
)


# ============================================================================
# Group 1 — Pipeline.process None handling (I-P1)
# ============================================================================


@pytest.mark.asyncio
class TestPipelineNoneHandling:

    async def test_pipeline_process_none_data_raises_value_error(self):
        """I-P1: `None` input raises ValueError synchronously — callers can
        rely on "if I got a return, it's a dict".
        """
        pipeline = ResponsePipeline(stages=[FormatStage()])
        with pytest.raises(ValueError, match="Pipeline data cannot be None"):
            await pipeline.process(None)  # type: ignore[arg-type]


# ============================================================================
# Group 2 — VerificationStage skip & error (I-P6, error path)
# ============================================================================


@pytest.mark.asyncio
class TestVerificationStage:

    async def test_verification_short_response_skips_and_marks_status_skipped(self):
        """VerificationStage + I-P6: response < 50 chars → status='skipped',
        score=1.0, verification_service NOT called.
        """
        stage = VerificationStage(min_response_length=50)
        data = {
            "response": "too short",  # 9 chars
            "query": "q",
            "context_chunks": ["some context"],
        }

        # If verification_service is called we want to know — patch it
        with patch(
            "backend.services.rag.agentic.pipeline.verification_service",
        ) as mock_svc:
            mock_svc.verify_response = AsyncMock()
            result = await stage.process(data)

        assert result["verification_score"] == 1.0
        assert result["verification_status"] == "skipped"
        mock_svc.verify_response.assert_not_called()

    async def test_verification_service_raise_yields_error_status_and_half_score(self):
        """VerificationStage error path: verify_response raises ValueError →
        score=0.5, status='error'. No unhandled raise escapes.
        """
        stage = VerificationStage(min_response_length=50)
        data = {
            "response": "a" * 100,  # long enough
            "query": "q",
            "context_chunks": ["some context chunk"],
        }

        with patch(
            "backend.services.rag.agentic.pipeline.verification_service",
        ) as mock_svc:
            mock_svc.verify_response = AsyncMock(side_effect=ValueError("verify blew up"))
            result = await stage.process(data)

        # Error path
        assert result["verification_score"] == 0.5
        assert result["verification_status"] == "error"
        # No `verification` dict populated (the happy-path-only field)
        assert "verification" not in result


# ============================================================================
# Group 3 — PostProcessingStage empty response (skip path)
# ============================================================================


@pytest.mark.asyncio
class TestPostProcessingStage:

    async def test_postprocessing_empty_response_is_noop(self):
        """PostProcessingStage skip: empty response → post_process_response
        NOT called, data["response"] unchanged (remains empty string).
        """
        stage = PostProcessingStage()
        data = {"response": "", "query": "q"}

        with patch(
            "backend.services.rag.agentic.pipeline.post_process_response",
        ) as mock_ppr:
            result = await stage.process(data)

        mock_ppr.assert_not_called()
        assert result["response"] == ""


# ============================================================================
# Group 4 — CitationStage normalize/dedupe/sort/trim (happy path + filter)
# ============================================================================


@pytest.mark.asyncio
class TestCitationStage:

    async def test_citation_normalize_dedupes_sorts_and_trims(self):
        """CitationStage happy path: 3 sources (two identical + one distinct
        + varied scores) → dedupe on (title,url), sort by score desc, trim
        to max_citations=2.
        """
        stage = CitationStage(max_citations=2)
        data = {
            "sources": [
                {"title": "Pasal 1", "url": "https://x", "score": 0.5, "snippet": "low"},
                {"title": "Pasal 2", "url": "https://y", "score": 0.9, "snippet": "hi"},
                # duplicate of first (same title + url) with different score → dedupe wins
                {"title": "Pasal 1", "url": "https://x", "score": 0.95, "snippet": "dup"},
                {"title": "Pasal 3", "url": "https://z", "score": 0.7, "snippet": "mid"},
            ],
        }

        result = await stage.process(data)

        citations = result["citations"]
        # Sort by score descending + trim to 2 (I-P7 uses float coercion)
        assert len(citations) == 2
        assert citations[0]["score"] > citations[1]["score"]
        # Dedupe keeps FIRST occurrence (score 0.5 kept, 0.95 dropped per
        # `seen.add(key)` in `_normalize_citations`). After dedupe,
        # candidate scores are: Pasal 1 (0.5), Pasal 2 (0.9), Pasal 3 (0.7).
        # Sort desc + trim to 2 → Pasal 2 (0.9) + Pasal 3 (0.7). Pasal 1 gone.
        top_titles = {c["title"] for c in citations}
        assert top_titles == {"Pasal 2", "Pasal 3"}
        # Pasal 1 filtered out by trim (was lowest score post-dedupe)
        assert not any(c["title"] == "Pasal 1" for c in citations)
        assert result["citation_count"] == 2

    async def test_citation_missing_title_filtered_out(self):
        """CitationStage filter: entries with no title, non-dict entries,
        and empty-title entries are filtered out. Only valid titled sources
        emerge.
        """
        stage = CitationStage(max_citations=10)
        data = {
            "sources": [
                {"title": "Valid", "url": "https://x", "score": 0.5},
                {},  # no title
                {"title": ""},  # empty title — falsy, filtered
                "not a dict",  # non-dict → skipped
                {"url": "missing.title"},  # no title key
            ],
        }

        result = await stage.process(data)

        citations = result["citations"]
        assert len(citations) == 1
        assert citations[0]["title"] == "Valid"


# ============================================================================
# Group 5 — FormatStage ensures citations + strips response (I-P5)
# ============================================================================


@pytest.mark.asyncio
class TestFormatStage:

    async def test_format_stage_ensures_citations_list_present(self):
        """FormatStage + I-P5: data without 'citations' key → FormatStage
        guarantees data["citations"] = []. Also strips whitespace from
        response and adds pipeline_version.
        """
        stage = FormatStage()
        data = {"response": "  final text  "}  # no citations key

        result = await stage.process(data)

        # Stripped
        assert result["response"] == "final text"
        # Citations ensured
        assert result["citations"] == []
        # Pipeline version set
        assert result["pipeline_version"] == "1.0"
        # stages_completed updated
        assert "FormatStage" in result["stages_completed"]


# ============================================================================
# Group 6 — Chain continues on stage failure (I-P2 + I-P3)
# ============================================================================


class _RaisingStage(PipelineStage):
    """Test-only stage that raises ValueError to simulate a mid-chain failure."""

    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("stage blew up intentionally")


class _MarkerStage(PipelineStage):
    """Test-only stage that sets a marker in data."""

    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        data["marker"] = "AFTER_RAISE"
        return data


@pytest.mark.asyncio
class TestChainContinuesOnFailure:

    async def test_stage_raise_does_not_abort_chain_marks_failed(self):
        """I-P2 + I-P3: mid-chain stage raise caught at pipeline level.
        stages_completed contains "<Name> (failed)". Next stage still runs.
        """
        pipeline = ResponsePipeline(stages=[_RaisingStage(), _MarkerStage()])

        result = await pipeline.process({"initial": True})

        # The raising stage is recorded as "(failed)"
        stages = result["stages_completed"]
        assert any("_RaisingStage (failed)" in s for s in stages), \
            f"Expected '_RaisingStage (failed)' in stages_completed: {stages}"
        # Second stage still ran — marker present
        assert result.get("marker") == "AFTER_RAISE"
        # Second stage recorded as success (no "(failed)" suffix)
        assert "_MarkerStage" in stages
        assert "_MarkerStage (failed)" not in stages


# ============================================================================
# Group 7 — Default pipeline cardinality (I-P4)
# ============================================================================


@pytest.mark.asyncio
class TestDefaultPipelineCardinality:

    async def test_default_pipeline_has_four_stages_in_fixed_order(self):
        """I-P4: create_default_pipeline → exactly 4 stages, in
        [Verification, PostProcessing, Citation, Format] order.
        """
        pipeline = create_default_pipeline()
        names = [s.name for s in pipeline.stages]
        assert names == [
            "VerificationStage",
            "PostProcessingStage",
            "CitationStage",
            "FormatStage",
        ]
