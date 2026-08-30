#!/usr/bin/env python3
"""PreToolUse hard-gate — Gap 1 fix (2026-05-25).

Blocca Bash|Edit|Write se:
  - transcript >800 lines AND
  - zero subagent dispatch in last 300 lines

Exit 2 + stderr message → Claude rilegge il blocco e riconsidera.
Override: env ORCHESTRATE_GATE_OFF=1.

Upgrade di dispatch_nudge.py (soft warn UserPromptSubmit) a hard-block PreToolUse.
Cicatrix family: T1.1 dispatch reminder, W33 kill-switch pattern.

DISARM AUDIBILITY (2026-08-12, cicatrix family #2 one level up — lesson
`lesson_a_disarmed_gate_is_mute_2026_08_12`): a session ran ~6400 transcript
lines with zero subagent dispatch and was never blocked once, because
ORCHESTRATE_GATE_OFF=1 was inherited from the launching shell's environment —
written in NO file (not settings.json, not any rc file), unrecoverable at the
source (macOS won't expose another process's env). The kill switch itself is
legitimate (W33 escape-hatch pattern) and stays fully functional — this file
never blocks while disarmed. What changed is that "disarmed" now SAYS SO,
once per session, on the first gated tool call, stating whether the gate
WOULD have blocked right now (line count + dispatch count) — "gate off" alone
is noise, "gate off, and it would be blocking now at 6400 lines / 0 dispatch"
is signal. Channel picked by measurement (WebFetch of the current Claude Code
hooks doc, 2026-08-12): PreToolUse `systemMessage` reaches the USER ONLY, not
Claude's context — it is what dispatch_nudge/premise_gate/stadio_zero_nudge
already use, so it stays here as a visible-to-operator courtesy, but the
signal that actually reaches THIS session is
`hookSpecificOutput.additionalContext` with `permissionDecision: "allow"`,
which the docs state Claude sees before its next decision. Both are emitted
together; neither blocks (`permissionDecision` is always "allow" here).
Cannot-verify (unreadable file / unrecognized transcript shape) stays fully
silent rather than claim a count it does not have — same discipline as the
blocking path's W106b guard just below.

SUBAGENT EXEMPTION (2026-08-21, lane-ship mandate): a session was hard-blocked
on this gate while running as a SUBAGENT — a context with no `Agent` tool of
its own (the current harness does not let a dispatched subagent dispatch a
further subagent), so "zero subagent dispatch in the last 300 lines" is a
structural impossibility for it, not a signal that direct work should stop.
Two independent markers identify that context, checked BEFORE any transcript
read (`is_subagent_context`, right below `GATED_TOOLS`):
  1. `payload["agent_id"]` — DOCUMENTED (code.claude.com/docs/en/hooks,
     checked 2026-08-21): "Present only when the hook fires inside a
     subagent call." Primary signal.
  2. `transcript_path` containing a `subagents` path component — UNDOCUMENTED
     but empirically verified live on 2026-08-21: a subagent's own dedicated
     transcript file lives at
     `<project>/<session>/subagents/agent-a<lane>-<hash>.jsonl`, confirmed
     against real on-disk files including the hook-author's own live
     transcript during this very investigation (every line of that file
     carried `"agentId"` and `"isSidechain":true`; the parent session's own
     transcript file carried neither — 0 occurrences of both). Fallback
     signal, kept in case a harness version omits `agent_id` on some events.
A main-session transcript with zero dispatches past the threshold keeps
blocking exactly as before — this exemption is scoped to the two markers
above, never to "transcript looks quiet."
"""
import json
import os
import pathlib
import re
import sys

# Phase-aware (STEP 3): path-safe import of _phase. Missing _phase → "never plan"
# (gate stays ON) — fail-safe. _phase.py is protected by host_boundary 🔴.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from _phase import is_plan_phase
except Exception:
    def is_plan_phase(payload):
        return False
try:
    from gate_coverage import record as _gc_record
except Exception:
    def _gc_record(hook_name, decision, payload=None):
        pass

HARD_BLOCK_THRESHOLD = 800
RECENT_LINES = 300

