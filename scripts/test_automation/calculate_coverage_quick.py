#!/usr/bin/env python3
"""
Quick Coverage Calculator - Estimates coverage without running all tests
Usa un campione rappresentativo di test per calcolare coverage velocemente
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict


def run_quick_coverage(backend_path: str = "apps/backend-rag") -> Dict:
    """Calcola coverage velocemente usando un campione di test"""
    backend_path = Path(backend_path).resolve()
    backend_code = backend_path / "backend"
    tests_path = backend_path / "tests"

    print("🚀 Quick Coverage Calculation")
    print(f"Backend: {backend_path}")

    results = {}

    for test_type in ["unit", "integration", "api"]:
        test_dir = tests_path / test_type
        if not test_dir.exists():
            continue

        print(f"\n📊 Analyzing {test_type} tests...")

        # Count test files
        test_files = list(test_dir.rglob("test_*.py"))
        print(f"  Found {len(test_files)} test files")

        # Run a sample (first 10 files) for quick estimate
        sample_files = test_files[:10] if len(test_files) > 10 else test_files

        coverage_file = backend_path / f".coverage.{test_type}"
        coverage_json = backend_path / f"coverage_{test_type}.json"

        env = {"COVERAGE_FILE": str(coverage_file), **dict(os.environ)}

        # Run coverage on sample
        if sample_files:
            test_paths = [str(f.relative_to(backend_path)) for f in sample_files]

            cmd = [
                "coverage",
                "run",
                "--source",
                str(backend_code.relative_to(backend_path)),
                "--rcfile",
                ".coveragerc",
                "-m",
                "pytest",
                *test_paths,
                "-v",
                "--tb=no",
            ]

            result = subprocess.run(
                cmd, cwd=backend_path, capture_output=True, text=True, env=env
            )

            # Generate report
            if coverage_file.exists():
                subprocess.run(
                    [
                        "coverage",
                        "json",
                        "-o",
                        str(coverage_json.relative_to(backend_path)),
                    ],
                    cwd=backend_path,
                    env=env,
                )

                if coverage_json.exists():
                    with open(coverage_json) as f:
                        data = json.load(f)
                        totals = data.get("totals", {})
                        percent = totals.get("percent_covered", 0)
                        print(f"  Sample coverage: {percent:.2f}%")
                        results[test_type] = data

    # Generate summary
    print("\n" + "=" * 80)
    print("📊 QUICK COVERAGE SUMMARY")
    print("=" * 80)

    for test_type, data in results.items():
        totals = data.get("totals", {})
        percent = totals.get("percent_covered", 0)
        statements = totals.get("num_statements", 0)
        covered = totals.get("covered_lines", 0)

        print(f"\n{test_type.upper()}:")
        print(f"  Coverage: {percent:.2f}%")
        print(f"  Statements: {statements:,}")
        print(f"  Covered: {covered:,}")

    return results


if __name__ == "__main__":
    import os

    backend_path = sys.argv[1] if len(sys.argv) > 1 else "apps/backend-rag"
    run_quick_coverage(backend_path)
