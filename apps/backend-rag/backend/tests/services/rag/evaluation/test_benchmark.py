"""
NUZANTARA RAG - Benchmark Tests

Comprehensive test suite for RAGBenchmark covering:
- Search method evaluation
- Benchmark run
- Result comparison
- Report generation
- Database operations
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.evaluation.benchmark import (
    BenchmarkConfig,
    BenchmarkResult,
    MethodResult,
    RAGBenchmark,
    create_evaluation_tables,
)
from backend.services.rag.evaluation.dataset_builder import EvaluationSample
from backend.services.rag.evaluation.ragas_evaluator import EvaluationResult

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_hybrid_service():
    """Create mock hybrid search service."""
    service = MagicMock()
    service.search_dense_only = AsyncMock(
        return_value={
            "results": [{"text": "Context 1"}, {"text": "Context 2"}],
            "search_type": "dense",
            "total_results": 2,
        },
    )
    service.search_hybrid = AsyncMock(
        return_value={
            "results": [{"text": "Context 1"}, {"text": "Context 2"}],
            "search_type": "hybrid_rrf",
            "bm25_enabled": True,
            "alpha": 0.5,
            "total_results": 2,
        },
    )
    return service


@pytest.fixture
def mock_reranker():
    """Create mock reranker."""
    reranker = MagicMock()
    reranker.rerank = AsyncMock(
        return_value=[
            {"text": "Context 1", "score": 0.95},
            {"text": "Context 2", "score": 0.85},
        ],
    )
    return reranker


@pytest.fixture
def mock_evaluator():
    """Create mock RAGAS evaluator."""
    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(
        return_value=EvaluationResult(
            query="test query",
            context=["Context 1"],
            answer="Test answer",
            ground_truth="Ground truth",
            metrics={
                "faithfulness": 0.9,
                "answer_relevance": 0.85,
                "context_entity_recall": 0.8,
            },
            metadata={},
        ),
    )
    return evaluator


@pytest.fixture
def benchmark(mock_evaluator, mock_hybrid_service, mock_reranker):
    """Create RAGBenchmark with mocked dependencies."""
    return RAGBenchmark(
        evaluator=mock_evaluator,
        hybrid_service=mock_hybrid_service,
        reranker=mock_reranker,
    )


@pytest.fixture
def sample_dataset():
    """Create sample evaluation dataset."""
    return [
        EvaluationSample(
            id="sample-1",
            query="Apa itu KITAS?",
            expected_answer="KITAS adalah izin tinggal.",
            relevant_context_ids=["ctx1"],
            category="visa",
            difficulty="easy",
            metadata={},
        ),
        EvaluationSample(
            id="sample-2",
            query="Bagaimana cara buat PT?",
            expected_answer="Proses pendirian PT meliputi...",
            relevant_context_ids=["ctx2"],
            category="business",
            difficulty="medium",
            metadata={},
        ),
    ]


@pytest.fixture
def benchmark_config():
    """Create sample benchmark configuration."""
    return BenchmarkConfig(
        name="test_benchmark",
        description="Test benchmark run",
        collection="test_collection",
        search_methods=["dense", "hybrid"],
        limit=5,
        alpha=0.5,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestInitialization:
    """Tests for RAGBenchmark initialization."""

    def test_init_with_dependencies(self, mock_evaluator, mock_hybrid_service):
        """Test initialization with provided dependencies."""
        benchmark = RAGBenchmark(
            evaluator=mock_evaluator,
            hybrid_service=mock_hybrid_service,
        )

        assert benchmark.evaluator is mock_evaluator
        assert benchmark.hybrid_service is mock_hybrid_service

    def test_init_lazy_reranker(self, mock_evaluator, mock_hybrid_service):
        """Test lazy initialization of reranker."""
        with patch(
            "backend.services.rag.evaluation.benchmark.CrossEncoderRerankerMixin",
        ) as mock_reranker_cls:
            mock_reranker = MagicMock()
            mock_reranker_cls.return_value = mock_reranker

            benchmark = RAGBenchmark(
                evaluator=mock_evaluator,
                hybrid_service=mock_hybrid_service,
            )

            mock_reranker_cls.assert_called_once()
            assert benchmark.reranker is mock_reranker

    def test_init_reranker_failure(self, mock_evaluator, mock_hybrid_service):
        """Test handling of reranker initialization failure."""
        with patch(
            "backend.services.rag.evaluation.benchmark.CrossEncoderRerankerMixin",
        ) as mock_reranker_cls:
            mock_reranker_cls.side_effect = Exception("Reranker not available")

            benchmark = RAGBenchmark(
                evaluator=mock_evaluator,
                hybrid_service=mock_hybrid_service,
            )

            assert benchmark.reranker is None


# =============================================================================
# Search Method Tests
# =============================================================================


class TestSearchMethods:
    """Tests for different search methods."""

    @pytest.mark.asyncio
    async def test_search_dense(self, benchmark, mock_hybrid_service):
        """Test dense-only search."""
        context, metadata = await benchmark._search_dense(
            query="test",
            collection="test_collection",
            limit=5,
        )

        assert len(context) == 2
        assert context[0] == "Context 1"
        assert metadata["search_type"] == "dense"
        assert "duration_ms" in metadata
        mock_hybrid_service.search_dense_only.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_hybrid(self, benchmark, mock_hybrid_service):
        """Test hybrid search."""
        context, metadata = await benchmark._search_hybrid(
            query="test",
            collection="test_collection",
            limit=5,
            alpha=0.5,
        )

        assert len(context) == 2
        assert metadata["search_type"] == "hybrid_rrf"
        assert metadata["bm25_enabled"] is True
        assert metadata["alpha"] == 0.5
        mock_hybrid_service.search_hybrid.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_hybrid_rerank(self, benchmark, mock_reranker):
        """Test hybrid search with reranking."""
        context, metadata = await benchmark._search_hybrid_rerank(
            query="test",
            collection="test_collection",
            limit=2,
            alpha=0.5,
            rerank_top_k=10,
        )

        assert len(context) == 2
        assert metadata["search_type"] == "hybrid_rerank"
        assert metadata["rerank_top_k"] == 10
        mock_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_hybrid_rerank_fallback(self, benchmark):
        """Test fallback when reranker is not available."""
        benchmark.reranker = None

        context, metadata = await benchmark._search_hybrid_rerank(
            query="test",
            collection="test_collection",
            limit=2,
        )

        assert metadata["search_type"] == "hybrid_rrf"

    @pytest.mark.asyncio
    async def test_search_hybrid_rerank_failure(self, benchmark, mock_reranker):
        """Test fallback when reranking fails."""
        mock_reranker.rerank.side_effect = Exception("Reranking failed")

        context, metadata = await benchmark._search_hybrid_rerank(
            query="test",
            collection="test_collection",
            limit=2,
        )

        # Should still return results from hybrid search
        assert len(context) == 2


# =============================================================================
# Sample Evaluation Tests
# =============================================================================


class TestSampleEvaluation:
    """Tests for individual sample evaluation."""

    @pytest.mark.asyncio
    async def test_evaluate_sample_dense(self, benchmark, sample_dataset, benchmark_config):
        """Test evaluating sample with dense search."""
        sample = sample_dataset[0]

        result, metadata = await benchmark.evaluate_sample(
            sample=sample,
            method="dense",
            config=benchmark_config,
        )

        assert isinstance(result, EvaluationResult)
        assert result.query is not None
        assert "search" in result.metadata
        assert metadata["search_type"] == "dense"

    @pytest.mark.asyncio
    async def test_evaluate_sample_hybrid(self, benchmark, sample_dataset, benchmark_config):
        """Test evaluating sample with hybrid search."""
        sample = sample_dataset[0]
        benchmark_config.search_methods = ["hybrid"]

        result, metadata = await benchmark.evaluate_sample(
            sample=sample,
            method="hybrid",
            config=benchmark_config,
        )

        assert isinstance(result, EvaluationResult)
        assert metadata["search_type"] == "hybrid_rrf"

    @pytest.mark.asyncio
    async def test_evaluate_sample_unknown_method(
        self, benchmark, sample_dataset, benchmark_config,
    ):
        """Test that unknown method raises error."""
        with pytest.raises(ValueError, match="Unknown search method"):
            await benchmark.evaluate_sample(
                sample=sample_dataset[0],
                method="unknown",
                config=benchmark_config,
            )


# =============================================================================
# Method Evaluation Tests
# =============================================================================


class TestMethodEvaluation:
    """Tests for evaluating entire dataset with one method."""

    @pytest.mark.asyncio
    async def test_evaluate_method(self, benchmark, sample_dataset, benchmark_config):
        """Test evaluating dataset with one method."""
        result = await benchmark.evaluate_method(
            dataset=sample_dataset,
            method="dense",
            config=benchmark_config,
        )

        assert isinstance(result, MethodResult)
        assert result.method == "dense"
        assert len(result.evaluation_results) == len(sample_dataset)
        assert "faithfulness" in result.avg_metrics
        assert result.overall_score > 0

    @pytest.mark.asyncio
    async def test_evaluate_method_with_failures(self, benchmark, sample_dataset, benchmark_config):
        """Test handling of evaluation failures."""
        # Make first evaluation fail
        benchmark.evaluator.evaluate = AsyncMock(
            side_effect=[
                Exception("Eval failed"),
                EvaluationResult(
                    query="test",
                    context=[],
                    answer="",
                    ground_truth="",
                    metrics={"faithfulness": 0.8},
                    metadata={},
                ),
            ],
        )

        result = await benchmark.evaluate_method(
            dataset=sample_dataset[:2],
            method="dense",
            config=benchmark_config,
        )

        assert len(result.evaluation_results) == 2
        # First result should have error metadata
        assert "error" in result.evaluation_results[0].metadata


# =============================================================================
# Full Benchmark Tests
# =============================================================================


class TestFullBenchmark:
    """Tests for complete benchmark run."""

    @pytest.mark.asyncio
    async def test_run_benchmark(self, benchmark, sample_dataset, benchmark_config):
        """Test running full benchmark."""
        result = await benchmark.run_benchmark(sample_dataset, benchmark_config)

        assert isinstance(result, BenchmarkResult)
        assert result.id.startswith("test_benchmark_")
        assert result.config == benchmark_config
        assert result.dataset_size == len(sample_dataset)
        assert len(result.method_results) == len(benchmark_config.search_methods)
        assert "best_method" in result.comparison

    @pytest.mark.asyncio
    async def test_run_benchmark_comparison(self, benchmark, sample_dataset):
        """Test that benchmark generates comparison."""
        config = BenchmarkConfig(
            name="comparison_test",
            description="Test",
            collection="test",
            search_methods=["dense", "hybrid", "hybrid_rerank"],
            limit=5,
        )

        result = await benchmark.run_benchmark(sample_dataset, config)

        assert len(result.method_results) == 3
        assert result.comparison["best_method"] in ["dense", "hybrid", "hybrid_rerank"]


# =============================================================================
# Comparison Tests
# =============================================================================


class TestComparison:
    """Tests for result comparison."""

    def test_generate_comparison(self, benchmark):
        """Test generating comparison between methods."""
        method_results = [
            MethodResult(
                method="dense",
                duration_ms=1000,
                evaluation_results=[],
                avg_metrics={"faithfulness": 0.7},
                overall_score=0.7,
            ),
            MethodResult(
                method="hybrid",
                duration_ms=1200,
                evaluation_results=[],
                avg_metrics={"faithfulness": 0.85},
                overall_score=0.85,
            ),
        ]

        comparison = benchmark._generate_comparison(method_results)

        assert comparison["best_method"] == "hybrid"
        assert comparison["best_overall_score"] == 0.85
        assert "method_scores" in comparison
        assert "improvement_vs_baseline" in comparison["method_scores"]["hybrid"]

    def test_generate_comparison_empty(self, benchmark):
        """Test comparison with no method results."""
        comparison = benchmark._generate_comparison([])

        assert comparison == {}

    def test_generate_comparison_single_method(self, benchmark):
        """Test comparison with single method."""
        method_results = [
            MethodResult(
                method="dense",
                duration_ms=1000,
                evaluation_results=[],
                avg_metrics={"faithfulness": 0.7},
                overall_score=0.7,
            ),
        ]

        comparison = benchmark._generate_comparison(method_results)

        assert comparison["best_method"] == "dense"
        assert "improvement_vs_baseline" not in comparison["method_scores"]["dense"]


# =============================================================================
# Report Generation Tests
# =============================================================================


class TestReportGeneration:
    """Tests for report generation."""

    def test_generate_report(self, benchmark):
        """Test generating human-readable report."""
        result = BenchmarkResult(
            id="test-id",
            config=BenchmarkConfig(
                name="test",
                description="Test benchmark",
                collection="test_collection",
                search_methods=["dense", "hybrid"],
            ),
            timestamp="2024-01-01T00:00:00",
            dataset_size=10,
            method_results=[
                MethodResult(
                    method="dense",
                    duration_ms=1000,
                    evaluation_results=[],
                    avg_metrics={"faithfulness": 0.8, "answer_relevance": 0.85},
                    overall_score=0.825,
                ),
            ],
            comparison={
                "best_method": "dense",
                "best_overall_score": 0.825,
                "method_scores": {"dense": {"overall": 0.825}},
            },
        )

        report = benchmark.generate_report(result)

        assert "RAG EVALUATION BENCHMARK REPORT" in report
        assert "test" in report
        assert "test_collection" in report
        assert "dense" in report
        assert "0.825" in report or "0.82" in report

    def test_save_report(self, benchmark, tmp_path):
        """Test saving report to file."""
        result = BenchmarkResult(
            id="test-id",
            config=BenchmarkConfig(
                name="test",
                description="Test",
                collection="test",
                search_methods=["dense"],
            ),
            timestamp="2024-01-01T00:00:00",
            dataset_size=10,
            method_results=[],
            comparison={},
        )

        filepath = str(tmp_path / "test_report.txt")
        benchmark.save_report(result, filepath)

        assert open(filepath).read()


# =============================================================================
# Database Operations Tests
# =============================================================================


class TestDatabaseOperations:
    """Tests for database operations."""

    @pytest.mark.asyncio
    async def test_save_results(self, benchmark):
        """Test saving benchmark results to database."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = BenchmarkResult(
            id="test-id",
            config=BenchmarkConfig(
                name="test",
                description="Test",
                collection="test",
                search_methods=["dense"],
            ),
            timestamp="2024-01-01T00:00:00",
            dataset_size=10,
            method_results=[],
            comparison={},
        )

        await benchmark.save_results(result, db_pool=mock_pool)

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_historical_results_with_name(self, benchmark):
        """Test getting historical results filtered by name."""
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"id": "run-1", "name": "weekly"},
                {"id": "run-2", "name": "weekly"},
            ],
        )
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await benchmark.get_historical_results(
            name="weekly",
            limit=5,
            db_pool=mock_pool,
        )

        assert len(results) == 2
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_historical_results_all(self, benchmark):
        """Test getting all historical results."""
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[{"id": "run-1"}])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await benchmark.get_historical_results(db_pool=mock_pool)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_historical_results_error(self, benchmark):
        """Test handling of database error."""
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB Error"))
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await benchmark.get_historical_results(db_pool=mock_pool)

        assert results == []


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.integration
class TestIntegration:
    """Integration tests with real dependencies."""

    @pytest.mark.asyncio
    async def test_end_to_end_benchmark(self):
        """Test end-to-end benchmark with real components."""
        import asyncio

        # Skip if dependencies not available
        try:
            benchmark = RAGBenchmark()
        except Exception:
            pytest.skip("Dependencies not available")

        dataset = [
            EvaluationSample(
                id="test-1",
                query="Apa itu KITAS?",
                expected_answer="KITAS adalah izin tinggal.",
                relevant_context_ids=["ctx1"],
                category="visa",
                difficulty="easy",
                metadata={},
            ),
        ]

        config = BenchmarkConfig(
            name="integration_test",
            description="Integration test",
            collection="test_collection",
            search_methods=["dense"],
            limit=2,
        )

        try:
            result = await asyncio.wait_for(benchmark.run_benchmark(dataset, config), timeout=10.0)
        except (asyncio.TimeoutError, Exception):
            pytest.skip("Integration test requires live Qdrant/OpenAI connection")

        assert result is not None
        assert result.dataset_size == 1


