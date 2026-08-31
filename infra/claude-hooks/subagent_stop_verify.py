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

# The lane's own declared check (L04-PR1). Imported from this same directory so
# the repo copy and the installed copy resolve it identically — the installer
# deploys both files side by side. A missing/broken import must NOT wall a
# subagent, so the failure degrades to a no-op evaluator rather than raising at
# hook start-up: superscar #2 says an absent guard should be VISIBLE, and the
# visibility here is that `lane_check` simply never blocks, which the corpus
# `test_subagent_stop_verify.py` can assert, rather than a traceback in a Stop
# hook that nobody reads.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import lane_check as _lane_check
except Exception:  # pragma: no cover - exercised only on a broken install
    _lane_check = None  # type: ignore[assignment]

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


def _marker_path(transcript_path: str, reason: str = "dirty") -> pathlib.Path:
    """Per-transcript, PER-REASON once-only marker (anti-loop belt-and-suspenders).

    The `reason` component was added with the lane check, and a blind refuter is
    why. A single shared marker gave the two block reasons ONE shot BETWEEN them:
    a lane-check block dropped the marker, and the next stop attempt short-
    circuited at the marker test before the dirty-worktree guard ever ran — so
    adding a feature silently un-armed a protection that had been in force. That
    is a worse outcome than the one this hook exists to prevent.

    One marker per reason keeps the anti-loop guarantee exactly as strong where
    it matters (no reason can ever block the same transcript twice, so no loop is
    possible) while bounding the total at one block per reason rather than one
    block overall. The sweep glob below matches both.
    """
    tmp_root = os.environ.get("TMPDIR", "/tmp")
    digest = hashlib.sha1((transcript_path or "").encode("utf-8", errors="ignore")).hexdigest()
    suffix = "" if reason == "dirty" else f".{reason}"
    return pathlib.Path(tmp_root) / f"subagent_stop_verify_{digest}{suffix}.once"


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
                # per-sibling stat/unlink race with another process: skip it,
                # keep sweeping the rest.
                continue
    except Exception:
        # fail-open by design (see docstring): GC must never be able to
        # change the hook's block/allow verdict, so any sweep error is inert.
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


def _drop_marker(marker: pathlib.Path) -> None:
    """Drop the once-only marker and sweep stale siblings, best-effort.

    Extracted when the lane check became a second block reason: both paths must
    drop the SAME marker before writing to stderr, or the anti-loop protection
    would hold for one reason and not the other."""
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except Exception:
        pass  # best-effort; a failed marker write must not change the verdict
    _sweep_stale_markers(marker)  # best-effort GC, never affects the verdict


def _lane_block_message(result) -> str:  # type: ignore[no-untyped-def]
    """Quote the lane check's own verdict verbatim.

    The message is not re-worded here: `lane_check` already composed an
    operator-facing block naming the command, the expected and actual exit and
    the stderr tail, and paraphrasing it in a second place is how the two drift
    apart until one of them lies (W106)."""
    return (
        "SUBAGENT STOP BLOCKED: the lane's own declared check did not pass.\n"
        f"{result.message}\n"
    )


