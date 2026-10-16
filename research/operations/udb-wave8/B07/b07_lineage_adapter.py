"""B07 Maintenance & Migration Lineage Adapter (D02, D11, D13).

Pure-stdlib, deterministic verification and contract-instance builder for Wave 8 B07.
Conforms strictly to `.agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md` and
addresses adversarial findings X1..X5, X10, and B07-F1..B07-F5.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

BASE_SOURCE_VERSION = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
STATIC_EVIDENCE_TIMESTAMP = "2026-10-15T07:06:22Z"
DR01_EVIDENCE_TIMESTAMP = "2026-10-15T08:55:00.474686+00:00"
DR01_STDOUT_SHA256 = "9f92dddb911159d272d6bbc5fd88fd67a84cdbc4215249bf18566db755be211b"
DR05_EVIDENCE_TIMESTAMP = "2026-10-15T08:55:00.474686+00:00"
DR05_STDOUT_SHA256 = "69e746095c59620db1b7da09bc52992532aa43faeed72678350f3a51f8d47b7b"
DR05_PRO_EVIDENCE_TIMESTAMP = "2026-10-15T08:55:09Z"

CANONICAL_PG_STORE_ID = "pg:fly:nuzantara-postgres/public"
UNASSIGNED_OPERATION_ID = "UNASSIGNED_B05"

VALID_STATUSES: frozenset[str] = frozenset(
    {"EVIDENCED", "PARTIAL", "BLOCKED", "CONFLICT", "UNKNOWN"}
)

BASE_FROZEN_KEYS: tuple[str, ...] = (
    "consumer_id",
    "operation_id",
    "store_id",
    "source_version",
    "evidence_timestamp",
    "evidence_sha256",
    "status",
    "unknowns",
)

INSTANCE_11_KEYS: tuple[str, ...] = (
    "principal",
    "role",
    "tenant",
    "authorization",
    "transaction",
    "effects",
    "retries",
    "idempotency",
    "failure",
    "retention",
    "recovery",
)

STORE_ID_PATTERN = re.compile(
    r"^(?:unknown:unknown:unknown|"
    r"(?:pg|qdrant|redis|sqlite|graph|object|file|sheet|browser|external):"
    r"(?:fly|pro|mini|m5|gcloud|gdrive|github|client|unknown):"
    r"[a-z0-9][a-z0-9._-]*(?:/[a-zA-Z0-9._/-]+)?)$"
)


def sha256_file(path: Path) -> str:
    """Compute hex SHA-256 of a file on disk."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_field(
    value: Any,
    status: str,
    evidence_ref: str | None,
) -> dict[str, Any]:
    """Create one of the 11 B05 operation-instance field objects."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid field status: {status!r}")
    return {
        "value": value,
        "status": status,
        "evidence_ref": evidence_ref,
    }


def load_consumer_matrix_index(
    csv_path: Path,
) -> tuple[frozenset[str], dict[str, list[str]]]:
    """Load consumer_id set and entry_point -> [consumer_id] map from consumer-matrix.csv."""
    consumer_ids: set[str] = set()
    by_entry_point: dict[str, list[str]] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cid = (row.get("consumer_id") or "").strip()
            ep = (row.get("entry_point") or "").strip()
            if cid:
                consumer_ids.add(cid)
            if cid and ep:
                by_entry_point.setdefault(ep, []).append(cid)
    return frozenset(consumer_ids), by_entry_point


def validate_operation_instance(
    record: dict[str, Any],
    valid_consumer_ids: frozenset[str],
) -> None:
    """Validate an operation instance against CONTRACT-CONVENTIONS.md."""
    for key in BASE_FROZEN_KEYS:
        if key not in record:
            raise ValueError(f"Missing frozen base key: {key!r}")
    for key in INSTANCE_11_KEYS:
        if key not in record:
            raise ValueError(f"Missing B05 instance key: {key!r}")
        field_obj = record[key]
        if not isinstance(field_obj, dict) or set(field_obj.keys()) != {
            "value",
            "status",
            "evidence_ref",
        }:
            raise ValueError(
                f"Field {key!r} must be {{'value', 'status', 'evidence_ref'}}, got {field_obj!r}"
            )
        if field_obj["status"] not in VALID_STATUSES:
            raise ValueError(f"Invalid status in field {key!r}: {field_obj['status']!r}")

    allowed_non_ext = set(BASE_FROZEN_KEYS) | set(INSTANCE_11_KEYS)
    for key in record:
        if key not in allowed_non_ext and not key.startswith("x_"):
            raise ValueError(
                f"Extra key {key!r} violates CONTRACT-CONVENTIONS.md (must be prefixed with 'x_')"
            )

    cid = record["consumer_id"]
    if cid not in valid_consumer_ids:
        raise ValueError(
            f"consumer_id {cid!r} not found in consumer-matrix.csv (X10 / B07-F4 violation)"
        )

    if record["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid top-level status: {record['status']!r}")

    if not STORE_ID_PATTERN.match(str(record["store_id"])):
        raise ValueError(f"Invalid store_id grammar: {record['store_id']!r}")

    if not isinstance(record["unknowns"], list):
        raise ValueError("unknowns must be a list of strings")
    if record["store_id"] == "unknown:unknown:unknown" and not any(
        isinstance(value, str) and value.startswith("STORE_ID_PROPOSED:")
        for value in record["unknowns"]
    ):
        raise ValueError("Unknown store sentinel requires STORE_ID_PROPOSED")


    if record["operation_id"] == UNASSIGNED_OPERATION_ID:
        if "OPERATION_ID_PENDING_B05" not in record["unknowns"]:
            raise ValueError(
                "UNASSIGNED_B05 operation_id requires 'OPERATION_ID_PENDING_B05' in unknowns"
            )


def reconcile_migration_checksums(
    disk_entry: dict[str, Any],
    schema_versions_row: dict[str, Any] | None,
    schema_migrations_row: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reconcile an on-disk migration manifest entry against both live tracking ledgers.

    Flags:
    - CHECKSUM_DRIFT_FILE_VS_LEDGER when a recorded ledger SHA-256 differs from on-disk SHA-256.
    - FORWARD_VS_FULL_HASH_MISMATCH when ledger matches forward_sha256 instead of full_sha256
      for a migration that contains a `-- ROLLBACK:` section.
    - MANUAL_APPLY_SENTINEL_BYPASS when ledger checksum is `'manual_apply'` or NULL.
    - DUAL_LEDGER_SPLIT_BRAIN when migration exists in one tracking table and not the other.
    - DUAL_LEDGER_CHECKSUM_MISMATCH when `_schema_versions.checksum != schema_migrations.checksum`.
    """
    version = int(disk_entry["num"])
    full_sha256 = str(disk_entry["full_sha256"])
    forward_sha256 = str(disk_entry["forward_sha256"])

    anomalies: list[str] = []
    in_sv = schema_versions_row is not None
    in_sm = schema_migrations_row is not None

    if not in_sv and not in_sm:
        return {
            "version": version,
            "status": "UNKNOWN",
            "anomalies": ["UNAPPLIED_IN_BOTH_LEDGERS"],
            "matches_full_sha256": False,
            "matches_forward_sha256": False,
        }

    if in_sv != in_sm:
        anomalies.append("DUAL_LEDGER_SPLIT_BRAIN")

    sv_checksum = (schema_versions_row or {}).get("checksum")
    sm_checksum = (schema_migrations_row or {}).get("checksum")

    for ledger_name, ck in (
        ("_schema_versions", sv_checksum if in_sv else None),
        ("schema_migrations", sm_checksum if in_sm else None),
    ):
        if (ledger_name == "_schema_versions" and not in_sv) or (
            ledger_name == "schema_migrations" and not in_sm
        ):
            continue
        if ck is None or ck == "manual_apply":
            if "MANUAL_APPLY_SENTINEL_BYPASS" not in anomalies:
                anomalies.append("MANUAL_APPLY_SENTINEL_BYPASS")
        elif ck != full_sha256:
            if ck == forward_sha256 and forward_sha256 != full_sha256:
                if "FORWARD_VS_FULL_HASH_MISMATCH" not in anomalies:
                    anomalies.append("FORWARD_VS_FULL_HASH_MISMATCH")
                if "CHECKSUM_DRIFT_FILE_VS_LEDGER" not in anomalies:
                    anomalies.append("CHECKSUM_DRIFT_FILE_VS_LEDGER")
            else:
                if "CHECKSUM_DRIFT_FILE_VS_LEDGER" not in anomalies:
                    anomalies.append("CHECKSUM_DRIFT_FILE_VS_LEDGER")

    if in_sv and in_sm and sv_checksum != sm_checksum:
        anomalies.append("DUAL_LEDGER_CHECKSUM_MISMATCH")

    status = "CONFLICT" if anomalies else "EVIDENCED"
    active_checksums = [
        c for c in (sv_checksum if in_sv else None, sm_checksum if in_sm else None) if c
    ]
    return {
        "version": version,
        "status": status,
        "anomalies": anomalies,
        "matches_full_sha256": bool(active_checksums)
        and all(c == full_sha256 for c in active_checksums),
        "matches_forward_sha256": bool(active_checksums)
        and all(c == forward_sha256 for c in active_checksums),
    }


