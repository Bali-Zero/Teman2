#!/usr/bin/env python3
"""Refuse hardcoded Google OAuth credentials (client secret / refresh token / client id) in the working tree.

WHY THIS EXISTS
---------------
On 2026-08-21 a fleet audit found a full Google OAuth credential triple —
client_id, `GOCSPX-…` client secret, and a `1//…` refresh token — hardcoded
in NINE one-off scripts under `apps/backend-rag/scripts/` (the same triple,
copy-pasted from an rclone gdrive remote setup into 09_company_reorg.py,
batch_passport_ocr.py, clean_arianna_shortcuts.py, copy_company_to_individual.py,
individual_crm_reorg.py, ocr_pipeline.py, ocr_pipeline_gemma.py,
sync_targeted.py, test_company_drive_ollama.py). A hardcoded refresh token is
a LIVE, long-lived credential: anyone with repo read access can mint access
tokens for the Drive scope until the client is revoked on Google Cloud
Console (rotation is `operator[secret]`, tracked in PENDING-ARMS).

No existing gate could have caught these: `detect-secrets` ships no detector
for the `GOCSPX-` / `1//` shapes (its Google plugin covers `AIza…` API keys,
not OAuth client material), and `secrets_permissions_audit.py` matches by
file NAME/path and deliberately never opens contents. The literals sat green
on `origin/main` for months under a passing secrets gate — the exact
"guard whose scope structurally skips a surface" shape of superscar #3.

Patterned on `lint_pg_dsn_credentials.py` (2026-08-21), itself patterned on
`lint_telegram_tokens.py`. Two deliberate choices inherited from both:

1. **It never prints the credential.** A gate that echoes the secret it
   found writes it into a CI log as public as the file it came from.
   Findings report file:line, rule name, value length, and a 16-hex-char
   SHA-256 fingerprint only.

2. **The values we KNOW were published are matched by SHA-256, not by
   value.** Carrying the literals here to blocklist them would re-publish
   the very strings this file exists to keep out.

An explicit, deliberate assertion by the author that a credential-shaped
literal is synthetic — the comment marker `synthetic-google-oauth-credential`
on the same line or the line directly above — suppresses a finding (same
contract as the sibling lints). Placeholders (a body of ≤2 distinct
characters, e.g. `GOCSPX-xxxxxxxxxx`) never fire; anything longer or more
varied must carry the marker explicitly.

Exit codes: 0 clean · 1 finding · 2 could not scan (never silently clean).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

# --- The three credential shapes -------------------------------------------
# `GOCSPX-` is Google's OAuth client-secret prefix — unambiguous, no anchor
# needed. The body is 20+ of the URL-safe set (the published one: 28).
CLIENT_SECRET_RE = re.compile(r"GOCSPX-([A-Za-z0-9_-]{20,})")

# OAuth refresh tokens are `1//` + a long URL-safe body (the published one:
# 100 chars). Anchored on quote OR assignment delimiters (`=`, `:`) with
# optional spacing, so DSN/.env/YAML shapes (`X=1//…`, `refresh_token: 1//…`)
# fire alongside quoted literals, while prose mentions of the `1//` shape
# (no anchor character) stay silent. Body 20+ chars (Codex red-team round 1:
# the quote-only anchor let `refresh_token=1//…` sail through).
REFRESH_TOKEN_RE = re.compile(r"[\"'=:]\s*1//([0-9A-Za-z_-]{20,})")

# A client id is not a credential by itself — but it is the invariant third
# member of the copy-paste blob this guard exists against, so its presence
# says "the pair may be next to me". Shape tightened to the real thing
# (10-13 digits, 20+ lowercase-alnum host part) after Codex red-team round 1
# flagged doc-prose like `123456-example.apps.googleusercontent.com` firing.
# Census 2026-08-21: the only hits in the whole tree were the nine guilty
# files. The synthetic marker is the escape for documentation examples.
CLIENT_ID_RE = re.compile(r"([0-9]{10,13}-[a-z0-9]{20,}\.apps\.googleusercontent\.com)")

# SHA-256 (first 16 hex) of values known to have been published on
# origin/main, so a re-introduction is NAMED ("this is the 2026-08-21 leak"),
# not merely flagged. The values themselves are deliberately absent.
KNOWN_COMPROMISED: dict[str, str] = {
    # The one client secret shared by all nine scripts (rclone gdrive remote
    # family), on origin/main until the 2026-08-21 redaction.
    "83f24d5051c7f127": "GOCSPX client secret published in 9 scripts until 2026-08-21",
    # The one refresh token shared by the same nine scripts.
    "220de0ba649f223e": "OAuth refresh token published in 9 scripts until 2026-08-21",
    # The client id of the same triple.
    "892a81bddb24909e": "OAuth client id published in 9 scripts until 2026-08-21",
}

_RULES: tuple[tuple[str, re.Pattern[str], bool], ...] = (
    # (rule name, pattern, pattern-includes-prefix-in-group-0?) — the
    # fingerprint is always over the FULL credential value (prefix + body),
    # which is what KNOWN_COMPROMISED keys on.
    ("google-oauth-client-secret", CLIENT_SECRET_RE, True),
    ("google-oauth-refresh-token", REFRESH_TOKEN_RE, True),
    ("google-oauth-client-id", CLIENT_ID_RE, False),
)

# A body of one or two distinct characters is a human writing a placeholder
# (`GOCSPX-xxxxxxxxxx`), not entropy from a credential issuer. Narrowed from
# the sibling lint's ≤4 after Codex red-team round 1 constructed a
# deterministic false negative (`abcdabcd…` body sailing through): a real
# 28-char base64url body with ≤2 distinct chars is ~2^-140; anything longer
# must carry the synthetic marker explicitly.
_PLACEHOLDER_MAX_DISTINCT = 2

# Same contract as the sibling lints: marker on the same line or the line
# directly above.
_SYNTHETIC_MARKER = re.compile(r"synthetic-google-oauth-credential", re.IGNORECASE)

_SKIP_DIRS = {".git", "node_modules", ".next", ".venv", "venv", "dist", "build"}


def _fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _is_placeholder(body: str) -> bool:
    return len(set(body)) <= _PLACEHOLDER_MAX_DISTINCT


def _full_value(rule_prefix: bool, match: re.Match[str]) -> str:
    """Reconstruct the full credential value from a rule match."""
    body = match.group(1)
    if not rule_prefix:
        return body
    if match.re is CLIENT_SECRET_RE:
        return "GOCSPX-" + body
    return "1//" + body


def _guard_google_oauth_credential(text: str, path: str = "<memory>") -> list[str]:
    """The guard proper: one human-readable finding per credential literal.

    Registered in infra/guard-conformance/registry.json under the `_guard_`
    census prefix — renaming this function without updating the registry
    fails the conformance gate (that is the contract working as designed).
    """
    findings: list[str] = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, 1):
        for rule_name, pattern, has_prefix in _RULES:
            for match in pattern.finditer(line):
                # Placeholder check on the BODY only — the `GOCSPX-`/`1//`
                # prefixes carry their own distinct characters and would
                # defeat the ≤4-distinct test on the reconstructed value.
                if _is_placeholder(match.group(1)):
                    continue
                value = _full_value(has_prefix, match)
                note = KNOWN_COMPROMISED.get(_fingerprint(value))
                if note is None:
                    above = lines[lineno - 2] if lineno >= 2 else ""
                    if _SYNTHETIC_MARKER.search(line) or _SYNTHETIC_MARKER.search(above):
                        continue
                label = f" — {note}" if note else ""
                findings.append(
                    f"{path}:{lineno}: hardcoded {rule_name} "
                    f"({len(value)} chars, sha256:{_fingerprint(value)}){label}"
                )
    return findings


def scan_text(text: str, path: str = "<memory>") -> list[str]:
    """Public wrapper kept for the test file's direct-call discipline."""
    return _guard_google_oauth_credential(text, path)


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
        findings.extend(_guard_google_oauth_credential(text, rel))
    return findings, scanned, missing


