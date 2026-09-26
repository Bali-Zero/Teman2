#!/usr/bin/env python3
"""Guilt+innocence: premise_gate.py, stadio_zero_nudge.py and dispatch_nudge.py
must reach Claude's own context (hookSpecificOutput.additionalContext), not
just the operator's terminal (systemMessage alone) — PENDING-ARMS L1087,
same fix orchestrate_gate.py already carries.

Run directly (`python3 test_nudge_hooks_additional_context.py`) or under pytest.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent
CASES = [
    (HERE / "premise_gate.py", "PreToolUse",
     {"tool_name": "Edit", "tool_input": {"file_path": "/repo/backend/app.py"}},
     '{"role":"user","content":"go"}\n' + '{"filler":"x"}\n' * 20),
    (HERE / "stadio_zero_nudge.py", "PreToolUse",
     {"tool_name": "Edit", "tool_input": {"file_path": "/repo/backend/app.py"}},
     '{"filler":"x"}\n' * 20),
    (HERE / "dispatch_nudge.py", "UserPromptSubmit", {}, '{"filler":"x"}\n' * 600),
]


def _run(hook: pathlib.Path, payload: dict, home: pathlib.Path) -> tuple[int, str]:
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    out = subprocess.run(
        [sys.executable, str(hook)], input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return out.returncode, out.stdout


@pytest.mark.parametrize(
    "hook,event,extra_payload,transcript_text", CASES, ids=[c[0].stem for c in CASES]
)
def test_warn_path_carries_additional_context(hook, event, extra_payload, transcript_text):
    home = pathlib.Path(tempfile.mkdtemp())
    transcript = home / "t.jsonl"
    transcript.write_text(transcript_text)
    payload = {**extra_payload, "transcript_path": str(transcript)}
    rc, out = _run(hook, payload, home)
    assert rc == 0
    doc = json.loads(out) if out.strip() else None
    assert doc is not None, f"{hook.name}: expected a warning, got {out!r}"
    hso = doc.get("hookSpecificOutput", {})
    assert hso.get("hookEventName") == event
    assert hso.get("additionalContext"), f"{hook.name}: additionalContext must carry the reminder"
    assert hso["additionalContext"] == doc["systemMessage"]


def test_premise_gate_silent_path_unaffected():
    home = pathlib.Path(tempfile.mkdtemp())
    transcript = home / "t.jsonl"
    transcript.write_text(
        '{"role":"user","content":"go"}\n'
        '{"type":"tool_use","name":"Read","input":{"file_path":"/repo/backend/app.py"}}\n'
    )
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/repo/backend/app.py"},
        "transcript_path": str(transcript),
    }
    rc, out = _run(HERE / "premise_gate.py", payload, home)
    assert (rc, out) == (0, "")


def test_dispatch_nudge_silent_path_unaffected():
    home = pathlib.Path(tempfile.mkdtemp())
    transcript = home / "t.jsonl"
    transcript.write_text('{"filler":"x"}\n' * 5)
    payload = {"transcript_path": str(transcript)}
    rc, out = _run(HERE / "dispatch_nudge.py", payload, home)
    assert (rc, out) == (0, "")


def main() -> int:
    failed = 0
    for case in CASES:
        try:
            test_warn_path_carries_additional_context(*case)
            print(f"  ok   — warn path ({case[0].name})")
        except AssertionError as e:
            print(f"  FAIL — warn path ({case[0].name}): {e}")
            failed += 1
    for name, fn in (("premise_gate silent", test_premise_gate_silent_path_unaffected),
                      ("dispatch_nudge silent", test_dispatch_nudge_silent_path_unaffected)):
        try:
            fn()
            print(f"  ok   — {name}")
        except AssertionError as e:
            print(f"  FAIL — {name}: {e}")
            failed += 1
    print()
    print("PASS — nudge hooks additionalContext" if not failed else f"FAIL ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
