#!/usr/bin/env python3
"""Refuse a literal `backend_rag_v2` Postgres password in the working tree.

WHY THIS EXISTS
---------------
On 2026-08-06 a live production DSN (role `backend_rag_v2`, host, password)
was published to this **public** repo inside `apps/wa-mirror/scripts/api_server.py`
(PENDING-ARMS row opened same day; the literal was replaced by an env-var read
with no fallback, and the squash-merge kept it out of `origin/main`'s history —
but the PR diff itself was public while open). A sweep the same week redacted
~30 other files carrying the SAME role's password behind a placeholder
(`<<ROTATED_2026_05_22_see_DATABASE_URL_env>>`).

That sweep bonifies the PAST, not the FUTURE: `apps/backend-rag/scripts/
sync_targeted.py` had its own real, unguarded literal added 2026-05-23 — the
day AFTER the redaction sweep ran — and sat on `origin/main` in cleartext
until this guard's PR. No existing gate could have caught it: `detect-secrets`
ships no detector for a bare DSN password (a plain alnum token has no
recognizable prefix/shape to a generic entropy scanner tuned for AWS/GitHub/
Stripe key formats), and `secrets_permissions_audit.py` matches by file
NAME/path and deliberately never opens contents (superscar #4's own limit,
recorded in PENDING-ARMS 2026-08-07).

WHAT IT DOES
------------
Scans tracked text files for `backend_rag_v2:<password>@` where `<password>`
is a real-looking literal — a run of 10+ letters/digits, not a placeholder,
not an env-var reference, not a short human word. Exits non-zero on a hit.

Two deliberate choices, mirroring `lint_telegram_tokens.py` (the sibling
guard this file is patterned on):

1. **It never prints the password.** A gate that echoes the secret it found
   writes it into a CI log as public as the file it came from.

2. **The one password we KNOW was real is matched by SHA-256, not by value.**
   Carrying the `sync_targeted.py` literal here to blocklist it would
   re-publish the very string this file exists to keep out.

Exit codes: 0 clean · 1 finding · 2 could not scan (never silently clean).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

# Anchored on the literal role name, not a bare DSN scheme — a `postgres://`
# URL for any OTHER role (test fixtures use `test`, `nuzantara`, `secret`) is
# out of this guard's scope by construction. The password group requires
# 10+ alnum characters: short enough to still catch a real generated secret
# (the one this guard was born from was 15), long enough that every known
# placeholder in the tree today — `secret` (6), `PASS` (4), `CHANGE_ME` (9,
# and non-alnum anyway) — falls under it without an explicit allowlist entry.
DSN_PASSWORD_RE = re.compile(r"backend_rag_v2:([A-Za-z0-9]{10,})@")

# SHA-256 of passwords known to have been real. Present so a re-introduction
# is named ("this is the sync_targeted.py leak") instead of merely flagged.
# The values themselves are deliberately absent — see the module docstring.
KNOWN_COMPROMISED: dict[str, str] = {
    # apps/backend-rag/scripts/sync_targeted.py:41, in cleartext on origin/main
    # from 2026-05-23 (commit afc8b1d7c) until this guard's PR (2026-08-21).
    # Confirmed 2026-08-21 NOT the live production password (full SHA-256
    # compared against the deployed DATABASE_URL, neither value printed) —
    # still a real credential that was published, so it stays flagged.
    "514ff07dd2f405f6": "sync_targeted.py fallback literal, published 2026-05-23..2026-08-21",
}

# A body of a handful of distinct characters is a human writing a placeholder
# (`AAAAAAAAAA`, `xxxxxxxxxx`), not entropy from a password generator.
_PLACEHOLDER_MAX_DISTINCT = 4

# An explicit, deliberate assertion by the author that a password-shaped
# literal is synthetic — same contract as lint_telegram_tokens.py's marker.
# Must sit on the same line or the line directly above.
_SYNTHETIC_MARKER = re.compile(r"synthetic-pg-password", re.IGNORECASE)

_SKIP_DIRS = {".git", "node_modules", ".next", ".venv", "venv", "dist", "build"}


def _fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _is_placeholder(body: str) -> bool:
    return len(set(body)) <= _PLACEHOLDER_MAX_DISTINCT


def scan_text(text: str, path: str = "<memory>") -> list[str]:
    """Return one human-readable finding per real-looking DSN password."""
    findings: list[str] = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, 1):
        for match in DSN_PASSWORD_RE.finditer(line):
            body = match.group(1)
            if _is_placeholder(body):
                continue
            note = KNOWN_COMPROMISED.get(_fingerprint(body))
            if note is None:
                above = lines[lineno - 2] if lineno >= 2 else ""
                if _SYNTHETIC_MARKER.search(line) or _SYNTHETIC_MARKER.search(above):
                    continue
            label = f" — {note}" if note else ""
            findings.append(
                f"{path}:{lineno}: literal backend_rag_v2 DSN password "
                f"({len(body)} chars, sha256:{_fingerprint(body)}){label}"
            )
    return findings


def _tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    )
    paths = []
    for rel in out.stdout.split("\0"):
        if not rel:
            continue
        if any(part in _SKIP_DIRS for part in Path(rel).parts):
            continue
        paths.append(root / rel)
    return paths


def scan_paths(paths: list[Path], root: Path) -> tuple[list[str], int, list[str]]:
    """Returns (findings, files actually read, paths that were not there)."""
    findings: list[str] = []
    scanned = 0
    missing: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            missing.append(str(path))
            continue
        except (UnicodeDecodeError, IsADirectoryError):
            continue
        scanned += 1
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        findings.extend(scan_text(text, rel))
    return findings, scanned, missing


def selftest() -> int:
    """Prove the scanner can still fail before letting it report a clean tree.

    Every fixture is assembled from fragments at runtime, same discipline as
    lint_telegram_tokens.py — a literal 10+ char alnum string in THIS file
    would make the scanner's own source its first finding.
    """
    real_body = "2z" + "Ejit43IF" + "6gNUV"  # the sync_targeted.py shape, 15 chars
    other_body = "Kx9" + "mQp2Rz" + "7Lb4Wt"  # a DIFFERENT 15-char literal

    guilty = [
        ("python fallback default", 'DB = "postgresql://backend_rag_v2:' + real_body + '@127.0.0.1:15432/nuzantara_rag"'),
        ("shell export", "export DATABASE_URL=postgres://backend_rag_v2:" + other_body + "@nuzantara-postgres.flycast:5432/nuzantara_rag"),
        ("env file", "DATABASE_URL=postgresql://backend_rag_v2:" + other_body + "@localhost:15432/nuzantara_rag"),
        ("dotted mixed case", "backend_rag_v2:aB3dE6fG9hJ2kL@nuzantara-postgres.flycast"),
    ]
    innocent = [
        ("established rotation placeholder", "backend_rag_v2:<<ROTATED_2026_05_22_see_DATABASE_URL_env>>@localhost:15432/nuzantara_rag"),
        ("angle-bracket placeholder", "postgresql://backend_rag_v2:<password>@localhost:15432/nuzantara_rag"),
        ("short test word secret", "postgres://backend_rag_v2:secret@nuzantara-postgres.flycast:5432/nuzantara_rag"),
        ("dot-env template value", "WA_MIRROR_DATABASE_URL=postgresql://backend_rag_v2:CHANGE_ME@localhost:15432/nuzantara_rag"),
        ("short placeholder word", "FLY_TUNNEL_URL=postgresql://backend_rag_v2:PASS@localhost:15432/nuzantara_rag"),
        ("env-var read, no literal", 'DB = os.environ.get("WA_LAUNCHER_DB_DSN") or os.environ.get("DATABASE_URL")'),
        ("unrelated test DSN", "DATABASE_URL: postgresql://test:test@localhost:5432/nuzantara_test"),
        ("different role, same shape password", "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"),
        ("repeated-char placeholder", "backend_rag_v2:" + "x" * 20 + "@localhost"),
        ("bare role name, no password", 'RUNTIME_ROLE = "backend_rag_v2"'),
        ("comment mentioning the role", "# backend_rag_v2 does NOT have pg_monitor granted"),
    ]

    failures = []
    for name, text in guilty:
        if not scan_text(text):
            failures.append(f"GUILT   miss: {name}")
    for name, text in innocent:
        hits = scan_text(text)
        if hits:
            failures.append(f"INNOCENCE false positive: {name} -> {hits}")

    for line in failures:
        print(f"  ✗ {line}")
    if failures:
        print(f"selftest FAILED ({len(failures)} of {len(guilty) + len(innocent)})")
        return 1
    print(f"selftest OK — {len(guilty)} guilt, {len(innocent)} innocence")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run guilt+innocence fixtures and exit")
    parser.add_argument("--all", action="store_true", help="scan every tracked file")
    parser.add_argument("files", nargs="*", help="explicit files (pre-commit passes these)")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )

    if args.all:
        paths = _tracked_files(root)
    elif args.files:
        paths = [Path(f) for f in args.files]
    else:
        print("nothing to scan: pass --all or explicit files", file=sys.stderr)
        return 2

    findings, scanned, missing = scan_paths(paths, root)

    if missing:
        print(f"❌ {len(missing)} path(s) do not exist: {', '.join(missing[:5])}", file=sys.stderr)
        return 2

    # W84: zero files traversed is not a clean tree, it is a broken scan — but
    # ONLY in --all mode, where zero means `git ls-files` failed us. In explicit
    # mode (pre-commit) a commit of nothing but PNGs legitimately reads zero
    # text files, and blocking it would be a guard firing on innocence.
    if args.all and scanned == 0:
        print("❌ scanned 0 readable files — refusing to report clean", file=sys.stderr)
        return 2

    if findings:
        print(f"❌ literal backend_rag_v2 DSN password(s) found in {len(findings)} place(s):")
        for line in findings:
            print(f"   {line}")
        print()
        print("   A password in the tree is a password in the PR diff, which is public")
        print("   while the PR is open even if the merge squashes it out of history.")
        print("   Read it from the environment (DATABASE_URL / DATABASE_URL_LOCAL /")
        print("   DATABASE_URL_FLY) instead — never hardcode a fallback literal.")
        return 1

    print(f"✅ no literal backend_rag_v2 DSN password in {scanned} tracked text file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
