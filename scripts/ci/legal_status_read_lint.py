#!/usr/bin/env python3
"""Refuse any code that READS `legal_status`. Writing it is still allowed.

Measured 2026-08-25 across all 84,283 points of `legal_unified_hybrid_hybrid`:
the field is derived by `STATUS_PATTERNS` in backend/core/legal/constants.py —
two bare regexes over chunk text, first match wins by dict order:

    dicabut: DICABUT|TIDAK BERLAKU|DIGANTI
    berlaku: BERLAKU|MASIH BERLAKU

The two OVERLAP: "TIDAK BERLAKU" contains "BERLAKU", so both match the same
string and only dict order decides. Consequences, all reproduced against live
text rather than reasoned about:

  * "Ketentuan ini tidak berlaku bagi warga negara asing" — a provision that
    does not apply to a class of PERSON marks the whole chunk revoked.
  * "penjamin dapat digantikan" — DIGANTI matches inside `digantikan`, so a
    guarantor being substituted revokes the regulation.
  * A law's own closing clause revoking its PREDECESSOR marks the CURRENT,
    still-valid law dead. That is the live PP_31_2013 case.

The field therefore names a document-level fact and holds chunk-level noise:
9 document_ids carry BOTH named values across their own points (Permen_1_2026:
dicabut 931 / berlaku 575). A document cannot honestly be both. Corpus-wide,
42,420 points say `dicabut` and 26,107 say `berlaku`; the two largest documents
marked revoked — UU_40_2007 and UU_6_2023 — are both independently confirmed in
force.

Zero signed (2026-08-25, decision 5) MARK over REMOVE, and the mark lives in
`kb/topics/<topic>.yaml`: per document, sourced, with an explicit
`source_verified`, gated by the G3 contract. This lint exists so the broken
signal cannot quietly become load-bearing before it is re-derived. Today there
are ZERO readers — the only reference in the backend is the write at ingestion —
and this keeps it that way.

Exit 0 clean · 1 a read was found · 2 the lint could not run.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FIELD = "legal_status"
NESTED = "metadata.legal_status"


def _roots(repo: Path) -> list[Path]:
    return [repo / "apps" / "backend-rag" / "backend"]


def _skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & {"tests", "__pycache__", ".venv", "migrations_v2"})


class _Reads(ast.NodeVisitor):
    """Every mention of the field that is NOT a key in a dict being built.

    A dict literal key is the ingestion WRITE — `{"legal_status": ...}` — and
    stays legal. Anything else is a read: `.get("legal_status")`,
    `payload["legal_status"]`, a Qdrant filter on "metadata.legal_status".
    """

    def __init__(self) -> None:
        self.hits: list[tuple[int, str]] = []
        self.writes = 0
        self._written: set[int] = set()

    def visit_Dict(self, node: ast.Dict) -> None:
        for key in node.keys:
            if isinstance(key, ast.Constant) and key.value in (FIELD, NESTED):
                self._written.add(id(key))
                self.writes += 1
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if node.value in (FIELD, NESTED) and id(node) not in self._written:
            self.hits.append((node.lineno, str(node.value)))
        self.generic_visit(node)


def count_writes(src: str) -> int:
    """Dict-literal mentions in one module — the legal shape."""
    finder = _Reads()
    finder.visit(ast.parse(src))
    return finder.writes


def scan_source(src: str) -> list[tuple[int, str]]:
    """Public for tests: reads found in one module's source."""
    # ONE mechanism, deliberately: visit_Dict marks a dict's keys before
    # generic_visit descends into them, so a write is always seen first. An
    # earlier version also pre-walked the tree marking the same keys — harmless,
    # but it made the exemption unfalsifiable: disabling either half left the
    # other doing the job, and the mutation that should have turned this file red
    # stayed green. Redundancy in a rule is redundancy in its proof.
    finder = _Reads()
    finder.visit(ast.parse(src))
    return sorted(finder.hits)


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    findings: list[str] = []
    scanned = 0
    writes = 0
    for root in _roots(repo):
        if not root.exists():
            print("BROKEN — %s does not exist; nothing was scanned." % root,
                  file=sys.stderr)
            return 2
        for path in sorted(root.rglob("*.py")):
            if _skip(path):
                continue
            scanned += 1
            try:
                src = path.read_text(encoding="utf-8")
                hits = scan_source(src)
                writes += count_writes(src)
            except SyntaxError as exc:
                print("BROKEN — %s could not be parsed: %s" % (path, exc),
                      file=sys.stderr)
                return 2
            for lineno, what in hits:
                findings.append("%s:%d reads %r" % (path.relative_to(repo), lineno, what))

    if scanned == 0:
        print("BROKEN — 0 files scanned. A lint that reads nothing passes "
              "everything.", file=sys.stderr)
        return 2

    print("scanned %d module(s) under apps/backend-rag/backend" % scanned)
    if findings:
        print("REFUSED — %d read(s) of a field measured untrustworthy:" % len(findings))
        for f in findings:
            print("  ! %s" % f)
        print()
        print("`legal_status` is derived by an over-matching regex over chunk text "
              "and is wrong on")
        print("the two largest documents it marks revoked. Read the per-document "
              "`status` in")
        print("kb/topics/<topic>.yaml instead — sourced, gated, and decided by a "
              "person.")
        return 1
    print("clean — 0 reads, %d write site(s)." % writes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
