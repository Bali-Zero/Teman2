#!/usr/bin/env python3
"""Guilt + innocence + cannot-verify for orchestrate_gate.py's disarm notice.

Why this file exists (lesson `lesson_a_disarmed_gate_is_mute_2026_08_12`): on
2026-08-12 a session ran ~6400 transcript lines with ZERO subagent dispatch
and was never blocked once, because ORCHESTRATE_GATE_OFF=1 was inherited from
the launching shell — written in no file, unrecoverable at the source. The
gate's own kill-switch check (`if ...OFF == "1": sys.exit(0)`) produced no
output whatsoever: cicatrix family #2 (esiste != armato) one level up — a
disarmed guard that leaves no trace of being disarmed.

This corpus pins the cure: when disarmed, the gate now emits ONE notice per
session naming the real transcript-line-count and dispatch-count and stating
whether it WOULD have blocked — without ever actually blocking (kill switch
stays fully functional). The notice is delivered on two channels: `systemMessage`
(user-visible only, per the Claude Code hooks doc) and
`hookSpecificOutput.additionalContext` with `permissionDecision: "allow"`
(reaches Claude's own context — verified against the current hooks doc,
2026-08-12; this is the channel that makes the notice something the SESSION
itself can act on, not just the terminal).

Tests use real `assert` (pytest-collectible AND directly runnable) — a
corpus that records failures without raising would pass under pytest no
matter what the hook does, which is its own instance of this file's disease.

Run directly (`python3 test_orchestrate_gate_disarm_notice.py`) or under pytest.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).resolve().parent / "orchestrate_gate.py"
BIG = 900  # > HARD_BLOCK_THRESHOLD (800)
SHAPE = '{"type":"tool_use","role":"assistant","filler":"x"}'
ALIEN = '{"unrecognized":"format"}'  # matches none of TRANSCRIPT_SHAPE_MARKERS
AGENT_DISPATCH = '{"type":"tool_use","name":"Agent","input":{"description":"x"}}'


def _padded(body_lines, shape_line=SHAPE, total=BIG):
    """Build transcript text whose LAST lines are `body_lines`, padded to `total`."""
    pad = [shape_line] * max(0, total - len(body_lines))
    return "\n".join(pad + list(body_lines)) + "\n"


def run_gate(transcript_text=None, tool="Bash", disarmed=False, home=None,
             transcript_name="transcript.jsonl", omit_transcript_path=False,
             transcript_path_override=None):
    """Invoke the real hook. Returns (returncode, stdout, stderr).

    `home` lets a caller reuse the SAME HOME (and therefore the SAME
    ~/.agent/decisions/state marker dir) across two calls, to test the
    once-per-session cap. A fresh tmp HOME per call otherwise — the marker
    file must never leak between unrelated test cases.
    """
    tmp = pathlib.Path(home) if home else pathlib.Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    payload = {"tool_name": tool, "tool_input": {"command": "ls"}}
    if transcript_path_override is not None:
        payload["transcript_path"] = transcript_path_override
    elif not omit_transcript_path:
        tp = tmp / transcript_name
        if transcript_text is not None:
            tp.write_text(transcript_text)
        payload["transcript_path"] = str(tp)
    # Minimal env, NOT inherited from os.environ — the live machine that runs
    # this suite may itself have ORCHESTRATE_GATE_OFF=1 set with no file
    # behind it (the exact disease this file is about); inheriting os.environ
    # would silently contaminate every "armed" case below.
    env = {"HOME": str(tmp), "PATH": "/usr/bin:/bin"}
    if disarmed:
        env["ORCHESTRATE_GATE_OFF"] = "1"
    out = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return out.returncode, out.stdout, out.stderr


def _notice_json(stdout):
    """Parse the hook's stdout as the notice JSON, or None if stdout is empty."""
    if not stdout.strip():
        return None
    return json.loads(stdout)


# ── guilt: disarmed + transcript that WOULD block → notice says so, exit 0 ──

def test_guilt_disarmed_would_block_notifies_and_does_not_block():
    text = _padded([SHAPE])  # 900 lines, no dispatch anywhere → would_block True
    rc, out, err = run_gate(text, disarmed=True)
    assert rc == 0, f"disarmed gate must never block, got rc={rc}"
    doc = _notice_json(out)
    assert doc is not None, f"expected a notice on stdout, got {out!r}"
    msg = doc.get("systemMessage", "")
    hso = doc.get("hookSpecificOutput", {})
    ctx = hso.get("additionalContext", "")
    assert "900" in msg, f"must name the real transcript line count: {msg!r}"
    assert " 0 subagent dispatch" in msg, f"must name the real dispatch count: {msg!r}"
    assert "WOULD BE BLOCKING" in msg, f"must claim the correct verdict: {msg!r}"
    assert "WOULD BE BLOCKING" in ctx, "additionalContext must carry the same claim"
    assert hso.get("hookEventName") == "PreToolUse"
    assert hso.get("permissionDecision") == "allow", "never denies — kill switch stays functional"
    assert err == "", f"no block message on stderr while disarmed: {err!r}"


# ── innocence: disarmed but would NOT currently block — no false claim ──────

