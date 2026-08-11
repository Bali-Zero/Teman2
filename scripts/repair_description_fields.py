#!/usr/bin/env python3
"""Strip leaked markdown out of the frontmatter fields that describe an article.

WHAT REACHES A HUMAN. Two fields, two different audiences, one defect:

  * `seoDescription` becomes `<meta name="description">` and `og:description`
    (page.tsx:194, `article.seoDescription || article.excerpt`) — the sentence a
    prospective client reads in Google's results and on every shared link.
  * `excerpt` is BOTH that fallback and the "ZANTARA AI SUMMARY" block of the
    AI-ingestion exports (generate-llms-full.ts:73,107,120), so it is what an
    LLM reads when it answers a question about Bali Zero.

Measured live on balizero.com 2026-08-11, every language:

    <meta name="description" content="## Facts  Indonesia's Directorate ...">

and in 33 files — English and Italian among them — a single-quoted scalar had
opened and never closed, so gray-matter folded the FOLLOWING KEYS into the
value and production served:

    <meta name="description" content="## Facts aiGenerated: true
     aiConfidenceScore: 0.85 aiOptimization:   answerSnippet: &quot;## Facts ...">

The search result for an immigration and tax advisory announced that its article
was AI-generated, with a confidence score, before anyone clicked. That is why
this ran the day it was found.

TWO REPAIRS, deliberately distinguished:

  A. PREFIX — the value is intact and merely opens with `## Facts`. Strip the
     marker. Purely mechanical, no judgement.
  B. UNRECOVERABLE — the value swallowed later keys AND was truncated mid-word
     ("…primaryQuestion: \"What does The Real Numbers on"). Drop it. Writing a
     replacement would be authoring a description and calling it a repair.

Dropping was chosen only after checking the premise, which turned out FALSE the
first time: these files do NOT still carry `aiGenerated` / `aiConfidenceScore` /
`aiOptimization` as their own keys — read the raw file, 18 lines of frontmatter
ending at the corrupt line. The data is genuinely gone, so keeping the value
preserves nothing.

Consequence, stated rather than discovered later: in those files `excerpt` is
the empty string and there is no `description` key, so the page ends up with NO
meta description and Google synthesises the snippet from the article body. That
is the standard behaviour for a missing description, and strictly better than
publishing the AI metadata.

Selecting on the `## Facts` prefix ALONE misses two files whose value reads
`"Facts aiGenerated: true …"` — the marker was stripped at some point while the
swallowed keys stayed. Those are the worst to miss, since the keys are the part
that reaches Google. Select on either signal.

Run with --check to report without writing.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

FIELDS = ("seoDescription", "excerpt")

# Strip the heading marker AND the heading word, but only a heading word we
# have actually verified in this corpus. A generic "drop the first word after
# the hashes" would eat the first real word of any description whose heading is
# something else — silently, and unreviewably across hundreds of files.
HEADING = re.compile(r"^\s*#{1,6}\s*(Facts|Fakta|Fatti|Faits|Факты)\b[ \t]*", re.I)
# Keys of this frontmatter schema. One INSIDE a value means the parser folded it
# in — never that an author typed it. Naming them beats "anything with a colon":
# prose legitimately contains colons ("Bali 2026: what changed").
SWALLOWED_KEY = re.compile(
    r"\b(aiGenerated|aiConfidenceScore|aiOptimization|answerSnippet"
    r"|primaryQuestion|seoTitle|seoDescription)\s*:"
)
STARTS_MARKDOWN = re.compile(r"^\s*(#{1,6}\s|\*\*)")


def frontmatter_span(raw: str):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", raw, re.S)
    return (m.group(1), m.end()) if m else (None, None)


def block_of(lines: list[str], key: str):
    """(start, end) of `key:` plus the folded continuation lines of its value."""
    for i, line in enumerate(lines):
        if re.match(rf"^{key}:(\s|$)", line):
            j = i + 1
            while j < len(lines) and not re.match(r"^[A-Za-z_][\w-]*:", lines[j]):
                j += 1
            return i, j
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root", default="apps/mouth/src/content/articles")
    args = ap.parse_args()

    stripped: dict[str, list[str]] = {f: [] for f in FIELDS}
    dropped: dict[str, list[str]] = {f: [] for f in FIELDS}
    unknown_heading: list[tuple[str, str, str]] = []

    for path in sorted(glob.glob(os.path.join(args.root, "*/*.mdx"))):
        raw = open(path, encoding="utf-8").read()
        fm, end = frontmatter_span(raw)
        if fm is None:
            continue
        rel = os.path.relpath(path, args.root)
        lines = fm.split("\n")
        touched = False

        for field in FIELDS:
            start, stop = block_of(lines, field)
            if start is None:
                continue
            flat = " ".join("\n".join(lines[start:stop]).split())
            val = re.sub(rf"^{field}:\s*", "", flat).strip().strip("\"'").strip()
            if not val:
                continue
            if not STARTS_MARKDOWN.match(val) and not SWALLOWED_KEY.search(val):
                continue

            if SWALLOWED_KEY.search(val):
                lines = lines[:start] + lines[stop:]
                dropped[field].append(rel)
                touched = True
                continue

            cleaned = HEADING.sub("", val)
            if cleaned is val or cleaned == val:
                # Heading marker present but the word is NOT one we know. Do not
                # guess which word was decoration and which was the sentence.
                unknown_heading.append((rel, field, val[:60]))
                continue
            cleaned = re.sub(r"^\s*\*\*(.+?)\*\*\s*", r"\1 ", cleaned)
            cleaned = " ".join(cleaned.split()).strip().strip("\"'").strip()
            if not cleaned:
                lines = lines[:start] + lines[stop:]
                dropped[field].append(rel)
            else:
                esc = cleaned.replace("\\", "\\\\").replace('"', '\\"')
                lines = lines[:start] + [f'{field}: "{esc}"'] + lines[stop:]
                stripped[field].append(rel)
            touched = True

        if touched and not args.check:
            open(path, "w", encoding="utf-8").write(
                "---\n" + "\n".join(lines) + "\n---\n" + raw[end:]
            )

    verb = "would strip" if args.check else "stripped"
    for f in FIELDS:
        print(f"{verb} markdown from {f}: {len(stripped[f])}")
        print(f"  dropped as unrecoverable: {len(dropped[f])}")
    print(f"left alone — heading word not in the known list: {len(unknown_heading)}")
    for rel, field, sample in unknown_heading[:10]:
        print(f"    {field:15s} {rel}\n       {sample!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
