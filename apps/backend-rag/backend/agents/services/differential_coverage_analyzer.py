"""
📊 Differential Coverage Analyzer - Best Practice 2026

Calcola coverage differenziale vs baseline.
Identifica regressioni e miglioramenti.
"""
from __future__ import annotations


import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .unified_coverage_collector import UnifiedCoverageReport

logger = logging.getLogger(__name__)


@dataclass
class CoverageDelta:
    """Coverage differential vs baseline"""

    component_name: str
    component_type: str
    current_coverage: float
    baseline_coverage: float
    delta: float
    delta_percent: float
    regression: bool
    improvement: bool
    files_added: int = 0
    files_removed: int = 0
    files_improved: int = 0
    files_regressed: int = 0


@dataclass
class DifferentialReport:
    """Differential coverage report"""

    timestamp: str
    baseline_timestamp: str
    overall_delta: float
    overall_delta_percent: float
    component_deltas: dict[str, CoverageDelta]
    regressions: list[CoverageDelta]
    improvements: list[CoverageDelta]
    critical_regressions: list[CoverageDelta]


class DifferentialCoverageAnalyzer:
    """
    Analyzes coverage differential vs baseline.

    Features:
    - Baseline tracking (git-based or snapshot)
    - Delta calculation
    - Regression detection
    - Improvement tracking
    """

    def __init__(self, project_root: Path, baseline_dir: Path | None = None) -> None:
        self.project_root = project_root
        self.baseline_dir = baseline_dir or (project_root / "coverage_baselines")
        self.baseline_dir.mkdir(exist_ok=True)

    def save_baseline(self, report: UnifiedCoverageReport, baseline_name: str = "latest") -> Path:
        """Save current coverage as baseline"""
        baseline_file = self.baseline_dir / f"{baseline_name}.json"

        baseline_data = {
            "timestamp": report.timestamp,
            "overall_coverage": report.overall_coverage,
            "components": {},
            "coverage_by_type": report.coverage_by_type,
            "total_files": report.total_files,
            "total_lines": report.total_lines,
            "covered_lines": report.covered_lines,
        }

        # Serialize components
        for comp_name, comp_data in report.components.items():
            baseline_data["components"][comp_name] = {
                "component_type": comp_data.component_type,
                "coverage_percent": comp_data.coverage_percent,
                "files_analyzed": comp_data.files_analyzed,
                "total_lines": comp_data.total_lines,
                "covered_lines": comp_data.covered_lines,
                "timestamp": comp_data.timestamp,
            }

        with open(baseline_file, "w") as f:
            json.dump(baseline_data, f, indent=2)

        logger.info(f"💾 Baseline saved: {baseline_file}")
        return baseline_file

    def load_baseline(self, baseline_name: str = "latest") -> dict[str, Any] | None:
        """Load baseline coverage"""
        baseline_file = self.baseline_dir / f"{baseline_name}.json"

        if not baseline_file.exists():
            logger.warning(f"⚠️ Baseline not found: {baseline_file}")
            return None

        with open(baseline_file) as f:
            return json.load(f)

    def calculate_delta(
        self, current_report: UnifiedCoverageReport, baseline_name: str = "latest"
    ) -> DifferentialReport | None:
        """Calculate coverage delta vs baseline"""
        baseline = self.load_baseline(baseline_name)

        if not baseline:
            logger.warning("⚠️ No baseline found - cannot calculate delta")
            return None

        logger.info("📊 Calculating coverage differential...")

        component_deltas = {}
        regressions = []
        improvements = []

        # Calculate overall delta
        baseline_overall = baseline.get("overall_coverage", 0.0)
        overall_delta = current_report.overall_coverage - baseline_overall
        overall_delta_percent = (
            (overall_delta / baseline_overall * 100) if baseline_overall > 0 else 0.0
        )

        # Calculate per-component deltas
        baseline_components = baseline.get("components", {})
        for comp_name, current_comp in current_report.components.items():
            baseline_comp = baseline_components.get(comp_name)

            if baseline_comp:
                baseline_cov = baseline_comp.get("coverage_percent", 0.0)
                current_cov = current_comp.coverage_percent

                delta = current_cov - baseline_cov
                delta_percent = (delta / baseline_cov * 100) if baseline_cov > 0 else 0.0

                regression = delta < -1.0  # More than 1% decrease
                improvement = delta > 1.0  # More than 1% increase

                comp_delta = CoverageDelta(
                    component_name=comp_name,
                    component_type=current_comp.component_type,
                    current_coverage=current_cov,
                    baseline_coverage=baseline_cov,
                    delta=delta,
                    delta_percent=delta_percent,
                    regression=regression,
                    improvement=improvement,
                    files_added=max(
                        0, current_comp.files_analyzed - baseline_comp.get("files_analyzed", 0)
                    ),
                    files_removed=max(
                        0, baseline_comp.get("files_analyzed", 0) - current_comp.files_analyzed
                    ),
                )

                component_deltas[comp_name] = comp_delta

                if regression:
                    regressions.append(comp_delta)
                elif improvement:
                    improvements.append(comp_delta)

            else:
                # New component
                logger.info(f"   🆕 New component: {comp_name}")
                comp_delta = CoverageDelta(
                    component_name=comp_name,
                    component_type=current_comp.component_type,
                    current_coverage=current_comp.coverage_percent,
                    baseline_coverage=0.0,
                    delta=current_comp.coverage_percent,
                    delta_percent=100.0,
                    regression=False,
                    improvement=True,
                    files_added=current_comp.files_analyzed,
                )
                component_deltas[comp_name] = comp_delta
                improvements.append(comp_delta)

        # Identify critical regressions (>5% decrease)
        critical_regressions = [d for d in regressions if d.delta < -5.0]

        differential_report = DifferentialReport(
            timestamp=current_report.timestamp,
            baseline_timestamp=baseline.get("timestamp", "unknown"),
            overall_delta=overall_delta,
            overall_delta_percent=overall_delta_percent,
            component_deltas=component_deltas,
            regressions=regressions,
            improvements=improvements,
            critical_regressions=critical_regressions,
        )

        logger.info("✅ Differential analysis completed:")
        logger.info(f"   Overall delta: {overall_delta:+.1f}% ({overall_delta_percent:+.1f}%)")
        logger.info(f"   Regressions: {len(regressions)}")
        logger.info(f"   Improvements: {len(improvements)}")
        logger.info(f"   Critical regressions: {len(critical_regressions)}")

        return differential_report

    def get_baseline_from_git(self, commit_hash: str = "HEAD") -> dict[str, Any] | None:
        """Load baseline from git commit"""
        import subprocess

        try:
            baseline_file = self.baseline_dir / f"git_{commit_hash}.json"

            # Try to get baseline from git
            result = subprocess.run(
                ["git", "show", f"{commit_hash}:coverage_baselines/latest.json"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10.0,
            )

            if result.returncode == 0:
                baseline_data = json.loads(result.stdout)
                # Save locally for future use
                with open(baseline_file, "w") as f:
                    json.dump(baseline_data, f, indent=2)
                return baseline_data
            else:
                logger.warning(f"⚠️ Could not load baseline from git commit {commit_hash}")
                return None

        except Exception as e:
            logger.error(f"❌ Error loading baseline from git: {e}")
            return None
