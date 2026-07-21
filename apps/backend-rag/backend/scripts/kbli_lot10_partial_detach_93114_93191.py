"""
kbli_lot10_partial_detach_93114_93191.py — ONE-OFF KG + Qdrant correction for
the two Batch-A Lot 10 codes whose canonical `per_skala` cure (PR #2921/#2923,
2026-07-21) was a TIER-SCOPED PARTIAL detach, not a full detach — the first
time a partial_detach cure has reached the KG/Qdrant surfaces.

WHY A ONE-OFF, NOT A NEW GENERIC PRIMITIVE: `kg_kbli_license_fix.py` and
`kbli_qdrant_risk_clear.py` are binary (all-or-nothing per code) — deleting
ALL REQUIRES edges / clearing the whole `kategori_risiko` field, gated on
canonical `per_skala == []`. 93114 and 93191 are NOT `per_skala == []` — each
still carries ONE valid surviving sound tier (see their canonical
`_data_note`), so the existing scripts' all-or-nothing logic does not apply
and is NOT touched here — future full-detach lots (e.g. 93193, same Lot 10)
keep using `kg_kbli_license_fix.py`/`kbli_qdrant_risk_clear.py` byte-identical.
This program's own precedent (the canonical-side tier-scoped primitive, PR
#2921, was only built once the SAME gap was confirmed TWICE — Lot 8 then Lot
9) says: fix a one-off first, generalize only once a THIRD lot needs it — see
the PENDING-ARMS entry appended alongside this script.

WHAT IT DOES (hardcoded, EXACT edge/value scope — never auto-discovered; all
values below were live-verified against Postgres kg_edges/kg_nodes, the Qdrant
`kbli_2025_final_hybrid` collection, and the canonical dataset's per-code
`per_skala`/`per_skala_disputed_pp28_collision` on 2026-07-21):

  93114 "Fasilitas Lapangan" — disputed tier = golf-course-specific
  (Tinggi risk, skala_usaha=[Menengah,Besar]):
    - DELETE + archive kg_edges (kbli:93114 -> perizinan:55be853cd247) and
      (kbli:93114 -> perizinan:a3aa2e154371) — both carry
      properties.skala_usaha=[Menengah,Besar].
    - LEAVE UNTOUCHED: (kbli:93114 -> perizinan:0bf540b11cf6) and
      (kbli:93114 -> perizinan:10829b720483) — skala_usaha=[Mikro,Kecil,
      Menengah], the surviving sound tier's own edges — and every other
      REQUIRES edge on kbli:93114 (5 non-perizinan-prefixed generic nodes
      whose kewajiban/perizinan text matches the SOUND tier, out of scope).
    - Qdrant: kategori_risiko 'Tinggi' (the disputed tier's stale value) ->
      'Menengah Rendah' (the surviving sound tier's OWN
      per_skala[0].kategori_risiko).

  93191 "Penyelenggaraan Kegiatan Olahraga" — disputed tier = foreign
  93193 "Aktivitas Perburuan" content wrongly present (Menengah Rendah risk,
  skala_usaha=[Kecil,Menengah,Besar]):
    - DELETE + archive kg_edges (kbli:93191 -> perizinan:0bf540b11cf6) and
      (kbli:93191 -> perizinan:e8782d0a474d) — both carry
      properties.skala_usaha=[Kecil,Menengah,Besar]. NOTE:
      perizinan:0bf540b11cf6 is a SEPARATE kg_edges row here
      (source_entity_id='kbli:93191') from the untouched
      (kbli:93114 -> perizinan:0bf540b11cf6) row above — same target node,
      shared by the KG's known name-dedup behavior (cicatrix #2), different
      source/edge; every DELETE below is scoped by the (source, target)
      pair, never by target alone.
    - LEAVE UNTOUCHED: (kbli:93191 -> perizinan:3d77b2be5090) — skala_usaha=
      [Mikro,Kecil,Menengah,Besar], the surviving sound "Promotor Kegiatan
      Olahraga" tier's own edge — and every other REQUIRES edge on
      kbli:93191 (4 non-perizinan generic nodes, incl. one literally named
      izin_usaha_promotor_kegiatan_olahraga matching the SOUND tier's own
      activity name, out of scope).
    - Qdrant: kategori_risiko is ALREADY 'Menengah Rendah' (equal to the
      surviving sound tier's own per_skala[0].kategori_risiko) — NO Qdrant
      write for 93191.

Neither code's `licensing_status` is touched (left exactly as-is,
'REGULATED' as of 2026-07-21) — a partial-detach code keeps one validly
licensed tier, unlike a full detach (kg_kbli_license_fix.py's
PENDING_REGULATION marker is correct ONLY when per_skala == [] / zero
surviving licensing). `description`/`properties.uraian` are also left
untouched — they describe the code generically, not per-tier, and re-sync is
outside this correction's scope.

Archive convention (matches kg_kbli_license_fix.py's `_disputed_requires`):
APPENDS (never overwrites) the 2 newly-detached target_entity_ids into
`kg_nodes.properties._disputed_requires` on the same node — idempotent, a
re-run that finds an edge already gone does not re-add it to the archive.

GUARDRAILS: before any write, every edge targeted for deletion is asserted
present with its EXACT expected `properties.skala_usaha`, and every edge that
must survive is asserted present — any drift from the live-verified state
above ABORTS (exit 1) rather than proceeding on a stale assumption.

RESULT (applied 2026-07-21, independently re-verified via fresh Postgres/
Qdrant queries — not the apply run's own success print):
  93114: kg_edges now has exactly 2 sound REQUIRES perizinan edges
  (0bf540b11cf6, 10829b720483) + 5 unrelated non-perizinan edges; the 2
  disputed edges are gone and archived in properties._disputed_requires;
  licensing_status untouched (REGULATED); Qdrant kategori_risiko corrected
  Tinggi -> Menengah Rendah. 93191: kg_edges now has exactly 1 sound REQUIRES
  perizinan edge (3d77b2be5090) + 4 unrelated non-perizinan edges; the 2
  disputed edges are gone and archived; licensing_status untouched
  (REGULATED); Qdrant kategori_risiko left at Menengah Rendah (no write —
  already correct). Public `/api/v1/kbli-notebook/inspect/{93114,93191}`
  confirmed clean of the cross-tier contamination post cache-bust.

USAGE (dry-run is the default; nothing is written without --apply). Run
inside the Fly VM (has the writable DATABASE_URL + reachable Qdrant):
    fly ssh console -a nuzantara-rag -g rag -C "python3 -" \
        < backend/scripts/kbli_lot10_partial_detach_93114_93191.py

    fly ssh console -a nuzantara-rag -g rag -C "python3 - --apply" \
        < backend/scripts/kbli_lot10_partial_detach_93114_93191.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg
from qdrant_client import QdrantClient
from qdrant_client.http import models

from backend.app.core.config import settings
from backend.core.collection_registry import resolve_collection_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kbli_lot10_partial_detach")

# Exact, live-verified (2026-07-21) edge scope — never auto-discovered.
DETACH_EDGES: dict[str, list[str]] = {
    "93114": ["perizinan:55be853cd247", "perizinan:a3aa2e154371"],
    "93191": ["perizinan:0bf540b11cf6", "perizinan:e8782d0a474d"],
}

# Expected properties.skala_usaha on each edge being detached — asserted
# before any write (guilt check).
EXPECTED_SKALA: dict[tuple[str, str], list[str]] = {
    ("93114", "perizinan:55be853cd247"): ["Menengah", "Besar"],
    ("93114", "perizinan:a3aa2e154371"): ["Menengah", "Besar"],
    ("93191", "perizinan:0bf540b11cf6"): ["Kecil", "Menengah", "Besar"],
    ("93191", "perizinan:e8782d0a474d"): ["Kecil", "Menengah", "Besar"],
}

# Edges that MUST survive untouched — asserted present (innocence check).
SOUND_EDGES_MUST_SURVIVE: dict[str, list[str]] = {
    "93114": ["perizinan:0bf540b11cf6", "perizinan:10829b720483"],
    "93191": ["perizinan:3d77b2be5090"],
}

# Qdrant kategori_risiko correction — only 93114 needs a write. Guarded: the
# CURRENT value must equal "from" exactly, or the script aborts rather than
# overwriting an unexpected state.
QDRANT_RISK_FIX: dict[str, dict[str, str]] = {
    "93114": {"from": "Tinggi", "to": "Menengah Rendah"},
    # 93191 intentionally absent: current value already correct, no write.
}


async def _fetch_state(conn: asyncpg.Connection, code: str) -> tuple[asyncpg.Record | None, dict]:
    """Return (kg_nodes row, {target_entity_id: properties dict}) for one code."""
    node = await conn.fetchrow(
        "SELECT entity_id, description, properties FROM kg_nodes WHERE entity_id = $1",
        f"kbli:{code}",
    )
    edges = await conn.fetch(
        "SELECT target_entity_id, properties FROM kg_edges "
        "WHERE source_entity_id = $1 AND relationship_type = 'REQUIRES'",
        f"kbli:{code}",
    )
    edge_props: dict[str, dict] = {}
    for row in edges:
        props = row["properties"]
        if isinstance(props, str):
            props = json.loads(props)
        edge_props[row["target_entity_id"]] = props or {}
    return node, edge_props


async def apply_kg(conn: asyncpg.Connection, apply: bool) -> None:
    for code, targets in DETACH_EDGES.items():
        node, edge_props = await _fetch_state(conn, code)
        if node is None:
            logger.error("ABORT %s: kbli node not found in kg_nodes", code)
            sys.exit(1)

        for tid in targets:
            if tid not in edge_props:
                logger.error("ABORT %s: expected edge -> %s not found in current kg_edges", code, tid)
                sys.exit(1)
            actual = edge_props[tid].get("skala_usaha")
            expected = EXPECTED_SKALA[(code, tid)]
            if actual != expected:
                logger.error(
                    "ABORT %s: edge -> %s skala_usaha mismatch: expected %s, found %s",
                    code, tid, expected, actual,
                )
                sys.exit(1)

        for tid in SOUND_EDGES_MUST_SURVIVE[code]:
            if tid not in edge_props:
                logger.error("ABORT %s: expected SURVIVING edge -> %s not found", code, tid)
                sys.exit(1)

        props = node["properties"]
        if isinstance(props, str):
            props = json.loads(props)
        props = dict(props or {})
        existing_archive = list(props.get("_disputed_requires") or [])
        already_archived = set(existing_archive)
        newly_archived = [t for t in targets if t not in already_archived]
        merged_archive = existing_archive + newly_archived

        logger.info(
            "%s: DELETE %d edge(s) %s | archive -> _disputed_requires (%d new, %d total) | "
            "licensing_status untouched (%s) | description/uraian untouched",
            code, len(targets), targets, len(newly_archived), len(merged_archive),
            props.get("licensing_status"),
        )
        for tid in SOUND_EDGES_MUST_SURVIVE[code]:
            logger.info(
                "%s: LEAVE UNTOUCHED -> %s (skala_usaha=%s)",
                code, tid, edge_props[tid].get("skala_usaha"),
            )

        if not apply:
            continue

        if newly_archived:
            new_props = dict(props)
            new_props["_disputed_requires"] = merged_archive
            await conn.execute(
                "UPDATE kg_nodes SET properties = $2::text::jsonb, updated_at = now() WHERE entity_id = $1",
                f"kbli:{code}",
                json.dumps(new_props, ensure_ascii=False),
            )
        await conn.execute(
            "DELETE FROM kg_edges WHERE source_entity_id = $1 AND relationship_type = 'REQUIRES' "
            "AND target_entity_id = ANY($2)",
            f"kbli:{code}",
            targets,
        )


def apply_qdrant(apply: bool) -> None:
    if not QDRANT_RISK_FIX:
        return
    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    collection = resolve_collection_name("kbli_2025_final")
    for code, fix in QDRANT_RISK_FIX.items():
        scroll_filter = models.Filter(
            must=[models.FieldCondition(key="kode_kbli", match=models.MatchValue(value=code))]
        )
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=scroll_filter,
            limit=16,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            logger.error("ABORT %s: no Qdrant points found for kode_kbli=%s", code, code)
            sys.exit(1)
        for rec in points:
            current = (rec.payload or {}).get("kategori_risiko")
            if current != fix["from"]:
                logger.error(
                    "ABORT %s: point %s kategori_risiko is %r, expected %r — refusing to write",
                    code, rec.id, current, fix["from"],
                )
                sys.exit(1)
            logger.info(
                "%s: point %s kategori_risiko %r -> %r%s",
                code, rec.id, current, fix["to"], "" if apply else " (dry-run, not written)",
            )
            if apply:
                client.set_payload(
                    collection_name=collection,
                    payload={"kategori_risiko": fix["to"]},
                    points=[rec.id],
                )


async def main() -> None:
    apply = "--apply" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await apply_kg(conn, apply)
    finally:
        await conn.close()
    apply_qdrant(apply)
    mode = "APPLY" if apply else "DRY-RUN"
    logger.info("%s complete", mode)
    if not apply:
        logger.info("dry-run complete — rerun with --apply to write")


if __name__ == "__main__":
    asyncio.run(main())
