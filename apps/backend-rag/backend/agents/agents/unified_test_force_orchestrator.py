"""
🌐 Unified Test Force Orchestrator - Best Practice 2026

Sistema completo per testare TUTTO il sistema:
- Backend (Python)
- Frontend (TypeScript/JS)
- Integration (E2E, API)
- WhatsApp/Telegram

Calcola coverage complessivo e differenziale.
Genera test con Qwen per tutti i componenti.
"""
from __future__ import annotations


import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.agents.services.differential_coverage_analyzer import (
    DifferentialCoverageAnalyzer,
)
from backend.agents.services.llm_adapter import LLMProvider, LLMRequest, get_llm_adapter

# Import system prompts configuration
try:
    from backend.agents.config.qwen_system_prompts import (
        SYSTEM_PROMPTS,
        TEST_GENERATION_SYSTEM_PROMPT_BACKEND,
        TEST_GENERATION_SYSTEM_PROMPT_FRONTEND,
    )
except ImportError:
    # Fallback if config not available
    TEST_GENERATION_SYSTEM_PROMPT_BACKEND = None
    TEST_GENERATION_SYSTEM_PROMPT_FRONTEND = None
    SYSTEM_PROMPTS = {}
from backend.agents.services.test_metrics import get_metrics_collector
from backend.agents.services.unified_coverage_collector import (
    UnifiedCoverageCollector,
    UnifiedCoverageReport,
)

logger = logging.getLogger(__name__)


