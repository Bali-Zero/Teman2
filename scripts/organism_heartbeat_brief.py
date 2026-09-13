#!/usr/bin/env python3
"""organism_heartbeat_brief.py — the DIET layer over the heartbeat receptor.

Born 2026-09-09: a Fable session measured ~49K tokens injected at SessionStart
before the first action, and the biggest single offender was
organism_alert_sessionstart.sh printing EVERY open finding from
organism_stale_detector.py, uncapped — including 27 WR2 organs that are stale
BY DECISION (Zero ruled 2026-09-01: "WR2 runs only on command", memory
decision_wr2_runs_only_on_command_2026_09_01) and every finding the session
already saw last time, unchanged.

This script sits BETWEEN the detector and the SessionStart hook and does three
things the detector itself must not do (it has ~40 other callers/tests and
this diet is scoped to the session-start injection path only):

  (a) drop organs matching infra/organism/on_command_organs.json's patterns —
      declarative, so re-arming WR2 (or adding a new manual-only organ) is a
      one-line JSON edit, not a code change;
  (b) show only findings NEW or CHANGED (kind, status) since the last session
      on THIS machine — state file keyed by organ_id, one per machine (the
      caller picks the path; on this fleet it lives under ~/.organism/,
      per-host by construction since ~/.organism/ is not synced cross-host) —
      plus a one-line unchanged count and the full-report command;
  (c) hard-cap the emitted block at --max-bytes (default 1500, matching the
      sibling receptors' SESSIONSTART_HOOK_MAX_BYTES convention).

Fail-open contract, identical to every SessionStart receptor in this family:
ANY error here — malformed findings JSON, an unreadable on-command file, a
corrupt state file, a write failure — must degrade to "print nothing, exit
0". A broken diet must never block a session start, and must never crash back
into the pre-diet flood (that would be worse than doing nothing).

Input: a JSON list of finding dicts (organism_stale_detector.StaleFinding.to_dict()
shape: organ_id/kind/age_days/status/detail) on stdin — the shape
`organism_stale_detector.py --json` prints. This script does not import the
detector or touch its sidecar directory; it only reshapes findings it is handed.

CLI:
    python3 scripts/organism_heartbeat_brief.py \\
        [--on-command-file PATH] [--state-file PATH] [--max-bytes N]
    # findings JSON list on stdin; prints a SessionStart hookSpecificOutput
    # JSON envelope on stdout if there is anything worth surfacing, else
    # nothing. Always exits 0.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)

DEFAULT_ON_COMMAND_FILE = os.path.join(_REPO_ROOT, "infra", "organism", "on_command_organs.json")
DEFAULT_STATE_FILE = os.path.expanduser("~/.organism/session_brief/heartbeat_last_session.json")
DEFAULT_MAX_BYTES = 1500

FULL_REPORT_CMD = "python3 scripts/organism_stale_detector.py --dir ~/.organism/last_seen"

_KIND_GLYPH = {
    "dead_channel": "💀",
    "corrupt": "❓",
    "stale": "🫥",
    "unhealthy": "🤒",
    "warning": "⚠️",
    "stale_branch": "🌿",
}


def load_on_command_patterns(path: str) -> list[str]:
    """Best-effort load of the declarative on-command allow-list.

    Any failure (missing file, bad JSON, wrong shape) returns [] — an empty
    exclusion list is the safe failure mode (nothing is silently hidden), not
    a crash.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        patterns = data.get("patterns", [])
        return [p for p in patterns if isinstance(p, str)]
    except Exception:
        return []


def is_on_command(organ_id: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(organ_id, p) for p in patterns)


def load_state(path: str) -> dict:
    """Best-effort load of the previous session's organ -> [kind, status] map."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        organs = data.get("organs", {})
        return organs if isinstance(organs, dict) else {}
    except Exception:
        return {}


def save_state(path: str, organs: dict) -> None:
    """Best-effort atomic write. A failure here must never raise — the next
    session simply sees the same delta baseline as this one (degrades to
    'no history', not to a crash)."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp.{os.getpid()}"
        payload = {
            "organs": organs,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)
    except Exception:
        pass


