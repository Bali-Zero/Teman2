"""
NUZANTARA RAG - RAGAS Evaluator Tests

Comprehensive test suite for RAGASEvaluator covering:
- Individual metric evaluation
- Full evaluation pipeline
- Caching behavior
- Integration with LLM providers
- Mock-based deterministic tests
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.llm.base import LLMResponse
from backend.services.rag.evaluation.ragas_evaluator import (
    ANSWER_RELEVANCE_PROMPT,
    CONTEXT_ENTITY_RECALL_PROMPT,
    CONTEXT_PRECISION_PROMPT,
    CONTEXT_RECALL_PROMPT,
    FAITHFULNESS_PROMPT,
    EvaluationResult,
    RAGASEvaluator,
    get_ragas_evaluator,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_llm_response():
    """Create mock LLM response with evaluation result."""

    def _create_response(score: float = 0.85, reasoning: str = "Test reasoning"):
        content = json.dumps(
            {
                "score": score,
                "reasoning": reasoning,
                "supported_statements": ["statement 1"],
                "unsupported_statements": [],
            },
        )
        return LLMResponse(
            content=content,
            model="gemini-2.0-flash",
            provider="gemini",
        )

    return _create_response


@pytest.fixture
def mock_llm_client(mock_llm_response):
    """Create mock LLM client."""
    client = MagicMock()
    client.generate = AsyncMock(return_value=mock_llm_response(score=0.85))
    return client


@pytest.fixture
def evaluator(mock_llm_client):
    """Create RAGAS evaluator with mock client."""
    return RAGASEvaluator(llm_client=mock_llm_client, enable_cache=False)


@pytest.fixture
def sample_query():
    """Sample query for testing."""
    return "Apa itu KITAS dan apa persyaratannya?"


@pytest.fixture
def sample_context():
    """Sample context for testing."""
    return [
        "KITAS (Kartu Izin Tinggal Terbatas) adalah izin tinggal untuk WNA di Indonesia.",
        "Persyaratan KITAS meliputi: paspor, foto, surat rekomendasi, dan biaya.",
    ]


@pytest.fixture
def sample_answer():
    """Sample answer for testing."""
    return (
        "KITAS adalah Kartu Izin Tinggal Terbatas untuk WNA di Indonesia. "
        "Persyaratannya meliputi paspor, foto, dan surat rekomendasi."
    )


@pytest.fixture
def sample_ground_truth():
    """Sample ground truth for testing."""
    return (
        "KITAS (Kartu Izin Tinggal Terbatas) adalah dokumen izin tinggal "
        "yang diberikan kepada WNA untuk tinggal di Indonesia dalam jangka waktu tertentu."
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestEvaluatorInitialization:
    """Tests for RAGASEvaluator initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        with patch(
            "backend.services.rag.evaluation.ragas_evaluator.create_default_client",
        ) as mock_create:
            mock_client = MagicMock()
            mock_create.return_value = mock_client

            evaluator = RAGASEvaluator()

            assert evaluator.enable_cache is True
            assert evaluator.cache_ttl == 86400
            assert evaluator._eval_count == 0

    def test_init_with_custom_params(self, mock_llm_client):
        """Test initialization with custom parameters."""
        evaluator = RAGASEvaluator(
            llm_client=mock_llm_client,
            enable_cache=False,
            cache_ttl=3600,
        )

        assert evaluator.llm_client is mock_llm_client
        assert evaluator.enable_cache is False
        assert evaluator.cache_ttl == 3600

    def test_init_creates_empty_cache(self, mock_llm_client):
        """Test that cache is initialized empty."""
        evaluator = RAGASEvaluator(llm_client=mock_llm_client)

        assert evaluator._cache == {}
        assert evaluator._cache_hit_count == 0


# =============================================================================
# Cache Tests
# =============================================================================


