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
    secrets_permissions_audit.py [--json] [--fix] [--notify] [--root PATH ...]
                                  [--max-depth N]

Custody roots (2026-09-10 incident): a directory named like
~/nuzantara/.secrets is judged by the FILE's own mode — any group/other
bit is a finding whatever the directory chain says; the chain is one
chmod away from opening, the file modes are the invariant the owner
restored by hand. Custody and `.env*` findings are REPORT-ONLY: printed
for a human, never chmod'ed — `--fix` refuses, by name, any file under a
`.secrets` directory and any `.env*` file. Credentials stay with the
human (Builder Contract rule 5); automated edits of `.env*` are
off-limits in this repo.

`--notify` (the LaunchAgent mode) hands findings to the Telegram gateway
(`tg_notify.py`) instead of printing them for a human, and wraps the normal
report in a run record. Never chmods anything; mutually exclusive with
`--fix` (argparse error, exit 2 for the pair).

Exit codes:
    Report mode (default): 0 if no findings, 1 if any findings.
    --fix mode:             0 only if nothing failed AND no report-only
                             finding remains, else 1.
    --notify mode:          1 if any alert could not be handed to the
                             gateway, else 0 — findings themselves leave
                             through the gateway, so this code is reserved
                             for "could not speak", not "found something".
    Either mode:            2 if the scan was BLIND (roots exist but zero
                             files traversed — TCC/sandbox denial, or a
                             custody directory that cannot be listed): a
                             blind audit never certifies "clean" (W84
                             discipline); with --notify the alert is still
                             sent.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import socket
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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
        "tmp",
        "jiti",
    }
)

