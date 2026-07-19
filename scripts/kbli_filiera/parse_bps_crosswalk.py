#!/usr/bin/env python3
"""parse_bps_crosswalk — Phase-0 deterministic BPS crosswalk extraction (Batch B).

Extracts the KBLI 2020<->2025 kelompok conversion relation from the vault-pinned
BPS Tabel Konversi Vol.2 PDF (sha256 29f17b3b...), per the frozen REV-4b design
`research/operations/2026-07-19-kbli-batch-b-design.md` (spec) §1.4:

- Lampiran 5  (KBLI 2020 -> 2025, forward),  PDF pages 131-245 (empirical span;
  the spec's "131-246" table row includes the trailing blank separator p.246).
- Lampiran 10 (KBLI 2025 -> 2020, reverse), PDF pages 325-442 (p.443 blank,
  p.444 footer-only — both carry zero table content, calibrated 2026-07-20).

Extraction is ROW-ANCHORED and geometry-grounded (spec §1.4 item 4):
- The table grid is drawn as thin full-width horizontal rects; the region
  between two consecutive full-width rules is one BAND = one physical row.
  Calibration 2026-07-20 verified rules are always full-width on data pages
  (no vertically-merged cells; splits/merges repeat the left-side cells).
- Every band must anchor on exactly one 5-digit code in the LEFT code column
  and exactly one in the RIGHT code column; anything else fails CLOSED into
  the unresolved-rows manifest (spec §1.4 item 8) — never guessed.
- WATERMARK: every page carries a diagonal "https://www.bps.go.id" watermark
  whose glyphs are fontname GZJQED+Arial-BoldMT (body text is the Aptos
  family; footers Verdana/Aptos). Watermark glyphs spatially merge into body
  words ("01118o", "01s279", "p01121" — the v0 prototype's 18% row loss).
  Chars whose fontname contains "Arial" are dropped BEFORE word assembly.
- `sebagian` (partial-mapping modifier) is extracted as a first-class
  attribute wherever it appears (spec §1.4 item 5). Empirical calibration
  note: the whole Vol.2 text layer contains zero `sebagian` occurrences in
  the L5/L10 tables (the 2 PDF-wide hits are the copyright page and an
  intro prose paragraph); the capability is implemented and the observed
  count is recorded honestly in the manifest.
- `uraian` (title) columns are captured for every edge and diffed for
  MATCH_LANGSUNG codes (spec §1.4 item 6) against both the in-table 2020
  title and the canonical judul.

Pinning (spec §1.4 item 9) lands in parser-run-manifest.json: PDF sha256,
pdfplumber+Python versions, parser source digests, page-numbering convention
(printed = pdf_page - 14, footer-verified per page), canonical input blob
sha256, output relation digest (parser_run_digest), unresolved-row manifest,
row-level locators, independent row-count ground truth (poppler pdftotext
lane vs pdfplumber band lane).

Writes ONLY under data/kbli-filiera/bps-crosswalk/ (data-plane guard #2550:
this script lives in scripts/kbli_filiera/, the sanctioned writer perimeter).

Run (pdfplumber lives in the backend venv):
    apps/backend-rag/.venv/bin/python scripts/kbli_filiera/parse_bps_crosswalk.py --full-run
    apps/backend-rag/.venv/bin/python scripts/kbli_filiera/parse_bps_crosswalk.py --calibrate 132 399
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PDF = Path("~/nuzantara-vault/bps/tabel-konversi-kbli-2020-2025-volume2-2026.pdf").expanduser()
EXPECTED_PDF_SHA256 = "29f17b3b133497a88c5bfd0eaa3f73c90233b9b95dd76dd0ea2ccaed31724949"
CANONICAL_PATH = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
OUT_DIR = REPO_ROOT / "data/kbli-filiera/bps-crosswalk"

# Frozen page spans (calibration 2026-07-20; see module docstring).
LAMPIRAN_SPANS = {
    5: (131, 245),   # PDF pages, inclusive; col1=KBLI2020, col3=KBLI2025
    10: (325, 442),  # PDF pages, inclusive; col1=KBLI2025, col3=KBLI2020
}
# Boundary guard: these pages must contain ZERO data bands (blank separators /
# non-kelompok lampiran) — fail-visible if violated.
BOUNDARY_GUARD_PAGES = [246, 247, 248, 249, 250, 323, 324, 443, 444]

PRINTED_PAGE_OFFSET = 14  # printed = pdf_page - 14, footer-verified per page

# Column zones (pts, calibrated across both lampiran; per-page code-column x0
# drift observed 46-66 left / 262-295 right — zones hold with margin and are
# cross-checked per page against the (1)/(3) label-row centers).
LEFT_CODE_ZONE = (38.0, 80.0)
RIGHT_CODE_ZONE = (255.0, 302.0)
COL2_MIN_X = 80.0
COL4_MIN_X = 302.0

CODE_RE = re.compile(r"^\d{5}$")
SEBAGIAN_RE = re.compile(r"sebagian", re.IGNORECASE)

HEADER_TOKENS = {"KBLI", "Judul", "(1)", "(2)", "(3)", "(4)", "2020", "2025"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canon_json(obj) -> str:
    """Canonical serialization for digests: sorted keys, no whitespace drift."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")


