#!/usr/bin/env python3
"""emit_lot_report.py — GARUDA-FILIERA lot-report compiler (plan §8 A-3).

Deterministic writer of a lot's closing report artifact
(`data/kbli-filiera/batch-reports/lot-<LOT_ID>.json`). Unlike
emit_batch_calibration.py (which re-derives digests/positions from the
canonical + manifest + membership artifacts), this compiler is deliberately
SIMPLE — plan §8 A-3 IS the input: the conductor's signed per-code verdict
table (codes + verdicts + categories) is a PINNED LITERAL below, never parsed
out of a run journal or re-derived. Data-plane guard (`infra/claude-hooks/
data-plane-registry.json`, entry "kbli-filiera") authorizes `scripts/
kbli_filiera/*.py` as the ONLY writer of `data/kbli-filiera/**`.

Why a pinned literal, not a journal parser: the workflow's own run log
(workflowProgress) is a harness artifact, not a git-tracked one, and a lot's
FINAL verdict for a given code can differ from what the runner emitted
in-flight (see code 38222 in Lot A-L1 — the runner said certified, the
conductor's D6 review demoted it). The lot report records the CONDUCTOR-
SIGNED outcome, not a mechanical replay of the runner's own output — exactly
the same "compiler validates, LLM/runner proposes" division of labor as
dossier_assemble.py (workflow doc §1, "no-hands rule").

FAIL-CLOSED BY CONSTRUCTION: every quarantined entry in the pinned literal
below MUST carry a non-null, in-registry `category` (or the literal sentinel
"OTHER_NEW_CATEGORY") — `_validate_verdicts` refuses to render or emit if any
entry is missing one. This is deliberate: a per-code category is a D6
conductor judgment call, and this compiler must never let an unlabeled
placeholder slip into a persisted, git-committed artifact by accident.

Determinism (G16): same LOT_A_L1_VERDICTS/LOT_A_L1_INNOCENCE inputs => byte-
identical JSON; sorted keys; trailing newline. PINNED_DATE is a constant,
never wall-clock.

Usage:
    python scripts/kbli_filiera/emit_lot_report.py            # dry-run
    python scripts/kbli_filiera/emit_lot_report.py --apply    # write the artifact
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_JSON_TEMPLATE = "data/kbli-filiera/batch-reports/lot-{lot_id}.json"
PLAN_PATH = "research/operations/2026-07-18-kbli-batch-a-plan.md"

# Pinned constant — never Date.now()/wall-clock (G16 determinism).
PINNED_DATE = "2026-07-18"

CONDUCTOR_SIGN_OFF = "SIGNED — Fable conductor session f5892d39, 2026-07-18"

LOT_ID = "A-L1"

# m3 — closed refutation/problem-category registry (plan §5), mirrored from
# infra/workflows/kbli-batch-a-lot.js's CALIBRATION.m3_refutation_categories.
REFUTATION_CATEGORIES: tuple[str, ...] = (
    "code_collision",
    "illegitimate_inheritance",
    "wrong_authority_level",
    "phantom_source_pointer",
    "source_absent_in_vault",
)
CATEGORY_SENTINEL = "OTHER_NEW_CATEGORY"

FROZEN_TAXONOMY: tuple[str, ...] = ("certified", "quarantined", "abstained")

# ---------------------------------------------------------------------------
# Lot A-L1 — conductor-signed verdict table (plan §8 amendment A-3).
#
# PINNED LITERAL, source: the conductor's D6 review + plan §8 A-3. Every
# entry with verdict="quarantined" MUST carry a category (see
# _validate_verdicts). Entries below with category=None are KNOWN-INCOMPLETE
# placeholders — the conductor's per-code category for these 9 codes was not
# yet supplied at the time this compiler was authored (2026-07-18); `--apply`
# and `--check` both refuse to run while any placeholder remains, by design
# (see module docstring "FAIL-CLOSED BY CONSTRUCTION").
# ---------------------------------------------------------------------------
LOT_A_L1_VERDICTS: list[dict[str, Any]] = [
    {
        "code": "19206",
        "verdict": "certified",
        "category": None,
        "d2_self_confirm_failed": False,
        "note": "image-verified provenance chain held under D6 review",
    },
    {
        "code": "01287",
        "verdict": "quarantined",
        "category": "illegitimate_inheritance",
        "d2_self_confirm_failed": False,
        "note": (
            "D6 image-confirmed: 3/8 per_skala rows copied from a livestock-feed code onto a "
            "narcotic-plant-cultivation code (silent PP28-crosswalk misfill)"
        ),
    },
    {
        "code": "01700",
        "verdict": "quarantined",
        "category": None,  # NEEDS-DATA: conductor per-code category pending
        "d2_self_confirm_failed": False,
        "note": "PENDING conductor per-code category (plan §8 A-3 aggregate only named 4 categories seen across the lot, not a per-code map)",
    },
    {
        "code": "02201",
        "verdict": "quarantined",
        "category": None,  # NEEDS-DATA
        "d2_self_confirm_failed": False,
        "note": "PENDING conductor per-code category",
    },
    {
        "code": "02402",
        "verdict": "quarantined",
        "category": "code_collision",
        "d2_self_confirm_failed": False,
        "note": "D6 image-confirmed same-digit cross-vintage collision, Lampiran-5 p.135",
    },
    {
        "code": "02409",
        "verdict": "quarantined",
        "category": None,  # NEEDS-DATA
        "d2_self_confirm_failed": False,
        "note": "PENDING conductor per-code category",
    },
    {
        "code": "05102",
        "verdict": "quarantined",
        "category": None,  # NEEDS-DATA
        "d2_self_confirm_failed": False,
        "note": "PENDING conductor per-code category",
    },
    {
        "code": "05200",
        "verdict": "quarantined",
        "category": None,  # NEEDS-DATA
        "d2_self_confirm_failed": False,
        "note": "PENDING conductor per-code category",
    },
    {
        "code": "08920",
        "verdict": "quarantined",
        "category": None,  # NEEDS-DATA
        "d2_self_confirm_failed": False,
        "note": "PENDING conductor per-code category",
    },
    {
        "code": "36003",
        "verdict": "quarantined",
        "category": None,  # NEEDS-DATA
        "d2_self_confirm_failed": False,
        "note": "PENDING conductor per-code category",
    },
    {
        "code": "38122",
        "verdict": "quarantined",
        "category": None,  # NEEDS-DATA
        "d2_self_confirm_failed": False,
        "note": "PENDING conductor per-code category",
    },
    {
        "code": "38222",
        "verdict": "quarantined",
        "category": "phantom_source_pointer",
        "d2_self_confirm_failed": True,
        "note": (
            "D6-DEMOTED: D1/D5 independently agreed clean, but D2's self-confirming extraction "
            "failed (evidence page carries only the parent code 38220, not 38222 itself). Runner "
            "gap fixed same PR (Part 1) — a certified verdict with a failed D2 self-confirmation "
            "is now impossible by construction."
        ),
    },
    {
        "code": "39001",
        "verdict": "quarantined",
        "category": None,  # NEEDS-DATA
        "d2_self_confirm_failed": False,
        "note": "PENDING conductor per-code category",
    },
]

# NEEDS-DATA: the 2 innocence-control codes for Lot A-L1 were not named in
# the mandate — codes below are placeholders (code=None) until supplied.
LOT_A_L1_INNOCENCE: list[dict[str, Any]] = [
    {"code": None, "verdict": "certified", "note": "PENDING: innocence-control code identity not yet supplied"},
    {"code": None, "verdict": "certified", "note": "PENDING: innocence-control code identity not yet supplied"},
]


class LotReportError(RuntimeError):
    """Raised on any validation failure — fail-visible, never silent."""


def _validate_verdicts(verdicts: list[dict[str, Any]], innocence: list[dict[str, Any]]) -> None:
    """FAIL-CLOSED gate (module docstring): every entry must be genuinely complete
    before this compiler will render or emit anything. Guilt: a None code or a
    quarantined entry with category=None must be refused. Innocence: a fully
    populated table (real codes, in-registry categories) must pass."""
    for entry in verdicts:
        if not entry.get("code"):
            raise LotReportError(f"verdict entry missing code: {entry!r}")
        verdict = entry.get("verdict")
        if verdict not in FROZEN_TAXONOMY:
            raise LotReportError(
                f"code {entry['code']}: verdict {verdict!r} outside frozen taxonomy {FROZEN_TAXONOMY}"
            )
        if verdict == "quarantined":
            category = entry.get("category")
            if category is None:
                raise LotReportError(
                    f"code {entry['code']}: quarantined entry has no category — this is a "
                    "KNOWN-INCOMPLETE placeholder (see module docstring); supply the conductor's "
                    "per-code category before this compiler will run"
                )
            if category != CATEGORY_SENTINEL and category not in REFUTATION_CATEGORIES:
                raise LotReportError(
                    f"code {entry['code']}: category {category!r} is outside the closed registry "
                    f"{REFUTATION_CATEGORIES} and is not the literal sentinel {CATEGORY_SENTINEL!r}"
                )
    for entry in innocence:
        if not entry.get("code"):
            raise LotReportError(f"innocence entry missing code: {entry!r}")
        if entry.get("verdict") not in FROZEN_TAXONOMY:
            raise LotReportError(
                f"innocence code {entry['code']}: verdict {entry.get('verdict')!r} outside frozen "
                f"taxonomy {FROZEN_TAXONOMY}"
            )


def build_report(
    *,
    lot_id: str,
    verdicts: list[dict[str, Any]],
    innocence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pure assembly of the report — no I/O, no wall-clock. Same inputs =>
    byte-identical render (G16). Raises LotReportError on any incomplete or
    out-of-taxonomy entry (see _validate_verdicts) — never silently emits a
    partial/fabricated report."""
    _validate_verdicts(verdicts, innocence)

    certified = [v for v in verdicts if v["verdict"] == "certified"]
    quarantined = [v for v in verdicts if v["verdict"] == "quarantined"]
    abstained = [v for v in verdicts if v["verdict"] == "abstained"]
    categories_seen = sorted({v["category"] for v in quarantined if v.get("category")})
    demoted = [v for v in quarantined if v.get("d2_self_confirm_failed") is True]

    return {
        "lot_id": lot_id,
        "batch": "A",
        "plan": PLAN_PATH,
        "date": PINNED_DATE,
        "verdicts": sorted(
            (
                {
                    "code": v["code"],
                    "verdict": v["verdict"],
                    "category": v.get("category"),
                    "d2_self_confirm_failed": bool(v.get("d2_self_confirm_failed", False)),
                    "note": v.get("note", ""),
                }
                for v in verdicts
            ),
            key=lambda v: v["code"],
        ),
        "innocence_controls": sorted(
            (
                {"code": i["code"], "verdict": i["verdict"], "note": i.get("note", "")}
                for i in innocence
            ),
            key=lambda i: i["code"],
        ),
        "census": {
            "adjudicated": len(verdicts),
            "certified": len(certified),
            "quarantined": len(quarantined),
            "abstained": len(abstained),
            "demoted_at_d6": len(demoted),
            "innocence_controls": len(innocence),
        },
        "categories_seen": categories_seen,
        "closed_registry": list(REFUTATION_CATEGORIES),
        "conductor_sign_off": CONDUCTOR_SIGN_OFF,
    }


def render_json(ctx: dict[str, Any]) -> str:
    return json.dumps(ctx, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _display_path(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the artifact (default: dry-run)")
    ap.add_argument(
        "--out-json",
        type=Path,
        default=REPO_ROOT / OUT_JSON_TEMPLATE.format(lot_id=LOT_ID),
    )
    args = ap.parse_args(argv)

    ctx = build_report(lot_id=LOT_ID, verdicts=LOT_A_L1_VERDICTS, innocence=LOT_A_L1_INNOCENCE)
    payload_json = render_json(ctx)

    print(f"emit_lot_report — lot {LOT_ID} — mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  census: {ctx['census']}")
    print(f"  categories seen: {ctx['categories_seen']}")

    if not args.apply:
        print("DRY RUN — no file written. Re-run with --apply.")
        return 0

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(payload_json, encoding="utf-8")
    print(f"wrote {_display_path(args.out_json)} (sha256 {hashlib.sha256(payload_json.encode()).hexdigest()[:12]})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LotReportError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)
