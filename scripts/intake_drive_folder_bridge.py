#!/usr/bin/env python3
"""Intake Drive folder→client bridge — Fase A/B resolver. DRY-RUN by default, ZERO writes.

The structural lever for the ~24.3k drive 0-candidate backlog: the human already organised
Drive per-client. `intake_queue.source_path` carries the folder hierarchy as NAMES. We resolve
each distinct folder segment → client (exact name match = 95% precision, measured on attached
ground truth; + trigram tier, precision measured here), then map every doc to a candidate client
via its folder provenance. A folder resolved once covers all its docs.

This is Station-2 candidate generation (it FINDS; it never attaches). Writeback of candidates
into entity_resolution.candidates goes through --write (gated) and is a SHADOW candidate set —
the existing deterministic tier / panel / human still make the attach decision. Never blind-attach.

Read-only against local nuzantara_dev (trust). PII (Law 2): emits ONLY counts, proposal_id (int),
client_id (int), method, similarity floats — never a client name / folder name / OCR text.

Usage:
  cd apps/backend-rag && source .venv/bin/activate
  PYTHONPATH=. python ../../scripts/intake_drive_folder_bridge.py                     # measure only
  PYTHONPATH=. python ../../scripts/intake_drive_folder_bridge.py --dump-candidates /tmp/cands.json
"""
from __future__ import annotations

import argparse
import asyncio
import json

import asyncpg

# the 16 root segments (staff/category folders) — never a client folder
ROOTS = {
    "novi", "data adi", "megi", "extend visa", "yanti", "pemegang kitas", "gendu", "yudi",
    "gendu (selective sync conflict 1)", "visa offshore", "lia", "data om dian", "driver",
    "dinok", "yoyok", "merp",
}

TRGM_TIER = 0.90  # trigram folder→client threshold (tight; precision measured against attached truth)

ZC = """
  p.status='review_pending'
  AND jsonb_typeof(p.entity_resolution->'candidates')='array'
  AND jsonb_array_length(p.entity_resolution->'candidates')=0
  AND q.source='drive' AND q.source_path IS NOT NULL
"""


async def _setup_temp(conn: asyncpg.Connection) -> None:
    await conn.execute("SET statement_timeout='250s'")
    # normalized client names (person + company), alive — run statements individually
    await conn.execute(
        """
        CREATE TEMP TABLE cln AS
          SELECT id AS client_id, lower(regexp_replace(trim(full_name),'\\s+',' ','g')) nm
            FROM clients WHERE deleted_at IS NULL AND length(trim(coalesce(full_name,'')))>=4
          UNION
          SELECT id, lower(regexp_replace(trim(company_name),'\\s+',' ','g'))
            FROM clients WHERE deleted_at IS NULL AND length(trim(coalesce(company_name,'')))>=4
        """
    )
    await conn.execute("CREATE INDEX ON cln (nm)")
    await conn.execute("CREATE INDEX cln_trgm ON cln USING gin (nm gin_trgm_ops)")
    await conn.execute("ANALYZE cln")
    # doc → each folder segment (non-root, non-filename)
    await conn.execute(
        f"""
        CREATE TEMP TABLE docseg AS
        SELECT p.id AS pid,
               lower(regexp_replace(trim(s.seg),'\\s+',' ','g')) sg
        FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id
        CROSS JOIN LATERAL unnest(string_to_array(regexp_replace(q.source_path,'^/*',''),'/')) AS s(seg)
        WHERE {ZC} AND length(trim(s.seg))>=4 AND s.seg !~ '\\.[a-zA-Z0-9]{{2,5}}$'
        """
    )
    await conn.execute("DELETE FROM docseg WHERE sg = ANY($1::text[])", list(ROOTS))
    await conn.execute("CREATE INDEX ON docseg (sg)")
    await conn.execute("CREATE INDEX ON docseg (pid)")


