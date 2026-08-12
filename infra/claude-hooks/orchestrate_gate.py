#!/usr/bin/env python3
"""PreToolUse hard-gate — Gap 1 fix (2026-05-25).

Blocca Bash|Edit|Write se:
  - transcript >800 lines AND
  - zero subagent dispatch in last 300 lines

Exit 2 + stderr message → Claude rilegge il blocco e riconsidera.
Override: env ORCHESTRATE_GATE_OFF=1.

Upgrade di dispatch_nudge.py (soft warn UserPromptSubmit) a hard-block PreToolUse.
Cicatrix family: T1.1 dispatch reminder, W33 kill-switch pattern.
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


def main():
    if os.environ.get("ORCHESTRATE_GATE_OFF") == "1":
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
        if is_plan_phase(payload): sys.exit(0)  # phase-aware: relax in plan-mode
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name") or payload.get("name") or ""
    if tool_name not in GATED_TOOLS:
        sys.exit(0)

    transcript_path = payload.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    p = pathlib.Path(transcript_path)
    if not p.exists():
        sys.exit(0)

    try:
        full_text = p.read_text(errors="ignore")
    except Exception:
        sys.exit(0)

    lines = full_text.splitlines()
    total_lines = len(lines)
    if total_lines <= HARD_BLOCK_THRESHOLD:
        sys.exit(0)

    if not transcript_is_recognizable(full_text):
        print(
            "[ORCHESTRATE-GATE] transcript format not recognized — cannot tell "
            "whether a subagent was dispatched, so NOT blocking. If this persists, "
            "the gate's detector needs re-measuring against a live transcript.",
            file=sys.stderr,
        )
        sys.exit(0)

    recent = "\n".join(lines[-RECENT_LINES:])
    if dispatch_count(recent) > 0:
        sys.exit(0)

    msg = (
        f"\n[ORCHESTRATE-GATE] Session {total_lines} lines, zero subagent "
        f"dispatch in last {RECENT_LINES} lines. Direct {tool_name} BLOCKED.\n"
        f"Choose: (a) Agent(subagent_type=Explore|backend-verifier|frontend-browser|"
        f"nb-curator|mcp-health|spalla-review|general-purpose, model=\"sonnet\", ...) "
        f"or (b) `export ORCHESTRATE_GATE_OFF=1` if intentional direct work.\n"
    )
    print(msg, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
