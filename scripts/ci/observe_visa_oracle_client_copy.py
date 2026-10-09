#!/usr/bin/env python3
"""observe_visa_oracle_client_copy.py — bites: observation for the Visa Oracle client copy.

Origin: PR-C1 (Visa Oracle result page speaks to the client), extended by PR-C2 (four duration
keys required) and PR-C4 (the interview's `q.*` / `why.*` helper copy and the atlas copy speak
to the visitor too).

# bites-observable — this script takes NO arguments: every path below is a literal in this
# file, it only reads three source files and touches no network, no node and no git.

Scans the string literals of the files that carry client-visible copy (`i18n.ts`,
`atlas-scenes.ts`, `engine-adapter.ts`, `outcome-fallbacks.ts`, under
`apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/`) and exits 1, printing file:line, if
any literal still holds an internal note or engine jargon the owner ruled out. In
`i18n.ts` and `atlas-scenes.ts` the whole-word jargon list (engine, interface, mesin,
antarmuka, decision fact, enum...) applies too, with an exact-phrase allowlist for the
ordinary-language uses; a dotted dictionary key is never copy and is skipped. It also
asserts that the keys PR-C1 and PR-C2 introduced exist in BOTH language blocks of the
dictionary. Comments are skipped.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib"
FILES = ("i18n.ts", "atlas-scenes.ts", "engine-adapter.ts", "outcome-fallbacks.ts")
WORD_FILES = ("i18n.ts", "atlas-scenes.ts")
BANNED = (
    "PNBP",
    "no PNBP-vs-fee",
    "Timeline unavailable",
    "verified operational processing timeline",
    "no verified",
    "signed rules",
    "fabricat",
    "shadow mode",
    "engine decision",
    "Verified reason:",
    "dibuat-buat",
    "aturan yang telah disahkan",
)
# PR-C4: whole-word jargon that must never reach a visitor, in either language.
BANNED_WORDS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bengine\b",
        r"\bmesin\b",
        r"\binterface\b",
        r"\bantarmuka\b",
        r"decision facts?",
        r"\bfakta\b",
        r"\benums?\b",
        r"\bclosed-",
        r"\breceives\b",
        r"\babstain",
        r"\bpayload\b",
        r"\brouting\b",
        r"\broutes (?:the|this|next)\b",
        r"\bboolean\b",
        r"\bunchanged\b",
        r"\btanpa perubahan\b",
        r"\bfields?\b",
        r"\blabels?\b",
        r"\bfacts?\b",
    )
)
# Exact phrases that are ordinary language, never a bare word (mirrors the vitest census).
ALLOWED_PHRASES = (
    "The result reflects only the facts you entered",
    "some routes depend on facts this tool does not ask",
    "{{facts}}",
)
DOTTED_KEY = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+$")
REQUIRED_KEYS = (
    "outcome.timeline_pending",
    "outcome.checked_on",
    "outcome.path_counter",
    # PR-C2: the stay-permit duration shown under the price.
    "outcome.duration_years",
    "outcome.duration_days",
    "outcome.duration_alternative",
    "outcome.duration_extension",
)
ID_BLOCK_MARKER = "const id: Record<Keys, string> = {"


def string_literals(source: str):
    """Yield (line, text) for every '...', "..." and `...` literal, skipping comments."""
    i, n, line = 0, len(source), 1
    while i < n:
        ch = source[i]
        if ch == "\n":
            line += 1
            i += 1
        elif source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = n if end == -1 else end + 2
            line += source.count("\n", i, end)
            i = end
        elif ch in "'\"`":
            start_line, quote, i, buf = line, ch, i + 1, []
            while i < n and source[i] != quote:
                if source[i] == "\\" and i + 1 < n:
                    buf.append(source[i + 1])
                    i += 2
                    continue
                if source[i] == "\n":
                    line += 1
                    if quote != "`":
                        break
                buf.append(source[i])
                i += 1
            i += 1
            yield start_line, "".join(buf)
        else:
            i += 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail if the Visa Oracle client copy holds internal notes or engine "
        "jargon, or lacks the PR-C1 keys (origin: PR-C1)."
    )
    parser.parse_args()

    problems: list[str] = []
    scanned = 0
    for name in FILES:
        path = LIB / name
        if not path.is_file():
            problems.append(f"{name}: file missing")
            continue
        source = path.read_text(encoding="utf-8")
        for line, text in string_literals(source):
            scanned += 1
            low = text.lower()
            for phrase in BANNED:
                if phrase.lower() in low:
                    problems.append(f"{name}:{line}: banned phrase {phrase!r}")
            if name in WORD_FILES and not DOTTED_KEY.match(text):
                visible = text
                for allowed in ALLOWED_PHRASES:
                    visible = visible.replace(allowed, " ")
                for word in BANNED_WORDS:
                    if word.search(visible):
                        problems.append(
                            f"{name}:{line}: banned word {word.pattern!r} in {text[:60]!r}"
                        )
        if name == "i18n.ts":
            if ID_BLOCK_MARKER not in source:
                problems.append("i18n.ts: language block marker not found")
            else:
                en_block, id_block = source.split(ID_BLOCK_MARKER, 1)
                for key in REQUIRED_KEYS:
                    for label, block in (("en", en_block), ("id", id_block)):
                        if f'"{key}"' not in block:
                            problems.append(
                                f"i18n.ts: key {key} missing in {label} block"
                            )

    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK visa-oracle client copy: {scanned} literals scanned, 0 banned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
