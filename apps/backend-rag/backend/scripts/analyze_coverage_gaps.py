#!/usr/bin/env python3
"""
Coverage Gap Analyzer for Autonomous Test-Fix Loop.

Reads pytest-cov JSON report and identifies:
1. Files with <80% coverage (critical gaps)
2. Uncovered branches in high-import modules
3. Recently changed files with low coverage
4. Public API endpoints with no tests

Usage:
    python3 -m backend.scripts.analyze_coverage_gaps /tmp/nuz-coverage.json
    python3 -m backend.scripts.analyze_coverage_gaps /tmp/nuz-coverage.json --top 20 --output /tmp/nuz-coverage-gaps.json
"""

import json
import subprocess
import sys
from pathlib import Path


def get_recently_changed_files(repo_root: str, days: int = 30) -> set[str]:
    """Get files changed in the last N days via git log."""
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"--since={days} days ago",
                "--name-only",
                "--pretty=format:",
                "--",
                "apps/backend-rag/backend/",
            ],
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=15,
        )
        files = {
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and line.strip().endswith(".py")
        }
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()


def count_importers(file_path: str, all_files: list[str]) -> int:
    """Rough estimate: how many other files import from this module.

    This is a heuristic based on module name matching, not AST parsing.
    """
    # Convert file path to module-style name
    # backend/services/crm.py -> services.crm, crm
    parts = file_path.replace("backend/", "").replace(".py", "").replace("/", ".")
    module_name = parts.split(".")[-1]  # e.g., "crm"

    count = 0
    for other_file in all_files:
        if other_file == file_path:
            continue
        # Simple heuristic: would need to read files for accuracy
        # but this gives a rough priority signal
        if module_name in other_file:
            count += 1

    return count


def is_router_file(file_path: str) -> bool:
    """Check if this is an API router (public-facing endpoint)."""
    return "/routers/" in file_path


def is_service_file(file_path: str) -> bool:
    """Check if this is a service (business logic)."""
    return "/services/" in file_path


def analyze(
    coverage_path: str,
    repo_root: str = "/Users/nuzantara/Desktop/nuzantara",
    top_n: int = 20,
    git_days: int = 30,
) -> dict:
    """Analyze coverage gaps and prioritize them."""
    with open(coverage_path) as f:
        cov = json.load(f)

    # pytest-cov JSON format: {"meta": {...}, "files": {"path": {...}}, "totals": {...}}
    files_data = cov.get("files", {})
    totals = cov.get("totals", {})

    recently_changed = get_recently_changed_files(repo_root, git_days)
    all_file_paths = list(files_data.keys())

    gaps: list[dict] = []

    for filepath, data in files_data.items():
        summary = data.get("summary", {})
        pct = summary.get("percent_covered", 100.0)
        num_statements = summary.get("num_statements", 0)
        missing_lines = data.get("missing_lines", [])
        missing_branches = data.get("missing_branches", [])

        # Skip tiny files (< 5 statements)
        if num_statements < 5:
            continue

        # Skip __init__.py files (usually just imports)
        if filepath.endswith("__init__.py"):
            continue

        # Calculate priority score (lower = more important to cover)
        priority_score = pct  # Base: lower coverage = higher priority

        # Boost priority for recently changed files
        is_recent = any(filepath in f or f.endswith(filepath) for f in recently_changed)
        if is_recent:
            priority_score -= 20  # Bump up priority

        # Boost priority for routers (public API surface)
        if is_router_file(filepath):
            priority_score -= 15

        # Boost priority for services (core business logic)
        if is_service_file(filepath):
            priority_score -= 10

        # Boost based on import count (rough heuristic)
        import_count = count_importers(filepath, all_file_paths)
        if import_count > 3:
            priority_score -= 10

        # Determine severity
        if pct < 30:
            severity = "critical"
        elif pct < 50:
            severity = "high"
        elif pct < 70:
            severity = "medium"
        elif pct < 80:
            severity = "low"
        else:
            continue  # Skip files above 80%

        gaps.append(
            {
                "file": filepath,
                "coverage_pct": round(pct, 1),
                "statements": num_statements,
                "missing_lines_count": len(missing_lines),
                "missing_branches_count": len(missing_branches),
                "severity": severity,
                "is_recent": is_recent,
                "is_router": is_router_file(filepath),
                "is_service": is_service_file(filepath),
                "priority_score": round(priority_score, 1),
            },
        )

    # Sort by priority score (lowest = most important)
    gaps.sort(key=lambda g: g["priority_score"])

    # Take top N
    top_gaps = gaps[:top_n]

    return {
        "total_coverage_pct": round(totals.get("percent_covered", 0), 1),
        "total_files_analyzed": len(files_data),
        "total_statements": totals.get("num_statements", 0),
        "covered_statements": totals.get("covered_lines", 0),
        "missing_statements": totals.get("missing_lines", 0),
        "gap_count": len(gaps),
        "severity_breakdown": {
            "critical": sum(1 for g in gaps if g["severity"] == "critical"),
            "high": sum(1 for g in gaps if g["severity"] == "high"),
            "medium": sum(1 for g in gaps if g["severity"] == "medium"),
            "low": sum(1 for g in gaps if g["severity"] == "low"),
        },
        "top_gaps": top_gaps,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Analyze coverage gaps")
    parser.add_argument("coverage_report", help="Path to pytest-cov JSON report")
    parser.add_argument(
        "--output",
        "-o",
        default="/tmp/nuz-coverage-gaps.json",
        help="Output path",
    )
    parser.add_argument("--top", type=int, default=20, help="Top N gaps to report")
    parser.add_argument("--days", type=int, default=30, help="Git log lookback days")
    args = parser.parse_args()

    if not Path(args.coverage_report).exists():
        print(f"ERROR: Coverage report not found: {args.coverage_report}", file=sys.stderr)
        sys.exit(1)

    result = analyze(
        args.coverage_report,
        top_n=args.top,
        git_days=args.days,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    # Print summary
    print("=== Coverage Gap Analysis ===")
    print(f"Total coverage: {result['total_coverage_pct']}%")
    print(f"Files analyzed: {result['total_files_analyzed']}")
    print(f"Files below 80%: {result['gap_count']}")
    print(f"Severity: {json.dumps(result['severity_breakdown'])}")
    print(f"\nTop {args.top} priority gaps:")
    for g in result["top_gaps"]:
        flags = []
        if g["is_recent"]:
            flags.append("RECENT")
        if g["is_router"]:
            flags.append("ROUTER")
        if g["is_service"]:
            flags.append("SERVICE")
        flag_str = f" [{','.join(flags)}]" if flags else ""
        print(f"  {g['coverage_pct']:5.1f}%  {g['file']}{flag_str}")
    print(f"\nOutput written to: {args.output}")


if __name__ == "__main__":
    main()