def norm_title(text: str) -> str:
    """Normalization for title comparison ONLY (raw text is always stored):
    NFKC, casefold, collapse whitespace, drop space after hyphen (line-wrap
    artifact "Kacang- Kacangan"), strip surrounding punctuation spacing."""
    t = unicodedata.normalize("NFKC", text)
    t = t.casefold()
    t = re.sub(r"-\s+", "-", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ---------------------------------------------------------------------------
# Page-level extraction
# ---------------------------------------------------------------------------

@dataclass
class Band:
    top: float
    bottom: float
    words: list = field(default_factory=list)
    kind: str = "unclassified"  # header | data | continuation | empty | unresolved
    reason: str = ""


def keep_char(obj) -> bool:
    """pdfplumber filter predicate: drop the Arial-BoldMT watermark glyphs."""
    if obj.get("object_type") != "char":
        return True
    return "Arial" not in (obj.get("fontname") or "")


def page_rules(page) -> list[float]:
    """Full-width horizontal rule y-positions (band boundaries)."""
    clusters: dict[int, list] = defaultdict(list)
    for r in page.rects:
        if (r["x1"] - r["x0"]) > 30 and (r["bottom"] - r["top"]) < 3:
            clusters[round(r["top"])].append(r)
    tops = []
    for t, rs in clusters.items():
        span = max(r["x1"] for r in rs) - min(r["x0"] for r in rs)
        if span >= 300:  # full-width (page body ~430-446pt wide)
            tops.append(float(t))
    return sorted(tops)


def cluster_lines(words: list) -> list[list]:
    """Group words into visual lines by top (2.6pt tolerance), reading order."""
    lines: list[list] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= 2.6:
            lines[-1].append(w)
        else:
            lines.append([w])
    return lines


def cell_text(words: list) -> str:
    parts = []
    for line in cluster_lines(words):
        parts.append(" ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"])))
    return " ".join(p for p in parts if p).strip()


