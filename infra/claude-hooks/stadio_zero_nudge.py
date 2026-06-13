#!/usr/bin/env python3
"""PreToolUse soft-nudge — STADIO-0 STUDY reminder (FASE-0 of the SOTA meta-dev-loop).

The judgment (what is relevant, which acceptance criteria) belongs to the agent — only
the agent can do the STUDY. This hook does the ANTI-FORGETTING half: if a session starts
EDITING code without having done the STUDY, it injects ONE reminder. It NEVER blocks
(sys.exit(0) always) — a blocking gate on a judgment act invites empty STUDYs to unblock
(reward-hacking, the exact failure P1 warns about). Mirrors dispatch_nudge.py.

Fires once per session, on the first Edit|Write|MultiEdit, only when no STUDY marker is
present in the transcript and the session is still young. Self-silences on trivial tasks.

Kill switch: env STADIO_ZERO_NUDGE_OFF=1.
Reference: STADIO-0 STUDY skill at ~/.claude/skills/stadio-zero/SKILL.md
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

GATED_TOOLS = {"Edit", "Write", "MultiEdit"}
# Only nudge while the session is still young — a long session has clearly moved past
# the entry point, and a late nudge is just noise.
YOUNG_SESSION_MAX_LINES = 400

# Markers that the STUDY was done OR explicitly skipped → no nudge.
# (a) skill invoked, (b) the STUDY output sections present, (c) explicit opt-out.
STUDY_MARKERS = (
    "stadio-zero",                 # skill name (invoked)
    "STADIO-0 STUDY",              # the output block heading
    "STADIO-0 skip",               # explicit skip declaration
    "STADIO-0 PII",                # a STUDY section was written
    "Memory-hits:",                # STUDY output section
    "Hot-files verificati",        # STUDY output section
)
# Trivial-intent markers → self-silence (don't nag on a typo/rename).
TRIVIAL_MARKERS = ("typo", "trivial", "one-liner", "rename", "skip study", "wip:", "checkpoint")

# Per-session guard: don't nudge twice. Keyed by transcript path hash.
STATE_DIR = pathlib.Path.home() / ".agent" / "decisions" / "state"


def _already_nudged(transcript_path: str) -> bool:
    """One nudge per session. Guard file keyed by transcript basename."""
    try:
        key = pathlib.Path(transcript_path).name
        marker = STATE_DIR / f"stadio_zero_nudge.{key}.done"
        if marker.exists():
            return True
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text("1")
        return False
    except OSError:
        # If we can't write the guard, fall back to nudging (better a dup than silence).
        return False


def main() -> None:
    if os.environ.get("STADIO_ZERO_NUDGE_OFF") == "1":
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
        text = p.read_text(errors="ignore")
    except Exception:
        sys.exit(0)

    # Only nudge a young session (the entry point). Past that, it's noise.
    if text.count("\n") > YOUNG_SESSION_MAX_LINES:
        sys.exit(0)

    lower = text.lower()
    # STUDY already done/skipped, or trivial task → no nudge.
    if any(m.lower() in lower for m in STUDY_MARKERS):
        sys.exit(0)
    if any(m in lower for m in TRIVIAL_MARKERS):
        sys.exit(0)

    # One per session.
    if _already_nudged(transcript_path):
        sys.exit(0)

    reminder = (
        "STADIO-0 reminder — about to edit code without a STUDY in this session. "
        "Before building, ground the task: (1) memory-hits (`mem query`), "
        "(2) hot-files VERIFIED on disk (never trust a cited path), (3) PII-risk scope (Law 2), "
        "(4) falsifiable acceptance criteria. Run /stadio-zero, or state in one line why you skip "
        "(trivial task). This does NOT block — it reminds."
    )
    print(json.dumps({"systemMessage": reminder}))
    sys.exit(0)


if __name__ == "__main__":
    main()
