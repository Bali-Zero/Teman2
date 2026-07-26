"""Phase-0 acceptance-gate — the conductor's INDEPENDENT eye-read truth (§1.4).

This module is the tracked, auditable home of the blind-holdout ground truth: the
edge set a human conductor transcribed BY EYE from the 10 rendered holdout pages at
200 DPI, never derived from any parser output (W100 — a provenance pointer is not a
content check; the whole point of the gate is that this reading is independent of
the thing it judges). It is a *compiler* under `scripts/kbli_filiera/` so the write
of `data/kbli-filiera/phase0/holdout_truth.json` is done by an authorized data-plane
writer (#2550), and so the transcription itself lives in version control as code — a
reviewer diffs `TRUTH` below against the rendered page images.

Frozen to the title-independent parse digest `ca9e7ffc…` (the relation carries only
codes + sebagian + source_locator, no titles, so watermark noise in the title cells
can never perturb the draw or the digest). Holdout pages, drawn deterministically by
`bps_phase0_gate.draw`: L5 (forward) 227/159/179/207/156 · L10 (reverse) 369/423/427/379/372.

Edges are canonical `(code2020, code2025)` regardless of page direction — the same
orientation `bps_phase0_gate.parser_edges_for_page` normalizes to, so truth and parser
edges are compared in one frame. Codes stay STRINGS: leading zeros are load-bearing
(01614, 03131, 03141, 03231, 03241, 03261, 03263).

Run `python scripts/kbli_filiera/holdout_truth_compile.py --write` to (re)emit the JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kbli_filiera import vault_common as common  # noqa: E402

logger = common.setup_logger("holdout_truth_compile")

PARSER_RUN_DIGEST = "ca9e7ffcadcaf526e1bd69afecb40f23d31ac20db8ab4aafa21a0271206100b2"  # pragma: allowlist secret  # sha256 of the parse relation, not a credential

DEFAULT_OUT = Path("data/kbli-filiera/phase0/holdout_truth.json")

# Conductor eye-read, transcribed from the rendered holdout PNGs (never a re-parse).
# L5 pages are forward tables: edge = (col1_2020, col3_2025).
# L10 pages are reverse tables: edge = (col3_2020, col1_2025).
TRUTH: dict[str, list[tuple[str, str]]] = {
    # ---- Lampiran 5 (forward) ----
    "227": [("77100", "77510"), ("77210", "77210"), ("77210", "77520"), ("77220", "77293"),
            ("77291", "77291"), ("77291", "77520"), ("77292", "77299"), ("77292", "77520"),
            ("77293", "77293"), ("77293", "77520"), ("77294", "77294"), ("77294", "77520"),
            ("77295", "77292"), ("77295", "77520"), ("77299", "77299")],
    "159": [("23941", "23941"), ("23942", "23942"), ("23943", "23943"), ("23951", "23951"),
            ("23952", "23952"), ("23953", "23951"), ("23953", "23952"), ("23954", "23953"),
            ("23955", "23954"), ("23956", "23954"), ("23957", "23955"), ("23959", "23951"),
            ("23959", "23952"), ("23959", "23953"), ("23959", "23954"), ("23959", "23955"),
            ("23961", "23961"), ("23961", "23962"), ("23962", "23961"), ("23962", "23962"),
            ("23963", "23969"), ("23969", "23961"), ("23969", "23962"), ("23969", "23969")],
    "179": [("46491", "46491"), ("46492", "46492"), ("46493", "46493"), ("46494", "46494"),
            ("46495", "46495"), ("46499", "46496"), ("46499", "46499"), ("46511", "46511"),
            ("46512", "46512"), ("46521", "46521"), ("46522", "46522"), ("46523", "46523"),
            ("46530", "46530"), ("46591", "46591"), ("46592", "46592"), ("46593", "46593"),
            ("46594", "46594"), ("46599", "46599"), ("46610", "46710")],
    "207": [("51106", "93199"), ("51107", "51102"), ("51108", "01614"), ("51108", "71109"),
            ("51108", "71204"), ("51108", "74201"), ("51108", "74991"), ("51108", "84231"),
            ("51108", "84234"), ("51108", "85321"), ("51108", "85322"), ("51108", "85401"),
            ("51108", "85402"), ("51108", "85530"), ("51108", "85578"), ("51108", "86994"),
            ("51108", "94910"), ("51109", "51101"), ("51109", "51103"), ("51201", "51201"),
            ("51202", "51202"), ("51203", "51201"), ("51204", "51202"), ("51204", "51203"),
            ("52101", "52109")],
    "156": [("20124", "20122"), ("20125", "20122"), ("20126", "20123"), ("20127", "20124"),
            ("20128", "20124"), ("20129", "20125"), ("20131", "20131"), ("20132", "20132"),
            ("20211", "20211"), ("20212", "20212"), ("20213", "20213"), ("20214", "20124"),
            ("20221", "20221"), ("20221", "20229"), ("20222", "20222"), ("20223", "20223"),
            ("20231", "20231"), ("20232", "20232"), ("20232", "20235"), ("20233", "20233"),
            ("20234", "20234"), ("20291", "20291"), ("20292", "20292"), ("20293", "20293"),
            ("20294", "20294"), ("20295", "20295"), ("20296", "20296"), ("20299", "20297"),
            ("20299", "20298"), ("20299", "20299")],
    # ---- Lampiran 10 (reverse) ----
    "369": [("43291", "43400"), ("43292", "43400"), ("43293", "43400"), ("43294", "43400"),
            ("43299", "43400"), ("43301", "43400"), ("43302", "43400"), ("43303", "43400"),
            ("43304", "43400"), ("43305", "43400"), ("43309", "43400"), ("43901", "43400"),
            ("43902", "43400"), ("43903", "43400"), ("43904", "43400"), ("43905", "43400"),
            ("43909", "43400"), ("63122", "43400"), ("43901", "43901"), ("43902", "43902"),
            ("43903", "43903"), ("43904", "43904"), ("43905", "43905"), ("03231", "43909"),
            ("03241", "43909"), ("03261", "43909"), ("43216", "43909"), ("43909", "43909")],
    "423": [("77319", "77311"), ("03131", "77312"), ("03141", "77312"), ("77312", "77312"),
            ("52296", "77313"), ("77313", "77313"), ("77391", "77391"), ("77392", "77392"),
            ("77393", "77393"), ("77394", "77394"), ("77395", "77395"), ("77321", "77396"),
            ("77322", "77396"), ("77329", "77396"), ("77399", "77397")],
    "427": [("03263", "82921"), ("82920", "82921"), ("82920", "82922"), ("82920", "82923"),
            ("82920", "82924"), ("82920", "82925"), ("82920", "82929"), ("82990", "82990"),
            ("84111", "84111"), ("84112", "84112"), ("84113", "84113"), ("84114", "84114"),
            ("84115", "84115"), ("84119", "84119"), ("84121", "84121"), ("84122", "84122"),
            ("84123", "84123"), ("84124", "84124"), ("84125", "84125"), ("84126", "84126"),
            ("84129", "84129")],
    "379": [("47825", "47246"), ("47911", "47246"), ("47992", "47246"), ("47249", "47249"),
            ("47829", "47249"), ("47911", "47249"), ("47992", "47249"), ("47301", "47301"),
            ("47996", "47301"), ("47302", "47302"), ("47892", "47302"), ("47919", "47302"),
            ("47996", "47302"), ("47303", "47303")],
    "372": [("46447", "46442"), ("46448", "46442"), ("46421", "46451"), ("46422", "46452"),
            ("46491", "46491"), ("46492", "46492"), ("46493", "46493"), ("46494", "46494"),
            ("46495", "46495"), ("46499", "46496"), ("46499", "46499"), ("46511", "46511"),
            ("46512", "46512"), ("46521", "46521"), ("46522", "46522"), ("46523", "46523"),
            ("46530", "46530"), ("46591", "46591"), ("46592", "46592"), ("46593", "46593")],
}

# Per-page edge counts as read against the rendered images (a self-check that the
# transcription below was not silently truncated — every count is a claim, not a cap).
EXPECTED_COUNTS = {"227": 15, "159": 24, "179": 19, "207": 25, "156": 30,
                   "369": 28, "423": 15, "427": 21, "379": 14, "372": 20}


def validate() -> None:
    """Fail-loud on any transcription defect before the truth can be written."""
    for page, edges in TRUTH.items():
        assert len(edges) == EXPECTED_COUNTS[page], (
            f"page {page}: {len(edges)} edges != expected {EXPECTED_COUNTS[page]} "
            f"(silent truncation guard, W97)")
        for a, b in edges:
            assert len(a) == 5 and a.isdigit(), f"page {page}: bad 2020 code {a!r}"
            assert len(b) == 5 and b.isdigit(), f"page {page}: bad 2025 code {b!r}"


def build() -> dict:
    validate()
    return {
        "method": ("conductor eye-read of rendered holdout pages at 200 DPI, "
                   "independent of the parse (never a re-parse; W100)"),
        "note": ("edges are (code2020, code2025); 5 forward (L5) + 5 reverse (L10) "
                 "holdout pages; title-independent digest ca9e7ffc"),
        "parser_run_digest": PARSER_RUN_DIGEST,
        "truth_edges_per_page": {k: [list(e) for e in v] for k, v in TRUTH.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit the Phase-0 blind-holdout eye-read truth")
    ap.add_argument("--write", action="store_true", help="write the JSON artifact")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    payload = build()
    total = sum(len(v) for v in TRUTH.values())
    logger.info("%s pages, %s truth edges, digest %s", len(TRUTH), total, PARSER_RUN_DIGEST[:12])
    if args.write:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        logger.info("wrote %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
