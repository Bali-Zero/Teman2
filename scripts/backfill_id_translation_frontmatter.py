#!/usr/bin/env python3
"""Backfill missing frontmatter fields on Indonesian (.id.mdx) article translations.

Context: research/operations/2026-10-06-subhi-translation-backlog.md (owner GO
2026-10-06) measured that of 851 `.id.mdx` files, 722 lack `lang: id`, 719 lack
`translatedAt`, 556 lack `relatedArticles`, 26 lack `seoDescription`, 21 lack
`seoTitle`. The compliant reference shape is the PR #2957/#2998/#2999 polish
wave (e.g. business/accounting-software-indonesia.id.mdx): `lang: id`,
`translatedAt: "YYYY-MM-DD"` (date of the git commit that added the file —
verified to match the exemplars), `seoTitle` / `seoDescription` copied verbatim
from the English source frontmatter, `relatedArticles` copied from the English
source.

Rules — every field is ADDITIVE ONLY, never overwrite an existing key:

  * `lang: id`              added when no top-level `lang:` key exists.
  * `translatedAt`          first commit that added the file
                            (`git log --diff-filter=A --format=%aI`), date part
                            only, quoted — mirrors the exemplars exactly.
  * `seoTitle`              copied verbatim from the English source frontmatter
                            (all 21 files have it there; the exemplars copy the
                            EN seoTitle verbatim, e.g. accounting-software-
                            indonesia).
  * `seoDescription`        copied verbatim from the English source; if the
                            source lacks it, the field is LEFT MISSING (a
                            fallback to the id file's own `description` was
                            implemented, measured, and REMOVED — those values
                            carry markdown-heading boilerplate that the
                            description-fields-integrity vitest rejects).
  * `relatedArticles`       copied verbatim from the English source. Only 10 of
                            the 556 missing files have it there; the other 546
                            have no deterministic source and are LEFT MISSING —
                            choosing related articles is a content decision.

Deliberately NOT added (stated in the PR body):
  * `translationStatus` — the audit found no file carries it and calls the
    convention undefined; inventing it is not a backfill.
  * `translatedFrom` / `translatedBy` — `translatedBy` is unknown for the bulk
    translation waves, and the exemplar pair is written by the translation
    pipeline, not a frontmatter backfill.

New keys are inserted at their alphabetical position among top-level keys
(the exemplar frontmatter is alphabetically sorted). Idempotent: a second run
finds every key present and writes nothing.

Run with --check to report without writing.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "apps/mouth/src/content/articles"

FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
TOPKEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):[ \t]?", re.M)


def parse_fm(text: str) -> str | None:
    m = FM_RE.match(text)
    return m.group(1) if m else None


def topkey_spans(fm: str) -> list[tuple[str, int, int]]:
    """Return (key, start, end) spans for every top-level key block."""
    matches = list(TOPKEY_RE.finditer(fm))
    spans = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(fm)
        spans.append((m.group(1), m.start(), end))
    return spans


def key_block(fm: str, key: str) -> str | None:
    """The full YAML block (key line + indented continuation) for `key`."""
    for k, start, end in topkey_spans(fm):
        if k == key:
            return fm[start:end].rstrip("\n")
    return None


def has_key(fm: str, key: str) -> bool:
    return any(k == key for k, _, _ in topkey_spans(fm))


def git_add_date(path: Path) -> str | None:
    rel = path.relative_to(ROOT)
    out = subprocess.run(
        ["git", "log", "--diff-filter=A", "--format=%aI", "--", str(rel)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    if not out:
        return None
    return sorted(out)[0][:10]  # oldest addition, date part


def rename_key(block: str, new_key: str) -> str:
    return re.sub(r"\A[A-Za-z_][A-Za-z0-9_]*:", f"{new_key}:", block, count=1)


def insert_key(fm: str, block: str) -> str:
    """Insert a top-level key block in alphabetical position."""
    new_key = TOPKEY_RE.match(block).group(1)
    for key, start, _ in topkey_spans(fm):
        if key > new_key:
            return fm[:start] + block + "\n" + fm[start:]
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + block + "\n"


def non_empty(block: str | None) -> str | None:
    """A block is usable only if it carries a value (inline or indented lines)."""
    if block is None:
        return None
    first, _, rest = block.partition("\n")
    value = first.split(":", 1)[1].strip()
    if value or rest.strip():
        return block
    return None


def process(path: Path, check: bool, stats: dict[str, int], skipped: dict[str, list[str]]) -> bool:
    text = path.read_text()
    fm = parse_fm(text)
    if fm is None:
        skipped.setdefault("no-frontmatter", []).append(str(path.relative_to(ROOT)))
        return False
    body = text[FM_RE.match(text).end() :]

    src = path.with_name(path.name[: -len(".id.mdx")] + ".mdx")
    src_fm = parse_fm(src.read_text()) if src.exists() else None
    if src_fm is None:
        skipped.setdefault("no-source", []).append(str(path.relative_to(ROOT)))

    additions: list[str] = []

    if not has_key(fm, "lang"):
        additions.append("lang: id")

    if not has_key(fm, "translatedAt"):
        date = git_add_date(path)
        if date:
            additions.append(f'translatedAt: "{date}"')
        else:
            skipped.setdefault("no-git-add-date", []).append(str(path.relative_to(ROOT)))

    if src_fm is not None:
        if not has_key(fm, "seoTitle"):
            block = non_empty(key_block(src_fm, "seoTitle"))
            if block:
                additions.append(block)
            else:
                skipped.setdefault("seoTitle-empty-source", []).append(str(path.relative_to(ROOT)))
        if not has_key(fm, "seoDescription"):
            # EN source only. Deliberately NO fallback to the id file's own
            # `description`/`excerpt`: measured 2026-10-06, the id `description`
            # values in this gap are dirty ("# Panduan Pendirian PT PMA ..."
            # boilerplate with markdown headings — the exact defect the
            # description-fields-integrity vitest guards), and copying them
            # would publish them as <meta name="description">. Filling the
            # remainder is a content decision, not a backfill.
            block = non_empty(key_block(src_fm, "seoDescription"))
            if block:
                additions.append(rename_key(block, "seoDescription"))
            else:
                skipped.setdefault("seoDescription-no-source", []).append(
                    str(path.relative_to(ROOT))
                )
        if not has_key(fm, "relatedArticles"):
            block = key_block(src_fm, "relatedArticles")
            if block and re.search(r"^\s*-\s+\S", block, re.M):
                additions.append(block)
            else:
                skipped.setdefault("relatedArticles-no-source", []).append(str(path.relative_to(ROOT)))

    if not additions:
        return False

    new_fm = fm
    for block in sorted(additions, key=lambda b: TOPKEY_RE.match(b).group(1)):
        new_fm = insert_key(new_fm, block)
    # The captured frontmatter group has no trailing newline before the closing
    # ---; the positional-insert path preserves that, so restore it here.
    if not new_fm.endswith("\n"):
        new_fm += "\n"

    for block in additions:
        key = TOPKEY_RE.match(block).group(1)
        stats[key] = stats.get(key, 0) + 1

    if not check:
        path.write_text(f"---\n{new_fm}---\n{body}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report without writing")
    args = ap.parse_args()

    files = sorted(ARTICLES.rglob("*.id.mdx"))
    stats: dict[str, int] = {}
    skipped: dict[str, list[str]] = {}
    changed = 0
    for f in files:
        if process(f, args.check, stats, skipped):
            changed += 1

    mode = "CHECK" if args.check else "WROTE"
    print(f"{mode}: {changed}/{len(files)} .id.mdx files {'would change' if args.check else 'changed'}")
    for key in sorted(stats):
        print(f"  +{key}: {stats[key]} files")
    for reason, paths in sorted(skipped.items()):
        print(f"  skipped ({reason}): {len(paths)}")
        for p in paths:
            print(f"    - {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
