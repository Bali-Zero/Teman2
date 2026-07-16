"""
kg_kbli_license_fix.py — remove collision/contaminated licensing (REQUIRES →
`perizinan:*`) edges from the Postgres knowledge graph for KBLI codes whose
CANONICAL dataset record says there is no per-code licensing to show
(`per_skala == []`), and re-sync the node's description/uraian off the same
canonical record.

WHY (2026-07-16, PENDING-ARMS follow-up to #2508): `inspect_kbli 68112`
returned 3 REQUIRES-linked license blocks that do not belong to this code:
an agriculture block ("good agriculture practices", reports to "Menteri
Pertanian" — a completely unrelated sector) and the PP28 MICE-venue block
(a code-NUMBER collision — 68112 under PP28's OLD KBLI-2020 numbering is a
different activity, "Penyewaan Venue ... MICE"). #2508 already fixed the
FRONTEND dataset copies (`per_skala -> []` + `_data_note` disclaimer,
verbatim canonical text below) — the KG is a SEPARATE datastore serving
`inspect_kbli`/`chat_kbli` and was untouched by that PR.

Live audit (read-only, 2026-07-16) found the license contamination is NOT
scoped to 68112: one single shared `perizinan:*` node carrying the
agriculture text above is REQUIRES-linked from 978 distinct `kbli:*` codes
(852 edges), and widening to any `perizinan:*` node whose properties mention
agriculture markers, 1069 of the KG's 1568 kbli codes are affected (~68% of
the whole catalog) — the majority attached to a non-agriculture sector. That
scale is FAR beyond what this script fixes: it only acts on codes passed
explicitly via `--only` (no code is EVER auto-discovered/swept), because the
generic "per_skala empty -> licenses wrong" signal this script relies on is
specific to codes like 68112 where the canonical dataset has ALREADY been
corrected to `per_skala: []`. A code whose canonical `per_skala` is still
non-empty (e.g. most of the 1069) needs its OWN dataset-level correction
first — this script has nothing to derive a fix from until then, so it skips
those with a log line rather than guessing. (Separately, the MICE/Venue
class of contamination — checked with a word-boundary regex, "PUMICE" is a
false-positive substring trap — is narrow: 68112 was in fact the only
non-legitimate hit found live.)

WHAT IT DOES per `--only` code:
  1. Fetch the canonical record (GitHub raw main, same source + URL as
     `kg_kbli_resync.py`).
  2. If `per_skala` is anything other than an explicit empty list: skip (no
     generic derivation path — logged, not silently ignored).
  3. If `per_skala == []`:
     a. DELETE the `kg_edges` rows `source_entity_id=kbli:<code>`,
        `relationship_type='REQUIRES'`, `target_entity_id LIKE 'perizinan:%'`.
        Edges to non-`perizinan:` targets (e.g. `company:pt_pma`, a legal
        entity-type fact, not a licensing requirement) are NEVER touched —
        this is scoped to entity TYPE, not a blanket wipe of the code's
        REQUIRES edges.
     b. UPDATE `kg_nodes.description` and `properties.uraian` to the
        canonical `uraian` (this also closes the gap in `kg_kbli_resync.py`
        where `properties.uraian` — which the router prefers over
        `description`, see `kbli_notebook.py` `props.get("uraian",
        node["description"])` — was never re-synced; see that script's
        matching patch in this same PR).
     c. If the canonical record carries a `_data_note`, mirror it into
        `properties._data_note` (never fabricated — only copied verbatim).
  Orphaned `perizinan:*` nodes (0 remaining edges after the delete) are left
  in place, not deleted — conservative default, they are inert once nothing
  points to them and deleting nodes is a separate, higher-risk decision.

USAGE (dry-run is the default; nothing is written without --apply):
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_kbli_license_fix.py --only 68112 [--apply]"

    # multiple codes (comma-separated, no spaces):
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_kbli_license_fix.py --only 68112,12345 --apply"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kg_kbli_license_fix")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"


@dataclass
class LicenseFixPlan:
    code: str
    found_in_kg: bool
    per_skala_empty: bool | None  # None when per_skala key absent from canonical record
    delete_perizinan_edges: bool
    new_description: str | None
    new_properties: dict | None
    update_node: bool
    skip_reason: str | None = field(default=None)


def plan_fix(code: str, record: dict | None, kg_row: dict | None) -> LicenseFixPlan:
    """Pure decision function — no I/O, easy to unit test.

    `record` is the canonical dataset row for `code` (or None if missing).
    `kg_row` is {"description": str, "properties": dict} from kg_nodes (or
    None if the code isn't in the KG at all).
    """
    if record is None:
        return LicenseFixPlan(code, kg_row is not None, None, False, None, None, False, "not in canonical dataset")
    if kg_row is None:
        return LicenseFixPlan(code, False, None, False, None, None, False, "not in KG (kg_nodes)")

    per_skala = record.get("per_skala")
    per_skala_empty = per_skala == []
    uraian = (record.get("uraian") or "").strip()
    data_note = record.get("_data_note")

    if not per_skala_empty:
        # Non-empty (or missing) per_skala: no generic derivation path yet.
        # Do NOT touch edges. Still worth syncing uraian/description below if
        # they drifted, so we fall through to that check rather than bailing.
        delete_edges = False
    else:
        delete_edges = True

    old_props = kg_row["properties"] or {}
    new_props = dict(old_props)
    if uraian:
        new_props["uraian"] = uraian
    if data_note:
        new_props["_data_note"] = data_note

    description_stale = bool(uraian) and kg_row["description"] != uraian
    props_stale = new_props != old_props
    update_node = description_stale or props_stale

    return LicenseFixPlan(
        code=code,
        found_in_kg=True,
        per_skala_empty=per_skala_empty,
        delete_perizinan_edges=delete_edges,
        new_description=uraian if uraian else None,
        new_properties=new_props if update_node else None,
        update_node=update_node,
        skip_reason=None if per_skala_empty else "per_skala non-empty — no generic derivation path",
    )


async def fetch_dataset() -> list[dict]:
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.get(DATASET_URL)
        r.raise_for_status()
        return r.json()["data"]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument(
        "--only",
        required=True,
        help="comma-separated list of 5-digit codes to process (never auto-discovered/swept)",
    )
    args = ap.parse_args()
    codes = [c.strip() for c in args.only.split(",") if c.strip()]
    if not codes:
        logger.error("--only produced an empty code list, nothing to do")
        return

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    dataset = await fetch_dataset()
    by_code = {str(r.get("kode_kbli_2025")): r for r in dataset}

    conn = await asyncpg.connect(dsn)
    try:
        rows = {
            r["entity_id"]: r
            for r in await conn.fetch(
                "SELECT entity_id, description, properties FROM kg_nodes WHERE entity_id = ANY($1)",
                [f"kbli:{c}" for c in codes],
            )
        }

        plans: list[LicenseFixPlan] = []
        for code in codes:
            kg_row = rows.get(f"kbli:{code}")
            kg_row_dict = None
            if kg_row is not None:
                props = json.loads(kg_row["properties"]) if isinstance(kg_row["properties"], str) else kg_row["properties"]
                kg_row_dict = {"description": kg_row["description"], "properties": props or {}}
            plan = plan_fix(code, by_code.get(code), kg_row_dict)
            plans.append(plan)

            if plan.skip_reason and not plan.update_node:
                logger.info("SKIP %s: %s", code, plan.skip_reason)
                continue

            if plan.delete_perizinan_edges:
                existing = await conn.fetch(
                    "SELECT target_entity_id, n.name FROM kg_edges e "
                    "JOIN kg_nodes n ON n.entity_id = e.target_entity_id "
                    "WHERE e.source_entity_id = $1 AND e.relationship_type = 'REQUIRES' "
                    "AND e.target_entity_id LIKE 'perizinan:%'",
                    f"kbli:{code}",
                )
                for row in existing:
                    logger.info("  %s: would delete REQUIRES -> %s (%s)", code, row["target_entity_id"], row["name"])
                if args.apply and existing:
                    await conn.execute(
                        "DELETE FROM kg_edges WHERE source_entity_id = $1 "
                        "AND relationship_type = 'REQUIRES' AND target_entity_id LIKE 'perizinan:%'",
                        f"kbli:{code}",
                    )

            if plan.update_node:
                logger.info(
                    "  %s: would update description/properties.uraian (%d chars)%s",
                    code,
                    len(plan.new_description or ""),
                    " + _data_note" if plan.new_properties and plan.new_properties.get("_data_note") else "",
                )
                if args.apply:
                    await conn.execute(
                        "UPDATE kg_nodes SET description = $2, properties = $3::jsonb, updated_at = now() "
                        "WHERE entity_id = $1",
                        f"kbli:{code}",
                        plan.new_description,
                        json.dumps(plan.new_properties, ensure_ascii=False),
                    )
    finally:
        await conn.close()

    mode = "APPLIED" if args.apply else "DRY-RUN"
    acted = [p for p in plans if p.delete_perizinan_edges or p.update_node]
    skipped = [p for p in plans if p not in acted]
    logger.info("%s: %d code(s) acted on | %d skipped", mode, len(acted), len(skipped))
    for p in skipped:
        logger.info("  skipped %s: %s", p.code, p.skip_reason)
    if not args.apply and acted:
        logger.info("dry-run complete — rerun with --apply to write")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
