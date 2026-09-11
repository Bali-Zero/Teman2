#!/usr/bin/env python3
"""Every hook this PR touches must exit 0 on a garbage/unparseable stdin
payload — a fail-open contract check across all 4 gates + the 2 new K1/K3
hooks in one place (item 6 of the K1/K3/X1/F7 mandate). A gate that throws
on bad input instead of degrading to exit 0 becomes the SIXTH single point
of failure this PR exists to make visible in the other five.

Also the regression test for a real pre-existing bug this PR fixes in 3 of
the 4 gates while it was already touching them for gate_coverage
instrumentation: `payload.get(...)` on a JSON payload that parses but is NOT
a dict (`null`, `42`, `[]`, a bare string) raised an uncaught AttributeError
in host_boundary.py / worktree_isolation.py / orchestrate_gate.py.
model_routing_gate.py already carried the `isinstance(payload, dict)` guard
(added 2026-08-22 for the exact same class of crash) — the other three did
not, until this PR.

Run: python3 scripts/tests/test_hooks_fail_open_on_garbage_payload.py
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "infra" / "claude-hooks"

HOOKS = [
    "host_boundary.py",
    "worktree_isolation.py",
    "orchestrate_gate.py",
    "model_routing_gate.py",
    "gate_coverage_report.py",
    "session_budget.py",
]

GARBAGE_INPUTS = [
    "",                     # empty stdin
    "not json at all {{{",  # unparseable
    "null",                 # valid JSON, not a dict
    "[]",                   # valid JSON, not a dict
    '"just a string"',      # valid JSON, not a dict
    "42",                   # valid JSON, not a dict
]


def main() -> int:
    fails = 0
    with tempfile.TemporaryDirectory() as td:
        home = pathlib.Path(td) / "home"
        home.mkdir()
        env = dict(os.environ)
        env["HOME"] = str(home)

        for hook in HOOKS:
            path = HOOKS_DIR / hook
            if not path.exists():
                fails += 1
                print(f"  [FAIL] {hook}: not found at {path}")
                continue
            for garbage in GARBAGE_INPUTS:
                try:
                    r = subprocess.run(
                        [sys.executable, str(path)], input=garbage,
                        capture_output=True, text=True, env=env, timeout=20,
                    )
                except subprocess.TimeoutExpired:
                    fails += 1
                    print(f"  [FAIL] {hook} on {garbage[:24]!r}: TIMED OUT (should fail-open fast)")
                    continue
                ok = r.returncode == 0
                if not ok:
                    fails += 1
                    detail = f" stderr={r.stderr.strip()[:200]!r}"
                else:
                    detail = ""
                print(f"  [{'OK ' if ok else 'FAIL'}] {hook} on {garbage[:24]!r}: rc={r.returncode} (expect 0){detail}")

    print("=== ALL GREEN ===" if not fails else f"=== {fails} FAIL ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