class TestEvaluatorCaching:
    """Tests for evaluation result caching."""

    def test_cache_key_generation(self, evaluator):
        """Test cache key generation is deterministic."""
        key1 = evaluator._get_cache_key("query", ["ctx1", "ctx2"], "answer", "metric")
        key2 = evaluator._get_cache_key("query", ["ctx1", "ctx2"], "answer", "metric")

        assert key1 == key2
        assert len(key1) == 32  # SHA256 hex digest length

    def test_cache_key_unique_per_content(self, evaluator):
        """Test cache keys are unique for different content."""
        key1 = evaluator._get_cache_key("query1", ["ctx"], "answer", "metric")
        key2 = evaluator._get_cache_key("query2", ["ctx"], "answer", "metric")

        assert key1 != key2

    def test_get_cached_result_when_disabled(self, evaluator):
        """Test cache retrieval when caching is disabled."""
        evaluator.enable_cache = False
        evaluator._cache["key"] = {"result": {"score": 0.9}, "timestamp": 9999999999}

        result = evaluator._get_cached_result("key")

        assert result is None

    def test_get_cached_result_valid(self, evaluator):
        """Test retrieval of valid cached result."""
        evaluator.enable_cache = True
        cached_data = {"score": 0.9, "reasoning": "test"}
        evaluator._cache["key"] = {"result": cached_data, "timestamp": 9999999999}

        result = evaluator._get_cached_result("key")

        assert result == cached_data
        assert evaluator._cache_hit_count == 1

    def test_get_cached_result_expired(self, evaluator):
        """Test that expired cache entries are removed."""
        evaluator.enable_cache = True
        evaluator.cache_ttl = 100  # 100 seconds
        evaluator._cache["key"] = {"result": {"score": 0.9}, "timestamp": 0}

        result = evaluator._get_cached_result("key")

        assert result is None
        assert "key" not in evaluator._cache

    def test_cache_result(self, evaluator):
        """Test storing result in cache."""
        evaluator.enable_cache = True
        result_data = {"score": 0.9, "reasoning": "test"}

        evaluator._cache_result("key", result_data)

        assert "key" in evaluator._cache
        assert evaluator._cache["key"]["result"] == result_data
        assert "timestamp" in evaluator._cache["key"]

    def test_clear_cache(self, evaluator):
        """Test clearing the cache."""
        evaluator.enable_cache = True
        evaluator._cache["key1"] = {"result": {}, "timestamp": 0}
        evaluator._cache["key2"] = {"result": {}, "timestamp": 0}
        evaluator._cache_hit_count = 5

        evaluator.clear_cache()

        assert evaluator._cache == {}
        assert evaluator._cache_hit_count == 0


# =============================================================================
# LLM Call Tests
# =============================================================================


