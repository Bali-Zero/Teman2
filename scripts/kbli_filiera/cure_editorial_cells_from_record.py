#!/usr/bin/env python3
"""cure_editorial_cells_from_record.py — make the stat card agree with the record.

WHAT IT FIXES, AND WHY THAT IS NOT AN EDITORIAL ACT
---------------------------------------------------
`intel_2026.editorial.byTheNumbers` is a list of label/value stat cards that
live IN THE DATA and are rendered verbatim. A cell reading
`Foreign-ownership ceiling · 100%` on a record whose `pma_max_asing` is 0 is not
a difference of opinion and not a sentence anybody chose: it is a stale COPY of
a field we own, left behind when the field moved. Restoring the copy asserts
nothing new, which is what makes this mechanical and what separates it from
`cure_national_ceiling_framing.py`, whose replacements had to be written by
someone and refuted by a cross-family seat before they could land.

Measured before writing this: all 27 affected records carry
`pma_cap_verified: true` and an integer cap. So the number being copied is one
the organism has already stood behind — the cure does not launder an unverified
value into a place it looks authoritative.

IT DOES NOT DECIDE WHICH CELLS ARE WRONG
----------------------------------------
The predicate lives in `editorial_record_conformance.py` and this module
CONSUMES its verdict rather than re-deriving it. Two tools that must agree about
the same fact do not get to invent two answers (W105) — and the predicate is
subtle in exactly the way that bites: a cell labelled `Bali PMA status` is
lawfully TERTUTUP over an open national record, and re-implementing "is this
cell wrong" here would eventually drift into rewriting 132 correct cells.

THE PROSE IS NOT TOUCHED, AND THAT IS ASSERTED, NOT PROMISED
-------------------------------------------------------------
27 further codes carry prose that contradicts the record. Replacing a sentence
means writing one (Legge 5), so this module leaves every string alone — and
proves it did, by re-running the detector on the patched document IN MEMORY and
requiring that the `needs_an_author` set comes out byte-identical. A cure that
silently improved a body would be authoring under cover of a mechanical pass.

FAIL-CLOSED, AND PROVEN BEFORE IT WRITES
-----------------------------------------
Nothing is written unless the patched document reports ZERO stale cells. A cure
that half-works is worse than one that refuses: it leaves a page consistent
enough to be believed and wrong where it counts. Any cell whose value cannot be
rewritten unambiguously — a ceiling holding two percentages, a status cell whose
text is not the stale status verbatim — is REFUSED and named, never guessed at.

USAGE (dry-run is the default; nothing is written without --apply):

    python3 scripts/kbli_filiera/cure_editorial_cells_from_record.py
    python3 scripts/kbli_filiera/cure_editorial_cells_from_record.py --apply
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_FILIERA = str(Path(__file__).resolve().parent)
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)

import editorial_record_conformance as E  # noqa: E402

from scripts.kbli_filiera.cure_l4_withdrawn_umkm_prose import (  # noqa: E402
    reconcile_sidecar,
    run_sync_script,
)

CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

logger = logging.getLogger("cure_editorial_cells")

_PERCENT = re.compile(r"(\d+)\s*%")


def _cells_of(record: dict[str, Any]) -> list[dict[str, Any]]:
    editorial = (record.get("intel_2026") or {}).get("editorial") or {}
    return [c for c in (editorial.get("byTheNumbers") or []) if isinstance(c, dict)]


def plan_for(record: dict[str, Any], verdict: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """What to rewrite on ONE record, and what this refuses to touch.

    `verdict` is `editorial_record_conformance.classify(record)` — the flagged
    cells are identified by their label, which is the only stable handle a cell
    has (the list has no ids and its order is not a contract).
    """
    edits: list[dict[str, Any]] = []
    refusals: list[str] = []
    code = record.get("kode_kbli_2025")
    cap = record.get("pma_max_asing")
    status = (record.get("pma_status") or "").upper()

    stale_ceiling = {c["label"] for c in verdict["ceiling_cells"]}
    stale_status = {c["label"]: c["says"] for c in verdict["status_cells"]}

    for cell in _cells_of(record):
        label = str(cell.get("label") or "")
        value = str(cell.get("value") or "")

        if label in stale_ceiling:
            if not isinstance(cap, int):
                refusals.append(f"{code}: {label!r} — record cap is {cap!r}, not a number")
                continue
            if len(_PERCENT.findall(value)) != 1:
                refusals.append(
                    f"{code}: {label!r} — value {value!r} holds "
                    f"{len(_PERCENT.findall(value))} percentages, cannot rewrite one"
                )
                continue
            edits.append(
                {
                    "code": code,
                    "label": label,
                    "cell": cell,
                    "was": value,
                    "now": _PERCENT.sub(f"{cap}%", value, count=1),
                }
            )
        elif label in stale_status:
            if value.strip().upper() != stale_status[label]:
                refusals.append(
                    f"{code}: {label!r} — value {value!r} is not the stale status "
                    f"{stale_status[label]!r} verbatim"
                )
                continue
            edits.append(
                {"code": code, "label": label, "cell": cell, "was": value, "now": status}
            )

    return edits, refusals


def run(canonical_path: Path, apply: bool) -> int:
    doc = json.loads(canonical_path.read_text(encoding="utf-8"))
    records = doc["data"]

    before = E.report(records)
    authored_before = list(before["needs_an_author"]["codes"])
    logger.info(
        "before: %d code(s) with stale cells (%d ceiling, %d status), %d needing an author",
        len(before["mechanically_correctable"]["codes"]),
        before["mechanically_correctable"]["ceiling_cells"],
        before["mechanically_correctable"]["status_cells"],
        len(authored_before),
    )

    patched = copy.deepcopy(records)
    all_edits: list[dict[str, Any]] = []
    all_refusals: list[str] = []
    for record in patched:
        verdict = E.classify(record)
        if not (verdict["ceiling_cells"] or verdict["status_cells"]):
            continue
        edits, refusals = plan_for(record, verdict)
        all_edits.extend(edits)
        all_refusals.extend(refusals)

    for edit in all_edits:
        edit["cell"]["value"] = edit["now"]

    for edit in all_edits:
        logger.info("  %s  %-34s %s -> %s", edit["code"], edit["label"], edit["was"], edit["now"])
    for refusal in all_refusals:
        logger.warning("  REFUSED %s", refusal)

    after = E.report(patched)
    remaining = len(after["mechanically_correctable"]["codes"])
    authored_after = list(after["needs_an_author"]["codes"])

    logger.info(
        "%s: %d cell(s) on %d code(s); %d refused; stale cells after: %d",
        "APPLY" if apply else "DRY-RUN",
        len(all_edits),
        len({e["code"] for e in all_edits}),
        len(all_refusals),
        remaining,
    )

    # The two conditions that make this safe to write, checked on the PATCHED
    # document rather than hoped for. Both are refusals, not warnings.
    if remaining:
        logger.error(
            "refusing to write: %d code(s) still hold a stale cell — a half-cure "
            "leaves a page consistent enough to be believed and wrong where it counts",
            remaining,
        )
        return 1
    if authored_after != authored_before:
        logger.error(
            "refusing to write: the set of codes needing an author changed "
            "(%d -> %d) — this pass must not touch prose",
            len(authored_before),
            len(authored_after),
        )
        return 1

    if not apply:
        logger.info("nothing written — rerun with --apply")
        return 0
    if not all_edits:
        logger.info("nothing to write")
        return 0

    doc["data"] = patched
    canonical_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("canonical written: %s", canonical_path)
    run_sync_script()
    reconcile_sidecar(canonical_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--canonical", type=Path, default=CANONICAL)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return run(args.canonical, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
