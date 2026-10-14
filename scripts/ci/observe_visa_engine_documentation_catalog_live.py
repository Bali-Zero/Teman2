#!/usr/bin/env python3
"""observe_visa_engine_documentation_catalog_live.py — post-deploy bites: observation for E33 PR-8.

# bites-observable — this script takes NO arguments: the program, the module and the
# URL it reaches are literal strings in this file, so nothing an invoker types can
# name a program to run, a file to write, or a database to reach.

Run AFTER the deploy (it reaches production; it needs the operator-owned driver token
file). Two observations, both required:
1. the live /evaluate, driven by the synthetic gold personas, returns documentation
   AVAILABLE with "surat penjaminan" on an E33F candidate and UNKNOWN on an E31B one
   (`documentation_live_probe`);
2. the public Visa Oracle page answers HTTP 200.
The offline sibling `observe_visa_engine_documentation_catalog.py` proves the catalogue
before the deploy; the headless browser replay of the rendered checklist stays a
separate prove-live step.
Exit 0 only if both hold.
"""

# bites-observable — no arguments; one literal module, one literal URL.

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "apps" / "backend-rag"
PROBE_MODULE = "backend.scripts.visa_engine.documentation_live_probe"
PAGE_URL = "https://balizero.com/visa-oracle"


def _backend_python() -> str:
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.is_file() else sys.executable


def page_status() -> int:
    try:
        with urllib.request.urlopen(PAGE_URL, timeout=30) as response:  # noqa: S310 - literal https URL
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (urllib.error.URLError, TimeoutError):
        return 0


def main() -> int:
    result = subprocess.run(
        [_backend_python(), "-m", PROBE_MODULE],
        cwd=BACKEND_DIR,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
        check=False,
        capture_output=True,
        text=True,
    )
    status = page_status()
    if result.returncode != 0 or status != 200:
        print(
            "observe_visa_engine_documentation_catalog_live: FAILED "
            f"(probe exit {result.returncode}, page HTTP {status})\n{result.stdout[-1000:]}"
        )
        return result.returncode or 1
    print("observe_visa_engine_documentation_catalog_live: E33F AVAILABLE, E31B UNKNOWN, page HTTP 200")
    return 0


if __name__ == "__main__":
    sys.exit(main())
