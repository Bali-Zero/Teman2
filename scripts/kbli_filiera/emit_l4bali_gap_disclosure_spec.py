#!/usr/bin/env python3
"""emit_l4bali_gap_disclosure_spec.py — census + spec emitter for the l4_bali
STALE-CERTIFYING codes that `cure_l4bali_disclosure.py` structurally cannot see.

WHY THIS EXISTS
---------------
`cure_l4bali_disclosure.py` (2026-07-19) cured 57 codes whose Bali verdict was
derived from a `kategori_risiko` tier that now lives only in a disowned
`per_skala_disputed_*` block. Its spec keys every entry on `disputed_key`, and
its guard skips any record where that key is absent.

That selector is the defect. A code detached WITHOUT ever receiving a disputed
marker has no key to name, so it is invisible to the cure — not skipped, not
reported, simply out of the tool's reach. Measured by THIS selector on the
canonical of 2026-07-25 (the emitted spec IS the census — re-count it, never
trust a number in prose):
**95 codes still carried a certified Bali verdict derived from a detached or
never-retrievable risk layer** — 40 with a disputed marker, **54 with no marker
at all**, and **1 partial detach** where rows survive but not the tier the
verdict cites. 24 of the 95 read `blocked: true` at `confidence: HIGH`,
`needs_review: false` — i.e. the page tells a client "a PT PMA cannot register
this in Bali", stated as settled, on a risk tier the same record declares
unverifiable. (The partial-detach one, 93114, fails the other way: it tells the
client the code IS registrable, at HIGH confidence, citing a Besar tier that is
no longer in the record.)

(An earlier hand census of the same population, run by matching risk words in
`l4_bali.reason` PROSE, said 134/101/64. It over-counted: the reason of a
PMA-derived verdict also mentions risk. The prose number is recorded here only
so nobody re-derives it and believes it — the structural selector is the census.)

This is the second sighting of one structural disease, already recorded in the
`/kbli-navigator` corner for the phantom codes: **every cure tool in the fleet
selects on a MARKER rather than on the STATE**, so whatever lacks the marker is
unreachable by all of them at once. The cure here selects on the state.

SELECTION (structural — never prose)
------------------------------------
A code is IN SCOPE when all four hold:

  1. `l4_bali.status` is one of `RISK_DERIVED_STATUSES` — verdicts the #1814
     pass computes FROM the risk/scale layer. Statuses derived from another
     layer (TERTUTUP/TERBATAS come from `pma_status`, CHIUSO_REGOLATORE_
     SETTORIALE from a sector regulator) are excluded: their basis is intact,
     so disclosing a derivation defect there would be false.
  2/3. The layer that basis comes from is DEAD, in one of three shapes
     (`_l4bali_basis.gap_basis`, shared with the writer):
       - `disputed_key`  — `per_skala == []` and a `per_skala_disputed_*` key
                           holds the disowned rows.
       - `no_oss_scope`  — `per_skala == []` and `_l2_status == "no_oss_risk"`,
                           i.e. no scope resolved from OSS when the dataset was
                           built. A bare empty `per_skala` with NEITHER signal
                           is not assumed to be a gap (F12: absence needs a
                           second signal).
       - `detached_tier` — a PARTIAL detach: rows SURVIVE, and the stored status
                           no longer follows from them under the same rule that
                           wrote it (`status_matches_surviving_rows`). Without
                           this shape a `per_skala == []` test reads a partially
                           detached record as intact — which is how 93114 kept
                           telling clients "registrable by a PT PMA" at HIGH
                           confidence on a Besar tier that had been disowned.
  4. The record still CERTIFIES that verdict: `confidence != "LOW"` or
     `needs_review is not True`, and the reason does not already carry the
     disclosure prefix.

Matching is on enum identity and structural state. No sentence is pattern-
matched to decide a verdict's basis (cicatrix superscar #3).

OUTPUT
------
`--census` prints the population and its breakdown, writing nothing.
`--emit <path>` writes a cure spec in the exact schema
`cure_l4bali_disclosure.py` consumes, with per-code `expected_*` preconditions
read from the live canonical, plus a `gap_basis` of:

  - `"disputed_key"` — a `per_skala_disputed_*` key exists and holds every row.
    (The suffix does NOT name the key: `l4_bali.reason` is reader-facing prose,
    and wave 1's key-naming sentence was migrated off it catalogue-wide by
    `cure_l4bali_disclosure.py --reword-legacy` on 2026-07-25.)
  - `"no_oss_scope"` — no disputed key exists; the suffix instead states what is
    actually true (no OSS-RBA scope retrievable when the dataset was built).
    Inventing a disputed key here would be a fabricated citation.
  - `"detached_tier"` — a partial detach; the suffix says the cited tier is no
    longer among the record's rows.

This script NEVER writes the canonical. It is a read-only census + spec emitter;
`cure_l4bali_disclosure.py` remains the only sanctioned writer.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("kbli_filiera.emit_l4bali_gap_disclosure_spec")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

# Sibling-module import: works both when this file is executed directly (Python
# auto-adds its own directory to sys.path[0]) and when a test has already
# inserted this directory (same pattern as cure_metadata_pp28_sources.py). The
# structural predicates live in ONE module shared with the writer, so census and
# cure can never disagree about which records are stale-certifying.
_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

from _l4bali_basis import (  # noqa: E402
    CODE_FIELD,
    DISCLOSURE_PREFIX,
    GAP_BASIS_DETACHED_TIER,
    GAP_BASIS_DISPUTED_KEY,
    GAP_BASIS_NO_OSS_SCOPE,
    NON_RISK_DERIVED_STATUSES,
    RISK_DERIVED_STATUSES,
    disputed_keys,
    gap_basis,
    still_certifies,
)


def select(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter]:
    """Return (in-scope records with their gap basis, a breakdown counter)."""
    seen_statuses: set[str] = set()
    selected: list[dict[str, Any]] = []
    stats: Counter = Counter()

    for record in records:
        l4 = record.get("l4_bali")
        if not isinstance(l4, dict):
            stats["no_l4_bali"] += 1
            continue
        status = l4.get("status")
        seen_statuses.add(str(status))

        basis = gap_basis(record)
        if status not in RISK_DERIVED_STATUSES:
            if basis:
                stats["excluded_basis_intact"] += 1
            continue
        if basis is None:
            stats["risk_derived_basis_present"] += 1
            continue
        if not still_certifies(l4):
            stats["already_disclosed"] += 1
            continue

        selected.append({"record": record, "gap_basis": basis})
        stats[f"selected_{basis}"] += 1
        if l4.get("blocked"):
            stats["selected_blocked_true"] += 1
        if l4.get("blocked") and l4.get("confidence") == "HIGH":
            stats["selected_blocked_true_high_confidence"] += 1

    unknown = seen_statuses - RISK_DERIVED_STATUSES - NON_RISK_DERIVED_STATUSES - {"None"}
    if unknown:
        # Fail loud: an unclassified status means this script cannot say whether
        # its basis is the detached layer, and guessing is how the original bug
        # was born.
        raise SystemExit(
            f"UNCLASSIFIED l4_bali.status values in canonical: {sorted(unknown)} — "
            "classify them in RISK_DERIVED_STATUSES or NON_RISK_DERIVED_STATUSES "
            "before emitting a spec"
        )
    return selected, stats


# Bookkeeping only — see `_meta.editorial_residue`. NEVER used for selection:
# prose decides nothing about a verdict's basis (cicatrix superscar #3).
_TIER_CLAIM_RE = re.compile(r"(medium-high|medium-low|medium|high|low)[- ]risk|risk tier", re.I)


def _intel_prose(record: dict[str, Any]) -> str:
    chunks: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            chunks.append(node)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key != "_l3_regen":  # generation metadata, not reader-facing
                    walk(value)

    walk(record.get("intel_2026") or {})
    return " ".join(chunks)


def _count_editorial_tier_claims(selected: list[dict[str, Any]]) -> int:
    return sum(1 for item in selected if _TIER_CLAIM_RE.search(_intel_prose(item["record"])))


def build_spec(selected: list[dict[str, Any]], canonical_path: Path) -> dict[str, Any]:
    codes: dict[str, Any] = {}
    for item in selected:
        record = item["record"]
        l4 = record["l4_bali"]
        entry: dict[str, Any] = {
            "gap_basis": item["gap_basis"],
            "expected_status": l4.get("status"),
            "expected_reason": l4.get("reason"),
            "expected_confidence": l4.get("confidence"),
            "expected_needs_review": l4.get("needs_review"),
            "expected_blocked": l4.get("blocked"),
        }
        if item["gap_basis"] == GAP_BASIS_DISPUTED_KEY:
            entry["disputed_key"] = disputed_keys(record)[0]
        codes[record[CODE_FIELD]] = entry

    return {
        "_meta": {
            "purpose": (
                "GARUDA-FILIERA l4_bali disclosure cure, wave 2: codes whose Bali "
                "verdict is derived from a risk/scale layer that is a declared gap, "
                "while the record still certifies that verdict (confidence != LOW or "
                "needs_review != true). Wave 1 (l4bali_disclosure_2026_07_19.json) "
                "selected on the presence of a per_skala_disputed_* marker and so "
                "could not see the codes detached without one."
            ),
            "created": date.today().isoformat(),
            "emitted_by": "scripts/kbli_filiera/emit_l4bali_gap_disclosure_spec.py",
            "canonical_source": str(canonical_path.relative_to(REPO_ROOT)),
            "selection": (
                "l4_bali.status in RISK_DERIVED_STATUSES AND the layer that status "
                "derives from is dead — per_skala == [] with a corroborating signal "
                "(per_skala_disputed_* present, or _l2_status == 'no_oss_risk'), OR a "
                "PARTIAL detach where rows survive but the stored status no longer "
                "follows from them — AND the record still certifies "
                "(structural only — no prose matching)"
            ),
            "editorial_residue": {
                "measured": (
                    f"{_count_editorial_tier_claims(selected)} of {len(selected)} codes in this "
                    "spec carry intel_2026 prose that states a risk tier as FACT (e.g. 'as a "
                    "medium-high/high-risk activity'). This cure deliberately does not touch "
                    "editorial prose — it only discloses l4_bali."
                ),
                "consequence": (
                    "on those pages the article body and the Bali badge now disagree: the badge "
                    "reads 'derivation under review', the prose still asserts the tier."
                ),
                "detection": (
                    "prose matching — sound for BOOKKEEPING, and never used to select a record "
                    "for cure (selection is structural only)."
                ),
                "owner": "editorial rewrite lane — tracked in modus PENDING-ARMS",
            },
            "hard_rule": (
                "Changes ONLY l4_bali.confidence -> LOW, l4_bali.needs_review -> true, "
                "and l4_bali.reason (disclosure-wrapped, original preserved verbatim as "
                "an audit-trail substring). l4_bali.status and l4_bali.blocked are NEVER "
                "modified — flipping either would be a re-derivation requiring the true "
                "risk tier (F15: the conservative posture stays)."
            ),
        },
        "codes": codes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--census", action="store_true", help="print the population, write nothing")
    parser.add_argument("--emit", type=Path, default=None, help="write the cure spec to this path")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    payload = json.loads(args.canonical.read_text(encoding="utf-8"))
    records = payload["data"]
    selected, stats = select(records)

    logger.info("canonical records: %d", len(records))
    logger.info("IN SCOPE (stale-certifying, gap-derived): %d", len(selected))
    for key in sorted(stats):
        logger.info("  %-42s %d", key, stats[key])

    if args.census and not args.emit:
        by_status = Counter(item["record"]["l4_bali"].get("status") for item in selected)
        logger.info("\nby l4_bali.status:")
        for status, n in by_status.most_common():
            logger.info("  %-32s %d", status, n)
        return 0

    if args.emit:
        spec = build_spec(selected, args.canonical)
        args.emit.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        logger.info("\nwrote spec: %s (%d codes)", args.emit, len(spec["codes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