class TestLLMCalls:
    """Tests for LLM evaluation calls."""

    @pytest.mark.asyncio
    async def test_call_llm_evaluator_success(self, evaluator, mock_llm_client):
        """Test successful LLM evaluation call."""
        expected_response = {
            "score": 0.85,
            "reasoning": "Good answer",
            "supported_statements": ["stmt1"],
        }
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps(expected_response),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator._call_llm_evaluator("test prompt")

        assert result["score"] == 0.85
        assert result["reasoning"] == "Good answer"
        # Verify correct message format
        call_args = mock_llm_client.generate.call_args
        assert call_args[1]["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_call_llm_evaluator_with_code_block(self, evaluator, mock_llm_client):
        """Test parsing LLM response with markdown code block."""
        mock_llm_client.generate.return_value = LLMResponse(
            content='```json\n{"score": 0.9, "reasoning": "test"}\n```',
            model="gemini",
            provider="gemini",
        )

        result = await evaluator._call_llm_evaluator("test prompt")

        assert result["score"] == 0.9

    @pytest.mark.asyncio
    async def test_call_llm_evaluator_json_decode_error(self, evaluator, mock_llm_client):
        """Test handling of invalid JSON response."""
        mock_llm_client.generate.return_value = LLMResponse(
            content="invalid json",
            model="gemini",
            provider="gemini",
        )

        result = await evaluator._call_llm_evaluator("test prompt")

        assert result["score"] == 0.5
        assert "error" in result

    @pytest.mark.asyncio
    async def test_call_llm_evaluator_missing_score(self, evaluator, mock_llm_client):
        """Test handling of response without score field."""
        mock_llm_client.generate.return_value = LLMResponse(
            content='{"reasoning": "test only"}',
            model="gemini",
            provider="gemini",
        )

        result = await evaluator._call_llm_evaluator("test prompt")

        assert result["score"] == 0.5  # Default value

    @pytest.mark.asyncio
    async def test_call_llm_evaluator_exception(self, evaluator, mock_llm_client):
        """Test handling of LLM exception."""
        mock_llm_client.generate.side_effect = Exception("LLM Error")

        result = await evaluator._call_llm_evaluator("test prompt")

        assert result["score"] == 0.5
        assert "error" in result

    @pytest.mark.asyncio
    async def test_call_llm_evaluator_clamps_score(self, evaluator, mock_llm_client):
        """Test that scores are clamped between 0 and 1."""
        mock_llm_client.generate.return_value = LLMResponse(
            content='{"score": 1.5}',
            model="gemini",
            provider="gemini",
        )

        result = await evaluator._call_llm_evaluator("test prompt")

        assert result["score"] == 1.0  # Clamped to max


# =============================================================================
# Metric Evaluation Tests
# =============================================================================


class TestFaithfulness:
    """Tests for faithfulness metric."""

    @pytest.mark.asyncio
    async def test_evaluate_faithfulness_success(
        self, evaluator, sample_answer, sample_context, mock_llm_client,
    ):
        """Test successful faithfulness evaluation."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.9, "reasoning": "Fully supported"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate_faithfulness(sample_answer, sample_context)

        assert result["score"] == 0.9
        assert "reasoning" in result
        evaluator._eval_count == 1

    @pytest.mark.asyncio
    async def test_evaluate_faithfulness_with_cache(self, evaluator, sample_answer, sample_context):
        """Test faithfulness evaluation with caching."""
        evaluator.enable_cache = True
        cached_result = {"score": 0.95, "reasoning": "cached"}
        cache_key = evaluator._get_cache_key("", sample_context, sample_answer, "faithfulness")
        evaluator._cache[cache_key] = {"result": cached_result, "timestamp": 9999999999}

        result = await evaluator.evaluate_faithfulness(sample_answer, sample_context)

        assert result == cached_result
        assert evaluator._cache_hit_count == 1

    @pytest.mark.asyncio
    async def test_evaluate_faithfulness_prompt_format(
        self, evaluator, sample_answer, sample_context, mock_llm_client,
    ):
        """Test that faithfulness prompt is correctly formatted."""
        await evaluator.evaluate_faithfulness(sample_answer, sample_context)

        call_args = mock_llm_client.generate.call_args
        messages = call_args[1]["messages"]

        # Check that context is formatted in prompt
        prompt_content = messages[1].content
        assert "Konteks 1" in prompt_content
        assert "Konteks 2" in prompt_content
        assert sample_answer in prompt_content


class TestAnswerRelevance:
    """Tests for answer relevance metric."""

    @pytest.mark.asyncio
    async def test_evaluate_answer_relevance_success(
        self, evaluator, sample_query, sample_answer, mock_llm_client,
    ):
        """Test successful answer relevance evaluation."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.88, "reasoning": "Relevant"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate_answer_relevance(sample_query, sample_answer)

        assert result["score"] == 0.88
        assert "reasoning" in result

    @pytest.mark.asyncio
    async def test_evaluate_answer_relevance_prompt_contains_query(
        self, evaluator, sample_query, sample_answer, mock_llm_client,
    ):
        """Test that prompt contains the query."""
        await evaluator.evaluate_answer_relevance(sample_query, sample_answer)

        call_args = mock_llm_client.generate.call_args
        messages = call_args[1]["messages"]
        prompt_content = messages[1].content

        assert sample_query in prompt_content
        assert sample_answer in prompt_content


class TestContextPrecision:
    """Tests for context precision metric."""

    @pytest.mark.asyncio
    async def test_evaluate_context_precision_success(
        self, evaluator, sample_query, sample_context, sample_ground_truth, mock_llm_client,
    ):
        """Test successful context precision evaluation."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.75, "reasoning": "Mostly relevant"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate_context_precision(
            sample_query, sample_context, sample_ground_truth,
        )

        assert result["score"] == 0.75

    @pytest.mark.asyncio
    async def test_evaluate_context_precision_with_cache(
        self, evaluator, sample_query, sample_context, sample_ground_truth,
    ):
        """Test context precision evaluation with caching."""
        evaluator.enable_cache = True
        cached_result = {"score": 0.8, "reasoning": "cached"}
        cache_key = evaluator._get_cache_key(sample_query, sample_context, "", "context_precision")
        evaluator._cache[cache_key] = {"result": cached_result, "timestamp": 9999999999}

        result = await evaluator.evaluate_context_precision(
            sample_query, sample_context, sample_ground_truth,
        )

        assert result == cached_result


class TestContextRecall:
    """Tests for context recall metric."""

    @pytest.mark.asyncio
    async def test_evaluate_context_recall_success(
        self, evaluator, sample_query, sample_context, sample_ground_truth, mock_llm_client,
    ):
        """Test successful context recall evaluation."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.82, "reasoning": "Good coverage"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate_context_recall(
            sample_query, sample_context, sample_ground_truth,
        )

        assert result["score"] == 0.82


