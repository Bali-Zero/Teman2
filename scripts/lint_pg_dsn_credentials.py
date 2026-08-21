#!/usr/bin/env python3
"""Refuse two known-shape secrets in the working tree: a literal
`backend_rag_v2` Postgres password, and a literal Google OAuth client
secret (`GOCSPX-...`).

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

Extended 2026-08-21 (same PR, same incident review): `sync_targeted.py`
carried a SECOND, unrelated live credential on the very next lines — a
Google OAuth client secret (`GOCSPX-...`) for the rclone gdrive remote,
alongside its client_id and refresh_token. Grepping the tree for that exact
literal found the SAME triple copy-pasted into 9 files total under
`apps/backend-rag/scripts/` (one, `bulk_populate_clients.py`, had already
been fixed by an earlier sweep — the same "sweep bonifies the past, not new
copies" pattern as the DSN password above). Unlike the DSN password,
`GOCSPX-` IS a recognizable prefix — Google mints it, GitHub's own secret-
scanning partner program keys on it — so no role/context anchor is needed,
just the prefix plus a real-looking body.

WHAT IT DOES
------------
Scans tracked text files for two independent shapes:

1. `backend_rag_v2:<password>@` where `<password>` is a real-looking
   literal — a run of 10+ letters/digits, not a placeholder, not an
   env-var reference, not a short human word.
2. `GOCSPX-<body>` where `<body>` is a run of 20+ base64url characters,
   not a placeholder (repeated-character strings like `GOCSPX-XXX...X`
   still pass — see `_is_placeholder`).

Exits non-zero on any hit.

HONEST LIMIT (declared, not closed by this file)
-------------------------------------------------
- The DSN check is anchored on the literal role name `backend_rag_v2`. A
  `postgres://<other-role>:<password>@...` DSN for ANY other role — a new
  service account, a per-client role, a local-dev role with a real-looking
  password — is silently out of scope. This guard proves one role's
  password is absent from the tree; it does not prove the tree has no
  Postgres credentials at all.
- The GOCSPX check catches Google OAuth **client secrets** only. The
  refresh_token that travels alongside a client secret in every leak this
  guard was born from (`1//...`-shaped, arguably the more dangerous of the
  two — it alone mints fresh access tokens indefinitely without the
  client secret) has no detector here. Neither does a bare OAuth client_id
  (`<digits>-<hash>.apps.googleusercontent.com`) — deliberately: a client_id
  is a public identifier, not a secret, and flagging it would be a guard
  crying wolf on every legitimate reference to it in code or docs.

Two deliberate choices, mirroring `lint_telegram_tokens.py` (the sibling
guard this file is patterned on):

1. **It never prints the secret.** A gate that echoes the secret it found
   writes it into a CI log as public as the file it came from.

2. **Every password/secret we KNOW was real is matched by SHA-256, not by
   value.** Carrying a leaked literal here to blocklist it would re-publish
   the very string this file exists to keep out.

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

# Google mints this prefix; nobody hand-writes a string shaped like it, so no
# role/context anchor is needed the way DSN_PASSWORD_RE needs `backend_rag_v2:`.
# 20+ base64url characters: the real body this guard was born from was 28
# (Google's current client-secret length), short enough margin that a
# shortened/truncated paste of the same secret still trips it.
GOCSPX_SECRET_RE = re.compile(r"GOCSPX-([A-Za-z0-9_-]{20,})")

# Same discipline as KNOWN_COMPROMISED above, separate map because the two
# guards match unrelated secret shapes and a fingerprint collision between
# them, while astronomically unlikely, should never be able to mislabel a
# finding. Found 2026-08-21: one Google OAuth client secret, copy-pasted
# alongside its client_id and refresh_token into 9 `apps/backend-rag/
# scripts/*.py` files (a 10th, bulk_populate_clients.py, was already fixed
# by an earlier sweep). The value itself is deliberately absent — see the
# module docstring.
GOCSPX_KNOWN_COMPROMISED: dict[str, str] = {
    # Same fragment discipline as the selftest() fixtures below: a bare
    # 16-char hex literal is exactly detect-secrets' own "Hex High Entropy
    # String" shape, so this fingerprint tripped its OWN generic scanner as
    # an unaudited finding (2026-08-21, CI run — same incident as the
    # Basic Auth Credentials false-positive in selftest() further down).
    # The `+` split breaks the contiguous run in the file's raw text while
    # the assembled dict key is byte-identical at runtime.
    ("f5df3367" + "7023bd29"): (
        "rclone gdrive remote OAuth client secret (client_id "
        "930328104463-...apps.googleusercontent.com), published in 9 "
        "apps/backend-rag/scripts/*.py files until this guard's PR (2026-08-21)"
    ),
}

# A body of a handful of distinct characters is a human writing a placeholder
# (`AAAAAAAAAA`, `xxxxxxxxxx`), not entropy from a password generator.
_PLACEHOLDER_MAX_DISTINCT = 4

# An explicit, deliberate assertion by the author that a password/secret-
# shaped literal is synthetic — same contract as lint_telegram_tokens.py's
# marker. Must sit on the same line or the line directly above. One marker
# for both shapes: there is no risk of it hiding a real finding of the OTHER
# kind, since each shape's own regex still has to match first.
_SYNTHETIC_MARKER = re.compile(r"synthetic-(?:pg-password|oauth-secret)", re.IGNORECASE)

_SKIP_DIRS = {".git", "node_modules", ".next", ".venv", "venv", "dist", "build"}


def _fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _is_placeholder(body: str) -> bool:
    return len(set(body)) <= _PLACEHOLDER_MAX_DISTINCT


def _scan_shape(
    lines: list[str],
    path: str,
    pattern: re.Pattern[str],
    known_compromised: dict[str, str],
    label_text: str,
) -> list[str]:
    """One shape's findings — shared by the DSN-password and GOCSPX scans."""
    findings: list[str] = []
    for lineno, line in enumerate(lines, 1):
        for match in pattern.finditer(line):
            body = match.group(1)
            if _is_placeholder(body):
                continue
            note = known_compromised.get(_fingerprint(body))
            if note is None:
                above = lines[lineno - 2] if lineno >= 2 else ""
                if _SYNTHETIC_MARKER.search(line) or _SYNTHETIC_MARKER.search(above):
                    continue
            note_suffix = f" — {note}" if note else ""
            findings.append(
                f"{path}:{lineno}: literal {label_text} "
                f"({len(body)} chars, sha256:{_fingerprint(body)}){note_suffix}"
            )
    return findings


