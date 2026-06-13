#!/usr/bin/env python3
"""
scar_query.py — lexical search over the cicatrix scar corpus (zero-dependency).

This is the retrieval half of the superscar context-bridge (cicatrix-superscar.md).
The bridge file enters every session (~3.9k tokens) and, per family, ends each
entry with a `→ dettaglio:` line pointing here:  `scar query "<theme>"`.
This tool is what makes that promise real: given a theme it returns the matching
full-body scars from cicatrix-scars.md + cicatrix-scars-archive.md, ranked.

DESIGN CONSTRAINT (load-bearing, verified 2026-06-14 on M5):
  - Qdrant is NOT running on M5; bge-m3 / Ollama are ABSENT on M5; the MOS
    semantic pipeline (`mos-plus-semantic-query.py`) lives only on Pro/Mini.
  - Therefore the DEFAULT path must NOT depend on any embedding service or
    external daemon, or it becomes a #2 "Esiste≠Armato" guardian that dies on
    first use on this machine. The default is pure-stdlib lexical ranking — it
    runs on every node, always, $0. Semantic embedding stays an OPTIONAL future
    upgrade, never a hard dependency of the bridge's promise.

The search is word-boundary aware (anti #3 guard-over-match: a query term must
match on a token boundary, so "ota" does not match "quota"). Title hits weigh
more than body hits; multi-term queries default to AND (all terms must appear),
with --any for OR.

Usage:
    scar query "home fork"            # AND search across both corpus files
    scar query --any "lease nominee"  # OR search
    scar query --family 4             # jump to a superscar family in the bridge
    scar query --list                 # list every scar header (W-number + title)
    scar query "secret" --titles      # one-line-per-hit (no body)

Exit codes: 0 = at least one hit (or list/family rendered); 1 = no hits; 2 = usage error.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# --- corpus location --------------------------------------------------------
# Resolve the rules dir relative to this script so it works from any worktree
# AND when installed as ~/.claude/scripts/scar (which is outside the repo): in
# the latter case we fall back to the canonical checkout paths.
def _candidate_rules_dirs() -> list[Path]:
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    # repo layout: <repo>/scripts/scar_query.py -> <repo>/.claude/rules
    candidates.append(here.parent.parent / ".claude" / "rules")
    # installed CLI: fall back to the known checkouts (M5 then Pro/Mini home)
    candidates.append(Path.home() / "Desktop" / "nuzantara" / ".claude" / "rules")
    return candidates


CORPUS_FILES = ("cicatrix-scars.md", "cicatrix-scars-archive.md")
BRIDGE_FILE = "cicatrix-superscar.md"


def _resolve_rules_dir(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if (p / CORPUS_FILES[0]).is_file():
            return p
        sys.exit(f"scar: --rules-dir {p} has no {CORPUS_FILES[0]}")
    for d in _candidate_rules_dirs():
        if (d / CORPUS_FILES[0]).is_file():
            return d
    sys.exit(
        "scar: could not locate cicatrix-scars.md — pass --rules-dir <path/to/.claude/rules>"
    )


# --- parsing ----------------------------------------------------------------
W_NUMBER_RE = re.compile(r"\bW(\d{2,3})\b")
# a scar block starts at a markdown H3 (### ...) and runs until the next H3,
# the "## Archived" section header, or a top-level "---" that precedes an H3.
HEADER_RE = re.compile(r"^### (.+?)\s*$")


@dataclass
class Scar:
    title: str
    body: str
    source: str  # filename
    w_numbers: list[str] = field(default_factory=list)
    line_no: int = 0

    @property
    def status_glyph(self) -> str:
        for g in ("🚨", "⚠️", "✅", "ℹ️", "🐛"):
            if g in self.title:
                return g
        return "•"


def parse_corpus(rules_dir: Path) -> list[Scar]:
    scars: list[Scar] = []
    for fname in CORPUS_FILES:
        path = rules_dir / fname
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        cur_title: str | None = None
        cur_start = 0
        cur_buf: list[str] = []

        def flush(title, start, buf):
            if title is None:
                return
            body = "\n".join(buf).strip()
            wnums = sorted(set(W_NUMBER_RE.findall(title + " " + body)), key=int)
            scars.append(
                Scar(
                    title=title,
                    body=body,
                    source=fname,
                    w_numbers=[f"W{n}" for n in wnums],
                    line_no=start,
                )
            )

        for i, line in enumerate(lines, start=1):
            m = HEADER_RE.match(line)
            if m:
                flush(cur_title, cur_start, cur_buf)
                cur_title = m.group(1).strip()
                cur_start = i
                cur_buf = []
            elif cur_title is not None:
                cur_buf.append(line)
        flush(cur_title, cur_start, cur_buf)
    return scars


# --- search -----------------------------------------------------------------
def _term_pattern(term: str) -> re.Pattern:
    # word-boundary on alphanumerics; tolerate hyphen/underscore inside the term
    esc = re.escape(term)
    return re.compile(rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])", re.IGNORECASE)


def score_scar(scar: Scar, patterns: list[re.Pattern], require_all: bool) -> int:
    title_hits = sum(len(p.findall(scar.title)) for p in patterns)
    body_hits = sum(len(p.findall(scar.body)) for p in patterns)
    matched_terms = sum(
        1 for p in patterns if p.search(scar.title) or p.search(scar.body)
    )
    if require_all and matched_terms < len(patterns):
        return 0
    if matched_terms == 0:
        return 0
    # title weighs 5x; a W-number exact match in the query is implicitly a title hit
    return title_hits * 5 + body_hits + matched_terms


def search(
    scars: list[Scar], terms: list[str], require_all: bool
) -> list[tuple[int, Scar]]:
    patterns = [_term_pattern(t) for t in terms]
    scored = [(score_scar(s, patterns, require_all), s) for s in scars]
    hits = [(sc, s) for sc, s in scored if sc > 0]
    hits.sort(key=lambda x: (-x[0], x[1].source, x[1].line_no))
    return hits


# --- rendering --------------------------------------------------------------
def render_hit(scar: Scar, score: int, titles_only: bool) -> str:
    wn = " ".join(scar.w_numbers)
    head = f"{scar.status_glyph} {wn + '  ' if wn else ''}{scar.title}"
    loc = f"    ↳ {scar.source}:{scar.line_no}  (score {score})"
    if titles_only:
        return f"{head}\n{loc}"
    return f"{head}\n{loc}\n\n{scar.body}\n\n{'─' * 78}"


def render_family(rules_dir: Path, family: str) -> int:
    bridge = rules_dir / BRIDGE_FILE
    if not bridge.is_file():
        sys.exit(f"scar: {BRIDGE_FILE} not found in {rules_dir}")
    text = bridge.read_text(encoding="utf-8")
    fam = family.lstrip("#")
    # match "## #N — ..." up to the next "## " header
    m = re.search(
        rf"^## #{re.escape(fam)} —.*?(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if fam.lower() in ("orfane", "orphan", "orphans"):
        m = re.search(r"^## Orfane.*?(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        sys.exit(f"scar: no superscar family '#{fam}' in {BRIDGE_FILE} (try 1-10 or 'orfane')")
    sys.stdout.write(m.group(0).rstrip() + "\n")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="scar query",
        description="Lexical search over the cicatrix scar corpus (the retrieval half of cicatrix-superscar.md).",
    )
    ap.add_argument("terms", nargs="*", help="search term(s); multi-term defaults to OR (theme search)")
    ap.add_argument("--all", action="store_true", help="AND search (every term must appear) instead of the default OR")
    ap.add_argument("--any", action="store_true", help="OR search (explicit; this is already the multi-term default)")
    ap.add_argument("--titles", action="store_true", help="one line per hit, no body")
    ap.add_argument("--list", action="store_true", help="list every scar header (W-number + title)")
    ap.add_argument("--family", metavar="N", help="render superscar family #N from the bridge (1-10 or 'orfane')")
    ap.add_argument("--rules-dir", help="override path to .claude/rules")
    ap.add_argument("--limit", type=int, default=0, help="max hits to print (0 = all)")
    args = ap.parse_args(argv)

    rules_dir = _resolve_rules_dir(args.rules_dir)

    if args.family:
        return render_family(rules_dir, args.family)

    scars = parse_corpus(rules_dir)

    if args.list:
        for s in scars:
            wn = " ".join(s.w_numbers)
            print(f"{s.status_glyph} {wn + '  ' if wn else ''}{s.title}  [{s.source}:{s.line_no}]")
        print(f"\n— {len(scars)} scars across {len(CORPUS_FILES)} corpus files —", file=sys.stderr)
        return 0

    if not args.terms:
        ap.print_usage(sys.stderr)
        print('scar: need a search term, or --list / --family N', file=sys.stderr)
        return 2

    # Tokenize: a single quoted multi-word arg (`scar query "esiste non armato"`,
    # exactly how the bridge cites its themes) must split into terms, else it is
    # searched as one impossible literal phrase. Split every arg on whitespace.
    terms = [tok for arg in args.terms for tok in arg.split() if tok]
    if not terms:
        print("scar: empty search term", file=sys.stderr)
        return 2

    # default is OR (theme search); --all forces AND. --any is explicit OR.
    require_all = args.all and not args.any
    hits = search(scars, terms, require_all=require_all)
    if not hits:
        mode = "all" if require_all else "any"
        print(f"scar: no scar matches {terms} (mode={mode})", file=sys.stderr)
        return 1

    shown = hits if args.limit <= 0 else hits[: args.limit]
    for score, scar in shown:
        print(render_hit(scar, score, args.titles))
    print(
        f"\n— {len(hits)} hit(s){'' if args.limit <= 0 else f', showing {len(shown)}'} for {terms} —",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