#: Default scan roots (mirrors the machines' real credential locations).
#: ~/.env* is a top-level glob, not a literal directory, and is expanded
#: separately in default_roots().
_DEFAULT_ROOT_RELATIVE_PATHS: Tuple[str, ...] = (
    "~/.ssh",
    "~/.claude",
    "~/.claude-acct2",
    "~/.kimi-code",
    "~/.qwen",
    "~/.openclaw",
    "~/.config",
    "~/.fly",
    "~/scripts",
    "~/Library/LaunchAgents",
    "~/.nuzantara-cron",
    # Main checkout's credential directory (2026-09-10: found loosened,
    # restored by hand — the auditor never looked here: root was missing).
    # Relative to HOME so it is the same on every node; skipped if absent.
    "~/nuzantara/.secrets",
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
#: The last five are the measured 2026-09-10 Pro false positives and no
#: wider: `.env` TEMPLATES (a plugin's .env.example) and usage-accounting
#: jsonl logs (token-usage-2026-09.jsonl, same family as *token_count*).
#: Kept this narrow on purpose — `id_rsa.example`, `token-usage.pem` or
#: `credentials.json.template` are still candidates. Never applied inside custody.
EXCLUDE_NAME_GLOBS: Tuple[str, ...] = (
    "*.pub",
    "known_hosts*",
    "*token_count*",
    "*tokenizer*",
    "*token-usage*.jsonl",
    "*token_usage*.jsonl",
    ".env*.example",
    ".env*.sample",
    ".env*.template",
)

#: Directory basenames (compared lower-case) that mark a credential CUSTODY
#: directory: inside one EVERY file is a credential and its own mode is the
#: invariant — no name filter, no exclusion, no chain (see scan strict).
CUSTODY_DIR_NAMES = frozenset({".secrets"})

#: `.env*` files are report-only: shown for a human, never chmod'ed.
ENV_NAME_GLOBS: Tuple[str, ...] = (".env*", "*.env*")

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
    # Custody: judged by the file's own mode alone — the directory chain
    # is one chmod away from opening (2026-09-10).
    custody: bool = False
    # Custody or `.env*`: reported for a human, never chmod'ed.
    # fix_findings honours this flag AND re-checks the name.
    report_only: bool = False


@dataclass(frozen=True)
class CustodyRootReport:
    """Per-custody-root summary for main() (text line and JSON entry)."""

    root: Path
    files_traversed: int
    findings: int
    dir_mode: Optional[str]  # octal string, e.g. "0700"; None if unstatable
    blind: bool  # dir exists but os.listdir raised — the walk saw nothing


@dataclass(frozen=True)
class AuditResult:
    """Merged custody (strict) + plain (reachability) scan result."""

    findings: List[Finding]
    custody: List[CustodyRootReport]
    roots_existing: int
    files_traversed: int
    blind: bool


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


def is_custody_root(root: Path) -> bool:
    """True when the NAMED root's basename (after expanduser, BEFORE any
    symlink resolution) marks a credential custody directory.

    WHY custody: the file's own mode decides inside one, not the directory
    chain — the chain is one chmod away from opening, so an audit that
    waits for it reports the exposure one mistake late (2026-09-10: a
    0644 probe inside a still-closed .secrets read count: 0).
    """
    return Path(root).expanduser().name.lower() in CUSTODY_DIR_NAMES


def is_env_shaped(path: Path) -> bool:
    """True when the basename — or its backup-stripped form — matches an
    `.env*` glob. Same helpers as is_candidate_path, case-insensitive.

    `.env*` files are off-limits to automated edits in this repo: their
    modes are reported for a human, never fixed.
    """
    name = path.name
    stripped = strip_backup_suffix(name)
    variants = {name} if stripped == name else {name, stripped}
    return any(_fnmatch_any(variant, ENV_NAME_GLOBS) for variant in variants)


def is_under_custody(path: Path) -> bool:
    """True when any directory above `path` is named like a custody root —
    whether the caller NAMED that root or the walk merely met it.

    Credentials stay with the human (Builder Contract rule 5): a file under
    a `.secrets` directory is reported, never chmod'ed. Checked by name so
    fix_findings needs nothing but the path.
    """
    return any(part.lower() in CUSTODY_DIR_NAMES for part in Path(path).parent.parts)


# --------------------------------------------------------------------------
# Filesystem walk (depth-capped, symlink-safe)
# --------------------------------------------------------------------------


def _iter_candidate_paths_under_dir(
    root: Path, max_depth: int, stats: Optional[dict] = None, all_files: bool = False
) -> Iterator[Path]:
    """Yield candidate-named file paths under a directory `root`.

    Depth 0 = files directly in `root`. Descent stops once a directory's
    depth reaches `max_depth` (files at that depth are still yielded; its
    subdirectories are not visited). Never follows symlinked directories.

    `all_files` (a custody root, possibly reached through a symlink that
    dropped the `.secrets` name) yields every file and prunes nothing; a
    `.secrets` directory met during an ordinary walk gets the same.
    """
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel = Path(dirpath).relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)

        if depth >= max_depth:
            dirnames[:] = []
        elif not all_files:
            dirnames[:] = [d for d in dirnames if d not in PRUNE_DIR_NAMES]

        if stats is not None:
            stats["files_traversed"] = stats.get("files_traversed", 0) + len(filenames)
        for filename in filenames:
            candidate = Path(dirpath) / filename
            if all_files or is_under_custody(candidate) or is_candidate_path(candidate):
                yield candidate


def _iter_candidate_paths(
    roots: Iterable[Path],
    max_depth: int,
    stats: Optional[dict] = None,
    all_files: bool = False,
) -> Iterator[Path]:
    """Yield candidate-named file paths across all `roots`.

    A root may itself be a regular file (e.g. an expanded `~/.env*` glob
    hit) rather than a directory — handled directly rather than via
    os.walk (which yields nothing for a non-directory top). Roots that do
    not exist are skipped.

    A root that IS a symlink is resolved once and its target audited. A
    root is NAMED by the caller; a link met during the walk is not, and
    only the latter is a way for the walk to be lured out of the tree it
    was asked to audit. Dropping a named root silently is how this tool
    certified "clean" for the fleet's own memory directory — reached
    through two symlinks — while looking at zero files: with no root
    counted, the blind-scan guard could not fire either. Broken or
    looping links are treated exactly like a path that does not exist.
    """
    seen_dirs: set = set()
    for raw_root in roots:
        root = Path(raw_root).expanduser()
        try:
            root_lstat = os.lstat(root)
        except OSError:
            continue  # doesn't exist — skip per spec

        if stat.S_ISLNK(root_lstat.st_mode):
            try:
                resolved = Path(os.path.realpath(root))
                root_lstat = os.stat(resolved)
            except OSError:
                continue  # broken or looping — same as a missing path
            root = resolved

        if stats is not None:
            stats["roots_existing"] = stats.get("roots_existing", 0) + 1
        if stat.S_ISDIR(root_lstat.st_mode):
            key = os.path.realpath(root)
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            yield from _iter_candidate_paths_under_dir(
                root, max_depth, stats, all_files
            )
        elif stat.S_ISREG(root_lstat.st_mode):
            if stats is not None:
                stats["files_traversed"] = stats.get("files_traversed", 0) + 1
            if all_files or is_candidate_path(root):
                yield root
        # sockets/fifos/char-devices as roots: nothing sensible to scan


