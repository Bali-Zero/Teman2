#!/usr/bin/env python3
"""Guilt + innocence for orchestrate_gate.py's dispatch detector.

Why this file exists: the gate was measured on 2026-08-12 against live M5
transcripts and 4 of its 5 keywords scored ZERO occurrences ever — they named
`Task`/`TaskCreate`, tools the harness had replaced with `Agent`. The single
surviving token, `"subagent_type"`, is an OPTIONAL parameter, so a perfectly
legal dispatch that omits it read as "no dispatch at all". A gate that keeps
blocking after you have done the thing it asked for is worse than no gate: it
teaches you to set its kill switch, which is exactly what had happened
(`ORCHESTRATE_GATE_OFF=1` sat in settings.json).

The detector is therefore pinned by BEHAVIOUR — exit codes out of the real
hook against synthetic transcripts — not by reading its keyword list. Reading
the list would only confirm we wrote down what we wrote down.

Run directly (`python3 test_orchestrate_gate_vocab.py`) or under pytest.
"""
import os
import json
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).resolve().parent / "orchestrate_gate.py"
BIG = 900  # > HARD_BLOCK_THRESHOLD (800)

# A line that makes a transcript look like a transcript. Without at least one
# of these the gate refuses to convict (cannot-verify is not a verdict).
SHAPE = '{"type":"tool_use","role":"assistant","filler":"x"}'


def _transcript(body_lines, shape=True, total=BIG):
    """Build a transcript whose LAST lines are `body_lines`."""
    pad = [SHAPE if shape else '{"unrecognized":"format"}'] * max(0, total - len(body_lines))
    return "\n".join(pad + list(body_lines)) + "\n"


def run_gate(text, tool="Bash", env_extra=None):
    """Invoke the real hook; return its exit code."""
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
        fh.write(text)
        path = fh.name
    try:
        env = dict(os.environ)
        env.pop("ORCHESTRATE_GATE_OFF", None)  # the live machine sets it; tests must not inherit
        env.update(env_extra or {})
        payload = json.dumps({"tool_name": tool, "transcript_path": path,
                              "tool_input": {"command": "ls"}})
        p = subprocess.run([sys.executable, str(HOOK)], input=payload,
                           capture_output=True, text=True, env=env)
        return p.returncode
    finally:
        os.unlink(path)


# ── guilt ────────────────────────────────────────────────────────────────────

def test_guilt_no_dispatch_blocks():
    assert run_gate(_transcript([SHAPE])) == 2


def test_guilt_dispatch_older_than_the_window_still_blocks():
    """A dispatch 400 lines ago does not license the next 400 lines of direct work."""
    old = ['{"name":"Agent","input":{"subagent_type":"Explore"}}']
    text = _transcript(old + [SHAPE] * 400)
    assert run_gate(text) == 2


# ── innocence: the vocabulary the harness actually emits ─────────────────────

def test_innocence_live_agent_tool_is_recognized():
    """THE regression pin: `"name":"Agent"` is what a real dispatch writes."""
    assert run_gate(_transcript(['{"name":"Agent","input":{"description":"x"}}'])) == 0


def test_innocence_agent_without_subagent_type_is_recognized():
    """The sharp one. `subagent_type` is optional — omitting it defaults to
    general-purpose. The old detector saw nothing here and kept blocking."""
    text = _transcript(['{"type":"tool_use","name":"Agent","input":{"prompt":"go"}}'])
    assert run_gate(text) == 0


def test_innocence_json_spacing_does_not_matter():
    assert run_gate(_transcript(['{"name": "Agent", "input": {}}'])) == 0


def test_innocence_legacy_task_vocabulary_still_counts():
    """Old transcripts must not suddenly start blocking."""
    assert run_gate(_transcript(['{"name": "Task", "input": {}}'])) == 0
    assert run_gate(_transcript(['{"name":"TaskCreate"}'])) == 0


def test_innocence_sidechain_marker_counts():
    """The harness's own record that a subagent turn happened."""
    assert run_gate(_transcript(['{"isSidechain":true,"role":"assistant"}'])) == 0


# ── innocence: the gate must stay out of the way elsewhere ───────────────────

def test_innocence_short_session_never_blocks():
    assert run_gate(_transcript([SHAPE], total=100)) == 0


def test_innocence_non_gated_tool_passes():
    assert run_gate(_transcript([SHAPE]), tool="Read") == 0


def test_innocence_kill_switch_passes():
    assert run_gate(_transcript([SHAPE]), env_extra={"ORCHESTRATE_GATE_OFF": "1"}) == 0


def test_unreadable_transcript_shape_does_not_convict():
    """If the transcript stops looking like one, "zero dispatch" is unproven.
    Blocking here would take the whole machine down on a format change.

    Note the body line must be unrecognizable TOO: the first draft of this test
    padded with junk but ended with `SHAPE`, so the "unreadable" transcript was
    readable and the case proved nothing.
    """
    alien = '{"unrecognized":"format"}'
    assert run_gate(_transcript([alien], shape=False)) == 0


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   — {name}")
            except AssertionError:
                print(f"  FAIL — {name}")
                failed += 1
    print()
    print("PASS — orchestrate_gate dispatch detector" if not failed else f"FAIL ({failed})")
    sys.exit(1 if failed else 0)
