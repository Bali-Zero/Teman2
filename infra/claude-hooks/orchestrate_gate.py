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
DISPATCH_KEYWORDS = (
    '"name":"TaskCreate"', '"name": "TaskCreate"',
    '"subagent_type"',
    '"name":"Task"', '"name": "Task"',
)
GATED_TOOLS = {"Bash", "Edit", "Write"}


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

    recent = "\n".join(lines[-RECENT_LINES:])
    dispatch_count = sum(recent.count(kw) for kw in DISPATCH_KEYWORDS)

    if dispatch_count > 0:
        sys.exit(0)

    msg = (
        f"\n[ORCHESTRATE-GATE] Session {total_lines} lines, zero subagent "
        f"dispatch in last {RECENT_LINES} lines. Direct {tool_name} BLOCKED.\n"
        f"Choose: (a) Agent(subagent_type=Explore|backend-verifier|frontend-browser|"
        f"nb-curator|mcp-health|spalla-review|general-purpose, ...) "
        f"or (b) `export ORCHESTRATE_GATE_OFF=1` if intentional direct work.\n"
    )
    print(msg, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