def extract_page(page, pdf_page: int, lampiran: int) -> dict:
    """Parse one page into bands -> rows. Returns page record with rows,
    unresolved bands, flags, and the geometric/textual censuses."""
    filtered = page.filter(keep_char)
    words = filtered.extract_words(keep_blank_chars=False, use_text_flow=False)
    rules = page_rules(page)
    out = {
        "pdf_page": pdf_page,
        "printed_page": pdf_page - PRINTED_PAGE_OFFSET,
        "lampiran": lampiran,
        "rows": [],
        "unresolved": [],
        "n_rules": len(rules),
        "footer_printed_ok": None,
        "label_row_ok": None,
        "has_continuation_first_band": False,
    }

    # Footer verification (printed-page convention): digit chars below y=675.
    foot = sorted(
        (c for c in filtered.chars if c["top"] > 675 and c["text"].isdigit()),
        key=lambda c: c["x0"],
    )
    foot_txt = "".join(c["text"] for c in foot).strip()
    out["footer_printed_ok"] = bool(foot_txt) and foot_txt.isdigit() and int(foot_txt) == pdf_page - PRINTED_PAGE_OFFSET

    if len(rules) < 2:
        return out  # no table grid on this page (blank/separator)

    # Label-row cross-check: "(1)"/"(3)" centers must sit inside the code zones.
    lbl = {w["text"]: (w["x0"] + w["x1"]) / 2 for w in words if w["text"] in {"(1)", "(3)"}}
    if "(1)" in lbl and "(3)" in lbl:
        out["label_row_ok"] = (
            LEFT_CODE_ZONE[0] <= lbl["(1)"] <= LEFT_CODE_ZONE[1] + 10
            and RIGHT_CODE_ZONE[0] <= lbl["(3)"] <= RIGHT_CODE_ZONE[1] + 10
        )

    # Bands between consecutive rules; assign words by vertical center.
    bands = [Band(top=rules[i], bottom=rules[i + 1]) for i in range(len(rules) - 1)]
    for w in words:
        yc = (w["top"] + w["bottom"]) / 2
        for b in bands:
            if b.top <= yc < b.bottom:
                b.words.append(w)
                break

    for idx, b in enumerate(bands):
        if not b.words:
            b.kind = "empty"
            continue
        texts = {w["text"] for w in b.words}
        left_codes = [w for w in b.words if CODE_RE.match(w["text"]) and LEFT_CODE_ZONE[0] <= w["x0"] < LEFT_CODE_ZONE[1]]
        right_codes = [w for w in b.words if CODE_RE.match(w["text"]) and RIGHT_CODE_ZONE[0] <= w["x0"] < RIGHT_CODE_ZONE[1]]
        if not left_codes and not right_codes:
            if texts & HEADER_TOKENS:
                b.kind = "header"
                continue
            # No codes at all: candidate cross-page title continuation if it is
            # the first content band; else unresolved (fail-closed).
            if idx <= 2 and not out["rows"]:
                b.kind = "continuation"
                out["has_continuation_first_band"] = True
                out["unresolved"].append({
                    "pdf_page": pdf_page, "band": [round(b.top, 1), round(b.bottom, 1)],
                    "reason": "first_band_no_codes_possible_continuation",
                    "text": cell_text(b.words)[:200],
                })
                continue
            b.kind = "unresolved"
            b.reason = "no_code_anchor"
            out["unresolved"].append({
                "pdf_page": pdf_page, "band": [round(b.top, 1), round(b.bottom, 1)],
                "reason": "no_code_anchor", "text": cell_text(b.words)[:200],
            })
            continue
        if len(left_codes) != 1 or len(right_codes) != 1:
            b.kind = "unresolved"
            b.reason = f"ambiguous_anchors_left={len(left_codes)}_right={len(right_codes)}"
            out["unresolved"].append({
                "pdf_page": pdf_page, "band": [round(b.top, 1), round(b.bottom, 1)],
                "reason": b.reason, "text": cell_text(b.words)[:200],
            })
            continue

        b.kind = "data"
        lc, rc = left_codes[0], right_codes[0]
        col2_words = [w for w in b.words if COL2_MIN_X <= w["x0"] < RIGHT_CODE_ZONE[0] and w is not lc]
        col4_words = [w for w in b.words if w["x0"] >= COL4_MIN_X and w is not rc]
        # sebagian: any word in a CODE cell zone (left/right) that is not the
        # code itself; plus explicit 'sebagian' tokens anywhere in the band.
        left_cell_extras = [w for w in b.words if w["x0"] < COL2_MIN_X and w is not lc]
        right_cell_extras = [w for w in b.words if RIGHT_CODE_ZONE[0] <= w["x0"] < COL4_MIN_X and w is not rc]
        seb_left = any(SEBAGIAN_RE.search(w["text"]) for w in left_cell_extras)
        seb_right = any(SEBAGIAN_RE.search(w["text"]) for w in right_cell_extras)
        code_cell_noise = [w["text"] for w in (left_cell_extras + right_cell_extras)
                           if not SEBAGIAN_RE.search(w["text"])]

        n_lines = max(len(cluster_lines(col2_words)) if col2_words else 1,
                      len(cluster_lines(col4_words)) if col4_words else 1)
        out["rows"].append({
            "left_code": lc["text"],
            "right_code": rc["text"],
            "left_title": cell_text(col2_words),
            "right_title": cell_text(col4_words),
            "sebagian_left": seb_left,
            "sebagian_right": seb_right,
            "code_cell_noise": code_cell_noise,
            "band": [round(b.top, 1), round(b.bottom, 1)],
            "n_title_lines": n_lines,
            "continuation_text": "",
        })
    return out


# ---------------------------------------------------------------------------
# Independent row-count lane (poppler pdftotext -layout, different library)
# ---------------------------------------------------------------------------

