#!/usr/bin/env python3
"""
Calculate Full Test Coverage - All 3 Types
Calcola coverage per unit, integration e api tests separatamente e genera report combinato
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict


class FullCoverageCalculator:
    """Calcola coverage per tutti i tipi di test"""

    def __init__(self, backend_path: str = "apps/backend-rag"):
        self.backend_path = Path(backend_path).resolve()
        self.backend_code = self.backend_path / "backend"
        self.tests_path = self.backend_path / "tests"

        # Output directories
        self.coverage_dir = self.backend_path / ".coverage_data"
        self.coverage_dir.mkdir(exist_ok=True)

        # Results storage
        self.results = {"unit": {}, "integration": {}, "api": {}, "combined": {}}

    def _create_default_coveragerc(self):
        """Crea file .coveragerc di default se non esiste"""
        coveragerc_path = self.backend_path / ".coveragerc"
        if coveragerc_path.exists():
            return

        default_config = """[run]
source = backend
omit = 
    */tests/*
    */migrations/*
    */__pycache__/*
    */venv/*
    */.venv/*
    */site-packages/*
    */test_*.py
    */_test.py
    */conftest.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
    @abc.abstractmethod
    class .*\bProtocol\):
    @(abc\.)?abstractmethod

precision = 2
show_missing = True
skip_covered = False

