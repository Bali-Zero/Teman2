"""
Complete test coverage for pipeline module
Target: >95% coverage

This file complements existing tests and adds comprehensive coverage for:
- VerificationStage - all error cases, verification service integration
- PostProcessingStage - error handling, edge cases
- CitationStage - normalization, deduplication, edge cases
- FormatStage - all formatting scenarios
- ResponsePipeline - error handling, stage failures
- create_default_pipeline() - factory function
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.agentic.pipeline import (
    CitationStage,
    FormatStage,
    PipelineStage,
    PostProcessingStage,
    ResponsePipeline,
    VerificationStage,
    create_default_pipeline,
)

# ============================================================================
# TESTS: VerificationStage - Complete Coverage
# ============================================================================


class TestVerificationStageComplete:
    """Complete tests for VerificationStage"""

    def test_verification_stage_default_init(self):
        """Test VerificationStage with default min_response_length"""
        stage = VerificationStage()
        assert stage.min_response_length == 50  # Default value

    def test_verification_stage_custom_init(self):
        """Test VerificationStage with custom min_response_length"""
        stage = VerificationStage(min_response_length=100)
        assert stage.min_response_length == 100

    @pytest.mark.asyncio
    async def test_verification_stage_short_response(self):
        """Test verification skipped for short response"""
        stage = VerificationStage(min_response_length=50)
        data = {"response": "Short", "query": "test", "context_chunks": ["context1", "context2"]}
        result = await stage.process(data)
        assert result["verification_status"] == "skipped"
        assert result["verification_score"] == 1.0

    @pytest.mark.asyncio
    async def test_verification_stage_no_context(self):
        """Test verification skipped when no context"""
        stage = VerificationStage(min_response_length=50)
        data = {
            "response": "This is a longer response that should trigger verification",
            "query": "test",
            "context_chunks": [],
        }
        result = await stage.process(data)
        assert result["verification_status"] == "skipped"
        assert result["verification_score"] == 1.0

    @pytest.mark.asyncio
    async def test_verification_stage_success(self):
        """Test successful verification"""
        stage = VerificationStage(min_response_length=50)

        mock_verification = MagicMock()
        mock_verification.is_valid = True
        mock_verification.status.value = "passed"
        mock_verification.score = 0.95
        mock_verification.reasoning = "Response is well-supported"
        mock_verification.missing_citations = []

        with patch("services.rag.agentic.pipeline.verification_service") as mock_service:
            mock_service.verify_response = AsyncMock(return_value=mock_verification)

            data = {
                "response": "This is a longer response that should trigger verification",
                "query": "test query",
                "context_chunks": ["context1", "context2"],
            }
            result = await stage.process(data)

            assert result["verification_status"] == "passed"
            assert result["verification_score"] == 0.95
            assert result["verification"]["is_valid"] is True
            mock_service.verify_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_verification_stage_value_error(self):
        """Test verification handling ValueError"""
        stage = VerificationStage(min_response_length=50)

        with patch("services.rag.agentic.pipeline.verification_service") as mock_service:
            mock_service.verify_response = AsyncMock(side_effect=ValueError("Invalid input"))

            data = {
                "response": "This is a longer response that should trigger verification",
                "query": "test query",
                "context_chunks": ["context1"],
            }
            result = await stage.process(data)

            assert result["verification_status"] == "error"
            assert result["verification_score"] == 0.5

    @pytest.mark.asyncio
    async def test_verification_stage_runtime_error(self):
        """Test verification handling RuntimeError"""
        stage = VerificationStage(min_response_length=50)

        with patch("services.rag.agentic.pipeline.verification_service") as mock_service:
            mock_service.verify_response = AsyncMock(side_effect=RuntimeError("Service error"))

            data = {
                "response": "This is a longer response that should trigger verification",
                "query": "test query",
                "context_chunks": ["context1"],
            }
            result = await stage.process(data)

            assert result["verification_status"] == "error"
            assert result["verification_score"] == 0.5

    @pytest.mark.asyncio
    async def test_verification_stage_key_error(self):
        """Test verification handling KeyError"""
        stage = VerificationStage(min_response_length=50)

        with patch("services.rag.agentic.pipeline.verification_service") as mock_service:
            mock_service.verify_response = AsyncMock(side_effect=KeyError("Missing key"))

            data = {
                "response": "This is a longer response that should trigger verification",
                "query": "test query",
                "context_chunks": ["context1"],
            }
            result = await stage.process(data)

            assert result["verification_status"] == "error"
            assert result["verification_score"] == 0.5

    @pytest.mark.asyncio
    async def test_verification_stage_exact_min_length(self):
        """Test verification with exact min_response_length"""
        stage = VerificationStage(min_response_length=50)
        data = {
            "response": "x" * 50,  # Exactly 50 chars
            "query": "test",
            "context_chunks": ["context1"],
        }
        result = await stage.process(data)
        # Should trigger verification (not skipped)
        assert "verification" in result or result["verification_status"] != "skipped"

    @pytest.mark.asyncio
    async def test_verification_stage_name_property(self):
        """Test stage name property"""
        stage = VerificationStage()
        assert stage.name == "VerificationStage"


# ============================================================================
# TESTS: PostProcessingStage - Complete Coverage
# ============================================================================


class TestPostProcessingStageComplete:
    """Complete tests for PostProcessingStage"""

    @pytest.mark.asyncio
    async def test_post_processing_stage_empty_response(self):
        """Test PostProcessingStage with empty response"""
        stage = PostProcessingStage()
        data = {"response": "", "query": "test"}
        result = await stage.process(data)
        assert result["response"] == ""

    @pytest.mark.asyncio
    async def test_post_processing_stage_none_response(self):
        """Test PostProcessingStage with None response"""
        stage = PostProcessingStage()
        data = {"response": None, "query": "test"}
        result = await stage.process(data)
        # Should handle None gracefully
        assert "response" in result

    @pytest.mark.asyncio
    async def test_post_processing_stage_value_error(self):
        """Test PostProcessingStage handling ValueError"""
        stage = PostProcessingStage()

        with patch(
            "services.rag.agentic.pipeline.post_process_response", side_effect=ValueError("Invalid")
        ):
            data = {"response": "Test response", "query": "test"}
            result = await stage.process(data)
            # Should keep original response on error
            assert result["response"] == "Test response"

    @pytest.mark.asyncio
    async def test_post_processing_stage_runtime_error(self):
        """Test PostProcessingStage handling RuntimeError"""
        stage = PostProcessingStage()

        with patch(
            "services.rag.agentic.pipeline.post_process_response", side_effect=RuntimeError("Error")
        ):
            data = {"response": "Test response", "query": "test"}
            result = await stage.process(data)
            # Should keep original response on error
            assert result["response"] == "Test response"

    @pytest.mark.asyncio
    async def test_post_processing_stage_success(self):
        """Test successful post-processing"""
        stage = PostProcessingStage()

        with patch(
            "services.rag.agentic.pipeline.post_process_response", return_value="Cleaned response"
        ):
            data = {"response": "Original response with THOUGHT: ...", "query": "test"}
            result = await stage.process(data)
            assert result["response"] == "Cleaned response"

    @pytest.mark.asyncio
    async def test_post_processing_stage_name_property(self):
        """Test stage name property"""
        stage = PostProcessingStage()
        assert stage.name == "PostProcessingStage"


# ============================================================================
# TESTS: CitationStage - Complete Coverage
# ============================================================================


class TestCitationStageComplete:
    """Complete tests for CitationStage"""

    def test_citation_stage_default_init(self):
        """Test CitationStage with default max_citations"""
        stage = CitationStage()
        assert stage.max_citations == 10  # Default value

    def test_citation_stage_custom_init(self):
        """Test CitationStage with custom max_citations"""
        stage = CitationStage(max_citations=5)
        assert stage.max_citations == 5

    @pytest.mark.asyncio
    async def test_citation_stage_no_sources(self):
        """Test CitationStage with no sources"""
        stage = CitationStage()
        data = {"response": "Test", "sources": []}
        result = await stage.process(data)
        assert result["citations"] == []
        assert result["citation_count"] == 0

    @pytest.mark.asyncio
    async def test_citation_stage_missing_sources_key(self):
        """Test CitationStage when sources key is missing"""
        stage = CitationStage()
        data = {"response": "Test"}
        result = await stage.process(data)
        assert result["citations"] == []
        assert result["citation_count"] == 0

    @pytest.mark.asyncio
    async def test_citation_stage_normalize_single(self):
        """Test citation normalization with single source"""
        stage = CitationStage()
        data = {
            "response": "Test",
            "sources": [
                {
                    "title": "Test Document",
                    "url": "https://example.com",
                    "score": 0.9,
                    "collection": "test_collection",
                }
            ],
        }
        result = await stage.process(data)
        assert len(result["citations"]) == 1
        assert result["citations"][0]["title"] == "Test Document"
        assert result["citations"][0]["url"] == "https://example.com"
        assert result["citations"][0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_citation_stage_deduplication(self):
        """Test citation deduplication by (title, url)"""
        stage = CitationStage()
        data = {
            "response": "Test",
            "sources": [
                {"title": "Doc 1", "url": "https://example.com/1", "score": 0.9},
                {"title": "Doc 1", "url": "https://example.com/1", "score": 0.8},  # Duplicate
                {"title": "Doc 2", "url": "https://example.com/2", "score": 0.7},
            ],
        }
        result = await stage.process(data)
        assert len(result["citations"]) == 2  # One duplicate removed
        assert result["citation_count"] == 2

    @pytest.mark.asyncio
    async def test_citation_stage_max_citations_limit(self):
        """Test citation limit enforcement"""
        stage = CitationStage(max_citations=3)
        data = {
            "response": "Test",
            "sources": [
                {"title": f"Doc {i}", "url": f"https://example.com/{i}", "score": 0.9 - i * 0.1}
                for i in range(10)
            ],
        }
        result = await stage.process(data)
        assert len(result["citations"]) == 3
        assert result["citation_count"] == 3

    @pytest.mark.asyncio
    async def test_citation_stage_sorting_by_score(self):
        """Test citations are sorted by score descending"""
        stage = CitationStage()
        data = {
            "response": "Test",
            "sources": [
                {"title": "Low", "url": "https://example.com/1", "score": 0.3},
                {"title": "High", "url": "https://example.com/2", "score": 0.9},
                {"title": "Medium", "url": "https://example.com/3", "score": 0.6},
            ],
        }
        result = await stage.process(data)
        assert result["citations"][0]["title"] == "High"  # Highest score first
        assert result["citations"][1]["title"] == "Medium"
        assert result["citations"][2]["title"] == "Low"

    @pytest.mark.asyncio
    async def test_citation_stage_missing_title(self):
        """Test citation with missing title is skipped"""
        stage = CitationStage()
        data = {
            "response": "Test",
            "sources": [
                {"url": "https://example.com/1", "score": 0.9},  # No title
                {"title": "Valid Doc", "url": "https://example.com/2", "score": 0.8},
            ],
        }
        result = await stage.process(data)
        assert len(result["citations"]) == 1
        assert result["citations"][0]["title"] == "Valid Doc"

    @pytest.mark.asyncio
    async def test_citation_stage_source_url_fallback(self):
        """Test source_url fallback when url is missing"""
        stage = CitationStage()
        data = {
            "response": "Test",
            "sources": [
                {"title": "Test Doc", "source_url": "https://example.com/fallback", "score": 0.9}
            ],
        }
        result = await stage.process(data)
        assert result["citations"][0]["url"] == "https://example.com/fallback"

    @pytest.mark.asyncio
    async def test_citation_stage_non_dict_source(self):
        """Test citation stage skips non-dict sources"""
        stage = CitationStage()
        data = {
            "response": "Test",
            "sources": [
                {"title": "Valid", "url": "https://example.com", "score": 0.9},
                "invalid_string",  # Not a dict
                {"title": "Also Valid", "url": "https://example.com/2", "score": 0.8},
            ],
        }
        result = await stage.process(data)
        assert len(result["citations"]) == 2  # Invalid skipped

    @pytest.mark.asyncio
    async def test_citation_stage_value_error(self):
        """Test CitationStage handling ValueError"""
        stage = CitationStage()

        # Mock _normalize_citations to raise ValueError
        with patch.object(stage, "_normalize_citations", side_effect=ValueError("Invalid")):
            data = {
                "response": "Test",
                "sources": [{"title": "Test", "url": "https://example.com"}],
            }
            result = await stage.process(data)
            assert result["citations"] == []
            assert result["citation_count"] == 0

    @pytest.mark.asyncio
    async def test_citation_stage_key_error(self):
        """Test CitationStage handling KeyError"""
        stage = CitationStage()

        with patch.object(stage, "_normalize_citations", side_effect=KeyError("Missing key")):
            data = {"response": "Test", "sources": [{"title": "Test"}]}
            result = await stage.process(data)
            assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_citation_stage_type_error(self):
        """Test CitationStage handling TypeError"""
        stage = CitationStage()

        with patch.object(stage, "_normalize_citations", side_effect=TypeError("Wrong type")):
            data = {"response": "Test", "sources": [{"title": "Test"}]}
            result = await stage.process(data)
            assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_citation_stage_normalize_with_metadata(self):
        """Test citation normalization includes metadata"""
        stage = CitationStage()
        data = {
            "response": "Test",
            "sources": [
                {
                    "title": "Test Doc",
                    "url": "https://example.com",
                    "score": 0.9,
                    "metadata": {"author": "Test Author", "date": "2024-01-01"},
                }
            ],
        }
        result = await stage.process(data)
        assert result["citations"][0]["metadata"]["author"] == "Test Author"
        assert result["citations"][0]["metadata"]["date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_citation_stage_normalize_with_snippet(self):
        """Test citation normalization includes snippet"""
        stage = CitationStage()
        data = {
            "response": "Test",
            "sources": [
                {
                    "title": "Test Doc",
                    "url": "https://example.com",
                    "score": 0.9,
                    "snippet": "This is a snippet from the document",
                }
            ],
        }
        result = await stage.process(data)
        assert result["citations"][0]["snippet"] == "This is a snippet from the document"

    @pytest.mark.asyncio
    async def test_citation_stage_name_property(self):
        """Test stage name property"""
        stage = CitationStage()
        assert stage.name == "CitationStage"


# ============================================================================
# TESTS: FormatStage - Complete Coverage
# ============================================================================


class TestFormatStageComplete:
    """Complete tests for FormatStage"""

    @pytest.mark.asyncio
    async def test_format_stage_basic(self):
        """Test FormatStage basic formatting"""
        stage = FormatStage()
        data = {"response": "  Test response  ", "query": "test"}
        result = await stage.process(data)
        assert result["response"] == "Test response"  # Stripped
        assert result["pipeline_version"] == "1.0"
        assert "stages_completed" in result

    @pytest.mark.asyncio
    async def test_format_stage_no_citations_key(self):
        """Test FormatStage adds citations key if missing"""
        stage = FormatStage()
        data = {"response": "Test", "query": "test"}
        result = await stage.process(data)
        assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_format_stage_existing_citations(self):
        """Test FormatStage preserves existing citations"""
        stage = FormatStage()
        data = {"response": "Test", "query": "test", "citations": [{"title": "Doc 1"}]}
        result = await stage.process(data)
        assert len(result["citations"]) == 1

    @pytest.mark.asyncio
    async def test_format_stage_stages_completed(self):
        """Test FormatStage adds to stages_completed"""
        stage = FormatStage()
        data = {
            "response": "Test",
            "query": "test",
            "stages_completed": ["VerificationStage", "PostProcessingStage"],
        }
        result = await stage.process(data)
        assert "FormatStage" in result["stages_completed"]
        assert len(result["stages_completed"]) == 3

    @pytest.mark.asyncio
    async def test_format_stage_no_stages_completed(self):
        """Test FormatStage creates stages_completed if missing"""
        stage = FormatStage()
        data = {"response": "Test", "query": "test"}
        result = await stage.process(data)
        assert "FormatStage" in result["stages_completed"]

    @pytest.mark.asyncio
    async def test_format_stage_name_property(self):
        """Test stage name property"""
        stage = FormatStage()
        assert stage.name == "FormatStage"


# ============================================================================
# TESTS: ResponsePipeline - Complete Coverage
# ============================================================================


class TestResponsePipelineComplete:
    """Complete tests for ResponsePipeline"""

    def test_response_pipeline_init(self):
        """Test ResponsePipeline initialization"""
        stages = [VerificationStage(), PostProcessingStage()]
        pipeline = ResponsePipeline(stages=stages)
        assert len(pipeline.stages) == 2

    def test_response_pipeline_init_empty_stages(self):
        """Test ResponsePipeline with empty stages list"""
        pipeline = ResponsePipeline(stages=[])
        assert len(pipeline.stages) == 0

    @pytest.mark.asyncio
    async def test_response_pipeline_process_success(self):
        """Test successful pipeline processing"""
        stage1 = MagicMock(spec=PipelineStage)
        stage1.name = "Stage1"
        stage1.process = AsyncMock(return_value={"response": "processed1", "stages_completed": []})

        stage2 = MagicMock(spec=PipelineStage)
        stage2.name = "Stage2"
        stage2.process = AsyncMock(
            return_value={"response": "processed2", "stages_completed": ["Stage1"]}
        )

        pipeline = ResponsePipeline(stages=[stage1, stage2])
        data = {"response": "original", "query": "test"}
        result = await pipeline.process(data)

        assert "stages_completed" in result
        assert len(result["stages_completed"]) == 2
        stage1.process.assert_called_once()
        stage2.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_pipeline_process_none_data(self):
        """Test pipeline raises ValueError for None data"""
        pipeline = ResponsePipeline(stages=[])
        with pytest.raises(ValueError, match="Pipeline data cannot be None"):
            await pipeline.process(None)

    @pytest.mark.asyncio
    async def test_response_pipeline_stage_failure_value_error(self):
        """Test pipeline continues when stage raises ValueError"""
        stage1 = MagicMock(spec=PipelineStage)
        stage1.name = "Stage1"
        stage1.process = AsyncMock(side_effect=ValueError("Stage error"))

        stage2 = MagicMock(spec=PipelineStage)
        stage2.name = "Stage2"

        async def stage2_process(data):
            return data

        stage2.process = stage2_process

        pipeline = ResponsePipeline(stages=[stage1, stage2])
        data = {"response": "original", "query": "test"}
        result = await pipeline.process(data)

        # Pipeline adds Stage1 (failed) and then Stage2
        assert "Stage1 (failed)" in result["stages_completed"]
        assert "Stage2" in result["stages_completed"]
        assert len(result["stages_completed"]) >= 2

    @pytest.mark.asyncio
    async def test_response_pipeline_stage_failure_runtime_error(self):
        """Test pipeline continues when stage raises RuntimeError"""
        stage1 = MagicMock(spec=PipelineStage)
        stage1.name = "Stage1"
        stage1.process = AsyncMock(side_effect=RuntimeError("Runtime error"))

        stage2 = MagicMock(spec=PipelineStage)
        stage2.name = "Stage2"

        async def stage2_process(data):
            # Don't modify stages_completed - pipeline handles it
            return data

        stage2.process = stage2_process

        pipeline = ResponsePipeline(stages=[stage1, stage2])
        data = {"response": "original", "query": "test"}
        result = await pipeline.process(data)

        assert "Stage1 (failed)" in result["stages_completed"]
        assert "Stage2" in result["stages_completed"]
        assert len(result["stages_completed"]) >= 2

    @pytest.mark.asyncio
    async def test_response_pipeline_stage_failure_key_error(self):
        """Test pipeline continues when stage raises KeyError"""
        stage1 = MagicMock(spec=PipelineStage)
        stage1.name = "Stage1"
        stage1.process = AsyncMock(side_effect=KeyError("Missing key"))

        stage2 = MagicMock(spec=PipelineStage)
        stage2.name = "Stage2"

        async def stage2_process(data):
            return data

        stage2.process = stage2_process

        pipeline = ResponsePipeline(stages=[stage1, stage2])
        data = {"response": "original", "query": "test"}
        result = await pipeline.process(data)

        assert "Stage1 (failed)" in result["stages_completed"]
        assert "Stage2" in result["stages_completed"]
        assert len(result["stages_completed"]) >= 2

    @pytest.mark.asyncio
    async def test_response_pipeline_stage_failure_type_error(self):
        """Test pipeline continues when stage raises TypeError"""
        stage1 = MagicMock(spec=PipelineStage)
        stage1.name = "Stage1"
        stage1.process = AsyncMock(side_effect=TypeError("Wrong type"))

        stage2 = MagicMock(spec=PipelineStage)
        stage2.name = "Stage2"

        async def stage2_process(data):
            return data

        stage2.process = stage2_process

        pipeline = ResponsePipeline(stages=[stage1, stage2])
        data = {"response": "original", "query": "test"}
        result = await pipeline.process(data)

        assert "Stage1 (failed)" in result["stages_completed"]
        assert "Stage2" in result["stages_completed"]
        assert len(result["stages_completed"]) >= 2

    @pytest.mark.asyncio
    async def test_response_pipeline_all_stages_fail(self):
        """Test pipeline when all stages fail"""
        stage1 = MagicMock(spec=PipelineStage)
        stage1.name = "Stage1"
        stage1.process = AsyncMock(side_effect=ValueError("Error 1"))

        stage2 = MagicMock(spec=PipelineStage)
        stage2.name = "Stage2"
        stage2.process = AsyncMock(side_effect=RuntimeError("Error 2"))

        pipeline = ResponsePipeline(stages=[stage1, stage2])
        data = {"response": "original", "query": "test"}
        result = await pipeline.process(data)

        # Should still complete with failed markers
        assert len(result["stages_completed"]) == 2
        assert "Stage1 (failed)" in result["stages_completed"]
        assert "Stage2 (failed)" in result["stages_completed"]

    @pytest.mark.asyncio
    async def test_response_pipeline_empty_stages(self):
        """Test pipeline with no stages"""
        pipeline = ResponsePipeline(stages=[])
        data = {"response": "original", "query": "test"}
        result = await pipeline.process(data)

        assert result["stages_completed"] == []
        assert result["response"] == "original"


# ============================================================================
# TESTS: create_default_pipeline()
# ============================================================================


class TestCreateDefaultPipeline:
    """Test create_default_pipeline() factory function"""

    def test_create_default_pipeline(self):
        """Test creating default pipeline"""
        pipeline = create_default_pipeline()
        assert isinstance(pipeline, ResponsePipeline)
        assert len(pipeline.stages) == 4

    def test_create_default_pipeline_stages_order(self):
        """Test default pipeline stages are in correct order"""
        pipeline = create_default_pipeline()
        stage_names = [stage.name for stage in pipeline.stages]
        assert stage_names == [
            "VerificationStage",
            "PostProcessingStage",
            "CitationStage",
            "FormatStage",
        ]

    def test_create_default_pipeline_verification_config(self):
        """Test VerificationStage configuration in default pipeline"""
        pipeline = create_default_pipeline()
        verification_stage = pipeline.stages[0]
        assert isinstance(verification_stage, VerificationStage)
        assert verification_stage.min_response_length == 50

    def test_create_default_pipeline_citation_config(self):
        """Test CitationStage configuration in default pipeline"""
        pipeline = create_default_pipeline()
        citation_stage = pipeline.stages[2]
        assert isinstance(citation_stage, CitationStage)
        assert citation_stage.max_citations == 10


# ============================================================================
# TESTS: PipelineStage Base Class
# ============================================================================


class TestPipelineStageBase:
    """Test PipelineStage abstract base class"""

    def test_pipeline_stage_is_abstract(self):
        """Test PipelineStage cannot be instantiated directly"""
        with pytest.raises(TypeError):
            PipelineStage()  # Abstract class

    def test_pipeline_stage_name_property(self):
        """Test PipelineStage name property returns class name"""

        # Create concrete implementation
        class TestStage(PipelineStage):
            async def process(self, data):
                return data

        stage = TestStage()
        assert stage.name == "TestStage"