def _changed_paths(cwd: str) -> list[str] | None:
    """Repo-relative paths this turn touched, for the lane check's `scope_globs`.

    WHY THIS EXISTS AT ALL — it was missing, and the absence was invisible.
    The first wiring of the lane check called `evaluate(cwd)` with no change
    set. `lane_check` treats an unknown change set as "always applies" ON
    PURPOSE (an unknown change set is not an out-of-scope one — letting a
    missing input silently disable a check is how a guard stops guarding
    without anyone editing it). The consequence at THIS call site was that
    `scope_globs` never narrowed anything: a declared, tested, documented
    feature that did nothing wherever it was actually used — superscar #2
    inside the change that introduced it. Found by driving the real hook with a
    real payload, not by reading the wiring.

    The set is the UNION of two things, because either alone is a lie about
    what the turn touched: files still dirty in the worktree, and files the
    turn already committed on this branch. Committing is exactly what this hook
    tells a subagent to do, so a change set that ignored commits would shrink
    to nothing precisely when the subagent complied.

    Returns None — meaning "unknown", which makes the check always apply — on
    any git failure. That is the safe direction: a scope we could not compute
    must never be read as a scope that excluded us.
    """
    paths: set[str] = set()
    try:
        # `-uall -z`, and BOTH flags were earned rather than chosen. Measured
        # 2026-08-31 on a throwaway repo, after a refuter named each:
        #   default   -> '?? "has space.txt"\n?? newdir/\n'
        #   -uall     -> individual files instead of the collapsed 'newdir/'
        #   -z        -> NUL-separated and UNQUOTED: 'has space.txt'
        # Without -uall an untracked DIRECTORY arrives as 'newdir/', which
        # matches no file glob, so a scoped check would silently skip on exactly
        # the change it was written for. Without -z a path containing a space
        # arrives quoted and matches nothing either, and the rename form
        # 'old -> new' cannot be told apart from a filename that contains that
        # substring. -z removes the quoting AND the ambiguity: with it, a rename
        # is two separate NUL-terminated fields rather than one arrow-joined
        # string, so the second field is simply the next record.
        st = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain", "-uall", "-z"],
            capture_output=True, text=True, timeout=5,
        )
        if st.returncode != 0:
            return None
        for record in st.stdout.split("\0"):
            if not record.strip():
                continue
            # 'XY path' — the status field is fixed-width, the rest is the path,
            # verbatim and unquoted thanks to -z.
            entry = record[3:] if len(record) > 3 else ""
            if entry.strip():
                paths.add(entry)
    except Exception:
        return None

    try:
        base = subprocess.run(
            ["git", "-C", cwd, "merge-base", "origin/main", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if base.returncode == 0 and base.stdout.strip():
            # THREE-DOT is wrong here and two-dot is right, which is the exact
            # inverse of the rule in W102 — different question. W102 asks "what
            # did this branch author" against a MOVED base; here the base is
            # already the merge-base, so `base..HEAD` is the branch's own
            # commits and nothing of main's.
            # -z here too, for the same quoting reason: `git diff --name-only`
            # quotes a path containing a space, and the quotes would then be
            # part of the string every glob is matched against.
            diff = subprocess.run(
                ["git", "-C", cwd, "diff", "--name-only", "-z", f"{base.stdout.strip()}..HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            if diff.returncode == 0:
                paths.update(p for p in diff.stdout.split("\0") if p.strip())
    except Exception:
        # The committed half is best-effort: the dirty half alone is still a
        # truthful (if narrower) change set, and returning None here would
        # widen every check to always-apply over a missing `origin/main`.
        pass

    return sorted(paths)


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

    # LANE CHECK FIRST, and the order is the argument: a subagent that broke the
    # lane's own declared build check has a worse problem than an uncommitted
    # file, and it is the one it can still fix inside this turn. A worktree with
    # no `.lane-check.json` resolves ABSENT and this costs a single `os.path.isfile`
    # — the innocence baseline, asserted by `test_lane_check.py` with a side-effect
    # probe rather than merely by the returned status.
    #
    # It shares the once-only marker below with the dirty check on purpose. The
    # marker exists so this hook can never wall a subagent in a loop, and that
    # protection has to be indivisible: two independent block reasons each
    # allowed one shot would be two shots. The cost is declared rather than
    # discovered — if a lane check blocks and the subagent then also leaves the
    # tree dirty, only the first message is shown, and the dirty state is caught
    # by the interactive Stop hook or by the reviewer instead.
    lane_marker = _marker_path(transcript_path, reason="lane")
    if _lane_check is not None and not lane_marker.exists():
        try:
            lane_result = _lane_check.evaluate(cwd, changed_paths_fn=lambda: _changed_paths(cwd))
            if _lane_check.blocks(lane_result):
                _drop_marker(lane_marker)
                sys.stderr.write(_lane_block_message(lane_result))
                return 2
        except Exception as exc:
            # A defect in the lane-check path must not wall a subagent over a
            # check the lane declared about itself. Degrade loudly-in-log,
            # silently-in-verdict, and fall through to the dirty check.
            sys.stderr.write(f"subagent_stop_verify: lane_check raised ({exc!r}) — ignoring it\n")

    dirty = _git_dirty_status(cwd)
    if dirty is None:
        return 0  # not a git repo / git error / clean — nothing to enforce

    if _has_intent_marker(transcript_path):
        return 0  # explicit intent to leave dirty, honored

    # Block — drop the marker BEFORE writing to stderr / exiting, so a repeat
    # invocation (even without stop_hook_active reaching us) does not re-block.
    _drop_marker(marker)

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
