#!/usr/bin/env python3
"""gate_coverage — shared library for PreToolUse gate decision telemetry (K1).

Superscar #2 (Esiste≠Armato): all four PreToolUse gates (host_boundary,
worktree_isolation, orchestrate_gate, model_routing_gate) are `type=command`
hooks, and the official Claude Code hooks doc says a timed-out command hook
does NOT block ("don't count on a stalled hook to act as a gate") — and all
four end every path in `except Exception: exit 0` too. So they fail OPEN on
timeout, crash, or fork failure (Mini 2026-08-23: `fork failed`; Pro tonight:
13 of 14 parallel subagent spawns failed with `fork failed: Device not
configured`). Nobody measured how often a tool call passes WITHOUT any of
the four ever reaching a decision.

This module gives each gate one call — `record(hook_name, decision, payload)`
— at EVERY one of its own exit paths, so a gate-eligible tool call the
transcript proves happened, with no matching record for that hook, is direct
evidence the gate never finished running (see gate_coverage_report.py, the
Stop hook that computes that gap per hook).

`decision` is one of "allow" | "deny" | "exempt":
  - "deny"   the gate blocked the call (its exit-2 path)
  - "allow"  the gate evaluated the call and let it through
  - "exempt" the gate looked and had nothing to say for THIS call (kill
             switch on, unparseable payload, tool outside its own matcher,
             cannot-verify, OR an in-process exception the gate's own
             try/except caught and chose to degrade from) — it still counts
             as "ran to completion", because the gate's Python code did run
             and did reach a decision point.

TWO DIFFERENT KINDS OF "the gate had nothing to say", and only one of them
is invisible to this file (2026-08-27, refuter finding — see PR #5045):
  1. An in-process Python exception caught by the gate's own try/except
     (e.g. model_routing_gate.py's `_apply_routing_floor` raising) IS
     recorded here as "exempt" — correctly: the gate's code executed, hit a
     bug, and chose to fail open rather than crash. This is a REAL decision,
     just a degraded one. A Stop-hook report showing full coverage for such
     a gate does NOT mean every call was fully evaluated — it means the gate
     ran to completion every time, which can include "ran to completion and
     gave up." That is weaker than it sounds; treat repeated "exempt" from
     one hook as a prompt to go read WHY, not as ipso facto proof of health.
  2. A process-level failure — the hook's OWN interpreter never got far
     enough to run this try/except at all (harness-level timeout kill,
     OOM/SIGKILL, `fork failed`) — genuinely never reaches this function.
     THIS is the class the module exists to expose: it shows up only as a
     GAP between the transcript's gate-eligible tool-call count and the
     decisions recorded here, never as a decision of any kind.

Contract (non-negotiable): NEVER raises, NEVER blocks, NEVER slows the
caller down — every exception is swallowed, target <5ms (one small JSON-line
append). A broken telemetry library must not become a fifth gate.

Kill switch: GATE_COVERAGE_OFF=1 → record() becomes a no-op.
"""
from __future__ import annotations

import json
import os
import time

STATE_DIR = os.path.expanduser("~/.claude/state/gate-coverage")


def record(hook_name: str, decision: str, payload: dict | None = None) -> None:
    """Append one decision line to ~/.claude/state/gate-coverage/<session_id>.jsonl.

    Fire-and-forget: `payload` is the already-parsed hook stdin JSON (or None
    when the gate exited before/without a usable payload, e.g. a JSON parse
    failure) — session_id is read from it, falling back to the
    CLAUDE_SESSION_ID env var, then the literal "unknown" so a decision is
    never silently dropped for lack of an id.
    """
    if os.environ.get("GATE_COVERAGE_OFF") == "1":
        return
    try:
        session_id = None
        if isinstance(payload, dict):
            sid = payload.get("session_id")
            if isinstance(sid, str) and sid:
                session_id = sid
        if not session_id:
            session_id = os.environ.get("CLAUDE_SESSION_ID") or "unknown"
        # Defensive: session_id becomes a filename component — never let it
        # traverse a path or inject something odd into ~/.claude/state/.
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_") or "unknown"
        os.makedirs(STATE_DIR, exist_ok=True)
        line = json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": session_id,
            "hook": hook_name,
            "decision": decision,
        })
        with open(os.path.join(STATE_DIR, f"{safe_id}.jsonl"), "a") as f:
            f.write(line + "\n")
    except Exception:
        pass  # fail-open, always — see module docstring contract
