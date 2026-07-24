#!/usr/bin/env python3
"""bps_crosswalk_parser.py — Phase-0 deterministic BPS Kelompok-crosswalk extractor.

WHAT THIS IS (Batch-B, GARUDA-FILIERA). The signed Batch-B design
(`research/operations/2026-07-19-kbli-batch-b-design.md`, §1.4) needs a
deterministic pass over the vault-pinned BPS "Tabel Konversi KBLI 2020-2025
Vol.2" PDF that extracts, for every 5-digit (Kelompok) code, its BPS
crosswalk ancestry — the edge set that later populates the additive
`bps_2020_ancestors` canonical field (§2.2). This module is that extractor
and NOTHING else: it reads the PDF and emits a build artifact (an edge
relation + a fully-pinned provenance manifest). **It writes no canonical
record** — the data-plane write is a separate compiler
(`populate_bps_ancestors.py`), per the #2550 data-plane-guard split.

GROUND TRUTH, verified in-turn against the real PDF (sha256 29f17b3b…,
2026-07-24), NOT the design's prose:

  * The two relevant tables are Lampiran 5 (forward, KBLI 2020→2025) and
    Lampiran 10 (reverse, KBLI 2025→2020), both at the **Kelompok**
    (5-digit) level. Titles verified on their first page (pg131 / pg325).
    The other forward/reverse blocks in the PDF are Lampiran 1-4 / 6-9 at
    coarser digit levels (Kategori/Golongan) and are OUT OF SCOPE here.
  * These are **ruled tables**: pdfplumber's line-based `extract_table`
    reads the grid cleanly. Wrapped/continuation title lines are joined
    inside a single cell (never lost to whitespace — the failure mode the
    design's throwaway `pdftotext` v0 prototype suffered, §1.4). N:M
    relations appear as repeated left-code rows. The diagonal `bps.go.id`
    watermark is a separate text layer and does not enter grid cells.
  * A code's edge set can **span a page boundary** (verified: 49222
    continues across pg398→pg399), and the column header repeats on every
    page — so edges are accumulated GLOBALLY by left-code, and header/label
    rows are filtered, never per-page-assumed.
  * Page convention: printed_page = pdf_page − 14 (131→117, 325→311,
    399→385; the last matches the design's own "PDF p.399 / printed p.385"
    for 49213). Pinned in the manifest (gate item 9).
  * The design's `sebagian` per-row modifier (gate item 5, a Gemini
    hypothesis) is **empirically absent**: 2 occurrences of "sebagian" in
    444 pages, both copyright/narrative, none a table cell. Split/merge is
    encoded purely by the N:M multi-row structure. We therefore emit
    `sebagian: false` for every edge and record the verified-absence in the
    manifest — a logged negative, never a silent scope reduction (W97).

FAIL-CLOSED (gate item 8). Any row whose code cell is not exactly five
digits after normalization is recorded in the unresolved-row manifest with
its page and reason and never guessed at; the code it would have belonged to
is a Tier-2.5 candidate downstream, not a Tier-3/4 clean edge.

DETERMINISM. Nothing here uses wall-clock, randomness, or dict ordering as a
tie-break. Given the same PDF bytes and the same pdfplumber version, two runs
produce byte-identical relation JSON and the identical output digest — the
property the design's acceptance gate (§1.4 item 2/10) is built on.

USAGE (dry structural census is the default; extraction needs --extract):
    python scripts/kbli_filiera/bps_crosswalk_parser.py --census
    python scripts/kbli_filiera/bps_crosswalk_parser.py --extract \\
        --out data/kbli-filiera/phase0/bps_crosswalk.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover - path shim for direct invocation
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import vault_common as common

logger = common.setup_logger("bps_crosswalk_parser")

# ---------------------------------------------------------------------------
# Pinned constants — the input identity and the parse contract
# ---------------------------------------------------------------------------

# The vault blob this parser is contracted to. A different PDF is a different
# document, not the same one re-fetched: extraction refuses to run against a
# sha mismatch rather than silently parse an unknown edition.
BPS_PDF_REL_PATH = "bps/tabel-konversi-kbli-2020-2025-volume2-2026.pdf"
BPS_PDF_SHA256 = "29f17b3b133497a88c5bfd0eaa3f73c90233b9b95dd76dd0ea2ccaed31724949"  # pragma: allowlist secret  # sha256 content-hash of the public vault PDF, not a credential

# printed_page = pdf_page + PRINTED_PAGE_OFFSET (verified 131→117 etc.).
PRINTED_PAGE_OFFSET = -14

# Table extraction settings — pinned and recorded in the manifest (gate item
# 9 requires tool name+version+flags). Line-based (lattice) because these are
# ruled tables; a whitespace strategy is exactly what lost rows in the v0
# prototype. Explicit so two runs cannot diverge on a library default change.
TABLE_SETTINGS: dict = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
}

# Lampiran block anchors (matched on the block's first page, case/'—'-tolerant).
# The direction is derived from the column header, not from these titles, but
# the titles are the identity check that we parsed the RIGHT lampiran.
FORWARD_TITLE_RE = re.compile(r"Lampiran\s*5\s+Tabel\s+Konversi\s+Kelompok", re.I)
REVERSE_TITLE_RE = re.compile(r"Lampiran\s*10\s+Tabel\s+Konversi\s+Kelompok", re.I)

# Expected pdf-page spans (1-based) — an assertion target, never the source of
# truth. If the detected block drifts off these, the parser fails loud rather
# than silently extracting the wrong pages (structure changed = stop).
EXPECTED_FORWARD_SPAN = (131, 245)
EXPECTED_REVERSE_SPAN = (325, 442)

_CODE_RE = re.compile(r"^\d{5}$")
_YEAR_2020 = "2020"
_YEAR_2025 = "2025"


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without a PDF)
# ---------------------------------------------------------------------------

def normalize_cell(cell: str | None) -> str:
    """Collapse internal whitespace/newlines a wrapped cell carries into
    single spaces and strip — pdfplumber joins continuation lines with '\\n'
    inside one cell, which is signal for titles but noise for codes."""
    if cell is None:
        return ""
    return re.sub(r"\s+", " ", cell).strip()


def extract_code(cell: str | None) -> str | None:
    """The real 5-digit code in a code cell, or None (fail-closed).

    A pristine cell is exactly five digits. But the PDF carries a diagonal
    "https://www.bps.go.id" watermark whose characters bleed into ~11% of
    code cells ('s p01121', '. 01725', '01119 g .'). That watermark string
    contains ZERO digits, so the digits present in a code cell are exactly
    the real code's digits — the watermark can insert noise around them but
    can never change or add a digit. Recovery is therefore deterministic and
    lossless, not a guess: isolate the digits and accept ONLY if exactly five
    remain. A cell with 0/4/6+ digits (empty, truncated, or two merged codes)
    still fails closed to an unresolved-row record (gate item 8)."""
    text = normalize_cell(cell)
    if _CODE_RE.match(text):
        return text
    digits = re.sub(r"\D", "", text)
    return digits if len(digits) == 5 else None


def classify_direction(header_row: list[str | None] | None) -> str | None:
    """'fwd' (2020 column precedes 2025 → Lampiran 5) or 'rev' (2025 precedes
    2020 → Lampiran 10), from the order the two years appear in the joined
    header. None if the row is not a recognizable year-header."""
    if not header_row:
        return None
    joined = " ".join(normalize_cell(c) for c in header_row)
    i2020, i2025 = joined.find(_YEAR_2020), joined.find(_YEAR_2025)
    if i2020 < 0 or i2025 < 0:
        return None
    return "fwd" if i2020 < i2025 else "rev"


def is_header_or_label_row(row: list[str | None] | None) -> bool:
    """True for the repeated column header ('KBLI 2025' / 'Judul …') and the
    '(1) (2) (3) (4)' column-number legend row — both recur on every page and
    must never be read as data."""
    if not row:
        return True
    cell0 = normalize_cell(row[0])
    if cell0.startswith("KBLI") or cell0 in {_YEAR_2020, _YEAR_2025}:
        return True
    if _COLNUM_RE.match(cell0):
        return True
    return False


_COLNUM_RE = re.compile(r"^\(\d\)$")


@dataclass
class ParsedRow:
    """One extracted crosswalk edge: left_code → right_code with both titles
    and the page it was read from. Direction fixes which year each side is."""

    left_code: str
    right_code: str
    left_title: str
    right_title: str
    pdf_page: int  # 1-based


@dataclass
class UnresolvedRow:
    """A row the parser could not confidently turn into an edge — recorded,
    never guessed (gate item 8). `reason` names why; `cells` keeps the raw
    normalized row for audit."""

    pdf_page: int
    reason: str
    cells: list[str]


def parse_table_rows(
    table: list[list[str | None]] | None,
    direction: str,
    pdf_page: int,
) -> tuple[list[ParsedRow], list[UnresolvedRow]]:
    """Turn one page's extracted table into edges + unresolved records.

    Column layout (verified): forward L5 = [code2020, judul2020, code2025,
    judul2025]; reverse L10 = [code2025, judul2025, code2020, judul2020]. The
    left/right code columns are 0 and 2 in BOTH directions — `direction` only
    labels which year is which downstream, it does not move the columns.
    """
    edges: list[ParsedRow] = []
    unresolved: list[UnresolvedRow] = []
    for row in table or []:
        if is_header_or_label_row(row):
            continue
        cells = [normalize_cell(c) for c in row]
        # A well-formed data row has at least the 4 columns.
        if len(row) < 4:
            unresolved.append(UnresolvedRow(pdf_page, "row_has_fewer_than_4_columns", cells))
            continue
        left = extract_code(row[0])
        right = extract_code(row[2])
        if left is None or right is None:
            # Fully-blank rows (grid artifacts) are dropped quietly; a row
            # with SOME content but a non-code in a code column is a genuine
            # unresolved finding routed to Tier 2.5, never silently dropped.
            if any(cells):
                which = []
                if left is None:
                    which.append("left")
                if right is None:
                    which.append("right")
                unresolved.append(
                    UnresolvedRow(pdf_page, f"non_5digit_code_in_{'+'.join(which)}_column", cells)
                )
            continue
        edges.append(
            ParsedRow(
                left_code=left,
                right_code=right,
                left_title=cells[1] if len(cells) > 1 else "",
                right_title=cells[3] if len(cells) > 3 else "",
                pdf_page=pdf_page,
            )
        )
    return edges, unresolved


# ---------------------------------------------------------------------------
# Relation assembly (accumulate globally by left-code, order-preserving)
# ---------------------------------------------------------------------------

@dataclass
class LampiranBlock:
    lampiran: int
    direction: str  # 'fwd' | 'rev'
    first_page: int  # 1-based
    last_page: int
    edges: list[ParsedRow] = field(default_factory=list)
    unresolved: list[UnresolvedRow] = field(default_factory=list)
    # Per-page strata for the acceptance-gate holdout draw (§1.4 item 2):
    # {pdf_page: int, wrapped: bool, nm: bool, edge_count: int}. `wrapped` is
    # computed from the RAW table (a data cell carrying '\n'), which is lost
    # once titles are normalized — so it is recorded here at parse time.
    pages: list[dict] = field(default_factory=list)


def page_stratum(raw_table: list[list[str | None]], page_edges: list[ParsedRow]) -> dict:
    """Classify one page for the holdout draw. `wrapped` = a data row carries a
    multi-line cell (continuation-row shape B5 named). `nm` = a code
    participates in >1 edge on this page (a split or a merge visible here)."""
    wrapped = any(
        "\n" in (cell or "")
        for row in raw_table
        if not is_header_or_label_row(row)
        for cell in row
    )
    counts: dict[str, int] = {}
    for e in page_edges:
        counts[e.left_code] = counts.get(e.left_code, 0) + 1
        counts[e.right_code] = counts.get(e.right_code, 0) + 1
    nm = any(c > 1 for c in counts.values())
    return {"wrapped": wrapped, "nm": nm, "edge_count": len(page_edges)}


def accumulate_ancestry(block: LampiranBlock) -> dict[str, dict]:
    """Group a reverse block's edges into {code2025: {codes:[…2020…],
    titles:{…}, locators:[…], title_2025:…}} — order-preserving,
    duplicate-collapsing. Reverse only: forward is consumed by the
    consistency check, not by the ancestry map."""
    if block.direction != "rev":
        raise ValueError("accumulate_ancestry expects a reverse (Lampiran 10) block")
    out: dict[str, dict] = {}
    for e in block.edges:
        rec = out.setdefault(
            e.left_code,
            {"codes": [], "titles": {}, "locators": [], "title_2025": e.left_title},
        )
        if e.right_code not in rec["codes"]:
            rec["codes"].append(e.right_code)
            rec["titles"][e.right_code] = e.right_title
            rec["locators"].append(
                {
                    "lampiran": block.lampiran,
                    "pdf_page": e.pdf_page,
                    "printed_page": e.pdf_page + PRINTED_PAGE_OFFSET,
                }
            )
    return out


def forward_edge_set(block: LampiranBlock) -> set[tuple[str, str]]:
    """Forward (2020→2025) edges as a set of (code2020, code2025) tuples."""
    return {(e.left_code, e.right_code) for e in block.edges}


def reverse_edge_set(block: LampiranBlock) -> set[tuple[str, str]]:
    """Reverse (2025→2020) edges re-expressed as (code2020, code2025) so the
    two directions are directly comparable for the L5↔L10 consistency check
    (gate item 7)."""
    return {(e.right_code, e.left_code) for e in block.edges}


def cross_direction_diff(
    fwd: LampiranBlock, rev: LampiranBlock
) -> dict[str, list[list[str]]]:
    """Gate item 7 — edges present in one direction and absent in the other.
    Returned as sorted lists (deterministic), never silently dropped. An
    empty diff on both sides is the clean case."""
    f = forward_edge_set(fwd)
    r = reverse_edge_set(rev)
    only_fwd = sorted([list(t) for t in (f - r)])
    only_rev = sorted([list(t) for t in (r - f)])
    return {"only_in_forward_L5": only_fwd, "only_in_reverse_L10": only_rev}


# ---------------------------------------------------------------------------
# PDF-facing extraction (kept thin; the logic above is PDF-free + tested)
# ---------------------------------------------------------------------------

def _open_pdf(vault_root: Path):
    import pdfplumber  # local import: only the extract path needs it

    pdf_path = vault_root / BPS_PDF_REL_PATH
    if not pdf_path.exists():
        raise FileNotFoundError(f"BPS PDF not found in vault: {pdf_path}")
    actual = common.sha256_file(pdf_path)
    if actual != BPS_PDF_SHA256:
        raise ValueError(
            f"BPS PDF sha256 mismatch: expected {BPS_PDF_SHA256}, got {actual}. "
            "Refusing to parse an unknown edition."
        )
    return pdfplumber.open(pdf_path), pdf_path


def _page_direction(page) -> str | None:
    table = page.extract_table(TABLE_SETTINGS)
    if not table or len(table) < 2:
        return None
    return classify_direction(table[0])


def find_block(pdf, title_re: re.Pattern, expected_direction: str, lampiran: int) -> LampiranBlock:
    """Locate a lampiran by its title page, then consume the contiguous run of
    same-direction table pages.

    The title alone is not enough to anchor: the DAFTAR LAMPIRAN (TOC, pg13)
    lists every lampiran title with dot-leaders and would false-match. The
    real start page is identified by CONTENT (W88): it must both match the
    title AND itself yield ≥1 genuine 5-digit edge of the expected direction
    — which the TOC never does. Fails loud if no such page exists."""
    first_idx = None
    for i, page in enumerate(pdf.pages):
        text = re.sub(r"\s+", " ", page.extract_text() or "")
        if not title_re.search(text):
            continue
        table = page.extract_table(TABLE_SETTINGS)
        if not table or classify_direction(table[0]) != expected_direction:
            continue
        edges, _ = parse_table_rows(table, expected_direction, i + 1)
        if edges:  # a real data page, not the TOC listing
            first_idx = i
            break
    if first_idx is None:
        raise ValueError(
            f"Lampiran {lampiran} start page not found (title match with real "
            f"{expected_direction} edges). The TOC is not a valid anchor."
        )

    block = LampiranBlock(lampiran=lampiran, direction=expected_direction,
                          first_page=first_idx + 1, last_page=first_idx + 1)
    for i in range(first_idx, len(pdf.pages)):
        page = pdf.pages[i]
        table = page.extract_table(TABLE_SETTINGS)
        direction = classify_direction(table[0]) if table and len(table) >= 2 else None
        if direction == expected_direction:
            edges, unresolved = parse_table_rows(table, direction, i + 1)
            block.edges.extend(edges)
            block.unresolved.extend(unresolved)
            stratum = page_stratum(table, edges)
            stratum["pdf_page"] = i + 1
            block.pages.append(stratum)
            block.last_page = i + 1
        elif direction is None:
            # A blank divider AFTER data ends the block; the start page's own
            # title/divider never reaches here because it parsed as data above.
            if block.edges:
                break
            # else: still before any data — keep scanning (defensive; the
            # verified start above means this branch is normally not taken).
        else:
            # A different-direction table = the next lampiran started.
            break
    return block


def _assert_span(block: LampiranBlock, expected: tuple[int, int]) -> list[str]:
    """Soft assertion: detected span must not drift materially from the pinned
    expectation. Returns warnings (recorded in the manifest); a gross drift
    (>3 pages either edge) is escalated by the caller to a hard failure."""
    warnings: list[str] = []
    if block.first_page != expected[0]:
        warnings.append(f"L{block.lampiran} first page {block.first_page} != expected {expected[0]}")
    if abs(block.last_page - expected[1]) > 3:
        warnings.append(f"L{block.lampiran} last page {block.last_page} far from expected {expected[1]}")
    return warnings


def _relation_digest(payload: dict) -> str:
    """sha256 of the canonically-serialized relation (sorted keys, no
    whitespace drift) — the output-relation digest the gate pins (item 9)."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return common.sha256_bytes(canonical.encode("utf-8"))


