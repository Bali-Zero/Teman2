"""
🌐 Unified Coverage Collector - Best Practice 2026

Raccoglie coverage da TUTTI i componenti del sistema:
- Backend (Python/pytest)
- Frontend (TypeScript/JS - Vitest, Jest)
- Integration (E2E, API contracts)
- WhatsApp/Telegram integrations

Calcola coverage complessivo e differenziale.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ComponentCoverage:
    """Coverage data for a single component"""

    component_name: str
    component_type: str  # "backend" | "frontend" | "integration"
    coverage_percent: float
    files_analyzed: int
    files_below_threshold: int
    total_lines: int
    covered_lines: int
    missing_lines: list[int] = field(default_factory=list)
    coverage_gaps: list[dict[str, Any]] = field(default_factory=list)
    report_path: str = ""
    timestamp: str = ""


@dataclass
class UnifiedCoverageReport:
    """Unified coverage report for entire system"""

    timestamp: str
    overall_coverage: float
    components: dict[str, ComponentCoverage] = field(default_factory=dict)
    coverage_by_type: dict[str, float] = field(default_factory=dict)
    total_files: int = 0
    total_lines: int = 0
    covered_lines: int = 0
    critical_gaps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CoverageDelta:
    """Coverage differential vs baseline"""

    component_name: str
    current_coverage: float
    baseline_coverage: float
    delta: float
    delta_percent: float
    regression: bool
    improvement: bool


class UnifiedCoverageCollector:
    """
    Collects coverage from ALL system components.

    Supports:
    - Backend: Python/pytest (JSON reports)
    - Frontend: TypeScript/JS (LCOV, JSON reports)
    - Integration: E2E tests
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.components = {}

    def collect_backend_coverage(
        self, component_path: Path, component_name: str
    ) -> ComponentCoverage | None:
        """Collect coverage from Python/pytest backend"""
        try:
            logger.info(f"🔍 Collecting backend coverage: {component_name}")

            # Run pytest coverage
            coverage_json = component_path / "coverage.json"
            # If coverage.json doesn't exist, generate it
            if not coverage_json.exists():
                logger.info(f"   Generating coverage for {component_name}...")
                # Longer timeout for large projects (30 minutes)
                timeout = 1800.0 if component_name == "backend-rag" else 600.0
                result = subprocess.run(
                    ["pytest", "--cov=.", "--cov-report=json", "--cov-report=html", "-q"],
                    cwd=component_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode != 0:
                    logger.warning(f"   ⚠️ Coverage generation had issues: {result.stderr[:200]}")
                    # Continue anyway - might have partial coverage

            if not coverage_json.exists():
                logger.warning(f"   ⚠️ No coverage.json found for {component_name}")
                return None

            # Parse coverage.json
            with open(coverage_json) as f:
                coverage_data = json.load(f)

            totals = coverage_data.get("totals", {})
            files_data = coverage_data.get("files", {})

            coverage_percent = totals.get("percent_covered", 0.0)
            total_lines = totals.get("num_statements", 0)
            covered_lines = totals.get("covered_lines", 0)

            # Analyze gaps
            gaps = []
            files_below_threshold = 0
            for file_path, file_data in files_data.items():
                file_coverage = file_data.get("summary", {}).get("percent_covered", 0.0)
                if file_coverage < 99.0:
                    files_below_threshold += 1
                    gaps.append(
                        {
                            "file": file_path,
                            "coverage": file_coverage,
                            "missing_lines": file_data.get("missing_lines", []),
                            "missing_lines_count": len(file_data.get("missing_lines", [])),
                        }
                    )

            return ComponentCoverage(
                component_name=component_name,
                component_type="backend",
                coverage_percent=coverage_percent,
                files_analyzed=len(files_data),
                files_below_threshold=files_below_threshold,
                total_lines=total_lines,
                covered_lines=covered_lines,
                coverage_gaps=gaps,
                report_path=str(coverage_json),
                timestamp=datetime.now().isoformat(),
            )

        except subprocess.TimeoutExpired:
            logger.warning(
                f"⏱️ Coverage generation timeout for {component_name} - "
                f"using existing coverage.json if available"
            )
            # Try to use existing coverage.json even if generation timed out
            if coverage_json.exists():
                try:
                    with open(coverage_json) as f:
                        coverage_data = json.load(f)
                    totals = coverage_data.get("totals", {})
                    files_data = coverage_data.get("files", {})
                    coverage_percent = totals.get("percent_covered", 0.0)
                    logger.info(f"   Using existing coverage: {coverage_percent:.1f}%")
                    # Return partial coverage data
                    return ComponentCoverage(
                        component_name=component_name,
                        component_type="backend",
                        coverage_percent=coverage_percent,
                        files_analyzed=len(files_data),
                        files_below_threshold=0,  # Unknown due to timeout
                        total_lines=totals.get("num_statements", 0),
                        covered_lines=totals.get("covered_lines", 0),
                        coverage_gaps=[],
                        report_path=str(coverage_json),
                        timestamp=datetime.now().isoformat(),
                    )
                except Exception as e2:
                    logger.error(f"❌ Error reading existing coverage: {e2}")
            return None
        except Exception as e:
            logger.error(f"❌ Error collecting backend coverage for {component_name}: {e}")
            return None

    def collect_frontend_coverage(
        self, component_path: Path, component_name: str
    ) -> ComponentCoverage | None:
        """Collect coverage from TypeScript/JS frontend"""
        try:
            logger.info(f"🔍 Collecting frontend coverage: {component_name}")

            # Check for different coverage formats
            lcov_file = component_path / "coverage" / "lcov.info"
            coverage_json = component_path / "coverage" / "coverage-final.json"

            # Try to generate coverage if not exists
            if not lcov_file.exists() and not coverage_json.exists():
                logger.info(f"   Generating coverage for {component_name}...")
                # Check package.json for test:coverage script
                package_json = component_path / "package.json"
                if package_json.exists():
                    with open(package_json) as f:
                        pkg = json.load(f)
                        test_script = pkg.get("scripts", {}).get("test:coverage") or pkg.get(
                            "scripts", {}
                        ).get("test:ci")
                        if test_script:
                            # Longer timeout for large frontend projects (20 minutes)
                            timeout = 1200.0 if component_name == "mouth-frontend" else 600.0
                            try:
                                result = subprocess.run(
                                    test_script.split(),
                                    cwd=component_path,
                                    capture_output=True,
                                    text=True,
                                    timeout=timeout,
                                )
                                if result.returncode != 0:
                                    logger.warning("   ⚠️ Coverage generation had issues")
                            except subprocess.TimeoutExpired:
                                logger.warning(
                                    f"⏱️ Coverage generation timeout for {component_name} - "
                                    f"skipping generation, will use existing if available"
                                )

            # Parse LCOV format (preferred)
            if lcov_file.exists():
                return self._parse_lcov(lcov_file, component_name, component_path)

            # Parse JSON format (Vitest)
            elif coverage_json.exists():
                return self._parse_vitest_json(coverage_json, component_name, component_path)

            else:
                logger.warning(f"   ⚠️ No coverage files found for {component_name}")
                return None

        except Exception as e:
            logger.error(f"❌ Error collecting frontend coverage for {component_name}: {e}")
            return None

    def _parse_lcov(
        self, lcov_file: Path, component_name: str, _component_path: Path
    ) -> ComponentCoverage:
        """Parse LCOV format"""
        total_lines = 0
        hit_lines = 0
        files_data = {}
        current_file = None

        with open(lcov_file) as f:
            for line in f:
                if line.startswith("SF:"):
                    current_file = line[3:].strip()
                    files_data[current_file] = {"lines": {}, "total": 0, "hit": 0}
                elif line.startswith("LF:"):
                    if current_file:
                        files_data[current_file]["total"] = int(line.split(":")[1])
                        total_lines += files_data[current_file]["total"]
                elif line.startswith("LH:"):
                    if current_file:
                        files_data[current_file]["hit"] = int(line.split(":")[1])
                        hit_lines += files_data[current_file]["hit"]
                elif line.startswith("DA:"):
                    # DA:line_number,hit_count
                    if current_file:
                        parts = line[3:].strip().split(",")
                        if len(parts) == 2:
                            line_num = int(parts[0])
                            hit_count = int(parts[1])
                            files_data[current_file]["lines"][line_num] = hit_count

        coverage_percent = (hit_lines / total_lines * 100) if total_lines > 0 else 0.0

        # Analyze gaps
        gaps = []
        files_below_threshold = 0
        for file_path, file_data in files_data.items():
            if file_data["total"] > 0:
                file_coverage = (file_data["hit"] / file_data["total"]) * 100
                if file_coverage < 99.0:
                    files_below_threshold += 1
                    missing_lines = [
                        line_num
                        for line_num, hit_count in file_data["lines"].items()
                        if hit_count == 0
                    ]
                    gaps.append(
                        {
                            "file": file_path,
                            "coverage": file_coverage,
                            "missing_lines": missing_lines,
                            "missing_lines_count": len(missing_lines),
                        }
                    )

        return ComponentCoverage(
            component_name=component_name,
            component_type="frontend",
            coverage_percent=coverage_percent,
            files_analyzed=len(files_data),
            files_below_threshold=files_below_threshold,
            total_lines=total_lines,
            covered_lines=hit_lines,
            coverage_gaps=gaps,
            report_path=str(lcov_file),
            timestamp=datetime.now().isoformat(),
        )

    def _parse_vitest_json(
        self, coverage_json: Path, component_name: str, _component_path: Path
    ) -> ComponentCoverage:
        """Parse Vitest JSON coverage format"""
        with open(coverage_json) as f:
            coverage_data = json.load(f)

        total_lines = 0
        covered_lines = 0
        files_data = {}

        for file_path, file_data in coverage_data.items():
            if isinstance(file_data, dict):
                statements = file_data.get("s", {})  # Statements

                file_total = len(statements)
                file_covered = sum(1 for stmt_id, count in statements.items() if count > 0)

                total_lines += file_total
                covered_lines += file_covered

                files_data[file_path] = {
                    "total": file_total,
                    "covered": file_covered,
                    "coverage": (file_covered / file_total * 100) if file_total > 0 else 0.0,
                }

        coverage_percent = (covered_lines / total_lines * 100) if total_lines > 0 else 0.0

        # Analyze gaps
        gaps = []
        files_below_threshold = 0
        for file_path, file_data in files_data.items():
            if file_data["coverage"] < 99.0:
                files_below_threshold += 1
                gaps.append(
                    {
                        "file": file_path,
                        "coverage": file_data["coverage"],
                        "missing_lines_count": file_data["total"] - file_data["covered"],
                    }
                )

        return ComponentCoverage(
            component_name=component_name,
            component_type="frontend",
            coverage_percent=coverage_percent,
            files_analyzed=len(files_data),
            files_below_threshold=files_below_threshold,
            total_lines=total_lines,
            covered_lines=covered_lines,
            coverage_gaps=gaps,
            report_path=str(coverage_json),
            timestamp=datetime.now().isoformat(),
        )

    def collect_all_coverage(self) -> UnifiedCoverageReport:
        """Collect coverage from ALL system components"""
        logger.info("🌐 Collecting unified coverage from all components...")

        components = {}

        # Backend components
        backend_components = [
            ("apps/backend-rag", "backend-rag"),
            ("apps/zantara-media/backend", "zantara-media-backend"),
            ("apps/bali-intel-scraper", "bali-intel-scraper"),
        ]

        for rel_path, name in backend_components:
            component_path = self.project_root / rel_path
            if component_path.exists():
                coverage = self.collect_backend_coverage(component_path, name)
                if coverage:
                    components[name] = coverage

        # Frontend components
        frontend_components = [
            ("apps/mouth", "mouth-frontend"),
            ("apps/admin-dashboard", "admin-dashboard"),
            ("apps/zantara-media/dashboard", "zantara-media-dashboard"),
        ]

        for rel_path, name in frontend_components:
            component_path = self.project_root / rel_path
            if component_path.exists():
                coverage = self.collect_frontend_coverage(component_path, name)
                if coverage:
                    components[name] = coverage

        # Calculate overall coverage
        total_lines_all = sum(c.total_lines for c in components.values())
        covered_lines_all = sum(c.covered_lines for c in components.values())
        overall_coverage = (
            (covered_lines_all / total_lines_all * 100) if total_lines_all > 0 else 0.0
        )

        # Coverage by type
        coverage_by_type = {}
        for comp_type in ["backend", "frontend", "integration"]:
            type_components = [c for c in components.values() if c.component_type == comp_type]
            if type_components:
                type_total = sum(c.total_lines for c in type_components)
                type_covered = sum(c.covered_lines for c in type_components)
                coverage_by_type[comp_type] = (
                    (type_covered / type_total * 100) if type_total > 0 else 0.0
                )

        # Critical gaps (coverage < 50%)
        critical_gaps = []
        for comp_name, comp_data in components.items():
            for gap in comp_data.coverage_gaps:
                if gap["coverage"] < 50.0:
                    critical_gaps.append(
                        {
                            "component": comp_name,
                            "file": gap["file"],
                            "coverage": gap["coverage"],
                            "missing_lines": gap.get("missing_lines_count", 0),
                        }
                    )

        report = UnifiedCoverageReport(
            timestamp=datetime.now().isoformat(),
            overall_coverage=overall_coverage,
            components=components,
            coverage_by_type=coverage_by_type,
            total_files=sum(c.files_analyzed for c in components.values()),
            total_lines=total_lines_all,
            covered_lines=covered_lines_all,
            critical_gaps=critical_gaps,
        )

        logger.info("✅ Unified coverage collected:")
        logger.info(f"   Overall: {overall_coverage:.1f}%")
        logger.info(f"   Components: {len(components)}")
        logger.info(f"   Backend: {coverage_by_type.get('backend', 0):.1f}%")
        logger.info(f"   Frontend: {coverage_by_type.get('frontend', 0):.1f}%")
        logger.info(f"   Critical gaps: {len(critical_gaps)}")

        return report