# Tool names that mean "a subagent was dispatched". `Agent` is the CURRENT
# harness tool; `Task`/`TaskCreate` are its predecessors, kept so an older
# transcript still reads correctly. Measured 2026-08-12 on live M5 transcripts:
# the quoted forms of Task/TaskCreate score ZERO occurrences ever, while
# `"name":"Agent"` is what a real dispatch actually writes — this gate spent
# an unknown stretch of its life with 4 of its 5 keywords pointing at a
# vocabulary the harness had stopped emitting.
DISPATCH_TOOLS = ("Agent", "Task", "TaskCreate")
# JSON spacing is not ours to assume: match `"name":"Agent"` and `"name": "Agent"`.
DISPATCH_TOOL_RE = re.compile(
    r'"(?:name|tool_name)"\s*:\s*"(?:%s)"' % "|".join(DISPATCH_TOOLS)
)
# Secondary positive signals. `subagent_type` is an OPTIONAL parameter — a
# dispatch that omits it defaults to general-purpose and would be invisible if
# this were the only detector, which is what the pre-2026-08-12 list relied on.
# `isSidechain` is the harness's own record that a subagent turn happened.
DISPATCH_MARKERS = ('"subagent_type"', '"isSidechain":true', '"isSidechain": true')

# If a transcript contains none of these, we are not reading the format we
# think we are reading, and "zero dispatch" is unproven rather than false.
TRANSCRIPT_SHAPE_MARKERS = ('"tool_use"', '"tool_result"', '"role":"assistant"',
                            '"role": "assistant"')

GATED_TOOLS = {"Bash", "Edit", "Write"}


def is_subagent_context(payload):
    """True when this PreToolUse call fires inside a dispatched subagent's own
    turn. See the module docstring's SUBAGENT EXEMPTION note for the evidence
    behind each signal. Checked BEFORE any transcript read — cheap, and works
    even if the transcript file has not been flushed yet."""
    if payload.get("agent_id"):
        return True
    transcript_path = payload.get("transcript_path") or ""
    if transcript_path and "subagents" in pathlib.PurePath(transcript_path).parts:
        return True
    return False

# Disarm-notice: at most once per session (keyed on transcript basename), so a
# 6400-line session gets ONE reminder, not one per Bash call.
STATE_DIR = pathlib.Path.home() / ".agent" / "decisions" / "state"


def dispatch_count(text):
    """Positive evidence that a subagent was dispatched in `text`."""
    return len(DISPATCH_TOOL_RE.findall(text)) + sum(text.count(m) for m in DISPATCH_MARKERS)


def transcript_is_recognizable(text):
    """False when the transcript does not look like a transcript we can parse.

    A gate that cannot read its evidence must not convict on it (W106b:
    cannot-verify is not a verdict). Without this, the day the transcript
    format changes is the day this gate blocks every Bash/Edit/Write on the
    machine for a reason that is not true.
    """
    return any(m in text for m in TRANSCRIPT_SHAPE_MARKERS)


def evaluate_transcript(full_text):
    """Pure evaluation shared by the BLOCK decision and the DISARM notice.

    One source of truth for "would this gate block right now" — the block
    path and the notice path can never disagree about it, because they read
    the same dict. Returns:
      {"total_lines": int, "recognizable": bool,
       "dispatch_count": int|None, "would_block": bool|None}
    `dispatch_count`/`would_block` are None when the transcript shape is not
    recognized — that is a cannot-verify state, not a "zero dispatch" verdict.
    """
    lines = full_text.splitlines()
    total_lines = len(lines)
    recognizable = transcript_is_recognizable(full_text)
    if not recognizable:
        return {
            "total_lines": total_lines,
            "recognizable": False,
            "dispatch_count": None,
            "would_block": None,
        }
    recent = "\n".join(lines[-RECENT_LINES:])
    dc = dispatch_count(recent)
    would_block = total_lines > HARD_BLOCK_THRESHOLD and dc == 0
    return {
        "total_lines": total_lines,
        "recognizable": True,
        "dispatch_count": dc,
        "would_block": would_block,
    }


def _read_transcript(transcript_path):
    """Return the transcript text, or None if it cannot be read (cannot-verify)."""
    if not transcript_path:
        return None
    p = pathlib.Path(transcript_path)
    if not p.exists():
        return None
    try:
        return p.read_text(errors="ignore")
    except Exception:
        return None


def _already_notified_disarm(transcript_path):
    """One disarm-notice per session. Guard file keyed by transcript basename.

    Mirrors premise_gate.py/stadio_zero_nudge.py exactly. On OSError (can't
    write the guard) we fall back to notifying — better a duplicate notice
    than the silence this feature exists to end.
    """
    try:
        key = pathlib.Path(transcript_path).name
        marker = STATE_DIR / f"orchestrate_gate_disarm.{key}.done"
        if marker.exists():
            return True
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text("1")
        return False
    except OSError:
        return False