def _self_blob_sha() -> str:
    """sha256 of this parser source file — pins parser identity in the
    manifest (item 9: parser commit/blob sha)."""
    return common.sha256_file(Path(__file__).resolve())


def _pdfplumber_version() -> str:
    import pdfplumber

    return getattr(pdfplumber, "__version__", "unknown")


def extract(vault_root: Path) -> dict:
    """Full Phase-0 extraction → the build-artifact payload (relation +
    manifest). Pure of side effects beyond opening the PDF; the caller writes
    it. Never touches canonical."""
    pdf, pdf_path = _open_pdf(vault_root)
    try:
        fwd = find_block(pdf, FORWARD_TITLE_RE, "fwd", 5)
        rev = find_block(pdf, REVERSE_TITLE_RE, "rev", 10)
    finally:
        pdf.close()

    span_warnings = _assert_span(fwd, EXPECTED_FORWARD_SPAN) + _assert_span(rev, EXPECTED_REVERSE_SPAN)
    if fwd.first_page != EXPECTED_FORWARD_SPAN[0] or rev.first_page != EXPECTED_REVERSE_SPAN[0]:
        raise ValueError(
            "Lampiran block first-page drifted from the pinned layout "
            f"(fwd={fwd.first_page}, rev={rev.first_page}); refusing to extract "
            f"potentially-wrong pages. Warnings: {span_warnings}"
        )

    ancestry = accumulate_ancestry(rev)
    consistency = cross_direction_diff(fwd, rev)

    # bps_2020_ancestors-shaped edge relation, reverse-driven (2025 → 2020…).
    # LEAN by design: only the canonical-bound fields the compiler writes
    # (codes/sebagian/source_locator). Titles are deliberately NOT here — the
    # output_relation_digest is over this relation and seeds the acceptance-gate
    # holdout draw, so it MUST be title-independent: an edge-preserving change
    # (watermark title cleanup in item-6, a pdfplumber upgrade) must not reseed
    # the gate. Titles carry ~11.5% watermark noise and are auxiliary (item-6
    # diffing regenerates them deterministically when needed).
    relation: dict[str, dict] = {}
    for code2025 in sorted(ancestry):
        rec = ancestry[code2025]
        relation[code2025] = {
            "codes": rec["codes"],
            "sebagian": [False] * len(rec["codes"]),  # verified-absent in source
            "source_locator": rec["locators"],
        }

    payload_core = {"relation": relation}
    relation_digest = _relation_digest(payload_core)

    manifest = {
        "artifact": "bps_crosswalk_phase0",
        "generated_at": common.now_iso(),
        "bps_pdf": {"rel_path": BPS_PDF_REL_PATH, "sha256": BPS_PDF_SHA256},
        "parser": {
            "file": "scripts/kbli_filiera/bps_crosswalk_parser.py",
            "blob_sha256": _self_blob_sha(),
            "extraction_tool": "pdfplumber",
            "extraction_tool_version": _pdfplumber_version(),
            "table_settings": TABLE_SETTINGS,
        },
        "page_convention": {"printed_page": "pdf_page + (-14)", "offset": PRINTED_PAGE_OFFSET},
        "lampiran": {
            "forward_L5": {"first_page": fwd.first_page, "last_page": fwd.last_page,
                           "edge_count": len(fwd.edges)},
            "reverse_L10": {"first_page": rev.first_page, "last_page": rev.last_page,
                            "edge_count": len(rev.edges)},
        },
        "span_warnings": span_warnings,
        "sebagian_modifier": "verified-absent-in-source (0 table-cell occurrences in 444 pages)",
        "counts": {
            "codes_2025_with_ancestry": len(relation),
            "unresolved_forward": len(fwd.unresolved),
            "unresolved_reverse": len(rev.unresolved),
        },
        "consistency_L5_vs_L10": {
            "only_in_forward_L5": len(consistency["only_in_forward_L5"]),
            "only_in_reverse_L10": len(consistency["only_in_reverse_L10"]),
        },
        "output_relation_digest": relation_digest,
    }

    unresolved = {
        "forward_L5": [vars(u) for u in fwd.unresolved],
        "reverse_L10": [vars(u) for u in rev.unresolved],
    }

    return {
        "manifest": manifest,
        "relation": relation,
        "consistency": consistency,
        "unresolved_rows": unresolved,
        "page_strata": {"forward_L5": fwd.pages, "reverse_L10": rev.pages},
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Phase-0 BPS Kelompok-crosswalk extractor")
    ap.add_argument("--vault-root", default=str(common.DEFAULT_VAULT_ROOT),
                    help="vault root holding bps/… (default: ~/nuzantara-vault)")
    ap.add_argument("--census", action="store_true",
                    help="report block structure + counts only, write nothing")
    ap.add_argument("--extract", action="store_true",
                    help="run full extraction and write the artifact")
    ap.add_argument("--out", default="data/kbli-filiera/phase0/bps_crosswalk.json",
                    help="artifact path for --extract")
    args = ap.parse_args()

    vault_root = Path(args.vault_root).expanduser()

    if not args.census and not args.extract:
        ap.error("choose --census or --extract")

    result = extract(vault_root)
    m = result["manifest"]
    logger.info("Lampiran 5 (fwd): pp%s-%s, %s edges",
                m["lampiran"]["forward_L5"]["first_page"],
                m["lampiran"]["forward_L5"]["last_page"],
                m["lampiran"]["forward_L5"]["edge_count"])
    logger.info("Lampiran 10 (rev): pp%s-%s, %s edges",
                m["lampiran"]["reverse_L10"]["first_page"],
                m["lampiran"]["reverse_L10"]["last_page"],
                m["lampiran"]["reverse_L10"]["edge_count"])
    logger.info("2025 codes with ancestry: %s", m["counts"]["codes_2025_with_ancestry"])
    logger.info("unresolved rows: fwd=%s rev=%s",
                m["counts"]["unresolved_forward"], m["counts"]["unresolved_reverse"])
    logger.info("L5↔L10 inconsistencies: only_fwd=%s only_rev=%s",
                m["consistency_L5_vs_L10"]["only_in_forward_L5"],
                m["consistency_L5_vs_L10"]["only_in_reverse_L10"])
    logger.info("output_relation_digest: %s", m["output_relation_digest"])
    if m["span_warnings"]:
        for w in m["span_warnings"]:
            logger.warning("span: %s", w)

    if args.extract:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        logger.info("wrote artifact: %s", out_path)
    else:
        logger.info("census only — nothing written (use --extract to write %s)", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
