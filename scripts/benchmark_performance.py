#!/usr/bin/env python3
"""
NUZANTARA PRIME - Performance Benchmark Script

Benchmarks RAG pipeline and database performance before/after Phase 1 fixes.
Measures:
- RAG pipeline timing (embedding, search, reranking)
- Database query performance
- Early exit rate
- Cache hit rates

Usage:
    python scripts/benchmark_performance.py --baseline  # Before fixes
    python scripts/benchmark_performance.py --compare   # After fixes
    python scripts/benchmark_performance.py --both      # Both with comparison
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# Add backend to path
backend_path = Path(__file__).parent.parent / "apps" / "backend-rag" / "backend"
sys.path.insert(0, str(backend_path))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """Performance benchmark for Phase 1 fixes"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize benchmark

        Args:
            base_url: Base URL of the backend API
        """
        self.base_url = base_url
        self.results: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {},
        }

    async def benchmark_rag_search(self, query: str, iterations: int = 10) -> dict[str, Any]:
        """Benchmark RAG search performance"""
        logger.info(f"🔍 Benchmarking RAG search: '{query}' ({iterations} iterations)")

        timings = {
            "total": [],
            "embedding": [],
            "search": [],
            "reranking": [],
            "early_exits": 0,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(iterations):
                try:
                    start_time = time.time()

                    # Call search endpoint (adjust endpoint as needed)
                    response = await client.post(
                        f"{self.base_url}/api/search",
                        json={"query": query, "user_level": 3, "limit": 5},
                        headers={"Content-Type": "application/json"},
                    )

                    total_time = time.time() - start_time

                    if response.status_code == 200:
                        data = response.json()
                        timings["total"].append(total_time)

                        # Extract timing info if available
                        if "early_exit" in data:
                            if data["early_exit"]:
                                timings["early_exits"] += 1

                        # Try to get component timings from response
                        if "timings" in data:
                            timings["embedding"].append(data["timings"].get("embedding", 0))
                            timings["search"].append(data["timings"].get("search", 0))
                            timings["reranking"].append(data["timings"].get("reranking", 0))

                    await asyncio.sleep(0.1)  # Small delay between requests

                except Exception as e:
                    logger.error(f"Benchmark iteration {i+1} failed: {e}")

        # Calculate statistics
        stats = {
            "query": query,
            "iterations": iterations,
            "total_time": {
                "mean": sum(timings["total"]) / len(timings["total"]) if timings["total"] else 0,
                "min": min(timings["total"]) if timings["total"] else 0,
                "max": max(timings["total"]) if timings["total"] else 0,
                "p95": sorted(timings["total"])[int(len(timings["total"]) * 0.95)]
                if timings["total"]
                else 0,
            },
            "early_exit_rate": timings["early_exits"] / iterations if iterations > 0 else 0,
        }

        if timings["embedding"]:
            stats["embedding_time"] = {
                "mean": sum(timings["embedding"]) / len(timings["embedding"]),
            }

        if timings["search"]:
            stats["search_time"] = {
                "mean": sum(timings["search"]) / len(timings["search"]),
            }

        if timings["reranking"]:
            stats["reranking_time"] = {
                "mean": sum(timings["reranking"]) / len(timings["reranking"]),
            }

        return stats

    async def benchmark_database_query(self, iterations: int = 100) -> dict[str, Any]:
        """Benchmark database query performance"""
        logger.info(f"🗄️ Benchmarking database queries ({iterations} iterations)")

        # This would require direct database access or a test endpoint
        # For now, we'll use Prometheus metrics if available
        timings = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Try to get database metrics from Prometheus
                response = await client.get(f"{self.base_url}/metrics")
                if response.status_code == 200:
                    # Parse Prometheus metrics for db_query_duration
                    metrics_text = response.text
                    for line in metrics_text.split("\n"):
                        if "zantara_db_query_duration_seconds" in line and not line.startswith("#"):
                            # Extract metric value
                            parts = line.split()
                            if len(parts) >= 2:
                                try:
                                    value = float(parts[-1])
                                    timings.append(value)
                                except ValueError:
                                    pass
            except Exception as e:
                logger.warning(f"Could not fetch database metrics: {e}")

        stats = {
            "iterations": iterations,
            "query_time": {
                "mean": sum(timings) / len(timings) if timings else 0,
                "min": min(timings) if timings else 0,
                "max": max(timings) if timings else 0,
            },
            "note": "Metrics from Prometheus if available",
        }

        return stats

    async def get_prometheus_metrics(self) -> dict[str, Any]:
        """Get current Prometheus metrics"""
        logger.info("📊 Fetching Prometheus metrics...")

        metrics_data: dict[str, Any] = {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/metrics")
                if response.status_code == 200:
                    metrics_text = response.text

                    # Extract key metrics
                    for line in metrics_text.split("\n"):
                        if "zantara_rag_" in line and not line.startswith("#"):
                            parts = line.split()
                            if len(parts) >= 2:
                                metric_name = parts[0]
                                try:
                                    value = float(parts[-1])
                                    metrics_data[metric_name] = value
                                except ValueError:
                                    pass
            except Exception as e:
                logger.warning(f"Could not fetch Prometheus metrics: {e}")

        return metrics_data

    async def run_benchmark(self, mode: str = "both") -> dict[str, Any]:
        """Run benchmark suite"""
        logger.info(f"🚀 Starting performance benchmark (mode: {mode})")

        # Test queries
        test_queries = [
            "What is a KITAS visa?",
            "How much does it cost to set up a PT PMA?",
            "What are the requirements for investor KITAS?",
            "Tell me about Bali Zero team",
            "What is the tax rate for foreign companies?",
        ]

        # Benchmark RAG searches
        rag_results = []
        for query in test_queries:
            result = await self.benchmark_rag_search(query, iterations=5)
            rag_results.append(result)
            self.results["tests"].append({"type": "rag_search", "result": result})

        # Benchmark database (if possible)
        db_result = await self.benchmark_database_query(iterations=10)
        self.results["tests"].append({"type": "database_query", "result": db_result})

        # Get Prometheus metrics
        prometheus_metrics = await self.get_prometheus_metrics()
        self.results["prometheus_metrics"] = prometheus_metrics

        # Calculate summary
        if rag_results:
            total_times = [r["total_time"]["mean"] for r in rag_results if "total_time" in r]
            self.results["summary"] = {
                "rag_pipeline": {
                    "mean_time": sum(total_times) / len(total_times) if total_times else 0,
                    "min_time": min(total_times) if total_times else 0,
                    "max_time": max(total_times) if total_times else 0,
                },
                "early_exit_rate": sum(r.get("early_exit_rate", 0) for r in rag_results)
                / len(rag_results)
                if rag_results
                else 0,
                "database": db_result,
                "prometheus_metrics": prometheus_metrics,
            }

        return self.results

    def save_results(self, output_path: Path | None = None, label: str = "") -> str:
        """Save benchmark results to JSON file"""
        if output_path is None:
            output_path = Path(__file__).parent.parent / "docs" / "debug" / "performance" / "benchmarks"
            output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_{label}_{timestamp}.json" if label else f"benchmark_{timestamp}.json"
        file_path = output_path / filename

        file_path.write_text(json.dumps(self.results, indent=2))
        logger.info(f"✅ Benchmark results saved to {file_path}")

        return str(file_path)

    def compare_results(self, baseline_path: str, compare_path: str) -> dict[str, Any]:
        """Compare baseline and comparison results"""
        baseline = json.loads(Path(baseline_path).read_text())
        compare = json.loads(Path(compare_path).read_text())

        comparison = {
            "baseline_file": baseline_path,
            "compare_file": compare_path,
            "improvements": {},
        }

        # Compare RAG pipeline times
        baseline_mean = baseline.get("summary", {}).get("rag_pipeline", {}).get("mean_time", 0)
        compare_mean = compare.get("summary", {}).get("rag_pipeline", {}).get("mean_time", 0)

        if baseline_mean > 0:
            improvement = ((baseline_mean - compare_mean) / baseline_mean) * 100
            comparison["improvements"]["rag_pipeline_time"] = {
                "baseline": baseline_mean,
                "compare": compare_mean,
                "improvement_percent": improvement,
            }

        # Compare early exit rates
        baseline_exit = baseline.get("summary", {}).get("early_exit_rate", 0)
        compare_exit = compare.get("summary", {}).get("early_exit_rate", 0)
        comparison["improvements"]["early_exit_rate"] = {
            "baseline": baseline_exit,
            "compare": compare_exit,
            "improvement": compare_exit - baseline_exit,
        }

        return comparison


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Performance Benchmark for Phase 1 Fixes")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the backend API",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Run baseline benchmark (before fixes)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run comparison benchmark (after fixes)",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Run both baseline and comparison",
    )

    args = parser.parse_args()

    benchmark = PerformanceBenchmark(base_url=args.base_url)

    if args.baseline or args.both:
        logger.info("📊 Running BASELINE benchmark...")
        results = await benchmark.run_benchmark(mode="baseline")
        baseline_path = benchmark.save_results(label="baseline")
        print(f"\n✅ Baseline benchmark complete: {baseline_path}")

    if args.compare or args.both:
        logger.info("📊 Running COMPARISON benchmark...")
        results = await benchmark.run_benchmark(mode="compare")
        compare_path = benchmark.save_results(label="compare")
        print(f"\n✅ Comparison benchmark complete: {compare_path}")

        if args.both:
            comparison = benchmark.compare_results(baseline_path, compare_path)
            print("\n📈 COMPARISON RESULTS:")
            print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

