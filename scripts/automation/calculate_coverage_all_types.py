#!/usr/bin/env python3
"""
Calculate test coverage for all 3 test types:
1. Unit tests
2. Integration tests
3. API tests (E2E)
"""

import json
import subprocess
import sys
from pathlib import Path


def run_coverage(test_type: str, test_path: str, marker: str, output_file: str) -> dict:
    """Run pytest with coverage for a specific test type"""
    print(f"\n{'=' * 60}")
    print(f"Running {test_type} tests with coverage...")
    print(f"{'=' * 60}\n")

    cmd = [
        "python",
        "-m",
        "pytest",
        test_path,
        "-m",
        marker,
        "--cov=backend",
        "--cov-report=term-missing",
        "--cov-report=json:" + output_file,
        "-q",
        "--tb=short",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes max
        )

        # Parse coverage from JSON
        coverage_data = {}
        if Path(output_file).exists():
            with open(output_file) as f:
                coverage_data = json.load(f)

        return {
            "success": result.returncode == 0,
            "coverage_data": coverage_data,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "coverage_data": {},
            "stdout": "",
            "stderr": "Test timeout after 5 minutes",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "coverage_data": {},
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
        }


def calculate_summary(coverage_data: dict) -> dict:
    """Calculate summary statistics from coverage data"""
    if not coverage_data or "totals" not in coverage_data:
        return {
            "total_statements": 0,
            "covered_statements": 0,
            "missing_statements": 0,
            "coverage_percent": 0.0,
        }

    totals = coverage_data["totals"]
    return {
        "total_statements": totals.get("num_statements", 0),
        "covered_statements": totals.get("covered_lines", 0),
        "missing_statements": totals.get("missing_lines", 0),
        "coverage_percent": totals.get("percent_covered", 0.0),
    }


def generate_report(results: dict):
    """Generate a comprehensive coverage report"""
    print("\n" + "=" * 80)
    print("TEST COVERAGE REPORT - ALL TYPES")
    print("=" * 80 + "\n")

    report_lines = []
    report_lines.append("# Test Coverage Report - All Types\n")
    report_lines.append(
        f"Generated: {subprocess.check_output(['date']).decode().strip()}\n\n"
    )

    total_statements = 0
    total_covered = 0

    for test_type, result in results.items():
        summary = calculate_summary(result["coverage_data"])
        total_statements = max(total_statements, summary["total_statements"])
        total_covered += summary["covered_statements"]

        status = "✅ PASSED" if result["success"] else "❌ FAILED"

        print(f"{test_type.upper()} TESTS: {status}")
        print(f"  Coverage: {summary['coverage_percent']:.1f}%")
        print(
            f"  Statements: {summary['covered_statements']}/{summary['total_statements']}"
        )
        print(f"  Missing: {summary['missing_statements']}")
        print()

        report_lines.append(f"## {test_type.upper()} Tests\n")
        report_lines.append(f"- Status: {status}\n")
        report_lines.append(f"- Coverage: {summary['coverage_percent']:.1f}%\n")
        report_lines.append(
            f"- Statements: {summary['covered_statements']}/{summary['total_statements']}\n"
        )
        report_lines.append(f"- Missing: {summary['missing_statements']}\n\n")

        if not result["success"]:
            report_lines.append(f"### Errors:\n```\n{result['stderr'][:500]}\n```\n\n")

    # Overall summary
    overall_coverage = (
        (total_covered / total_statements * 100) if total_statements > 0 else 0
    )

    print("=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)
    print(f"Total Statements: {total_statements}")
    print(f"Total Covered: {total_covered}")
    print(f"Overall Coverage: {overall_coverage:.1f}%")
    print("=" * 80 + "\n")

    report_lines.append("## Overall Summary\n")
    report_lines.append(f"- Total Statements: {total_statements}\n")
    report_lines.append(f"- Total Covered: {total_covered}\n")
    report_lines.append(f"- Overall Coverage: {overall_coverage:.1f}%\n")

    # Write report to file
    report_file = Path("COVERAGE_REPORT_ALL_TYPES.md")
    report_file.write_text("".join(report_lines))
    print(f"📄 Full report written to: {report_file}")

    return overall_coverage


def main():
    """Main function"""
    base_dir = Path(__file__).parent.parent

    # Define test types
    test_types = {
        "unit": {
            "path": "tests/unit",
            "marker": "unit",
            "output": "coverage_unit.json",
        },
        "integration": {
            "path": "tests/integration",
            "marker": "integration",
            "output": "coverage_integration.json",
        },
        "api": {"path": "tests/api", "marker": "api", "output": "coverage_api.json"},
    }

    results = {}

    # Change to backend-rag directory
    os.chdir(base_dir)

    # Run coverage for each test type
    for test_type, config in test_types.items():
        result = run_coverage(
            test_type, config["path"], config["marker"], config["output"]
        )
        results[test_type] = result

    # Generate report
    overall_coverage = generate_report(results)

    # Exit with appropriate code
    all_passed = all(r["success"] for r in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    import os

    main()
