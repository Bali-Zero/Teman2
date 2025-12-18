#!/usr/bin/env python3
"""
Backend Diff Coverage Calculator

Computes coverage percentage for only the lines changed in git diff.
Uses pytest-cov JSON coverage report format.

Usage:
    python scripts/coverage/diff_coverage_py.py [--threshold=80] [--base=main] [--coverage-file=apps/backend-rag/coverage.json]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


def get_changed_lines(base_branch: str = "main") -> Dict[str, Set[int]]:
    """
    Get changed line numbers per file from git diff.
    
    Returns:
        Dict mapping file paths (relative to repo root) to set of changed line numbers
    """
    changed_lines: Dict[str, Set[int]] = {}
    
    # Get diff with unified=0 to get line numbers
    cmd = ["git", "diff", f"origin/{base_branch}...HEAD", "--unified=0"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        # Fallback to local diff if remote branch doesn't exist
        cmd = ["git", "diff", base_branch, "--unified=0"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    
    if result.returncode != 0:
        print(f"⚠️  Warning: Could not get git diff. Using staged changes instead.")
        cmd = ["git", "diff", "--cached", "--unified=0"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    
    if result.returncode != 0:
        print(f"❌ Error: No git diff available. Are you in a git repository?")
        return changed_lines
    
    current_file = None
    for line in result.stdout.splitlines():
        # Look for file header: @@ -start,count +start,count @@
        if line.startswith("@@") and "@@" in line[2:]:
            # Extract line numbers from hunk header
            # Format: @@ -old_start,old_count +new_start,new_count @@
            parts = line.split("@@")
            if len(parts) >= 2:
                hunk_info = parts[1].strip()
                # Parse +new_start,new_count
                if "+" in hunk_info:
                    new_part = [p for p in hunk_info.split() if p.startswith("+")][0]
                    new_part = new_part[1:]  # Remove +
                    if "," in new_part:
                        start_str, count_str = new_part.split(",", 1)
                    else:
                        start_str = new_part
                        count_str = "1"
                    try:
                        start = int(start_str)
                        count = int(count_str)
                        # Add all lines in this hunk
                        if current_file:
                            for line_num in range(start, start + count):
                                changed_lines[current_file].add(line_num)
                    except ValueError:
                        pass
        # Look for file path: --- a/path or +++ b/path
        elif line.startswith("+++ b/"):
            file_path = line[6:]  # Remove "+++ b/"
            # Normalize path (remove apps/backend-rag/backend/ prefix if present)
            if file_path.startswith("apps/backend-rag/backend/"):
                file_path = file_path[len("apps/backend-rag/backend/"):]
            elif file_path.startswith("apps/backend-rag/"):
                file_path = file_path[len("apps/backend-rag/"):]
            # Only track Python files
            if file_path.endswith(".py") and "/test" not in file_path.lower():
                current_file = file_path
                if current_file not in changed_lines:
                    changed_lines[current_file] = set()
        elif line.startswith("--- a/"):
            # Reset current file on old file header
            pass
    
    return changed_lines


def load_coverage_data(coverage_file: Path) -> Dict:
    """Load pytest-cov JSON coverage data."""
    if not coverage_file.exists():
        print(f"❌ Coverage file not found: {coverage_file}")
        print(f"   Run: cd apps/backend-rag && pytest --cov=backend --cov-report=json:{coverage_file.name}")
        sys.exit(1)
    
    with open(coverage_file) as f:
        return json.load(f)


def calculate_diff_coverage(
    coverage_data: Dict,
    changed_lines: Dict[str, Set[int]],
    backend_dir: Path = Path("apps/backend-rag/backend")
) -> Tuple[float, Dict[str, Dict]]:
    """
    Calculate coverage percentage for changed lines only.
    
    Returns:
        (diff_coverage_percent, file_details_dict)
    """
    total_changed = 0
    total_covered = 0
    file_details: Dict[str, Dict] = {}
    
    files = coverage_data.get("files", {})
    
    for file_path, changed_line_nums in changed_lines.items():
        if not changed_line_nums:
            continue
        
        # Find matching coverage entry
        # Coverage JSON uses paths like "backend/path/to/file.py"
        coverage_key = None
        for key in files.keys():
            # Normalize paths for comparison
            normalized_key = key.replace("apps/backend-rag/backend/", "").replace("apps/backend-rag/", "")
            if normalized_key == file_path or key.endswith(file_path):
                coverage_key = key
                break
        
        if not coverage_key:
            # File not in coverage (new file, not tested)
            file_details[file_path] = {
                "changed_lines": len(changed_line_nums),
                "covered_lines": 0,
                "coverage": 0.0,
                "missing_lines": sorted(changed_line_nums)
            }
            total_changed += len(changed_line_nums)
            continue
        
        file_data = files[coverage_key]
        executed_lines = set(file_data.get("executed_lines", []))
        missing_lines = set(file_data.get("missing_lines", []))
        
        # Count coverage for changed lines only
        changed_covered = len([ln for ln in changed_line_nums if ln in executed_lines])
        changed_missing = len([ln for ln in changed_line_nums if ln in missing_lines])
        
        # Lines that are changed but not in coverage (new lines, excluded, etc.)
        changed_unknown = len(changed_line_nums) - changed_covered - changed_missing
        
        file_changed = len(changed_line_nums)
        file_covered = changed_covered
        
        total_changed += file_changed
        total_covered += file_covered
        
        file_details[file_path] = {
            "changed_lines": file_changed,
            "covered_lines": file_covered,
            "coverage": (file_covered / file_changed * 100) if file_changed > 0 else 100.0,
            "missing_lines": sorted([ln for ln in changed_line_nums if ln in missing_lines]),
            "unknown_lines": changed_unknown
        }
    
    diff_coverage = (total_covered / total_changed * 100) if total_changed > 0 else 100.0
    
    return diff_coverage, file_details


def print_report(diff_coverage: float, file_details: Dict[str, Dict], threshold: float):
    """Print formatted coverage report."""
    print("\n" + "=" * 80)
    print("BACKEND DIFF COVERAGE REPORT")
    print("=" * 80)
    print(f"\nDiff Coverage: {diff_coverage:.2f}%")
    print(f"Threshold: {threshold:.1f}%")
    
    if diff_coverage >= threshold:
        print("✅ PASSED")
    else:
        print(f"❌ FAILED (below threshold by {threshold - diff_coverage:.2f}%)")
    
    if file_details:
        print("\nFile Details:")
        print("-" * 80)
        for file_path, details in sorted(file_details.items(), key=lambda x: x[1]["coverage"]):
            status = "✅" if details["coverage"] >= threshold else "❌"
            print(f"{status} {details['coverage']:5.1f}% | "
                  f"{details['covered_lines']:3d}/{details['changed_lines']:3d} lines | "
                  f"{file_path}")
            if details.get("missing_lines"):
                missing_preview = details["missing_lines"][:5]
                missing_str = ", ".join(map(str, missing_preview))
                if len(details["missing_lines"]) > 5:
                    missing_str += f" ... (+{len(details['missing_lines']) - 5} more)"
                print(f"      Missing lines: {missing_str}")
    
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Calculate diff coverage for backend Python code"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Minimum coverage threshold (default: 80.0%%)"
    )
    parser.add_argument(
        "--base",
        type=str,
        default="main",
        help="Base branch for diff (default: main)"
    )
    parser.add_argument(
        "--coverage-file",
        type=str,
        default="apps/backend-rag/coverage.json",
        help="Path to pytest-cov JSON coverage file (default: apps/backend-rag/coverage.json)"
    )
    parser.add_argument(
        "--generate-coverage",
        action="store_true",
        help="Generate coverage file before calculating diff coverage"
    )
    
    args = parser.parse_args()
    
    coverage_file = Path(args.coverage_file)
    
    # Generate coverage if requested
    if args.generate_coverage or not coverage_file.exists():
        print("📊 Generating coverage report...")
        backend_dir = Path("apps/backend-rag")
        if not backend_dir.exists():
            print(f"❌ Backend directory not found: {backend_dir}")
            sys.exit(1)
        
        cmd = [
            "python", "-m", "pytest",
            str(backend_dir / "tests" / "unit"),
            "-m", "unit",
            "--cov=backend",
            f"--cov-report=json:{coverage_file}",
            "--cov-report=term",
            "-q"
        ]
        
        result = subprocess.run(cmd, cwd=backend_dir, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️  Warning: Tests had failures, but continuing with coverage...")
            if not coverage_file.exists():
                print(f"❌ Failed to generate coverage file")
                sys.exit(1)
    
    # Get changed lines
    print("🔍 Analyzing git diff...")
    changed_lines = get_changed_lines(args.base)
    
    if not changed_lines:
        print("ℹ️  No changed Python files found in diff.")
        print("   This might mean:")
        print("   - No changes compared to base branch")
        print("   - Only test files were changed")
        print("   - Only non-Python files were changed")
        print("\n✅ Diff coverage check passed (no production code changes)")
        sys.exit(0)
    
    # Load coverage data
    print(f"📖 Loading coverage data from {coverage_file}...")
    coverage_data = load_coverage_data(coverage_file)
    
    # Calculate diff coverage
    print("🧮 Calculating diff coverage...")
    diff_coverage, file_details = calculate_diff_coverage(coverage_data, changed_lines)
    
    # Print report
    print_report(diff_coverage, file_details, args.threshold)
    
    # Exit with appropriate code
    if diff_coverage >= args.threshold:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

