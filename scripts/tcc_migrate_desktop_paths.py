#!/usr/bin/env python3
"""Fleet migration: repoint HOME/repo payloads off ~/Desktop/nuzantara → ~/nuzantara.

W84 structural cure. ~/Desktop is one of macOS's three TCC-protected home folders
(Desktop/Documents/Downloads); the rest of $HOME is not. A payload that reaches into
~/Desktop needs a TCC grant that launchd can silently lose — observed 4× on M5, and
live right now in wr2-queue-pull ("mv: ... Operation not permitted" on a job launchd
still reports green). Outside ~/Desktop there is no grant to lose: the bug stops being
possible rather than being cured.

The fleet HOME side (~/scripts, ~/bin, ~/.local/bin, ~/.openclaw/bin, LaunchAgents) and
the repo checkout itself (mv + compat symlink) were already migrated live on all three
machines (2026-07-16). This tool's SECOND job — --git-scope — is the regeneration
source: 809 tracked files in the repo still hardcode `Desktop/nuzantara`, and sync
hooks (e.g. scripts/pro-mini-git-sync-hook.sh copying scripts/mini/mini-git-pull.sh
into ~/scripts/) reintroduce the old path into HOME the moment they run. Until the
repo itself is swept, the cure leaks.

Two scan modes:
  HOME roots (default, unchanged)  — bin/scripts/.local/bin/.openclaw/bin/LaunchAgents
  --git-scope                      — every `git ls-files`-tracked file under --repo-root
                                      (naturally skips .venv/.worktrees/node_modules —
                                      all gitignored, so git ls-files never lists them)

Safety:
  - text-only (UTF-8 decodable, <2MB); binaries skipped, never guessed at
  - archaeology skipped (.bak*/.old*/.pre-*/.patched-*, archive/ backup/ dirs)
  - `Desktop/nuzantara-deploy` is NOT swept by accident — the negative lookahead stops
    at a word char, so a sibling checkout stays an explicit decision (Pro has one)
  - --exclude-file <path>: newline-delimited repo-relative paths NEVER touched even if
    they match — the declared-exception mechanism for guard-test fixtures (scar #3:
    some Desktop paths are guilt/innocence corpus, not live payload) and deliberate
    historical record (scar files describing what WAS)
  - --apply writes a .bak-tcc-<date> beside each file it touches
  - idempotent: re-running finds nothing

Symlinks (2026-07-16, live gap found on Pro): a plain `if path.is_symlink(): continue`
would silently miss a link whose TARGET STRING crosses Desktop even though its content
is fine — exactly what happened to
`~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge-watchdog.plist`, a symlink
pointing at `/Users/nuzantara/Desktop/nuzantara/infra/launchagents/...`: launchd
resolves the link THROUGH ~/Desktop and stays TCC-exposed regardless of what the
target file says. This tool now treats a symlink as its own finding class: the raw
`os.readlink()` target string (never resolved/followed) is regex-checked and, under
--apply, the LINK is repointed (unlink + recreate with the corrected target) — the
file the link points at is never opened, read, or rewritten as a side effect of
walking the link (that would double-write it if the target is also visited directly
as its own path in the same scan).

Exit: 0 clean · 1 findings (--check) · 2 blind scan (0 files walked ≠ clean, W84 lesson)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Two checkouts live under ~/Desktop on Pro: `nuzantara` and the separate `nuzantara-deploy`
# clone (~20 cron depend on it — W81). Both move; both must be swept.
#
# Anchored so any OTHER sibling (`nuzantara-old`, `nuzantara-2`, ...) is NOT caught by
# accident: the segment must end right there (next char is neither word char nor hyphen).
#   Desktop/nuzantara/apps        -> nuzantara/apps          (alt 1, next is '/')
#   Desktop/nuzantara-deploy/x    -> nuzantara-deploy/x      (alt 1 fails on '-', alt 2 wins)
#   Desktop/nuzantara-old         -> untouched               (neither alt matches)
PATTERN = re.compile(r"Desktop/(nuzantara(?:-deploy)?)(?![-\w])")
REPLACEMENT = r"\1"

DEFAULT_ROOTS = ["bin", "scripts", ".local/bin", ".openclaw/bin", "Library/LaunchAgents"]

SKIP_SUFFIX_RE = re.compile(r"\.(bak|old|pre|patched|orig)[-.\w]*$|\.pre-[\w-]+$|\.old-[\w-]+$")
SKIP_DIR_PARTS = {"archive", "backup", "node_modules", ".git", "__pycache__", ".worktrees", ".venv"}
MAX_BYTES = 2 * 1024 * 1024


def _skip(path: Path, relparts: tuple[str, ...] | None = None) -> str | None:
    """relparts: path components relative to the SCAN ROOT (home or repo_root), not
    the absolute filesystem path. Required when the scan runs from inside a worktree
    (`.worktrees/<lane>/...` is then part of every absolute path's ancestry — checking
    absolute parts would archaeology-skip every single file).

    The size check is skipped for symlinks: Path.stat() FOLLOWS the link, so a
    symlink whose target doesn't exist on disk (legitimate — launchd resolves
    the link string regardless of whether the target is currently reachable)
    would raise FileNotFoundError and get misclassified as "stat-failed" skip.
    We never read symlink target bytes as file content, so a size cap is moot."""
    parts = relparts if relparts is not None else path.parts
    if any(p in SKIP_DIR_PARTS for p in parts):
        return "archaeology-dir"
    if SKIP_SUFFIX_RE.search(path.name):
        return "archaeology-suffix"
    if path.is_symlink():
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            return "too-big"
    except OSError as e:
        return f"stat-failed:{e.__class__.__name__}"
    return None


def _read_text(path: Path) -> str | None:
    """Return text, or None if binary/unreadable. Never guesses at bytes."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _rewrite(path: Path, text: str, stamp: str) -> None:
    """Rewrite in place, preserving the original mode.

    Some payloads are deliberately 0555 (read-only). We own them, so widen just long
    enough to write and put the exact original mode back — a migration must not quietly
    leave a hardened file writable behind it.
    """
    mode = path.stat().st_mode
    widened = False
    try:
        if not os.access(path, os.W_OK):
            os.chmod(path, mode | 0o200)
            widened = True
        shutil.copy2(path, path.with_name(path.name + f".bak-tcc-{stamp}"))
        path.write_text(PATTERN.sub(REPLACEMENT, text), encoding="utf-8")
    finally:
        if widened:
            os.chmod(path, mode)


