#!/usr/bin/env python3
"""Guilt/innocence trap-table for gate_coverage_report.py (K1 reporting half).

Guilt: a fixture transcript with 5 Bash tool_use events + a decisions file
with only 2 recorded decisions must report "decided 2 of 5". Innocence: the
same transcript with 5 recorded decisions must report "decided 5 of 5". Uses
`worktree_isolation`'s real matcher ({"Bash"}) for a clean 1:1 test — every
Bash call in the fixture is eligible for exactly that one gate. Also proves
the hook exits 0 (never blocks Stop) on garbage/empty stdin.

Run: python3 scripts/tests/test_gate_coverage_report.py  (exit 0 = all green)
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "infra" / "claude-hooks" / "gate_coverage_report.py"


def _write_transcript(path: pathlib.Path, n_bash_calls: int) -> None:
    lines = []
    for i in range(n_bash_calls):
        evt = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": f"tu_{i}", "name": "Bash", "input": {"command": f"echo {i}"}}
                ],
            },
        }
        lines.append(json.dumps(evt))
    path.write_text("\n".join(lines) + "\n")


def _write_decisions(state_dir: pathlib.Path, session_id: str, hook_name: str, n_decisions: int) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"ts": "2026-08-27T00:00:00Z", "session_id": session_id, "hook": hook_name, "decision": "allow"})
        for _ in range(n_decisions)
    ]
    text = "\n".join(lines) + ("\n" if lines else "")
    (state_dir / f"{session_id}.jsonl").write_text(text)


def _run_hook(env_home: pathlib.Path, stdin_payload) -> tuple:
    env = dict(os.environ)
    env["HOME"] = str(env_home)
    stdin = json.dumps(stdin_payload) if isinstance(stdin_payload, dict) else (stdin_payload or "")
    r = subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, env=env, timeout=15)
    return r.stdout, r.returncode


def main() -> int:
    fails = 0

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        home = tmp / "home"
        state_dir = home / ".claude" / "state" / "gate-coverage"
        state_dir.mkdir(parents=True)
        transcript = tmp / "fixture.jsonl"
        _write_transcript(transcript, 5)

        # --- GUILT: 2 of 5 ---
        session_a = "sess-guilt-aaaa"
        _write_decisions(state_dir, session_a, "worktree_isolation", 2)
        out, rc = _run_hook(home, {"session_id": session_a, "transcript_path": str(transcript), "hook_event_name": "Stop"})
        ok = rc == 0 and "worktree_isolation: decided 2 of 5 tool calls" in out
        if not ok:
            fails += 1
        print(f"  [{'OK ' if ok else 'FAIL'}] guilt (2 recorded / 5 eligible): rc={rc} out={out.strip()!r}")

        # --- INNOCENCE: 5 of 5 ---
        session_b = "sess-innoc-bbbb"
        _write_decisions(state_dir, session_b, "worktree_isolation", 5)
        out, rc = _run_hook(home, {"session_id": session_b, "transcript_path": str(transcript), "hook_event_name": "Stop"})
        ok = rc == 0 and "worktree_isolation: decided 5 of 5 tool calls" in out
        if not ok:
            fails += 1
        print(f"  [{'OK ' if ok else 'FAIL'}] innocence (5 recorded / 5 eligible): rc={rc} out={out.strip()!r}")

        # --- zero decisions at all -> 0 of 5 (the pure fail-open case) ---
        session_c = "sess-zero-cccc"
        out, rc = _run_hook(home, {"session_id": session_c, "transcript_path": str(transcript), "hook_event_name": "Stop"})
        ok = rc == 0 and "worktree_isolation: decided 0 of 5 tool calls" in out
        if not ok:
            fails += 1
        print(f"  [{'OK ' if ok else 'FAIL'}] pure fail-open (0 recorded / 5 eligible): rc={rc} out={out.strip()!r}")

        # --- garbage / empty stdin never blocks Stop ---
        for label, garbage in [("garbage json", "not json at all {{{"), ("empty stdin", "")]:
            out, rc = _run_hook(home, garbage)
            ok = rc == 0
            if not ok:
                fails += 1
            print(f"  [{'OK ' if ok else 'FAIL'}] {label}: rc={rc} (expect 0)")

    print("=== ALL GREEN ===" if not fails else f"=== {fails} FAIL ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
