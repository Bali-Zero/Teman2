"""
kg_kbli_license_fix.py — remove collision/contaminated licensing (REQUIRES
edges) from the Postgres knowledge graph for KBLI codes whose CANONICAL
dataset record says there is no per-code licensing to show
(`per_skala == []`), and re-sync the node's description/uraian off the same
canonical record.

WHY (2026-07-16/17, PENDING-ARMS follow-up to #2508, extended for
GARUDA-FILIERA Fase 1): `inspect_kbli 68112` returned REQUIRES-linked
license blocks that do not belong to this code — a code-NUMBER collision
between BPS's current KBLI-2025 numbering and PP28/2025's OLD KBLI-2020
numbering re-using the same 5-digit code for an unrelated activity. #2508
fixed the FRONTEND dataset copy for 68112; the Fase 1 canonical cure
(commit `1ff7169bc6`, GO by Zero, pilot A1 image-verified) detached the
SAME pattern for 7 more codes — 49213, 51103, 51203, 20111, 50115, 60312,
64310 — bringing the total to 8 codes whose canonical `per_skala` is now an
explicit `[]` (frontend guards read `licensing.length > 0`, so `[]` renders
as an honest "not yet defined" gap, never a fabricated answer). The KG is a
SEPARATE datastore serving `inspect_kbli`/`chat_kbli` and is untouched by
either cure.

BUG in the first draft of this script (2026-07-16, caught before merge):
it deleted ONLY `kg_edges` rows whose `target_entity_id LIKE 'perizinan:%'`.
Live audit found the contamination is NOT confined to that prefix — e.g.
51103 (space-passenger transport, one of the 7) also carries wrong
licensing via a BARE-NAME target node (`sertifikat_operator_pesawat_udara_
aoc`, an AVIATION operator certificate — the false-friend collision is
aviation-vs-space, same numbering-vintage root cause as 68112's MICE-venue
collision) and a `license:sertifikat_standar` edge. Both survive a
`perizinan:%`-only DELETE. Since canonical `per_skala == []` means "this
code has NO licensing defined, full stop, honest gap" — not "no
`perizinan:`-prefixed licensing" — the correct scope is ALL of the code's
REQUIRES edges, any target prefix. This version fixes that: it deletes
`kg_edges` rows `source_entity_id = kbli:<code>`, `relationship_type =
'REQUIRES'` with NO prefix filter on `target_entity_id`. It still only
ever deletes EDGE rows, never target nodes (those are shared across many
codes and a separate, higher-risk decision) — see "Orphaned nodes" below.

AUDIT PARITY (never silent-delete, mirrors the canonical cure's own
`per_skala_disputed_pp28_collision` pattern): before an edge DELETE, the
list of `target_entity_id`s being removed is archived verbatim into
`kg_nodes.properties._disputed_requires` (a JSON array) on the SAME row, so
the removal is auditable by reading the node itself — no separate log-only
trail that can go stale or get lost. Idempotent: a re-run that finds the
edges already gone (current REQUIRES targets = []) does not touch — and
does not blank — a `_disputed_requires` archive written by an earlier run.

WHAT IT DOES per `--only` code:
  1. Load the canonical record — see `--dataset` below for local-file vs
     URL.
  2. If `per_skala` is anything other than an explicit empty list (INCLUDING
     the key being entirely absent): skip edge deletion — no generic
     derivation path exists for a non-empty/unknown licensing block, logged
     as a skip_reason, never guessed. Description/`properties.uraian` sync
     still runs independently if it drifted (a text staleness is unrelated
     to the licensing decision).
  3. If `per_skala == []`:
     a. Archive the CURRENT `target_entity_id`s of every `kbli:<code>`
        REQUIRES edge into `properties._disputed_requires` (skipped if
        there is nothing to archive — no edges currently exist).
     b. DELETE those `kg_edges` rows (`source_entity_id = kbli:<code>`,
        `relationship_type = 'REQUIRES'`, any target prefix).
     c. UPDATE `kg_nodes.description` and `properties.uraian` to the
        canonical `uraian` (this also closes the gap in `kg_kbli_resync.py`
        where `properties.uraian` — which the router prefers over
        `description`, see `kbli_notebook.py` `props.get("uraian",
        node["description"])` — was never re-synced).
     d. If the canonical record carries a `_data_note`, mirror it into
        `properties._data_note` (never fabricated — only copied verbatim).
  Orphaned target nodes (0 remaining edges after the delete) are left in
  place, not deleted — conservative default, they are inert once nothing
  points to them and node deletion is a separate, higher-risk decision.

SCOPE DISCIPLINE (unchanged from the first draft): `--only` is MANDATORY —
no code is EVER auto-discovered/swept. A live audit found licensing
contamination far beyond these 8 codes (one shared agriculture-marker
`perizinan:*` node alone is REQUIRES-linked from ~68% of the KG's ~1568
KBLI codes) — this script acts ONLY on codes explicitly named, because the
generic "per_skala empty -> licenses wrong" signal is specific to codes
whose canonical dataset record has ALREADY been corrected. A code whose
canonical `per_skala` is still non-empty needs its OWN dataset-level
correction first (this script has nothing to derive a fix from until
then) — it is skipped with a logged reason, never guessed.

USAGE (dry-run is the default; nothing is written without --apply):
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_kbli_license_fix.py --only 68112 [--apply]"

    # multiple codes (comma-separated, no spaces):
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_kbli_license_fix.py \
            --only 68112,49213,51103,51203,20111,50115,60312,64310 --apply"

    # dry-run against a LOCAL cured canonical file, BEFORE it merges to
    # main (the default --dataset is the GitHub raw main URL):
    python backend/scripts/kg_kbli_license_fix.py \
        --only 49213 --dataset data/source_documents/KBLI_2025_FINAL_CLEAN.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

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
    delete_all_requires: bool
    disputed_requires: list[str] = field(default_factory=list)  # target_entity_ids archived+deleted
    new_description: str | None = None
    new_properties: dict | None = None
    update_node: bool = False
    skip_reason: str | None = None


def plan_fix(
    code: str,
    record: dict | None,
    kg_row: dict | None,
    current_requires_targets: list[str] | None = None,
) -> LicenseFixPlan:
    """Pure decision function — no I/O, easy to unit test.

    `record` is the canonical dataset row for `code` (or None if missing).
    `kg_row` is {"description": str, "properties": dict} from kg_nodes (or
    None if the code isn't in the KG at all).
    `current_requires_targets` is the list of `target_entity_id` values for
    every `kg_edges` row `source_entity_id=kbli:<code>`,
    `relationship_type='REQUIRES'` presently in the KG — ANY target prefix
    (`perizinan:`, `license:`, bare-name, ...), not just `perizinan:%`. Pass
    `None`/`[]` when there is nothing to archive (none exist, or the caller
    hasn't queried edges at all — e.g. a dry-run with no DB access).
    """
    targets = list(current_requires_targets or [])

    if record is None:
        return LicenseFixPlan(
            code=code,
            found_in_kg=kg_row is not None,
            per_skala_empty=None,
            delete_all_requires=False,
            skip_reason="not in canonical dataset",
        )
    if kg_row is None:
        return LicenseFixPlan(
            code=code,
            found_in_kg=False,
            per_skala_empty=None,
            delete_all_requires=False,
            skip_reason="not in KG (kg_nodes)",
        )

    per_skala = record.get("per_skala")
    per_skala_empty = per_skala == []
    uraian = (record.get("uraian") or "").strip()
    data_note = record.get("_data_note")

    if per_skala_empty:
        # Honest gap: canonical says NO licensing at all for this code, so
        # EVERY REQUIRES edge is contamination — no prefix filter (the bug
        # this version fixes: a prior draft scoped this to `perizinan:%`
        # only and missed bare-name/`license:` targets).
        delete_all_requires = True
        disputed = targets
    else:
        # Non-empty (or missing) per_skala: no generic derivation path.
        # Do NOT touch edges. Still worth syncing uraian/description below
        # if they drifted — that's independent of the licensing decision —
        # so we fall through rather than bailing.
        delete_all_requires = False
        disputed = []

    old_props = kg_row["properties"] or {}
    new_props = dict(old_props)
    if uraian:
        new_props["uraian"] = uraian
    if data_note:
        new_props["_data_note"] = data_note
    if delete_all_requires and disputed:
        # Audit parity: archive what's about to be deleted, on the node
        # itself, BEFORE the edges are gone — mirrors the canonical cure's
        # own per_skala_disputed_pp28_collision pattern (never silent-delete).
        new_props["_disputed_requires"] = disputed

    old_description = kg_row["description"]
    description_stale = bool(uraian) and old_description != uraian
    props_stale = new_props != old_props
    update_node = description_stale or props_stale
    # Never write NULL over a perfectly good description: if update_node is
    # True purely because properties changed (uraian itself empty/unchanged),
    # new_description must fall back to the CURRENT value, not None — a
    # bare `uraian if uraian else None` here would bind NULL in the UPDATE
    # (same class of bug fixed live in kg_fix_68112_node.py's sibling cure).
    new_description = (uraian if uraian else old_description) if update_node else None

    return LicenseFixPlan(
        code=code,
        found_in_kg=True,
        per_skala_empty=per_skala_empty,
        delete_all_requires=delete_all_requires,
        disputed_requires=disputed,
        new_description=new_description,
        new_properties=new_props if update_node else None,
        update_node=update_node,
        skip_reason=None if per_skala_empty else "per_skala non-empty (or absent) — no generic derivation path",
    )


def _looks_like_local_path(source: str) -> bool:
    return not source.startswith(("http://", "https://")) and Path(source).exists()


async def load_dataset(source: str) -> list[dict]:
    """Load the canonical dataset from a local file path or a URL.

    A local path is used AS-IS, no network fetch — lets a dry-run validate
    against an uncommitted/pre-merge cured file on disk (e.g.
    `data/source_documents/KBLI_2025_FINAL_CLEAN.json`) before the
    canonical PR lands on `main`. Anything that isn't an existing local
    path is treated as a URL and fetched via httpx (default: GitHub raw).
    """
    if _looks_like_local_path(source):
        logger.info("dataset: reading local file %s", source)
        text = Path(source).read_text(encoding="utf-8")
        return json.loads(text)["data"]
    logger.info("dataset: fetching %s", source)
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.get(source)
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
    ap.add_argument(
        "--dataset",
        default=DATASET_URL,
        help="canonical dataset: local file path (read directly) or URL (httpx fetch). "
        "Default: GitHub raw main.",
    )
    args = ap.parse_args()
    codes = [c.strip() for c in args.only.split(",") if c.strip()]
    if not codes:
        logger.error("--only produced an empty code list, nothing to do")
        return

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    dataset = await load_dataset(args.dataset)
    by_code = {str(r.get("kode_kbli_2025")): r for r in dataset}

    conn = await asyncpg.connect(dsn)
    try:
        entity_ids = [f"kbli:{c}" for c in codes]
        node_rows = {
            r["entity_id"]: r
            for r in await conn.fetch(
                "SELECT entity_id, description, properties FROM kg_nodes WHERE entity_id = ANY($1)",
                entity_ids,
            )
        }
        edge_rows = await conn.fetch(
            "SELECT source_entity_id, target_entity_id FROM kg_edges "
            "WHERE source_entity_id = ANY($1) AND relationship_type = 'REQUIRES'",
            entity_ids,
        )
        edges_by_code: dict[str, list[str]] = {}
        for row in edge_rows:
            edges_by_code.setdefault(row["source_entity_id"], []).append(row["target_entity_id"])

        target_ids = sorted({t for targets in edges_by_code.values() for t in targets})
        target_names: dict[str, str] = {}
        if target_ids:
            for row in await conn.fetch(
                "SELECT entity_id, name FROM kg_nodes WHERE entity_id = ANY($1)", target_ids
            ):
                target_names[row["entity_id"]] = row["name"]

        plans: list[LicenseFixPlan] = []
        for code in codes:
            row = node_rows.get(f"kbli:{code}")
            kg_row_dict = None
            if row is not None:
                props = json.loads(row["properties"]) if isinstance(row["properties"], str) else row["properties"]
                kg_row_dict = {"description": row["description"], "properties": props or {}}
            current_targets = edges_by_code.get(f"kbli:{code}", [])
            plan = plan_fix(code, by_code.get(code), kg_row_dict, current_targets)
            plans.append(plan)

            if plan.skip_reason and not plan.update_node:
                logger.info("SKIP %s: %s", code, plan.skip_reason)
                continue

            if plan.delete_all_requires:
                for tid in current_targets:
                    logger.info("  %s: would delete REQUIRES -> %s (%s)", code, tid, target_names.get(tid, "?"))
                if args.apply and current_targets:
                    await conn.execute(
                        "DELETE FROM kg_edges WHERE source_entity_id = $1 AND relationship_type = 'REQUIRES'",
                        f"kbli:{code}",
                    )

            if plan.update_node:
                logger.info(
                    "  %s: would update description/properties.uraian (%d chars)%s%s",
                    code,
                    len(plan.new_description or ""),
                    " + _data_note" if plan.new_properties and plan.new_properties.get("_data_note") else "",
                    f" + _disputed_requires({len(plan.disputed_requires)})" if plan.disputed_requires else "",
                )
                if args.apply:
                    # W89 jsonb double-encoding class-guard: bind the pre-serialized
                    # json.dumps() string to a $N::text::jsonb placeholder (form (a)) so
                    # the server casts text->jsonb exactly once — correct whether or not a
                    # json codec is registered on the connection. A bare $N::jsonb next to
                    # json.dumps() is the double-encoding disease.
                    await conn.execute(
                        "UPDATE kg_nodes SET description = $2, properties = $3::text::jsonb, updated_at = now() "
                        "WHERE entity_id = $1",
                        f"kbli:{code}",
                        plan.new_description,
                        json.dumps(plan.new_properties, ensure_ascii=False),
                    )
    finally:
        await conn.close()

    mode = "APPLIED" if args.apply else "DRY-RUN"
    acted = [p for p in plans if p.delete_all_requires or p.update_node]
    skipped = [p for p in plans if p not in acted]
    logger.info("%s: %d code(s) acted on | %d skipped", mode, len(acted), len(skipped))
    for p in skipped:
        logger.info("  skipped %s: %s", p.code, p.skip_reason)
    if not args.apply and acted:
        logger.info("dry-run complete — rerun with --apply to write")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