def _rewrite_symlink(path: Path, target: str, stamp: str) -> None:
    """Repoint a symlink whose raw target string crosses Desktop/nuzantara.

    The backup is itself a symlink to the OLD target (not a content copy — copying
    "through" the link would silently swap to following-semantics and back up the
    wrong thing). Uses os.path.lexists (not Path.exists, which follows the link and
    reports False for an already-broken target) to detect a pre-existing backup.
    """
    backup = path.with_name(path.name + f".bak-tcc-{stamp}")
    if not os.path.lexists(backup):
        os.symlink(target, backup)
    new_target = PATTERN.sub(REPLACEMENT, target)
    path.unlink()
    path.symlink_to(new_target)


def _git_tracked_files(repo_root: Path) -> list[Path] | None:
    """`git ls-files` under repo_root, absolute paths. None on git failure (never
    silently returns empty — that would masquerade as a blind scan, not a real one)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"git ls-files failed to run: {e}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(f"git ls-files exited {proc.returncode}: {proc.stderr.strip()[:200]}", file=sys.stderr)
        return None
    return [repo_root / rel for rel in proc.stdout.splitlines() if rel]


def _load_exclude(exclude_file: Path | None, repo_root: Path) -> set[Path]:
    if exclude_file is None:
        return set()
    out: set[Path] = set()
    for line in exclude_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add((repo_root / line).resolve())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="rewrite in place (default: report only)")
    ap.add_argument("--check", action="store_true", help="exit 1 if any payload still cites the old path")
    ap.add_argument("--roots", nargs="*", default=None, help="HOME-mode: roots relative to $HOME")
    ap.add_argument("--home", default=str(Path.home()), help="home dir (for testing)")
    ap.add_argument("--git-scope", action="store_true",
                     help="scan git-tracked files under --repo-root instead of HOME roots")
    ap.add_argument("--repo-root", default=".", help="git-scope: repo root (default cwd)")
    ap.add_argument("--extensions", default=None,
                     help="git-scope: comma-separated suffixes to include, e.g. .sh,.py,.plist "
                          "(default: all tracked files)")
    ap.add_argument("--exclude-file", default=None,
                     help="newline-delimited repo-relative paths to never touch/report "
                          "(declared exceptions — guard-test fixtures, historical record)")
    args = ap.parse_args(argv)

    stamp = _dt.datetime.now().strftime("%Y%m%d")
    walked = 0
    hits: list[tuple[Path, int]] = []
    changed: list[tuple[Path, int]] = []
    skipped_binary: list[Path] = []
    failed: list[tuple[Path, str]] = []

    if args.git_scope:
        base = Path(args.repo_root).resolve()
        exclude = _load_exclude(Path(args.exclude_file).resolve() if args.exclude_file else None, base)
        tracked = _git_tracked_files(base)
        if tracked is None:
            print("BLIND SCAN: git ls-files failed — not a clean result.", file=sys.stderr)
            return 2
        exts = None
        if args.extensions:
            exts = {e if e.startswith(".") else f".{e}" for e in args.extensions.split(",")}
        candidates = []
        for path in sorted(tracked):
            if exts is not None and path.suffix.lower() not in exts:
                continue
            if path.resolve() in exclude:
                continue
            candidates.append(path)
    else:
        base = Path(args.home).resolve()
        roots = [base / r for r in (args.roots or DEFAULT_ROOTS)]
        candidates = []
        for root in roots:
            if not root.exists():
                print(f"  (root absent, skipped: {root})")
                continue
            candidates.extend(p for p in sorted(root.rglob("*")))

    for path in candidates:
        # relparts = path components relative to the SCAN ROOT, not the absolute
        # filesystem path — required so a scan run from inside a worktree doesn't see
        # ".worktrees" in every ancestor and archaeology-skip everything (live bug,
        # caught before shipping: candidates built as base/rel, so this never resolves
        # through a symlink in the final component).
        relparts = path.relative_to(base).parts

        if path.is_symlink():
            # A symlink's TARGET STRING can cross Desktop even when its content (if
            # followed) would look fine — launchd resolves the link, not the content.
            # Never follow it: read the raw target only, never open/rewrite what it
            # points at as a side effect of walking the link.
            if _skip(path, relparts):
                continue
            try:
                target = os.readlink(path)
            except OSError:
                continue
            walked += 1
            n = len(PATTERN.findall(target))
            if not n:
                continue
            hits.append((path, n))
            if args.apply:
                try:
                    _rewrite_symlink(path, target, stamp)
                except OSError as e:
                    failed.append((path, f"{e.__class__.__name__}: {e.strerror or e}"))
                    continue
                changed.append((path, n))
            continue

        if not path.is_file():
            continue
        if _skip(path, relparts):
            continue
        walked += 1
        text = _read_text(path)
        if text is None:
            # A binary could still embed the path, but rewriting bytes blind is how you
            # corrupt a payload. Surface it; never silently "handle" it.
            if PATTERN.search(str(path)):
                skipped_binary.append(path)
            continue
        n = len(PATTERN.findall(text))
        if not n:
            continue
        hits.append((path, n))
        if args.apply:
            try:
                _rewrite(path, text, stamp)
            except OSError as e:
                # One unwritable file must never abort the sweep: a half-swept fleet is
                # worse than a reported one. Collect and surface at the end.
                failed.append((path, f"{e.__class__.__name__}: {e.strerror or e}"))
                continue
            changed.append((path, n))

    # W84/W97 lesson: a scan that walked nothing is not a clean scan. Fail loud.
    if walked == 0:
        print("BLIND SCAN: 0 files walked — TCC block or wrong roots, NOT a clean result.", file=sys.stderr)
        return 2

    verb = "rewrote" if args.apply else "would rewrite"
    total = sum(n for _, n in hits)
    for path, n in hits:
        print(f"  {n:3d} hit  {path}")
    if skipped_binary:
        print("\n  !! binary payloads citing the path (NOT touched — handle by hand):")
        for p in skipped_binary:
            print(f"     {p}")
    if failed:
        print("\n  !! FAILED to rewrite (still on the old path — handle by hand):")
        for p, why in failed:
            print(f"     {p}  [{why}]")
    print(f"\n{verb} {len(changed) if args.apply else len(hits)} file(s) / {total} occurrence(s); "
          f"{walked} file(s) walked; {len(failed)} failed.")

    if failed:
        return 1
    if args.check and hits:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