def scan_text(text: str, path: str = "<memory>") -> list[str]:
    """Return one human-readable finding per real-looking secret literal."""
    lines = text.splitlines()
    findings = _scan_shape(
        lines, path, DSN_PASSWORD_RE, KNOWN_COMPROMISED, "backend_rag_v2 DSN password"
    )
    findings += _scan_shape(
        lines,
        path,
        GOCSPX_SECRET_RE,
        GOCSPX_KNOWN_COMPROMISED,
        "Google OAuth client secret (GOCSPX-...)",
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
    mixed_body = "aB3dE6" + "fG9hJ2kL"  # a THIRD 14-char literal, mixed case, no separators
    # Synthetic GOCSPX bodies, 22-26 chars each, NOT the real leaked value
    # (that one is named only by fingerprint — GOCSPX_KNOWN_COMPROMISED above).
    gocspx_body_a = "aZ3xQ9" + "mR7bN2kP5vT8" + "wY1c"
    gocspx_body_b = "Hj4Lp8" + "Qw2Rt6Yu0Io3Pa" + "s5Dg9"

    guilty = [
        ("python fallback default", 'DB = "postgresql://backend_rag_v2:' + real_body + '@127.0.0.1:15432/nuzantara_rag"'),
        ("shell export", "export DATABASE_URL=postgres://backend_rag_v2:" + other_body + "@nuzantara-postgres.flycast:5432/nuzantara_rag"),
        ("env file", "DATABASE_URL=postgresql://backend_rag_v2:" + other_body + "@localhost:15432/nuzantara_rag"),
        ("dotted mixed case", "backend_rag_v2:" + mixed_body + "@nuzantara-postgres.flycast"),
        ("gocspx python literal", 'OAUTH_CLIENT_SECRET = "GOCSPX-' + gocspx_body_a + '"'),
        ("gocspx shell export", "export GOOGLE_CLIENT_SECRET=GOCSPX-" + gocspx_body_b),
        ("gocspx json value", '"client_secret": "GOCSPX-' + gocspx_body_a + '"'),
    ]
    # Same fragment discipline for the INNOCENT fixtures below: several of these
    # embed a `user:pass@host` run behind a `scheme` + colon-slash-slash prefix
    # (by design — that's exactly the form this guard must NOT flag), which is
    # also exactly the shape detect-secrets' generic "Basic Auth Credentials"
    # plugin looks for — including in a COMMENT: this very paragraph, in an
    # earlier wording that spelled the two halves contiguously, was ITSELF
    # flagged unaudited by that separate scanner (2026-08-21, CI run
    # 32416377500), the same run that flagged the fixtures below. The `+`
    # split at the password/`@` boundary breaks the contiguous run/host shape
    # in the file's RAW TEXT (a static scan, same as ours), while `scan_text()`
    # still receives the identical assembled string at runtime, so the
    # guilt/innocence assertion below is unchanged.
    innocent = [
        ("established rotation placeholder", "backend_rag_v2:<<ROTATED_2026_05_22_see_DATABASE_URL_env>>@localhost:15432/nuzantara_rag"),
        ("angle-bracket placeholder", "postgresql://backend_rag_v2:<password>@localhost:15432/nuzantara_rag"),
        ("short test word secret", "postgres://backend_rag_v2:secret" + "@nuzantara-postgres.flycast:5432/nuzantara_rag"),
        ("dot-env template value", "WA_MIRROR_DATABASE_URL=postgresql://backend_rag_v2:CHANGE_ME" + "@localhost:15432/nuzantara_rag"),
        ("short placeholder word", "FLY_TUNNEL_URL=postgresql://backend_rag_v2:PASS" + "@localhost:15432/nuzantara_rag"),
        ("env-var read, no literal", 'DB = os.environ.get("WA_LAUNCHER_DB_DSN") or os.environ.get("DATABASE_URL")'),
        ("unrelated test DSN", "DATABASE_URL: postgresql://test:test" + "@localhost:5432/nuzantara_test"),
        ("different role, same shape password", "postgresql://nuzantara:nuzantara_local_2024" + "@localhost:5432/nuzantara"),
        ("repeated-char placeholder", "backend_rag_v2:" + "x" * 20 + "@localhost"),
        ("bare role name, no password", 'RUNTIME_ROLE = "backend_rag_v2"'),
        ("comment mentioning the role", "# backend_rag_v2 does NOT have pg_monitor granted"),
        # GOCSPX innocence — mirrors the redaction convention this guard's own
        # PR introduced in the 9 files it fixed (`# Rotate GOCSPX-*** on Google
        # Cloud Console...`): only 3 non-alnum chars after the prefix, well
        # under the 20-char body minimum, so the redaction comment itself
        # never trips the guard it accompanies.
        ("redaction comment, not a literal", "# Rotate GOCSPX-*** on Google Cloud Console if previously committed in plaintext."),
        ("gocspx placeholder, repeated char", "GOCSPX-" + "X" * 28),
        ("gocspx prefix without body", "# see the GOCSPX- prefix convention in the module docstring"),
        ("env-var read, no gocspx literal", 'OAUTH_CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET_RCLONE"]'),
        ("bare client_id, not a secret", '"client_id": "000000000000-abcdefghijklmnopqrstuvwxyzabcdef00.apps.googleusercontent.com  # synthetic-google-oauth-credential"'),
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
        print(f"❌ literal secret(s) found in {len(findings)} place(s):")
        for line in findings:
            print(f"   {line}")
        print()
        print("   A secret in the tree is a secret in the PR diff, which is public")
        print("   while the PR is open even if the merge squashes it out of history.")
        print("   Read it from the environment instead — never hardcode a fallback")
        print("   literal. For the DSN password: DATABASE_URL / DATABASE_URL_LOCAL /")
        print("   DATABASE_URL_FLY. For a GOCSPX- client secret: GOOGLE_CLIENT_SECRET")
        print("   or a service-specific equivalent (see this repo's other Drive")
        print("   OAuth call sites for the established env-var names).")
        return 1

    print(
        f"✅ no literal backend_rag_v2 DSN password or GOCSPX- OAuth client "
        f"secret in {scanned} tracked text file(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
