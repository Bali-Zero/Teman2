#!/usr/bin/env python3
"""bps_phase0_gate.py — Phase-0 acceptance gate for the BPS crosswalk parser.

The signed Batch-B design (§1.4 item 2, REV-4/4b) makes the parser's edge-level
precision/recall on a BLIND holdout the pass/fail gate before any Batch-B lot
may dispatch, and freezes the holdout draw so two conductors running the gate
against the same parse produce the identical page sample byte-for-byte. This
module is that frozen draw plus the scoring harness. It does NOT itself decide
truth — the holdout pages are eye-adjudicated by the conductor on the raw page
renders (an INDEPENDENT channel, never a re-parse: a re-parse would measure
transcription fidelity, not correctness — scar W100). This module renders the
pages, reconstructs the parser's own edges per page, and — once the conductor
supplies the eye-read truth — computes edge-level precision/recall.

FROZEN DRAW (§1.4 item 2):
  1. Eligible pages = the lampiran's data pages (from the parse artifact's
     page_strata), ascending.
  2. Rank each by SHA256(parser_run_digest ":" lampiran_id ":"
     zero_padded_printed_page(4)), hex ascending.
  3. Greedy stratified fill: walk rank-ascending, take lowest-ranked pages to
     ≥3 wrapped-row, then ≥3 N:M, then remaining to 10 total. A page counts
     toward every stratum it satisfies; never taken twice.
  4. Tuning/holdout split: drawn pages sorted by rank, odd rank-position (1st,
     3rd, …) → tuning, even → holdout. Holdout scored blind, exactly once.

The AQL derivation (item 10) reads holdout_edge_error_rate = max(1-precision,
1-recall) from this gate's holdout result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from kbli_filiera import bps_crosswalk_parser as parser
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover - path shim
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import bps_crosswalk_parser as parser
    from kbli_filiera import vault_common as common

logger = common.setup_logger("bps_phase0_gate")

MIN_WRAPPED = 3
MIN_NM = 3
DRAW_SIZE = 10
PASS_PRECISION = 0.995
PASS_RECALL = 0.995


# ---------------------------------------------------------------------------
# Frozen holdout draw (pure — unit-tested without a PDF)
# ---------------------------------------------------------------------------

def page_rank_key(parser_run_digest: str, lampiran_id: str, printed_page: int) -> str:
    """SHA256(digest ":" lampiran ":" zero_padded_printed_page(4)) hex. The
    printed page (not the PDF page) zero-padded to 4 digits, per REV-4b."""
    material = f"{parser_run_digest}:{lampiran_id}:{printed_page:04d}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def rank_pages(pages: list[dict], parser_run_digest: str, lampiran_id: str,
               offset: int = parser.PRINTED_PAGE_OFFSET) -> list[dict]:
    """Attach a rank key to each page stratum and return them rank-ascending.
    `pages` are the artifact's per-page strata dicts (pdf_page/wrapped/nm)."""
    ranked = []
    for pg in pages:
        printed = pg["pdf_page"] + offset
        ranked.append({**pg, "printed_page": printed,
                       "rank": page_rank_key(parser_run_digest, lampiran_id, printed)})
    return sorted(ranked, key=lambda p: p["rank"])


def greedy_stratified_draw(ranked: list[dict], size: int = DRAW_SIZE,
                           min_wrapped: int = MIN_WRAPPED, min_nm: int = MIN_NM) -> list[dict]:
    """The frozen greedy fill. Walk rank-ascending taking pages to satisfy the
    wrapped stratum (≥min_wrapped), then the N:M stratum (≥min_nm), then fill
    to `size` with the lowest-ranked remaining. Overlap rule: a taken page
    counts toward every stratum it satisfies; never taken twice."""
    chosen: list[dict] = []
    chosen_pdf: set[int] = set()

    def take_for(predicate, need: int) -> None:
        have = sum(1 for c in chosen if predicate(c))
        for pg in ranked:
            if have >= need:
                break
            if pg["pdf_page"] in chosen_pdf or not predicate(pg):
                continue
            chosen.append(pg)
            chosen_pdf.add(pg["pdf_page"])
            have += 1

    take_for(lambda p: p["wrapped"], min_wrapped)
    take_for(lambda p: p["nm"], min_nm)
    # fill remaining to `size` with the lowest-ranked not-yet-chosen
    for pg in ranked:
        if len(chosen) >= size:
            break
        if pg["pdf_page"] not in chosen_pdf:
            chosen.append(pg)
            chosen_pdf.add(pg["pdf_page"])
    # return in rank order (chosen was built stratum-first; the split needs
    # the pages ordered by rank, not by selection order)
    return sorted(chosen, key=lambda p: p["rank"])


