#!/usr/bin/env python3
"""Latency bound for gate_coverage.record() (K1 contract: "<5ms, never slows
the caller"). Refuter finding 2026-08-27 (PR #5045, Kimi K3 round 1): the
contract was asserted in the docstring and enforced nowhere. This is a
generous, non-flaky bound — 20ms/call average over 200 calls to a real
tempdir-backed file, not a tight timing assertion — so normal CI/disk
variance does not make it flap; its job is to catch a REGRESSION (e.g. an
accidental network call, a blocking lock, an O(n) scan of prior lines)
orders of magnitude past the design target, not to prove sub-5ms on every
runner.

Run: python3 scripts/tests/test_gate_coverage_record_latency.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "infra" / "claude-hooks" / "gate_coverage.py"

N_CALLS = 200
GENEROUS_AVG_MS = 20  # design target is <5ms; this bound only catches gross regressions


def _load_gate_coverage(state_dir: pathlib.Path):
    spec = importlib.util.spec_from_file_location("gate_coverage_uut", str(MODULE_PATH))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.STATE_DIR = str(state_dir)  # redirect off the real ~/.claude/state/
    return mod


def main() -> int:
    fails = 0

    with tempfile.TemporaryDirectory() as td:
        state_dir = pathlib.Path(td) / "gate-coverage"
        gc = _load_gate_coverage(state_dir)

        payload = {"session_id": "sess-latency-dddd", "tool_name": "Bash"}

        start = time.monotonic()
        for i in range(N_CALLS):
            gc.record("worktree_isolation", "allow" if i % 2 == 0 else "deny", payload)
        elapsed_ms = (time.monotonic() - start) * 1000

        avg_ms = elapsed_ms / N_CALLS
        ok = avg_ms < GENEROUS_AVG_MS
        if not ok:
            fails += 1
        print(f"  [{'OK ' if ok else 'FAIL'}] {N_CALLS} record() calls: {elapsed_ms:.1f}ms total, "
              f"{avg_ms:.3f}ms avg (bound: <{GENEROUS_AVG_MS}ms avg)")

        # All N_CALLS lines actually landed — the fast path did not silently drop writes.
        written = (state_dir / "sess-latency-dddd.jsonl").read_text().strip().splitlines()
        ok = len(written) == N_CALLS
        if not ok:
            fails += 1
        print(f"  [{'OK ' if ok else 'FAIL'}] {len(written)} of {N_CALLS} lines written (no silent drops)")

    print("=== ALL GREEN ===" if not fails else f"=== {fails} FAIL ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
