#!/usr/bin/env python3
"""observe_zantara_e28_1015.py - bites: observation for the E28 Zantara + legacy matcher lane (2026-10-15).

# bites-observable - this script takes NO arguments: the program it runs and the test files it
# names are literal strings in this file, so nothing an invoker types can name a program to run,
# a file to write, or a database to reach.

Zantara's golden routes, few-shot examples, worked prompts and the legacy /api/visa/match E28A
entry must say only what the signed pack (seq-29) and the saved official E28 pages say: no E28G,
no E28A as a worker permit, no IDR 10 billion as minimum or paid-up capital, Golden Visa figures
bound per code to the saved page, E28A extension 365 days and the page's document list.

Runs the three guilt-and-innocence files under apps/backend-rag with the backend venv when the
checkout carries one. Exit 0 only on a pure pass (no failed, skipped or error) of at least 60 tests.
"""

# bites-observable - no arguments; one literal program, literal test files.

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "apps" / "backend-rag"
TESTS = [
    "backend/tests/services/rag/test_kg_routes_e28_1015.py",
    "backend/tests/services/visa_check/test_catalogue_e28a_1015.py",
    "backend/tests/unit/prompts/test_prompts_e28_1015.py",
]
MIN_TESTS = 60
TIMEOUT_SECONDS = 300

_SUMMARY = re.compile(r"^=*\s*(\d+) passed in [\d.]+s(?: \(.*\))?\s*=*$")


def summary_ok(line: str | None) -> bool:
    """True only for a pytest line that is a pure pass (no failed/skipped/error), N >= MIN_TESTS."""
    if line is None:
        return False
    match = _SUMMARY.match(line.strip())
    return match is not None and int(match.group(1)) >= MIN_TESTS


def _python() -> str:
    venv = BACKEND_ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def main() -> int:
    env = dict(os.environ)
    env.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
    env.setdefault("API_KEYS", "test_api_key_1")
    try:
        result = subprocess.run(
            [_python(), "-m", "pytest", "-p", "no:cacheprovider", "--color=no", *TESTS],
            cwd=BACKEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"observe_zantara_e28_1015: FAILED (timeout after {TIMEOUT_SECONDS}s)")
        return 1
    out = result.stdout + result.stderr
    lines = [ln for ln in out.splitlines() if " passed" in ln or " failed" in ln or "error" in ln]
    line = lines[-1] if lines else None
    summary = line.strip() if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_zantara_e28_1015: FAILED ({summary})\n{out[-1500:]}")
        return 1
    print(f"observe_zantara_e28_1015: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