# --------------------------------------------------------------------------
# Core scan
# --------------------------------------------------------------------------


def _dir_traversal(
    directory: str, cache: Optional[dict] = None
) -> Tuple[bool, bool]:
    """(group_can_traverse, other_can_traverse) for ONE directory.

    On any stat error the answer is (True, True): a guard that could not
    verify must never absolve (W106b — CANNOT-VERIFY is not the same as
    clean).

    `cache` is supplied by the caller and lives for exactly one scan — a
    fleet walk crosses ~90k files over a few hundred directories, so the
    saving is real, but a cache that outlived the scan would be a stored
    answer about a world that can change under it. Same reason the default
    is None rather than a shared dict.
    """
    if cache is not None:
        hit = cache.get(directory)
        if hit is not None:
            return hit
    try:
        mode = stat.S_IMODE(os.stat(directory).st_mode)
        result = (bool(mode & stat.S_IXGRP), bool(mode & stat.S_IXOTH))
    except OSError:
        result = (True, True)
    if cache is not None:
        cache[directory] = result
    return result


def reachable_by(path: Path, cache: Optional[dict] = None) -> Tuple[bool, bool]:
    """(group, other) — can each actually walk down to this file?

    A 0644 file inside a 0700 directory is NOT in the clear: nobody but the
    owner can reach it. Judging the file's own mode alone answers a narrower
    question than the one this tool exists to ask, and the gap is not
    academic — it shows up as a permanent stream of findings for files that
    cannot be read by anyone, which is precisely how a guard's output stops
    being read at all (superscar #2). Every directory from the file up to the
    root must permit traversal, so one tight directory anywhere in the chain
    is enough to close the path.

    DECLARED LIMIT: this follows the resolved path only. A hard link to the
    same inode from a permissive directory would still be reachable and this
    function cannot see it — hard links are outside what a path-based audit
    can answer, and saying so here is cheaper than implying otherwise.
    """
    group = other = True
    try:
        directory = path.parent.resolve()
    except OSError:
        return (True, True)
    while True:
        can_group, can_other = _dir_traversal(str(directory), cache)
        group = group and can_group
        other = other and can_other
        if not (group or other) or directory.parent == directory:
            return (group, other)
        directory = directory.parent


