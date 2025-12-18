#!/usr/bin/env python3
"""
Coverage Monitor - Monitors test coverage and identifies gaps

Features:
- Runs pytest with coverage
- Generates coverage.json with detailed data
- Identifies files below target coverage
- Generates prioritized gap report
- Outputs actionable recommendations
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class CoverageMonitor:
    """Monitora test coverage e identifica gap"""

    def __init__(self, target_coverage: float = 90.0):
        self.target_coverage = target_coverage
        self.test_dir = Path("apps/backend-rag/tests/unit")
        self.source_dir = Path("apps/backend-rag/backend")
        self.coverage_json = Path("apps/backend-rag/coverage.json")
        self.report_file = Path("coverage_report.txt")

    def run_coverage(self) -> bool:
        """Esegue pytest con coverage"""
        print("Running pytest with coverage...")

        cmd = [
            "pytest",
            str(self.test_dir),
            f"--cov={self.source_dir}",
            f"--cov-report=json:{self.coverage_json}",
            "--cov-report=term",
            "-v",
            "--tb=no",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0 and "FAILED" in result.stdout:
            print("⚠️  Some tests failed, but continuing coverage analysis...")

        return self.coverage_json.exists()

    def load_coverage_data(self) -> dict[str, Any]:
        """Carica coverage.json"""
        if not self.coverage_json.exists():
            raise FileNotFoundError(f"Coverage file not found: {self.coverage_json}")

        with open(self.coverage_json) as f:
            return json.load(f)

    def identify_gaps(self, coverage_data: dict) -> list[tuple[str, float, list[int]]]:
        """Identifica file con coverage sotto target"""
        gaps = []
        files = coverage_data.get("files", {})

        for file_path, file_data in files.items():
            # Skip test files
            if "test_" in file_path or "/tests/" in file_path:
                continue

            summary = file_data.get("summary", {})
            percent_covered = summary.get("percent_covered", 0)

            if percent_covered < self.target_coverage:
                missing_lines = file_data.get("missing_lines", [])
                gaps.append((file_path, percent_covered, missing_lines))

        # Sort by coverage (lowest first)
        gaps.sort(key=lambda x: x[1])

        return gaps

    def generate_report(self, coverage_data: dict, gaps: list[tuple[str, float, list[int]]]) -> str:
        """Genera report dettagliato"""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("📊 COVERAGE MONITOR REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Summary
        totals = coverage_data.get("totals", {})
        total_coverage = totals.get("percent_covered", 0)
        gap = self.target_coverage - total_coverage

        lines.append(f"Total Coverage: {total_coverage:.2f}%")
        lines.append(f"Target: {self.target_coverage}%")
        lines.append(f"Gap: {gap:.2f}%")
        lines.append("")

        if total_coverage >= self.target_coverage:
            lines.append("✅ COVERAGE TARGET MET!")
        else:
            lines.append(f"⚠️  BELOW TARGET by {gap:.2f}%")

        lines.append("")

        # Coverage Gaps
        if gaps:
            lines.append(f"📉 Coverage Gaps ({len(gaps)} files below {self.target_coverage}%):")
            lines.append("-" * 80)

            for file_path, coverage, missing_lines in gaps:
                # Shorten file path
                short_path = file_path.replace("apps/backend-rag/backend/", "")
                missing_count = len(missing_lines)

                lines.append(f" {coverage:5.1f}% | {missing_count:4d} missing | {short_path}")

            lines.append("")

        # Recommendations
        lines.append("=" * 80)
        lines.append("💡 RECOMMENDATIONS:")
        lines.append("")
        lines.append("1. Focus on lowest coverage files first")
        lines.append("2. Use test_generator.py to create test skeletons")
        lines.append("3. Run: python scripts/test_automation/test_generator.py")
        lines.append("4. Check missing lines in coverage.json for specifics")
        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def save_report(self, report: str) -> None:
        """Salva report su file"""
        with open(self.report_file, "w") as f:
            f.write(report)
        print(f"✅ Report saved to: {self.report_file}")

    def run(self) -> int:
        """Esegue monitoring completo"""
        # Run coverage
        if not self.run_coverage():
            print("❌ Failed to generate coverage data")
            return 1

        # Load coverage data
        try:
            coverage_data = self.load_coverage_data()
        except FileNotFoundError as e:
            print(f"❌ {e}")
            return 1

        # Identify gaps
        gaps = self.identify_gaps(coverage_data)

        # Generate report
        report = self.generate_report(coverage_data, gaps)

        # Print to console
        print()
        print(report)

        # Save to file
        self.save_report(report)

        # Exit code based on target
        total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
        return 0 if total_coverage >= self.target_coverage else 1


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor test coverage")
    parser.add_argument(
        "target",
        type=float,
        nargs="?",
        default=90.0,
        help="Target coverage percentage (default: 90)",
    )

    args = parser.parse_args()

    monitor = CoverageMonitor(target_coverage=args.target)
    exit_code = monitor.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