def selftest() -> int:
    """Prove the scanner can still fail before letting it report a clean tree.

    Every fixture is assembled from fragments at runtime, same discipline as
    the sibling lints — a literal credential-shaped string in THIS file would
    make the scanner's own source its first finding.
    """
    sec_body = "Ab" + "3dEf6H" + "iJ9kLm2N" + "oP4qRs7T" + "uVwX"  # 28-char body
    ref_body = "0c" + "defghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-abcd"
    cid_body = "123456789012" + "-" + "abcdefghijklmnopqrstuvwxyzabcdef" + ".apps.googleusercontent.com"

    guilty = [
        ("dict literal client secret", '"client_secret": "GOCSPX-' + sec_body + '",'),
        ("constant assignment", 'OAUTH_CLIENT_SECRET = "GOCSPX-' + sec_body + '"'),
        ("refresh token in payload", '"refresh_token": "1//' + ref_body + '",'),
        ("single-quoted refresh token", "OAUTH_REFRESH_TOKEN = '1//" + ref_body + "'"),
        ("env-file assignment, no quotes", "OAUTH_REFRESH_TOKEN=1//" + ref_body),
        ("yaml colon shape", "refresh_token: 1//" + ref_body),
        ("low-entropy repeated-chunk body", 'SECRET = "GOCSPX-' + "abcd" * 7 + '"'),
        ("client id literal", 'OAUTH_CLIENT_ID = "' + cid_body + '"'),
    ]
    innocent = [
        ("masked rotation comment", "# Rotate GOCSPX-*** on Google Cloud Console if committed"),
        ("placeholder client secret", 'OAUTH_CLIENT_SECRET = "GOCSPX-' + "x" * 24 + '"'),
        ("env read, no literal", 'OAUTH_CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET_RCLONE"]'),
        ("synthetic marker same line", 'SECRET = "GOCSPX-' + sec_body + '"  # synthetic-google-oauth-credential'),
        ("synthetic marker line above", "# synthetic-google-oauth-credential\nSECRET = \"GOCSPX-" + sec_body + '"'),
        ("short 1// string not a token", 'ratio = "1//2"  # not a credential'),
        ("prose 1// mention, no anchor", "the token shape is 1// followed by a long body"),
        ("yaml-looking prose under 20 chars", "refresh_token: 1//short"),
        ("doc-prose client id shape", "an id looks like 123456-example.apps.googleusercontent.com"),
        ("docs prose mentioning the prefix", "client secrets start with GOCSPX- and must stay in env"),
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

    # W84: zero files traversed is not a clean tree, it is a broken scan —
    # but ONLY in --all mode, where zero means `git ls-files` failed us. In
    # explicit mode (pre-commit) a commit of nothing but PNGs legitimately
    # reads zero text files, and blocking it would fire on innocence.
    if args.all and scanned == 0:
        print("❌ scanned 0 readable files — refusing to report clean", file=sys.stderr)
        return 2

    if findings:
        print(f"❌ {len(findings)} hardcoded Google OAuth credential finding(s):", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        print(
            "  → move the credential to an env var read (no literal fallback); "
            "if the literal is synthetic, mark it `synthetic-google-oauth-credential`.",
            file=sys.stderr,
        )
        return 1

    print(f"clean — {scanned} file(s) scanned, no hardcoded Google OAuth credentials")
    return 0


if __name__ == "__main__":
    sys.exit(main())
