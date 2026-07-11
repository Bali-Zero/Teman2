#!/usr/bin/env python3
"""arm_keep_worktrees.py — freeze uncommitted worktree work onto quarantine refs.

WHY THIS EXISTS (scar W80, 2026-06-28):
  A triage run marked two worktrees "KEEP" (live uncommitted work) — but "KEEP"
  is only a word. Between the analysis and the next reaper tick the worktree dirs
  were removed and the uncommitted work (~2400 lines of livekit runtime + agy
  migration) was lost, because nothing had ARMED it. The official reaper
  (worktree_gc_universal.py) DOES quarantine before removal, but a triage that
  hand-removes worktrees, or any window where a reaper fires async, bypasses it.

THE RULE: before ANY operation that may remove worktrees — a manual triage, a
cleanup sweep, a multi-agent disposition run — ARM the work first. Run this. It
captures every worktree's tracked+untracked changes (and any unpushed commits on
a detached HEAD) onto `refs/agent-quarantine/<slug>` PLUS a human-readable
`.agent-receipts/quarantine-<slug>.patch`, so the work survives even a blind
`rm -rf` of the dir. Idempotent and read-only to your working trees (it stages
then resets; it never commits to your branch or pushes).

USAGE:
  python scripts/arm_keep_worktrees.py            # arm ALL worktrees with dirty/unpushed work
  python scripts/arm_keep_worktrees.py --names a,b # arm only these worktree dir-names
  python scripts/arm_keep_worktrees.py --dry-run   # show what WOULD be armed
  python scripts/arm_keep_worktrees.py --list      # list existing quarantine refs (recovery)

RECOVERY (later):
  git stash apply <sha>                       # re-apply the captured tree onto a checkout
  git -C <fresh-worktree> apply .agent-receipts/quarantine-<slug>.patch
  git for-each-ref refs/agent-quarantine/     # browse what is frozen
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

QUARANTINE_REF_PREFIX = "refs/agent-quarantine"


def _repo_root() -> Path:
    # Resolve from this script's location — path-aware (M5 balizero vs Pro nuzantara,
    # superscar #1: never hardcode /Users/<name>).
    return Path(__file__).resolve().parent.parent


REPO_ROOT = _repo_root()


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        capture_output=True, text=True, timeout=60, check=False,
    )


def _slug(path: Path) -> str:
    # Canonicalize first: the same physical worktree must yield the SAME slug no
    # matter how the path was written (relative, trailing slash, or the macOS
    # /var → /private/var symlink). Otherwise the quarantine ref a reader looks
    # for (e.g. the arm-before-remove hook) misses the one the writer created,
    # and recovery silently breaks. resolve() with a fallback for non-existent
    # paths (dry-run / already-removed) so it never raises.
    try:
        canon = path.resolve()
    except Exception:
        canon = path
    return str(canon).strip("/").replace("/", "_")


def _worktrees() -> list[dict]:
    """Parse `git worktree list --porcelain` into dicts with path/branch/detached."""
    out = _git(["worktree", "list", "--porcelain"]).stdout
    entries: list[dict] = []
    cur: dict = {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur:
                entries.append(cur)
            cur = {"path": Path(line[len("worktree "):]), "branch": None, "detached": False}
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch "):]
        elif line.strip() == "detached":
            cur["detached"] = True
    if cur:
        entries.append(cur)
    # Only the managed agent worktrees under .worktrees/ — never the main checkout.
    return [e for e in entries if "/.worktrees/" in str(e["path"])]


def _dirty_count(wt: Path) -> int:
    r = _git(["status", "--porcelain"], cwd=wt)
    return len([ln for ln in r.stdout.splitlines() if ln.strip()])


def _unpushed(wt: Path, branch: str | None) -> int:
    if not branch:
        return 0
    short = branch.replace("refs/heads/", "")
    r = _git(["rev-list", "--count", f"origin/{short}..HEAD"], cwd=wt)
    try:
        return int(r.stdout.strip() or "0")
    except ValueError:
        return 0


def _arm_one(wt: Path, *, apply: bool) -> tuple[bool, str]:
    """Capture tracked+untracked into a quarantine ref + patch receipt. Best-effort."""
    slug = _slug(wt)
    ref = f"{QUARANTINE_REF_PREFIX}/{slug}"
    if not apply:
        return True, f"[dry-run] would arm {wt.name} -> {ref}"
    try:
        # Stage everything (incl. untracked) so `stash create` captures it, then
        # reset — your working tree is left exactly as it was.
        _git(["add", "-A"], cwd=wt)
        created = _git(["stash", "create", f"arm-keep {slug}"], cwd=wt)
        sha = created.stdout.strip()
        if sha:
            _git(["update-ref", ref, sha])
        # Human-readable receipt survives even if the ref is later pruned.
        # Use `stash show -p <sha>` (NOT `git diff HEAD`) so the patch includes
        # the UNTRACKED files captured by `add -A` + stash create — diff HEAD
        # would silently drop them (the exact gap that lost livekit's untracked
        # runtime files in scar W80).
        _git(["reset"], cwd=wt)  # unstage NOW — leave working tree untouched
        receipts = REPO_ROOT / ".agent-receipts"
        receipts.mkdir(exist_ok=True)
        # The stash-create commit has the pre-arm HEAD as a parent, so the full
        # captured change (tracked + untracked) == diff(sha^, sha). This is the
        # robust receipt — `git diff HEAD` would drop untracked (the W80 gap).
        patch = ""
        if sha:
            patch = _git(["diff", f"{sha}^", sha], cwd=wt).stdout
        if patch:
            (receipts / f"quarantine-{slug}.patch").write_text(patch)
        tag = sha[:10] if sha else "patch-only"
        return True, f"armed {wt.name} -> {ref} ({tag})"
    except Exception as exc:  # noqa: BLE001 — never crash, the point is to NOT lose work
        return False, f"FAILED to arm {wt.name}: {exc}"


def _list_quarantine() -> int:
    r = _git(["for-each-ref", QUARANTINE_REF_PREFIX,
              "--format=%(refname:short)  %(objectname:short)  %(creatordate:short)"])
    if not r.stdout.strip():
        print("no quarantine refs.")
        return 0
    print("Frozen worktree work (recover with `git stash apply <sha>`):")
    for ln in r.stdout.splitlines():
        print(f"  {ln}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="show what would be armed")
    ap.add_argument("--names", default="", help="comma-separated worktree dir-names to arm (default: all dirty/unpushed)")
    ap.add_argument("--list", action="store_true", help="list existing quarantine refs and exit")
    args = ap.parse_args(argv)

    if args.list:
        return _list_quarantine()

    only = {n.strip() for n in args.names.split(",") if n.strip()}
    apply = not args.dry_run

    targets = []
    for e in _worktrees():
        wt = e["path"]
        if only and wt.name not in only:
            continue
        dirty = _dirty_count(wt)
        unpushed = _unpushed(wt, e["branch"])
        # Arm anything with unsaved value: dirty working tree, or unpushed commits
        # (so a removed worktree's local-only commits are also captured).
        if dirty or unpushed:
            targets.append((wt, dirty, unpushed))

    if not targets:
        print("arm-keep: nothing to arm (no worktree has dirty/unpushed work).")
        return 0

    print(f"arm-keep: {'(dry-run) ' if args.dry_run else ''}arming {len(targets)} worktree(s)...")
    failures = 0
    for wt, dirty, unpushed in targets:
        ok, msg = _arm_one(wt, apply=apply)
        flag = "  ✓" if ok else "  ✗"
        print(f"{flag} {msg}  [dirty={dirty} unpushed={unpushed}]")
        if not ok:
            failures += 1

    if failures:
        print(f"\narm-keep: {failures} worktree(s) FAILED to arm — DO NOT remove those.", file=sys.stderr)
        return 1
    print("\narm-keep: all targets frozen. Safe to triage. Recover via `--list` + `git stash apply`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
