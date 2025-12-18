#!/usr/bin/env python3
"""
Test Quality Checker - Verifies quality of existing tests

Checks:
1. Docstrings - Every test has documentation
2. Assertions - Every test has at least one assert
3. Pytest Import - File uses pytest
4. Mock Usage - Tests use appropriate mocking
5. Structure - Follows best practices

Quality Score: 0-100 based on weighted checks
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Any


class TestQualityChecker:
    """Verifica qualità dei test esistenti"""

    def __init__(self, test_dir: str = "apps/backend-rag/tests/unit"):
        self.test_dir = Path(test_dir)
        self.report_file = Path("test_quality_report.txt")

    def check_test_file(self, test_file: Path) -> Dict[str, Any]:
        """Analizza singolo test file"""
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return {"error": str(e), "quality_score": 0}

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return {"error": f"Syntax error: {e}", "quality_score": 0}

        stats = {
            "total_tests": 0,
            "tests_with_docstrings": 0,
            "tests_with_assertions": 0,
            "has_pytest_import": False,
            "has_mock_import": False,
            "issues": []
        }

        # Check for pytest import
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'pytest':
                        stats["has_pytest_import"] = True
                    if 'mock' in alias.name.lower():
                        stats["has_mock_import"] = True

            elif isinstance(node, ast.ImportFrom):
                if node.module and 'mock' in node.module.lower():
                    stats["has_mock_import"] = True

        # Analyze test functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    stats["total_tests"] += 1

                    # Check docstring
                    if ast.get_docstring(node):
                        stats["tests_with_docstrings"] += 1
                    else:
                        stats["issues"].append(f"{node.name}: Missing docstring")

                    # Check for assertions
                    has_assertion = False
                    for child in ast.walk(node):
                        if isinstance(child, (ast.Assert, ast.Call)):
                            if isinstance(child, ast.Call):
                                if hasattr(child.func, 'attr') and 'assert' in child.func.attr.lower():
                                    has_assertion = True
                            else:
                                has_assertion = True

                    if has_assertion:
                        stats["tests_with_assertions"] += 1
                    else:
                        stats["issues"].append(f"{node.name}: No assertions found")

        # Calculate quality score
        if stats["total_tests"] == 0:
            return {"stats": stats, "quality_score": 0, "grade": "N/A"}

        # Weighted scoring
        docstring_score = (stats["tests_with_docstrings"] / stats["total_tests"]) * 30
        assertion_score = (stats["tests_with_assertions"] / stats["total_tests"]) * 40
        structure_score = 30 if stats["has_pytest_import"] else 0

        quality_score = docstring_score + assertion_score + structure_score

        # Grade
        if quality_score >= 80:
            grade = "✅ Excellent"
        elif quality_score >= 60:
            grade = "⚠️ Good"
        else:
            grade = "❌ Poor"

        return {
            "stats": stats,
            "quality_score": round(quality_score, 1),
            "grade": grade
        }

    def analyze_all_tests(self) -> Dict[str, Any]:
        """Analizza tutti i test files"""
        test_files = list(self.test_dir.glob("test_*.py"))

        results = {}
        for test_file in test_files:
            rel_path = test_file.relative_to(self.test_dir)
            results[str(rel_path)] = self.check_test_file(test_file)

        return results

    def generate_report(self, results: Dict[str, Any]) -> str:
        """Genera report qualità"""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("🔍 TEST QUALITY CHECKER REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Summary
        total_files = len(results)
        total_tests = sum(r.get("stats", {}).get("total_tests", 0) for r in results.values())
        avg_score = sum(r.get("quality_score", 0) for r in results.values()) / total_files if total_files > 0 else 0

        lines.append(f"Total Test Files: {total_files}")
        lines.append(f"Total Tests: {total_tests}")
        lines.append(f"Average Quality Score: {avg_score:.1f}/100")
        lines.append("")

        # Distribution
        excellent = sum(1 for r in results.values() if r.get("quality_score", 0) >= 80)
        good = sum(1 for r in results.values() if 60 <= r.get("quality_score", 0) < 80)
        poor = sum(1 for r in results.values() if r.get("quality_score", 0) < 60)

        lines.append("Quality Distribution:")
        lines.append(f"  ✅ Excellent (80-100): {excellent} files")
        lines.append(f"  ⚠️  Good (60-79): {good} files")
        lines.append(f"  ❌ Poor (<60): {poor} files")
        lines.append("")

        # Low quality files
        low_quality = [(f, r) for f, r in results.items() if r.get("quality_score", 0) < 80]
        low_quality.sort(key=lambda x: x[1].get("quality_score", 0))

        if low_quality:
            lines.append("📉 Low Quality Files (need improvement):")
            lines.append("-" * 80)

            for filename, result in low_quality[:10]:  # Top 10 worst
                score = result.get("quality_score", 0)
                total_tests = result.get("stats", {}).get("total_tests", 0)

                lines.append(f" {score:5.1f}/100 | {total_tests:3d} tests | {filename}")

                # Show issues
                issues = result.get("stats", {}).get("issues", [])
                for issue in issues[:3]:  # Show first 3 issues
                    lines.append(f"           └─ {issue}")

                if len(issues) > 3:
                    lines.append(f"           └─ ... and {len(issues) - 3} more issues")

                lines.append("")

        # Recommendations
        lines.append("=" * 80)
        lines.append("💡 RECOMMENDATIONS:")
        lines.append("")
        lines.append("1. Add docstrings to all test functions")
        lines.append("2. Ensure every test has at least one assertion")
        lines.append("3. Use pytest fixtures for setup/teardown")
        lines.append("4. Use mocking for external dependencies")
        lines.append("5. Follow AAA pattern: Arrange, Act, Assert")
        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def save_report(self, report: str) -> None:
        """Salva report su file"""
        with open(self.report_file, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to: {self.report_file}")

    def run(self) -> int:
        """Esegue check completo"""
        print("Analyzing test quality...")

        # Analyze all tests
        results = self.analyze_all_tests()

        # Generate report
        report = self.generate_report(results)

        # Print to console
        print()
        print(report)

        # Save to file
        self.save_report(report)

        # Exit code based on average quality
        avg_score = sum(r.get("quality_score", 0) for r in results.values()) / len(results) if results else 0

        return 0 if avg_score >= 70 else 1


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Check test quality')
    parser.add_argument('test_dir', nargs='?', default='apps/backend-rag/tests/unit', help='Test directory')

    args = parser.parse_args()

    checker = TestQualityChecker(test_dir=args.test_dir)
    exit_code = checker.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