def pdftotext_row_count(pdf_path: Path, first: int, last: int) -> dict:
    """Counts lines whose leading columns hold a bare 5-digit code, per page.
    Independent of pdfplumber (poppler C++ lane). The watermark pollutes some
    glyph runs in pdftotext too, but the LEFT code column is outside the
    diagonal's x-range on the calibrated pages; divergences vs the band lane
    are enumerated per page and eye-adjudicated, never averaged away."""
    per_page: dict[int, int] = {}
    for pno in range(first, last + 1):
        try:
            txt = subprocess.run(
                ["pdftotext", "-f", str(pno), "-l", str(pno), "-layout", str(pdf_path), "-"],
                capture_output=True, text=True, timeout=60, check=True,
            ).stdout
        except (subprocess.SubprocessError, FileNotFoundError) as exc:  # fail-visible
            per_page[pno] = -1
            continue
        n = 0
        for line in txt.splitlines():
            # LEFT-column code = 5-digit first token at indent <= 4 (the left
            # code column sits at cols 1-7 in -layout output; right-column-only
            # lines carry ~40+ leading spaces; title columns start ~col 10).
            if re.match(r"^ {0,4}\d{5}(\s|$)", line):
                n += 1
        per_page[pno] = n
    return per_page


# ---------------------------------------------------------------------------
# Full run
# ---------------------------------------------------------------------------