def build_disarm_notice(tool_name, verdict):
    """Informative, never decorative: names the counts and the verdict they imply."""
    total_lines = verdict["total_lines"]
    dc = verdict["dispatch_count"]
    if verdict["would_block"]:
        judgment = (
            f"WOULD BE BLOCKING this {tool_name} right now — {total_lines} transcript "
            f"lines (> {HARD_BLOCK_THRESHOLD}) and {dc} subagent dispatch in the last "
            f"{RECENT_LINES} lines."
        )
    else:
        judgment = (
            f"would NOT be blocking this {tool_name} right now — {total_lines} transcript "
            f"lines, {dc} subagent dispatch in the last {RECENT_LINES} lines."
        )
    return (
        "[ORCHESTRATE-GATE] disarmed — ORCHESTRATE_GATE_OFF=1 is set in this process's "
        "environment (it may be in no file: check `env | grep ORCHESTRATE_GATE_OFF` and "
        "`launchctl getenv ORCHESTRATE_GATE_OFF`, an inherited shell export leaves neither "
        f"trace). The gate {judgment} `unset ORCHESTRATE_GATE_OFF` and start a fresh shell "
        "to re-arm — this notice fires once per session."
    )


def _emit_disarm_notice(notice):
    print(json.dumps({
        "systemMessage": notice,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": notice,
        },
    }))


def main():
    disarmed = os.environ.get("ORCHESTRATE_GATE_OFF") == "1"

    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            # Bug fixed 2026-08-27: same non-dict-JSON crash class model_routing_gate.py
            # already guarded 2026-08-22 (payload.get() on null/42/[]/a string raises).
            _gc_record("orchestrate_gate", "exempt", None)
            sys.exit(0)
        if is_plan_phase(payload):
            _gc_record("orchestrate_gate", "exempt", payload)  # phase-aware: relax in plan-mode
            sys.exit(0)
    except Exception:
        _gc_record("orchestrate_gate", "exempt", None)
        sys.exit(0)

    tool_name = payload.get("tool_name") or payload.get("name") or ""
    if tool_name not in GATED_TOOLS:
        _gc_record("orchestrate_gate", "exempt", payload)
        sys.exit(0)

    if is_subagent_context(payload):
        sys.stderr.write(
            "[ORCHESTRATE-GATE] subagent context detected (agent_id or "
            "subagents/ transcript path) — exempt: a dispatched subagent has "
            "no Agent tool of its own, so it cannot satisfy 'zero dispatch in "
            f"last {RECENT_LINES} lines' by legitimate means. Not blocking.\n"
        )
        _gc_record("orchestrate_gate", "exempt", payload)
        sys.exit(0)

    transcript_path = payload.get("transcript_path", "")
    full_text = _read_transcript(transcript_path)
    if full_text is None:
        _gc_record("orchestrate_gate", "exempt", payload)
        sys.exit(0)  # cannot-verify: no transcript to read, no claim to make

    verdict = evaluate_transcript(full_text)

    if not disarmed:
        # ARMED — byte-identical to the pre-2026-08-12 behaviour.
        if not verdict["recognizable"]:
            print(
                "[ORCHESTRATE-GATE] transcript format not recognized — cannot tell "
                "whether a subagent was dispatched, so NOT blocking. If this persists, "
                "the gate's detector needs re-measuring against a live transcript.",
                file=sys.stderr,
            )
            _gc_record("orchestrate_gate", "exempt", payload)
            sys.exit(0)
        if not verdict["would_block"]:
            _gc_record("orchestrate_gate", "allow", payload)
            sys.exit(0)
        msg = (
            f"\n[ORCHESTRATE-GATE] Session {verdict['total_lines']} lines, zero subagent "
            f"dispatch in last {RECENT_LINES} lines. Direct {tool_name} BLOCKED.\n"
            f"Choose: (a) Agent(subagent_type=Explore|backend-verifier|frontend-browser|"
            f"nb-curator|mcp-health|spalla-review|general-purpose, model=\"sonnet\", ...) "
            f"or (b) `export ORCHESTRATE_GATE_OFF=1` if intentional direct work.\n"
        )
        print(msg, file=sys.stderr)
        _gc_record("orchestrate_gate", "deny", payload)
        sys.exit(2)

    # DISARMED — never blocks. Say so, once per session, with the real verdict.
    if not verdict["recognizable"]:
        _gc_record("orchestrate_gate", "exempt", payload)
        sys.exit(0)  # cannot-verify: unrecognized shape, no would-block claim to make
    if _already_notified_disarm(transcript_path):
        _gc_record("orchestrate_gate", "exempt", payload)
        sys.exit(0)
    _emit_disarm_notice(build_disarm_notice(tool_name, verdict))
    _gc_record("orchestrate_gate", "exempt", payload)
    sys.exit(0)


if __name__ == "__main__":
    main()
