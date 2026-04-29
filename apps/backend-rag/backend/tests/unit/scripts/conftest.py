"""conftest for scripts/* tests.

Some scripts under test live at the *repo root* `/scripts/` (cron utilities
shared across apps), while pytest is invoked from `apps/backend-rag/` with
`PYTHONPATH=.`. The repo-root `scripts/` is therefore not on sys.path, and
imports like `from scripts.drive_token_watchdog import ...` fail at
collection time with `ModuleNotFoundError`.

This conftest prepends the repo root to sys.path so test modules in this
directory can import either:
    - `scripts.<name>`   when the script lives at the repo root
    - `scripts.<name>`   when the script lives at apps/backend-rag/scripts/

Python's import system resolves whichever it finds first; for our purposes
the repo-root `scripts/` (containing drive_token_watchdog.py) is added once.

Other tests in `apps/backend-rag/backend/tests/unit/scripts/` already work
because their target scripts live at `apps/backend-rag/scripts/<name>.py`,
which is resolvable from the existing `PYTHONPATH=.` (PYTHONPATH ==
apps/backend-rag/, so `scripts/` package = apps/backend-rag/scripts/).
Adding the repo root doesn't shadow them — Python finds the closer one
first via sys.path order.

Reference: P1-11 (Drive OAuth tiers, PR #343 follow-up).
"""

from __future__ import annotations

import os
import sys

# This file:    apps/backend-rag/backend/tests/unit/scripts/conftest.py
# Repo root:    apps/backend-rag/backend/tests/unit/scripts/../../../../../..
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "..", "..", ".."))

if _REPO_ROOT not in sys.path:
    # Append, not prepend: prefer the closer apps/backend-rag/scripts/ when
    # both exist (existing behavior preserved). Repo-root scripts/ is the
    # fallback for cron utilities like drive_token_watchdog.py.
    sys.path.append(_REPO_ROOT)
