#!/usr/bin/env python3
"""SubagentStop hook — block a subagent from ending its turn with a dirty
worktree and no committed/declared intent.

Mirror of stop_verify.py (T2.6, `research/operations/specs/T2.6-stop-verify-hook.md`)
for the SubagentStop event: today a subagent that finishes with uncommitted
work is a silent binary failure (cicatrix W80/wave15-live-reap — a worktree
reaper or a sibling session can wipe a subagent's uncommitted work with zero
trace, because nothing forced the subagent to commit, stash, or DECLARE the
dirty state before its turn ended). This hook extends the subagent's turn
with constructive stderr instead of letting it die quietly.

Contract (SubagentStop, verified against docs): JSON payload on stdin with
`session_id`, `transcript_path`, `cwd`, `hook_event_name`, `agent_id`,
`agent_type`, `last_assistant_message`, `stop_hook_active`. Exit 2 + stderr =
block (the subagent's turn continues, stderr is fed back as guidance). Exit 0
= allow the stop.

Anti-loop (mandatory, checked BEFORE everything else): `stop_hook_active`
truthy means we already blocked this same continuation once — Claude Code is
re-invoking the hook because we forced it to keep going. Blocking again would
wall the subagent in an infinite loop. A second, belt-and-suspenders defense
is a per-transcript marker file: once we block, we drop a marker so that even
if `stop_hook_active` is not reliably threaded back to us, we never re-block
the SAME transcript twice.

Kill switches: SUBAGENT_STOP_VERIFY_OFF=1 disables this hook outright.
STOP_VERIFY_ALLOW_DIRTY=1 is honored too (same override as stop_verify.py —
one env var, both Stop-shaped hooks relax).

Fail-open everywhere: any unexpected exception must not wall a subagent — a
broken guardian is worse than no guardian (host_boundary.py / dispatch_nudge.py
precedent). Every failure path here degrades to exit 0.

Reference: research/operations/specs/T2.6-stop-verify-hook.md (the Stop-hook
sibling this mirrors) · cicatrix-scars.md W80 / wave15-live-reap (the failure
class this closes) · infra/claude-hooks/README.md (this repo copy is the audit
trail; the live/executing copy is `~/.claude/hooks/subagent_stop_verify.py`).
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

INTENT_MARKERS = (
    "wip:",
    "checkpoint",
    "leave dirty",
    "leave-dirty",
    "non commit",
    "incomplete on purpose",
    "pause here",
    "salvare per dopo",
)
RECENT_TRANSCRIPT_BYTES = 10_000
MARKER_STALE_SECONDS = 24 * 3600


def _marker_path(transcript_path: str) -> pathlib.Path:
    """Per-transcript once-only marker (anti-loop belt-and-suspenders)."""
    tmp_root = os.environ.get("TMPDIR", "/tmp")
    digest = hashlib.sha1((transcript_path or "").encode("utf-8", errors="ignore")).hexdigest()
    return pathlib.Path(tmp_root) / f"subagent_stop_verify_{digest}.once"


def _sweep_stale_markers(marker: pathlib.Path) -> None:
    """P3: markers accumulate in $TMPDIR forever otherwise — one per distinct
    transcript, never cleaned up. Best-effort GC of SIBLING markers older than
    MARKER_STALE_SECONDS, run whenever we drop a fresh one. Every failure mode
    (missing dir, permission, race with another process) is swallowed: cleanup
    must never be able to change the block/allow verdict."""
    try:
        cutoff = time.time() - MARKER_STALE_SECONDS
        for sibling in marker.parent.glob("subagent_stop_verify_*.once"):
            try:
                if sibling.stat().st_mtime < cutoff:
                    sibling.unlink()
            except Exception:
                continue
    except Exception:
        pass


def _has_intent_marker(transcript_path: str) -> bool:
    if not transcript_path:
        return False
    try:
        p = pathlib.Path(transcript_path)
        if not p.exists():
            return False
        text = p.read_text(errors="ignore")
    except Exception:
        return False
    recent = text[-RECENT_TRANSCRIPT_BYTES:].lower()
    return any(marker in recent for marker in INTENT_MARKERS)


def _git_dirty_status(cwd: str) -> str | None:
    """Returns the `git status --porcelain` output, or None if the dir is not
    a (usable) git repo / clean / unreadable — i.e. "nothing to say"."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    dirty = result.stdout.strip("\n")
    if not dirty.strip():
        return None
    return dirty


def _block_message(cwd: str, dirty: str) -> str:
    lines = dirty.split("\n")
    n = len(lines)
    listing = "\n".join(f"  {line}" for line in lines)
    return (
        "SUBAGENT STOP BLOCKED: dirty worktree with no committed/declared intent.\n"
        f"Working dir: {cwd}\n"
        f"Dirty files ({n} di {n}):\n{listing}\n\n"
        "Before ending your turn, do ONE of:\n"
        "1. Commit ONLY the files YOU modified, path by path\n"
        "   (`git add <specific-path-1> <specific-path-2> ...`), then\n"
        "   `git commit -m 'feat|fix|chore(scope): ...'`. This may be a SHARED\n"
        "   main checkout (cicatrix family #5, sibling-race) — NEVER stage\n"
        "   blindly: no `-A` flag, no `-u` flag, no bare `.`. A blanket\n"
        "   stage-everything can silently capture a sibling session's\n"
        "   in-flight files.\n"
        "2. Declare a deliberate leave-dirty in your final output — state the\n"
        "   owner and the reason (e.g. 'leave-dirty: WIP, orchestrator will\n"
        "   finish in a follow-up turn').\n"
        "3. If some of this dirty state is NOT yours (a sibling session's\n"
        "   files), say so explicitly and do NOT touch/commit/discard it —\n"
        "   see #1: only ever `git add` the specific paths you authored.\n"
        "\n"
        "Override (if this block is wrong): set SUBAGENT_STOP_VERIFY_OFF=1 or\n"
        "STOP_VERIFY_ALLOW_DIRTY=1 and retry.\n"
    )


def _run() -> int:
    if os.environ.get("SUBAGENT_STOP_VERIFY_OFF", "0") == "1":
        return 0
    if os.environ.get("STOP_VERIFY_ALLOW_DIRTY", "0") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # malformed/absent stdin — never block on our own parse failure

    # Anti-loop, PRIMA DI TUTTO: we already forced a continuation, never re-block it.
    if payload.get("stop_hook_active"):
        return 0

    transcript_path = payload.get("transcript_path", "")
    marker = _marker_path(transcript_path)
    if marker.exists():
        return 0  # already blocked this transcript once — do not loop

    cwd = payload.get("cwd", os.getcwd())

    dirty = _git_dirty_status(cwd)
    if dirty is None:
        return 0  # not a git repo / git error / clean — nothing to enforce

    if _has_intent_marker(transcript_path):
        return 0  # explicit intent to leave dirty, honored

    # Block — drop the marker BEFORE writing to stderr / exiting, so a repeat
    # invocation (even without stop_hook_active reaching us) does not re-block.
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except Exception:
        pass  # best-effort; a failed marker write must not change the verdict
    _sweep_stale_markers(marker)  # best-effort GC, never affects the verdict

    sys.stderr.write(_block_message(cwd, dirty))
    return 2


def main() -> int:
    try:
        return _run()
    except Exception as exc:  # fail-open: a broken guardian must not wall subagents
        sys.stderr.write(f"subagent_stop_verify: internal error ({exc!r}) — fail-open, allowing stop\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
