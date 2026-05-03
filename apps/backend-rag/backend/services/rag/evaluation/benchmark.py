"""
RAG Evaluation Benchmark Runner

Runs full evaluation on dataset comparing multiple retrieval methods:
- Dense-only search
- Hybrid search (BM25 + dense)
- Hybrid + reranking

Generates reports with scores and tracks metrics over time.
Stores results in PostgreSQL for historical tracking.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.app.core.database import get_db_pool
from backend.app.core.logging_config import get_performance_logger
from backend.services.rag.evaluation.dataset_builder import (
    DatasetBuilder,
    EvaluationSample,
)
from backend.services.rag.evaluation.ragas_evaluator import (
    EvaluationResult,
    RAGASEvaluator,
    get_ragas_evaluator,
)
from backend.services.rag.hybrid_search import HybridSearchService
from backend.services.rag.reranker_integration import (
    CrossEncoderRerankerMixin,
)

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark run."""

    name: str
    description: str
    collection: str
    search_methods: list[str]  # dense, hybrid, hybrid_rerank
    limit: int = 5
    alpha: float = 0.5  # For hybrid search
    rerank_top_k: int = 10
    enable_caching: bool = True


@dataclass
class MethodResult:
    """Results for a single search method."""

    method: str
    duration_ms: float
    evaluation_results: list[EvaluationResult]
    avg_metrics: dict[str, float]
    overall_score: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "method": self.method,
            "duration_ms": self.duration_ms,
            "evaluations": [e.to_dict() for e in self.evaluation_results],
            "avg_metrics": self.avg_metrics,
            "overall_score": self.overall_score,
        }


@dataclass
class BenchmarkResult:
    """Complete benchmark results."""

    id: str
    config: BenchmarkConfig
    timestamp: str
    dataset_size: int
    method_results: list[MethodResult]
    comparison: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "config": asdict(self.config),
            "timestamp": self.timestamp,
            "dataset_size": self.dataset_size,
            "method_results": [m.to_dict() for m in self.method_results],
            "comparison": self.comparison,
        }