def load_dr01_manifest(dr01_path: Path) -> dict[str, Any]:
    """Load the Dux-executed DR-B07-01 on-disk migration SHA-256 manifest."""
    manifest = json.loads(dr01_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or set(manifest) != {"migrations_v2", "py_migrations"}:
        raise ValueError("DR01 requires actual migrations_v2 and py_migrations arrays")
    for key, hash_keys in (("migrations_v2", ("full_sha256", "forward_sha256")), ("py_migrations", ("sha256",))):
        rows = manifest[key]
        if not isinstance(rows, list) or not rows:
            raise ValueError("DR01 manifest arrays must be nonempty")
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("file"), str):
                raise ValueError("DR01 row requires filename")
            if row["file"] in seen:
                raise ValueError("DR01 duplicate filename")
            seen.add(row["file"])
            if key == "migrations_v2" and not re.match(r"^\d+_", row["file"]):
                raise ValueError("SQL migration filename requires numeric prefix")
            for hash_key in hash_keys:
                if not re.fullmatch(r"[0-9a-f]{64}", str(row.get(hash_key, ""))):
                    raise ValueError("DR01 row requires SHA256")
    return manifest


def parse_dr05_pro_kv(dr05_pro_path: Path) -> dict[str, str]:
    """Parse key=value lines from DR-B07-05.pro.out."""
    result: dict[str, str] = {}
    for raw_line in dr05_pro_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("host="):
            for token in line.split():
                if "=" in token:
                    key, val = token.split("=", 1)
                    result[key] = val
        elif line == "~/nuzantara DIRECTORY":
            result["home_nuzantara_exists"] = "DIRECTORY"
        elif line.startswith("~/Desktop/nuzantara SYMLINK -> "):
            result["desktop_nuzantara_exists"] = line.split(" ", 1)[1]
        elif "=" in line:
            key, val = line.split("=", 1)
            result[key.strip()] = val.strip()
    return result


