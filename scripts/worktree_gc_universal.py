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
      touches no file, so mtime never moves). `lsof` is resolved by ABSOLUTE
      path (round-2 fix, 2026-07-18: the daily cron's plist PATH is
      `/opt/homebrew/bin:/usr/bin:/bin`, which does NOT contain `lsof` on
      either M5 or Pro — it lives at `/usr/sbin/lsof` — so a bare
      `["lsof", ...]` call silently raised FileNotFoundError under the REAL
      cron and the guard was inert the whole time: scar #2, green-but-not-
      working). lsof is invoked ONCE per gc() run (system-wide cwd dump),
      never once per worktree — a 53-worktree fleet at a 20s timeout each
      would be ~17min cumulative worst case. Missing binary / any error →
      logged (visibly, not silently) and falls through to the age/dirty
      gates below; a live-cwd check must never crash or hang the GC.
  3. Dirty classification: `git status --porcelain` AND a whitespace-insensitive
     diff. Pure formatting noise (Prettier/Black reflow) is NOT real work
     (W62: the 6 orphans were all formatting-only). Real dirty → QUARANTINE.
  4. Preservation before removal runs on TWO INDEPENDENT tracks, either of
     which can veto the remove:
       a. Real uncommitted work (any worktree) → stash-quarantine onto
          refs/agent-quarantine/<slug> (git stash create; never touches the
          stash stack). Quarantine failure → KEEP, never remove.
       b. Detached HEAD (round-2 fix, 2026-07-18 — cure for a silent-orphan
          bug: a CLEAN detached-HEAD worktree has no branch ref, so
          `git worktree remove` was dropping the only pointer to its
          commits into dangling/unreachable space. `git stash create` is
          EMPTY on a clean tree, so the old real_dirty-only quarantine never
          fired for this case). For ANY detached worktree about to be
          removed, UNCONDITIONALLY resolve `git rev-parse --verify HEAD` and
          write it to refs/agent-quarantine/<slug>-head BEFORE removal —
          never gated by the unpushed-commit proxy (rule 5), which can
          false-zero a detached HEAD via the three-dot content
          short-circuit. Resolution or ref-write failure → KEEP, never
          remove (log "could not preserve detached HEAD").
     Quarantine/preservation refs check for a pre-existing ref at the same
     name first (slug-truncation collision) and append a short sha
     uniquifier on collision, so a re-run never clobbers a prior quarantine.
  5. Unpushed-commit handling for NAMED branches only (FIXED 2026-07-18 —
     cure for the W88 "kept forever" bug: the daily cron reaped 0 for days,
     53 worktrees / 55G accumulated, because this gate hard-KEPT every
     named-branch worktree with `rev-list origin/main..HEAD` > 0 — a proxy
     that inflated to 7779-7833 on divergent/rebased/squashed bases). A
     NAMED branch's unpushed commits no longer block dir removal:
     `git worktree remove` only deletes the WORKING DIRECTORY, never the
     branch ref — the branch (and every commit on it) survives in
     refs/heads/ untouched and is fully recoverable via
     `git worktree add <path> <branch>`. The GC logs a RECLAIM-DIR line
     (operator awareness + the exact resume command) and proceeds to remove
     the dir. This script NEVER runs `git branch -D`/`-d` — grep the file to
     confirm the invariant holds. (Detached HEAD is rule 4b above, not this
     rule — it never had a branch ref to rely on.)
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
import shutil
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


def _resolve_lsof_path() -> str | None:
    """Resolve an absolute path to `lsof`, independent of the caller's PATH.

    BLOCKER (round-2, 2026-07-18): the daily cron's plist sets
    `PATH=/opt/homebrew/bin:/usr/bin:/bin`. On BOTH M5 and Pro, `lsof` lives
    ONLY at `/usr/sbin/lsof` — not on that PATH. A bare
    `subprocess.run(["lsof", ...])` therefore raised FileNotFoundError under
    the ACTUAL cron every single run, and the old `_has_live_cwd` caught
    that broadly and returned False — so the live-cwd guard was silently
    inert in production the whole time it existed (scar #2, "green but not
    working": no crash, no log, just a guard that never once fired).

    `shutil.which` first (honors an explicit PATH when one is set — covers
    interactive/test invocations), else probe the two known-good absolute
    locations directly. None found → caller must log visibly and degrade,
    never fail silently again.
    """
    found = shutil.which("lsof")
    if found:
        return found
    for candidate in ("/usr/sbin/lsof", "/usr/bin/lsof"):
        if Path(candidate).exists():
            return candidate
    return None