[html]
directory = htmlcov
"""
        with open(coveragerc_path, "w") as f:
            f.write(default_config)

    def run_coverage_for_type(self, test_type: str) -> bool:
        """Esegue pytest con coverage per un tipo specifico di test"""
        print(f"\n{'='*80}")
        print(f"🧪 Running {test_type.upper()} tests with coverage...")
        print(f"{'='*80}")

        test_dir = self.tests_path / test_type
        if not test_dir.exists():
            print(f"⚠️  Test directory not found: {test_dir}")
            return False

        coverage_file = self.coverage_dir / f".coverage.{test_type}"
        coverage_json = self.coverage_dir / f"coverage_{test_type}.json"
        coverage_html = self.coverage_dir / f"htmlcov_{test_type}"

        # Ensure .coveragerc exists
        coveragerc_path = self.backend_path / ".coveragerc"
        if not coveragerc_path.exists():
            self._create_default_coveragerc()

        # Use relative path from backend_path (pytest runs from there)
        test_dir_rel = test_dir.relative_to(self.backend_path)
        backend_code_rel = self.backend_code.relative_to(self.backend_path)
        coverage_json_rel = coverage_json.relative_to(self.backend_path)
        coverage_html_rel = coverage_html.relative_to(self.backend_path)

        # Set coverage data file
        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(coverage_file)

        # Use coverage run instead of pytest --cov for better error handling
        # Limit verbosity and use parallel execution for faster results
        coverage_cmd = [
            "coverage",
            "run",
            "--source",
            str(backend_code_rel),
            "--rcfile",
            ".coveragerc",
            "-m",
            "pytest",
            str(test_dir_rel),
            "-v",
            "--tb=line",  # Shorter traceback
            "--continue-on-collection-errors",  # Continue even if some tests fail to import
            "-x",  # Stop on first failure (remove if you want full run)
        ]

        result = subprocess.run(
            coverage_cmd, cwd=self.backend_path, capture_output=True, text=True, env=env
        )

        # Print output (even if tests fail, coverage might still be collected)
        if result.stdout:
            print(result.stdout)
        if result.stderr and "INTERNALERROR" not in result.stderr:
            print(result.stderr)

        # Generate reports even if some tests failed
        report_cmd = [
            "coverage",
            "json",
            "-o",
            str(coverage_json_rel),
        ]

        report_result = subprocess.run(
            report_cmd, cwd=self.backend_path, capture_output=True, text=True, env=env
        )

        if report_result.returncode != 0:
            print(f"⚠️  Failed to generate JSON report: {report_result.stderr}")

        # Generate HTML report
        html_cmd = [
            "coverage",
            "html",
            "-d",
            str(coverage_html_rel),
        ]

        html_result = subprocess.run(
            html_cmd, cwd=self.backend_path, capture_output=True, text=True, env=env
        )

        # Check if coverage JSON was generated
        if coverage_json.exists():
            return True
        else:
            print(f"⚠️  No coverage data generated for {test_type}")
            return False

    def analyze_coverage(self, test_type: str) -> Dict:
        """Analizza coverage report JSON per un tipo di test"""
        coverage_json = self.coverage_dir / f"coverage_{test_type}.json"

        if not coverage_json.exists():
            print(f"⚠️  Coverage report not found: {coverage_json}")
            return {}

        with open(coverage_json, "r") as f:
            data = json.load(f)

        return data

    def calculate_file_coverage(self, coverage_data: Dict) -> Dict[str, float]:
        """Calcola coverage per file"""
        file_coverage = {}
        files = coverage_data.get("files", {})

        for file_path, file_data in files.items():
            # Skip test files
            if "test_" in file_path or "/tests/" in file_path:
                continue

            summary = file_data.get("summary", {})
            percent_covered = summary.get("percent_covered", 0)

            # Normalize path
            normalized_path = file_path.replace(str(self.backend_path) + "/", "")
            file_coverage[normalized_path] = percent_covered

        return file_coverage

    def combine_coverage(self) -> Dict:
        """Combina coverage da tutti i tipi di test usando coverage combine"""
        import os

        print("\n" + "=" * 80)
        print("🔄 Combining coverage from all test types...")
        print("=" * 80)

        # Use coverage combine to merge all .coverage files
        coverage_files = [
            self.coverage_dir / f".coverage.{test_type}"
            for test_type in ["unit", "integration", "api"]
        ]

        # Filter existing files
        existing_files = [f for f in coverage_files if f.exists()]

        if not existing_files:
            print("⚠️  No coverage files to combine")
            return {}

        # Combine using coverage combine
        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(self.coverage_dir / ".coverage.combined")

        # Copy all coverage files to current dir for combine
        import shutil

        for i, cov_file in enumerate(existing_files):
            shutil.copy(cov_file, self.coverage_dir / f".coverage.{i}")

        # Run coverage combine
        result = subprocess.run(
            [
                "coverage",
                "combine",
                "--keep",
                str(self.coverage_dir),
            ],
            cwd=self.backend_path,
            capture_output=True,
            text=True,
            env=env,
        )

        if result.returncode != 0:
            print(f"⚠️  Coverage combine failed: {result.stderr}")
            # Fallback: manual combination
            return self._manual_combine_coverage()

        # Generate combined JSON report
        combined_json = self.coverage_dir / "coverage_combined.json"
        env["COVERAGE_FILE"] = str(self.coverage_dir / ".coverage.combined")

        result = subprocess.run(
            [
                "coverage",
                "json",
                "-o",
                str(combined_json),
            ],
            cwd=self.backend_path,
            capture_output=True,
            text=True,
            env=env,
        )

        if result.returncode != 0:
            print(f"⚠️  Failed to generate combined JSON: {result.stderr}")
            return self._manual_combine_coverage()

        # Load combined data
        if combined_json.exists():
            with open(combined_json, "r") as f:
                return json.load(f)

        return self._manual_combine_coverage()

    def _manual_combine_coverage(self) -> Dict:
        """Fallback: manual combination of coverage data"""
        print("📊 Using manual combination method...")

        # Collect all covered files from all test types
        all_executed = {}  # file_path -> set of executed lines
        all_missing = {}  # file_path -> set of missing lines
        all_statements = {}  # file_path -> total statements

        for test_type in ["unit", "integration", "api"]:
            coverage_data = self.results[test_type]
            if not coverage_data:
                continue

            files = coverage_data.get("files", {})
            for file_path, file_data in files.items():
                if "test_" in file_path or "/tests/" in file_path:
                    continue

                if file_path not in all_executed:
                    all_executed[file_path] = set()
                    all_missing[file_path] = set()

                # Merge executed and missing lines
                executed = file_data.get("executed_lines", [])
                missing = file_data.get("missing_lines", [])

                all_executed[file_path].update(executed)
                all_missing[file_path].update(missing)

                # Track total statements
                summary = file_data.get("summary", {})
                num_statements = summary.get("num_statements", 0)
                if file_path not in all_statements:
                    all_statements[file_path] = num_statements
                else:
                    # Use max to get true statement count
                    all_statements[file_path] = max(
                        all_statements[file_path], num_statements
                    )

        # Calculate combined coverage
        combined_files = {}
        total_statements = 0
        total_covered = 0
        total_missing = 0

        for file_path in all_executed.keys():
            executed = all_executed[file_path]
            missing = all_missing[file_path]

            # Remove lines that are executed from missing
            missing = missing - executed

            num_statements = len(executed) + len(missing)
            covered_lines = len(executed)
            missing_lines = len(missing)

            if num_statements > 0:
                percent_covered = (covered_lines / num_statements) * 100
            else:
                percent_covered = 100.0

            combined_files[file_path] = {
                "executed_lines": sorted(list(executed)),
                "missing_lines": sorted(list(missing)),
                "excluded_lines": [],
                "summary": {
                    "num_statements": num_statements,
                    "excluded_lines": 0,
                    "missing_lines": missing_lines,
                    "covered_lines": covered_lines,
                    "num_branches": 0,
                    "num_partial_branches": 0,
                    "covered_branches": 0,
                    "missing_branches": 0,
                    "percent_covered": percent_covered,
                    "percent_covered_display": f"{percent_covered:.2f}",
                },
            }

            total_statements += num_statements
            total_covered += covered_lines
            total_missing += missing_lines

        # Calculate overall percentage
        if total_statements > 0:
            overall_percent = (total_covered / total_statements) * 100
        else:
            overall_percent = 0.0

        return {
            "files": combined_files,
            "totals": {
                "num_statements": total_statements,
                "excluded_lines": 0,
                "missing_lines": total_missing,
                "covered_lines": total_covered,
                "num_branches": 0,
                "num_partial_branches": 0,
                "covered_branches": 0,
                "missing_branches": 0,
                "percent_covered": overall_percent,
                "percent_covered_display": f"{overall_percent:.2f}",
            },
        }

    def generate_report(self) -> str:
        """Genera report completo"""
        lines = [
            "",
            "=" * 80,
            "📊 FULL TEST COVERAGE REPORT - ALL 3 TYPES",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Individual reports
        for test_type in ["unit", "integration", "api"]:
            data = self.results[test_type]
            if not data:
                lines.append(f"\n❌ {test_type.upper()}: No coverage data")
                continue

            totals = data.get("totals", {})
            percent = totals.get("percent_covered", 0)
            statements = totals.get("num_statements", 0)
            covered = totals.get("covered_lines", 0)
            missing = totals.get("missing_lines", 0)

            lines.extend(
                [
                    f"\n{'─'*80}",
                    f"📋 {test_type.upper()} TESTS COVERAGE",
                    f"{'─'*80}",
                    f"  Coverage: {percent:.2f}%",
                    f"  Statements: {statements:,}",
                    f"  Covered: {covered:,}",
                    f"  Missing: {missing:,}",
                ]
            )

        # Combined report
        combined = self.results["combined"]
        if combined:
            totals = combined.get("totals", {})
            percent = totals.get("percent_covered", 0)
            statements = totals.get("num_statements", 0)
            covered = totals.get("covered_lines", 0)
            missing = totals.get("missing_lines", 0)

            lines.extend(
                [
                    f"\n{'═'*80}",
                    "🎯 COMBINED COVERAGE (ALL TEST TYPES)",
                    f"{'═'*80}",
                    f"  Overall Coverage: {percent:.2f}%",
                    f"  Total Statements: {statements:,}",
                    f"  Covered Lines: {covered:,}",
                    f"  Missing Lines: {missing:,}",
                ]
            )

        # Top files by coverage
        if combined:
            files = combined.get("files", {})
            sorted_files = sorted(
                files.items(), key=lambda x: x[1]["summary"]["percent_covered"]
            )

            lines.extend(
                [
                    "",
                    f"{'─'*80}",
                    "📈 TOP 20 FILES BY COVERAGE",
                    f"{'─'*80}",
                ]
            )

            for file_path, file_data in sorted_files[:20]:
                percent = file_data["summary"]["percent_covered"]
                short_path = file_path.replace("apps/backend-rag/backend/", "")
                lines.append(f"  {percent:6.2f}% | {short_path}")

        # Bottom files (lowest coverage)
        if combined:
            lines.extend(
                [
                    "",
                    f"{'─'*80}",
                    "📉 BOTTOM 20 FILES BY COVERAGE (NEEDS ATTENTION)",
                    f"{'─'*80}",
                ]
            )

            sorted_files = sorted(
                files.items(), key=lambda x: x[1]["summary"]["percent_covered"]
            )

            for file_path, file_data in sorted_files[-20:]:
                percent = file_data["summary"]["percent_covered"]
                short_path = file_path.replace("apps/backend-rag/backend/", "")
                missing = file_data["summary"]["missing_lines"]
                lines.append(f"  {percent:6.2f}% | {missing:4d} missing | {short_path}")

        lines.extend(
            [
                "",
                "=" * 80,
                "💡 HTML REPORTS GENERATED:",
                f"  Unit: {self.coverage_dir}/htmlcov_unit/index.html",
                f"  Integration: {self.coverage_dir}/htmlcov_integration/index.html",
                f"  API: {self.coverage_dir}/htmlcov_api/index.html",
                "=" * 80,
            ]
        )

        return "\n".join(lines)

    def calculate(self) -> int:
        """Esegue calcolo completo del coverage"""
        print("🚀 Starting Full Coverage Calculation")
        print(f"Backend path: {self.backend_path.absolute()}")
        print(f"Tests path: {self.tests_path.absolute()}")

        # Run coverage for each test type
        success_count = 0
        for test_type in ["unit", "integration", "api"]:
            if self.run_coverage_for_type(test_type):
                success_count += 1
                # Analyze coverage
                coverage_data = self.analyze_coverage(test_type)
                if coverage_data:
                    self.results[test_type] = coverage_data
            else:
                print(f"⚠️  {test_type} tests failed or had no coverage data")

        if success_count == 0:
            print("❌ No test types succeeded")
            return 1

        # Combine coverage
        self.results["combined"] = self.combine_coverage()

        # Save combined JSON
        combined_json = self.coverage_dir / "coverage_combined.json"
        with open(combined_json, "w") as f:
            json.dump(self.results["combined"], f, indent=2)
        print(f"\n💾 Combined coverage saved to: {combined_json}")

        # Generate report
        report = self.generate_report()
        print(report)

        # Save report
        report_file = self.backend_path / "COVERAGE_FULL_REPORT.md"
        with open(report_file, "w") as f:
            f.write(report)
        print(f"\n📝 Full report saved to: {report_file}")

        return 0


def main():
    backend_path = sys.argv[1] if len(sys.argv) > 1 else "apps/backend-rag"

    calculator = FullCoverageCalculator(backend_path=backend_path)
    exit_code = calculator.calculate()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