def build_b07_operation_instances(
    repo_root: Path, *, consumer_matrix_path: Path | None = None,
    dr05_pro_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Build instances from explicit inputs; defaults retain admitted real-input behavior."""
    csv_path = consumer_matrix_path if consumer_matrix_path is not None else (
        repo_root / ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    )
    if dr05_pro_path is None:
        dr05_pro_path = (
            repo_root / "research/operations/udb-wave8/B07/dux-requests/DR-B07-05.pro.out"
        )
    dr05_pro_sha256 = sha256_file(dr05_pro_path)

    valid_cids, _ = load_consumer_matrix_index(csv_path)

    specs: list[dict[str, Any]] = [
        # D11 — Migration Runners & Schema Audit
        {
            "consumer_id": "src_e98bb23501189d64",
            "x_research_line": "D11",
            "x_entry_point": ".github/workflows/fly-deploy.yml",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(
                repo_root / ".github/workflows/fly-deploy.yml"
            ),
            "status": "PARTIAL",
            "unknowns": ['OPERATION_ID_PENDING_B05', 'STATIC_SOURCE_ONLY', 'CI_RUNTIME_RESULT_UNOBSERVED'],
            "principal_val": "github_actions:deploy_workflow_ssh",
            "principal_ref": '.github/workflows/fly-deploy.yml:142-165;283-306',
            "tx_val": 'pre-deploy and post-deploy jobs invoke migration CLI over flyctl SSH',
            "effects_val": 'workflow invokes backend.db.migrate apply-all before deploy and SQL v2 migrations after deploy',
            "idempotency_val": 'migration idempotency delegated to invoked CLI; workflow result not observed',
            "failure_val": 'run-migrations has no continue-on-error; deploy needs run-migrations; unrelated lint step is non-blocking',
            "retention_val": "N/A",
            "recovery_val": 'rerun behavior and fresh-image selection require actual CI observation',
        },
        {
            "consumer_id": "src_c8f206461cd9bf69",
            "x_research_line": "D11",
            "x_entry_point": "apps/backend-rag/backend/db/migrate.py",
            "evidence_timestamp": DR01_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(repo_root / 'apps/backend-rag/backend/db/migrate.py'),
            "status": "PARTIAL",
            "unknowns": ['OPERATION_ID_PENDING_B05', 'STATIC_SOURCE_ONLY', 'LIVE_LEDGER_RECONCILIATION_BLOCKED_PENDING_BOOLEAN_PROBE_ADMISSION', 'RUNTIME_ROLE_UNOBSERVED', 'CHECKSUM_FORMAT_CONFLICT_NOT_ESTABLISHED'],
            "principal_val": "env:DATABASE_URL_ADMIN_FALLBACK_DATABASE_URL",
            "principal_ref": "apps/backend-rag/backend/db/migrate.py:60-78",
            "tx_val": 'delegates to MigrationManager.apply_all_pending; no inline full-file checksum computation',
            "effects_val": 'delegates pending SQL migration execution and ledger writes to MigrationManager',
            "idempotency_val": 'delegates applied-migration-number skip check to MigrationManager',
            "failure_val": 'lock-busy result may contain empty failed list; CLI treats len(failed)==0 as success',
            "retention_val": 'migration ledger writes delegated; live retention not measured',
            "recovery_val": 'manual migration or restore reconciliation remains unverified',
        },
        {
            "consumer_id": "src_058ad32e4ad2e6a8",
            "x_research_line": "D11",
            "x_entry_point": "apps/backend-rag/backend/db/migration_manager.py",
            "evidence_timestamp": DR01_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(repo_root / 'apps/backend-rag/backend/db/migration_manager.py'),
            "status": "PARTIAL",
            "unknowns": ['OPERATION_ID_PENDING_B05', 'STATIC_SOURCE_ONLY', 'LIVE_LEDGER_RECONCILIATION_BLOCKED_PENDING_BOOLEAN_PROBE_ADMISSION', 'RUNTIME_ROLE_UNOBSERVED'],
            "principal_val": "env:DATABASE_URL",
            "principal_ref": "apps/backend-rag/backend/db/migration_manager.py:501-600",
            "tx_val": 'session advisory lock 73491 around apply_all_pending; migration execution delegated',
            "effects_val": 'discovers SQL files in migrations_v2 and applies pending migration numbers',
            "idempotency_val": 'skips migration_number values returned by get_applied_migrations',
            "failure_val": 'lock-busy refusal returns empty applied/skipped/failed lists; caller can report success',
            "retention_val": 'ledger records written; no live retention observation',
            "recovery_val": 'rollback lineage and dual-ledger state require admitted reconciliation',
        },
        {
            "consumer_id": "src_7d02a5740175b765",
            "x_research_line": "D11",
            "x_entry_point": "apps/backend-rag/backend/db/migration_base.py",
            "evidence_timestamp": DR01_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(repo_root / 'apps/backend-rag/backend/db/migration_base.py'),
            "status": 'PARTIAL',
            "unknowns": ['OPERATION_ID_PENDING_B05', 'STATIC_SOURCE_ONLY', 'LIVE_LEDGER_RECONCILIATION_BLOCKED_PENDING_BOOLEAN_PROBE_ADMISSION', 'CHECKSUM_FORMAT_CONFLICT_NOT_ESTABLISHED'],
            "principal_val": "caller_supplied_asyncpg_connection",
            "principal_ref": "apps/backend-rag/backend/db/migration_base.py:832-834;921-960;1045-1129",
            "tx_val": 'run_with_lock_retry wraps forward SQL execution and dual-ledger logging',
            "effects_val": 'logs checksum of complete sql argument to schema_migrations and _schema_versions',
            "idempotency_val": 'reads complete UTF8 SQL file, passes sql to _log_migration, and hashes that argument; executes parsed forward SQL separately',
            "failure_val": 'migration errors are raised; no CLI-vs-base checksum format conflict established',
            "retention_val": 'ledger writes have no TTL in reviewed logging method',
            "recovery_val": 'rollback SQL stored separately; live recovery unverified',
        },
        {
            "consumer_id": "src_697f237385fbe9eb",
            "x_research_line": "D11",
            "x_entry_point": "apps/backend-rag/backend/db/schema_audit.py",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(
                repo_root / "apps/backend-rag/backend/db/schema_audit.py"
            ),
            "status": "PARTIAL",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "LIVE_EXECUTION_OUTPUT_NOT_PINNED",
            ],
            "principal_val": "env:DATABASE_URL",
            "principal_ref": "apps/backend-rag/backend/db/schema_audit.py:540-575",
            "tx_val": "read_only_catalog_queries",
            "effects_val": "SELECT against information_schema, pg_catalog, _schema_versions, schema_migrations",
            "idempotency_val": "read-only deterministic audit",
            "failure_val": "returns non-zero exit code on schema drift",
            "retention_val": "stateless stdout/JSON report",
            "recovery_val": "N/A (read-only)",
        },
        # D13 — Olympus Guardian / Pulse / Heartbeat / Rules / Insights / Safety
        {
            "consumer_id": "src_fcca1b3652b56e72",
            "x_research_line": "D13",
            "x_entry_point": "apps/backend-rag/backend/services/olympus/guardian.py",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(
                repo_root / "apps/backend-rag/backend/services/olympus/guardian.py"
            ),
            "status": 'PARTIAL',
            "unknowns": ['OPERATION_ID_PENDING_B05', 'STATIC_SOURCE_ONLY', 'TASK_CANCELLATION_CLEANUP_UNOBSERVED'],
            "principal_val": "app.state.db_pool (runtime role)",
            "principal_ref": "apps/backend-rag/backend/services/olympus/guardian.py:32-145",
            "tx_val": "autocommit pool.execute / pool.fetch per maintenance action",
            "effects_val": "DDL CREATE TABLE partition, DELETE retention rows, ANALYZE, pg_terminate_backend, SET/RESET SYSTEM, INSERT olympus_actions",
            "idempotency_val": "IF NOT EXISTS on partition creation; non-atomic audit logging",
            "failure_val": 'stop sets _running=False, cancels tasks and clears task list without awaiting their completion; cleanup outcome unobserved',
            "retention_val": "deletes old rows per olympus_rules config; olympus_actions unbounded",
            "recovery_val": "pool_recycle / reset_config fallback",
        },
        {
            "consumer_id": "src_5726ef98e1124f67",
            "x_research_line": "D13",
            "x_entry_point": "apps/backend-rag/backend/services/olympus/pulse.py",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(
                repo_root / "apps/backend-rag/backend/services/olympus/pulse.py"
            ),
            "status": "CONFLICT",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "CE_04_NON_ATOMIC_MAINTENANCE_AND_AUDIT_WRITE",
            ],
            "principal_val": "app.state.db_pool (runtime role)",
            "principal_ref": "apps/backend-rag/backend/services/olympus/pulse.py:55-625",
            "tx_val": "separate autocommit statements for maintenance DDL/DML and olympus_actions INSERT",
            "effects_val": "bloat/index/vacuum/retention/partition maintenance + INSERT olympus_actions",
            "idempotency_val": "cooldown-gated in memory; lost on process restart",
            "failure_val": "CE-04: maintenance effect can succeed while audit INSERT fails (or vice versa)",
            "retention_val": "prunes api_audit_trail / persistent_sessions / olympus_heartbeats",
            "recovery_val": "next pulse tick retries after cooldown",
        },
        {
            "consumer_id": "src_e20ebbdb6f795a47",
            "x_research_line": "D13",
            "x_entry_point": "apps/backend-rag/backend/services/olympus/heartbeat.py",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(
                repo_root / "apps/backend-rag/backend/services/olympus/heartbeat.py"
            ),
            "status": "PARTIAL",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "LIVE_PARTITION_STATE_PENDING_BOOLEAN_PROBE",
            ],
            "principal_val": "app.state.db_pool (runtime role)",
            "principal_ref": "apps/backend-rag/backend/services/olympus/heartbeat.py:155-245",
            "tx_val": "autocommit INSERT into olympus_heartbeats and CREATE TABLE partition",
            "effects_val": "INSERT olympus_heartbeats; DDL CREATE TABLE olympus_heartbeats_yYYYYmMM PARTITION OF olympus_heartbeats",
            "idempotency_val": "CREATE TABLE IF NOT EXISTS for monthly partitions",
            "failure_val": "falls back to olympus_heartbeats_default partition if monthly partition missing",
            "retention_val": "prune_old_heartbeats deletes rows older than retention threshold",
            "recovery_val": "ensure_next_month_partition self-heals on pulse",
        },
        {
            "consumer_id": "src_d272bb6bdef03fbe",
            "x_research_line": "D13",
            "x_entry_point": "apps/backend-rag/backend/services/olympus/insights.py",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(
                repo_root / "apps/backend-rag/backend/services/olympus/insights.py"
            ),
            "status": "PARTIAL",
            "unknowns": ["OPERATION_ID_PENDING_B05", "STATIC_SOURCE_ONLY"],
            "principal_val": "app.state.db_pool (runtime role)",
            "principal_ref": "apps/backend-rag/backend/services/olympus/insights.py:28-160",
            "tx_val": "autocommit INSERT/SELECT on olympus_insights",
            "effects_val": "INSERT/SELECT public.olympus_insights",
            "idempotency_val": "append-only insight log",
            "failure_val": "logs warning and continues",
            "retention_val": "unbounded unless pruned by guardian",
            "recovery_val": "stateless re-computation on next pulse",
        },
        {
            "consumer_id": "src_37fd824491703880",
            "x_research_line": "D13",
            "x_entry_point": "apps/backend-rag/backend/services/olympus/rules_engine.py",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(
                repo_root / "apps/backend-rag/backend/services/olympus/rules_engine.py"
            ),
            "status": "PARTIAL",
            "unknowns": ["OPERATION_ID_PENDING_B05", "STATIC_SOURCE_ONLY"],
            "principal_val": "app.state.db_pool (runtime role)",
            "principal_ref": "apps/backend-rag/backend/services/olympus/rules_engine.py:23-60",
            "tx_val": "autocommit SELECT/UPDATE on olympus_rules",
            "effects_val": "SELECT/UPDATE public.olympus_rules",
            "idempotency_val": "rule lookup cached with fallback defaults",
            "failure_val": "falls back to hardcoded default thresholds on query error",
            "retention_val": "configuration table (seeded by migrations 074 and 233)",
            "recovery_val": "fallback defaults in code",
        },
        {
            "consumer_id": "src_4104f553c1186e0c",
            "x_research_line": "D13",
            "x_entry_point": "apps/backend-rag/backend/services/olympus/safety.py",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(
                repo_root / "apps/backend-rag/backend/services/olympus/safety.py"
            ),
            "status": "CONFLICT",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "CE_03_PROCESS_LOCAL_RATE_LIMIT_SHARED_ACROSS_CALLERS",
            ],
            "principal_val": "in_memory_process_local",
            "principal_ref": "apps/backend-rag/backend/services/olympus/safety.py:10-45",
            "tx_val": "in-memory dict/list state only (not persisted in PG)",
            "effects_val": "gates Olympus maintenance actions via in-memory blast-radius counters",
            "idempotency_val": "CE-03: reset on process restart; not coordinated across multiple machines/workers",
            "failure_val": "blocks maintenance action in-memory when threshold exceeded",
            "retention_val": "ephemeral process memory",
            "recovery_val": "process restart clears all safety history",
        },
        # D02 — Retention, Pruning, and Restore Drill Lineage
        {
            "consumer_id": "src_05d88b7c837c1309",
            "x_research_line": "D02",
            "x_entry_point": "scripts/outbox-prune.sh",
            "evidence_timestamp": DR05_PRO_EVIDENCE_TIMESTAMP,
            "evidence_sha256": dr05_pro_sha256,
            "status": 'PARTIAL',
            "unknowns": ['OPERATION_ID_PENDING_B05', 'STATIC_SOURCE_ONLY', 'PRO_LAUNCHAGENT_PLIST_COUNT_2_OBSERVED_IN_DR05_PRO', 'LIVE_PRUNE_NOT_EXECUTED'],
            "principal_val": 'DATABASE_URL connection in shell-invoked Python; live role unobserved',
            "principal_ref": 'scripts/outbox-prune.sh:75-85; apps/backend-rag/backend/services/events/outbox.py:422-442',
            "tx_val": 'single prune_consumed DELETE via asyncpg connection',
            "effects_val": 'DELETE events_outbox WHERE consumed_at IS NOT NULL AND consumed_at is older than configured days; no dead_letter predicate',
            "idempotency_val": 'repeated predicate delete removes only remaining eligible consumed rows',
            "failure_val": 'prune_consumed error propagates through shell-invoked Python',
            "retention_val": 'OUTBOX_PRUNE_DAYS defaults to30; prune_consumed default older_than_days=30',
            "recovery_val": 'deleted data requires separate backup recovery proof',
        },
        {
            "consumer_id": "src_9ad4d21e806efece",
            "x_research_line": "D02",
            "x_entry_point": "scripts/outbox_prune.py",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(repo_root / "scripts/outbox_prune.py"),
            "status": "PARTIAL",
            "unknowns": ["OPERATION_ID_PENDING_B05", "STATIC_SOURCE_ONLY"],
            "principal_val": "env:DATABASE_URL",
            "principal_ref": "scripts/outbox_prune.py:24-96",
            "tx_val": "asyncpg connection execute",
            "effects_val": "prunes delivered/expired rows in events_outbox",
            "idempotency_val": "idempotent timestamp-bounded DELETE",
            "failure_val": "raises exception and exits nonzero",
            "retention_val": "configurable retention window",
            "recovery_val": "PG backup restore only",
        },
        {
            "consumer_id": "src_6e1c7398dbc460bf",
            "x_research_line": "D02",
            "x_entry_point": "apps/backend-rag/backend/scripts/visa_engine/retention_worker.py",
            "evidence_timestamp": DR05_PRO_EVIDENCE_TIMESTAMP,
            "evidence_sha256": dr05_pro_sha256,
            "status": "PARTIAL",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "ZERO_SCHEDULER_REFS_ON_PRO_IN_DR05_PRO_MINI_WRAPPER_REGISTERED",
            ],
            "principal_val": "mini_launchd:com.nuzantara.visa-oracle-retention.15min",
            "principal_ref": "apps/backend-rag/backend/scripts/visa_engine/retention_worker.py:83-354",
            "tx_val": "SECURITY DEFINER RPC calls inside explicit transaction",
            "effects_val": "executes visa_decision_retention_policies erasure/retention batches and records batch evidence",
            "idempotency_val": "batch ledger + legal hold guard prevents double erasure",
            "failure_val": "rolls back transaction and exits nonzero",
            "retention_val": "policy-driven per visa_decision_retention_policies (e.g. 30d/90d)",
            "recovery_val": "immutable retention batch audit log in visa_decision_retention_batches",
        },
        {
            "consumer_id": "src_66593fdb65bc402e",
            "x_research_line": "D02",
            "x_entry_point": "apps/backend-rag/backend/services/visa_engine/retention.py",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(
                repo_root / "apps/backend-rag/backend/services/visa_engine/retention.py"
            ),
            "status": "EVIDENCED",
            "unknowns": ["OPERATION_ID_PENDING_B05", "STATIC_SOURCE_ONLY"],
            "principal_val": "visa_retention_worker_role (SECURITY DEFINER binder)",
            "principal_ref": "apps/backend-rag/backend/services/visa_engine/retention.py:53-253",
            "tx_val": "transactional batch execution with legal-hold exclusion",
            "effects_val": "DELETE/UPDATE on visa_decisions, visa_decision_payloads, visa_evaluate_idempotency, garuda_voa_checks + INSERT batch ledgers",
            "idempotency_val": "idempotent bounded batch execution with audit receipt",
            "failure_val": "raises error and aborts batch transaction",
            "retention_val": "enforces public.visa_decision_retention_policies",
            "recovery_val": "legal hold events in visa_decision_legal_hold_events block erasure",
        },
        {
            "consumer_id": "src_def7a4c288a552af",
            "x_research_line": "D02",
            "x_entry_point": "scripts/pg-restore-drill.sh",
            "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
            "evidence_sha256": sha256_file(csv_path),
            "status": 'BLOCKED',
            "unknowns": ['OPERATION_ID_PENDING_B05', 'HISTORICAL_SOURCE_UNAVAILABLE_AT_FROZEN_BASE', 'SUCCESSOR_LINEAGE_UNPROVEN', 'HISTORICAL_STORE_BINDING_UNOBSERVED'],
            "principal_val": 'UNKNOWN',
            "principal_ref": '.agent-receipts/udb-wave8-inputs/consumer-matrix.csv',
            "tx_val": 'UNKNOWN',
            "effects_val": 'UNKNOWN',
            "idempotency_val": 'UNKNOWN',
            "failure_val": 'UNKNOWN',
            "retention_val": 'UNKNOWN',
            "recovery_val": 'UNKNOWN',
        },
    ]

    instances: list[dict[str, Any]] = []
    for spec in specs:
        ref = spec["principal_ref"]
        st = spec["status"]
        record: dict[str, Any] = {
            "consumer_id": spec["consumer_id"],
            "operation_id": UNASSIGNED_OPERATION_ID,
            "store_id": CANONICAL_PG_STORE_ID,
            "source_version": BASE_SOURCE_VERSION,
            "evidence_timestamp": spec["evidence_timestamp"],
            "evidence_sha256": spec["evidence_sha256"],
            "status": st,
            "unknowns": list(spec["unknowns"]),
            "principal": make_field(spec["principal_val"], "EVIDENCED", ref),
            "role": make_field(
                "postgres_admin_or_runtime_pool",
                "PARTIAL",
                ref,
            ),
            "tenant": make_field("single_tenant_balizero", "EVIDENCED", ref),
            "authorization": make_field(
                "connection_role_grants_and_security_definer",
                "PARTIAL",
                ref,
            ),
            "transaction": make_field(spec["tx_val"], "EVIDENCED", ref),
            "effects": make_field(spec["effects_val"], "EVIDENCED", ref),
            "retries": make_field("none_in_sql_layer", "EVIDENCED", ref),
            "idempotency": make_field(
                spec["idempotency_val"],
                "CONFLICT" if st == "CONFLICT" else "EVIDENCED",
                ref,
            ),
            "failure": make_field(
                spec["failure_val"],
                "CONFLICT" if st == "CONFLICT" else "EVIDENCED",
                ref,
            ),
            "retention": make_field(spec["retention_val"], "EVIDENCED", ref),
            "recovery": make_field(spec["recovery_val"], "PARTIAL", ref),
            "x_research_line": spec["x_research_line"],
            "x_entry_point": spec["x_entry_point"],
        }
        # Static source describes configured code, not a live role or tenant binding.
        for field in ("role", "tenant", "authorization"):
            record[field] = make_field("UNKNOWN", "UNKNOWN", ref)
        record["principal"]["status"] = "PARTIAL"
        record["unknowns"].extend([
            "RUNTIME_PRINCIPAL_ROLE_TENANT_BINDING_UNOBSERVED",
            "CANONICAL_STORE_ID_IS_LOGICAL_TARGET_NOT_LIVE_BINDING",
        ])
        if spec["consumer_id"] == "src_def7a4c288a552af":
            record["x_historical_source_available"] = False
            record["x_successor_lineage_status"] = "UNPROVEN"
            for field in INSTANCE_11_KEYS:
                record[field] = make_field("UNKNOWN", "UNKNOWN", ref)
        validate_operation_instance(record, valid_cids)
        instances.append(record)

    return instances