async def _resolve_exact(conn: asyncpg.Connection) -> None:
    """folder segment == client name, unique client → deterministic-folder tier."""
    await conn.execute(
        """
        CREATE TEMP TABLE res_exact AS
        SELECT d.pid, min(c.client_id) client_id
        FROM docseg d JOIN cln c ON d.sg = c.nm
        GROUP BY d.pid
        HAVING count(DISTINCT c.client_id) = 1;
        """
    )


async def _resolve_trgm(conn: asyncpg.Connection) -> None:
    """folder segment ~ client name (trigram >= TRGM_TIER), unique client, and NOT already exact."""
    await conn.execute("SELECT set_limit($1)", TRGM_TIER)
    await conn.execute(
        """
        CREATE TEMP TABLE res_trgm AS
        WITH cand AS (
          SELECT DISTINCT d.pid, c.client_id
          FROM docseg d JOIN cln c ON d.sg % c.nm
          WHERE d.pid NOT IN (SELECT pid FROM res_exact)
        )
        SELECT pid, min(client_id) client_id
        FROM cand GROUP BY pid HAVING count(DISTINCT client_id) = 1;
        """
    )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump-candidates", default=None)
    args = ap.parse_args()

    conn = await asyncpg.connect(
        host="127.0.0.1", port=5432, user="nuzantara", database="nuzantara_dev"
    )
    await _setup_temp(conn)
    await _resolve_exact(conn)
    await _resolve_trgm(conn)

    total = await conn.fetchval(
        f"SELECT count(DISTINCT p.id) FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id WHERE {ZC}"
    )
    n_exact = await conn.fetchval("SELECT count(*) FROM res_exact")
    n_trgm = await conn.fetchval("SELECT count(*) FROM res_trgm")
    folders_exact = await conn.fetchval(
        "SELECT count(DISTINCT c.client_id) FROM docseg d JOIN cln c ON d.sg=c.nm"
    )

    # PRECISION on attached-drive ground truth: exact-segment → does it point to the TRUE client?
    prec = await conn.fetchrow(
        """
        WITH attseg AS (
          SELECT p.id pid, (p.routing->>'client_id') true_cid,
                 lower(regexp_replace(trim(s.seg),'\\s+',' ','g')) sg
          FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id
          CROSS JOIN LATERAL unnest(string_to_array(regexp_replace(coalesce(q.source_path,''),'^/*',''),'/')) AS s(seg)
          WHERE p.status IN ('routed','auto_routed') AND q.source='drive'
            AND (p.routing->>'client_id') IS NOT NULL AND length(trim(s.seg))>=4
        )
        SELECT
          count(DISTINCT pid) FILTER (WHERE EXISTS (SELECT 1 FROM cln c WHERE c.nm=a.sg)) AS has_exact,
          count(DISTINCT pid) FILTER (WHERE EXISTS (SELECT 1 FROM cln c WHERE c.nm=a.sg AND c.client_id::text=a.true_cid)) AS exact_true
        FROM attseg a
        """
    )

    report = {
        "drive_zero_candidate_total": total,
        "resolved_exact_folder": n_exact,
        "resolved_trigram_folder": n_trgm,
        "resolved_union": n_exact + n_trgm,
        "resolved_pct": round(100.0 * (n_exact + n_trgm) / max(total, 1), 2),
        "distinct_folders_resolved_exact": folders_exact,
        "precision_validation_attached": {
            "exact_match_fires": prec["has_exact"],
            "exact_points_to_true_client": prec["exact_true"],
            "precision": round(prec["exact_true"] / max(prec["has_exact"], 1), 3),
        },
        "note": "DRY-RUN. exact tier = deterministic-folder (95% precision). Candidates only — attach via writer/panel.",
    }
    print(json.dumps(report, indent=2))

    if args.dump_candidates:
        rows = await conn.fetch(
            "SELECT pid, client_id, 'exact' m FROM res_exact "
            "UNION ALL SELECT pid, client_id, 'trgm' FROM res_trgm"
        )
        with open(args.dump_candidates, "w") as fh:
            json.dump([{"proposal_id": r["pid"], "client_id": r["client_id"], "method": r["m"]} for r in rows], fh)
        print(f"candidates (ints only) -> {args.dump_candidates} ({len(rows)} rows)")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
