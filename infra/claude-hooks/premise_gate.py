#!/usr/bin/env python3
"""PreToolUse soft-warn — PREMISE GATE (the L1 detector of the organism DNA).

The organism DNA (dna_organismo_unico, 2026-06-23) names the malattia-madre as
"green != working": the body marks exit-0 on an empty cycle; the session-brain
proceeds *ordinato* on a FALSE PREMISE. The Heartbeat Semantic (L2) is the body's
detector. This is the brain's: it catches an Edit on a product file whose current
contents were NOT verified by a tool-call in THIS turn — i.e. anti-hallucination
rule #2 ("mai costruire su una premessa non falsificata in questo turn") made
mechanical, so the operator (L3) doesn't have to be the only Heartbeat.

WHY warn-only (sys.exit 0, never block): a blocking gate on a judgment act invites
reward-hacking — a token Read to unblock (the exact failure P1 warns about, the
same reason stadio_zero_nudge never blocks). It REMINDS; the judgment stays the
agent's. It also only fires when the evidence of a missing premise is HIGH (Edit
on a product file with zero in-turn read of that file), self-silencing otherwise.

Scope (deliberately narrow — minimize false alarms, the W83/84/85/86 lesson):
  - ONLY Edit / MultiEdit (you modify → you presume what's there). NOT Write of a
    NEW file (no prior premise to verify). NOT Write over an existing file either —
    Edit already requires a prior Read by the harness, so this gate's value is the
    *in-turn* freshness check the harness does not enforce.
  - ONLY product files. Scratchpad, memory (.claude/projects/*/memory), /tmp,
    research/ drafts are exempt (low blast radius, often intentional fresh writes).
  - NOT in plan-mode (phase-aware).
  - One warn per file per session (no nagging).

A "premise verified in THIS turn" = since the last user message, a Read OR a Bash
that names this file path (cat/grep/sed/head/git show/etc.) appears in the transcript
tail. If found → silent. If not → ONE systemMessage reminder.

Kill switch: env PREMISE_GATE_OFF=1.
Reference: dna_organismo_unico_2026_06_23 (L1), CLAUDE.md §6 anti-hallucination rule #2.
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from _phase import is_plan_phase
except Exception:
    def is_plan_phase(payload):
        return False

GATED_TOOLS = {"Edit", "MultiEdit"}

# Product-file gate: exempt low-blast-radius surfaces where a fresh write is normal.
EXEMPT_SUBSTRINGS = (
    "/scratchpad/",
    "/.claude/projects/",          # MOS memory
    "/memory/",
    "/tmp/",
    "/.worktrees/",                # worktree scratch is fine; product lives on main paths
    "/research/",                  # ad-hoc research drafts
    ".bak",
)

STATE_DIR = pathlib.Path.home() / ".agent" / "decisions" / "state"


def _file_path(payload) -> str:
    ti = payload.get("tool_input") or payload.get("input") or {}
    return ti.get("file_path") or ti.get("path") or ""


def _is_product_file(fp: str) -> bool:
    if not fp:
        return False
    low = fp.lower()
    return not any(s in low for s in EXEMPT_SUBSTRINGS)


def _last_user_turn(text: str) -> str:
    """Return the transcript slice since the last user message — i.e. THIS turn.

    Transcript is JSONL; a user message line contains '"role":"user"' (or
    '"type":"user"'). We take everything after the last such line. Fallback: the
    last ~12k chars (a generous single-turn window) if we can't find a marker.
    """
    markers = ('"role": "user"', '"role":"user"', '"type":"user"', '"type": "user"')
    idx = -1
    for m in markers:
        j = text.rfind(m)
        if j > idx:
            idx = j
    if idx == -1:
        return text[-12000:]
    return text[idx:]


def _premise_verified_in_turn(turn_text: str, fp: str) -> bool:
    """True if THIS turn already read/inspected `fp` (Read tool or a shell read)."""
    base = pathlib.Path(fp).name
    if not base:
        return False
    low = turn_text.lower()
    bl = base.lower()
    # The filename appearing in the turn alongside a read-ish tool is the signal.
    # We look for the basename in the turn (a Read tool_use, a cat/grep/head/git show,
    # or an earlier Edit of the same file all mention the path). Cheap + robust:
    # if the file was touched read-side this turn, its basename is in the slice.
    if bl not in low:
        return False
    # basename present — confirm it co-occurs with a read-side action (not only this
    # very Edit's own pre-image, which the harness may echo). Any of these = verified.
    read_signals = ("\"read\"", "tool_use", "cat ", "grep", "head ", "tail ", "sed -n",
                    "git show", "git diff", "git log", "rg ", "less ", "open(")
    return any(s in low for s in read_signals)


def _already_warned(transcript_path: str, fp: str) -> bool:
    try:
        tkey = pathlib.Path(transcript_path).name
        fkey = pathlib.Path(fp).name
        marker = STATE_DIR / f"premise_gate.{tkey}.{fkey}.done"
        if marker.exists():
            return True
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text("1")
        return False
    except OSError:
        return False


def main() -> None:
    if os.environ.get("PREMISE_GATE_OFF") == "1":
        sys.exit(0)
    try:
        payload = json.load(sys.stdin)
        if is_plan_phase(payload):
            sys.exit(0)
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name") or payload.get("name") or ""
    if tool_name not in GATED_TOOLS:
        sys.exit(0)

    fp = _file_path(payload)
    if not _is_product_file(fp):
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

    turn = _last_user_turn(text)
    if _premise_verified_in_turn(turn, fp):
        sys.exit(0)  # premise was checked this turn → silent

    if _already_warned(transcript_path, fp):
        sys.exit(0)

    reminder = (
        f"PREMISE GATE — about to Edit `{pathlib.Path(fp).name}` but no in-turn read of it "
        "is visible this turn. DNA L1 (green != working): don't build on a premise you "
        "haven't falsified in THIS turn — the file may differ from what you remember "
        "(stale checkout / another session / your own assumption). Re-Read it now, or "
        "proceed if you just verified it another way. This does NOT block — it reminds."
    )
    print(json.dumps({"systemMessage": reminder}))
    sys.exit(0)


if __name__ == "__main__":
    main()
