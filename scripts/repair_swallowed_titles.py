#!/usr/bin/env python3
"""Repair `.id` articles whose frontmatter `title:` swallowed the article.

WHAT WENT WRONG. The Indonesian translation step wrote the translated markdown
into frontmatter scalars instead of the body. For `title:` the result is a YAML
string that opens with the article's H1 and then continues for thousands of
characters, so the page renders an essay — with raw `#` and `**` — where the
headline belongs. Measured 2026-08-11: 101 files, longest title 6,811 chars.

THE REPAIR is recovery, not authoring: the intended title is the FIRST PARAGRAPH
of that value, which is the H1 the pipeline meant to keep. Everything after the
first blank line is prose that already exists in the body.

Two traps this script is written around, both hit while developing it:

  1. Cutting at the first *physical line* truncates mid-title, because YAML
     folds long double-quoted scalars across lines. "…Transisi KBLI 2025
     Indonesia Tanpa" is not a title; "…Tanpa Terbakar" is. Cut on the parsed
     value's blank line, never on the raw file's line breaks.
  2. A regex over the raw frontmatter undercounts (99 vs the real 101) and
     mis-reads escaped `\\n` sequences. Parse the YAML, then operate on the
     resulting string.

Run with --check to report without writing (used by CI and by the guard test).
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

import yaml

FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)

# Length is the WRONG signal for "still swallowed", and this cap learned that
# the hard way: at 200 it rejected the UAE/expat-visas headline, whose English
# sibling is a legitimate 221 characters — a syndicated news title, not prose.
# The structural signals below decide; this stays only as a far-outside-normal
# backstop so a pathological value can never pass silently.
MAX_TITLE = 400


def split_frontmatter(raw: str):
    m = FRONTMATTER.match(raw)
    return (m.group(1), raw[m.end():], m.end()) if m else (None, None, None)


def clean_title(value: str) -> str | None:
    """First paragraph of the value, minus its markdown heading marker."""
    first = value.strip().split("\n\n")[0]
    first = " ".join(first.split())
    first = re.sub(r"^#{1,6}\s*", "", first).strip()
    first = first.strip("*").strip()
    return first or None


def replace_title_block(fm: str, new_title: str) -> str:
    """Swap only the `title:` block, leaving every other key byte-identical."""
    lines = fm.split("\n")
    out, i, done = [], 0, False
    while i < len(lines):
        # `title:` may carry its value inline OR open a folded block with the
        # value starting on the NEXT line, in which case the line is exactly
        # "title:" — `^title:\s` matches the first shape only, silently no-ops
        # on the second, and the script then reports files it never changed.
        # That happened: 103 "repaired", 70 of them untouched.
        if not done and re.match(r"^title:(\s|$)", lines[i]):
            escaped = new_title.replace("\\", "\\\\").replace('"', '\\"')
            out.append(f'title: "{escaped}"')
            i += 1
            # consume the folded continuation of the old value
            while i < len(lines) and not re.match(r"^[A-Za-z_][\w-]*:", lines[i]):
                i += 1
            done = True
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    ap.add_argument("--root", default="apps/mouth/src/content/articles")
    args = ap.parse_args()

    repaired, skipped, unparseable = [], [], []

    for path in sorted(glob.glob(os.path.join(args.root, "*/*.mdx"))):
        raw = open(path, encoding="utf-8").read()
        fm, body, end = split_frontmatter(raw)
        if fm is None:
            continue
        try:
            data = yaml.safe_load(fm) or {}
        except yaml.YAMLError:
            unparseable.append(path)
            continue
        title = data.get("title")
        if not isinstance(title, str):
            continue
        # Selecting on a leading "#" alone MISSES the variant that opens with a
        # bold headline (`**Bali Aparthotels: …**\n\n### Gambaran Umum\n\n…`).
        # Six files hid there. The load-bearing signal is that a title spans
        # more than one line — a headline never does — so select on that first
        # and treat the markers as secondary.
        swallowed = (
            "\n" in title
            or title.lstrip().startswith("#")
            or title.lstrip().startswith("**")
        )
        if not swallowed:
            continue

        new = clean_title(title)
        rel = os.path.relpath(path, args.root)
        # Structural signals, not length: a repaired title is a single line with
        # no markdown left in it. If either survives, the value had no paragraph
        # break to cut on and a human has to look.
        still_broken = bool(new) and ("\n" in new or "**" in new or new.startswith("#"))
        if not new or still_broken or len(new) > MAX_TITLE:
            skipped.append((rel, len(new or "")))
            continue

        if not args.check:
            rewritten = "---\n" + replace_title_block(fm, new) + "\n---\n" + raw[end:]
            # Never report a repair without confirming it took. A silent no-op
            # that still prints "repaired" is worse than a crash: it launders a
            # failure into a success line nobody re-checks.
            check = yaml.safe_load(FRONTMATTER.match(rewritten).group(1)) or {}
            if check.get("title") != new:
                skipped.append((rel, len(new)))
                continue
            open(path, "w", encoding="utf-8").write(rewritten)
        repaired.append((rel, len(title), len(new)))

    verb = "would repair" if args.check else "repaired"
    print(f"{verb}: {len(repaired)}")
    for rel, was, now in repaired[:5]:
        print(f"  {was:6d} -> {now:3d} chars  {rel}")
    if len(repaired) > 5:
        print(f"  … {len(repaired) - 5} more")
    print(f"needs a human (no paragraph break): {len(skipped)}")
    for rel, n in skipped:
        print(f"  {n:6d} chars  {rel}")
    print(f"unparseable frontmatter (untouched here): {len(unparseable)}")
    for p in unparseable:
        print(f"  {os.path.relpath(p, args.root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
