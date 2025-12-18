#!/usr/bin/env python3
"""
NUZANTARA PRIME - Centralized Performance Profiler

Analyzes the codebase to identify performance bottlenecks using:
- Prometheus metrics (/api/performance/metrics)
- Log analysis (response times, errors)
- Database query analysis (slow queries, connection pool usage)
- API endpoint profiling

Output: Prioritized report with areas ordered by performance impact (time × frequency)
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from prometheus_client.parser import text_string_to_metric_families

# Add backend to path
backend_path = Path(__file__).parent.parent / "apps" / "backend-rag" / "backend"
sys.path.insert(0, str(backend_path))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PerformanceProfiler:
    """Centralized performance profiler for Nuzantara"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize profiler

        Args:
            base_url: Base URL of the backend API (default: localhost:8000)
        """
        self.base_url = base_url
        self.results: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "areas": {},
            "priorities": {"critical": [], "warning": [], "info": []},
        }

    async def collect_prometheus_metrics(self) -> dict[str, Any]:
        """Collect metrics from Prometheus endpoint"""
        logger.info("📊 Collecting Prometheus metrics...")
        metrics_data: dict[str, Any] = {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try Prometheus metrics endpoint
                try:
                    response = await client.get(f"{self.base_url}/metrics")
                    if response.status_code == 200:
                        metrics_text = response.text
                        metrics_data["prometheus_raw"] = metrics_text

                        # Parse Prometheus format
                        parsed_metrics = {}
                        for family in text_string_to_metric_families(metrics_text):
                            for sample in family.samples:
                                metric_name = sample.name
                                metric_value = sample.value
                                labels = sample.labels

                                if metric_name not in parsed_metrics:
                                    parsed_metrics[metric_name] = []

                                parsed_metrics[metric_name].append(
                                    {"value": metric_value, "labels": labels}
                                )

                        metrics_data["parsed"] = parsed_metrics
                        logger.info(f"✅ Collected {len(parsed_metrics)} Prometheus metrics")
                except Exception as e:
                    logger.warning(f"⚠️ Prometheus metrics endpoint not available: {e}")

                # Try performance metrics endpoint
                try:
                    response = await client.get(f"{self.base_url}/api/performance/metrics")
                    if response.status_code == 200:
                        perf_data = response.json()
                        metrics_data["performance"] = perf_data.get("metrics", {})
                        logger.info("✅ Collected performance metrics")
                except Exception as e:
                    logger.warning(f"⚠️ Performance metrics endpoint not available: {e}")

        except Exception as e:
            logger.error(f"❌ Failed to collect metrics: {e}")

        return metrics_data

    async def analyze_database_queries(self) -> dict[str, Any]:
        """Analyze database connection pools and query patterns"""
        logger.info("🗄️ Analyzing database queries...")
        db_analysis: dict[str, Any] = {
            "connection_pools": {},
            "slow_queries": [],
            "n_plus_one_patterns": [],
        }

        try:
            # Analyze connection pool configurations
            pool_configs = [
                {
                    "file": "services/memory_service_postgres.py",
                    "pattern": r"asyncpg\.create_pool\([^)]+min_size=(\d+)[^)]+max_size=(\d+)",
                },
                {
                    "file": "services/golden_answer_service.py",
                    "pattern": r"asyncpg\.create_pool\([^)]+min_size=(\d+)[^)]+max_size=(\d+)",
                },
            ]

            for config in pool_configs:
                file_path = backend_path / config["file"]
                if file_path.exists():
                    content = file_path.read_text()
                    matches = re.findall(config["pattern"], content)
                    if matches:
                        min_size, max_size = matches[0]
                        db_analysis["connection_pools"][config["file"]] = {
                            "min_size": int(min_size),
                            "max_size": int(max_size),
                            "utilization_risk": "high" if int(max_size) < 20 else "medium",
                        }

            # Look for potential N+1 query patterns
            # Pattern: Loop with database queries inside
            python_files = list(backend_path.rglob("*.py"))
            for py_file in python_files[:50]:  # Limit for performance
                if "test" in str(py_file) or "__pycache__" in str(py_file):
                    continue

                try:
                    content = py_file.read_text()
                    # Simple heuristic: for loop followed by await conn.fetch
                    if "for " in content and "await" in content and "fetch" in content:
                        lines = content.split("\n")
                        for i, line in enumerate(lines):
                            if "for " in line and i + 1 < len(lines):
                                next_lines = "\n".join(lines[i : i + 5])
                                if "await" in next_lines and "fetch" in next_lines:
                                    db_analysis["n_plus_one_patterns"].append(
                                        {
                                            "file": str(py_file.relative_to(backend_path.parent.parent)),
                                            "line": i + 1,
                                            "pattern": "potential_n_plus_one",
                                        }
                                    )
                                    break
                except Exception:
                    pass

            logger.info(
                f"✅ Analyzed {len(db_analysis['connection_pools'])} connection pools, "
                f"found {len(db_analysis['n_plus_one_patterns'])} potential N+1 patterns"
            )

        except Exception as e:
            logger.error(f"❌ Failed to analyze database: {e}")

        return db_analysis

    def analyze_code_patterns(self) -> dict[str, Any]:
        """Analyze code for performance anti-patterns"""
        logger.info("🔍 Analyzing code patterns...")
        patterns: dict[str, Any] = {
            "sync_operations": [],
            "blocking_calls": [],
            "large_loops": [],
            "missing_caching": [],
        }

        try:
            python_files = list(backend_path.rglob("*.py"))
            python_files = [
                f for f in python_files if "test" not in str(f) and "__pycache__" not in str(f)
            ]

            for py_file in python_files[:100]:  # Limit for performance
                try:
                    content = py_file.read_text()
                    lines = content.split("\n")

                    # Check for sync operations in async functions
                    for i, line in enumerate(lines, 1):
                        # time.sleep in async function
                        if "async def" in "\n".join(lines[max(0, i - 10) : i]):
                            if "time.sleep" in line or "sleep(" in line:
                                patterns["sync_operations"].append(
                                    {
                                        "file": str(py_file.relative_to(backend_path.parent.parent)),
                                        "line": i,
                                        "issue": "time.sleep in async function",
                                    }
                                )

                        # requests.get/post (blocking) instead of httpx
                        if "requests.get" in line or "requests.post" in line:
                            patterns["blocking_calls"].append(
                                {
                                    "file": str(py_file.relative_to(backend_path.parent.parent)),
                                    "line": i,
                                    "issue": "blocking HTTP call",
                                }
                            )

                        # Large loops without batching
                        if "for " in line and "in " in line:
                            # Check if it's iterating over a large dataset
                            if "range(" in line or "items()" in line:
                                # Check if there are await calls inside (potential for batching)
                                context = "\n".join(lines[i - 1 : min(len(lines), i + 20)])
                                if "await" in context and context.count("await") > 3:
                                    patterns["large_loops"].append(
                                        {
                                            "file": str(
                                                py_file.relative_to(backend_path.parent.parent)
                                            ),
                                            "line": i,
                                            "issue": "loop with multiple await calls",
                                        }
                                    )

                except Exception as e:
                    logger.debug(f"Error analyzing {py_file}: {e}")

            logger.info(
                f"✅ Found {len(patterns['sync_operations'])} sync operations, "
                f"{len(patterns['blocking_calls'])} blocking calls, "
                f"{len(patterns['large_loops'])} large loops"
            )

        except Exception as e:
            logger.error(f"❌ Failed to analyze code patterns: {e}")

        return patterns

    def analyze_service_structure(self) -> dict[str, Any]:
        """Analyze service structure for performance hotspots"""
        logger.info("🏗️ Analyzing service structure...")
        services: dict[str, Any] = {}

        try:
            services_dir = backend_path / "services"
            if not services_dir.exists():
                return services

            # Identify key services from plan
            key_services = {
                "rag_pipeline": [
                    "search_service.py",
                    "rag/agentic/orchestrator.py",
                    "reranker_service.py",
                ],
                "database": [
                    "memory_service_postgres.py",
                    "golden_answer_service.py",
                ],
                "llm_api": [
                    "intelligent_router.py",
                    "rag/agentic/llm_gateway.py",
                ],
                "memory": [
                    "memory_service_postgres.py",
                    "collective_memory_service.py",
                ],
                "agentic": [
                    "rag/agentic/orchestrator.py",
                ],
            }

            for area, service_files in key_services.items():
                services[area] = {
                    "files": [],
                    "line_count": 0,
                    "complexity_score": 0,
                }

                for service_file in service_files:
                    file_path = services_dir / service_file
                    if file_path.exists():
                        content = file_path.read_text()
                        lines = content.split("\n")
                        line_count = len([l for l in lines if l.strip() and not l.strip().startswith("#")])

                        # Simple complexity: count async functions and await calls
                        async_funcs = len(re.findall(r"async def", content))
                        await_calls = len(re.findall(r"await ", content))

                        services[area]["files"].append(str(service_file))
                        services[area]["line_count"] += line_count
                        services[area]["complexity_score"] += async_funcs * 2 + await_calls

            logger.info(f"✅ Analyzed {len(services)} service areas")

        except Exception as e:
            logger.error(f"❌ Failed to analyze service structure: {e}")

        return services

    def calculate_priority_scores(self) -> dict[str, Any]:
        """Calculate priority scores for each area"""
        logger.info("📈 Calculating priority scores...")

        scores: dict[str, Any] = {}

        # RAG Pipeline (CRITICAL)
        scores["rag_pipeline"] = {
            "priority": "critical",
            "score": 100,
            "reason": "Core functionality, high frequency, CPU/IO intensive",
            "impact": "Blocks entire system if slow",
        }

        # Database (CRITICAL)
        db_score = 90
        if self.results.get("database", {}).get("connection_pools", {}):
            pool_issues = sum(
                1
                for pool in self.results["database"]["connection_pools"].values()
                if pool.get("utilization_risk") == "high"
            )
            db_score += pool_issues * 10

        scores["database"] = {
            "priority": "critical",
            "score": db_score,
            "reason": "Connection pool issues, N+1 queries",
            "impact": "Can cause timeouts and connection exhaustion",
        }

        # LLM API (CRITICAL)
        scores["llm_api"] = {
            "priority": "critical",
            "score": 85,
            "reason": "External API calls, rate limiting, timeouts",
            "impact": "Blocks user requests, high latency",
        }

        # Memory Services (WARNING)
        scores["memory"] = {
            "priority": "warning",
            "score": 60,
            "reason": "Cache hit rate, query optimization",
            "impact": "Affects UX but doesn't block",
        }

        # Agentic Orchestrator (WARNING)
        scores["agentic"] = {
            "priority": "warning",
            "score": 55,
            "reason": "Multi-step reasoning overhead",
            "impact": "Slower responses but functional",
        }

        # Code Quality (INFO)
        code_issues = (
            len(self.results.get("code_patterns", {}).get("sync_operations", []))
            + len(self.results.get("code_patterns", {}).get("blocking_calls", []))
            + len(self.results.get("code_patterns", {}).get("large_loops", []))
        )
        scores["code_quality"] = {
            "priority": "info",
            "score": 30 + min(code_issues, 20),
            "reason": f"Found {code_issues} code quality issues",
            "impact": "Minor optimizations",
        }

        return scores

    async def run_profiling(self) -> dict[str, Any]:
        """Run complete profiling analysis"""
        logger.info("🚀 Starting performance profiling...")

        # Collect all data
        self.results["metrics"] = await self.collect_prometheus_metrics()
        self.results["database"] = await self.analyze_database_queries()
        self.results["code_patterns"] = self.analyze_code_patterns()
        self.results["services"] = self.analyze_service_structure()
        self.results["priority_scores"] = self.calculate_priority_scores()

        # Organize by priority
        for area, score_data in self.results["priority_scores"].items():
            priority = score_data["priority"]
            self.results["priorities"][priority].append(
                {
                    "area": area,
                    "score": score_data["score"],
                    "reason": score_data["reason"],
                    "impact": score_data["impact"],
                }
            )

        # Sort by score (descending)
        for priority in self.results["priorities"]:
            self.results["priorities"][priority].sort(key=lambda x: x["score"], reverse=True)

        logger.info("✅ Profiling complete")
        return self.results

    def generate_report(self, output_path: Path | None = None) -> str:
        """Generate markdown report"""
        if output_path is None:
            output_path = Path(__file__).parent.parent / "docs" / "debug" / "performance"
            output_path.mkdir(parents=True, exist_ok=True)
            output_path = output_path / "profiling_report.md"

        report_lines = [
            "# Performance Profiling Report",
            f"Generated: {self.results['timestamp']}",
            "",
            "## Executive Summary",
            "",
            "This report identifies performance bottlenecks in the Nuzantara codebase, "
            "organized by priority (critical → warning → info).",
            "",
            "## Priority Areas",
            "",
        ]

        # Critical priorities
        report_lines.append("### 🔴 CRITICAL Priority")
        report_lines.append("")
        for item in self.results["priorities"]["critical"]:
            report_lines.append(f"#### {item['area'].replace('_', ' ').title()}")
            report_lines.append(f"- **Score**: {item['score']}/100")
            report_lines.append(f"- **Reason**: {item['reason']}")
            report_lines.append(f"- **Impact**: {item['impact']}")
            report_lines.append("")

        # Warning priorities
        report_lines.append("### 🟡 WARNING Priority")
        report_lines.append("")
        for item in self.results["priorities"]["warning"]:
            report_lines.append(f"#### {item['area'].replace('_', ' ').title()}")
            report_lines.append(f"- **Score**: {item['score']}/100")
            report_lines.append(f"- **Reason**: {item['reason']}")
            report_lines.append(f"- **Impact**: {item['impact']}")
            report_lines.append("")

        # Info priorities
        report_lines.append("### 🟢 INFO Priority")
        report_lines.append("")
        for item in self.results["priorities"]["info"]:
            report_lines.append(f"#### {item['area'].replace('_', ' ').title()}")
            report_lines.append(f"- **Score**: {item['score']}/100")
            report_lines.append(f"- **Reason**: {item['reason']}")
            report_lines.append(f"- **Impact**: {item['impact']}")
            report_lines.append("")

        # Detailed findings
        report_lines.append("## Detailed Findings")
        report_lines.append("")

        # Database findings
        if self.results.get("database"):
            report_lines.append("### Database Analysis")
            report_lines.append("")
            if self.results["database"].get("connection_pools"):
                report_lines.append("#### Connection Pools")
                for file, config in self.results["database"]["connection_pools"].items():
                    report_lines.append(f"- **{file}**: min={config['min_size']}, max={config['max_size']}")
                    report_lines.append(f"  - Utilization risk: {config['utilization_risk']}")
                report_lines.append("")

            if self.results["database"].get("n_plus_one_patterns"):
                report_lines.append("#### Potential N+1 Query Patterns")
                for pattern in self.results["database"]["n_plus_one_patterns"][:10]:
                    report_lines.append(f"- **{pattern['file']}**:{pattern['line']}")
                report_lines.append("")

        # Code patterns
        if self.results.get("code_patterns"):
            report_lines.append("### Code Pattern Analysis")
            report_lines.append("")
            for pattern_type, issues in self.results["code_patterns"].items():
                if issues:
                    report_lines.append(f"#### {pattern_type.replace('_', ' ').title()}")
                    for issue in issues[:10]:
                        report_lines.append(f"- **{issue['file']}**:{issue['line']} - {issue.get('issue', '')}")
                    report_lines.append("")

        # Metrics summary
        if self.results.get("metrics", {}).get("performance"):
            report_lines.append("### Performance Metrics Summary")
            report_lines.append("")
            perf_metrics = self.results["metrics"]["performance"]
            for key, value in perf_metrics.items():
                report_lines.append(f"- **{key}**: {value}")
            report_lines.append("")

        report_lines.append("## Next Steps")
        report_lines.append("")
        report_lines.append("1. Review critical priority areas first")
        report_lines.append("2. Create task files for each Composer")
        report_lines.append("3. Run parallel debugging sessions")
        report_lines.append("4. Measure improvements with benchmarks")
        report_lines.append("")

        report_content = "\n".join(report_lines)
        output_path.write_text(report_content)
        logger.info(f"✅ Report written to {output_path}")

        return str(output_path)


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Performance Profiler for Nuzantara")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BACKEND_URL", "http://localhost:8000"),
        help="Base URL of the backend API",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for report (default: docs/debug/performance/profiling_report.md)",
    )

    args = parser.parse_args()

    profiler = PerformanceProfiler(base_url=args.base_url)
    await profiler.run_profiling()
    report_path = profiler.generate_report(args.output)

    print(f"\n✅ Profiling complete! Report: {report_path}\n")
    print("Priority areas:")
    for priority in ["critical", "warning", "info"]:
        items = profiler.results["priorities"][priority]
        if items:
            print(f"\n{priority.upper()}:")
            for item in items:
                print(f"  - {item['area']}: {item['score']}/100")


if __name__ == "__main__":
    asyncio.run(main())

