#!/usr/bin/env python3
"""Universal worktree GC — covers ALL git worktrees, not just broker/WR2 lanes.

Closes the gap between the two existing GCs (cicatrix W62/W63 + 3-LLM panel
2026-05-29):
  - scripts/agent_start.py --cleanup  → only worktrees with .agent-task.json,
    filtered by metadata TTL. Orphans/manual/nested/<tmp> worktrees invisible.
  - scripts/wr2_worktree_gc.py        → only wr2-run-* prefix, by mtime.

This script enumerates `git worktree list --porcelain` so EVERY worktree is in
scope. For each candidate it applies the panel's safety model:

  1. NEVER touch the main checkout or known long-lived worktrees (allowlist).
  2. Age gate: skip if mtime < MIN_AGE_MIN (active session).
  2b. Live-cwd gate: skip if any process on the machine has its cwd inside the
      worktree (exact match OR a subdirectory) — a precise "active session"
      signal the mtime-age gate alone misses (a shell idling deep in the tree
      touches no file, so mtime never moves). Best-effort via `lsof`; missing
      binary / any error → falls through to the age/dirty gates below, never
      crashes the GC.
  3. Dirty classification: `git status --porcelain` AND a whitespace-insensitive
     diff. Pure formatting noise (Prettier/Black reflow) is NOT real work
     (W62: the 6 orphans were all formatting-only). Real dirty → QUARANTINE.
  4. Quarantine before removal: if a worktree has real uncommitted work OR is on
     a detached HEAD with commits, stash it onto refs/agent-quarantine/<slug>
     so nothing is lost, THEN remove. Never blind-delete dirty work.
  5. Unpushed-commit handling (FIXED 2026-07-18 — cure for the W88 "kept
     forever" bug: the daily cron reaped 0 for days, 53 worktrees / 55G
     accumulated, because this gate hard-KEPT every named-branch worktree
     with `rev-list origin/main..HEAD` > 0 — a proxy that inflated to
     7779-7833 on divergent/rebased/squashed bases). A NAMED branch's
     unpushed commits no longer block dir removal: `git worktree remove`
     only deletes the WORKING DIRECTORY, never the branch ref — the branch
     (and every commit on it) survives in refs/heads/ untouched and is fully
     recoverable via `git worktree add <path> <branch>`. The GC logs a
     RECLAIM-DIR line (operator awareness + the exact resume command) and
     proceeds to remove the dir. This script NEVER runs `git branch -D`/`-d`
     — grep the file to confirm the invariant holds. Detached HEAD with
     unpushed commits is the one case still quarantined first (those commits
     have no branch ref to fall back on if the dir goes away).
  6. `git worktree prune` at the end → clears phantom admin entries for /tmp
     worktrees deleted on reboot (Pattern 7).
  7. dry-run by DEFAULT; --apply required to remove.
  8. Loop-bug alarm: WARN if it would remove > MAX_REMOVE_ALARM in one run.

Kill switch: WORKTREE_GC_ENABLED=false → no-op exit 0.
Run: python scripts/worktree_gc_universal.py [--apply] [--quiet]
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("worktree_gc_universal")

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKTREES_DIR = REPO_ROOT / ".worktrees"
STATE_FILENAME = ".agent-task.json"
KILL_SWITCH_ENV = "WORKTREE_GC_ENABLED"

MIN_AGE_MIN = 15          # skip worktrees touched in the last 15 min (active)
DEFAULT_MAX_AGE_HOURS = 24
MAX_REMOVE_ALARM = 5      # WARN if a single run removes more than this
QUARANTINE_REF_PREFIX = "refs/agent-quarantine"

# Worktrees that must NEVER be GC'd, regardless of age/state.
# Matched by resolved absolute path.
ALLOWLIST_PATHS = {
    str(REPO_ROOT),
    str(Path.home() / "Desktop" / "nuzantara-deploy"),
    str(Path.home() / "Desktop" / "nuzantara-crm-guardian-drive"),
}


def _run_git(args, *, cwd=None, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        check=check,
    )


def _kill_switch_active() -> bool:
    return os.environ.get(KILL_SWITCH_ENV, "true").strip().lower() in (
        "false", "0", "no", "off", "disabled",
    )


def _list_worktrees() -> list[dict]:
    """Parse `git worktree list --porcelain` into dicts.

    Each: {path, head, branch (or None), detached (bool), bare (bool)}.
    """
    out = _run_git(["worktree", "list", "--porcelain"], check=True).stdout
    entries: list[dict] = []
    cur: dict = {}
    for line in out.splitlines():
        if not line.strip():
            if cur:
                entries.append(cur)
                cur = {}
            continue
        if line.startswith("worktree "):
            cur = {"path": line[len("worktree "):], "branch": None,
                   "detached": False, "bare": False, "head": None}
        elif line.startswith("HEAD "):
            cur["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch "):].replace("refs/heads/", "")
        elif line.strip() == "detached":
            cur["detached"] = True
        elif line.strip() == "bare":
            cur["bare"] = True
    if cur:
        entries.append(cur)
    return entries


def _mtime_age_seconds(path: Path) -> float | None:
    """Newest mtime among path + path/.git (the broker bumps the latter).

    Returns None if the path doesn't exist (phantom /tmp entry)."""
    try:
        m = path.stat().st_mtime
    except OSError:
        return None
    gitp = path / ".git"
    try:
        m = max(m, gitp.stat().st_mtime)
    except OSError:
        pass
    return time.time() - m


