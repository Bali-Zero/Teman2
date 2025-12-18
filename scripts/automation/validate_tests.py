#!/usr/bin/env python3
"""
NUZANTARA PRIME - Incremental Test Validator
Analyzes modified files and runs only relevant tests before push.
"""

import subprocess
import sys
from pathlib import Path

# Colors for output
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color


def get_modified_files() -> list[str]:
    """Get list of modified Python files in backend"""
    try:
        # Get staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
        staged_files = (
            result.stdout.strip().split("\n") if result.stdout.strip() else []
        )

        # Get unstaged files
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
        unstaged_files = (
            result.stdout.strip().split("\n") if result.stdout.strip() else []
        )

        # Combine and filter Python files in backend
        all_files = set(staged_files + unstaged_files)
        backend_files = [
            f
            for f in all_files
            if f.startswith("apps/backend-rag/backend/") and f.endswith(".py")
        ]

        return backend_files
    except subprocess.CalledProcessError:
        return []


def map_file_to_test(file_path: str) -> str | None:
    """Map a backend file to its corresponding test file"""
    # Remove apps/backend-rag/ prefix
    if file_path.startswith("apps/backend-rag/"):
        file_path = file_path[len("apps/backend-rag/") :]

    # Map backend/... to tests/unit/test_...
    if file_path.startswith("backend/"):
        test_path = file_path.replace("backend/", "tests/unit/test_")
        # Handle subdirectories
        if "/" in test_path:
            parts = test_path.split("/")
            # Insert 'test_' before filename
            filename = parts[-1]
            parts[-1] = f"test_{filename}"
            test_path = "/".join(parts)

        # Check if test file exists
        full_test_path = Path("apps/backend-rag") / test_path
        if full_test_path.exists():
            return str(full_test_path)

    return None


def get_relevant_tests(modified_files: list[str]) -> set[str]:
    """Get set of relevant test files for modified files"""
    test_files = set()

    for file_path in modified_files:
        test_file = map_file_to_test(file_path)
        if test_file:
            test_files.add(test_file)

    return test_files


def run_tests(test_files: set[str] | None = None, verbose: bool = False) -> bool:
    """Run pytest on specified test files or all unit tests"""
    cmd = ["python", "-m", "pytest"]

    if test_files:
        cmd.extend(sorted(test_files))
    else:
        cmd.append("tests/unit/")

    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    cmd.extend(["--tb=short", "-x"])  # Stop on first failure

    print(f"{BLUE}Running: {' '.join(cmd)}{NC}")
    print("")

    result = subprocess.run(cmd, cwd="apps/backend-rag")
    return result.returncode == 0


def main():
    """Main validation logic"""
    print(f"{BLUE}🧪 NUZANTARA PRIME - Incremental Test Validator{NC}")
    print("=" * 60)
    print("")

    # Get modified files
    modified_files = get_modified_files()

    if not modified_files:
        print(f"{YELLOW}⚠️  No modified Python files in backend detected{NC}")
        print(f"{GREEN}✅ Skipping test validation${NC}")
        return 0

    print(f"{BLUE}📋 Modified files:${NC}")
    for f in modified_files:
        print(f"  - {f}")
    print("")

    # Get relevant tests
    test_files = get_relevant_tests(modified_files)

    if test_files:
        print(f"{BLUE}🎯 Relevant test files:${NC}")
        for tf in sorted(test_files):
            print(f"  - {tf}")
        print("")
        print(f"{YELLOW}Running incremental tests...${NC}")
        print("")
        success = run_tests(test_files, verbose=True)
    else:
        print(f"{YELLOW}⚠️  No specific test files found for modified files${NC}")
        print(f"{YELLOW}Running all unit tests...${NC}")
        print("")
        success = run_tests(verbose=True)

    if success:
        print("")
        print(f"{GREEN}✅ All tests passed!${NC}")
        print(f"{GREEN}✅ Safe to push!${NC}")
        return 0
    else:
        print("")
        print(f"{RED}❌ Tests failed!${NC}")
        print("")
        print(f"{YELLOW}💡 To fix:${NC}")
        print("  1. Review the test failures above")
        print("  2. Fix the failing tests")
        print("  3. Run: cd apps/backend-rag && python -m pytest tests/unit/ -v")
        print("  4. Then try pushing again")
        print("")
        return 1


if __name__ == "__main__":
    sys.exit(main())
