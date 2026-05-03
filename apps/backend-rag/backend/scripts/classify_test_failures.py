#!/usr/bin/env python3
"""
Failure Classification Engine for Autonomous Test-Fix Loop.

Reads pytest-json-report output and classifies each failure into:
- IMPORT: ModuleNotFoundError, ImportError
- SYNTAX: SyntaxError, IndentationError
- FIXTURE: fixture not found, setup errors
- TYPE: TypeError, AttributeError (wrong interface)
- LOGIC: AssertionError (wrong result)
- INTEGRATION: ConnectionError, TimeoutError, database errors
- FLAKY: passes on re-run (detected by 3x retry — future)

Priority: IMPORT > SYNTAX > FIXTURE > TYPE > LOGIC > INTEGRATION > FLAKY

Usage:
    python3 -m backend.scripts.classify_test_failures /tmp/nuz-test-results.json
    python3 -m backend.scripts.classify_test_failures /tmp/nuz-test-results.json --output /tmp/nuz-failure-queue.json
"""

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

FailureType = Literal["IMPORT", "SYNTAX", "FIXTURE", "TYPE", "LOGIC", "INTEGRATION", "FLAKY"]

PRIORITY: dict[FailureType, int] = {
    "IMPORT": 1,
    "SYNTAX": 2,
    "FIXTURE": 3,
    "TYPE": 4,
    "LOGIC": 5,
    "INTEGRATION": 6,
    "FLAKY": 99,
}

# Order matters: first match wins. More specific patterns first.
ERROR_PATTERNS: list[tuple[FailureType, list[str]]] = [
    (
        "IMPORT",
        [
            "ModuleNotFoundError",
            "ImportError",
            "No module named",
            "cannot import name",
        ],
    ),
    (
        "SYNTAX",
        [
            "SyntaxError",
            "IndentationError",
            "invalid syntax",
            "unexpected EOF",
        ],
    ),
    (
        "FIXTURE",
        [
            "fixture",
            "ERRORS",
            "SetupError",
            "E fixture",
            "not found",
            "ScopeMismatch",
            "Failed: Database",
            "conftest",
        ],
    ),
    (
        "INTEGRATION",
        [
            "ConnectionError",
            "ConnectionRefusedError",
            "TimeoutError",
            "OperationalError",
            "httpx.ConnectError",
            "aiohttp.ClientError",
            "redis.exceptions",
            "asyncpg",
            "sqlalchemy.exc",
            "qdrant_client",
        ],
    ),
    (
        "TYPE",
        [
            "TypeError",
            "AttributeError",
            "has no attribute",
            "unexpected keyword",
            "missing .* required",
            "takes .* positional",
            "got an unexpected keyword",
        ],
    ),
    (
        "LOGIC",
        [
            "AssertionError",
            "AssertionError",
            "assert ",
            "!=",
            "Expected",
            "not equal",
        ],
    ),
]


@dataclass
class TestFailure:
    test_id: str
    file_path: str
    test_file: str
    error_type: FailureType
    error_message: str
    root_exception: str
    priority: int
    fix_attempts: int = 0
    status: str = "pending"
    group_key: str = ""


def extract_root_exception(longrepr: str) -> str:
    """Extract the root/innermost exception from a traceback.

    For fixture errors, pytest wraps the real error in the test's traceback.
    We need to dig through to find the actual cause.
    """
    if not longrepr:
        return ""

    # Look for "E   <ExceptionType>:" lines (pytest format)
    e_lines = re.findall(r"^E\s+(\w+(?:Error|Exception|Warning)\s*:.*)$", longrepr, re.MULTILINE)
    if e_lines:
        return e_lines[-1].strip()[:300]

    # Look for standard Python traceback "ExceptionType: message"
    exc_lines = re.findall(r"^(\w+(?:Error|Exception|Warning):\s*.*)$", longrepr, re.MULTILINE)
    if exc_lines:
        return exc_lines[-1].strip()[:300]

    # Look for "FAILED" or "ERROR" summary lines
    fail_lines = re.findall(r"^(FAILED|ERROR)\s+.*$", longrepr, re.MULTILINE)
    if fail_lines:
        return fail_lines[0].strip()[:300]

    # Fallback: last non-empty line
    lines = [line.strip() for line in longrepr.strip().splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""


def classify_error(longrepr: str, root_exc: str) -> FailureType:
    """Classify the error type based on traceback and root exception."""
    search_text = f"{longrepr}\n{root_exc}"

    for error_type, patterns in ERROR_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, search_text, re.IGNORECASE):
                return error_type

    return "LOGIC"  # default


def infer_source_from_test(test_path: str) -> str:
    """Infer source file from test file path.

    Conventions:
        backend/tests/unit/services/test_crm.py -> backend/services/crm.py
        backend/tests/unit/routers/test_auth.py -> backend/routers/auth.py
        backend/tests/services/rag/test_kg.py   -> backend/services/rag/kg.py
    """
    path = test_path

    # Remove test directory prefixes
    path = re.sub(r"backend/tests/unit/", "backend/", path)
    path = re.sub(r"backend/tests/integration/", "backend/", path)
    path = re.sub(r"backend/tests/e2e/", "backend/", path)
    path = re.sub(r"backend/tests/", "backend/", path)

    # Remove test_ prefix from filename
    parts = path.rsplit("/", 1)
    if len(parts) == 2:
        directory, filename = parts
        filename = re.sub(r"^test_", "", filename)
        path = f"{directory}/{filename}"

    return path