def _collect_live_cwds() -> set[str]:
    """Run `lsof -a -d cwd -Fn` ONCE (system-wide, no path filter) and return
    the set of every process's cwd path on the machine.

    Cheap: a syscall-table read (~0.2s even on a busy box), NOT a directory
    walk (`lsof +D <dir>` would recursively stat every open file under the
    target — catastrophic on a worktree that can run to tens of GB, which is
    exactly why this GC exists). Call this ONCE per gc() run and pass the
    result to `_has_live_cwd` for each worktree (round-2 fix, 2026-07-18:
    Codex flagged that calling lsof per-worktree could cost up to ~17min
    cumulative worst-case across a 53-worktree fleet at a 20s timeout each).

    lsof missing (resolver finds nothing) or any invocation error → empty
    set, logged ONCE here (not once per worktree, which would spam the log
    across a large fleet) as a WARNING so the degradation is VISIBLE. Falls
    through to the age/dirty gates for every worktree this run; a live-cwd
    check must never crash or hang the GC.
    """
    lsof_path = _resolve_lsof_path()
    if lsof_path is None:
        logger.warning(
            "live-cwd guard DEGRADED — lsof not found (checked PATH + "
            "/usr/sbin/lsof + /usr/bin/lsof); this run falls back to "
            "age/dirty gates only",
        )
        return set()
    try:
        out = subprocess.run(
            [lsof_path, "-a", "-d", "cwd", "-Fn"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception as exc:  # noqa: BLE001 — best-effort, never crash the GC
        logger.warning("live-cwd guard DEGRADED — lsof invocation failed: %s", exc)
        return set()
    return {line[1:] for line in out.splitlines() if line.startswith("n")}


def _has_live_cwd(worktree: Path, live_cwds: set[str]) -> bool:
    """True if `live_cwds` (from _collect_live_cwds(), collected ONCE per
    gc() run) contains this worktree's path — exact match OR a subdirectory
    — a precise "active session" signal the mtime-age gate alone misses (a
    shell idling deep in the tree touches no file, so mtime never moves).

    Pure Python prefix-match, no subprocess call here (verified empirically
    on macOS, 2026-07-18: the obvious `lsof -a -d cwd -Fn -- <dir>` form
    only matches an EXACT cwd — a shell cd'd into a *subdirectory* of the
    worktree, e.g. `<worktree>/apps/backend-rag`, is invisible to it — so
    the prefix-match has to happen in Python against the full system-wide
    dump, not via lsof's own path filter).
    """
    try:
        target = str(worktree.resolve())
    except OSError:
        target = str(worktree)
    prefix = target.rstrip("/") + "/"
    return any(c == target or c.startswith(prefix) for c in live_cwds)


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


def _ref_exists(ref: str) -> bool:
    """True if `ref` already resolves to an object (any worktree shares the
    same ref namespace via the common .git dir)."""
    result = _run_git(["rev-parse", "--verify", "--quiet", ref], check=False)
    return result.returncode == 0


def _unique_ref(base_ref: str, sha_hint: str) -> str:
    """Return base_ref, or base_ref + a short sha-based uniquifier if
    base_ref already resolves (FIX C, round-2, 2026-07-18): the 80-char
    truncation in _slug() can theoretically collide two different worktree
    paths onto the same slug, and re-running the GC before a prior
    quarantine ref is manually cleaned up would otherwise clobber it with
    `update-ref` (unconditional overwrite). Cheap: one `rev-parse --verify`.
    """
    if not _ref_exists(base_ref):
        return base_ref
    return f"{base_ref}-{sha_hint[:8]}"


def _quarantine(worktree: Path, slug: str, *, apply: bool) -> bool:
    """Create a quarantine ref capturing the worktree's current tree+untracked.

    Uses `git stash create` (produces a commit object without touching the
    stash stack) then writes it to refs/agent-quarantine/<slug> (or a
    collision-safe variant, see _unique_ref). Returns True on success (or
    dry-run). Best-effort: failure → False (caller keeps wt).

    NOTE: `git stash create` is EMPTY on a clean working tree — it captures
    only uncommitted diffs, never committed-but-unreachable-elsewhere
    commits. It is NOT a substitute for _preserve_detached_head(), which
    covers the orthogonal case of a detached HEAD's own commits (BLOCKER B,
    round-2, 2026-07-18).
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
            final_ref = _unique_ref(ref, sha)
            _run_git(["update-ref", final_ref, sha], check=False)
            logger.info("quarantined %s -> %s (%s)", worktree, final_ref, sha[:10])
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


def _preserve_detached_head(worktree: Path, slug: str, *, apply: bool) -> bool:
    """Unconditionally create a durable ref to a detached worktree's HEAD
    BEFORE removal (BLOCKER B, round-2, 2026-07-18).

    A detached-HEAD worktree has NO branch ref — its commits are reachable
    ONLY through that worktree's HEAD. `git worktree remove` drops that
    pointer; if nothing else references the commits, they become dangling
    and are eventually GC'd by git itself. `git stash create` (the
    _quarantine() mechanism) does NOT cover this — it is EMPTY on a clean
    tree, so a CLEAN detached-HEAD worktree with unique commits sailed
    through the old real_dirty-only quarantine gate and got force-removed,
    orphaning its commits.

    This check runs for EVERY detached worktree about to be removed,
    UNCONDITIONALLY — never gated by _unpushed_commits(), which can
    false-zero a detached HEAD via its three-dot content short-circuit
    (e.g. a revert/merge commit unique to this worktree but content-equal
    to origin/main would read as "0 unpushed" while still being the only
    reachable pointer to that commit object).

    Returns True iff a durable ref now exists pointing at HEAD (or dry-run).
    False → caller MUST keep the worktree, never remove it.
    """
    ref = f"{QUARANTINE_REF_PREFIX}/{slug}-head"
    if not apply:
        logger.info(
            "[dry-run] would preserve detached HEAD %s -> %s", worktree, ref,
        )
        return True
    rev = _run_git(["rev-parse", "--verify", "HEAD"], cwd=worktree, check=False)
    sha = rev.stdout.strip()
    if rev.returncode != 0 or not sha:
        logger.error(
            "could not resolve HEAD for detached worktree %s (rc=%d) — "
            "refusing to remove", worktree, rev.returncode,
        )
        return False
    final_ref = _unique_ref(ref, sha)
    updated = _run_git(["update-ref", final_ref, sha], check=False)
    if updated.returncode != 0:
        logger.error(
            "update-ref failed for detached worktree %s -> %s (rc=%d) — "
            "refusing to remove", worktree, final_ref, updated.returncode,
        )
        return False
    logger.info(
        "preserved detached HEAD %s -> %s (%s)", worktree, final_ref, sha[:10],
    )
    return True


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
    # Collected ONCE for the whole run — see _collect_live_cwds() docstring
    # for why (round-2 fix: calling lsof per-worktree could cost ~17min
    # cumulative worst-case across a large fleet).
    live_cwds = _collect_live_cwds()

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

        if _has_live_cwd(path, live_cwds):
            logger.info("KEEP %s — live process cwd inside (active)", path_str)
            kept_active += 1
            continue

        if age < max_age_hours * 3600:
            # Not old enough yet.
            continue

        slug = _slug(path_str)
        real_dirty = _has_real_dirty(path)
        is_detached = bool(e.get("detached"))

        # INVARIANT: this GC NEVER deletes a branch (no `git branch -D`/`-d`
        # anywhere in this file — grep to confirm). `git worktree remove`
        # only removes the WORKING DIRECTORY.
        #
        # Preservation runs on TWO INDEPENDENT tracks; either can veto the
        # remove. See module docstring rule 4 for the full rationale.

        # Track 1: real uncommitted work → stash-quarantine (any worktree).
        if real_dirty:
            if not _quarantine(path, slug, apply=apply):
                logger.warning("KEEP %s — quarantine failed, refusing to remove",
                               path_str)
                continue
            quarantined += 1

        # Track 2a: detached HEAD → UNCONDITIONAL durable ref to HEAD before
        # removal (BLOCKER B, round-2, 2026-07-18 — a clean detached-HEAD
        # worktree has no branch ref, and _quarantine()'s stash-create is
        # empty on a clean tree, so its commits would otherwise be orphaned).
        if is_detached:
            if not _preserve_detached_head(path, slug, apply=apply):
                logger.warning(
                    "KEEP %s — could not preserve detached HEAD, refusing "
                    "to remove", path_str,
                )
                continue
        else:
            # Track 2b: named branch → the branch ref already preserves
            # every commit (W88 cure, 2026-07-18): unpushed commits never
            # block removal, just get logged for operator awareness.
            unpushed = _unpushed_commits(path, e.get("branch"))
            if unpushed > 0:
                logger.warning(
                    "RECLAIM-DIR %s — branch '%s' retains %d commit(s) not "
                    "on origin/main; dir reclaimed to free disk, branch ref "
                    "PRESERVED (resume with: git worktree add %s %s)",
                    path_str, e.get("branch"), unpushed, path_str,
                    e.get("branch"),
                )
                reclaimed_unpushed += 1

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
