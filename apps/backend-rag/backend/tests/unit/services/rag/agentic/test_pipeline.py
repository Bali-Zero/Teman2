"""
Unit tests for pipeline module
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.agentic.pipeline import (
    CitationStage,
    FormatStage,
    PostProcessingStage,
    ResponsePipeline,
    VerificationStage,
)


class TestPipelineStages:
    """Tests for pipeline stages"""

    def test_verification_stage_init(self):
        """Test VerificationStage initialization"""
        stage = VerificationStage(min_response_length=50)
        assert stage.min_response_length == 50

    @pytest.mark.asyncio
    async def test_verification_stage_process_short_response(self):
        """Test VerificationStage with short response"""
        stage = VerificationStage(min_response_length=50)
        data = {"response": "Short", "query": "test", "context_chunks": []}
        result = await stage.process(data)
        assert result["verification_status"] == "skipped"

    @pytest.mark.asyncio
    async def test_verification_stage_process_no_context(self):
        """Test VerificationStage with no context"""
        stage = VerificationStage(min_response_length=50)
        data = {
            "response": "This is a longer response that should trigger verification",
            "query": "test",
            "context_chunks": [],
        }
        result = await stage.process(data)
        assert result["verification_status"] == "skipped"

    @pytest.mark.asyncio
    async def test_post_processing_stage(self):
        """Test PostProcessingStage"""
        stage = PostProcessingStage()
        data = {"response": "Test response with [citation:1]", "query": "test"}
        result = await stage.process(data)
        assert isinstance(result, dict)
        assert "response" in result

    @pytest.mark.asyncio
    async def test_citation_stage(self):
        """Test CitationStage"""
        stage = CitationStage()
        data = {"response": "Test response", "sources": [{"id": "1", "text": "Source 1"}]}
        result = await stage.process(data)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_format_stage(self):
        """Test FormatStage"""
        stage = FormatStage()
        data = {"response": "Test response", "query": "test"}
        result = await stage.process(data)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_response_pipeline(self):
        """Test ResponsePipeline"""
        # Check if ResponsePipeline requires stages parameter
        try:
            pipeline = ResponsePipeline(stages=[])
            data = {"response": "Test response", "query": "test", "context_chunks": []}
            result = await pipeline.process(data)
            assert isinstance(result, dict)
        except TypeError:
            # If it requires stages, create with default stages
            stages = [VerificationStage(), PostProcessingStage(), CitationStage(), FormatStage()]
            pipeline = ResponsePipeline(stages=stages)
            data = {"response": "Test response", "query": "test", "context_chunks": []}
            result = await pipeline.process(data)
            assert isinstance(result, dict)
