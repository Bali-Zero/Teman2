#!/usr/bin/env python3
"""
NUZANTARA PRIME - Code Watchdog (24/7 Monitoring)
Continuously monitors codebase for issues and auto-fixes when possible.
Can run as a daemon or scheduled task.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("watchdog.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class CodeWatchdog:
    """24/7 code monitoring and auto-fix system"""

    def __init__(self, check_interval: int = 300):  # 5 minutes default
        self.check_interval = check_interval
        self.backend_path = backend_path
        self.issues_found = []
        self.fixes_applied = []

    async def check_type_hints(self) -> list[dict[str, Any]]:
        """Check for missing type hints"""
        issues = []
        python_files = list(self.backend_path.rglob("*.py"))
        python_files = [
            f for f in python_files
            if "test" not in str(f) and "__pycache__" not in str(f)
        ]

        for py_file in python_files[:100]:  # Limit for performance
            try:
                import ast
                content = py_file.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.returns and not node.name.startswith("_"):
                            issues.append({
                                "file": str(py_file.relative_to(self.backend_path.parent.parent)),
                                "line": node.lineno,
                                "function": node.name,
                                "issue": "Missing return type hint",
                                "fixable": True,
                            })
            except Exception as e:
                logger.debug(f"Error checking {py_file}: {e}")

        return issues

    async def check_print_statements(self) -> list[dict[str, Any]]:
        """Check for print() statements"""
        issues = []
        python_files = list(self.backend_path.rglob("*.py"))
        python_files = [
            f for f in python_files
            if "test" not in str(f) and "__pycache__" not in str(f)
        ]

        for py_file in python_files:
            try:
                content = py_file.read_text()
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if "print(" in line and "#" not in line.split("print(")[0]:
                        issues.append({
                            "file": str(py_file.relative_to(self.backend_path.parent.parent)),
                            "line": i,
                            "issue": "print() statement found, should use logger",
                            "fixable": True,
                        })
            except Exception as e:
                logger.debug(f"Error checking {py_file}: {e}")

        return issues

    async def check_hardcoded_secrets(self) -> list[dict[str, Any]]:
        """Check for hardcoded secrets"""
        issues = []
        import re

        python_files = list(self.backend_path.rglob("*.py"))
        suspicious_patterns = [
            (r'sk-[a-zA-Z0-9]{32,}', "OpenAI API key"),
            (r'AIza[0-9A-Za-z-_]{35}', "Google API key"),
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
        ]

        for py_file in python_files:
            try:
                content = py_file.read_text()
                for pattern, description in suspicious_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        issues.append({
                            "file": str(py_file.relative_to(self.backend_path.parent.parent)),
                            "issue": f"Potential {description}",
                            "fixable": False,  # Requires manual review
                            "severity": "critical",
                        })
            except Exception as e:
                logger.debug(f"Error checking {py_file}: {e}")

        return issues

    async def check_missing_tests(self) -> list[dict[str, Any]]:
        """Check for modules without tests"""
        issues = []
        modules_dir = self.backend_path / "app" / "modules"
        tests_dir = self.backend_path.parent / "tests" / "modules"

        if not modules_dir.exists():
            return issues

        modules = [d for d in modules_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
        for module in modules:
            test_module_dir = tests_dir / module.name
            if not test_module_dir.exists() or not list(test_module_dir.glob("test_*.py")):
                issues.append({
                    "file": f"modules/{module.name}/",
                    "issue": "Module missing test files",
                    "fixable": True,
                    "severity": "warning",
                })

        return issues

    async def auto_fix_print_statements(self) -> int:
        """Auto-fix print() statements"""
        fixes = 0
        python_files = list(self.backend_path.rglob("*.py"))
        python_files = [
            f for f in python_files
            if "test" not in str(f) and "__pycache__" not in str(f)
        ]

        for py_file in python_files:
            try:
                content = py_file.read_text()
                if "print(" in content and "logger" not in content:
                    # Check if logger is imported
                    if "import logging" not in content:
                        # Add import
                        lines = content.split("\n")
                        import_idx = 0
                        for i, line in enumerate(lines):
                            if line.startswith("import ") or line.startswith("from "):
                                import_idx = i + 1
                        lines.insert(import_idx, "import logging")
                        lines.insert(import_idx + 1, "logger = logging.getLogger(__name__)")
                        content = "\n".join(lines)

                    # Replace print() with logger.info()
                    import re
                    content = re.sub(
                        r'print\(([^)]+)\)',
                        r'logger.info(\1)',
                        content
                    )

                    py_file.write_text(content)
                    fixes += 1
                    logger.info(f"✅ Auto-fixed print() statements in {py_file.name}")
            except Exception as e:
                logger.debug(f"Error fixing {py_file}: {e}")

        return fixes

    async def run_checks(self) -> dict[str, Any]:
        """Run all checks"""
        logger.info("🔍 Running code quality checks...")

        results = {
            "type_hints": await self.check_type_hints(),
            "print_statements": await self.check_print_statements(),
            "hardcoded_secrets": await self.check_hardcoded_secrets(),
            "missing_tests": await self.check_missing_tests(),
        }

        total_issues = sum(len(v) for v in results.values())
        logger.info(f"📊 Found {total_issues} issues")

        return results

    async def apply_auto_fixes(self) -> dict[str, Any]:
        """Apply auto-fixes where possible"""
        logger.info("🔧 Applying auto-fixes...")

        fixes = {
            "print_statements": await self.auto_fix_print_statements(),
        }

        total_fixes = sum(fixes.values())
        logger.info(f"✅ Applied {total_fixes} auto-fixes")

        return fixes

    async def generate_report(self, results: dict[str, Any], fixes: dict[str, Any]) -> str:
        """Generate monitoring report"""
        report = []
        report.append("=" * 70)
        report.append("NUZANTARA PRIME - CODE WATCHDOG REPORT")
        report.append("=" * 70)
        report.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Issues
        report.append("📋 ISSUES FOUND:")
        for category, issues in results.items():
            if issues:
                report.append(f"  {category}: {len(issues)} issues")
                for issue in issues[:5]:  # Show first 5
                    report.append(f"    - {issue.get('file', 'unknown')}:{issue.get('line', '?')} - {issue.get('issue', 'unknown')}")
        report.append("")

        # Fixes
        report.append("🔧 AUTO-FIXES APPLIED:")
        for category, count in fixes.items():
            if count > 0:
                report.append(f"  {category}: {count} fixes")
        report.append("")

        # Summary
        total_issues = sum(len(v) for v in results.values())
        total_fixes = sum(fixes.values())
        report.append("=" * 70)
        report.append(f"SUMMARY: {total_issues} issues found, {total_fixes} auto-fixes applied")
        report.append("=" * 70)

        return "\n".join(report)

    async def run_once(self) -> None:
        """Run checks and fixes once"""
        results = await self.run_checks()
        fixes = await self.apply_auto_fixes()
        report = await self.generate_report(results, fixes)
        print(report)

    async def run_continuous(self) -> None:
        """Run continuously with interval"""
        logger.info(f"🚀 Starting Code Watchdog (check interval: {self.check_interval}s)")
        logger.info("Press Ctrl+C to stop")

        try:
            while True:
                await self.run_once()
                logger.info(f"⏳ Waiting {self.check_interval}s until next check...")
                await asyncio.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("🛑 Watchdog stopped by user")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Code Watchdog - 24/7 monitoring")
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once instead of continuously",
    )

    args = parser.parse_args()

    watchdog = CodeWatchdog(check_interval=args.interval)

    if args.once:
        asyncio.run(watchdog.run_once())
    else:
        asyncio.run(watchdog.run_continuous())


if __name__ == "__main__":
    main()


