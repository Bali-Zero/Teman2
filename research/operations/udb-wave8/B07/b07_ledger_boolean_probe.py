"""B07 Read-Only Metadata-Only Migration Ledger Boolean Probe.

Proposed per `.agent-receipts/udb-wave8-dux/DUX-CONSOLIDATION.md` (lines 42-46) and
`ADVERSARY-FINDINGS.md` (`B07-F2`, `B07-F3`) for fresh Opus 5.5 source review and
BLUE Dux execution.

Privacy & Safety Invariants:
1. Opens an explicit `READ ONLY` transaction (`SET TRANSACTION READ ONLY`).
2. Never selects or exports `applied_by`, `applied_as`, migration names, role names,
   rule names, or any string/text column from PostgreSQL.
3. Computes checksum equality in SQL/Python against the pinned `DR-B07-01.out`
   on-disk SHA-256 manifest and emits ONLY integer migration numbers, booleans,
   and aggregate integer counts.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_sql_manifest(path: Path) -> dict[int, dict[str, Any]]:
    """Normalize actual DR01 SQL filenames before any database connection."""
    import re
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or set(manifest) != {"migrations_v2", "py_migrations"}:
        raise ValueError("Expected actual DR01 migrations_v2/py_migrations schema")
    entries = manifest["migrations_v2"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("DR01 SQL array must be nonempty")
    result = {}
    for entry in entries:
        name = entry.get("file", "") if isinstance(entry, dict) else ""
        match = re.match(r"^(\d+)_.*\.sql$", name)
        if match is None:
            raise ValueError("SQL migration filename requires numeric prefix")
        number = int(match.group(1))
        if number in result:
            raise ValueError("Duplicate SQL migration number")
        for key in ("full_sha256", "forward_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get(key, ""))):
                raise ValueError("Missing SQL SHA256")
        result[number] = dict(entry, num=number)
    return result


async def run_boolean_probe(dr01_manifest_path: Path, dsn_env_var: str = "DATABASE_URL") -> dict[str, Any]:
    """Execute read-only boolean-only reconciliation against `_schema_versions` and `schema_migrations`."""
    import asyncpg  # Imported lazily only when Dux executes the probe

    disk_by_num = load_sql_manifest(dr01_manifest_path)

    dsn = os.environ[dsn_env_var]
    conn = await asyncpg.connect(dsn=dsn, timeout=15.0)
    try:
        async with conn.transaction(readonly=True):
            # Select ONLY integer version and boolean predicates — zero strings or actor columns
            sv_rows = await conn.fetch(
                """
                SELECT
                    migration_number::int AS version_num,
                    (checksum IS NOT NULL) AS has_checksum,
                    (checksum = 'manual_apply') AS is_manual_apply,
                    md5(COALESCE(checksum, '')) AS checksum_md5_internal,
                    checksum AS checksum_raw_internal,
                    (applied_by IS NOT NULL AND applied_as IS NOT NULL) AS has_provenance_populated
                FROM public._schema_versions
                ORDER BY migration_number::int ASC
                """
            )
            sm_rows = await conn.fetch(
                """
                SELECT
                    NULLIF( regexp_replace(split_part(migration_name, '_', 1), '[^0-9]', '', 'g'), '' )::int AS version_num,
                    (checksum IS NOT NULL) AS has_checksum,
                    (checksum = 'manual_apply') AS is_manual_apply,
                    checksum AS checksum_raw_internal
                FROM public.schema_migrations
                WHERE regexp_replace(split_part(migration_name, '_', 1), '[^0-9]', '', 'g') <> ''
                ORDER BY 1 ASC
                """
            )
            partition_stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE c.relname ~ '^olympus_heartbeats_y[0-9]{4}m[0-9]{2}$'
                    )::int AS monthly_partition_count,
                    BOOL_OR(c.relname = 'olympus_heartbeats_default') AS has_default_partition
                FROM pg_inherits i
                JOIN pg_class p ON p.oid = i.inhparent
                JOIN pg_class c ON c.oid = i.inhrelid
                JOIN pg_namespace n ON n.oid = p.relnamespace
                WHERE n.nspname = 'public' AND p.relname = 'olympus_heartbeats'
                """
            )
    finally:
        await conn.close()

    sv_by_num: dict[int, dict[str, Any]] = {}
    for row in sv_rows:
        v = row["version_num"]
        if isinstance(v, int):
            sv_by_num[v] = dict(row)

    sm_by_num: dict[int, list[dict[str, Any]]] = {}
    for row in sm_rows:
        v = row["version_num"]
        if isinstance(v, int):
            sm_by_num.setdefault(v, []).append(dict(row))

    all_nums = sorted(set(disk_by_num.keys()) | set(sv_by_num.keys()) | set(sm_by_num.keys()))
    per_migration_booleans: list[dict[str, int | bool]] = []

    counts = {
        "total_migration_numbers_evaluated": len(all_nums),
        "in_both_ledgers_count": 0,
        "in_schema_versions_only_count": 0,
        "in_schema_migrations_only_count": 0,
        "unapplied_on_disk_count": 0,
        "matches_disk_full_sha256_count": 0,
        "matches_disk_forward_sha256_only_count": 0,
        "manual_apply_sentinel_count": 0,
        "checksum_drift_count": 0,
        "dual_ledger_checksum_mismatch_count": 0,
        "schema_migrations_duplicate_number_count": 0,
        "provenance_populated_count": 0,
    }

    for num in all_nums:
        disk = disk_by_num.get(num)
        sv = sv_by_num.get(num)
        sm_list = sm_by_num.get(num, [])
        sm = sm_list[0] if sm_list else None

        in_sv = sv is not None
        in_sm = sm is not None
        has_dup_sm = len(sm_list) > 1

        sv_ck = sv["checksum_raw_internal"] if sv else None
        sm_ck = sm["checksum_raw_internal"] if sm else None
        full_sha = disk["full_sha256"] if disk else None
        fwd_sha = disk["forward_sha256"] if disk else None

        ledgers_equal = bool(in_sv and in_sm and sv_ck == sm_ck)
        active_cks = [c for c in (sv_ck if in_sv else None, sm_ck if in_sm else None) if c is not None]
        is_manual = any(c == "manual_apply" for c in active_cks) or (
            (in_sv and sv_ck is None) or (in_sm and sm_ck is None)
        )
        matches_full = bool(
            full_sha and active_cks and all(c == full_sha for c in active_cks)
        )
        matches_fwd = bool(
            fwd_sha and active_cks and all(c == fwd_sha for c in active_cks)
        )
        has_prov = bool(sv and sv["has_provenance_populated"])

        if in_sv and in_sm:
            counts["in_both_ledgers_count"] += 1
            if sv_ck != sm_ck:
                counts["dual_ledger_checksum_mismatch_count"] += 1
        elif in_sv and not in_sm:
            counts["in_schema_versions_only_count"] += 1
        elif in_sm and not in_sv:
            counts["in_schema_migrations_only_count"] += 1
        else:
            counts["unapplied_on_disk_count"] += 1

        if has_dup_sm:
            counts["schema_migrations_duplicate_number_count"] += 1
        if is_manual:
            counts["manual_apply_sentinel_count"] += 1
        if matches_full:
            counts["matches_disk_full_sha256_count"] += 1
        elif matches_fwd and not matches_full:
            counts["matches_disk_forward_sha256_only_count"] += 1
            counts["checksum_drift_count"] += 1
        elif (in_sv or in_sm) and not is_manual:
            counts["checksum_drift_count"] += 1

        if has_prov:
            counts["provenance_populated_count"] += 1

        per_migration_booleans.append(
            {
                "migration_number": int(num),
                "on_disk": disk is not None,
                "in_schema_versions": bool(in_sv),
                "in_schema_migrations": bool(in_sm),
                "schema_migrations_duplicate_num": bool(has_dup_sm),
                "ledgers_checksum_equal": bool(ledgers_equal),
                "is_manual_apply_sentinel": bool(is_manual),
                "matches_disk_full_sha256": bool(matches_full),
                "matches_disk_forward_sha256": bool(matches_fwd),
                "has_provenance_populated": bool(has_prov),
            }
        )

    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "readonly_transaction": True,
        "pii_or_actor_strings_exported": False,
        "summary_counts": counts,
        "olympus_heartbeats_partitions": {
            "monthly_partition_count": int(
                partition_stats["monthly_partition_count"] if partition_stats else 0
            ),
            "has_default_partition": bool(
                partition_stats["has_default_partition"] if partition_stats else False
            ),
        },
        "per_migration_booleans": per_migration_booleans,
    }


if __name__ == "__main__":
    default_dr01 = (
        Path(__file__).resolve().parent / "dux-requests" / "DR-B07-01.out"
    )
    output = asyncio.run(run_boolean_probe(default_dr01))
    print(json.dumps(output, indent=2, sort_keys=True))