class RAGBenchmark:
    """
    Benchmark runner for RAG evaluation.

    Compares multiple retrieval methods and generates comprehensive reports.
    Stores results in PostgreSQL for historical tracking.

    Example:
        >>> benchmark = RAGBenchmark()
        >>> config = BenchmarkConfig(
        ...     name="weekly_eval",
        ...     collection="legal_unified_hybrid",
        ...     search_methods=["dense", "hybrid", "hybrid_rerank"]
        ... )
        >>> results = await benchmark.run_benchmark(dataset, config)
        >>> await benchmark.save_results(results)
    """

    def __init__(
        self,
        evaluator: RAGASEvaluator | None = None,
        hybrid_service: HybridSearchService | None = None,
        reranker: CrossEncoderRerankerMixin | None = None,
    ) -> None:
        """
        Initialize RAG Benchmark.

        Args:
            evaluator: RAGAS evaluator instance
            hybrid_service: Hybrid search service
            reranker: Reranker integration
        """
        self.evaluator = evaluator or get_ragas_evaluator()
        self.hybrid_service = hybrid_service or HybridSearchService()
        self.reranker = reranker

        # Lazy init reranker
        if self.reranker is None:
            try:
                self.reranker = CrossEncoderRerankerMixin()
            except Exception as e:
                logger.warning(f"Failed to initialize reranker: {e}")
                self.reranker = None

        logger.info("RAGBenchmark initialized")

    async def _search_dense(
        self,
        query: str,
        collection: str,
        limit: int,
    ) -> tuple[list[str], dict[str, Any]]:
        """
        Perform dense-only search.

        Args:
            query: Search query
            collection: Collection name
            limit: Number of results

        Returns:
            Tuple of (context_texts, metadata)
        """
        start = time.time()
        results = await self.hybrid_service.search_dense_only(
            query=query,
            collection=collection,
            limit=limit,
        )
        duration = (time.time() - start) * 1000

        context_texts = [r["text"] for r in results.get("results", [])]
        metadata = {
            "search_type": results.get("search_type", "dense"),
            "duration_ms": duration,
            "total_results": results.get("total_results", 0),
        }

        return context_texts, metadata

    async def _search_hybrid(
        self,
        query: str,
        collection: str,
        limit: int,
        alpha: float = 0.5,
    ) -> tuple[list[str], dict[str, Any]]:
        """
        Perform hybrid search.

        Args:
            query: Search query
            collection: Collection name
            limit: Number of results
            alpha: Hybrid weight

        Returns:
            Tuple of (context_texts, metadata)
        """
        start = time.time()
        results = await self.hybrid_service.search_hybrid(
            query=query,
            collection=collection,
            limit=limit,
            alpha=alpha,
        )
        duration = (time.time() - start) * 1000

        context_texts = [r["text"] for r in results.get("results", [])]
        metadata = {
            "search_type": results.get("search_type", "hybrid"),
            "bm25_enabled": results.get("bm25_enabled", False),
            "alpha": results.get("alpha", alpha),
            "duration_ms": duration,
            "total_results": results.get("total_results", 0),
        }

        return context_texts, metadata

    async def _search_hybrid_rerank(
        self,
        query: str,
        collection: str,
        limit: int,
        alpha: float = 0.5,
        rerank_top_k: int = 10,
    ) -> tuple[list[str], dict[str, Any]]:
        """
        Perform hybrid search with reranking.

        Args:
            query: Search query
            collection: Collection name
            limit: Number of results
            alpha: Hybrid weight
            rerank_top_k: Top k to rerank

        Returns:
            Tuple of (context_texts, metadata)
        """
        if self.reranker is None:
            logger.warning("Reranker not available, falling back to hybrid")
            return await self._search_hybrid(query, collection, limit, alpha)

        start = time.time()

        # First get more results for reranking
        results = await self.hybrid_service.search_hybrid(
            query=query,
            collection=collection,
            limit=rerank_top_k,
            alpha=alpha,
        )

        # Rerank if available
        try:
            reranked = await self.reranker.rerank(
                query=query,
                results=results.get("results", []),
                top_k=limit,
            )
            context_texts = [r["text"] for r in reranked]
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, using original order")
            context_texts = [r["text"] for r in results.get("results", [])[:limit]]

        duration = (time.time() - start) * 1000

        metadata = {
            "search_type": "hybrid_rerank",
            "bm25_enabled": results.get("bm25_enabled", False),
            "alpha": alpha,
            "rerank_top_k": rerank_top_k,
            "duration_ms": duration,
            "total_results": len(context_texts),
        }

        return context_texts, metadata

    async def evaluate_sample(
        self,
        sample: EvaluationSample,
        method: str,
        config: BenchmarkConfig,
    ) -> tuple[EvaluationResult, dict[str, Any]]:
        """
        Evaluate a single sample with given search method.

        Args:
            sample: Evaluation sample
            method: Search method (dense, hybrid, hybrid_rerank)
            config: Benchmark configuration

        Returns:
            Tuple of (evaluation_result, search_metadata)
        """
        # Retrieve context using specified method
        if method == "dense":
            context, search_meta = await self._search_dense(
                sample.query,
                config.collection,
                config.limit,
            )
        elif method == "hybrid":
            context, search_meta = await self._search_hybrid(
                sample.query,
                config.collection,
                config.limit,
                config.alpha,
            )
        elif method == "hybrid_rerank":
            context, search_meta = await self._search_hybrid_rerank(
                sample.query,
                config.collection,
                config.limit,
                config.alpha,
                config.rerank_top_k,
            )
        else:
            raise ValueError(f"Unknown search method: {method}")

        # Generate simple answer from context (or use ground truth for context-only eval)
        # In production, this would call the actual RAG pipeline
        answer = self._generate_placeholder_answer(sample.query, context)

        # Evaluate using RAGAS
        eval_result = await self.evaluator.evaluate(
            query=sample.query,
            context=context,
            answer=answer,
            ground_truth=sample.expected_answer,
        )

        # Add search metadata
        eval_result.metadata["search"] = search_meta

        return eval_result, search_meta

    def _generate_placeholder_answer(self, query: str, context: list[str]) -> str:
        """
        Generate a placeholder answer from context.

        In production, this should call the actual generation pipeline.
        For benchmarking retrieval, we use context concatenation.
        """
        if not context:
            return "Maaf, tidak dapat menemukan informasi yang relevan."

        # Simple concatenation for retrieval evaluation
        # Real implementation would use the actual RAG generation
        return " ".join(context[:2])  # Use top 2 chunks

    async def evaluate_method(
        self,
        dataset: list[EvaluationSample],
        method: str,
        config: BenchmarkConfig,
    ) -> MethodResult:
        """
        Evaluate entire dataset with one search method.

        Args:
            dataset: Evaluation dataset
            method: Search method
            config: Benchmark configuration

        Returns:
            Method results
        """
        logger.info(f"Evaluating method: {method}")
        start_time = time.time()

        evaluation_results: list[EvaluationResult] = []

        for i, sample in enumerate(dataset):
            try:
                result, _ = await self.evaluate_sample(sample, method, config)
                evaluation_results.append(result)

                if (i + 1) % 10 == 0:
                    logger.info(f"  Progress: {i + 1}/{len(dataset)} samples evaluated")

            except Exception as e:
                logger.error(f"Failed to evaluate sample {sample.id}: {e}")
                # Create empty result on failure
                evaluation_results.append(
                    EvaluationResult(
                        query=sample.query,
                        context=[],
                        answer="",
                        ground_truth=sample.expected_answer,
                        metrics={},
                        metadata={"error": str(e)},
                    ),
                )

        duration_ms = (time.time() - start_time) * 1000

        # Calculate average metrics
        avg_metrics: dict[str, float] = {}
        metric_keys = set()
        for result in evaluation_results:
            metric_keys.update(result.metrics.keys())

        for key in metric_keys:
            values = [r.metrics.get(key, 0) for r in evaluation_results if key in r.metrics]
            if values:
                avg_metrics[key] = sum(values) / len(values)

        overall_score = sum(avg_metrics.values()) / len(avg_metrics) if avg_metrics else 0.0

        return MethodResult(
            method=method,
            duration_ms=duration_ms,
            evaluation_results=evaluation_results,
            avg_metrics=avg_metrics,
            overall_score=overall_score,
        )

    async def run_benchmark(
        self,
        dataset: list[EvaluationSample],
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """
        Run full benchmark on dataset.

        Args:
            dataset: Evaluation dataset
            config: Benchmark configuration

        Returns:
            Complete benchmark results
        """
        with get_performance_logger(__name__, f"benchmark_{config.name}"):
            logger.info(
                f"Starting benchmark: {config.name} "
                f"(dataset={len(dataset)}, methods={config.search_methods})",
            )

            method_results: list[MethodResult] = []

            for method in config.search_methods:
                result = await self.evaluate_method(dataset, method, config)
                method_results.append(result)

            # Generate comparison
            comparison = self._generate_comparison(method_results)

            benchmark_result = BenchmarkResult(
                id=f"{config.name}_{int(time.time())}",
                config=config,
                timestamp=datetime.now(timezone.utc).isoformat(),
                dataset_size=len(dataset),
                method_results=method_results,
                comparison=comparison,
            )

            logger.info(
                f"Benchmark completed: {config.name} "
                f"(best_method={comparison.get('best_method', 'N/A')})",
            )

            return benchmark_result

    def _generate_comparison(self, method_results: list[MethodResult]) -> dict[str, Any]:
        """Generate comparison between methods."""
        if not method_results:
            return {}

        # Find best method by overall score
        best_method = max(method_results, key=lambda x: x.overall_score)

        comparison = {
            "best_method": best_method.method,
            "best_overall_score": best_method.overall_score,
            "method_scores": {
                m.method: {
                    "overall": m.overall_score,
                    "metrics": m.avg_metrics,
                    "duration_ms": m.duration_ms,
                }
                for m in method_results
            },
        }

        # Calculate improvements
        if len(method_results) > 1:
            baseline = next((m for m in method_results if m.method == "dense"), method_results[0])
            for method_result in method_results:
                if method_result.method != baseline.method:
                    improvement = (
                        (method_result.overall_score - baseline.overall_score)
                        / baseline.overall_score
                        * 100
                        if baseline.overall_score > 0
                        else 0
                    )
                    comparison["method_scores"][method_result.method]["improvement_vs_baseline"] = (
                        round(improvement, 2)
                    )

        return comparison

    async def save_results(
        self,
        result: BenchmarkResult,
        db_pool: asyncpg.Pool | None = None,
    ) -> None:
        """
        Save benchmark results to PostgreSQL.

        Args:
            result: Benchmark results
            db_pool: Database pool (optional)
        """
        pool = db_pool or await get_db_pool()

        try:
            async with pool.acquire() as conn:
                # Insert benchmark run
                await conn.execute(
                    """
                    INSERT INTO rag_evaluation_runs (
                        id, name, description, timestamp, dataset_size,
                        config, results, comparison
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO UPDATE SET
                        results = EXCLUDED.results,
                        comparison = EXCLUDED.comparison
                """,
                    result.id,
                    result.config.name,
                    result.config.description,
                    result.timestamp,
                    result.dataset_size,
                    json.dumps(asdict(result.config)),
                    json.dumps([m.to_dict() for m in result.method_results]),
                    json.dumps(result.comparison),
                )

            logger.info(f"Saved benchmark results to database: {result.id}")

        except Exception as e:
            logger.error(f"Failed to save benchmark results: {e}")
            raise

    async def get_historical_results(
        self,
        name: str | None = None,
        limit: int = 10,
        db_pool: asyncpg.Pool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get historical benchmark results.

        Args:
            name: Filter by benchmark name
            limit: Maximum results to return
            db_pool: Database pool (optional)

        Returns:
            List of historical results
        """
        pool = db_pool or await get_db_pool()

        try:
            async with pool.acquire() as conn:
                if name:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM rag_evaluation_runs
                        WHERE name = $1
                        ORDER BY timestamp DESC
                        LIMIT $2
                    """,
                        name,
                        limit,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM rag_evaluation_runs
                        ORDER BY timestamp DESC
                        LIMIT $1
                    """,
                        limit,
                    )

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get historical results: {e}")
            return []

    def generate_report(self, result: BenchmarkResult) -> str:
        """
        Generate human-readable report.

        Args:
            result: Benchmark results

        Returns:
            Formatted report string
        """
        report_lines = [
            "=" * 60,
            "RAG EVALUATION BENCHMARK REPORT",
            "=" * 60,
            f"Benchmark: {result.config.name}",
            f"Description: {result.config.description}",
            f"Timestamp: {result.timestamp}",
            f"Dataset Size: {result.dataset_size} samples",
            f"Collection: {result.config.collection}",
            "",
            "RESULTS BY METHOD",
            "-" * 60,
        ]

        for method_result in result.method_results:
            report_lines.extend(
                [
                    f"\nMethod: {method_result.method.upper()}",
                    f"  Overall Score: {method_result.overall_score:.3f}",
                    f"  Duration: {method_result.duration_ms:.0f}ms",
                    "  Metrics:",
                ],
            )
            for metric, value in method_result.avg_metrics.items():
                report_lines.append(f"    {metric}: {value:.3f}")

        report_lines.extend(
            [
                "",
                "COMPARISON",
                "-" * 60,
                f"Best Method: {result.comparison.get('best_method', 'N/A')}",
                f"Best Score: {result.comparison.get('best_overall_score', 0):.3f}",
            ],
        )

        method_scores = result.comparison.get("method_scores", {})
        for method, scores in method_scores.items():
            if "improvement_vs_baseline" in scores:
                report_lines.append(
                    f"  {method}: +{scores['improvement_vs_baseline']:.1f}% vs baseline",
                )

        report_lines.extend(
            [
                "",
                "=" * 60,
                "End of Report",
                "=" * 60,
            ],
        )

        return "\n".join(report_lines)

    def save_report(
        self,
        result: BenchmarkResult,
        filepath: str,
    ) -> None:
        """
        Save report to file.

        Args:
            result: Benchmark results
            filepath: Path to save report
        """
        report = self.generate_report(result)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"Saved report to {filepath}")


async def create_evaluation_tables() -> None:
    """Create necessary database tables for evaluation results."""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_evaluation_runs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                dataset_size INTEGER,
                config JSONB,
                results JSONB,
                comparison JSONB
            );

            CREATE INDEX IF NOT EXISTS idx_eval_runs_name
            ON rag_evaluation_runs(name);

            CREATE INDEX IF NOT EXISTS idx_eval_runs_timestamp
            ON rag_evaluation_runs(timestamp DESC);
        """,
        )

    logger.info("Evaluation tables created/verified")


async def run_weekly_benchmark(
    dataset_path: str | None = None,
    collection: str = "legal_unified_hybrid",
) -> BenchmarkResult:
    """
    Run weekly benchmark evaluation.

    Args:
        dataset_path: Path to evaluation dataset (auto-generated if None)
        collection: Collection to search

    Returns:
        Benchmark results
    """
    # Create tables if needed
    await create_evaluation_tables()

    # Load or build dataset
    builder = DatasetBuilder()
    if dataset_path:
        dataset = builder.load_dataset(dataset_path)
    else:
        dataset = await builder.build_dataset(target_size=50)

    # Configure benchmark
    config = BenchmarkConfig(
        name=f"weekly_eval_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        description="Weekly automated RAG evaluation",
        collection=collection,
        search_methods=["dense", "hybrid", "hybrid_rerank"],
        limit=5,
        alpha=0.5,
    )

    # Run benchmark
    benchmark = RAGBenchmark()
    result = await benchmark.run_benchmark(dataset, config)

    # Save results
    await benchmark.save_results(result)

    # Save report
    report_path = f"/tmp/rag_benchmark_{config.name}.txt"
    benchmark.save_report(result, report_path)

    return result
