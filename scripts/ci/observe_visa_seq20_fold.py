#!/usr/bin/env python3
"""observe_visa_seq20_fold.py — bites: observation for the seq-20 fold lane.

# bites-observable — this script takes NO arguments: every path and command
# below is a literal in this file, so nothing an invoker types can name a
# program to run, a file to write, or a database to reach (the exact bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets for a script
# reachable from a pack.yml `observe:` line).

Runs the two consumers named in this lane's `Bites:` line, in order, and
fails loud on the first red one:

1. ``apps/backend-rag``'s ``test_seq20_pack.py`` — the fold-integrity /
   identity / rule-set-delta / per-edit guilt+innocence / gold-coverage gate
   suite for ``rulepack-prod-020.source.json``.
2. ``apps/mouth``'s ``engine-adapter.test.ts`` — the cross-app consumer that
   reads the HIGHEST-sequence ``rulepack-prod-*.source.json`` on disk
   (``latestProductionPackFile``) and asserts every HUMAN_REVIEW
   ``reason_code`` the pack can emit is either mapped in
   ``REVIEW_REASON_COPY`` or named in the known-gap list — AND that no entry
   in that gap list names a code the pack stopped emitting. seq-20 retires
   ``review.e33g.income-evidence``, so this is the concrete proof that a
   retirement inside the Python package that authors the pack is observed by
   the TypeScript app that renders its reason codes: without the same-PR
   update to that gap list, this second consumer goes red.

Exit 0 only if both are green.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"

#: Production trust store PUBLIC key only (no secret) — the same constant
#: `test_seq20_pack.py`'s own `PROD_TRUST_STORE_JSON` pins, needed because
#: `fold_pack_seq20.fold()` verifies the seq-19 anchor's signature before
#: doing anything else.
_TRUST_STORE_JSON = (
    '[{"kid": "prod-2026-07-1", "public_key": '
    '"gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA", '  # pragma: allowlist secret
    '"environment": "PRODUCTION", "valid_from": "2026-07-19T00:00:00Z", '
    '"valid_to": null, "revoked_at": null}]'
)


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> int:
    print(f"observe_visa_seq20_fold: running {' '.join(cmd)} (cwd={cwd})")
    return subprocess.run(cmd, cwd=cwd, env=env, check=False).returncode


def _backend_rag_python() -> str:
    """Prefer the project's own venv (CLAUDE.md: `apps/backend-rag/.venv/`) —
    fall back to whatever interpreter is running this script if the venv is
    absent (e.g. a CI image that installs deps onto the system interpreter
    directly rather than into a checked-out venv)."""
    venv_python = BACKEND_RAG_DIR / ".venv" / "bin" / "python3"
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable


def main() -> int:
    python_env = dict(os.environ)
    python_env["PYTHONPATH"] = "."
    python_env["VISA_ENGINE_TRUST_STORE_KEYS_JSON"] = _TRUST_STORE_JSON
    rc = _run(
        [
            _backend_rag_python(),
            "-m",
            "pytest",
            "backend/tests/services/visa_engine/test_seq20_pack.py",
        ],
        cwd=BACKEND_RAG_DIR,
        env=python_env,
    )
    if rc != 0:
        print("observe_visa_seq20_fold: test_seq20_pack.py FAILED")
        return rc

    node_env = dict(os.environ)
    rc = _run(
        [
            "npx",
            "vitest",
            "run",
            "src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts",
        ],
        cwd=MOUTH_DIR,
        env=node_env,
    )
    if rc != 0:
        print("observe_visa_seq20_fold: engine-adapter.test.ts FAILED")
        return rc

    print("observe_visa_seq20_fold: both consumers green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