def _has_real_dirty(worktree: Path) -> bool:
    """True if the worktree has NON-formatting uncommitted changes.

    A pure whitespace/formatting reflow (Prettier/Black) is NOT real work
    (cicatrix W62). We detect that by diffing with --ignore-all-space: if the
    porcelain status is non-empty BUT the whitespace-insensitive diff is empty,
    it's formatting noise → not real dirty.
    Unreadable/corrupt → True (safer to keep).
    """
    try:
        status = _run_git(["status", "--porcelain"], cwd=worktree, check=True).stdout
    except subprocess.CalledProcessError as exc:
        logger.warning("status failed in %s: %s — treating as dirty", worktree, exc)
        return True
    lines = [
        ln for ln in status.splitlines()
        if ln.strip() and not ln.strip().endswith(STATE_FILENAME)
    ]
    if not lines:
        return False
    # Untracked files (??) are always real work — diff can't see them.
    if any(ln.startswith("??") for ln in lines):
        return True
    # Tracked changes: check if they survive whitespace-insensitivity.
    try:
        diff = _run_git(
            ["diff", "--ignore-all-space", "--ignore-blank-lines"],
            cwd=worktree, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return True
    return bool(diff.strip())


def _has_live_cwd(worktree: Path) -> bool:
    """True if any process on the machine has its cwd inside this worktree
    (exact match OR a subdirectory) — a precise "active session" signal the
    mtime-age gate alone misses (a shell idling deep in the tree touches no
    file, so mtime never moves).

    Implementation note (verified empirically on macOS, 2026-07-18): the
    obvious `lsof -a -d cwd -Fn -- <dir>` form only matches an EXACT cwd —
    a shell cd'd into a *subdirectory* of the worktree (e.g.
    `<worktree>/apps/backend-rag`) is invisible to it. `lsof +D <dir>`
    recursively walks the target directory's open files and would be
    catastrophically slow on a large worktree (this GC exists because
    worktrees grow to tens of GB). The reliable+cheap form: ask lsof for
    EVERY process's cwd system-wide (`lsof -a -d cwd -Fn`, no path filter —
    a syscall-table read, ~0.2s even on a busy box) and prefix-match the
    paths in Python. That correctly catches both exact and nested cwds.

    lsof missing/erroring/timing out → False (fall back to the age/dirty
    gates; a live-cwd check must never crash or hang the GC).
    """
    try:
        target = str(worktree.resolve())
    except OSError:
        target = str(worktree)
    try:
        out = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-Fn"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:
        return False
    prefix = target.rstrip("/") + "/"
    for line in out.splitlines():
        if not line.startswith("n"):
            continue
        name = line[1:]
        if name == target or name.startswith(prefix):
            return True
    return False


def _unpushed_commits(worktree: Path, branch: str | None) -> int:
    """Count commits on this worktree's HEAD not present on origin/main.

    W88 CAVEAT: this is a PROXY, not a truth signal. `rev-list --count
    origin/main..HEAD` inflates wildly on a divergent/rebased/squashed base
    (verified 2026-07-18: 7779-7833 on health/repush/one-shot worktrees whose
    content was long since squash-merged) — that inflation is exactly what
    made the GC's old unpushed-gate KEEP-FOREVER (see gc()). Since 2026-07-18
    this count is used ONLY to produce an operator-facing log number, never to
    gate dir-removal for a named branch (a clean branch's commits survive in
    the branch ref regardless of what this reports).

    Honesty short-circuit: if `git diff --quiet origin/main...HEAD` (three-dot,
    content since common ancestor) reports no difference, the branch is fully
    merged BY CONTENT — return 0 even if rev-list would over-count. The
    three-dot form has its own known failure mode post-squash (cicatrix #9,
    the W88 double-trap: an arrears merge-base can make it report a phantom
    difference) — but that failure only produces a false NON-zero, never a
    false zero, so trusting a "no diff" (exit 0) verdict here is safe; we
    never trust a "has diff" verdict as truth, we just fall through to the
    raw, known-noisy rev-list count for the log line.

    Conservative on error: any git failure → return 1 (log-line only, no
    longer a keep/remove gate for named branches).
    """
    try:
        quiet = _run_git(
            ["diff", "--quiet", "origin/main...HEAD"], cwd=worktree, check=False,
        )
        if quiet.returncode == 0:
            return 0
    except Exception:  # noqa: BLE001 — best-effort short-circuit, never fatal
        pass
    try:
        # Use origin/main as the canonical upstream baseline.
        out = _run_git(
            ["rev-list", "--count", "origin/main..HEAD"],
            cwd=worktree, check=True,
        ).stdout.strip()
        return int(out or "0")
    except (subprocess.CalledProcessError, ValueError):
        return 1


def _quarantine(worktree: Path, slug: str, *, apply: bool) -> bool:
    """Create a quarantine ref capturing the worktree's current tree+untracked.

    Uses `git stash create` (produces a commit object without touching the
    stash stack) then writes it to refs/agent-quarantine/<slug>. Returns True
    on success (or dry-run). Best-effort: failure → False (caller keeps wt).
    """
    ref = f"{QUARANTINE_REF_PREFIX}/{slug}"
    if not apply:
        logger.info("[dry-run] would quarantine %s -> %s", worktree, ref)
        return True
    try:
        # stash create captures tracked changes; add -u-equivalent by staging
        # untracked first into the index of a temp — simplest robust path:
        # `git stash create` does NOT include untracked, so we snapshot via
        # a throwaway commit of `git add -A` is invasive. Instead capture a
        # patch artifact AND a stash-create commit for tracked changes.
        _run_git(["add", "-A"], cwd=worktree, check=False)
        created = _run_git(["stash", "create", f"quarantine {slug}"],
                           cwd=worktree, check=False)
        sha = created.stdout.strip()
        if sha:
            _run_git(["update-ref", ref, sha], check=False)
            logger.info("quarantined %s -> %s (%s)", worktree, ref, sha[:10])
        # Also drop a patch artifact under .agent-receipts/ for human-readable
        # recovery even if the ref is later pruned.
        receipts = REPO_ROOT / ".agent-receipts"
        receipts.mkdir(exist_ok=True)
        patch = _run_git(["diff", "HEAD"], cwd=worktree, check=False).stdout
        (receipts / f"quarantine-{slug}.patch").write_text(patch)
        # Reset the index we just staged so removal is clean.
        _run_git(["reset"], cwd=worktree, check=False)
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort, never crash GC
        logger.warning("quarantine failed for %s: %s", worktree, exc)
        return False


def _remove(worktree: Path, *, apply: bool) -> bool:
    if not apply:
        logger.info("[dry-run] would remove worktree %s", worktree)
        return True
    try:
        _run_git(["worktree", "remove", "--force", str(worktree)], check=True)
        logger.info("removed worktree %s", worktree)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("remove failed %s: %s", worktree, (exc.stderr or "").strip())
        return False


def _slug(path: str) -> str:
    return path.rstrip("/").replace("/", "_").lstrip("_")[:80]


def gc(*, apply: bool, max_age_hours: float) -> int:
    if _kill_switch_active():
        logger.info("%s=false — GC disabled, no-op", KILL_SWITCH_ENV)
        return 0

    entries = _list_worktrees()
    # In dry-run these count what WOULD happen; in apply they count what DID.
    removed = 0
    quarantined = 0
    reclaimed_unpushed = 0
    kept_active = 0
    pruned_phantom = 0
    verb = "would " if not apply else ""

    for e in entries:
        path_str = e["path"]
        path = Path(path_str)

        if e.get("bare"):
            continue
        if path_str in ALLOWLIST_PATHS or str(path.resolve()) in ALLOWLIST_PATHS:
            continue

        age = _mtime_age_seconds(path)
        if age is None:
            # Phantom: registered but dir gone (reboot-cleared /tmp). Prune.
            logger.info("phantom worktree (dir missing): %s", path_str)
            pruned_phantom += 1
            continue

        if age < MIN_AGE_MIN * 60:
            kept_active += 1
            continue

        if _has_live_cwd(path):
            logger.info("KEEP %s — live process cwd inside (active)", path_str)
            kept_active += 1
            continue

        if age < max_age_hours * 3600:
            # Not old enough yet.
            continue

        slug = _slug(path_str)
        real_dirty = _has_real_dirty(path)
        unpushed = _unpushed_commits(path, e.get("branch"))

        # Detached HEAD with commits OR real dirty work → quarantine first.
        needs_quarantine = real_dirty or (e.get("detached") and unpushed > 0)

        # INVARIANT: this GC NEVER deletes a branch (no `git branch -D`/`-d`
        # anywhere in this file — grep to confirm). `git worktree remove`
        # only removes the WORKING DIRECTORY; the branch ref — and every
        # commit on it — survives untouched in refs/heads/ and is fully
        # recoverable via `git worktree add <path> <branch>`. So a clean
        # named branch's unpushed commits must NOT block dir reclamation
        # (W88 cure, 2026-07-18): log for operator awareness, then fall
        # through to removal below (no quarantine needed — the branch ref
        # IS the durable copy).
        if unpushed > 0 and not e.get("detached"):
            logger.warning(
                "RECLAIM-DIR %s — branch '%s' retains %d commit(s) not on "
                "origin/main; dir reclaimed to free disk, branch ref "
                "PRESERVED (resume with: git worktree add %s %s)",
                path_str, e.get("branch"), unpushed, path_str, e.get("branch"),
            )
            reclaimed_unpushed += 1

        if needs_quarantine:
            if not _quarantine(path, slug, apply=apply):
                logger.warning("KEEP %s — quarantine failed, refusing to remove",
                               path_str)
                continue
            quarantined += 1

        if _remove(path, apply=apply):
            removed += 1
            logger.info("%sremove counted: %s (total %d)", verb, path_str, removed)

    # Always prune phantom admin entries (cheap, safe, fixes /tmp reboot bug).
    if apply:
        _run_git(["worktree", "prune"], check=False)

    if removed > MAX_REMOVE_ALARM:
        logger.warning(
            "[ALARM] universal worktree GC removed %d worktrees in one run — "
            "investigate possible loop bug", removed,
        )

    logger.info(
        "done: removed=%d quarantined=%d reclaimed_unpushed=%d kept_active=%d "
        "phantom=%d apply=%s",
        removed, quarantined, reclaimed_unpushed, kept_active, pruned_phantom, apply,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="actually remove (default: dry-run report only)")
    parser.add_argument("--max-age-hours", type=float,
                        default=float(os.environ.get("WORKTREE_GC_MAX_AGE_HOURS",
                                                      DEFAULT_MAX_AGE_HOURS)))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    return gc(apply=args.apply, max_age_hours=args.max_age_hours)


if __name__ == "__main__":
    raise SystemExit(main())
