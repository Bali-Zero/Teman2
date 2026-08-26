#!/usr/bin/env python3
"""gate_coverage_report — Stop hook (K1, reporting half).

Reads this session's recorded gate decisions
(~/.claude/state/gate-coverage/<session_id>.jsonl, written by the 4 PreToolUse
gates via gate_coverage.record()) and compares them against how many
gate-eligible tool_use events the transcript actually shows, PER GATE — each
gate's own PreToolUse matcher (copied verbatim from ~/.claude/settings.json,
audited 2026-08-27) decides its own eligible-tool set, see GATE_MATCHERS.
Prints one line per gate that has any signal at all:

    gate coverage: <hook>: decided X of Y tool calls

X < Y is direct evidence some of those Y calls hit a fail-open path (timeout,
crash, fork failure) — the gate never even reached one of its own record()
calls (see gate_coverage.py's module docstring: a `type=command` hook that
times out does NOT block, per the official Claude Code hooks doc, and all
four gates also end every path in `except Exception: exit 0`). Also appends
one JSON summary line to ~/logs/gate-coverage.jsonl.

Transcript read is TAIL-bounded (TRANSCRIPT_TAIL_BYTES) — a session
transcript can be tens of MB (measured 2026-08-26 across the fleet: 33MB
Pro / 48MB Mini / 43MB M5) and this hook runs on every Stop, so it must stay
cheap regardless of file size — same bounded-read posture already used in
this hook family (subagent_stop_verify.py's RECENT_TRANSCRIPT_BYTES).
KNOWN LIMITATION, stated rather than hidden: the decisions file is a
whole-session cumulative count while the transcript read is a bounded tail,
so on a session much longer than the tail cap, X can nominally exceed Y for
a gate — that is a visibility artifact of the bound, not a correctness bug;
the number that matters is a STARK gap (X far below Y), which the bound does
not hide.

Fail-open everywhere: this is a REPORTING hook, never a gate — any exception
degrades to printing nothing and exiting 0. Never blocks Stop.

Kill switch: GATE_COVERAGE_OFF=1 → no-op (shared with gate_coverage.py).
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter

TRANSCRIPT_TAIL_BYTES = 5_000_000  # bounded tail-read regardless of transcript size

# One entry per PreToolUse gate this K1 mandate covers, matcher copied
# verbatim from ~/.claude/settings.json (audited 2026-08-27 — see PR body's
# timeout-audit table for the full hook list). If a gate's matcher changes,
# this dict is the one place to update.
GATE_MATCHERS = {
    "host_boundary": {"Bash", "Edit", "Write", "MultiEdit"},
    "worktree_isolation": {"Bash"},
    "orchestrate_gate": {"Bash", "Edit", "Write"},
    "model_routing_gate": {"Agent"},
}

STATE_DIR = os.path.expanduser("~/.claude/state/gate-coverage")
SUMMARY_LOG = os.path.expanduser("~/logs/gate-coverage.jsonl")


def _tail_read(path: str, cap: int) -> str:
    """Best-effort bounded tail read. Returns "" on any failure (missing
    file, permission error, not a real path — all degrade the same way)."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > cap:
                f.seek(size - cap)
                f.readline()  # drop the (likely partial) first line
            return f.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def count_eligible_tool_calls(transcript_text: str) -> dict:
    """Best-effort count of tool_use events by tool name, from raw JSONL
    text. A targeted per-line substring pre-filter (both JSON spacings, same
    defensive posture as orchestrate_gate.py's DISPATCH_TOOL_RE) before the
    real json.loads, so one malformed/truncated line (expected from the
    tail-seek) cannot crash the whole scan."""
    counts: Counter = Counter()
    for line in transcript_text.splitlines():
        if '"type":"tool_use"' not in line and '"type": "tool_use"' not in line:
            continue
        try:
            evt = json.loads(line)
        except Exception:
            continue
        if not isinstance(evt, dict):
            continue
        content = (evt.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                name = item.get("name")
                if isinstance(name, str) and name:
                    counts[name] += 1
    return dict(counts)


def count_recorded_decisions(session_id: str) -> dict:
    """Per-hook count of decisions recorded this session. {} if no file."""
    counts: Counter = Counter()
    path = os.path.join(STATE_DIR, f"{session_id}.jsonl")
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if not isinstance(rec, dict):
                    continue
                hook = rec.get("hook")
                if isinstance(hook, str) and hook:
                    counts[hook] += 1
    except Exception:
        pass  # missing file / unreadable — zero decisions is the honest answer
    return dict(counts)


def main() -> int:
    if os.environ.get("GATE_COVERAGE_OFF") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = None

    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    if not session_id:
        session_id = os.environ.get("CLAUDE_SESSION_ID") or "unknown"
    transcript_path = payload.get("transcript_path") if isinstance(payload, dict) else None

    try:
        transcript_text = _tail_read(transcript_path, TRANSCRIPT_TAIL_BYTES) if transcript_path else ""
        tool_counts = count_eligible_tool_calls(transcript_text)
        decided = count_recorded_decisions(session_id)

        summary = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": session_id,
            "gates": {},
        }
        for hook, eligible_tools in GATE_MATCHERS.items():
            y = sum(tool_counts.get(t, 0) for t in eligible_tools)
            x = decided.get(hook, 0)
            summary["gates"][hook] = {"decided": x, "eligible": y}
            if y > 0 or x > 0:
                print(f"gate coverage: {hook}: decided {x} of {y} tool calls")

        try:
            os.makedirs(os.path.dirname(SUMMARY_LOG), exist_ok=True)
            with open(SUMMARY_LOG, "a") as f:
                f.write(json.dumps(summary) + "\n")
        except Exception:
            pass
    except Exception:
        pass  # reporting hook — never fail Stop over a telemetry bug

    return 0


if __name__ == "__main__":
    sys.exit(main())