# =============================================================================
# Data Classes Tests
# =============================================================================


class TestDataClasses:
    """Tests for data class serialization."""

    def test_benchmark_config_dict(self):
        """Test BenchmarkConfig serialization."""
        from dataclasses import asdict

        config = BenchmarkConfig(
            name="test",
            description="Test config",
            collection="test_collection",
            search_methods=["dense", "hybrid"],
            limit=5,
            alpha=0.5,
        )

        data = asdict(config)

        assert data["name"] == "test"
        assert data["search_methods"] == ["dense", "hybrid"]
        assert data["limit"] == 5

    def test_method_result_to_dict(self):
        """Test MethodResult serialization."""
        result = MethodResult(
            method="dense",
            duration_ms=1000,
            evaluation_results=[],
            avg_metrics={"faithfulness": 0.8},
            overall_score=0.8,
        )

        data = result.to_dict()

        assert data["method"] == "dense"
        assert data["overall_score"] == 0.8
        assert data["avg_metrics"]["faithfulness"] == 0.8

    def test_benchmark_result_to_dict(self):
        """Test BenchmarkResult serialization."""
        result = BenchmarkResult(
            id="test-id",
            config=BenchmarkConfig(
                name="test",
                description="Test",
                collection="test",
                search_methods=["dense"],
            ),
            timestamp="2024-01-01T00:00:00",
            dataset_size=10,
            method_results=[],
            comparison={},
        )

        data = result.to_dict()

        assert data["id"] == "test-id"
        assert data["timestamp"] == "2024-01-01T00:00:00"


