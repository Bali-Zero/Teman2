#!/usr/bin/env python3
"""
NUZANTARA PRIME - Refactoring Assistant
Helps identify and execute common refactoring patterns.
"""

import ast
import sys
from pathlib import Path
from typing import Any

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class RefactoringAnalyzer:
    """Analyzes code for refactoring opportunities"""

    def __init__(self, target_path: Path):
        self.target_path = Path(target_path)
        if self.target_path.is_file():
            self.files = [self.target_path]
        elif self.target_path.is_dir():
            self.files = list(self.target_path.rglob("*.py"))
            self.files = [f for f in self.files if "__pycache__" not in str(f) and "test" not in str(f)]
        else:
            raise ValueError(f"Path not found: {target_path}")

    def find_duplicate_code(self) -> list[dict[str, Any]]:
        """Find duplicate function patterns"""
        duplicates = []
        function_bodies = {}

        for file_path in self.files:
            try:
                content = file_path.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Normalize function body (remove names, keep structure)
                        body_str = ast.dump(node.body)
                        if body_str in function_bodies:
                            duplicates.append({
                                "file": str(file_path),
                                "function": node.name,
                                "line": node.lineno,
                                "duplicate_of": function_bodies[body_str],
                            })
                        else:
                            function_bodies[body_str] = {
                                "file": str(file_path),
                                "function": node.name,
                                "line": node.lineno,
                            }
            except Exception as e:
                logger.warning(f"Error analyzing {file_path}: {e}")

        return duplicates

    def find_missing_type_hints(self) -> list[dict[str, Any]]:
        """Find functions without type hints"""
        missing_hints = []

        for file_path in self.files:
            try:
                content = file_path.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Check if function has return type hint
                        has_return_type = node.returns is not None
                        # Check if all parameters have type hints
                        has_param_types = all(arg.annotation is not None for arg in node.args.args)

                        if not has_return_type or not has_param_types:
                            missing_hints.append({
                                "file": str(file_path),
                                "function": node.name,
                                "line": node.lineno,
                                "missing_return": not has_return_type,
                                "missing_params": not has_param_types,
                            })
            except Exception as e:
                logger.warning(f"Error analyzing {file_path}: {e}")

        return missing_hints

    def find_inconsistent_error_handling(self) -> list[dict[str, Any]]:
        """Find functions with inconsistent error handling"""
        inconsistent = []

        for file_path in self.files:
            try:
                content = file_path.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Check if function has try/except
                        has_try_except = any(
                            isinstance(stmt, ast.Try) for stmt in node.body
                        )
                        # Check if function uses logger
                        has_logger = "logger" in content or "logging" in content

                        # Functions that do I/O should have error handling
                        is_io_function = any(
                            "async" in str(node.decorator_list) or
                            "await" in ast.dump(node) or
                            "db" in node.name.lower() or
                            "api" in node.name.lower() or
                            "http" in node.name.lower()
                        )

                        if is_io_function and not has_try_except:
                            inconsistent.append({
                                "file": str(file_path),
                                "function": node.name,
                                "line": node.lineno,
                                "issue": "Missing error handling",
                                "has_logger": has_logger,
                            })
            except Exception as e:
                logger.warning(f"Error analyzing {file_path}: {e}")

        return inconsistent

    def find_hardcoded_values(self) -> list[dict[str, Any]]:
        """Find hardcoded URLs, magic numbers, etc."""
        hardcoded = []

        for file_path in self.files:
            try:
                content = file_path.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    # Check for string literals that look like URLs
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        value = node.value
                        if value.startswith(("http://", "https://")):
                            hardcoded.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "type": "URL",
                                "value": value[:50] + "..." if len(value) > 50 else value,
                            })
                        # Check for magic numbers (long numeric strings)
                        elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                            if abs(node.value) > 1000:  # Large numbers might be magic
                                hardcoded.append({
                                    "file": str(file_path),
                                    "line": node.lineno,
                                    "type": "Magic Number",
                                    "value": str(node.value),
                                })
            except Exception as e:
                logger.warning(f"Error analyzing {file_path}: {e}")

        return hardcoded

    def find_print_statements(self) -> list[dict[str, Any]]:
        """Find print() statements that should use logger"""
        print_statements = []

        for file_path in self.files:
            try:
                content = file_path.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == "print":
                            print_statements.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "statement": ast.unparse(node)[:100],
                            })
            except Exception as e:
                logger.warning(f"Error analyzing {file_path}: {e}")

        return print_statements

    def generate_refactoring_report(self) -> str:
        """Generate comprehensive refactoring report"""
        report = []
        report.append("=" * 70)
        report.append("NUZANTARA PRIME - REFACTORING ANALYSIS REPORT")
        report.append("=" * 70)
        report.append(f"\nAnalyzing: {self.target_path}")
        report.append(f"Files analyzed: {len(self.files)}\n")

        # Duplicate code
        duplicates = self.find_duplicate_code()
        if duplicates:
            report.append(f"🔍 DUPLICATE CODE ({len(duplicates)} found):")
            for dup in duplicates[:10]:  # Limit output
                report.append(f"  - {dup['file']}:{dup['line']} - {dup['function']}")
                report.append(f"    Duplicate of: {dup['duplicate_of']['file']}:{dup['duplicate_of']['line']}")
            report.append("")

        # Missing type hints
        missing_hints = self.find_missing_type_hints()
        if missing_hints:
            report.append(f"📝 MISSING TYPE HINTS ({len(missing_hints)} found):")
            for hint in missing_hints[:20]:  # Limit output
                issues = []
                if hint['missing_return']:
                    issues.append("return type")
                if hint['missing_params']:
                    issues.append("parameter types")
                report.append(f"  - {hint['file']}:{hint['line']} - {hint['function']} (missing: {', '.join(issues)})")
            report.append("")

        # Inconsistent error handling
        inconsistent = self.find_inconsistent_error_handling()
        if inconsistent:
            report.append(f"⚠️  INCONSISTENT ERROR HANDLING ({len(inconsistent)} found):")
            for issue in inconsistent[:20]:
                report.append(f"  - {issue['file']}:{issue['line']} - {issue['function']}: {issue['issue']}")
            report.append("")

        # Hardcoded values
        hardcoded = self.find_hardcoded_values()
        if hardcoded:
            report.append(f"🔒 HARDCODED VALUES ({len(hardcoded)} found):")
            for hc in hardcoded[:20]:
                report.append(f"  - {hc['file']}:{hc['line']} - {hc['type']}: {hc['value']}")
            report.append("")

        # Print statements
        print_stmts = self.find_print_statements()
        if print_stmts:
            report.append(f"🖨️  PRINT STATEMENTS ({len(print_stmts)} found):")
            for stmt in print_stmts[:20]:
                report.append(f"  - {stmt['file']}:{stmt['line']} - {stmt['statement']}")
            report.append("")

        # Summary
        total_issues = len(duplicates) + len(missing_hints) + len(inconsistent) + len(hardcoded) + len(print_stmts)
        report.append("=" * 70)
        report.append(f"SUMMARY: {total_issues} refactoring opportunities found")
        report.append("=" * 70)

        return "\n".join(report)


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze code for refactoring opportunities")
    parser.add_argument("target", type=str, help="Target file or directory to analyze")
    parser.add_argument("--output", "-o", type=str, help="Output file for report (optional)")

    args = parser.parse_args()

    target_path = Path(args.target)
    if not target_path.exists():
        logger.error(f"❌ Target not found: {target_path}")
        sys.exit(1)

    analyzer = RefactoringAnalyzer(target_path)
    report = analyzer.generate_refactoring_report()

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report)
        print(f"✅ Report saved to: {output_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()

