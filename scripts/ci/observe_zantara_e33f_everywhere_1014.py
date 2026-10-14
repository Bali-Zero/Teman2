#!/usr/bin/env python3
"""observe_zantara_e33f_everywhere_1014.py — bites: observation for the E33F-everywhere ruling (2026-10-14).

# bites-observable — this script takes NO arguments: the programs it runs and the test files it
# names are literal strings in this file, so nothing an invoker types can name a program to run,
# a file to write, or a database to reach.

Zero ruled "E33F everywhere": the three internal Retirement rows leave search, the LLM context,
the no-query pricing tools, the legacy recommender, the pricing list routes and the Qdrant sync
(report-only unless --purge-internal), while get_service_by_key / get_all_prices / get_pricing
stay raw so old signed packs and the renewal rules keep resolving them.

The observation runs two pytest invocations and exits 0 only if BOTH are a pure pass (no failed,
skipped or error) at or above their floor:
  1. repo root: tests/scripts/test_sync_pricing_collection_prices_internal_1014.py
  2. apps/backend-rag: the new search/context/tool/recommender guilt-and-innocence file plus the
     pricing service, pricing router and visa oracle service tests that pin the raw resolution.
"""

# bites-observable — no arguments; literal programs, literal test files.

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "apps" / "backend-rag"
TIMEOUT_SECONDS = 600

ROOT_TESTS = ["tests/scripts/test_sync_pricing_collection_prices_internal_1014.py"]
ROOT_FLOOR = 6

BACKEND_TESTS = [
    "backend/tests/services/pricing/test_internal_rows_leave_search_1014.py",
    "backend/tests/unit/prompts/test_few_shot_e33f_everywhere_1014.py",
    "backend/tests/unit/scripts/test_prepare_payloads_internal_1014.py",
    "backend/tests/services/pricing/test_pricing_service.py",
    "backend/tests/routers/test_dynamic_pricing.py",
    "backend/tests/services/test_visa_oracle_service.py",
    "backend/tests/services/misc/test_zantara_tools.py",
]
BACKEND_FLOOR = 110

_SUMMARY = re.compile(r"^=*\s*(\d+) passed in [\d.]+s(?: \(.*\))?\s*=*$")


def summary_ok(line: str | None, floor: int) -> bool:
    """True only for a pytest line that is a pure pass (no failed/skipped/error), N >= floor."""
    if line is None:
        return False
    match = _SUMMARY.match(line.strip())
    return match is not None and int(match.group(1)) >= floor


def _python() -> str:
    """The backend venv interpreter when the checkout carries one, else the running interpreter."""
    venv = BACKEND_ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def _run(
    label: str, cwd: Path, tests: list[str], floor: int, env: dict[str, str]
) -> bool:
    try:
        result = subprocess.run(
            [
                _python(),
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "--color=no",
                *tests,
            ],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(
            f"observe_zantara_e33f_everywhere_1014: FAILED {label} (timeout after {TIMEOUT_SECONDS}s)"
        )
        return False
    out = result.stdout + result.stderr
    lines = [
        ln
        for ln in out.splitlines()
        if " passed" in ln or " failed" in ln or "error" in ln
    ]
    line = lines[-1] if lines else None
    summary = line.strip() if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line, floor):
        print(
            f"observe_zantara_e33f_everywhere_1014: FAILED {label} ({summary})\n{out[-1500:]}"
        )
        return False
    print(f"observe_zantara_e33f_everywhere_1014: {label}: {summary}")
    return True


def main() -> int:
    env = dict(os.environ)
    env.setdefault(
        "JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long"
    )
    env.setdefault("API_KEYS", "test_api_key_1")
    ok_root = _run("root", REPO_ROOT, ROOT_TESTS, ROOT_FLOOR, env)
    ok_backend = _run("backend", BACKEND_ROOT, BACKEND_TESTS, BACKEND_FLOOR, env)
    if not (ok_root and ok_backend):
        return 1
    print(
        "observe_zantara_e33f_everywhere_1014: internal Retirement rows leave client paths, raw rows still resolve"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
