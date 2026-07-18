#!/usr/bin/env python3
"""Intake Station-0 dedup/junk REPORT — DRY-RUN, ZERO writes.

Deterministic, no-LLM queue hygiene over the zero-candidate review_pending backlog.
Reads DB metadata only (blob_hash / blob_path extension) — retention-eviction of the
blob FILE does not block this. Emits redacted counts and, optionally, proposal_id lists
(integers only — Law 2 safe) for the operator to arm through the writer/terminal-state
path. It NEVER writes the DB itself.

Two cohorts:
  1. exact-duplicate blobs   -> candidate `duplicate` terminal state (keep 1 canonical per hash)
  2. hard-junk non-documents -> candidate `rejected`  terminal state (.zip/.aae/.mp4/... )

Usage:
  cd apps/backend-rag && source .venv/bin/activate
  PYTHONPATH=. python ../../scripts/intake_station0_report.py [--dump-ids /tmp/station0_ids.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json

import asyncpg

HARD_JUNK_EXT = (
    "zip", "rar", "kml", "bin", "eps", "ai", "mp4", "mov", "aae", "jps", "jfif",
)

ZC_FILTER = """
  p.status='review_pending'
  AND jsonb_typeof(p.entity_resolution->'candidates')='array'
  AND jsonb_array_length(p.entity_resolution->'candidates')=0
"""


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump-ids", default=None, help="write redacted proposal_id lists as JSON")
    args = ap.parse_args()

    conn = await asyncpg.connect(
        host="127.0.0.1", port=5432, user="nuzantara", database="nuzantara_dev"
    )

    # cohort 1: exact-duplicate blobs. For each blob_hash with >1 proposal, keep the
    # lowest proposal id as canonical; the rest are removable duplicates.
    dup_rows = await conn.fetch(
        f"""
        WITH zc AS (
          SELECT p.id AS pid, q.blob_hash
          FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id
          WHERE {ZC_FILTER} AND q.blob_hash IS NOT NULL
        ),
        ranked AS (
          SELECT pid, blob_hash,
                 row_number() OVER (PARTITION BY blob_hash ORDER BY pid) AS rn,
                 count(*)    OVER (PARTITION BY blob_hash)               AS grp
          FROM zc
        )
        SELECT pid FROM ranked WHERE grp > 1 AND rn > 1
        """
    )
    dup_ids = [r["pid"] for r in dup_rows]

    # cohort 2: hard-junk non-document extensions
    junk_rows = await conn.fetch(
        f"""
        SELECT p.id AS pid
        FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id
        WHERE {ZC_FILTER}
          AND lower(regexp_replace(q.blob_path,'.*\\.','')) = ANY($1::text[])
        """,
        list(HARD_JUNK_EXT),
    )
    junk_ids = [r["pid"] for r in junk_rows]

    await conn.close()

    # dedupe overlap (a junk file could also be a dup) — junk wins classification
    junk_set = set(junk_ids)
    dup_only = [i for i in dup_ids if i not in junk_set]

    report = {
        "cohort_duplicate_removable": len(dup_only),
        "cohort_hard_junk_reject": len(junk_ids),
        "total_removable_from_queue": len(dup_only) + len(junk_ids),
        "note": "DRY-RUN. No DB write. Arm via writer/terminal-state path with operator go.",
    }
    print(json.dumps(report, indent=2))

    if args.dump_ids:
        with open(args.dump_ids, "w") as fh:
            json.dump({"duplicate": dup_only, "reject": junk_ids}, fh)
        print(f"proposal_id lists (ints only) -> {args.dump_ids}")


if __name__ == "__main__":
    asyncio.run(main())