# =============================================================================
# Utility Functions Tests
# =============================================================================


class TestUtilityFunctions:
    """Tests for utility functions."""

    @pytest.mark.asyncio
    async def test_create_evaluation_tables(self):
        """Test creation of evaluation tables."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.services.rag.evaluation.benchmark.get_db_pool", return_value=mock_pool):
            await create_evaluation_tables()

        mock_conn.execute.assert_called_once()
        # Check that CREATE TABLE is in the call
        call_args = mock_conn.execute.call_args
        assert "CREATE TABLE" in call_args[0][0]


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_placeholder_answer_generation(self, benchmark):
        """Test placeholder answer generation."""
        context = ["Context 1", "Context 2", "Context 3"]

        answer = benchmark._generate_placeholder_answer("test query", context)

        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_placeholder_answer_empty_context(self, benchmark):
        """Test placeholder answer with empty context."""
        answer = benchmark._generate_placeholder_answer("test query", [])

        assert "tidak dapat menemukan" in answer.lower() or "maaf" in answer.lower()

    @pytest.mark.asyncio
    async def test_evaluate_method_empty_dataset(self, benchmark, benchmark_config):
        """Test evaluating empty dataset."""
        result = await benchmark.evaluate_method(
            dataset=[],
            method="dense",
            config=benchmark_config,
        )

        assert result.method == "dense"
        assert len(result.evaluation_results) == 0
        assert result.overall_score == 0.0

    @pytest.mark.asyncio
    async def test_run_benchmark_empty_methods(self, benchmark, sample_dataset):
        """Test benchmark with empty method list."""
        config = BenchmarkConfig(
            name="empty_test",
            description="Test",
            collection="test",
            search_methods=[],
        )

        result = await benchmark.run_benchmark(sample_dataset, config)

        assert len(result.method_results) == 0
        assert result.comparison == {}
