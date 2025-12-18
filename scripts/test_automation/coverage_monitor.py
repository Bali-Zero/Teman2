#!/usr/bin/env python3
"""
Coverage Monitor - Continuous Coverage Tracking
Monitora coverage e identifica gap automaticamente
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class CoverageMonitor:
    """Monitora test coverage e identifica gap"""

    def __init__(self, target_coverage: float = 90.0):
        self.target_coverage = target_coverage
        self.coverage_file = Path("apps/backend-rag/.coverage")
        self.coverage_json = Path("apps/backend-rag/coverage.json")

    def run_coverage(self) -> bool:
        """Esegue pytest con coverage"""
        print("🔍 Running tests with coverage...")

        result = subprocess.run(
            [
                "pytest",
                "apps/backend-rag/tests/unit",
                "--cov=apps/backend-rag/backend",
                "--cov-config=apps/backend-rag/.coveragerc",
                "--cov-report=json:apps/backend-rag/coverage.json",
                "--cov-report=term",
                "-v",
            ],
            capture_output=True,
            text=True,
        )

        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            return False

        return True

    def analyze_coverage(self) -> Dict:
        """Analizza coverage report JSON"""
        if not self.coverage_json.exists():
            print(f"❌ Coverage report not found: {self.coverage_json}")
            return {}

        with open(self.coverage_json, "r") as f:
            data = json.load(f)

        return data

    def identify_gaps(self, coverage_data: Dict) -> List[Tuple[str, float, List[int]]]:
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

    def generate_report(self, coverage_data: Dict, gaps: List[Tuple]) -> str:
        """Genera report coverage"""
        total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)

        lines = [
            "",
            "=" * 80,
            "📊 COVERAGE MONITOR REPORT",
            "=" * 80,
            "",
            f"Total Coverage: {total_coverage:.2f}%",
            f"Target: {self.target_coverage}%",
            f"Gap: {max(0, self.target_coverage - total_coverage):.2f}%",
            "",
        ]

        if total_coverage >= self.target_coverage:
            lines.append(f"✅ TARGET REACHED! Coverage is {total_coverage:.2f}%")
        else:
            lines.append(
                f"⚠️  BELOW TARGET by {self.target_coverage - total_coverage:.2f}%"
            )

        lines.extend(
            [
                "",
                f"📉 Coverage Gaps ({len(gaps)} files below {self.target_coverage}%):",
                "-" * 80,
            ]
        )

        for file_path, percent, missing_lines in gaps[:20]:  # Top 20 gaps
            # Shorten path
            short_path = file_path.replace("apps/backend-rag/backend/", "")
            missing_count = len(missing_lines)

            lines.append(f"{percent:5.1f}% | {missing_count:4d} missing | {short_path}")

        if len(gaps) > 20:
            lines.append(f"... and {len(gaps) - 20} more files")

        lines.extend(
            [
                "",
                "=" * 80,
                "💡 RECOMMENDATIONS:",
                "",
                "1. Focus on lowest coverage files first",
                "2. Use test_generator.py to create test skeletons",
                "3. Run: python scripts/test_automation/test_generator.py",
                "4. Check missing lines in coverage.json for specifics",
                "",
                "=" * 80,
            ]
        )

        return "\n".join(lines)

    def monitor(self) -> int:
        """Esegue monitoring completo"""
        # Run coverage
        if not self.run_coverage():
            print("❌ Coverage run failed")
            return 1

        # Analyze
        coverage_data = self.analyze_coverage()
        if not coverage_data:
            print("❌ No coverage data available")
            return 1

        # Identify gaps
        gaps = self.identify_gaps(coverage_data)

        # Generate report
        report = self.generate_report(coverage_data, gaps)
        print(report)

        # Write report to file
        report_file = Path("coverage_report.txt")
        with open(report_file, "w") as f:
            f.write(report)
        print(f"\n📝 Report saved to: {report_file}")

        # Exit code based on target
        total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
        if total_coverage >= self.target_coverage:
            return 0
        else:
            return 1


def main():
    target = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0

    monitor = CoverageMonitor(target_coverage=target)
    exit_code = monitor.monitor()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