class TestContextEntityRecall:
    """Tests for context entity recall metric."""

    @pytest.mark.asyncio
    async def test_evaluate_context_entity_recall_success(
        self, evaluator, sample_answer, sample_context, mock_llm_client,
    ):
        """Test successful context entity recall evaluation."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps(
                {
                    "score": 0.85,
                    "reasoning": "Entities found",
                    "entities_in_answer": ["KITAS", "WNA"],
                    "entities_in_context": ["KITAS", "WNA"],
                },
            ),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate_context_entity_recall(sample_answer, sample_context)

        assert result["score"] == 0.85
        assert "entities_in_answer" in result


# =============================================================================
# Full Evaluation Tests
# =============================================================================


class TestFullEvaluation:
    """Tests for complete evaluation pipeline."""

    @pytest.mark.asyncio
    async def test_evaluate_all_metrics(
        self,
        evaluator,
        sample_query,
        sample_context,
        sample_answer,
        sample_ground_truth,
        mock_llm_client,
    ):
        """Test full evaluation with all metrics."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.85, "reasoning": "test"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate(
            query=sample_query,
            context=sample_context,
            answer=sample_answer,
            ground_truth=sample_ground_truth,
        )

        assert isinstance(result, EvaluationResult)
        assert result.query == sample_query
        assert result.context == sample_context
        assert result.answer == sample_answer
        assert result.ground_truth == sample_ground_truth

        # Check all metrics are present
        assert "faithfulness" in result.metrics
        assert "answer_relevance" in result.metrics
        assert "context_precision" in result.metrics
        assert "context_recall" in result.metrics
        assert "context_entity_recall" in result.metrics

    @pytest.mark.asyncio
    async def test_evaluate_without_ground_truth(
        self, evaluator, sample_query, sample_context, sample_answer, mock_llm_client,
    ):
        """Test evaluation without ground truth."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.8, "reasoning": "test"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate(
            query=sample_query,
            context=sample_context,
            answer=sample_answer,
            ground_truth=None,
        )

        # Context precision and recall should not be computed
        assert "faithfulness" in result.metrics
        assert "answer_relevance" in result.metrics
        assert "context_precision" not in result.metrics
        assert "context_recall" not in result.metrics

    @pytest.mark.asyncio
    async def test_evaluate_specific_metrics(
        self, evaluator, sample_query, sample_context, sample_answer, mock_llm_client,
    ):
        """Test evaluation with specific metrics only."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.9, "reasoning": "test"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate(
            query=sample_query,
            context=sample_context,
            answer=sample_answer,
            metrics=["faithfulness", "answer_relevance"],
        )

        assert "faithfulness" in result.metrics
        assert "answer_relevance" in result.metrics
        assert "context_entity_recall" not in result.metrics

    @pytest.mark.asyncio
    async def test_evaluate_overall_score(
        self, evaluator, sample_query, sample_context, sample_answer, mock_llm_client,
    ):
        """Test overall score calculation."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.8, "reasoning": "test"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate(
            query=sample_query,
            context=sample_context,
            answer=sample_answer,
        )

        # Overall score should be average of metrics
        expected_avg = sum(result.metrics.values()) / len(result.metrics)
        assert result.overall_score == expected_avg

    @pytest.mark.asyncio
    async def test_evaluate_result_to_dict(
        self, evaluator, sample_query, sample_context, sample_answer, mock_llm_client,
    ):
        """Test EvaluationResult serialization."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.85, "reasoning": "test"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate(
            query=sample_query,
            context=sample_context,
            answer=sample_answer,
        )

        data = result.to_dict()

        assert data["query"] == sample_query
        assert data["context"] == sample_context
        assert data["answer"] == sample_answer
        assert "metrics" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_evaluate_metadata(
        self, evaluator, sample_query, sample_context, sample_answer, mock_llm_client,
    ):
        """Test that evaluation result includes metadata."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.85, "reasoning": "test"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate(
            query=sample_query,
            context=sample_context,
            answer=sample_answer,
        )

        assert "detailed_results" in result.metadata
        assert "cache_enabled" in result.metadata
        assert "eval_count" in result.metadata


# =============================================================================
# Statistics Tests
# =============================================================================


class TestEvaluatorStats:
    """Tests for evaluator statistics."""

    def test_get_stats(self, evaluator):
        """Test getting evaluator statistics."""
        evaluator._eval_count = 10
        evaluator._cache_hit_count = 5
        evaluator._cache = {"key1": {}, "key2": {}}

        stats = evaluator.get_stats()

        assert stats["total_evaluations"] == 10
        assert stats["cache_hits"] == 5
        assert stats["cache_size"] == 2
        assert stats["cache_enabled"] is False

    def test_get_stats_empty(self, evaluator):
        """Test stats with no evaluations."""
        stats = evaluator.get_stats()

        assert stats["total_evaluations"] == 0
        assert stats["cache_hits"] == 0
        assert stats["cache_size"] == 0


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for global singleton instance."""

    def test_get_ragas_evaluator_singleton(self):
        """Test that get_ragas_evaluator returns a singleton."""
        with patch("backend.services.rag.evaluation.ragas_evaluator.RAGASEvaluator") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            # Reset global instance
            import backend.services.rag.evaluation.ragas_evaluator as eval_module

            eval_module._ragas_evaluator = None

            evaluator1 = get_ragas_evaluator()
            evaluator2 = get_ragas_evaluator()

            assert evaluator1 is evaluator2
            mock_cls.assert_called_once()

    def test_get_ragas_evaluator_with_params(self):
        """Test getting evaluator with custom parameters."""
        with patch("backend.services.rag.evaluation.ragas_evaluator.RAGASEvaluator") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            # Reset global instance
            import backend.services.rag.evaluation.ragas_evaluator as eval_module

            eval_module._ragas_evaluator = None

            mock_client = MagicMock()
            get_ragas_evaluator(llm_client=mock_client, enable_cache=False)

            mock_cls.assert_called_once_with(
                llm_client=mock_client,
                enable_cache=False,
            )


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.integration
class TestIntegration:
    """Integration tests with real pipeline."""

    @pytest.mark.asyncio
    async def test_end_to_end_evaluation(self):
        """Test end-to-end evaluation with mocked LLM client."""
        mock_client = MagicMock()
        mock_client.generate = AsyncMock(
            return_value=LLMResponse(
                content=json.dumps({"score": 0.85, "reasoning": "Test reasoning"}),
                model="test-model",
                provider="test",
            ),
        )
        evaluator = RAGASEvaluator(llm_client=mock_client, enable_cache=False)

        query = "Apa itu KITAS?"
        context = ["KITAS adalah izin tinggal untuk WNA."]
        answer = "KITAS adalah izin tinggal."

        result = await evaluator.evaluate(query, context, answer)

        assert result.metrics
        assert all(0 <= v <= 1 for v in result.metrics.values())


