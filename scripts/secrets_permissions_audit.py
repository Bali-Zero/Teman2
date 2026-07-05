#!/usr/bin/env python3
"""secrets_permissions_audit.py — superscar #4 "Secret in the clear" auditor.

Superscar #4 (see `.claude/rules/cicatrix-superscar.md`) is the family of
incidents where production credentials (DB passwords, API keys, SSH keys,
`.env` files) end up exposed on the filesystem with world/group-readable
permissions — bypassing the platform secret manager. Backup files (`.bak`,
`.bak-*`, `.orig`, trailing `~`) inherit the sensitivity of the file they
were copied from, and are a recurring source of forgotten-wide-open copies
(W65 skills-bridge `.bak`, P0 2026-05-21 postgres password in 32 files).

This script finds candidates for that failure mode by NAME/PATH PATTERN
ONLY. It never opens, reads, or prints the contents of any file it
inspects — only `os.lstat()` (permission bits) and path strings are
touched. That is a deliberate invariant: an audit tool for secrets must
not itself become a way to exfiltrate them (via stdout, logs, or a
transcript).

Usage:
    secrets_permissions_audit.py [--json] [--fix] [--root PATH ...]
                                  [--max-depth N]

Exit codes:
    Report mode (default): 0 if no findings, 1 if any findings.
    --fix mode:             0 if every finding was fixed (or none existed),
                             1 if any chmod failed.
    Either mode:            2 if the scan was BLIND (roots exist but zero
                             files traversed — TCC/sandbox denial): a blind
                             audit never certifies "clean" (W84 discipline).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import socket
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DEFAULT_MAX_DEPTH = 4

#: Directories os.walk should never descend into (heavy, irrelevant, or
#: themselves ephemeral caches — not sources of durable secret exposure).
PRUNE_DIR_NAMES = frozenset(
    {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "Cache",
        "Caches",
        "CachedData",
    }
)

#: Default scan roots (mirrors the machines' real credential locations).
#: ~/.env* is a top-level glob, not a literal directory, and is expanded
#: separately in default_roots().
_DEFAULT_ROOT_RELATIVE_PATHS: Tuple[str, ...] = (
    "~/.ssh",
    "~/.claude",
    "~/.claude-glm",
    "~/.claude-acct2",
    "~/.openclaw",
    "~/.config",
    "~/.fly",
    "~/scripts",
    "~/Library/LaunchAgents",
    "~/.nuzantara-cron",
)

#: Name globs (case-insensitive) that mark a file as credential-like.
SECRET_NAME_GLOBS: Tuple[str, ...] = (
    "*.env*",
    ".env*",
    "*secret*",
    "*token*",
    "*credential*",
    "*apikey*",
    "*api_key*",
    "*api-key*",
    "*password*",
    "*passwd*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "id_ecdsa*",
    "*keychain*",
    "*.netrc",
    ".netrc",
    ".npmrc",
    ".pypirc",
)

#: Name globs (case-insensitive) that are false positives and must never
#: be reported, even if they also match a SECRET_NAME_GLOBS pattern.
EXCLUDE_NAME_GLOBS: Tuple[str, ...] = (
    "*.pub",
    "known_hosts*",
    "*token_count*",
    "*tokenizer*",
)

#: Trailing backup-suffix pattern: ".bak", ".bak-<anything without / or .>",
#: ".orig", or a lone trailing "~". A backup inherits the sensitivity of
#: the file it was copied from, so we strip this and re-test the name.
_BACKUP_SUFFIX_RE = re.compile(r"(\.bak(?:-[^./]*)?|\.orig|~)$", re.IGNORECASE)

# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """A candidate file with a group/other-readable (or writable) mode."""

    path: Path
    mode: int  # permission bits only, e.g. 0o644 (see stat.S_IMODE)


# --------------------------------------------------------------------------
# Name/path pattern matching (pure string logic — no filesystem I/O)
# --------------------------------------------------------------------------


def _fnmatch_any(value: str, patterns: Sequence[str]) -> bool:
    """Case-insensitive fnmatch against any of `patterns`."""
    lowered = value.lower()
    return any(fnmatch.fnmatchcase(lowered, pattern.lower()) for pattern in patterns)


def strip_backup_suffix(name: str) -> str:
    """Strip a trailing backup suffix (.bak, .bak-*, .orig, ~) so the
    underlying base name can be re-tested for sensitivity. A backup file
    inherits the sensitivity of whatever it is a backup of.

    Applied iteratively (bounded) to catch chained suffixes such as
    "config.bak.orig" or "id_rsa.bak~".
    """
    result = name
    for _ in range(4):
        replaced = _BACKUP_SUFFIX_RE.sub("", result)
        if replaced == result or not replaced:
            break
        result = replaced
    return result


def is_candidate_path(path: Path) -> bool:
    """Return True if `path` looks credential-like by NAME/PATH ONLY.

    Never touches file contents. Checks the basename, its backup-stripped
    form (so `service.token.bak-20260101` is caught via `service.token`),
    and — as a fallback — the full path string (a containing directory
    can hint at sensitivity even when the basename alone does not).
    Exclusions (id_rsa.pub, known_hosts, tokenizer.*, *token_count*) win
    over any positive match, on the basename or its backup-stripped form.
    """
    name = path.name
    stripped = strip_backup_suffix(name)
    name_variants = {name} if stripped == name else {name, stripped}

    if any(_fnmatch_any(variant, EXCLUDE_NAME_GLOBS) for variant in name_variants):
        return False

    if any(_fnmatch_any(variant, SECRET_NAME_GLOBS) for variant in name_variants):
        return True

    return _fnmatch_any(str(path), SECRET_NAME_GLOBS)


# --------------------------------------------------------------------------
# Filesystem walk (depth-capped, symlink-safe)
# --------------------------------------------------------------------------


def _iter_candidate_paths_under_dir(
    root: Path, max_depth: int, stats: Optional[dict] = None
) -> Iterator[Path]:
    """Yield candidate-named file paths under a directory `root`.

    Depth 0 = files directly in `root`. Descent stops once a directory's
    depth reaches `max_depth` (files at that depth are still yielded; its
    subdirectories are not visited). Never follows symlinked directories.
    """
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel = Path(dirpath).relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)

        if depth >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if d not in PRUNE_DIR_NAMES]

        if stats is not None:
            stats["files_traversed"] = stats.get("files_traversed", 0) + len(filenames)
        for filename in filenames:
            candidate = Path(dirpath) / filename
            if is_candidate_path(candidate):
                yield candidate


def _iter_candidate_paths(
    roots: Iterable[Path], max_depth: int, stats: Optional[dict] = None
) -> Iterator[Path]:
    """Yield candidate-named file paths across all `roots`.

    A root may itself be a regular file (e.g. an expanded `~/.env*` glob
    hit) rather than a directory — handled directly rather than via
    os.walk (which yields nothing for a non-directory top). Roots that do
    not exist are skipped. Root-level symlinks are not followed.
    """
    seen_dirs: set = set()
    for raw_root in roots:
        root = Path(raw_root).expanduser()
        try:
            root_lstat = os.lstat(root)
        except OSError:
            continue  # doesn't exist — skip per spec

        if stat.S_ISLNK(root_lstat.st_mode):
            continue  # never follow symlinks, including at the root level

        if stats is not None:
            stats["roots_existing"] = stats.get("roots_existing", 0) + 1
        if stat.S_ISDIR(root_lstat.st_mode):
            key = os.path.abspath(root)
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            yield from _iter_candidate_paths_under_dir(root, max_depth, stats)
        elif stat.S_ISREG(root_lstat.st_mode):
            if stats is not None:
                stats["files_traversed"] = stats.get("files_traversed", 0) + 1
            if is_candidate_path(root):
                yield root
        # sockets/fifos/char-devices as roots: nothing sensible to scan


# --------------------------------------------------------------------------
# Core scan
# --------------------------------------------------------------------------


def scan(
    roots: Iterable[Path],
    max_depth: int = DEFAULT_MAX_DEPTH,
    stats: Optional[dict] = None,
) -> List[Finding]:
    """Scan `roots` for credential-like files with group/other permission
    bits set. Returns findings sorted by path. Never opens file contents —
    only os.lstat() (for mode + symlink/regular-file detection) is used.

    `stats` (optional dict) accumulates `roots_existing` and
    `files_traversed` so the caller can detect a BLIND scan (roots exist
    but zero files were walked — TCC/sandbox denial): a scan that cannot
    see must never certify "clean" (W84 dead-green discipline).
    """
    findings: List[Finding] = []
    seen_files: set = set()

    for candidate in _iter_candidate_paths(roots, max_depth, stats):
        key = os.path.abspath(candidate)
        if key in seen_files:
            continue
        seen_files.add(key)

        try:
            lst = os.lstat(candidate)
        except OSError:
            continue

        if not stat.S_ISREG(lst.st_mode):
            continue  # symlink, socket, fifo, etc. — skip, never follow

        mode_bits = stat.S_IMODE(lst.st_mode)
        if mode_bits & 0o077:
            findings.append(Finding(path=candidate, mode=mode_bits))

    findings.sort(key=lambda f: str(f.path))
    return findings


def default_roots() -> List[Path]:
    """The standard set of roots to audit on a Bali Zero fleet machine."""
    home = Path.home()
    roots = [Path(p).expanduser() for p in _DEFAULT_ROOT_RELATIVE_PATHS]
    roots.extend(sorted(home.glob(".env*")))
    return roots


# --------------------------------------------------------------------------
# --fix
# --------------------------------------------------------------------------


def fix_findings(findings: Sequence[Finding]) -> Tuple[int, int, List[str]]:
    """chmod every finding to 0o600 and verify via a fresh lstat.

    Returns (fixed_count, failed_count, failure_messages). Failure
    messages carry only the path and the exception CLASS NAME — never
    exception text that could echo file contents or other detail.
    """
    fixed = 0
    failed = 0
    failures: List[str] = []

    for finding in findings:
        try:
            os.chmod(finding.path, 0o600)
            verify = os.lstat(finding.path)
        except OSError as exc:
            failed += 1
            failures.append(f"{finding.path}: {type(exc).__name__}")
            continue

        if stat.S_IMODE(verify.st_mode) == 0o600:
            fixed += 1
        else:
            failed += 1
            failures.append(f"{finding.path}: ModeVerificationMismatch")

    return fixed, failed, failures


# --------------------------------------------------------------------------
# Machine label (mirror proprioception, see CLAUDE.md machine table)
# --------------------------------------------------------------------------


def machine_label(hostname: Optional[str] = None) -> str:
    """Map a hostname to the fleet's short machine label convention."""
    host = hostname if hostname is not None else socket.gethostname()
    lowered = host.lower()
    if "air-m5" in lowered:
        return "m5"
    if "mini" in lowered:
        return "mini"
    if lowered == "nuzantara":
        return "pro"
    return host


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _mode_octal(mode: int) -> str:
    return f"{mode:04o}"