def test_innocence_disarmed_short_session_says_would_not_block():
    text = _padded([SHAPE], total=100)  # under HARD_BLOCK_THRESHOLD
    rc, out, _ = run_gate(text, disarmed=True)
    assert rc == 0
    doc = _notice_json(out)
    assert doc is not None, "disarm state itself is news even on a short session"
    msg = doc["systemMessage"]
    assert "WOULD BE BLOCKING" not in msg, f"must not claim it would block: {msg!r}"
    assert "would NOT be blocking" in msg, msg
    assert "100" in msg, f"must name the real total_lines: {msg!r}"


def test_innocence_disarmed_with_recent_dispatch_says_would_not_block():
    text = _padded([AGENT_DISPATCH])  # 900 lines, dispatch IS in the recent window
    rc, out, _ = run_gate(text, disarmed=True)
    assert rc == 0
    doc = _notice_json(out)
    assert doc is not None
    msg = doc["systemMessage"]
    assert "WOULD BE BLOCKING" not in msg, msg
    assert "0 subagent dispatch" not in msg, f"must name the nonzero dispatch count: {msg!r}"


# ── innocence: switch UNSET → byte-identical to pre-existing behaviour ──────

def test_innocence_armed_blocks_exactly_as_before_no_notice_fields():
    text = _padded([SHAPE])
    rc, out, err = run_gate(text, disarmed=False)
    assert rc == 2, f"armed gate must still hard-block, got rc={rc}"
    assert out == "", f"no JSON notice on the armed path — it never existed pre-fix: {out!r}"
    assert "BLOCKED" in err, err
    assert "disarmed" not in err.lower(), "armed-path message must not mention disarm vocabulary"


def test_innocence_armed_short_session_silent():
    text = _padded([SHAPE], total=100)
    rc, out, err = run_gate(text, disarmed=False)
    assert (rc, out, err) == (0, "", "")


def test_innocence_armed_with_dispatch_silent():
    text = _padded([AGENT_DISPATCH])
    rc, out, err = run_gate(text, disarmed=False)
    assert (rc, out, err) == (0, "", "")


def test_innocence_non_gated_tool_never_notifies_even_when_disarmed():
    text = _padded([SHAPE])
    rc, out, _ = run_gate(text, tool="Read", disarmed=True)
    assert rc == 0
    assert out == "", f"Read is not a gated tool — no notice expected: {out!r}"


# ── cannot-verify: never claim a count we don't have ────────────────────────

def test_cannot_verify_missing_transcript_path_disarmed_stays_silent():
    rc, out, _ = run_gate(disarmed=True, omit_transcript_path=True)
    assert rc == 0
    assert out == "", f"no transcript_path at all — nothing to notify about: {out!r}"


def test_cannot_verify_nonexistent_transcript_disarmed_stays_silent():
    tmp = tempfile.mkdtemp()
    rc, out, _ = run_gate(
        disarmed=True, home=tmp,
        transcript_path_override=str(pathlib.Path(tmp) / "does-not-exist.jsonl"),
    )
    assert rc == 0
    assert out == "", f"nonexistent transcript file — no fabricated count: {out!r}"


def test_cannot_verify_unrecognized_shape_disarmed_stays_silent():
    text = _padded([ALIEN], shape_line=ALIEN)  # nothing in it matches shape markers
    rc, out, _ = run_gate(text, disarmed=True)
    assert rc == 0
    assert out == "", f"unrecognized transcript shape — no fabricated count: {out!r}"


def test_cannot_verify_unrecognized_shape_armed_matches_pre_existing_behaviour():
    text = _padded([ALIEN], shape_line=ALIEN)
    rc, out, err = run_gate(text, disarmed=False)
    assert rc == 0, "must not convict on unproven evidence"
    assert "transcript format not recognized" in err, err


# ── do not spam: at most one notice per session ──────────────────────────────

def test_notice_fires_once_per_session_same_transcript():
    text = _padded([SHAPE])
    tmp = tempfile.mkdtemp()
    rc1, out1, _ = run_gate(text, disarmed=True, home=tmp, transcript_name="t.jsonl")
    rc2, out2, _ = run_gate(text, disarmed=True, home=tmp, transcript_name="t.jsonl")
    assert out1 != "", "first call on a disarmed session must notify"
    assert out2 == "", f"second call on the SAME transcript must be silent: {out2!r}"
    assert rc1 == 0 and rc2 == 0, "neither call ever blocks"


def test_notice_fires_again_for_a_different_session():
    text = _padded([SHAPE])
    tmp = tempfile.mkdtemp()
    _, out1, _ = run_gate(text, disarmed=True, home=tmp, transcript_name="session-a.jsonl")
    _, out2, _ = run_gate(text, disarmed=True, home=tmp, transcript_name="session-b.jsonl")
    assert out1 != "" and out2 != "", "each distinct transcript gets its own one-time notice"


def main():
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   — {name}")
            except AssertionError as e:
                print(f"  FAIL — {name}: {e}")
                failed += 1
    print()
    print("PASS — orchestrate_gate disarm notice" if not failed else f"FAIL ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
