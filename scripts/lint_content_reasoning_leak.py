#!/usr/bin/env python3
"""Fail CI when a content MDX file contains raw LLM reasoning/translation leak.

WHY THIS EXISTS (scar 2026-07-21 — "the /insights?tag= prompt leak"):
An OLD translation pipeline fed a reasoning model an *empty* source slot and
wrote the model's raw chain-of-thought (``Thinking...``, ``*Self-correction:*``,
``Wait, looking at the input:``) verbatim into 25 ``*.{id,fr,ru}.mdx`` files —
into ``tags:``/``description:``/``answerSnippet`` frontmatter AND the body. The
contaminated ``tags`` then rendered as ``/insights?tag=<garbage>`` links that
Google crawled. Documentation did not stop it; this hook does (CLAUDE.md §7:
"se una regola critica è violabile, scrivi un hook").

WHAT IT DOES:
Scans ``apps/mouth/src/content/articles/**/*.mdx`` for translation-reasoning
leak markers. A match anywhere (frontmatter or body) fails the build so the
file can never be committed/republished.

DESIGN (scar #3 guard-over/under-match — match INTENT, test guilt AND
innocence): markers are multi-word *translation-meta* phrases, never a bare
substring like "wait" (legit prose says "Wait for your number to be called").
Run ``--selftest`` to prove both guilt and innocence corpora.

FAIL-VISIBLE (scar #2/W84 blind-scan): scanning zero files is exit 2, never a
silent green.

Usage:
    python scripts/lint_content_reasoning_leak.py            # scan default dir
    python scripts/lint_content_reasoning_leak.py --path P   # scan a path
    python scripts/lint_content_reasoning_leak.py --selftest # guilt+innocence
Exit: 0 clean · 1 leak(s) found · 2 nothing scanned (blind) · 3 selftest fail
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "apps" / "mouth" / "src" / "content" / "articles"

# Translation chain-of-thought / prompt-echo signatures. Every entry is a
# multi-word phrase that a reasoning model emits when it narrates its own
# translation process — NOT a word a real visa/tax/property article uses.
# Case-insensitive. Keep each anchored enough that legit prose cannot trip it.
_LEAK_PATTERNS: list[str] = [
    r"\bthinking\.\.\.",                       # reasoning-model preamble
    r"<think>",
    # asterisk-emphasised form ONLY — reasoning models write ``*Self-correction:*``.
    # Bare "Self-Correction" is a real tax concept (Pembetulan SPT) and must pass.
    r"\*+\s*self[-\s]?correction",
    r"\bwait,\s+(looking at|the input|the source|the original|the prompt|the user|i'?ll|let'?s|usually|if|is |\")",
    r"\blooking at the (input|source|words|structure|original|prompt|text)\b",
    r"\bthe (input|source) text is\b",
    r"\bthe (input|source|original) is:\s*$",
    r"\btranslate (it |them |word for word)",
    r"\bif i translate\b",
    r"\bonly the translation\b",
    # translation-instruction form ONLY — must sit next to only/output/translation.
    # Bare "with no explanation" is legit prose (bank-statement red flags etc.).
    r"\bno explanations?\b[\s.,:*]*(only|output|response|just|the translation)",
    r"\boutput\s*(format)?\s*:?\s*(\*?only\*?|no explanations)",
    r"\brispondi solo con la traduzione\b",     # the Italian old-pipeline prompt
    r"\btesto da tradurre\b",
    r"\bthe user (provided|forgot|wants|asked|meant)\b",
    r"\bthe prompt (says|is|ends|provided)\b",
    r"\bas an ai\b",
    r"\bi (cannot|can't) (translate|perform)\b",
    r"\bre-?evaluate the input\b",
    r"\bfinal check of the input\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _LEAK_PATTERNS]


def scan_text(text: str) -> list[tuple[int, str, str]]:
    """Return list of (line_no, matched_snippet, line) for every leak hit."""
    hits: list[tuple[int, str, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for rx in _COMPILED:
            m = rx.search(line)
            if m:
                hits.append((i, m.group(0).strip(), line.strip()[:120]))
                break  # one hit per line is enough to flag it
    return hits


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    try:
        return scan_text(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:  # unreadable = surface it
        return [(0, f"<unreadable: {exc}>", "")]


def iter_mdx(root: Path):
    yield from sorted(root.rglob("*.mdx"))


def run_scan(root: Path) -> int:
    if not root.exists():
        print(f"::error:: content path not found: {root}", file=sys.stderr)
        return 2
    files = list(iter_mdx(root))
    if not files:
        # blind-scan guard: zero files traversed is NOT a clean pass (W84).
        print(f"::error:: no .mdx files under {root} — refusing silent green", file=sys.stderr)
        return 2

    leaked: dict[Path, list[tuple[int, str, str]]] = {}
    for f in files:
        hits = scan_file(f)
        if hits:
            leaked[f] = hits

    if not leaked:
        print(f"OK: {len(files)} content MDX scanned, zero reasoning-leak markers.")
        return 0

    total = sum(len(h) for h in leaked.values())
    print(
        f"REASONING-LEAK: {len(leaked)} file(s), {total} line(s) — raw LLM "
        f"chain-of-thought/translation-meta leaked into published content.\n",
        file=sys.stderr,
    )
    for f, hits in leaked.items():
        rel = f.relative_to(REPO_ROOT) if REPO_ROOT in f.parents else f
        for line_no, snippet, line in hits[:6]:
            print(f"  {rel}:{line_no}: [{snippet}]  {line}", file=sys.stderr)
        if len(hits) > 6:
            print(f"  … +{len(hits) - 6} more in this file", file=sys.stderr)
    return 1


# ── Self-test: guilt AND innocence (scar #3) ────────────────────────────────

_GUILTY = [
    'description: "Thinking...\\nProfessional Translator (Italian/English)"',
    '  - "Wait, the input text is:"',
    '  - "Wait, looking at the source:"',
    "  - Wait, the user provided them on separate lines.",
    '  - "Input:"\n  - "Output: ONLY the translation."',
    "*Self-correction:* If I respond saying please provide the text.",
    "As an AI, I should wait for the text or indicate it is missing.",
    "If I translate word for word with line breaks:",
    "Rispondi SOLO con la traduzione.",
]

_INNOCENT = [
    "- Wait for your number to be called at the immigration office.",
    "- Waiting for investor KITAS sponsorship to be approved.",
    "- Note: English support is limited, bring a translator.",
    "The input VAT (PPN Masukan) can be credited against output VAT.",
    "tags: [\"immigration\", \"kitas\", \"pt pma\", \"second home visa\"]",
    "Gemini 3 shows strong native reasoning on math benchmarks.",  # tech article prose — see note
    "Bali's zoning map decides where you can build.",
    "## Facts\n\nIndonesia tightened passport rules in 2026.",
    # real near-misses found on first live scan (2026-07-21) — must stay clear:
    "| Self-correction (Pembetulan SPT) (Pasal 8(2)) | Reference rate + 0% |",
    "## Voluntary Disclosure and Self-Correction",
    "| Government correspondence | No, use professional translator | Formal Bahasa |",
    "First, verify your NPWP status and confirm whether you meet the threshold.",
]


def selftest() -> int:
    failed = False
    for s in _GUILTY:
        if not scan_text(s):
            print(f"SELFTEST FAIL (guilt missed): {s!r}", file=sys.stderr)
            failed = True
    for s in _INNOCENT:
        hits = scan_text(s)
        if hits:
            print(f"SELFTEST FAIL (innocent flagged): {s!r} -> {hits}", file=sys.stderr)
            failed = True
    if failed:
        return 3
    print(f"SELFTEST OK: {len(_GUILTY)} guilty caught, {len(_INNOCENT)} innocent cleared.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", default=str(DEFAULT_DIR), help="dir or file to scan")
    ap.add_argument("--selftest", action="store_true", help="run guilt+innocence corpus")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    target = Path(args.path)
    if target.is_file():
        hits = scan_file(target)
        if not hits:
            print(f"OK: {target} clean.")
            return 0
        for line_no, snippet, line in hits:
            print(f"  {target}:{line_no}: [{snippet}]  {line}", file=sys.stderr)
        return 1
    return run_scan(target)


if __name__ == "__main__":
    raise SystemExit(main())