def scan(
    roots: Iterable[Path],
    max_depth: int = DEFAULT_MAX_DEPTH,
    stats: Optional[dict] = None,
    strict: bool = False,
) -> List[Finding]:
    """Scan `roots` for credential-like files with group/other permission
    bits set. Returns findings sorted by path. Never opens file contents —
    only os.lstat() (for mode + symlink/regular-file detection) is used.

    `stats` (optional dict) accumulates `roots_existing` and
    `files_traversed` so the caller can detect a BLIND scan (roots exist
    but zero files were walked — TCC/sandbox denial): a scan that cannot
    see must never certify "clean" (W84 dead-green discipline).

    `strict` (custody semantics, used by audit() for custody roots):
    every file under the root is a candidate, reachability is skipped —
    any group/other bit on the file is a finding whatever the chain says —
    and findings are `custody=True`. A file under a `.secrets` directory
    met during an ordinary walk is judged the same way. A custody file
    that cannot be lstat'ed is counted in stats["unreadable"]: audit()
    turns that into BLIND, never "clean".
    """
    findings: List[Finding] = []
    seen_files: set = set()
    traversal_cache: dict = {}  # one scan's worth — see _dir_traversal

    for candidate in _iter_candidate_paths(roots, max_depth, stats, strict):
        key = os.path.abspath(candidate)
        if key in seen_files:
            continue
        seen_files.add(key)

        custody = strict or is_under_custody(candidate)
        try:
            lst = os.lstat(candidate)
        except OSError:
            if custody and stats is not None:
                stats["unreadable"] = stats.get("unreadable", 0) + 1
            continue

        if not stat.S_ISREG(lst.st_mode):
            continue  # symlink, socket, fifo, etc. — skip, never follow

        mode_bits = stat.S_IMODE(lst.st_mode)
        if not mode_bits & 0o077:
            continue

        if custody:
            # Custody semantics: the file's own mode is the invariant.
            exposed = True
        else:
            # The mode says who MAY read; the directory chain says who can
            # get here at all. Both have to be true for exposure.
            can_group, can_other = reachable_by(candidate, traversal_cache)
            exposed = (bool(mode_bits & 0o070) and can_group) or (
                bool(mode_bits & 0o007) and can_other
            )
        if exposed:
            findings.append(
                Finding(
                    path=candidate,
                    mode=mode_bits,
                    custody=custody,
                    report_only=custody or is_env_shaped(candidate),
                )
            )

    findings.sort(key=lambda f: str(f.path))
    return findings


def default_roots() -> List[Path]:
    """The standard set of roots to audit on a Bali Zero fleet machine."""
    home = Path.home()
    roots = [Path(p).expanduser() for p in _DEFAULT_ROOT_RELATIVE_PATHS]
    roots.extend(sorted(home.glob(".env*")))
    return roots


# --------------------------------------------------------------------------
# audit — custody roots one-by-one in strict mode, everything else together
# --------------------------------------------------------------------------


def audit(
    roots: Sequence[Path], max_depth: int = DEFAULT_MAX_DEPTH
) -> AuditResult:
    """Scan `roots` with custody semantics: custody roots one-by-one in
    strict mode (the file's own mode decides, whatever the chain), all
    other roots together with reachability. Findings merge, deduped by
    os.path.abspath with the custody finding winning. `blind` is True
    when roots exist but zero files were traversed, or any custody
    directory cannot be listed (W84: a blind audit never certifies clean).
    """
    merged: dict = {}
    reports: List[CustodyRootReport] = []
    total_roots_existing = 0
    total_files = 0
    unreadable = 0

    custody_roots = [r for r in roots if is_custody_root(r)]
    plain_roots = [r for r in roots if not is_custody_root(r)]

    seen_custody: set = set()
    for raw_root in custody_roots:
        root = Path(raw_root).expanduser()
        try:
            root_stat = os.stat(root)
        except (FileNotFoundError, NotADirectoryError):
            continue  # a custody root that does not exist is omitted
        except OSError:
            # Exists but cannot be stat'ed (EACCES on the chain): BLIND.
            reports.append(CustodyRootReport(root, 0, 0, None, True))
            continue
        if not stat.S_ISDIR(root_stat.st_mode):
            continue
        key = os.path.realpath(root)
        if key in seen_custody:
            continue  # named twice (default + --root): one report, not two
        seen_custody.add(key)
        stats: dict = {}
        findings = scan([root], max_depth=max_depth, stats=stats, strict=True)
        for finding in findings:
            merged[os.path.abspath(finding.path)] = finding  # custody wins
        try:
            os.listdir(root)
            blind_dir = stats.get("unreadable", 0) > 0
        except OSError:
            blind_dir = True
        dir_mode: Optional[str] = _mode_octal(stat.S_IMODE(root_stat.st_mode))
        reports.append(
            CustodyRootReport(
                root=root,
                files_traversed=stats.get("files_traversed", 0),
                findings=len(findings),
                dir_mode=dir_mode,
                blind=blind_dir,
            )
        )
        total_roots_existing += stats.get("roots_existing", 0)
        total_files += stats.get("files_traversed", 0)

    if plain_roots:
        stats = {}
        findings = scan(plain_roots, max_depth=max_depth, stats=stats)
        for finding in findings:
            merged.setdefault(os.path.abspath(finding.path), finding)
        total_roots_existing += stats.get("roots_existing", 0)
        total_files += stats.get("files_traversed", 0)
        unreadable += stats.get("unreadable", 0)

    blind = (
        (total_roots_existing > 0 and total_files == 0)
        or unreadable > 0
        or any(r.blind for r in reports)
    )
    return AuditResult(
        findings=sorted(merged.values(), key=lambda f: str(f.path)),
        custody=reports,
        roots_existing=total_roots_existing,
        files_traversed=total_files,
        blind=blind,
    )


