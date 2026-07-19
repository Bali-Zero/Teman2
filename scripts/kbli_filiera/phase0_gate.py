#!/usr/bin/env python3
"""phase0_gate — the §1.4 acceptance gate for the Batch-B BPS crosswalk parser.

Implements, VERBATIM from the frozen REV-4b spec
(`research/operations/2026-07-19-kbli-batch-b-design.md` §1.4), the
deterministic truth-sample machinery and the one-shot scoring:

- item 2 draw: per lampiran, rank every eligible (data) page by
  `SHA256(parser_run_digest + ":" + lampiran_id + ":" + zero_padded_printed_page)`
  hex ascending (lampiran_id is the bare number as string, "5"/"10";
  zero-padded printed page to 4 digits per the REV-4b conductor amendment),
  then a deterministic greedy fill: >=3 wrapped/continuation-row pages, then
  >=3 N:M-relation pages, then any pages to 10 total. A page already taken
  counts toward EVERY stratum it satisfies; the same page is never taken
  twice. FROZEN interpretation of "continue walking" (documented here
  because the spec's prose admits two readings): each greedy phase re-scans
  the rank-ascending list from the top over not-yet-selected pages — i.e.
  every phase takes the LOWEST-RANKED pages satisfying its stratum, which is
  the spec's own stated selection property; a single forward-only pointer
  could dead-end with an unfillable stratum, which the spec's construction
  clearly does not intend.
- tuning/holdout split: by final rank order of the 10 selected pages,
  odd rank-position -> tuning, even -> holdout (item 2).
- item 3 m_P: precision/recall against the TUNING half, repeatable diagnostic.
- item 2 pass criterion: edge-level precision >= 0.995 AND recall >= 0.995 on
  the HOLDOUT half only, scored EXACTLY ONCE — this script refuses to score
  the holdout twice (the presence of holdout-scores.json is the latch).
- item 10 AQL derivation rule: ISO 2859-1 single sampling, General
  Inspection Level II, normal inspection; AQL class = smallest standard AQL
  value >= the measured holdout edge error rate := max(1-precision,
  1-recall); lot size = the Tier-4 stratum code count; switching: tightened
  after 2 of 5 consecutive lots rejected, back to normal after 5 consecutive
  accepted under tightened.

ANTI-SELF-GRADING (mandate MINI-A1): truth labels are produced by a BLIND
cross-family seat (Kimi K3 / GLM on 300-dpi renders — never this session,
never the parser) and FROZEN (sha256 + seat identity) via --freeze-labels
BEFORE any scoring. --score-holdout refuses to run without a freeze record,
and --freeze-labels refuses to run after a holdout score exists.

Edge identity for scoring: the directional pair (kbli_2020, kbli_2025), as
multisets per page (duplicate printed rows count). sebagian flags are
reported as a secondary exactness diagnostic, never part of the frozen
pass criterion (frozen here, pre-scoring).

Writes ONLY under data/kbli-filiera/bps-crosswalk/phase0-gate/ (data-plane
guard #2550 — sanctioned writer perimeter). Renders live OUTSIDE the repo
(vault side), pinned by sha256 in the render manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = REPO_ROOT / "data/kbli-filiera/bps-crosswalk"
GATE_DIR = RUN_DIR / "phase0-gate"
DEFAULT_PDF = Path("~/nuzantara-vault/bps/tabel-konversi-kbli-2020-2025-volume2-2026.pdf").expanduser()
DEFAULT_RENDER_DIR = Path("~/nuzantara-vault/bps/phase0-renders").expanduser()
CANONICAL_PATH = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"

PASS_THRESHOLD = 0.995

# ISO 2859-1 General Inspection Level II: lot-size range -> sample-size code letter.
GIL2_LETTERS = [
    (2, 8, "A"), (9, 15, "B"), (16, 25, "C"), (26, 50, "D"), (51, 90, "E"),
    (91, 150, "F"), (151, 280, "G"), (281, 500, "H"), (501, 1200, "J"),
    (1201, 3200, "K"), (3201, 10000, "L"), (10001, 35000, "M"),
]
LETTER_N = {"A": 2, "B": 3, "C": 5, "D": 8, "E": 13, "F": 20, "G": 32, "H": 50,
            "J": 80, "K": 125, "L": 200, "M": 315, "N": 500, "P": 800, "Q": 1250}
LETTER_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q"]
STANDARD_AQL = [0.010, 0.015, 0.025, 0.040, 0.065, 0.10, 0.15, 0.25, 0.40, 0.65, 1.0, 1.5, 2.5, 4.0, 6.5, 10.0]
# The Ac=0 diagonal of Table 2-A (single sampling, normal): for each AQL class,
# the smallest sample size whose plan is Ac=0/Re=1 (n * AQL% ~= 0.125).
AC0_DIAGONAL_N = {0.010: 1250, 0.015: 800, 0.025: 500, 0.040: 315, 0.065: 200,
                  0.10: 125, 0.15: 80, 0.25: 50, 0.40: 32, 0.65: 20, 1.0: 13,
                  1.5: 8, 2.5: 5, 4.0: 3, 6.5: 2, 10.0: 2}
# Descending a Table 2-A column below the Ac=0 diagonal, acceptance numbers
# follow the standard ladder (one step per sample-size letter).
AC_LADDER = [0, 1, 2, 3, 5, 7, 10, 14, 21]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canon_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")


def load_run():
    manifest = json.loads((RUN_DIR / "parser-run-manifest.json").read_text(encoding="utf-8"))
    census = json.loads((RUN_DIR / "page-census.json").read_text(encoding="utf-8"))
    edges = {
        5: json.loads((RUN_DIR / "edges-lampiran5.json").read_text(encoding="utf-8")),
        10: json.loads((RUN_DIR / "edges-lampiran10.json").read_text(encoding="utf-8")),
    }
    return manifest, census, edges


# ---------------------------------------------------------------------------
# --draw
# ---------------------------------------------------------------------------

def cmd_draw() -> int:
    manifest, census, _ = load_run()
    digest = manifest["parser_run_digest"]
    table = {"parser_run_digest": digest, "rank_formula":
             'SHA256(parser_run_digest + ":" + lampiran_id + ":" + zero_padded_printed_page(4))',
             "greedy_interpretation":
             "each phase re-scans rank-ascending over not-yet-selected pages (lowest-ranked satisfying the stratum); overlap rule: a taken page counts toward every stratum it satisfies",
             "split_rule": "final rank order of the 10 selected, odd position -> tuning, even -> holdout",
             "lampiran": {}}
    for lampiran in (5, 10):
        pages = [p for p in census if p["lampiran"] == lampiran and p["n_rows"] >= 1]
        pages.sort(key=lambda p: p["pdf_page"])
        ranked = []
        for p in pages:
            key = f"{digest}:{lampiran}:{p['printed_page']:04d}"
            ranked.append({
                "pdf_page": p["pdf_page"],
                "printed_page": p["printed_page"],
                "rank_hex": hashlib.sha256(key.encode("utf-8")).hexdigest(),
                "wrapped": bool(p["has_wrapped_row"]),
                "nm": bool(p.get("has_nm_relation", False)),
            })
        ranked.sort(key=lambda r: r["rank_hex"])
        for i, r in enumerate(ranked):
            r["rank_position_all"] = i + 1

        selected: list[dict] = []
        selected_pages = set()

        def take(pred, need_fn, phase):
            for r in ranked:
                if need_fn():
                    break
                if r["pdf_page"] in selected_pages or not pred(r):
                    continue
                r["phase"] = phase
                selected.append(r)
                selected_pages.add(r["pdf_page"])

        # NB: need_fn counts ALL selected pages satisfying the stratum (overlap rule).
        take(lambda r: r["wrapped"], lambda: sum(1 for s in selected if s["wrapped"]) >= 3, "wrapped>=3")
        take(lambda r: r["nm"], lambda: sum(1 for s in selected if s["nm"]) >= 3, "nm>=3")
        take(lambda r: True, lambda: len(selected) >= 10, "fill-to-10")

        if len(selected) < 10:
            print(f"FATAL: lampiran {lampiran} eligible pages insufficient for a 10-page draw", file=sys.stderr)
            return 2
        selected.sort(key=lambda r: r["rank_hex"])
        for i, r in enumerate(selected):
            r["final_rank_position"] = i + 1
            r["split"] = "tuning" if (i + 1) % 2 == 1 else "holdout"
        table["lampiran"][str(lampiran)] = {
            "eligible_pages": len(pages),
            "stratum_counts_in_sample": {
                "wrapped": sum(1 for s in selected if s["wrapped"]),
                "nm": sum(1 for s in selected if s["nm"]),
            },
            "selected": selected,
            "full_rank_table": ranked,
        }
    write_json(GATE_DIR / "page-rank-table.json", table)
    summary = {l: [(s["pdf_page"], s["split"]) for s in table["lampiran"][l]["selected"]] for l in ("5", "10")}
    print(json.dumps({"page_rank_table": str(GATE_DIR / "page-rank-table.json"), "selected": summary}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# --render
# ---------------------------------------------------------------------------

def cmd_render(pdf: Path, render_dir: Path) -> int:
    table = json.loads((GATE_DIR / "page-rank-table.json").read_text(encoding="utf-8"))
    render_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for lampiran in ("5", "10"):
        for s in table["lampiran"][lampiran]["selected"]:
            pno = s["pdf_page"]
            prefix = render_dir / f"l{lampiran}-p{pno:04d}"
            subprocess.run(
                ["pdftoppm", "-f", str(pno), "-l", str(pno), "-r", "300", "-png", str(pdf), str(prefix)],
                check=True, timeout=120,
            )
            out = next(render_dir.glob(f"l{lampiran}-p{pno:04d}*.png"))
            entries.append({
                "lampiran": int(lampiran), "pdf_page": pno, "printed_page": s["printed_page"],
                "split": s["split"], "file": out.name, "sha256": sha256_file(out),
            })
    write_json(GATE_DIR / "render-manifest.json", {
        "render_command": "pdftoppm -f P -l P -r 300 -png <vault pdf> <prefix>",
        "render_dir": str(render_dir),
        "renders": sorted(entries, key=lambda e: (e["lampiran"], e["pdf_page"])),
    })
    print(json.dumps({"rendered": len(entries), "dir": str(render_dir)}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# --freeze-labels
# ---------------------------------------------------------------------------

def cmd_freeze_labels(labels_path: Path, seat: str, transcript_dir: Path | None) -> int:
    if (GATE_DIR / "holdout-scores.json").exists():
        print("REFUSED: holdout already scored — labels can no longer be (re)frozen.", file=sys.stderr)
        return 2
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    table = json.loads((GATE_DIR / "page-rank-table.json").read_text(encoding="utf-8"))
    expected = {(int(l), s["pdf_page"]) for l in ("5", "10") for s in table["lampiran"][l]["selected"]}
    got = {(e["lampiran"], e["pdf_page"]) for e in labels}
    if expected != got:
        print(f"REFUSED: label pages != drawn pages. missing={sorted(expected-got)} extra={sorted(got-expected)}", file=sys.stderr)
        return 2
    for e in labels:
        for r in e["rows"]:
            for k in ("left_code", "right_code"):
                if not (isinstance(r.get(k), str) and len(r[k]) == 5 and r[k].isdigit()):
                    print(f"REFUSED: malformed row in l{e['lampiran']} p{e['pdf_page']}: {r}", file=sys.stderr)
                    return 2
    transcripts = []
    if transcript_dir and transcript_dir.exists():
        for f in sorted(transcript_dir.glob("*")):
            if f.is_file():
                transcripts.append({"file": f.name, "sha256": sha256_file(f)})
    freeze = {
        "seat": seat,
        "labels_sha256": hashlib.sha256(canon_json(labels).encode("utf-8")).hexdigest(),
        "labels": labels,
        "blindness": "seat received ONLY the 300-dpi page renders + format instructions; it never saw parser output, canonical data, or this repo",
        "transcripts": transcripts,
        "scoring_metric_frozen": {
            "edge_identity": "(kbli_2020, kbli_2025) directional pair, multiset per page",
            "pass": f"precision >= {PASS_THRESHOLD} AND recall >= {PASS_THRESHOLD} on the HOLDOUT half only",
            "sebagian": "reported as secondary exactness diagnostic, not part of the pass criterion",
        },
    }
    write_json(GATE_DIR / "truth-labels-frozen.json", freeze)
    print(json.dumps({"frozen": True, "seat": seat, "labels_sha256": freeze["labels_sha256"],
                      "pages": len(labels)}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def truth_pairs(entry: dict) -> Counter:
    """Map a labeled page to (kbli_2020, kbli_2025) multiset. Labels are
    visual left/right; L5 left=2020, L10 left=2025."""
    c = Counter()
    for r in entry["rows"]:
        if entry["lampiran"] == 5:
            c[(r["left_code"], r["right_code"])] += 1
        else:
            c[(r["right_code"], r["left_code"])] += 1
    return c


def parser_pairs(edges: dict, lampiran: int, pdf_page: int) -> Counter:
    c = Counter()
    for e in edges[lampiran]:
        if e["pdf_page"] == pdf_page:
            c[(e["kbli_2020"], e["kbli_2025"])] += 1
    return c


def score_half(split: str):
    _, _, edges = load_run()
    freeze = json.loads((GATE_DIR / "truth-labels-frozen.json").read_text(encoding="utf-8"))
    table = json.loads((GATE_DIR / "page-rank-table.json").read_text(encoding="utf-8"))
    sel = {(int(l), s["pdf_page"]): s for l in ("5", "10") for s in table["lampiran"][l]["selected"]}
    tp = fp = fn = 0
    per_page = []
    seb_match = seb_total = 0
    for entry in freeze["labels"]:
        key = (entry["lampiran"], entry["pdf_page"])
        if sel[key]["split"] != split:
            continue
        t = truth_pairs(entry)
        p = parser_pairs(edges, entry["lampiran"], entry["pdf_page"])
        inter = sum((t & p).values())
        tp += inter
        fpp = sum((p - t).values())
        fnp = sum((t - p).values())
        fp += fpp
        fn += fnp
        # sebagian secondary diagnostic (pair-level, only where the pair matched)
        for r in entry["rows"]:
            pair = (r["left_code"], r["right_code"]) if entry["lampiran"] == 5 else (r["right_code"], r["left_code"])
            match = next((e for e in edges[entry["lampiran"]]
                          if e["pdf_page"] == entry["pdf_page"] and (e["kbli_2020"], e["kbli_2025"]) == pair), None)
            if match is not None:
                seb_total += 1
                lab_l = bool(r.get("sebagian_left", False))
                lab_r = bool(r.get("sebagian_right", False))
                if entry["lampiran"] == 5:
                    ok = (match["sebagian_2020"] == lab_l and match["sebagian_2025"] == lab_r)
                else:
                    ok = (match["sebagian_2025"] == lab_l and match["sebagian_2020"] == lab_r)
                seb_match += ok
        per_page.append({
            "lampiran": entry["lampiran"], "pdf_page": entry["pdf_page"],
            "truth_rows": sum(t.values()), "parser_rows": sum(p.values()),
            "tp": inter, "fp": fpp, "fn": fnp,
            "fp_pairs": sorted([f"{a}->{b}" for (a, b), n in (p - t).items() for _ in range(n)]),
            "fn_pairs": sorted([f"{a}->{b}" for (a, b), n in (t - p).items() for _ in range(n)]),
        })
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "split": split,
        "pages": sorted(per_page, key=lambda r: (r["lampiran"], r["pdf_page"])),
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 6), "recall": round(recall, 6),
        "sebagian_secondary": {"matched_pairs_checked": seb_total, "flag_exact": seb_match},
        "labels_sha256": freeze["labels_sha256"],
    }


def cmd_score_tuning() -> int:
    res = score_half("tuning")
    res["metric"] = "m_P (tuning-half diagnostic, §1.4 item 3 — no pass/fail of its own)"
    write_json(GATE_DIR / "mp-tuning-scores.json", res)
    print(json.dumps({k: res[k] for k in ("precision", "recall", "tp", "fp", "fn")}, indent=2))
    return 0


def cmd_score_holdout() -> int:
    latch = GATE_DIR / "holdout-scores.json"
    if latch.exists():
        print("REFUSED: holdout already scored EXACTLY ONCE — re-scoring is forbidden (§1.4 item 2).", file=sys.stderr)
        return 2
    if not (GATE_DIR / "truth-labels-frozen.json").exists():
        print("REFUSED: no frozen truth labels.", file=sys.stderr)
        return 2
    res = score_half("holdout")
    res["pass_threshold"] = PASS_THRESHOLD
    res["verdict"] = "PASS" if (res["precision"] >= PASS_THRESHOLD and res["recall"] >= PASS_THRESHOLD) else "FAIL"
    res["holdout_edge_error_rate"] = round(max(1 - res["precision"], 1 - res["recall"]), 6)
    write_json(latch, res)
    print(json.dumps({k: res[k] for k in ("verdict", "precision", "recall", "tp", "fp", "fn", "holdout_edge_error_rate")}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# --aql (item 10) + tiering census
# ---------------------------------------------------------------------------

def cmd_aql() -> int:
    hold = json.loads((GATE_DIR / "holdout-scores.json").read_text(encoding="utf-8"))
    if hold["verdict"] != "PASS":
        print("REFUSED: AQL parameters are only emitted on a PASSED gate (§1.4 item 10).", file=sys.stderr)
        return 2
    manifest, _, edges = load_run()
    canonical = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
    records = canonical["data"]
    pop = [r for r in records if r.get("_l2_source") == "OSS_RBA_resiko_2025"]
    pop_codes = {r["kode_kbli_2025"] for r in pop}
    by_code = {r["kode_kbli_2025"]: r for r in records if r.get("kode_kbli_2025")}

    tier1 = sorted(r["kode_kbli_2025"] for r in pop
                   if r.get("status_mapping") == "MATCH_CON_AGGREGAZIONE" and len(r.get("pp28_sources") or []) == 1)
    tier2 = sorted(r["kode_kbli_2025"] for r in pop
                   if r.get("status_mapping") == "MATCH_LANGSUNG"
                   and (r.get("pp28_sources") or [None])[0] not in (None, r["kode_kbli_2025"]))
    tier5 = sorted(r["kode_kbli_2025"] for r in pop
                   if r.get("status_mapping") == "BPS_ONLY" or r.get("status_mapping") is None)
    if len(tier1) != 46 or len(tier2) != 16:
        print(f"FATAL: frozen seed lists drifted — tier1={len(tier1)} (spec 46), tier2={len(tier2)} (spec 16)", file=sys.stderr)
        return 2

    # Tier 2.5: codes touched by unresolved rows or unresolved L5<->L10 diffs.
    consistency = json.loads((RUN_DIR / "consistency-l5-l10.json").read_text(encoding="utf-8"))
    unresolved_conflict_codes = set()
    adjud_path = RUN_DIR / "consistency-adjudications.json"
    adjudicated = {}
    if adjud_path.exists():
        adjudicated = {tuple(k.split("->")): v for k, v in
                       json.loads(adjud_path.read_text(encoding="utf-8"))["adjudications"].items()}
    for side in ("in_l5_only", "in_l10_only"):
        for d in consistency[side]:
            if (d["kbli_2020"], d["kbli_2025"]) not in adjudicated:
                if d["kbli_2025"] in pop_codes:
                    unresolved_conflict_codes.add(d["kbli_2025"])
    tier25 = sorted(unresolved_conflict_codes - set(tier1) - set(tier2))

    # Tier 3 candidates: population codes whose PARSED reverse ancestry
    # disputes the canonical crosswalk-metadata shape (mechanical census only
    # — adjudication is the lots' job, not this gate's).
    parsed_anc = {}
    for e in edges[10]:
        parsed_anc.setdefault(e["kbli_2025"], set()).add(e["kbli_2020"])
    tier3 = []
    for code in sorted(pop_codes - set(tier1) - set(tier2) - set(tier25) - set(tier5)):
        rec = by_code[code]
        anc = parsed_anc.get(code)
        if anc is None:
            continue  # no BPS row parsed for this code -> §1.1b reconciliation, not Tier 3
        sm = rec.get("status_mapping")
        pp = rec.get("pp28_sources") or []
        mismatch = None
        if sm == "MATCH_LANGSUNG":
            if anc != {code}:
                mismatch = "declared 1:1 same-code but parsed ancestors differ"
        elif sm == "CODICE_RINUMERATO":
            if len(anc) != 1 or anc == {code}:
                mismatch = "declared renumbered 1:1 but parsed ancestry disagrees"
            elif pp and set(pp) != anc:
                mismatch = "renumbered pointer disputes parsed ancestor"
        elif sm == "MATCH_CON_AGGREGAZIONE":
            if pp and not set(pp) <= (anc | {code}):
                mismatch = "declared ancestors not a subset of parsed ancestors"
        if mismatch:
            tier3.append({"code": code, "mismatch": mismatch,
                          "parsed_ancestors": sorted(anc), "pp28_sources": pp, "status_mapping": sm})
    tier3_codes = [t["code"] for t in tier3]

    tier4 = sorted(pop_codes - set(tier1) - set(tier2) - set(tier25) - set(tier3_codes) - set(tier5))
    lot_size = len(tier4)

    err = hold["holdout_edge_error_rate"] * 100.0  # percent
    aql_class = next(a for a in STANDARD_AQL if a >= err)
    letter = next(l for lo, hi, l in GIL2_LETTERS if lo <= lot_size <= hi)
    n_letter = LETTER_N[letter]
    # Table 2-A navigation: if the (letter, AQL) cell sits above the Ac=0
    # diagonal (n_letter < diagonal n), the standard's arrow points DOWN to
    # the first available plan = the diagonal plan (Ac=0, Re=1) at n_diag.
    n_diag = AC0_DIAGONAL_N[aql_class]
    if n_letter <= n_diag:
        n, ac = n_diag, 0
    else:
        steps = LETTER_ORDER.index(letter) - LETTER_ORDER.index(
            next(l for l in LETTER_ORDER if LETTER_N.get(l) == n_diag))
        ac = AC_LADDER[min(steps, len(AC_LADDER) - 1)]
        n = n_letter
    hundred_pct = n >= lot_size
    out = {
        "rule": "ISO 2859-1 single sampling, General Inspection Level II, normal inspection to start (spec §1.4 item 10, REV-4 frozen derivation)",
        "holdout_edge_error_rate": hold["holdout_edge_error_rate"],
        "holdout_edge_error_rate_pct": round(err, 4),
        "aql_class_pct": aql_class,
        "tier_census": {
            "population": len(pop_codes),
            "tier1": {"count": len(tier1), "codes": tier1},
            "tier2": {"count": len(tier2), "codes": tier2},
            "tier2_5": {"count": len(tier25), "codes": tier25},
            "tier3_candidates": {"count": len(tier3_codes), "detail": tier3},
            "tier4": {"count": lot_size},
            "tier5": {"count": len(tier5), "codes": tier5},
        },
        "lot_size": lot_size,
        "sample_size_code_letter": letter,
        "sample_size_n": n,
        "acceptance_number_Ac": ac,
        "rejection_number_Re": ac + 1,
        "note_100pct": ("sample size >= lot size -> 100% inspection per the standard" if hundred_pct else None),
        "switching_rule": "tightened after 2 of 5 consecutive lots rejected; back to normal after 5 consecutive lots accepted under tightened",
        "ratification": "Zero (Legge 5) accept-or-override of this frozen default — PENDING (operator[business])",
        "table_2a_navigation_note": "cells above the Ac=0 diagonal follow the standard's down-arrow to the diagonal plan; below-diagonal Ac follows the standard ladder one step per letter — verify the single derived (n, Ac) cell against a paper Table 2-A at ratification",
    }
    write_json(GATE_DIR / "aql-parameters.json", out)
    print(json.dumps({k: out[k] for k in ("aql_class_pct", "lot_size", "sample_size_n",
                                          "acceptance_number_Ac", "note_100pct")}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    ap.add_argument("--render-dir", type=Path, default=DEFAULT_RENDER_DIR)
    ap.add_argument("--labels", type=Path)
    ap.add_argument("--seat", type=str, default="")
    ap.add_argument("--transcripts", type=Path)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--draw", action="store_true")
    g.add_argument("--render", action="store_true")
    g.add_argument("--freeze-labels", action="store_true")
    g.add_argument("--score-tuning", action="store_true")
    g.add_argument("--score-holdout", action="store_true")
    g.add_argument("--aql", action="store_true")
    args = ap.parse_args()
    if args.draw:
        return cmd_draw()
    if args.render:
        return cmd_render(args.pdf, args.render_dir)
    if args.freeze_labels:
        if not args.labels or not args.seat:
            print("--freeze-labels requires --labels and --seat", file=sys.stderr)
            return 2
        return cmd_freeze_labels(args.labels, args.seat, args.transcripts)
    if args.score_tuning:
        return cmd_score_tuning()
    if args.score_holdout:
        return cmd_score_holdout()
    if args.aql:
        return cmd_aql()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
