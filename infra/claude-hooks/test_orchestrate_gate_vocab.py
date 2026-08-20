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


def run_gate(text, tool="Bash", env_extra=None, agent_id=None, transcript_path=None):
    """Invoke the real hook; return its exit code.

    `transcript_path`, when given, is used verbatim as the payload's
    transcript_path INSTEAD of writing `text` to a real temp file — needed to
    test the subagents/-path exemption, which must fire before the hook ever
    opens the file (a subagent's transcript may not be flushed yet)."""
    path = transcript_path
    owns_file = False
    if path is None:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            fh.write(text)
            path = fh.name
        owns_file = True
    try:
        env = dict(os.environ)
        env.pop("ORCHESTRATE_GATE_OFF", None)  # the live machine sets it; tests must not inherit
        env.update(env_extra or {})
        payload_dict = {"tool_name": tool, "transcript_path": path,
                         "tool_input": {"command": "ls"}}
        if agent_id is not None:
            payload_dict["agent_id"] = agent_id
        payload = json.dumps(payload_dict)
        p = subprocess.run([sys.executable, str(HOOK)], input=payload,
                           capture_output=True, text=True, env=env)
        return p.returncode
    finally:
        if owns_file:
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


# ── subagent exemption (2026-08-21) ───────────────────────────────────────────
# A subagent has no Agent tool of its own — "zero dispatch in the last N
# lines" is a structural impossibility for it, not a signal to heed. Two
# independent markers exempt it (see the hook's module docstring for the
# evidence): `agent_id` (documented) and a `subagents/` path component in
# `transcript_path` (empirically verified, undocumented fallback).

def test_innocence_agent_id_exempts_a_quiet_subagent():
    """The documented marker: `agent_id` present ⇒ inside a subagent call.
    A huge, dispatch-free transcript must NOT block when this is set."""
    assert run_gate(_transcript([SHAPE]), agent_id="alane-ship-65c1db88930053a2") == 0


def test_innocence_subagents_path_exempts_even_an_unwritten_transcript():
    """The path-shaped marker must short-circuit BEFORE the file is ever
    opened — a subagent's dedicated transcript may not be flushed yet. A
    transcript_path that does not exist on disk must still exempt."""
    fake = "/tmp/does-not-exist-on-purpose/subagents/agent-afoo-deadbeef.jsonl"
    assert run_gate(None, transcript_path=fake) == 0


def test_guilt_main_session_with_zero_dispatch_still_blocks():
    """The guard must keep biting where it should: neither `agent_id` nor a
    `subagents/` path is present ⇒ ordinary main-session behaviour, unchanged."""
    assert run_gate(_transcript([SHAPE])) == 2


def test_guilt_agent_id_alone_does_not_forge_a_subagents_path_bypass():
    """Sanity: the exemption is not a blanket 'any extra field allows' —
    it fires ONLY on the two named markers, checked directly against the
    payload dict, never against transcript content."""
    text = _transcript([SHAPE])
    assert run_gate(text, agent_id="") == 2  # falsy agent_id must NOT exempt
    assert run_gate(text, agent_id=None) == 2  # absent agent_id (default) must NOT exempt


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
