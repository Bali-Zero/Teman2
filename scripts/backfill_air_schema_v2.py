#!/usr/bin/env python3
"""Backfill Air historical snapshots to schema v2.

# Organ: scripts/ (one-shot migration, Air only)
# Produce: updated metabolic_snapshots (old rows split into global + host)
# Consume: existing metabolic_snapshots rows where collector_host IS NULL

Idempotent: if all rows already have collector_host set, exits cleanly.

For each legacy Air row (collector_host IS NULL):
  1. UPDATE in place → (collector='air', scope='global'), null out IA+FE
  2. INSERT new row → (collector='air', scope='host'), null out TTR+DO, keep IA+FE from legacy

Usage (Air only):
    python3 scripts/backfill_air_schema_v2.py --db-path ~/.agent/decisions/organism_metrics.db
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Air snapshots to v2 schema")
    parser.add_argument(
        "--db-path",
        default=os.path.expanduser("~/.agent/decisions/organism_metrics.db"),
        help="Path to organism_metrics.db",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would change")
    args = parser.parse_args()

    if not os.path.isfile(args.db_path):
        print(f"ERR: DB not found: {args.db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row

    # Preflight: confirm v2 schema present
    cols = {r[1] for r in conn.execute("PRAGMA table_info(metabolic_snapshots)")}
    if "collector_host" not in cols or "metric_scope" not in cols:
        print(
            "ERR: v2 schema missing (collector_host / metric_scope). "
            "Run metabolic_rollup.py once with cell-core v2 code first.",
            file=sys.stderr,
        )
        return 2

    # Find legacy rows
    legacy = conn.execute(
        "SELECT * FROM metabolic_snapshots WHERE collector_host IS NULL"
    ).fetchall()

    if not legacy:
        print("[backfill] no legacy rows — nothing to do (idempotent)")
        return 0

    print(f"[backfill] found {len(legacy)} legacy rows to split")
    if args.dry_run:
        for r in legacy:
            print(f"  id={r['id']}, at={r['calculated_at']}, ttr={r['ttr_value']}, ia={r['ia_value']}")
        print("[backfill] dry-run: no changes written")
        return 0

    not_applicable = json.dumps({"error": "not_applicable_by_design"})

    try:
        conn.execute("BEGIN IMMEDIATE")
        for r in legacy:
            # UPDATE legacy row → scope='global', keep TTR+DO, null IA+FE
            conn.execute(
                """UPDATE metabolic_snapshots
                   SET collector_host='air',
                       metric_scope='global',
                       ia_value=NULL,
                       ia_metadata=?,
                       fe_value=NULL,
                       fe_metadata=?
                   WHERE id=?""",
                (not_applicable, not_applicable, r["id"]),
            )
            # INSERT new host row → scope='host', null TTR+DO, keep IA+FE from legacy
            conn.execute(
                """INSERT INTO metabolic_snapshots
                   (calculated_at,
                    ttr_value, ttr_metadata,
                    do_value, do_metadata,
                    ia_value, ia_metadata,
                    fe_value, fe_metadata,
                    collector_host, metric_scope)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["calculated_at"],
                    None, not_applicable,
                    None, not_applicable,
                    r["ia_value"], r["ia_metadata"],
                    r["fe_value"], r["fe_metadata"],
                    "air", "host",
                ),
            )
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"ERR: backfill failed, rolled back: {e}", file=sys.stderr)
        return 3

    # Summary
    total = conn.execute("SELECT COUNT(*) FROM metabolic_snapshots").fetchone()[0]
    air_global = conn.execute(
        "SELECT COUNT(*) FROM metabolic_snapshots WHERE collector_host='air' AND metric_scope='global'"
    ).fetchone()[0]
    air_host = conn.execute(
        "SELECT COUNT(*) FROM metabolic_snapshots WHERE collector_host='air' AND metric_scope='host'"
    ).fetchone()[0]
    pro_host = conn.execute(
        "SELECT COUNT(*) FROM metabolic_snapshots WHERE collector_host='pro' AND metric_scope='host'"
    ).fetchone()[0]
    conn.close()

    print(f"[backfill] OK: split {len(legacy)} legacy rows into {len(legacy)*2} scoped rows")
    print(f"  total rows: {total}")
    print(f"  air(global): {air_global}, air(host): {air_host}, pro(host): {pro_host}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