# --------------------------------------------------------------------------
# --fix
# --------------------------------------------------------------------------


def fix_findings(findings: Sequence[Finding]) -> Tuple[int, int, List[str]]:
    """chmod every finding to 0o600 — except custody and `.env*` files,
    which are never touched, and anything that is not a regular file (a
    symlink would hand the chmod to its target) — and verify via lstat.

    Returns (fixed_count, failed_count, failure_messages). Failure
    messages carry only the path and the exception CLASS NAME — never
    exception text that could echo file contents or other detail.
    """
    fixed = 0
    failed = 0
    failures: List[str] = []

    for finding in findings:
        if (
            finding.custody
            or finding.report_only
            or is_env_shaped(finding.path)
            or is_under_custody(finding.path)
        ):
            # Custody and `.env*` are report-only: never chmod'ed, counted
            # by main(). The flag covers a custody root reached through a
            # symlink (its path lost the name); the NAME covers a hand-built
            # Finding — either one is enough to skip.
            continue
        try:
            if not stat.S_ISREG(os.lstat(finding.path).st_mode):
                failed += 1
                failures.append(f"{finding.path}: NotARegularFile")
                continue
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
# --notify: findings -> Telegram alerts. Text carries ONLY machine label,
# directory (HOME shown as ~), count and mode class — never a file name,
# never contents (Builder Contract rule 4).
# --------------------------------------------------------------------------


#: (class name, permission bit), in the fixed order every alert text uses.
_MODE_CLASS_BITS: Tuple[Tuple[str, int], ...] = (
    ("group-read", 0o040),
    ("group-write", 0o020),
    ("group-exec", 0o010),
    ("other-read", 0o004),
    ("other-write", 0o002),
    ("other-exec", 0o001),
)


def mode_classes(mode: int) -> List[str]:
    """Permission bits -> class names, in the fixed `_MODE_CLASS_BITS`
    order. Pure: no filesystem I/O, no knowledge of a Finding."""
    return [name for name, bit in _MODE_CLASS_BITS if mode & bit]


def _home_relative(path: object) -> str:
    """Render a path with HOME collapsed to `~` — same convention the text
    report already uses for CUSTODY lines, reused here so an alert never
    spells out the home directory's real name."""
    home = str(Path.home())
    shown = str(path)
    if shown == home:
        return "~"
    if shown.startswith(home + os.sep):
        return "~" + shown[len(home):]
    return shown


def _union_classes(findings: Sequence[Finding]) -> List[str]:
    """Union of mode_classes() across `findings`, in the fixed class order
    — not the order the findings happen to be listed in."""
    present = set()
    for finding in findings:
        present.update(mode_classes(finding.mode))
    return [name for name, _bit in _MODE_CLASS_BITS if name in present]


@dataclass(frozen=True)
class Alert:
    """One outbound Telegram alert, ready for send_alerts()."""

    tier: str
    dedup_key: str
    text: str


