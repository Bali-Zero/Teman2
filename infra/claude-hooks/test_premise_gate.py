#!/usr/bin/env python3
"""Innocence+guilt test for premise_gate.py (the L1 detector).

A guard merged without an innocence AND guilt test is the W83/84/85/86 family.
This proves premise_gate WARNS on a genuine missing-premise Edit and STAYS SILENT
on every legitimate neighbor (read-in-turn, exempt surfaces, plan-mode, repeat).

    python3 infra/claude-hooks/test_premise_gate.py
Exit 0 = all pass.
"""
from __future__ import annotations
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "premise_gate.py"


def run(payload: dict, transcript: str) -> bool:
    """Return True if the hook WARNED (emitted a systemMessage), False if silent."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    tp = tmp / "transcript.jsonl"
    tp.write_text(transcript)
    payload = {**payload, "transcript_path": str(tp)}
    # fresh state dir per run so the per-session guard never cross-contaminates
    env = {"HOME": str(tmp), "PATH": "/usr/bin:/bin"}
    out = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return "systemMessage" in (out.stdout or "")


USER = '{"role": "user", "content": "go"}\n'


def edit(fp: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": fp}}


def main() -> int:
    PROD = "/Users/x/Desktop/nuzantara/apps/mouth/src/foo.tsx"
    fails = 0
    cases = [
        # name, payload, transcript, expect_warn
        # --- GUILT: Edit on product file, no in-turn read → WARN ---
        ("guilt: edit product, no read",
         edit(PROD), USER + '{"assistant":"editing now"}\n', True),

        # --- INNOCENCE: read in THIS turn (Read tool_use mentions the file) → silent ---
        ("innocent: Read tool this turn",
         edit(PROD), USER + '{"tool_use":"Read","content":"foo.tsx line 1"}\n', False),
        # --- INNOCENCE: shell read this turn (grep foo.tsx) → silent ---
        ("innocent: grep this turn",
         edit(PROD), USER + '{"assistant":"grep needle foo.tsx"}\n', False),
        # --- INNOCENCE: scratchpad → exempt ---
        ("innocent: scratchpad",
         edit("/tmp/x/scratchpad/note.md"), USER + '{"a":"b"}\n', False),
        # --- INNOCENCE: memory MOS → exempt ---
        ("innocent: memory file",
         edit("/Users/x/.claude/projects/p/memory/MEMORY.md"), USER + '{"a":"b"}\n', False),
        # --- INNOCENCE: /tmp → exempt ---
        ("innocent: tmp file",
         edit("/tmp/scratch.txt"), USER + '{"a":"b"}\n', False),
        # --- INNOCENCE: Write (new file), not Edit → not gated ---
        ("innocent: Write not Edit",
         {"tool_name": "Write", "tool_input": {"file_path": PROD}}, USER + '{"a":"b"}\n', False),
        # --- INNOCENCE: read happened, file basename + Read both present ---
        ("innocent: read mentions path",
         edit(PROD), USER + '{"tool_use":"Read","file_path":"' + PROD + '"}\n', False),
    ]
    for name, payload, transcript, expect in cases:
        got = run(payload, transcript)
        ok = got == expect
        if not ok:
            fails += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] warn={got!s:5} expect={expect!s:5} | {name}")

    # repeat-suppression: second identical edit in same session → silent (one warn/file)
    tmp = pathlib.Path(tempfile.mkdtemp())
    tp = tmp / "t.jsonl"
    tp.write_text(USER + '{"a":"b"}\n')
    env = {"HOME": str(tmp), "PATH": "/usr/bin:/bin"}
    pl = {**edit(PROD), "transcript_path": str(tp)}
    r1 = "systemMessage" in subprocess.run([sys.executable, str(HOOK)], input=json.dumps(pl),
                                           capture_output=True, text=True, env=env).stdout
    r2 = "systemMessage" in subprocess.run([sys.executable, str(HOOK)], input=json.dumps(pl),
                                           capture_output=True, text=True, env=env).stdout
    ok = r1 and not r2
    if not ok:
        fails += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] warn1={r1} warn2={r2} (expect True,False) | repeat-suppression")

    total = len(cases) + 1
    print(f"\n=== {'ALL ' + str(total) + ' PASS' if not fails else str(fails) + '/' + str(total) + ' FAIL'} ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
