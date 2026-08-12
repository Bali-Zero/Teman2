#!/usr/bin/env python3
"""Emit the state-derived spec for the additive ``l4_bali.verdict_state``.

Selection is the live canonical population, not a hand-authored code list.
Each entry pins the facts that determine the four-state verdict and asks the
companion compiler to add exactly one field.  This emitter never writes the
canonical dataset.

Usage:
  python scripts/kbli_filiera/emit_l4bali_verdict_state_spec.py --census
  python scripts/kbli_filiera/emit_l4bali_verdict_state_spec.py \
    --emit scripts/kbli_filiera/cure_specs/l4bali_verdict_state_2026_08_12.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

FILIERA_DIR = Path(__file__).resolve().parent
if str(FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(FILIERA_DIR))

from _l4bali_basis import (  # noqa: E402
    CODE_FIELD,
    OPEN_TIER_DERIVED_STATUSES,
    derive_verdict_state,
    verdict_state_facts,
)

logger = logging.getLogger("kbli_filiera.emit_l4bali_verdict_state_spec")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = (
    REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
)


class EmitError(RuntimeError):
    """The live dataset cannot support a complete, unambiguous spec."""


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise EmitError(f"{path}: expected a non-empty record list")
    return records


def build_spec(
    records: list[dict[str, Any]], canonical_path: Path
) -> tuple[dict[str, Any], Counter[str]]:
    """Return a complete state-selected spec and its measured census."""
    codes: dict[str, Any] = {}
    stats: Counter[str] = Counter()
    for record in records:
        code = str(record.get(CODE_FIELD) or "")
        if not code:
            raise EmitError("record without kode_kbli_2025")
        if code in codes:
            raise EmitError(f"duplicate kode_kbli_2025 {code!r}")
        try:
            facts = verdict_state_facts(record)
            target = derive_verdict_state(record)
        except ValueError as exc:
            raise EmitError(f"{code}: {exc}") from exc

        codes[code] = {
            "facts_basis": facts,
            "patch": {"verdict_state": target},
        }
        stats[f"verdict_state:{target}"] += 1
        stats[f"status:{facts['status']}"] += 1
        if facts["supporting_tier_absent"]:
            stats["open_supporting_tier_absent"] += 1
            stats[f"open_supporting_tier_absent:{facts['status']}"] += 1
        if facts["status"] == "NON_CLASSIFICABILE" and facts["blocked"]:
            stats["unknown_blocked_true_preserved"] += 1

    meta = {
        "purpose": (
            "Add l4_bali.verdict_state without changing the meaning or type of "
            "l4_bali.blocked. Selection and targets are derived from live record state."
        ),
        "created": date.today().isoformat(),
        "emitted_by": "scripts/kbli_filiera/emit_l4bali_verdict_state_spec.py",
        "canonical_source": str(canonical_path),
        "selection": "every live canonical record carrying a valid l4_bali Boolean verdict",
        "derivation_order": [
            "NON_CLASSIFICABILE -> unknown",
            "APERTO/OK with no supporting Besar high-risk tier -> provisional",
            "needs_review == true or confidence != HIGH -> provisional",
            "blocked == true -> blocked",
            "unblocked APERTO/OK open-family status -> open",
            "every other unblocked status -> provisional",
        ],
        "hard_rule": (
            "The only permitted patch key is verdict_state. blocked is never written; "
            "blocked=true on unknown records is deliberately preserved."
        ),
        "open_tier_statuses": sorted(OPEN_TIER_DERIVED_STATUSES),
        "measured_counts": dict(sorted(stats.items())),
    }
    return {"_meta": meta, "codes": codes}, stats


def report(records: list[dict[str, Any]], stats: Counter[str]) -> None:
    logger.info("canonical records: %d", len(records))
    logger.info("spec entries (state-selected): %d", len(records))
    logger.info("verdict_state:")
    for state in ("blocked", "open", "unknown", "provisional"):
        logger.info("  %-12s %d", state, stats[f"verdict_state:{state}"])
    logger.info("NON_CLASSIFICABILE: %d", stats["status:NON_CLASSIFICABILE"])
    logger.info(
        "  blocked=true preserved: %d", stats["unknown_blocked_true_preserved"]
    )
    logger.info(
        "open verdicts with supporting tier absent: %d",
        stats["open_supporting_tier_absent"],
    )
    for status in sorted(OPEN_TIER_DERIVED_STATUSES):
        logger.info(
            "  %-28s %d",
            status,
            stats[f"open_supporting_tier_absent:{status}"],
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--census", action="store_true", help="report only")
    parser.add_argument("--emit", type=Path, help="write the derived spec here")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        records = load_records(args.canonical)
        spec, stats = build_spec(records, args.canonical)
    except (OSError, json.JSONDecodeError, EmitError) as exc:
        logger.error("CANNOT-VERIFY: %s", exc)
        return 4

    report(records, stats)
    if args.emit:
        args.emit.parent.mkdir(parents=True, exist_ok=True)
        args.emit.write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        logger.info("wrote spec: %s (%d codes)", args.emit, len(spec["codes"]))
    elif not args.census:
        logger.info("no --emit supplied; census only, no files written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
