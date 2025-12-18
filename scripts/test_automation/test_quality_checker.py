#!/usr/bin/env python3
"""
Test Quality Checker - Verifica Qualità Test
Analizza test esistenti e verifica best practices
"""

import ast
from pathlib import Path
from typing import Dict, List, Tuple


class TestQualityChecker:
    """Verifica qualità dei test esistenti"""

    def __init__(self, test_dir: str):
        self.test_dir = Path(test_dir)
        self.issues = []

    def check_test_file(self, test_file: Path) -> Dict:
        """Analizza singolo test file"""
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {
                "file": str(test_file),
                "error": "Syntax error",
                "quality_score": 0,
                "issues": ["File has syntax errors"],
            }

        issues = []
        stats = {
            "total_tests": 0,
            "tests_with_docstrings": 0,
            "tests_with_assertions": 0,
            "tests_with_mocks": 0,
            "async_tests": 0,
            "fixture_usage": 0,
        }

        # Check for imports
        has_pytest = False
        has_mock = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "pytest":
                        has_pytest = True
                    if "mock" in alias.name.lower():
                        has_mock = True

            if isinstance(node, ast.ImportFrom):
                if node.module and "mock" in node.module:
                    has_mock = True

        if not has_pytest:
            issues.append("Missing pytest import")

        # Analyze test functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                stats["total_tests"] += 1

                # Check docstring
                if ast.get_docstring(node):
                    stats["tests_with_docstrings"] += 1
                else:
                    issues.append(f"{node.name}: Missing docstring")

                # Check for assertions
                has_assertion = False
                has_mock_usage = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Assert):
                        has_assertion = True
                    if isinstance(child, ast.Call):
                        if hasattr(child.func, "id") and "Mock" in str(child.func.id):
                            has_mock_usage = True

                if has_assertion:
                    stats["tests_with_assertions"] += 1
                else:
                    issues.append(f"{node.name}: No assertions found")

                if has_mock_usage:
                    stats["tests_with_mocks"] += 1

                # Check if async
                if isinstance(node, ast.AsyncFunctionDef):
                    stats["async_tests"] += 1

        # Calculate quality score
        if stats["total_tests"] == 0:
            quality_score = 0
        else:
            docstring_score = (
                stats["tests_with_docstrings"] / stats["total_tests"]
            ) * 30
            assertion_score = (
                stats["tests_with_assertions"] / stats["total_tests"]
            ) * 40
            structure_score = 30 if has_pytest else 0

            quality_score = docstring_score + assertion_score + structure_score

        return {
            "file": str(test_file.name),
            "quality_score": round(quality_score, 1),
            "stats": stats,
            "issues": issues,
            "has_pytest": has_pytest,
            "has_mock": has_mock,
        }

    def check_all_tests(self) -> List[Dict]:
        """Analizza tutti i test file"""
        results = []

        for test_file in self.test_dir.glob("test_*.py"):
            result = self.check_test_file(test_file)
            results.append(result)

        return results

    def generate_report(self, results: List[Dict]) -> str:
        """Genera report qualità test"""
        if not results:
            return "No test files found"

        total_tests = sum(r["stats"]["total_tests"] for r in results if "stats" in r)
        avg_quality = sum(r["quality_score"] for r in results) / len(results)

        # Sort by quality score (lowest first)
        results_sorted = sorted(results, key=lambda x: x["quality_score"])

        lines = [
            "",
            "=" * 80,
            "🔍 TEST QUALITY CHECKER REPORT",
            "=" * 80,
            "",
            f"Total Test Files: {len(results)}",
            f"Total Tests: {total_tests}",
            f"Average Quality Score: {avg_quality:.1f}/100",
            "",
        ]

        # Quality distribution
        excellent = sum(1 for r in results if r["quality_score"] >= 80)
        good = sum(1 for r in results if 60 <= r["quality_score"] < 80)
        poor = sum(1 for r in results if r["quality_score"] < 60)

        lines.extend(
            [
                "Quality Distribution:",
                f"  ✅ Excellent (80-100): {excellent} files",
                f"  ⚠️  Good (60-79): {good} files",
                f"  ❌ Poor (<60): {poor} files",
                "",
            ]
        )

        # Low quality files
        lines.extend(
            [
                "📉 Low Quality Files (need improvement):",
                "-" * 80,
            ]
        )

        for result in results_sorted[:10]:  # Bottom 10
            if result["quality_score"] < 70:
                lines.append(
                    f"{result['quality_score']:5.1f}/100 | "
                    f"{result['stats']['total_tests']:3d} tests | "
                    f"{result['file']}"
                )

                # Show top issues
                for issue in result["issues"][:3]:
                    lines.append(f"           └─ {issue}")

        lines.extend(
            [
                "",
                "=" * 80,
                "💡 RECOMMENDATIONS:",
                "",
                "1. Add docstrings to all test functions",
                "2. Ensure every test has at least one assertion",
                "3. Use pytest fixtures for setup/teardown",
                "4. Use mocking for external dependencies",
                "5. Follow AAA pattern: Arrange, Act, Assert",
                "",
                "=" * 80,
            ]
        )

        return "\n".join(lines)

    def check_quality(self) -> Tuple[str, int]:
        """Esegue quality check completo"""
        print(f"🔍 Checking test quality in: {self.test_dir}")
        print()

        results = self.check_all_tests()
        report = self.generate_report(results)

        print(report)

        # Calculate exit code
        avg_quality = (
            sum(r["quality_score"] for r in results) / len(results) if results else 0
        )
        exit_code = 0 if avg_quality >= 70 else 1

        return report, exit_code


def main():
    import sys

    test_dir = sys.argv[1] if len(sys.argv) > 1 else "apps/backend-rag/tests/unit"

    checker = TestQualityChecker(test_dir)
    report, exit_code = checker.check_quality()

    # Write report
    report_file = Path("test_quality_report.txt")
    with open(report_file, "w") as f:
        f.write(report)
    print(f"\n📝 Report saved to: {report_file}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
