#!/usr/bin/env python3
"""
Script to help achieve 100% test coverage

1. Comment out tests for removed endpoints
2. Run coverage analysis
3. Generate report of uncovered files
"""

import re
import subprocess
import sys
from pathlib import Path

# Files with tests that need to be fixed
TEST_FILES_TO_FIX = [
    "apps/backend-rag/tests/unit/test_identity_router.py",
]

# Endpoints that were removed (to comment out tests)
REMOVED_ENDPOINTS = [
    "seed_team_endpoint",
    "run_migration_010",
    "debug_auth",
    "reset_admin_user",
]


def comment_out_tests_for_removed_endpoints():
    """Comment out test functions that use removed endpoints"""
    for test_file in TEST_FILES_TO_FIX:
        file_path = Path(test_file)
        if not file_path.exists():
            print(f"⚠️  File not found: {test_file}")
            continue

        content = file_path.read_text(encoding="utf-8")

        # Find and comment out test functions that use removed endpoints
        for endpoint in REMOVED_ENDPOINTS:
            # Pattern to find test functions that import or use the endpoint
            pattern = rf"(# NOTE:.*?{endpoint}.*?\n)?(@pytest\.mark\.asyncio\s+async def test_.*?{endpoint}.*?\(.*?\):.*?\n(?:.*?\n)*?)(?=@pytest\.mark\.asyncio|def test_|# =|$)"

            def comment_match(match):
                test_code = match.group(0)
                if test_code.strip().startswith("#"):
                    return test_code  # Already commented
                # Comment out the entire test
                lines = test_code.split("\n")
                commented_lines = []
                for line in lines:
                    if line.strip():
                        commented_lines.append(f"# {line}")
                    else:
                        commented_lines.append(line)
                return "\n".join(commented_lines) + "\n"

            # First pass: comment out imports
            import_pattern = rf"from app\.modules\.identity\.router import.*?{endpoint}"
            content = re.sub(
                import_pattern,
                lambda m: f"# REMOVED: {m.group(0)}",
                content,
                flags=re.MULTILINE | re.DOTALL,
            )

            # Second pass: comment out usage
            usage_pattern = rf"await {endpoint}\(\)"
            content = re.sub(
                usage_pattern,
                lambda m: f"# REMOVED: {m.group(0)}",
                content,
                flags=re.MULTILINE,
            )

        file_path.write_text(content, encoding="utf-8")
        print(f"✅ Fixed: {test_file}")


def run_coverage():
    """Run coverage analysis"""
    print("\n" + "=" * 60)
    print("Running Coverage Analysis")
    print("=" * 60)

    backend_path = Path("apps/backend-rag")
    os.chdir(backend_path)

    # Run coverage
    result = subprocess.run(
        [
            "python",
            "-m",
            "coverage",
            "run",
            "--source=backend",
            "-m",
            "pytest",
            "tests/unit",
            "-v",
            "--tb=line",
        ],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    # Generate report
    report_result = subprocess.run(
        ["python", "-m", "coverage", "report", "--show-missing"],
        capture_output=True,
        text=True,
    )

    print("\n" + "=" * 60)
    print("Coverage Report")
    print("=" * 60)
    print(report_result.stdout)

    return result.returncode == 0


if __name__ == "__main__":
    import os

    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("=" * 60)
    print("Fixing Test Coverage")
    print("=" * 60)

    # Step 1: Comment out tests for removed endpoints
    print("\nStep 1: Commenting out tests for removed endpoints...")
    comment_out_tests_for_removed_endpoints()

    # Step 2: Run coverage
    print("\nStep 2: Running coverage analysis...")
    success = run_coverage()

    sys.exit(0 if success else 1)