def build_alerts(result: AuditResult, machine: str) -> List[Alert]:
    """Findings -> at most two alerts: one CUSTODY p0 (every custody
    finding plus every blind custody root) and one `.env*`-modes digest
    (every other report-only finding, grouped by parent directory). An
    ordinary finding (neither custody nor report-only) raises no alert —
    it is still printed in the run's report lines. Pure: takes an
    already-computed AuditResult, does no I/O of its own.
    """
    alerts: List[Alert] = []

    # Grouped by the finding's own directory, not by the named root: a
    # custody root reached through a symlink, or a .secrets directory met
    # during a walk, yields findings under no CustodyRootReport root.
    groups: dict = {}  # parent dir (home-relative) -> [Finding, ...]
    for finding in result.findings:  # path-sorted already
        if finding.custody:
            groups.setdefault(_home_relative(finding.path.parent), []).append(finding)
    clauses = [
        f"{parent} — {len(group)} credential file(s) open beyond the "
        f"owner ({', '.join(_union_classes(group))})"
        for parent, group in groups.items()
    ]
    clauses += [
        f"{_home_relative(r.root)} — directory cannot be listed: custody NOT verified"
        for r in result.custody
        if r.blind
    ]

    if clauses:
        body = "; ".join(clauses)
        body += "; custody expects dir 0700, files 0600/0400." if groups else "."
        alerts.append(
            Alert(
                tier="p0",
                dedup_key="secrets-audit:secrets-dir",
                text=f"secrets-audit [{machine}]: {body}",
            )
        )

    env_findings = [f for f in result.findings if f.report_only and not f.custody]
    if env_findings:
        groups = {}  # parent dir (home-relative) -> [Finding, ...]
        for finding in env_findings:  # result.findings is path-sorted already
            groups.setdefault(_home_relative(finding.path.parent), []).append(finding)
        parts = [
            f"{parent} ({len(group)}, {', '.join(_union_classes(group))})"
            for parent, group in groups.items()
        ]
        text = (
            f"secrets-audit [{machine}]: .env* modes — {len(env_findings)} "
            f"file(s) readable beyond the owner (report-only: never opened, "
            f"never chmod'ed): " + ", ".join(parts) + "."
        )
        alerts.append(Alert(tier="digest", dedup_key="secrets-audit:env-modes", text=text))

    return alerts