def tuning_holdout_split(drawn_rank_ordered: list[dict]) -> tuple[list[dict], list[dict]]:
    """Odd rank-position (1st, 3rd, …) → tuning; even → holdout. Input MUST be
    rank-ordered (greedy_stratified_draw returns it so)."""
    tuning = [pg for i, pg in enumerate(drawn_rank_ordered) if i % 2 == 0]  # 1st,3rd -> 0,2
    holdout = [pg for i, pg in enumerate(drawn_rank_ordered) if i % 2 == 1]
    return tuning, holdout


def draw_for_lampiran(page_strata: list[dict], parser_run_digest: str,
                      lampiran_id: str) -> dict:
    ranked = rank_pages(page_strata, parser_run_digest, lampiran_id)
    drawn = greedy_stratified_draw(ranked)
    tuning, holdout = tuning_holdout_split(drawn)
    return {
        "lampiran": lampiran_id,
        "eligible_count": len(page_strata),
        "drawn_pdf_pages": [p["pdf_page"] for p in drawn],
        "tuning_pdf_pages": [p["pdf_page"] for p in tuning],
        "holdout_pdf_pages": [p["pdf_page"] for p in holdout],
        "drawn": drawn,
        "tuning": tuning,
        "holdout": holdout,
    }


# ---------------------------------------------------------------------------
# Edge-level scoring (pure)
# ---------------------------------------------------------------------------

def score_page(parser_edges: set[tuple[str, str]],
               truth_edges: set[tuple[str, str]]) -> dict:
    """Edge-level TP/FP/FN + precision/recall for one page. Edges are
    direction-normalized tuples so a forward and reverse page compare the same
    way (see edges_from_* below)."""
    tp = parser_edges & truth_edges
    fp = parser_edges - truth_edges
    fn = truth_edges - parser_edges
    return {
        "tp": len(tp), "fp": len(fp), "fn": len(fn),
        "false_positive_edges": sorted(list(e) for e in fp),
        "false_negative_edges": sorted(list(e) for e in fn),
    }


# ISO 2859-1 preferred AQL series (%), ascending — the standard grid points
# (not the copyrighted sampling tables; just the AQL ladder every reference
# lists). The (n, Ac) lookup from a lot size + AQL class needs the ISO tables
# and is deferred to Tier-4 time, per §1.4 item 10.
ISO_2859_1_AQL_SERIES = [
    0.010, 0.015, 0.025, 0.040, 0.065, 0.10, 0.15, 0.25, 0.40, 0.65,
    1.0, 1.5, 2.5, 4.0, 6.5, 10.0, 15.0, 25.0, 40.0, 65.0,
    100.0, 150.0, 250.0, 400.0, 650.0, 1000.0,
]


def derive_tier4_aql(holdout_edge_error_rate: float) -> dict:
    """§1.4 item-10 FROZEN rule → the ratifiable Tier-4 AQL default.

    AQL class = the smallest standard ISO 2859-1 AQL value that is ≥ the
    measured holdout edge error rate (expressed as a percent). The regime is
    fixed (single sampling, General Inspection Level II, normal start, the
    frozen switching rule). The concrete (n, Ac) is NOT derivable here — it
    needs the Tier-4 stratum lot size (fixed at tiering) and the ISO sampling
    tables — so it is deferred; this returns exactly what Zero accepts or
    overrides (Legge 5) before any Tier-4 certification runs."""
    pct = holdout_edge_error_rate * 100.0
    aql = next((a for a in ISO_2859_1_AQL_SERIES if a >= pct), ISO_2859_1_AQL_SERIES[-1])
    return {
        "measured_holdout_edge_error_rate": holdout_edge_error_rate,
        "measured_as_percent": pct,
        "aql_class_percent": aql,
        "sampling": "ISO 2859-1 single sampling",
        "inspection_level": "General Inspection Level II",
        "inspection_start": "normal",
        "lot_size": "Tier-4 stratum code count (fixed at tiering; (n, Ac) looked up then)",
        "switching_rule": ("tighten after 2 of 5 consecutive lots rejected; "
                           "return to normal after 5 consecutive accepted under tightened"),
        "status": "CONDUCTOR-PROPOSED default — Zero accepts-or-overrides (Legge 5) "
                  "before any Tier-4 certification runs",
    }