def run_full(pdf_path: Path, out_dir: Path) -> int:
    pdf_sha = sha256_file(pdf_path)
    if pdf_sha != EXPECTED_PDF_SHA256:
        print(f"FATAL: PDF sha256 {pdf_sha} != vault pin {EXPECTED_PDF_SHA256}", file=sys.stderr)
        return 2
    canonical_sha = sha256_file(CANONICAL_PATH)
    canonical = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
    canon_records = canonical["data"]
    canon_by_code = {r["kode_kbli_2025"]: r for r in canon_records if r.get("kode_kbli_2025")}

    edges = {5: [], 10: []}
    unresolved_all = []
    page_census = []
    sebagian_count = 0
    boundary_guard = {}

    with pdfplumber.open(pdf_path) as pdf:
        # Boundary guard: zero data bands outside the frozen spans.
        for pno in BOUNDARY_GUARD_PAGES:
            rec = extract_page(pdf.pages[pno - 1], pno, 0)
            boundary_guard[str(pno)] = len(rec["rows"])

        for lampiran, (first, last) in LAMPIRAN_SPANS.items():
            prev_page_rows = None
            for pno in range(first, last + 1):
                rec = extract_page(pdf.pages[pno - 1], pno, lampiran)
                # Cross-page title continuation: attach to the LAST row of the
                # PREVIOUS page (deterministic, flagged; the edge itself was
                # anchored there — fail-closed rule only guards edges, titles
                # keep their completeness via this stitch).
                cont = [u for u in rec["unresolved"] if u["reason"] == "first_band_no_codes_possible_continuation"]
                if cont and prev_page_rows:
                    prev_page_rows[-1]["continuation_text"] = cont[0]["text"]
                    rec["unresolved"] = [u for u in rec["unresolved"] if u["reason"] != "first_band_no_codes_possible_continuation"]
                for row in rec["rows"]:
                    if lampiran == 5:
                        k2020, k2025 = row["left_code"], row["right_code"]
                        t2020, t2025 = row["left_title"], row["right_title"]
                        s2020, s2025 = row["sebagian_left"], row["sebagian_right"]
                    else:
                        k2025, k2020 = row["left_code"], row["right_code"]
                        t2025, t2020 = row["left_title"], row["right_title"]
                        s2025, s2020 = row["sebagian_left"], row["sebagian_right"]
                    if s2020 or s2025:
                        sebagian_count += 1
                    edges[lampiran].append({
                        "kbli_2020": k2020,
                        "kbli_2025": k2025,
                        "uraian_2020": t2020,
                        "uraian_2025": t2025,
                        "sebagian_2020": s2020,
                        "sebagian_2025": s2025,
                        "code_cell_noise": row["code_cell_noise"],
                        "lampiran": lampiran,
                        "pdf_page": rec["pdf_page"],
                        "printed_page": rec["printed_page"],
                        "band": row["band"],
                        "n_title_lines": row["n_title_lines"],
                        "title_continued_from_next_page": bool(row["continuation_text"]),
                        "continuation_text": row["continuation_text"],
                    })
                unresolved_all.extend(rec["unresolved"])
                page_census.append({
                    "pdf_page": rec["pdf_page"],
                    "printed_page": rec["printed_page"],
                    "lampiran": lampiran,
                    "n_rows": len(rec["rows"]),
                    "n_unresolved": len(rec["unresolved"]),
                    "n_rules": rec["n_rules"],
                    "footer_printed_ok": rec["footer_printed_ok"],
                    "label_row_ok": rec["label_row_ok"],
                    "has_continuation_first_band": rec["has_continuation_first_band"],
                    "has_wrapped_row": any(r["n_title_lines"] >= 2 for r in rec["rows"]),
                    "max_title_lines": max((r["n_title_lines"] for r in rec["rows"]), default=0),
                })
                if rec["rows"]:
                    prev_page_rows = rec["rows"]

    # Relation degrees -> N:M flags per page (within each lampiran's edge set).
    for lampiran in (5, 10):
        fwd = Counter(e["kbli_2020"] for e in edges[lampiran])
        rev = Counter(e["kbli_2025"] for e in edges[lampiran])
        nm_pages = {e["pdf_page"] for e in edges[lampiran] if fwd[e["kbli_2020"]] > 1 or rev[e["kbli_2025"]] > 1}
        for pc in page_census:
            if pc["lampiran"] == lampiran:
                pc["has_nm_relation"] = pc["pdf_page"] in nm_pages

    # L5 <-> L10 consistency (spec §1.4 item 7): compare edge SETS.
    set5 = {(e["kbli_2020"], e["kbli_2025"]) for e in edges[5]}
    set10 = {(e["kbli_2020"], e["kbli_2025"]) for e in edges[10]}
    loc5 = defaultdict(list)
    for e in edges[5]:
        loc5[(e["kbli_2020"], e["kbli_2025"])].append({"pdf_page": e["pdf_page"], "band": e["band"]})
    loc10 = defaultdict(list)
    for e in edges[10]:
        loc10[(e["kbli_2020"], e["kbli_2025"])].append({"pdf_page": e["pdf_page"], "band": e["band"]})
    only5 = sorted(set5 - set10)
    only10 = sorted(set10 - set5)
    dup5 = sorted([k for k, v in Counter((e["kbli_2020"], e["kbli_2025"]) for e in edges[5]).items() if v > 1])
    dup10 = sorted([k for k, v in Counter((e["kbli_2020"], e["kbli_2025"]) for e in edges[10]).items() if v > 1])
    consistency = {
        "edges_l5": len(edges[5]),
        "edges_l10": len(edges[10]),
        "unique_pairs_l5": len(set5),
        "unique_pairs_l10": len(set10),
        "pairs_in_both": len(set5 & set10),
        "in_l5_only": [{"kbli_2020": a, "kbli_2025": b, "locators": loc5[(a, b)]} for a, b in only5],
        "in_l10_only": [{"kbli_2020": a, "kbli_2025": b, "locators": loc10[(a, b)]} for a, b in only10],
        "duplicate_pairs_l5": [{"kbli_2020": a, "kbli_2025": b, "locators": loc5[(a, b)]} for a, b in dup5],
        "duplicate_pairs_l10": [{"kbli_2020": a, "kbli_2025": b, "locators": loc10[(a, b)]} for a, b in dup10],
        "sebagian_flag_mismatches": [],
        "unique_2025_codes_l10": len({e["kbli_2025"] for e in edges[10]}),
        "unique_2020_codes_l5": len({e["kbli_2020"] for e in edges[5]}),
    }

    # MATCH_LANGSUNG title-diff (spec §1.4 item 6) + canonical judul diff.
    langsung_codes = {r["kode_kbli_2025"] for r in canon_records if r.get("status_mapping") == "MATCH_LANGSUNG"}
    same_code_changed_title = []
    canonical_title_mismatch = []
    seen_2025 = {}
    for e in edges[5] + edges[10]:
        if e["kbli_2020"] == e["kbli_2025"]:
            full_2025 = (e["uraian_2025"] + (" " + e["continuation_text"] if e["title_continued_from_next_page"] and e["lampiran"] == 5 else "")).strip()
            if norm_title(e["uraian_2020"]) != norm_title(e["uraian_2025"]):
                same_code_changed_title.append({
                    "code": e["kbli_2020"],
                    "in_match_langsung_canonical": e["kbli_2020"] in langsung_codes,
                    "uraian_2020": e["uraian_2020"],
                    "uraian_2025": e["uraian_2025"],
                    "lampiran": e["lampiran"], "pdf_page": e["pdf_page"], "band": e["band"],
                })
        if e["kbli_2025"] not in seen_2025:
            seen_2025[e["kbli_2025"]] = e
            canon_rec = canon_by_code.get(e["kbli_2025"])
            if canon_rec and norm_title(canon_rec.get("judul", "")) != norm_title(e["uraian_2025"]):
                canonical_title_mismatch.append({
                    "code": e["kbli_2025"],
                    "canonical_judul": canon_rec.get("judul", ""),
                    "table_uraian_2025": e["uraian_2025"],
                    "lampiran": e["lampiran"], "pdf_page": e["pdf_page"], "band": e["band"],
                })
    # de-dup same_code_changed_title on (code, lampiran) keeping first locator
    dedup = {}
    for f in same_code_changed_title:
        dedup.setdefault((f["code"], f["lampiran"]), f)
    same_code_changed_title = sorted(dedup.values(), key=lambda f: (f["code"], f["lampiran"]))
    title_diff = {
        "same_code_changed_title": same_code_changed_title,
        "same_code_changed_title_count": len(same_code_changed_title),
        "canonical_title_mismatch": sorted(canonical_title_mismatch, key=lambda f: f["code"]),
        "canonical_title_mismatch_count": len(canonical_title_mismatch),
        "match_langsung_canonical_total": len(langsung_codes),
    }

    # Independent row-count lane (poppler).
    pcount = {}
    for lampiran, (first, last) in LAMPIRAN_SPANS.items():
        pcount[lampiran] = pdftotext_row_count(pdf_path, first, last)
    band_counts = {lampiran: sum(pc["n_rows"] for pc in page_census if pc["lampiran"] == lampiran) for lampiran in (5, 10)}
    poppler_counts = {lampiran: sum(v for v in pcount[lampiran].values() if v >= 0) for lampiran in (5, 10)}
    divergent_pages = {
        str(lampiran): [
            {"pdf_page": pc["pdf_page"], "band_rows": pc["n_rows"], "pdftotext_rows": pcount[lampiran].get(pc["pdf_page"], -1)}
            for pc in page_census
            if pc["lampiran"] == lampiran and pc["n_rows"] != pcount[lampiran].get(pc["pdf_page"], -1)
        ]
        for lampiran in (5, 10)
    }

    # Output relation digest: content-pure (edges only, no timestamps).
    e5 = sorted(edges[5], key=lambda e: (e["pdf_page"], e["band"][0]))
    e10 = sorted(edges[10], key=lambda e: (e["pdf_page"], e["band"][0]))
    parser_run_digest = hashlib.sha256((canon_json(e5) + canon_json(e10)).encode("utf-8")).hexdigest()

    parser_src = Path(__file__).resolve()
    try:
        git_blob = subprocess.run(
            ["git", "hash-object", str(parser_src)], capture_output=True, text=True, timeout=20, check=True,
            cwd=str(REPO_ROOT),
        ).stdout.strip()
    except subprocess.SubprocessError:
        git_blob = None

    manifest = {
        "spec": "research/operations/2026-07-19-kbli-batch-b-design.md (REV-4b) §1.4",
        "bps_pdf": {"path": str(pdf_path), "sha256": pdf_sha, "pages": 444},
        "extraction_tool": {
            "library": "pdfplumber",
            "version": pdfplumber.__version__,
            "flags": {
                "char_filter": "drop chars whose fontname contains 'Arial' (diagonal 'https://www.bps.go.id' watermark; body=Aptos family)",
                "extract_words": {"keep_blank_chars": False, "use_text_flow": False},
                "band_rule": "full-width horizontal rects (width-span>=300pt, height<3pt), bands = inter-rule regions, word assignment by vertical center",
                "anchor_rule": "exactly one ^\\d{5}$ in LEFT zone [38,80) AND exactly one in RIGHT zone [255,302) per band; else fail-closed to unresolved",
            },
        },
        "python": {"version": platform.python_version(), "implementation": platform.python_implementation()},
        "parser_source": {"path": "scripts/kbli_filiera/parse_bps_crosswalk.py", "sha256": sha256_file(parser_src), "git_blob": git_blob},
        "page_numbering": {
            "convention": f"printed_page = pdf_page - {PRINTED_PAGE_OFFSET}",
            "footer_verified_pages": sum(1 for pc in page_census if pc["footer_printed_ok"]),
            "footer_total_pages": len(page_census),
            "footer_failures": [pc["pdf_page"] for pc in page_census if not pc["footer_printed_ok"]],
        },
        "canonical_input": {"path": "data/source_documents/KBLI_2025_FINAL_CLEAN.json", "sha256": canonical_sha},
        "lampiran_spans_pdf_pages": {str(k): list(v) for k, v in LAMPIRAN_SPANS.items()},
        "boundary_guard_data_bands": boundary_guard,
        "parser_run_digest": parser_run_digest,
        "edges": {"lampiran5": len(edges[5]), "lampiran10": len(edges[10])},
        "unresolved_rows": len(unresolved_all),
        "sebagian_observed_rows": sebagian_count,
        "sebagian_note": "capability implemented (code-cell modifier scan); Vol.2 L5/L10 tables carry zero 'sebagian' markers (2 PDF-wide hits are copyright/prose pages) — calibration 2026-07-20",
        "row_count_ground_truth": {
            "band_lane": band_counts,
            "pdftotext_lane": poppler_counts,
            "divergent_pages": divergent_pages,
            "note": "two independent extraction lanes (pdfplumber geometry vs poppler layout-text); per-page divergences MUST be eye-adjudicated before the §1.4 gate uses a frozen true count",
        },
        "label_row_failures": [pc["pdf_page"] for pc in page_census if pc["label_row_ok"] is False],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "edges-lampiran5.json", e5)
    write_json(out_dir / "edges-lampiran10.json", e10)
    write_json(out_dir / "unresolved-rows.json", sorted(unresolved_all, key=lambda u: (u["pdf_page"], u["band"][0])))
    write_json(out_dir / "page-census.json", sorted(page_census, key=lambda p: p["pdf_page"]))
    write_json(out_dir / "consistency-l5-l10.json", consistency)
    write_json(out_dir / "title-diff-report.json", title_diff)
    write_json(out_dir / "parser-run-manifest.json", manifest)

    print(json.dumps({
        "parser_run_digest": parser_run_digest,
        "edges_l5": len(edges[5]), "edges_l10": len(edges[10]),
        "unresolved": len(unresolved_all),
        "pairs_l5_only": len(only5), "pairs_l10_only": len(only10),
        "band_counts": band_counts, "pdftotext_counts": poppler_counts,
        "divergent_pages": {k: len(v) for k, v in divergent_pages.items()},
        "sebagian_rows": sebagian_count,
        "same_code_changed_title": len(same_code_changed_title),
        "boundary_guard": boundary_guard,
        "out_dir": str(out_dir),
    }, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Calibration mode (stdout only, no artifact writes)
# ---------------------------------------------------------------------------

def run_calibrate(pdf_path: Path, pages: list[int]) -> int:
    with pdfplumber.open(pdf_path) as pdf:
        for pno in pages:
            lampiran = 5 if LAMPIRAN_SPANS[5][0] <= pno <= LAMPIRAN_SPANS[5][1] else 10
            rec = extract_page(pdf.pages[pno - 1], pno, lampiran)
            print(f"\n=== p{pno} (lampiran {lampiran}) rows={len(rec['rows'])} unresolved={len(rec['unresolved'])} "
                  f"rules={rec['n_rules']} footer_ok={rec['footer_printed_ok']} label_ok={rec['label_row_ok']} ===")
            for r in rec["rows"]:
                seb = ""
                if r["sebagian_left"] or r["sebagian_right"]:
                    seb = f" SEBAGIAN(L={r['sebagian_left']},R={r['sebagian_right']})"
                noise = f" NOISE={r['code_cell_noise']}" if r["code_cell_noise"] else ""
                print(f"  {r['left_code']} -> {r['right_code']}{seb}{noise} | {r['left_title'][:60]} || {r['right_title'][:60]}")
            for u in rec["unresolved"]:
                print(f"  UNRESOLVED {u['band']}: {u['reason']} | {u['text'][:80]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--full-run", action="store_true")
    g.add_argument("--calibrate", nargs="+", type=int, metavar="PAGE")
    args = ap.parse_args()
    if args.calibrate:
        return run_calibrate(args.pdf, args.calibrate)
    return run_full(args.pdf, args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