def partition_and_diff(
    findings: list[dict], patterns: list[str], previous: dict
) -> tuple[list[dict], int, int, dict]:
    """Split findings into (new_or_changed, unchanged_count, excluded_count,
    next_state).

    next_state only carries currently-present, non-excluded organs — a cured
    organ (absent from this run's findings) is dropped from state too, so the
    state file self-prunes and never becomes a graveyard (same SNAPSHOT
    contract as ~/.organism/alerts/open.jsonl).
    """
    new_or_changed: list[dict] = []
    unchanged = 0
    excluded = 0
    next_state: dict = {}

    for f in findings:
        organ_id = f.get("organ_id")
        if not isinstance(organ_id, str) or not organ_id:
            continue
        if is_on_command(organ_id, patterns):
            excluded += 1
            continue
        kind = f.get("kind")
        status = f.get("status")
        current = [kind, status]
        next_state[organ_id] = current
        prev = previous.get(organ_id)
        if prev == current:
            unchanged += 1
        else:
            new_or_changed.append(f)

    return new_or_changed, unchanged, excluded, next_state


def _payload(ctx: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": ctx,
            }
        }
    )


def _build(new_or_changed: list[dict], show_n: int, unchanged: int, excluded: int) -> str:
    lines = ["🫀 ORGANISM HEARTBEAT (SessionStart delta, injected by receptor)"]
    if new_or_changed:
        lines.append(f"  — {len(new_or_changed)} new/changed since last session:")
        for f in new_or_changed[:show_n]:
            glyph = _KIND_GLYPH.get(f.get("kind"), "•")
            detail = f.get("detail") or f.get("status") or ""
            lines.append(f"    {glyph} {f.get('organ_id')}: {detail}")
        if len(new_or_changed) > show_n:
            lines.append(f"    … +{len(new_or_changed) - show_n} more new/changed")
    else:
        lines.append("  — 0 new/changed since last session.")
    tail_bits = []
    if unchanged:
        tail_bits.append(f"+{unchanged} unchanged")
    if excluded:
        tail_bits.append(f"{excluded} on-command (excluded)")
    trailer = f"run `{FULL_REPORT_CMD}` for the full report."
    if tail_bits:
        lines.append("  — " + ", ".join(tail_bits) + " — " + trailer)
    else:
        lines.append("  — " + trailer)
    return "\n".join(lines)


def build_report(
    new_or_changed: list[dict], unchanged: int, excluded: int, max_bytes: int
) -> str | None:
    if not new_or_changed and unchanged == 0 and excluded == 0:
        return None

    show_n = max(len(new_or_changed), 1)
    ctx = _build(new_or_changed, show_n, unchanged, excluded)
    while len(_payload(ctx).encode("utf-8")) > max_bytes and show_n > 1:
        show_n -= 1
        ctx = _build(new_or_changed, show_n, unchanged, excluded)

    if len(_payload(ctx).encode("utf-8")) > max_bytes:
        # Defensive last resort (a single unbounded `detail` can still
        # overflow at show_n=1): hard-truncate at a line boundary.
        lines = ctx.split("\n")
        kept: list[str] = []
        running = 0
        char_budget = max(max_bytes - 200, 0)  # margin for JSON envelope + trailer
        for ln in lines:
            running += len(ln) + 1
            if running > char_budget:
                break
            kept.append(ln)
        hidden = len(lines) - len(kept)
        if hidden > 0:
            kept.append(f"… (+{hidden} lines, run: {FULL_REPORT_CMD})")
        ctx = "\n".join(kept) if kept else lines[0]

    return ctx


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--on-command-file", default=DEFAULT_ON_COMMAND_FILE)
    ap.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = ap.parse_args(argv)

    try:
        raw = sys.stdin.read()
        findings = json.loads(raw) if raw.strip() else []
        if not isinstance(findings, list):
            findings = []
    except Exception:
        return 0

    try:
        patterns = load_on_command_patterns(args.on_command_file)
        previous = load_state(args.state_file)
        new_or_changed, unchanged, excluded, next_state = partition_and_diff(
            findings, patterns, previous
        )
        ctx = build_report(new_or_changed, unchanged, excluded, args.max_bytes)
        save_state(args.state_file, next_state)
        if ctx:
            print(_payload(ctx))
    except Exception:
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