def aggregate_scores(page_scores: list[dict]) -> dict:
    tp = sum(s["tp"] for s in page_scores)
    fp = sum(s["fp"] for s in page_scores)
    fn = sum(s["fn"] for s in page_scores)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall,
        "holdout_edge_error_rate": max(1 - precision, 1 - recall),
        "passes": precision >= PASS_PRECISION and recall >= PASS_RECALL,
    }


# ---------------------------------------------------------------------------
# PDF-facing: per-page parser edges + render (thin)
# ---------------------------------------------------------------------------

def parser_edges_for_page(pdf, pdf_page: int, direction: str) -> set[tuple[str, str]]:
    """The parser's OWN edges on one page, direction-normalized to
    (code2020, code2025). This is what the eye-read truth is scored against."""
    page = pdf.pages[pdf_page - 1]
    table = page.extract_table(parser.TABLE_SETTINGS)
    edges, _ = parser.parse_table_rows(table, direction, pdf_page)
    if direction == "fwd":  # left=2020, right=2025
        return {(e.left_code, e.right_code) for e in edges}
    return {(e.right_code, e.left_code) for e in edges}  # rev: left=2025, right=2020


def render_page(pdf, pdf_page: int, out_dir: Path, resolution: int = 200) -> Path:
    page = pdf.pages[pdf_page - 1]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"holdout_p{pdf_page:04d}.png"
    page.to_image(resolution=resolution).save(str(out))
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_artifact(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_draw(args) -> int:
    art = _load_artifact(Path(args.artifact))
    digest = art["manifest"]["output_relation_digest"]
    draws = {
        "5": draw_for_lampiran(art["page_strata"]["forward_L5"], digest, "5"),
        "10": draw_for_lampiran(art["page_strata"]["reverse_L10"], digest, "10"),
    }
    for lid, d in draws.items():
        logger.info("Lampiran %s: eligible=%s holdout(pdf)=%s tuning(pdf)=%s",
                    lid, d["eligible_count"], d["holdout_pdf_pages"], d["tuning_pdf_pages"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"parser_run_digest": digest, "draws": draws},
                              ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    logger.info("wrote draw plan: %s", out)
    return 0


def cmd_render(args) -> int:
    plan = _load_artifact(Path(args.draw_plan))
    vault_root = Path(args.vault_root).expanduser()
    pdf, _ = parser._open_pdf(vault_root)
    out_dir = Path(args.out_dir)
    try:
        for lid, d in plan["draws"].items():
            direction = "fwd" if lid == "5" else "rev"
            for pdf_page in d["holdout_pdf_pages"]:
                png = render_page(pdf, pdf_page, out_dir)
                edges = parser_edges_for_page(pdf, pdf_page, direction)
                logger.info("L%s pdf_p%s -> %s (%s parser edges)", lid, pdf_page, png.name, len(edges))
                # dump parser edges alongside for the conductor to diff against
                (out_dir / f"parser_edges_p{pdf_page:04d}.json").write_text(
                    json.dumps(sorted(list(e) for e in edges), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    finally:
        pdf.close()
    logger.info("rendered holdout pages + parser edges to %s", out_dir)
    return 0


def cmd_score(args) -> int:
    """Score the conductor eye-read truth against the parser's per-page edges
    and emit the full, auditable gate report (verdict + Tier-4 AQL default).

    The truth file is the conductor's INDEPENDENT reading of the rendered
    holdout pages (a JSON of {pdf_page: [[code2020, code2025], …]}), never a
    re-parse — that independence is the whole point of the gate (W100)."""
    art = _load_artifact(Path(args.artifact))
    digest = art["manifest"]["output_relation_digest"]
    plan = _load_artifact(Path(args.draw_plan))
    if plan.get("parser_run_digest") != digest:
        logger.error("draw plan digest %s != artifact digest %s — refusing to score a "
                     "holdout drawn under a different parse", plan.get("parser_run_digest"), digest)
        raise SystemExit(3)
    truth = _load_artifact(Path(args.truth))
    truth_edges = truth["truth_edges_per_page"]
    holdout_dir = Path(args.holdout_dir)

    holdout_pages = plan["draws"]["5"]["holdout_pdf_pages"] + plan["draws"]["10"]["holdout_pdf_pages"]
    page_scores = []
    for pg in sorted(holdout_pages):
        key = str(pg)
        if key not in truth_edges:
            logger.error("no eye-read truth for holdout page %s — every holdout page must be adjudicated", pg)
            raise SystemExit(3)
        parser_edges = {tuple(e) for e in
                        json.loads((holdout_dir / f"parser_edges_p{pg:04d}.json").read_text())}
        t = {tuple(e) for e in truth_edges[key]}
        s = score_page(parser_edges, t)
        s["page"] = pg
        s["parser_edge_count"] = len(parser_edges)
        s["truth_edge_count"] = len(t)
        page_scores.append(s)
        logger.info("p%s: parser=%s truth=%s tp=%s fp=%s fn=%s",
                    pg, len(parser_edges), len(t), s["tp"], s["fp"], s["fn"])

    agg = aggregate_scores(page_scores)
    aql = derive_tier4_aql(agg["holdout_edge_error_rate"])
    report = {
        "gate": "bps_phase0_acceptance",
        "verdict": "PASS" if agg["passes"] else "FAIL",
        "parser_run_digest": digest,
        "bps_pdf_sha256": art["manifest"]["bps_pdf"]["sha256"],
        "pass_thresholds": {"precision": PASS_PRECISION, "recall": PASS_RECALL},
        "eye_adjudication_method": truth.get("method"),
        "holdout_pdf_pages": sorted(holdout_pages),
        "scores_per_page": page_scores,
        "aggregate": agg,
        "tier4_aql_default_item10": aql,
        "sebagian_modifier_item5": art["manifest"]["sebagian_modifier"],
        "consistency_item7": art["manifest"]["consistency_L5_vs_L10"],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    logger.info("VERDICT: %s  precision=%.5f recall=%.5f  error_rate=%.5f",
                report["verdict"], agg["precision"], agg["recall"], agg["holdout_edge_error_rate"])
    logger.info("Tier-4 AQL default (item 10): class=%.3f%% (%s)",
                aql["aql_class_percent"], aql["status"])
    logger.info("wrote gate report: %s", out)
    return 0 if agg["passes"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase-0 acceptance gate (holdout draw + scoring)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("draw", help="compute the frozen holdout/tuning draw from a parse artifact")
    d.add_argument("--artifact", required=True)
    d.add_argument("--out", default="data/kbli-filiera/phase0/holdout_draw.json")
    d.set_defaults(func=cmd_draw)

    r = sub.add_parser("render", help="render holdout pages + dump parser edges for eye-adjudication")
    r.add_argument("--draw-plan", required=True)
    r.add_argument("--vault-root", default=str(common.DEFAULT_VAULT_ROOT))
    r.add_argument("--out-dir", required=True)
    r.set_defaults(func=cmd_render)

    s = sub.add_parser("score", help="score eye-read truth vs parser edges → gate report")
    s.add_argument("--artifact", required=True)
    s.add_argument("--draw-plan", required=True)
    s.add_argument("--holdout-dir", required=True)
    s.add_argument("--truth", required=True)
    s.add_argument("--out", default="data/kbli-filiera/phase0/gate_report.json")
    s.set_defaults(func=cmd_score)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