def _finding_to_dict(finding: Finding) -> dict:
    return {"path": str(finding.path), "mode": _mode_octal(finding.mode)}


def resolve_roots(
    extra_roots: Optional[Sequence[str]], no_defaults: bool = False
) -> List[Path]:
    """Build the effective root list: defaults plus any --root additions.

    `no_defaults` drops the default set entirely (isolated scans, tests).
    """
    roots = [] if no_defaults else default_roots()
    if extra_roots:
        roots.extend(Path(r).expanduser() for r in extra_roots)
    return roots


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secrets_permissions_audit.py",
        description=(
            "Audit credential-like files for world/group-readable permissions "
            "(superscar #4 'Secret in the clear'). Finds by NAME/PATH pattern "
            "only — never opens or prints file contents."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--fix", action="store_true", help="chmod 0600 every finding.")
    parser.add_argument(
        "--no-default-roots",
        action="store_true",
        help="Scan ONLY the --root paths (drop the default fleet root set).",
    )
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=None,
        metavar="PATH",
        help="Additional root to scan (repeatable).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        help=f"Max walk depth below each root (default: {DEFAULT_MAX_DEPTH}).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    roots = resolve_roots(args.roots, no_defaults=args.no_default_roots)
    stats: dict = {}
    findings = scan(roots, max_depth=args.max_depth, stats=stats)

    roots_existing = stats.get("roots_existing", 0)
    files_traversed = stats.get("files_traversed", 0)
    # BLIND-scan guard (W84 dead-green): roots exist but the walk saw ZERO
    # files → TCC/sandbox/permission denial is hiding the world. A blind
    # audit must never certify "clean".
    blind = roots_existing > 0 and files_traversed == 0

    fixed: Optional[int] = None
    failed = 0
    failures: List[str] = []
    if args.fix and not blind:
        fixed, failed, failures = fix_findings(findings)

    if args.json:
        payload = {
            "schema": 1,
            "findings": [_finding_to_dict(f) for f in findings],
            "count": len(findings),
            "fixed": fixed,
            "machine": machine_label(),
            "roots_existing": roots_existing,
            "files_traversed": files_traversed,
            "blind": blind,
        }
        print(json.dumps(payload))
    else:
        for finding in findings:
            print(f"{_mode_octal(finding.mode)} {finding.path}")
        print(
            f"FINDINGS: {len(findings)} file(s) with group/other permissions "
            f"matching credential name patterns "
            f"(traversed {files_traversed} files under {roots_existing} roots)"
        )
        if blind:
            print(
                "BLIND SCAN — roots exist but zero files were traversed: the "
                "environment (TCC / sandbox / permissions) is hiding the "
                "filesystem. Result is NOT trustworthy; do not read as clean."
            )
        if args.fix and not blind:
            print(f"FIXED: {fixed}  FAILED: {failed}")
            for failure in failures:
                print(f"  ! {failure}")

    if blind:
        return 2
    if args.fix:
        return 0 if failed == 0 else 1
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