def compute_group_key(failure: TestFailure) -> str:
    """Compute a grouping key for batching similar failures.

    Failures with the same group_key likely share a root cause.
    """
    if failure.error_type == "IMPORT":
        # Group by the missing module name
        match = re.search(r"No module named ['\"]([^'\"]+)['\"]", failure.error_message)
        if match:
            return f"IMPORT:{match.group(1)}"
        match = re.search(r"cannot import name ['\"]([^'\"]+)['\"]", failure.error_message)
        if match:
            return f"IMPORT:{match.group(1)}"
        return f"IMPORT:{failure.file_path}"

    if failure.error_type == "FIXTURE":
        # Group by fixture name
        match = re.search(r"fixture ['\"]([^'\"]+)['\"]", failure.error_message)
        if match:
            return f"FIXTURE:{match.group(1)}"
        return f"FIXTURE:{failure.test_file}"

    if failure.error_type == "TYPE":
        # Group by the affected class/function
        return f"TYPE:{failure.file_path}"

    # Default: group by source file
    return f"{failure.error_type}:{failure.file_path}"


def classify_report(report_path: str) -> list[TestFailure]:
    """Parse pytest-json-report and classify all failures."""
    with open(report_path) as f:
        report = json.load(f)

    failures: list[TestFailure] = []

    for test in report.get("tests", []):
        outcome = test.get("outcome", "")
        if outcome not in ("failed", "error"):
            continue

        # Extract traceback — handle both call and setup phases
        longrepr = ""
        for phase in ("call", "setup", "teardown"):
            phase_data = test.get(phase, {})
            if phase_data.get("longrepr"):
                longrepr = phase_data["longrepr"]
                break
            # Sometimes it's nested under crash/traceback
            if phase_data.get("crash", {}).get("message"):
                longrepr = phase_data["crash"]["message"]
                break
            if phase_data.get("traceback"):
                tb = phase_data["traceback"]
                if isinstance(tb, list):
                    longrepr = "\n".join(entry.get("message", str(entry)) for entry in tb)
                else:
                    longrepr = str(tb)
                break

        # For fixture errors, also check if longrepr is at test level
        if not longrepr and test.get("longrepr"):
            longrepr = str(test["longrepr"])

        root_exc = extract_root_exception(longrepr)
        error_type = classify_error(longrepr, root_exc)

        # Override: if outcome is "error" (not "failed"), it's likely setup/fixture
        if outcome == "error" and error_type not in ("IMPORT", "SYNTAX"):
            error_type = "FIXTURE"

        test_file = test.get("nodeid", "").split("::")[0]
        source_path = infer_source_from_test(test_file)

        failure = TestFailure(
            test_id=test.get("nodeid", "unknown"),
            file_path=source_path,
            test_file=test_file,
            error_type=error_type,
            error_message=longrepr[:500],
            root_exception=root_exc,
            priority=PRIORITY[error_type],
        )
        failure.group_key = compute_group_key(failure)
        failures.append(failure)

    # Sort by priority
    failures.sort(key=lambda f: (f.priority, f.group_key))
    return failures


def build_summary(failures: list[TestFailure]) -> dict:
    """Build summary statistics."""
    by_type: dict[str, int] = {}
    by_group: dict[str, int] = {}

    for f in failures:
        by_type[f.error_type] = by_type.get(f.error_type, 0) + 1
        by_group[f.group_key] = by_group.get(f.group_key, 0) + 1

    # Top root causes (groups with most failures)
    top_groups = sorted(by_group.items(), key=lambda x: -x[1])[:20]

    return {
        "total": len(failures),
        "by_type": by_type,
        "top_root_causes": [{"group": g, "count": c} for g, c in top_groups],
        "unique_groups": len(by_group),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Classify pytest failures")
    parser.add_argument("report", help="Path to pytest-json-report JSON file")
    parser.add_argument(
        "--output",
        "-o",
        default="/tmp/nuz-failure-queue.json",
        help="Output path for classified failures",
    )
    args = parser.parse_args()

    if not Path(args.report).exists():
        print(f"ERROR: Report file not found: {args.report}", file=sys.stderr)
        sys.exit(1)

    failures = classify_report(args.report)
    summary = build_summary(failures)

    output = {
        **summary,
        "queue": [asdict(f) for f in failures],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary to stdout
    print("=== Test Failure Classification ===")
    print(f"Total failures: {summary['total']}")
    print(f"By type: {json.dumps(summary['by_type'], indent=2)}")
    print(f"Unique root causes: {summary['unique_groups']}")
    print("\nTop root causes:")
    for item in summary["top_root_causes"][:10]:
        print(f"  {item['count']:4d}x  {item['group']}")
    print(f"\nOutput written to: {args.output}")


if __name__ == "__main__":
    main()
