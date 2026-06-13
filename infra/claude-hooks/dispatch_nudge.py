#!/usr/bin/env python3
"""UserPromptSubmit hook — counter orchestration regression.

Reads transcript file from Claude env, if long session + zero subagent
dispatch in recent history, injects system reminder.

Reference: research/operations/specs/T1.1-dispatch-nudge-hook.md
"""
import json
import pathlib
import sys

# Phase-aware (STEP 3): path-safe import of _phase. Missing _phase → "never plan"
# (gate stays ON) — fail-safe. _phase.py is protected by host_boundary 🔴.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from _phase import is_plan_phase
except Exception:
    def is_plan_phase(payload):
        return False

LINE_THRESHOLD = 500
RECENT_BYTES = 40_000
# DA Patch 2 (H2) — match actual JSON transcript format, NOT Python-call literals.
# Empirical (devils-advocate scan 2026-05-22): "Agent(" appears 0× in transcripts,
# "Task(" matches "TaskCreate" only partially. Real tool_use blocks have
# {"name": "TaskCreate"} or {"name": "Task"} + {"subagent_type": "..."}.
DISPATCH_KEYWORDS = ('"name":"TaskCreate"', '"name": "TaskCreate"', '"subagent_type"', '"name":"Task"', '"name": "Task"')


def main():
    try:
        payload = json.load(sys.stdin)
        if is_plan_phase(payload): sys.exit(0)  # phase-aware: relax in plan-mode
    except Exception:
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

    total_lines = full_text.count("\n")
    if total_lines <= LINE_THRESHOLD:
        sys.exit(0)

    recent = full_text[-RECENT_BYTES:]
    dispatch_count = sum(recent.count(kw) for kw in DISPATCH_KEYWORDS)

    if dispatch_count == 0:
        reminder = (
            "ORCHESTRATION REMINDER — session is {} lines but no subagent "
            "has been dispatched recently. Before answering, choose one: "
            "(a) direct Bash, (b) load skill, (c) spawn subagent, (d) call MCP — "
            "and state why this choice fits the task."
        ).format(total_lines)
        print(json.dumps({"systemMessage": reminder}))

    sys.exit(0)


if __name__ == "__main__":
    main()
