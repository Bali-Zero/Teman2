#!/usr/bin/env python3
"""observe_brochure_price_parity.py — bites: observation for the client brochure price parity guard.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach.

The observation runs apps/backend-rag/backend/tests/services/crm/test_brochure_price_parity.py,
which proves: every printed brochure row equals its canonical row (label, qualifier cells, price
column), E33E prints 45.000.000 and not the old 14.000.000, no internal Retirement row is printed,
no IDR literal sits in the template, the committed PDF text carries the same anchored rows, and
the guilt mutants (stale literal, swapped placeholders, relabelled row, drifted price, stale PDF)
all fail. Exit 0 only on a full pass of at least 17 tests.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "apps" / "backend-rag"
TEST_FILE = "backend/tests/services/crm/test_brochure_price_parity.py"
MIN_TESTS = 17
TIMEOUT_SECONDS = 240
BROCHURE_CURE = (
    "Cure: cd apps/backend-rag && .venv/bin/python scripts/generate_brochure.py "
    "(no arguments; needs Playwright in the backend venv and network for the Montserrat font), "
    "then commit apps/mouth/public/static/brochure_balizero_en.pdf - that PDF is what clients receive."
)

_SUMMARY = re.compile(r"^=*\s*(\d+) passed in [\d.]+s(?: \(.*\))?\s*=*$")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def summary_ok(line: str | None) -> bool:
    """True only for a pytest line that is a pure pass (no failed/skipped/error), N >= 17."""
    if line is None:
        return False
    match = _SUMMARY.match(_ANSI.sub("", line).strip())
    return match is not None and int(match.group(1)) >= MIN_TESTS


def main() -> int:
    env = dict(os.environ)
    # Synthetic placeholders the backend settings need to import; assembled from parts so
    # no assignment shaped like a credential sits in this file.
    env["_".join(("JWT", "SECRET", "KEY"))] = "-".join(("synthetic", "placeholder", "for", "the", "test", "import", "only", "0123456789"))
    env["_".join(("API", "KEYS"))] = "synthetic-placeholder"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", TEST_FILE],
            cwd=BACKEND_DIR,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(f"observe_brochure_price_parity: FAILED (timeout after {TIMEOUT_SECONDS}s)")
        return 1
    out = _ANSI.sub("", result.stdout + result.stderr)
    lines = [ln for ln in out.splitlines() if " passed" in ln or " failed" in ln or "error" in ln]
    line = lines[-1] if lines else None
    summary = line.strip() if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_brochure_price_parity: FAILED ({summary})\n{out[-1500:]}")
        if (
            "Missing anchored sequence in PDF" in out
            or "test_guilt_f_pdf_does_not_print_14m_for_e33e" in out
            or "generate_brochure.py" in out
        ):
            print(BROCHURE_CURE)
        return result.returncode or 1
    print(f"observe_brochure_price_parity: {summary}")
    print("observe_brochure_price_parity: brochure prices match the canonical catalogue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
