#!/usr/bin/env python3
"""Refuse a Telegram bot token in the working tree.

WHY THIS EXISTS
---------------
On 2026-08-13 the live token of `@Balizerobot` was found in cleartext on the
**public** default branch, inside two archived planning documents
(`docs/archive/2026-07-orphans/superpowers/{plans,specs}/…-sentinel-v2-dlq-autopilot*.md`,
removed in #4160). Every gate was green while it sat there:

  * `detect-secrets` (pre-commit hook AND the required "Detect Secrets" check)
    ships no detector for this shape. Measured, not assumed: a file whose only
    content is a token-shaped string scans to `results: {}`.
  * The token lived in `.md`, so no Python/TS linter ever looked at it.

The consequence outlived the discovery: BotFather answers only the account that
created a bot, that account is lost, so `@Balizerobot` can never be revoked and
its published token stays valid indefinitely. A gate that had refused the commit
would have cost one rejected push; its absence cost a permanently burned bot.

WHAT IT DOES
------------
Scans tracked text files for the Telegram bot-token shape `<bot-id>:AA<body>`
and exits non-zero on a hit.

Two deliberate choices, both of which are the point rather than polish:

1. **It never prints the token.** A gate that echoes the secret it found writes
   it into a CI log that is as public as the file it came from — the same
   disease, one layer down. Findings carry `file:line`, the bot id (already
   public, it is half of the bot's identity) and a length, never the body.

2. **Known-compromised tokens are matched by SHA-256, not by value.** Carrying
   `@Balizerobot`'s token here to blocklist it would re-publish the very string
   this file exists to keep out of the repository.

Exit codes: 0 clean · 1 finding · 2 could not scan (never silently clean).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

# `<bot-id>:AA<33 chars>` — the shape the Bot API issues. Anchored on the literal
# `AA` prefix (present in every token BotFather has issued), so it is a shape
# match and not a substring sweep: `1234567890` alone, a `sha256:…` digest and an
# `${ENV}` placeholder cannot reach it.
#
# The edges are lookarounds over the token's OWN alphabet, not `\b`. The first
# draft used `\b` and was blind to the likeliest hiding place of all —
# `https://api.telegram.org/bot<TOKEN>/sendMessage` — because the character before
# the bot id there is `t`, so no word boundary exists to match. Its own guilt
# corpus caught it. `\b` describes the shape of the surrounding text; `(?<!\d)`
# and `(?![A-Za-z0-9_-])` describe where the entity actually ends.
TOKEN_RE = re.compile(r"(?<!\d)(\d{6,12}):(AA[A-Za-z0-9_-]{30,40})(?![A-Za-z0-9_-])")

# SHA-256 of tokens known to be burned. Present so a re-introduction is named
# ("this is the @Balizerobot token") instead of merely flagged. The values
# themselves are deliberately absent — see the module docstring.
KNOWN_COMPROMISED: dict[str, str] = {
    # @Balizerobot (bot id 8295471667) — unrevocable, public in git history.
    "a54b897b432002bb": "@Balizerobot (unrevocable — never route traffic here)",
}

# A body of a handful of distinct characters is a human writing a placeholder
# (`AAAAA…`, `AAAAxxxx…`), not 33 bytes of base64 from BotFather. Real tokens
# measured well above this; the threshold is low enough that no real token can
# fall under it and high enough that the usual placeholders do.
_PLACEHOLDER_MAX_DISTINCT = 5

# An explicit, deliberate assertion by the author that a token-shaped literal is
# synthetic. It exists because the tree legitimately contains one: the corpus
# pinning the 2026-08-11 scar (a live token printed into an Actions log by httpx
# at INFO) needs a string of the real SHAPE — that is the whole point of it.
# Blocking that file would be the over-match that gets a guard switched off, and
# the file it would block is a sibling security guard.
#
# The marker must sit on the same line or the line directly above, so a reviewer
# reads the claim next to the value. It is an assertion, not a formality.
#
# It CANNOT launder a token we already know is real: a hash in KNOWN_COMPROMISED
# is reported however it is marked. An exemption that can excuse a burned
# credential is not an exemption, it is a hole with a comment on it.
_SYNTHETIC_MARKER = re.compile(r"synthetic-telegram-token", re.IGNORECASE)

_SKIP_DIRS = {".git", "node_modules", ".next", ".venv", "venv", "dist", "build"}


def _fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _is_placeholder(body: str) -> bool:
    return len(set(body[2:])) <= _PLACEHOLDER_MAX_DISTINCT


def scan_text(text: str, path: str = "<memory>") -> list[str]:
    """Return one human-readable finding per real-looking token."""
    findings: list[str] = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, 1):
        for match in TOKEN_RE.finditer(line):
            bot_id, body = match.group(1), match.group(2)
            if _is_placeholder(body):
                continue
            note = KNOWN_COMPROMISED.get(_fingerprint(body))
            if note is None:
                above = lines[lineno - 2] if lineno >= 2 else ""
                if _SYNTHETIC_MARKER.search(line) or _SYNTHETIC_MARKER.search(above):
                    continue
            label = f" — {note}" if note else ""
            findings.append(
                f"{path}:{lineno}: Telegram bot token for bot id {bot_id} "
                f"(body {len(body)} chars, sha256:{_fingerprint(body)}){label}"
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
    """Returns (findings, files actually read, paths that were not there).

    Binary and directory entries are skipped silently — a token cannot hide in
    them as text. A path that does not EXIST is different in kind and is
    reported, because in explicit mode it means the caller and this scanner
    disagree about what is being checked.
    """
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

    Every fixture is assembled from fragments at runtime. A literal token-shaped
    string in this file would make the scanner's own source its first finding,
    and the usual escape — exempting the guard's own path — is how a guard grows
    a hole named after itself.
    """
    # Split into short fragments, not one long literal. Same reason the whole
    # corpus is assembled at runtime, one level down: a single 33-char varied
    # string is high-entropy enough that detect-secrets flags it as a
    # Base64 High Entropy String, and the only way to clear that is a triage
    # rule approving `real_body = "AA" + "<33 chars>"` — which would approve
    # that shape for any future value, including a live token body pasted in
    # fragments this gate cannot see. Short pieces need no such approval.
    real_body = "AA" + "Hn4Kd9Wq" + "2Zx7Lm1P" + "v6Rt3Yb8" + "Sc5Ug0Jf"
    guilty = [
        ("plain markdown", "token: " + "8295471667" + ":" + real_body),
        ("inside a plist", "<string>" + "123456789" + ":" + real_body + "</string>"),
        ("shell export", "export TG=" + "999999999" + ":" + real_body),
        # The case the first draft was blind to — see TOKEN_RE. Kept here, in the
        # corpus CI runs on every PR, so the `\b` cannot come back quietly.
        ("inside an api.telegram.org URL",
         "https://api.telegram.org/bot" + "8295471667" + ":" + real_body + "/sendMessage"),
    ]
    innocent = [
        ("env placeholder", "token: ${TELEGRAM_BOT_TOKEN}"),
        ("angle placeholder", "token: <bot-token>"),
        ("bare chat id", "TELEGRAM_OWNER_CHAT_ID=8847435604"),
        ("git sha", "commit sha256:3d69bc0e10ab4419f8b2c7d5e6a1f0b3c2d4e5f6"),
        ("repeated-char placeholder", "token: " + "123456789" + ":" + "AA" + "A" * 33),
        ("too short to be a token", "token: " + "123456789" + ":" + "AA" + "x" * 10),
        ("a timestamp with a colon", "at 12345678:00 the job ran"),
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
        print(f"❌ Telegram bot token(s) found in {len(findings)} place(s):")
        for line in findings:
            print(f"   {line}")
        print()
        print("   A token in the tree is a token in the history, and a bot whose")
        print("   creating account is gone can never be revoked. Replace it with")
        print("   ${TELEGRAM_BOT_TOKEN} read from the environment.")
        return 1

    print(f"✅ no Telegram bot token in {scanned} tracked text file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