def send_alerts(alerts: Sequence[Alert]) -> Tuple[int, List[str]]:
    """Hand each alert to tg_notify.py's frozen CLI:
    `tg_notify.py --tier <t> --source secrets-audit --dedup-key <k> "<text>"`.
    Never shell=True. Returns (handed_over, failures); a failure is recorded
    as "<tier>: <exception class name or rc=N>" — never the alert text.

    `<gateway>` = env SECRETS_AUDIT_TG_NOTIFY when set (tests point it at a
    fake script — the real tg_notify.py sends real Telegram messages and
    must never run under test), else the real tg_notify.py next to this
    file.
    """
    gateway = os.environ.get("SECRETS_AUDIT_TG_NOTIFY") or str(
        Path(__file__).resolve().parent / "tg_notify.py"
    )
    handed = 0
    failures: List[str] = []
    for alert in alerts:
        cmd = [
            sys.executable,
            gateway,
            "--tier", alert.tier,
            "--source", "secrets-audit",
            "--dedup-key", alert.dedup_key,
            alert.text,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            failures.append(f"{alert.tier}: TimeoutExpired")
            continue
        except OSError as exc:
            failures.append(f"{alert.tier}: {type(exc).__name__}")
            continue
        if proc.returncode != 0:
            failures.append(f"{alert.tier}: rc={proc.returncode}")
            continue
        handed += 1
    return handed, failures


def _run_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_launcher() -> str:
    """launchd when launchd is our direct parent (ppid 1); shell otherwise
    — a plain interactive or CI invocation."""
    return "launchd" if os.getppid() == 1 else "shell"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _mode_octal(mode: int) -> str:
    return f"{mode:04o}"


def _finding_to_dict(finding: Finding) -> dict:
    return {
        "path": str(finding.path),
        "mode": _mode_octal(finding.mode),
        "custody": finding.custody,
        "report_only": finding.report_only,
    }


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
    parser.add_argument("--fix", action="store_true", help="chmod 0600 every ordinary finding (custody and .env* stay report-only).")
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Hand findings to the Telegram gateway and print a run record — the LaunchAgent mode.",
    )
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

    if args.notify and args.fix:
        parser.error("--notify and --fix are mutually exclusive")

    roots = resolve_roots(args.roots, no_defaults=args.no_default_roots)
    result = audit(roots, max_depth=args.max_depth)

    findings = result.findings
    roots_existing = result.roots_existing
    files_traversed = result.files_traversed
    # BLIND-scan guard (W84 dead-green): roots exist but the walk saw ZERO
    # files, or a custody directory cannot be listed. Never certify "clean".
    blind = result.blind
    report_only = sum(1 for f in findings if f.report_only)

    fixed: Optional[int] = None
    failed = 0
    failures: List[str] = []
    if args.fix and not blind:
        fixed, failed, failures = fix_findings(findings)

    # --notify: build + send alerts regardless of `blind` (a blind custody
    # root is itself alert-worthy — "the alert is still sent").
    alerts: List[Alert] = []
    handed = 0
    notify_failures: List[str] = []
    run_ts = run_machine = run_launcher = run_service = None
    run_ppid: Optional[int] = None
    if args.notify:
        run_ts = _run_timestamp()
        run_machine = machine_label()
        run_launcher = _run_launcher()
        run_ppid = os.getppid()
        run_service = os.environ.get("XPC_SERVICE_NAME", "-")
        alerts = build_alerts(result, run_machine)
        if alerts:
            handed, notify_failures = send_alerts(alerts)

    if blind:
        rc = 2
    elif args.notify:
        rc = 0 if not notify_failures else 1
    elif args.fix:
        # 0 only when nothing failed AND no report-only finding remains
        # (custody and .env* are never chmod'ed, so one keeps rc 1).
        rc = 0 if failed == 0 and report_only == 0 else 1
    else:
        rc = 0 if not findings else 1

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
            "custody": [
                {
                    "root": str(r.root),
                    "files_traversed": r.files_traversed,
                    "findings": r.findings,
                    "dir_mode": r.dir_mode,
                    "blind": r.blind,
                }
                for r in result.custody
            ],
            "report_only": report_only,
        }
        if args.notify:
            payload["run"] = {
                "ts": run_ts,
                "machine": run_machine,
                "launcher": run_launcher,
                "ppid": run_ppid,
                "service": run_service,
            }
            payload["notify"] = {
                "p0": sum(1 for a in alerts if a.tier == "p0"),
                "digest": sum(1 for a in alerts if a.tier == "digest"),
                "handed": handed,
                "failed": notify_failures,
            }
        print(json.dumps(payload))
    else:
        if args.notify:
            print(
                f"RUN {run_ts} machine={run_machine} launcher={run_launcher} "
                f"ppid={run_ppid} service={run_service}"
            )
        home = str(Path.home())
        for r in result.custody:
            shown = str(r.root)
            if shown.startswith(home):
                shown = "~" + shown[len(home):]
            line = (
                f"CUSTODY {shown}: {r.files_traversed} file(s) checked, "
                f"{r.findings} finding(s), dir {r.dir_mode or '????'}"
            )
            if r.blind:
                line += " — BLIND: directory cannot be listed"
            print(line)
        for finding in findings:
            line = f"{_mode_octal(finding.mode)} {finding.path}"
            if finding.custody:
                line += "  CUSTODY"
            if finding.report_only:
                line += "  REPORT-ONLY (never chmod'ed)"
            print(line)
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
            print(f"FIXED: {fixed}  FAILED: {failed}  REPORT-ONLY: {report_only}")
            for failure in failures:
                print(f"  ! {failure}")
        if args.notify:
            p0_count = sum(1 for a in alerts if a.tier == "p0")
            digest_count = sum(1 for a in alerts if a.tier == "digest")
            print(
                f"NOTIFY p0={p0_count} digest={digest_count} handed={handed} "
                f"failed={len(notify_failures)}"
            )
            for failure in notify_failures:
                print(f"  ! {failure}")
            print(f"RUN-END rc={rc}")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
