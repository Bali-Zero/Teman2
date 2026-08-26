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
             cannot-verify) — it still counts as "ran to completion", which
             is the point: a fail-open TIMEOUT/CRASH/fork-failure never
             reaches this function at all, so it shows up only as a GAP in
             the Stop-hook report, never as a decision here.

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