# =============================================================================
# Prompt Template Tests
# =============================================================================


class TestPromptTemplates:
    """Tests for evaluation prompt templates."""

    def test_faithfulness_prompt_format(self):
        """Test faithfulness prompt template."""
        formatted = FAITHFULNESS_PROMPT.format(
            question="test question",
            context="[Konteks 1]\ntest context",
            answer="test answer",
        )

        assert "evaluator" in formatted.lower() or "Anda adalah" in formatted
        assert "test question" in formatted
        assert "test context" in formatted
        assert "test answer" in formatted
        assert "score" in formatted.lower()

    def test_answer_relevance_prompt_format(self):
        """Test answer relevance prompt template."""
        formatted = ANSWER_RELEVANCE_PROMPT.format(
            question="test question",
            answer="test answer",
        )

        assert "relevan" in formatted.lower()
        assert "test question" in formatted
        assert "test answer" in formatted

    def test_context_precision_prompt_format(self):
        """Test context precision prompt template."""
        formatted = CONTEXT_PRECISION_PROMPT.format(
            question="test question",
            context="[Konteks 1]\ntest context",
            ground_truth="test ground truth",
        )

        assert "konteks" in formatted.lower()
        assert "ground truth" in formatted.lower()

    def test_context_recall_prompt_format(self):
        """Test context recall prompt template."""
        formatted = CONTEXT_RECALL_PROMPT.format(
            question="test question",
            context="[Konteks 1]\ntest context",
            ground_truth="test ground truth",
        )

        assert "kelengkapan" in formatted.lower() or "semua" in formatted.lower()

    def test_context_entity_recall_prompt_format(self):
        """Test context entity recall prompt template."""
        formatted = CONTEXT_ENTITY_RECALL_PROMPT.format(
            question="test question",
            context="[Konteks 1]\ntest context",
            answer="test answer",
        )

        assert "entitas" in formatted.lower()


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_evaluate_empty_context(
        self, evaluator, sample_query, sample_answer, mock_llm_client,
    ):
        """Test evaluation with empty context."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.0, "reasoning": "No context"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate(
            query=sample_query,
            context=[],
            answer=sample_answer,
        )

        assert result is not None
        assert result.context == []

    @pytest.mark.asyncio
    async def test_evaluate_empty_answer(
        self, evaluator, sample_query, sample_context, mock_llm_client,
    ):
        """Test evaluation with empty answer."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.0, "reasoning": "Empty answer"}),
            model="gemini",
            provider="gemini",
        )

        result = await evaluator.evaluate(
            query=sample_query,
            context=sample_context,
            answer="",
        )

        assert result is not None
        assert result.answer == ""

    @pytest.mark.asyncio
    async def test_evaluate_multilingual(self, evaluator, mock_llm_client):
        """Test evaluation with mixed Indonesian/English content."""
        mock_llm_client.generate.return_value = LLMResponse(
            content=json.dumps({"score": 0.85, "reasoning": "Good"}),
            model="gemini",
            provider="gemini",
        )

        query = "What is KITAS dan cara mengurusnya?"
        context = ["KITAS is a limited stay permit untuk WNA."]
        answer = "KITAS adalah limited stay permit."

        result = await evaluator.evaluate(query, context, answer)

        assert result is not None
        assert "faithfulness" in result.metrics

    def test_evaluation_result_empty_metrics(self):
        """Test EvaluationResult with no metrics."""
        result = EvaluationResult(
            query="test",
            context=[],
            answer="test",
            metrics={},
        )

        assert result.overall_score == 0.0