class UnifiedTestForceOrchestrator:
    """
    Unified orchestrator for testing entire Nuzantara system.

    Features:
    - Collects coverage from ALL components
    - Calculates differential coverage
    - Generates tests for all components using Qwen
    - Provides unified reporting
    """

    def __init__(self, project_root: Path, llm_provider: str = "local") -> None:
        self.project_root = project_root
        self.llm_provider = llm_provider

        # Initialize services
        self.coverage_collector = UnifiedCoverageCollector(project_root)
        self.differential_analyzer = DifferentialCoverageAnalyzer(project_root)

        # Initialize LLM adapter
        self.llm_adapter = get_llm_adapter()
        self.metrics_collector = get_metrics_collector()
        self.orchestrator_metrics = self.metrics_collector.register_agent("UnifiedOrchestrator")

        logger.info("🌐 Unified Test Force Orchestrator initialized")

    async def run_full_analysis(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Run comprehensive analysis of entire system.

        Steps:
        1. Collect coverage from all components
        2. Calculate differential vs baseline
        3. Identify critical gaps
        4. Generate tests for gaps (using Qwen)
        """
        start_time = time.time()
        options = options or {}

        logger.info("🚀 Starting unified system analysis...")

        results = {
            "analysis_type": "unified_full",
            "start_time": datetime.now().isoformat(),
            "components_analyzed": [],
            "coverage_report": None,
            "differential_report": None,
            "test_generation": {},
            "summary": {},
        }

        try:
            # Step 1: Collect coverage from ALL components
            logger.info("📊 Step 1: Collecting coverage from all components...")
            coverage_report = self.coverage_collector.collect_all_coverage()
            results["coverage_report"] = {
                "overall_coverage": coverage_report.overall_coverage,
                "components": {
                    name: {
                        "type": comp.component_type,
                        "coverage": comp.coverage_percent,
                        "files": comp.files_analyzed,
                        "gaps": len(comp.coverage_gaps),
                    }
                    for name, comp in coverage_report.components.items()
                },
                "coverage_by_type": coverage_report.coverage_by_type,
                "critical_gaps": len(coverage_report.critical_gaps),
            }
            results["components_analyzed"] = list(coverage_report.components.keys())

            # Step 2: Calculate differential vs baseline
            logger.info("📈 Step 2: Calculating coverage differential...")
            differential = self.differential_analyzer.calculate_delta(coverage_report)
            if differential:
                results["differential_report"] = {
                    "overall_delta": differential.overall_delta,
                    "overall_delta_percent": differential.overall_delta_percent,
                    "regressions": len(differential.regressions),
                    "improvements": len(differential.improvements),
                    "critical_regressions": len(differential.critical_regressions),
                }

            # Step 3: Save baseline if requested
            if options.get("save_baseline", False):
                logger.info("💾 Step 3: Saving baseline...")
                self.differential_analyzer.save_baseline(coverage_report)

            # Step 4: Generate tests for critical gaps (using Qwen)
            if options.get("generate_tests", True):
                logger.info("🤖 Step 4: Generating tests for critical gaps (Qwen)...")
                test_generation = await self._generate_tests_for_gaps(
                    coverage_report, options.get("max_tests_per_component", 5)
                )
                results["test_generation"] = test_generation

                # Step 5: Ricalcola coverage dopo i test generati ed eseguiti
                if test_generation.get("tests_passed", 0) > 0:
                    logger.info("📊 Step 5: Ricalcolo coverage dopo test generati...")
                    updated_coverage = await self._recalculate_coverage_after_tests()
                    if updated_coverage:
                        logger.info(
                            f"   ✅ Coverage aggiornata: {updated_coverage.get('overall_coverage', 0):.1f}%"
                        )
                        # Aggiorna coverage nel report
                        coverage_report.overall_coverage = updated_coverage.get(
                            "overall_coverage", coverage_report.overall_coverage
                        )
                        results["coverage_report"]["overall_coverage"] = (
                            coverage_report.overall_coverage
                        )
                        results["coverage_after_tests"] = updated_coverage

            # Generate summary
            duration = time.time() - start_time
            results["duration"] = duration
            results["end_time"] = datetime.now().isoformat()
            results["summary"] = self._generate_summary(results)

            # Record metrics
            self.orchestrator_metrics.record_operation(duration, True)

            logger.info(f"✅ Unified analysis completed in {duration:.2f}s")
            self._log_summary(results["summary"])

            return results

        except Exception as e:
            error_msg = f"Unified analysis failed: {e}"
            logger.error(f"❌ {error_msg}")
            import traceback

            traceback.print_exc()
            self.orchestrator_metrics.record_operation(time.time() - start_time, False, error_msg)
            # Try to return partial results if available
            partial_results = {
                "success": False,
                "error": error_msg,
                "coverage_report": results.get("coverage_report"),
                "test_generation": results.get("test_generation"),
                "components_analyzed": results.get("components_analyzed", []),
            }
            return partial_results

    async def _generate_tests_for_gaps(
        self, coverage_report: UnifiedCoverageReport, max_per_component: int
    ) -> dict[str, Any]:
        """Generate tests for coverage gaps using Qwen"""
        test_results = {
            "tests_generated": 0,
            "tests_by_component": {},
            "tests_passed": 0,
            "tests_failed": 0,
        }

        # Prioritize critical gaps
        all_gaps = []
        for comp_name, comp_data in coverage_report.components.items():
            for gap in comp_data.coverage_gaps[:max_per_component]:  # Top N gaps per component
                all_gaps.append(
                    {
                        "component": comp_name,
                        "component_type": comp_data.component_type,
                        "file": gap["file"],
                        "coverage": gap["coverage"],
                        "missing_lines": gap.get("missing_lines", []),
                        "missing_lines_count": gap.get("missing_lines_count", 0),
                    }
                )

        # Sort by priority (lowest coverage first)
        all_gaps.sort(key=lambda x: x["coverage"])

        logger.info(f"🎯 Generating tests for {len(all_gaps)} critical gaps...")

        for i, gap in enumerate(all_gaps[:20], 1):  # Limit to top 20 gaps
            logger.info(
                f"   [{i}/{min(len(all_gaps), 20)}] Generating test for {gap['component']}/{gap['file']}"
            )

            try:
                test_code = await self._generate_test_with_qwen(gap)
                if test_code:
                    # Salva il test generato in file
                    test_file_path = self._save_test_file(gap, test_code)
                    if test_file_path:
                        test_results["tests_generated"] += 1
                        comp_name = gap["component"]
                        if comp_name not in test_results["tests_by_component"]:
                            test_results["tests_by_component"][comp_name] = 0
                        test_results["tests_by_component"][comp_name] += 1

                        # Esegui il test per verificare che funzioni
                        test_passed = await self._run_test(test_file_path, gap)
                        if test_passed:
                            test_results["tests_passed"] += 1
                        else:
                            test_results["tests_failed"] += 1
                    else:
                        logger.warning(f"   ⚠️ Failed to save test for {gap['file']}")
                        test_results["tests_failed"] += 1

            except Exception as e:
                logger.error(f"   ❌ Failed to generate test: {e}")
                test_results["tests_failed"] += 1

        return test_results

    async def _generate_test_with_qwen(self, gap: dict[str, Any]) -> str | None:
        """Generate test code using Qwen"""
        component_type = gap["component_type"]
        file_path = gap["file"]
        coverage = gap["coverage"]
        missing_lines = gap.get("missing_lines", [])

        # Build context-aware prompt
        if component_type == "backend":
            prompt = f"""Generate comprehensive pytest unit tests for this Python file to improve coverage from {coverage:.1f}% to 99%+.

File: {file_path}
Missing lines: {missing_lines[:20]}  # Showing first 20

Requirements:
1. Use pytest and pytest-asyncio if needed
2. Mock ALL external dependencies
3. Test all missing lines
4. Achieve 99%+ coverage
5. Return ONLY Python code, no markdown

Generate complete test file."""
        else:  # frontend
            prompt = f"""Generate comprehensive Vitest unit tests for this TypeScript/React file to improve coverage from {coverage:.1f}% to 99%+.

File: {file_path}
Missing lines count: {gap.get("missing_lines_count", 0)}

Requirements:
1. Use Vitest and @testing-library/react
2. Mock external dependencies
3. Test all components and functions
4. Achieve 99%+ coverage
5. Return ONLY TypeScript/TSX code, no markdown

Generate complete test file."""

        # Select appropriate system prompt based on component type
        system_prompt = (
            TEST_GENERATION_SYSTEM_PROMPT_BACKEND
            if component_type == "backend"
            else TEST_GENERATION_SYSTEM_PROMPT_FRONTEND
        )

        request = LLMRequest(
            prompt=prompt,
            max_tokens=2000,  # Reduced to avoid timeouts - can generate multiple smaller requests if needed
            temperature=0.2,
            provider=LLMProvider.OLLAMA,
            system=system_prompt,  # Add system prompt to define Qwen behavior
        )

        try:
            response = await self.llm_adapter.generate(request)
            if response.provider == LLMProvider.OLLAMA:
                return response.text
            else:
                logger.warning("⚠️ Fallback to Mock - Qwen unavailable")
                return None
        except Exception as e:
            logger.error(f"❌ Qwen generation failed: {e}")
            return None

    def _save_test_file(self, gap: dict[str, Any], test_code: str) -> str | None:
        """Save generated test code to file"""
        try:
            file_path = Path(gap["file"])
            component = gap["component"]
            component_type = gap["component_type"]

            # Determina directory test basata sul componente
            if component == "zantara-media-backend":
                test_dir = Path("apps/zantara-media-backend/tests")
            elif component == "bali-intel-scraper":
                test_dir = Path("apps/bali-intel-scraper/tests/unit")
            elif component == "mouth-frontend":
                test_dir = Path("apps/mouth-frontend/tests")
            else:
                # Default: cerca directory tests nel componente
                component_path = Path(f"apps/{component}")
                test_dir = (
                    component_path / "tests" / "unit"
                    if (component_path / "tests" / "unit").exists()
                    else component_path / "tests"
                )

            # Crea directory se non esiste
            test_dir.mkdir(parents=True, exist_ok=True)

            # Nome file test basato sul file originale
            test_filename = (
                f"test_{file_path.stem}.py"
                if component_type == "backend"
                else f"{file_path.stem}.test.ts"
            )
            test_file_path = test_dir / test_filename

            # Salva il test
            with open(test_file_path, "w") as f:
                f.write(test_code)

            logger.info(f"   ✅ Test salvato: {test_file_path}")
            return str(test_file_path)

        except Exception as e:
            logger.error(f"   ❌ Errore salvataggio test: {e}")
            return None

    async def _run_test(self, test_file_path: str, gap: dict[str, Any]) -> bool:
        """Run generated test to verify it works"""
        try:
            component_type = gap["component_type"]
            component = gap["component"]

            if component_type == "backend":
                # Esegui pytest
                import subprocess

                result = subprocess.run(
                    ["pytest", test_file_path, "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=60.0,
                    cwd=Path("apps") / component,
                )
                if result.returncode == 0:
                    logger.info(f"   ✅ Test passato: {test_file_path}")
                    return True
                else:
                    logger.warning(f"   ⚠️ Test fallito: {test_file_path}")
                    logger.debug(f"   Output: {result.stderr[:200]}")
                    return False
            else:
                # Frontend: esegui vitest
                import subprocess

                result = subprocess.run(
                    ["npm", "run", "test", "--", test_file_path],
                    capture_output=True,
                    text=True,
                    timeout=60.0,
                    cwd=Path("apps") / component,
                )
                if result.returncode == 0:
                    logger.info(f"   ✅ Test passato: {test_file_path}")
                    return True
                else:
                    logger.warning(f"   ⚠️ Test fallito: {test_file_path}")
                    return False

        except Exception as e:
            logger.warning(f"   ⚠️ Errore esecuzione test: {e}")
            return False

    async def _recalculate_coverage_after_tests(self) -> dict[str, Any] | None:
        """Ricalcola coverage dopo aver generato ed eseguito i test"""
        try:
            # Raccogli coverage aggiornata
            collector = UnifiedCoverageCollector()
            updated_report = await collector.collect_all_coverage()

            if updated_report:
                logger.info(f"   📊 Coverage aggiornata: {updated_report.overall_coverage:.1f}%")
                return {
                    "overall_coverage": updated_report.overall_coverage,
                    "components": {
                        name: {
                            "coverage": comp.coverage,
                            "files": comp.files_count,
                        }
                        for name, comp in updated_report.components.items()
                    },
                }
            return None
        except Exception as e:
            logger.warning(f"   ⚠️ Errore ricalcolo coverage: {e}")
            return None

    def _generate_summary(self, results: dict[str, Any]) -> dict[str, Any]:
        """Generate comprehensive summary"""
        differential_report = results.get("differential_report")
        summary = {
            "duration": results.get("duration", 0),
            "components_analyzed": len(results.get("components_analyzed", [])),
            "overall_coverage": results.get("coverage_report", {}).get("overall_coverage", 0.0),
            "tests_generated": results.get("test_generation", {}).get("tests_generated", 0),
            "regressions": differential_report.get("regressions", 0) if differential_report else 0,
            "improvements": differential_report.get("improvements", 0)
            if differential_report
            else 0,
        }
        return summary

    def _log_summary(self, summary: dict[str, Any]):
        """Log summary information"""
        logger.info("📊 Unified Analysis Summary:")
        logger.info(f"   Duration: {summary.get('duration', 0):.2f}s")
        logger.info(f"   Components analyzed: {summary.get('components_analyzed', 0)}")
        logger.info(f"   Overall coverage: {summary.get('overall_coverage', 0):.1f}%")
        logger.info(f"   Tests generated: {summary.get('tests_generated', 0)}")
        if summary.get("regressions", 0) > 0:
            logger.warning(f"   ⚠️ Regressions: {summary.get('regressions', 0)}")
        if summary.get("improvements", 0) > 0:
            logger.info(f"   ✅ Improvements: {summary.get('improvements', 0)}")

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up Unified Orchestrator...")
        # Cleanup handled by singleton adapters


# CLI interface
async def main():
    """Main CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Unified Test Force Orchestrator")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--provider", default="local", choices=["local", "mock"])
    parser.add_argument("--save-baseline", action="store_true", help="Save current as baseline")
    parser.add_argument(
        "--generate-tests", action="store_true", default=True, help="Generate tests"
    )
    parser.add_argument("--max-tests", type=int, default=5, help="Max tests per component")
    parser.add_argument("--output", help="Output JSON report file")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] 🌐 UnifiedTestForce: %(message)s",
    )

    # Create orchestrator
    project_root = Path(args.project_root).resolve()
    orchestrator = UnifiedTestForceOrchestrator(project_root, llm_provider=args.provider)

    try:
        # Run analysis
        options = {
            "save_baseline": args.save_baseline,
            "generate_tests": args.generate_tests,
            "max_tests_per_component": args.max_tests,
        }

        result = await orchestrator.run_full_analysis(options)

        # Output results
        if args.output:
            import json

            with open(args.output, "w") as f:
                json.dump(result, f, indent=2, default=str)
            logger.info(f"📄 Report saved to: {args.output}")
        else:
            import json

            logger.info("\n" + json.dumps(result, indent=2, default=str))

    finally:
        await orchestrator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
