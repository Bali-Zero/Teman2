#!/usr/bin/env python3
"""B05 Effective Operation Contracts Validator, AST Verifier, and Artifact Builder.

Pure-Python stdlib implementation conforming to:
  - .agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md (sha256: a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559)
  - .agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md (sha256: 29c57f706bcc0dd8e7f492f3ffe5215598798ed173f452f19aa7a086c8faaf54)
  - .agent-receipts/udb-wave8-dux/DUX-CONSOLIDATION.md (sha256: c39218718f496b643b550abf98ca40bd2755e74d3954caed953005eb5b906e14)

No network, no database driver, no third-party dependencies outside Python stdlib.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

BASE_COMMIT_SHA = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
BASE_COMMIT_TIMESTAMP = "2026-10-15T07:06:22Z"
LEAD_DELTA_CONSUMER_ID = "runtime_mini_46522da0ef79d3aa7422ca41"

APPROVED_TARGET_DATABASE = "nuzantara_rag"
APPROVED_TARGET_SCHEMA = "public"
RELATION_ID_DERIVATION = "md5(database||chr(31)||schema||chr(31)||relation)"
RELATION_ID_DERIVATION_EVIDENCE_REF = (
    "approved-target.json (sha256: 95bb674b7433fbc7198bce7000d044854bf44ec63ecece7fc8726765ef5d9ba7); "
    "contract_metadata.py (sha256: 7b093d621878ae393522920814e685e29ed5e259a22fcca5d32f04af1d1a87a2); "
    "B05-DERIVATION-PROOF.json (sha256: 7bb91413c226a9466f36d1226449eb3086f5a6343f9b8adf9ae4c9dd16f0c4ef); "
    "FORCE-B05-RELATION-JOIN.json (sha256: e4a85ab8de1728059c66ba549fac0833124b9950538070215a0bb831152e37b2)"
)

FROZEN_BASE_FIELDS: tuple[str, ...] = (
    "consumer_id",
    "operation_id",
    "store_id",
    "source_version",
    "evidence_timestamp",
    "evidence_sha256",
    "status",
    "unknowns",
)

INSTANCE_FIELDS: tuple[str, ...] = (
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

REQUIRED_19_KEYS: tuple[str, ...] = FROZEN_BASE_FIELDS + INSTANCE_FIELDS

ALLOWED_STATUSES: tuple[str, ...] = (
    "EVIDENCED",
    "PARTIAL",
    "BLOCKED",
    "CONFLICT",
    "UNKNOWN",
)

ALLOWED_ENGINES: tuple[str, ...] = (
    "pg",
    "qdrant",
    "redis",
    "sqlite",
    "graph",
    "object",
    "file",
    "sheet",
    "browser",
    "external",
)

ALLOWED_PLATFORMS: tuple[str, ...] = (
    "fly",
    "pro",
    "mini",
    "m5",
    "gcloud",
    "gdrive",
    "github",
    "client",
    "unknown",
)

OPERATION_ID_RE = re.compile(r"^op:[a-z0-9-]+:[a-z0-9-]+:[a-z0-9-]+$")
STORE_ID_RE = re.compile(
    r"^(pg|qdrant|redis|sqlite|graph|object|file|sheet|browser|external):"
    r"(fly|pro|mini|m5|gcloud|gdrive|github|client|unknown):"
    r"[a-z0-9._-]+(/[A-Za-z0-9._-]+)?$"
)
EXTENSION_KEY_RE = re.compile(r"^x_[a-z0-9_]+$")
SOURCE_VERSION_RE = re.compile(r"^([0-9a-f]{40}|prior:[0-9a-f]{10,40}|prior:UNKNOWN)$")
ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UNKNOWN_TOKEN_RE = re.compile(r"^[A-Z0-9_]+(:[A-Za-z0-9._:/-]+)?$")
CONSUMER_FAMILY_STRIP_RE = re.compile(r"[-_]?[0-9a-f]{12,24}$")

# Pinned SHA-256 digests from DUX-B05-01..04 and pinned inputs
PINNED_SHA256: dict[str, str] = {
    "DUX-B05-01.out": "7454582231aaebbc6460c7839e26c3e3e948fc34ca611ecfd33df7dd77c72e25",
    "DUX-B05-02.out": "e6d1f2fc0feda8f6fe3a8b36259dec7b2bce548c60569e1dadb7303109ae707c",
    "DUX-B05-04.out": "3ba2c4c9b5065e2f36673256c3992fd3dcbc36276fa03c7f364ba10b56e641a2",
    "conversation_repository.py": "c3a9c44b8f97b4ef2155194d440feb2f1a23216057eba94eb91d51e988dd15fe",
    "retention_policy.py": "4250d14a07a16dc14f3e325369faec611c7f8c5424a09733c5363c533a4dcb1a",
    "279_research_os_contract_core.sql": "f58500d2793336d6adff1faa9ace21a336699e15c759c96663ecb3a675cdb1c0",
    "284_garuda_orders.sql": "d4438d4cca052e691f60292e045f0da2f1152c2c82d5e314e9ce474020822d34",
    "restore_drill_verify.py": "3fe0dfc48e5f4e3e2000b0813b59d60a8500503f68c89596e4b09a0b91dad856",
    "LEAD-DELTA.json": "91e6bac9c91181a2b3aa3f6cd1dc6585671c18ce90cb887444229a1a17a084e7",
    "LIVE-DB-METADATA.json": "2bb691c347efd556eb106877e4a84b5c566f765edaa597a1c12ca73820dd56e6",
    "SYNTHETIC-PG-RESULT.json": "38f9500820971b08cb6bbe2ada8251294f436905db96f49d59de547ce60aaa81",
    "POOL-FACTORY-SOURCE.json": "d93668cbd3bbc1e40352a333e3fd28ffa192909e4de7b9cc0f12dbfa9fb044b8",
}

PINNED_RELPATHS: dict[str, str] = {
    "DUX-B05-01.out": "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out",
    "DUX-B05-02.out": "research/operations/udb-wave8/B05/dux-requests/DUX-B05-02.out",
    "DUX-B05-04.out": "research/operations/udb-wave8/B05/dux-requests/DUX-B05-04.out",
    "conversation_repository.py": "apps/backend-rag/backend/db/repositories/conversation_repository.py",
    "retention_policy.py": "apps/backend-rag/backend/core/retention_policy.py",
    "279_research_os_contract_core.sql": "apps/backend-rag/backend/db/migrations_v2/279_research_os_contract_core.sql",
    "284_garuda_orders.sql": "apps/backend-rag/backend/db/migrations_v2/284_garuda_orders.sql",
    "restore_drill_verify.py": "scripts/ci/restore_drill_verify.py",
    "LEAD-DELTA.json": ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json",
    "LIVE-DB-METADATA.json": ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json",
    "SYNTHETIC-PG-RESULT.json": ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/SYNTHETIC-PG-RESULT.json",
    "POOL-FACTORY-SOURCE.json": ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json",
}


def compute_census(csv_path: Path) -> list[dict[str, Any]]:
    """Compute deterministic (family, contract_coverage_status, disposition) census buckets from CSV."""
    counts: dict[tuple[str, str, str], int] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row["consumer_id"]
            fam = CONSUMER_FAMILY_STRIP_RE.sub("", cid)
            cov = (row.get("contract_coverage_status") or "").strip() or "EMPTY"
            disp = (row.get("disposition") or "").strip() or "EMPTY"
            key = (fam, cov, disp)
            counts[key] = counts.get(key, 0) + 1

    sorted_items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1], kv[0][2]))
    return [
        {
            "family": fam,
            "contract_coverage_status": cov,
            "disposition": disp,
            "count": count,
        }
        for (fam, cov, disp), count in sorted_items
    ]


def load_valid_consumer_ids(repo_root: Path) -> set[str]:
    """Return the set of valid consumer_ids from consumer-matrix.csv plus LEAD-DELTA.json additions."""
    csv_path = repo_root / ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    lead_delta_path = (
        repo_root
        / ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json"
    )
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        ids = {row["consumer_id"] for row in csv.DictReader(f)}
    lead_delta = json.loads(lead_delta_path.read_text(encoding="utf-8"))
    for item in lead_delta.get("additions", []):
        if "consumer_id" in item:
            ids.add(item["consumer_id"])
    return ids


def verify_pinned_sha256(repo_root: Path) -> list[str]:
    """Verify every digest in PINNED_SHA256 against the on-disk file under repo_root."""
    errors: list[str] = []
    for label, expected_sha in PINNED_SHA256.items():
        rel_path = PINNED_RELPATHS[label]
        fpath = repo_root / rel_path
        if not fpath.is_file():
            errors.append(f"Missing pinned file for '{label}' at {rel_path}")
            continue
        actual_sha = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            errors.append(
                f"SHA-256 mismatch for '{label}' ({rel_path}): expected {expected_sha}, got {actual_sha}"
            )
    return errors


def make_field(value: Any, status: str, evidence_ref: str | None) -> dict[str, Any]:
    """Construct a canonical 3-key instance field object."""
    return {
        "value": value,
        "status": status,
        "evidence_ref": evidence_ref,
    }


def validate_operation_instance(
    record: dict[str, Any],
    valid_consumer_ids: set[str] | None = None,
) -> list[str]:
    """Validate a single operation contract instance against CONTRACT-CONVENTIONS.md.

    Returns a list of validation error strings (empty list means valid).
    """
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["Record must be a JSON object / dict."]

    # 1. Check required 19 keys
    missing_keys = [k for k in REQUIRED_19_KEYS if k not in record]
    if missing_keys:
        errors.append(f"Missing required keys: {missing_keys}")

    # 2. Check extra keys: must be prefixed with `x_`
    for key in record:
        if key not in REQUIRED_19_KEYS and not EXTENSION_KEY_RE.match(key):
            errors.append(
                f"Illegal unprefixed extra key '{key}': sibling extensions must match ^x_[a-z0-9_]+$"
            )

    if missing_keys:
        return errors

    # 3. Validate 8 frozen base fields
    consumer_id = record["consumer_id"]
    if not isinstance(consumer_id, str) or not consumer_id.strip():
        errors.append("consumer_id must be a non-empty string.")
    elif "." in consumer_id:
        errors.append(
            f"consumer_id '{consumer_id}' contains '.' (human alias forbidden; use verbatim consumer_id)."
        )
    elif valid_consumer_ids is not None and consumer_id not in valid_consumer_ids:
        errors.append(
            f"consumer_id '{consumer_id}' not found in consumer-matrix.csv or LEAD-DELTA.json."
        )

    unknowns = record["unknowns"]
    if not isinstance(unknowns, list) or not all(isinstance(u, str) for u in unknowns):
        errors.append("unknowns must be a list of strings.")
        unknowns_list: list[str] = []
    else:
        unknowns_list = unknowns
        for token in unknowns_list:
            if not UNKNOWN_TOKEN_RE.match(token):
                errors.append(
                    f"Invalid unknowns token '{token}': must be UPPER_SNAKE (or UPPER_SNAKE:payload)."
                )

    operation_id = record["operation_id"]
    if not isinstance(operation_id, str):
        errors.append("operation_id must be a string.")
    elif operation_id == "UNASSIGNED_B05":
        if "OPERATION_ID_PENDING_B05" not in unknowns_list:
            errors.append(
                "operation_id 'UNASSIGNED_B05' requires 'OPERATION_ID_PENDING_B05' in unknowns."
            )
    elif not OPERATION_ID_RE.match(operation_id):
        errors.append(
            f"operation_id '{operation_id}' violates grammar ^op:<domain>:<verb>:<object>$."
        )

    store_id = record["store_id"]
    if not isinstance(store_id, str):
        errors.append("store_id must be a string.")
    elif store_id == "unknown:unknown:unknown":
        has_store_unknown = any(u.startswith("STORE_ID_PROPOSED:") for u in unknowns_list)
        if not has_store_unknown:
            errors.append(
                "store_id 'unknown:unknown:unknown' requires STORE_ID_PROPOSED:<val> in unknowns."
            )
    elif not STORE_ID_RE.match(store_id):
        errors.append(
            f"store_id '{store_id}' violates grammar <engine>:<platform>:<lower-case-instance>[/<subcontainer>]."
        )

    source_version = record["source_version"]
    if not isinstance(source_version, str) or not SOURCE_VERSION_RE.match(source_version):
        errors.append(
            f"source_version '{source_version}' must be 40-hex commit SHA, prior:<sha>, or prior:UNKNOWN."
        )

    evidence_timestamp = record["evidence_timestamp"]
    if not isinstance(evidence_timestamp, str) or not ISO_UTC_RE.match(evidence_timestamp):
        errors.append(
            f"evidence_timestamp '{evidence_timestamp}' must be ISO-8601 UTC ending in Z."
        )
    elif (
        source_version == BASE_COMMIT_SHA
        and evidence_timestamp == BASE_COMMIT_TIMESTAMP
        and record.get("status") != "EVIDENCED"
        and "STATIC_SOURCE_ONLY" not in unknowns_list
    ):
        errors.append(
            "Static repo source using base commit timestamp must include 'STATIC_SOURCE_ONLY' in unknowns."
        )

    evidence_sha256 = record["evidence_sha256"]
    if not isinstance(evidence_sha256, str) or not SHA256_RE.match(evidence_sha256):
        errors.append(
            f"evidence_sha256 '{evidence_sha256}' must be a 64-character lowercase hex SHA-256."
        )

    status = record["status"]
    if status not in ALLOWED_STATUSES:
        errors.append(f"Top-level status '{status}' not in {ALLOWED_STATUSES}.")

    # 4. Validate 11 instance fields
    all_fields_evidenced = True
    for field_name in INSTANCE_FIELDS:
        fobj = record[field_name]
        if not isinstance(fobj, dict):
            errors.append(f"Instance field '{field_name}' must be an object/dict.")
            all_fields_evidenced = False
            continue
        if set(fobj.keys()) != {"value", "status", "evidence_ref"}:
            errors.append(
                f"Instance field '{field_name}' must have exact keys {{'value', 'status', 'evidence_ref'}}, got {set(fobj.keys())}."
            )
            all_fields_evidenced = False
            continue
        f_status = fobj["status"]
        f_val = fobj["value"]
        f_ref = fobj["evidence_ref"]
        if f_status not in ALLOWED_STATUSES:
            errors.append(
                f"Instance field '{field_name}.status'='{f_status}' not in {ALLOWED_STATUSES}."
            )
        if f_status != "EVIDENCED":
            all_fields_evidenced = False
        if f_status == "EVIDENCED":
            if not isinstance(f_ref, str) or not f_ref.strip():
                errors.append(
                    f"Instance field '{field_name}' has status EVIDENCED but missing evidence_ref."
                )
            if f_val is None or f_val == "" or f_val == "UNKNOWN":
                errors.append(
                    f"Instance field '{field_name}' has status EVIDENCED but empty/UNKNOWN value."
                )
        elif f_status == "UNKNOWN":
            if f_ref is not None and (not isinstance(f_ref, str) or not f_ref.strip()):
                errors.append(
                    f"Instance field '{field_name}' with status UNKNOWN must have evidence_ref=null or valid ref string."
                )
        else:
            if not isinstance(f_ref, str) or not f_ref.strip():
                errors.append(
                    f"Instance field '{field_name}' with status {f_status} requires non-empty evidence_ref."
                )

    # 5. Completeness consistency rules (CONTRACT-CONVENTIONS.md §1 & §2.1)
    if status == "EVIDENCED":
        if unknowns_list:
            errors.append(
                f"Record status is EVIDENCED but unknowns is non-empty: {unknowns_list}"
            )
        if not all_fields_evidenced:
            errors.append(
                "Record status is EVIDENCED but not all 11 instance fields have status == 'EVIDENCED'."
            )
    else:
        if not unknowns_list:
            errors.append(
                f"Record status is {status} (not EVIDENCED) but unknowns is empty []."
            )
        if all_fields_evidenced:
            errors.append(
                f"All 11 instance fields are EVIDENCED, so top-level status cannot be {status}."
            )

    return errors


def is_complete_contract(
    record: dict[str, Any],
    valid_consumer_ids: set[str] | None = None,
) -> bool:
    """Return True iff the operation contract instance is valid and COMPLETE (EVIDENCED)."""
    errors = validate_operation_instance(record, valid_consumer_ids=valid_consumer_ids)
    if errors:
        return False
    return (
        record["status"] == "EVIDENCED"
        and record["unknowns"] == []
        and all(record[f]["status"] == "EVIDENCED" for f in INSTANCE_FIELDS)
    )


def instance_to_csv_row(record: dict[str, Any]) -> dict[str, str]:
    """Serialize a 19-key (+ optional x_ extension keys) operation contract instance into a flat CSV row dict."""
    row: dict[str, str] = {
        "consumer_id": str(record["consumer_id"]),
        "operation_id": str(record["operation_id"]),
        "store_id": str(record["store_id"]),
        "source_version": str(record["source_version"]),
        "evidence_timestamp": str(record["evidence_timestamp"]),
        "evidence_sha256": str(record["evidence_sha256"]),
        "status": str(record["status"]),
        "unknowns": ";".join(record["unknowns"]),
    }
    for field_name in INSTANCE_FIELDS:
        row[field_name] = json.dumps(record[field_name], sort_keys=True, separators=(",", ":"))
    for key, val in record.items():
        if key not in REQUIRED_19_KEYS and EXTENSION_KEY_RE.match(key):
            if isinstance(val, (dict, list)):
                row[key] = json.dumps(val, sort_keys=True, separators=(",", ":"))
            elif val is None:
                row[key] = ""
            else:
                row[key] = str(val)
    return row


def csv_row_to_instance(row: dict[str, str]) -> dict[str, Any]:
    """Deserialize a CSV row dict back into an operation contract instance (preserving x_ columns)."""
    unknowns_raw = row.get("unknowns", "").strip()
    unknowns_list = [u for u in unknowns_raw.split(";") if u] if unknowns_raw else []
    record: dict[str, Any] = {
        "consumer_id": row["consumer_id"],
        "operation_id": row["operation_id"],
        "store_id": row["store_id"],
        "source_version": row["source_version"],
        "evidence_timestamp": row["evidence_timestamp"],
        "evidence_sha256": row["evidence_sha256"],
        "status": row["status"],
        "unknowns": unknowns_list,
    }
    for field_name in INSTANCE_FIELDS:
        record[field_name] = json.loads(row[field_name])
    for key, val in row.items():
        if key is not None and key not in REQUIRED_19_KEYS and EXTENSION_KEY_RE.match(key):
            if val != "":
                record[key] = val
    return record


def verify_conversation_repo_ast(repo_root: Path) -> dict[str, Any]:
    """AST-verify conversation_repository.py for the Wave-7 locking/transaction counterexample.

    Wave-7 consumer-matrix.csv:545 (`src_6ad3cb3fa4349521`) claims:
      transaction_boundary = 'One asyncpg transaction per save; two-int advisory session lock; row lock'
      latency_availability = '5 second lock timeout; failure returns None; product SLO UNKNOWN'
      disposition = 'ADAPTED_PARTIAL_VERIFIED'
    On current branch 8061c88e0c43dd42e735fd012f9ed072df3ef3d6:
      - `save_messages` (L32-L136) uses `async with conn.transaction():` (L60), but contains
        NO advisory lock (`pg_advisory_lock` / `pg_advisory_xact_lock`) and NO `FOR UPDATE` row lock.
      - `cleanup_old_conversations` (L183-L236) and `anonymize_user_data` (L243-L290) execute
        DELETE/UPDATE without `conn.transaction()`.
    """
    target = repo_root / "apps/backend-rag/backend/db/repositories/conversation_repository.py"
    source_bytes = target.read_bytes()
    source_text = source_bytes.decode("utf-8")
    sha256_hex = hashlib.sha256(source_bytes).hexdigest()
    tree = ast.parse(source_text, filename=str(target))

    methods: dict[str, dict[str, Any]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
            "save_messages",
            "get_messages",
            "cleanup_old_conversations",
            "anonymize_user_data",
        }:
            has_tx = False
            calls: list[str] = []
            sql_literals: list[str] = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
                    if child.func.attr == "transaction":
                        has_tx = True
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    sql_literals.append(child.value)
            joined_sql = "\n".join(sql_literals).upper()
            methods[node.name] = {
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", None),
                "has_conn_transaction": has_tx,
                "has_advisory_lock": "ADVISORY" in joined_sql,
                "has_for_update_row_lock": "FOR UPDATE" in joined_sql,
                "attribute_calls": sorted(set(calls)),
            }

    save_info = methods.get("save_messages", {})
    return {
        "file": "apps/backend-rag/backend/db/repositories/conversation_repository.py",
        "sha256": sha256_hex,
        "methods": methods,
        "counterexample_proven": bool(
            save_info.get("has_conn_transaction") is True
            and save_info.get("has_advisory_lock") is False
            and save_info.get("has_for_update_row_lock") is False
            and methods.get("anonymize_user_data", {}).get("has_conn_transaction") is False
        ),
    }


def verify_migration_lock_busy_ast(repo_root: Path) -> dict[str, Any]:
    """AST-verify migration_manager.py and migrate.py for the lock-busy exit code counterexample.

    Wave-7 consumer-matrix.csv lines 343 (`src_058ad32e4ad2e6a8`) and 4440 (`src_c8f206461cd9bf69`)
    claim: 'Lock-busy refusal is nonzero; applied numbers skipped' with status ADAPTED_ISOLATED_VERIFIED.
    On base commit 8061c88e0c43dd42e735fd012f9ed072df3ef3d6:
      - migration_manager.py:501 (`apply_all_pending`) at L539-541 returns
        {"applied": [], "skipped": [], "failed": []} when `not locked`
      - migrate.py:77 (`cmd_apply`) returns `len(result["failed"]) == 0` (True when `failed` is empty)
      - migrate.py:170 (`main`) executes `sys.exit(0 if success is not False else 1)` (exiting 0).
    """
    mm_path = repo_root / "apps/backend-rag/backend/db/migration_manager.py"
    m_path = repo_root / "apps/backend-rag/backend/db/migrate.py"

    mm_bytes = mm_path.read_bytes()
    m_bytes = m_path.read_bytes()

    mm_tree = ast.parse(mm_bytes.decode("utf-8"), filename=str(mm_path))
    m_tree = ast.parse(m_bytes.decode("utf-8"), filename=str(m_path))

    apply_all_pending_lineno: int | None = None
    not_locked_return: dict[str, Any] | None = None
    for node in ast.walk(mm_tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "apply_all_pending":
            apply_all_pending_lineno = node.lineno
            for child in ast.walk(node):
                if isinstance(child, ast.If):
                    test = child.test
                    if (
                        isinstance(test, ast.UnaryOp)
                        and isinstance(test.op, ast.Not)
                        and isinstance(test.operand, ast.Name)
                        and test.operand.id == "locked"
                    ):
                        for stmt in child.body:
                            if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                                keys = [
                                    k.value for k in stmt.value.keys if isinstance(k, ast.Constant)
                                ]
                                empty_lists = all(
                                    isinstance(v, ast.List) and len(v.elts) == 0
                                    for v in stmt.value.values
                                )
                                not_locked_return = {
                                    "if_not_locked_lineno": child.lineno,
                                    "lineno": stmt.lineno,
                                    "keys": keys,
                                    "all_lists_empty": empty_lists,
                                }

    cmd_apply_return_len_failed_eq_zero = False
    cmd_apply_lineno: int | None = None
    main_sys_exit_zero_when_not_false = False
    main_sys_exit_lineno: int | None = None

    for node in ast.walk(m_tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "cmd_apply":
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Compare):
                    cmp = child.value
                    if (
                        isinstance(cmp.left, ast.Call)
                        and isinstance(cmp.left.func, ast.Name)
                        and cmp.left.func.id == "len"
                        and len(cmp.left.args) == 1
                        and isinstance(cmp.left.args[0], ast.Subscript)
                        and isinstance(cmp.left.args[0].value, ast.Name)
                        and cmp.left.args[0].value.id == "result"
                        and isinstance(cmp.left.args[0].slice, ast.Constant)
                        and cmp.left.args[0].slice.value == "failed"
                        and len(cmp.ops) == 1
                        and isinstance(cmp.ops[0], ast.Eq)
                        and len(cmp.comparators) == 1
                        and isinstance(cmp.comparators[0], ast.Constant)
                        and cmp.comparators[0].value == 0
                    ):
                        cmd_apply_return_len_failed_eq_zero = True
                        cmd_apply_lineno = child.lineno
        elif isinstance(node, ast.FunctionDef) and node.name == "main":
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == "sys"
                    and child.func.attr == "exit"
                    and len(child.args) == 1
                    and isinstance(child.args[0], ast.IfExp)
                ):
                    ifexp = child.args[0]
                    if (
                        isinstance(ifexp.body, ast.Constant)
                        and ifexp.body.value == 0
                        and isinstance(ifexp.orelse, ast.Constant)
                        and ifexp.orelse.value == 1
                        and isinstance(ifexp.test, ast.Compare)
                        and isinstance(ifexp.test.left, ast.Name)
                        and ifexp.test.left.id == "success"
                        and len(ifexp.test.ops) == 1
                        and isinstance(ifexp.test.ops[0], ast.IsNot)
                        and len(ifexp.test.comparators) == 1
                        and isinstance(ifexp.test.comparators[0], ast.Constant)
                        and ifexp.test.comparators[0].value is False
                    ):
                        main_sys_exit_zero_when_not_false = True
                        main_sys_exit_lineno = child.lineno

    proven = bool(
        apply_all_pending_lineno is not None
        and not_locked_return is not None
        and not_locked_return.get("all_lists_empty") is True
        and cmd_apply_return_len_failed_eq_zero is True
        and main_sys_exit_zero_when_not_false is True
    )
    return {
        "migration_manager_sha256": hashlib.sha256(mm_bytes).hexdigest(),
        "migrate_sha256": hashlib.sha256(m_bytes).hexdigest(),
        "apply_all_pending_lineno": apply_all_pending_lineno,
        "not_locked_return": not_locked_return,
        "cmd_apply_lineno": cmd_apply_lineno,
        "cmd_apply_exit_zero_when_failed_empty": cmd_apply_return_len_failed_eq_zero,
        "main_sys_exit_lineno": main_sys_exit_lineno,
        "main_sys_exit_zero_when_not_false": main_sys_exit_zero_when_not_false,
        "counterexample_proven": proven,
    }


def derive_relation_id(
    relation: str,
    database: str = APPROVED_TARGET_DATABASE,
    schema: str = APPROVED_TARGET_SCHEMA,
) -> str:
    """Compute relation_id = md5(database || chr(31) || schema || chr(31) || relation)."""
    raw = chr(31).join([database, schema, relation]).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def join_live_db_metadata_md5(
    repo_root: Path,
    candidate_relations: list[str] | None = None,
    candidate_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Recompute producer MD5 hashes to join candidate names against LIVE-DB-METADATA.json.

    LIVE-DB-METADATA.json stores hashed catalog metadata under `native_metadata`:
      - `actors`: list of dicts keyed by `role_id` = md5(rolname)
      - `relations`: list of dicts keyed by `relation_id` = md5(database || chr(31) || schema || chr(31) || relation)
      - `role_relation_grants`: list of dicts keyed by `(role_id, relation_id)`
    """
    meta_path = (
        repo_root
        / ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json"
    )
    pool_path = (
        repo_root
        / ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json"
    )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    native = meta.get("native_metadata", {})

    if candidate_relations is None:
        candidate_relations = [
            "conversations",
            "clients",
            "visa_decisions",
            "events_outbox",
            "visa_decision_retention_policies",
            "garuda_orders",
            "research_os_objects",
            "schema_migrations",
        ]
    if candidate_roles is None:
        candidate_roles = [
            "postgres",
            "backend_rag_v2",
            "nuzantara",
            "nuzantara_app",
            "nuzantara_readonly",
        ]

    public_schema_md5 = hashlib.md5(APPROVED_TARGET_SCHEMA.encode("utf-8")).hexdigest()
    rel_index: dict[str, dict[str, Any]] = {
        entry["relation_id"]: entry
        for entry in native.get("relations", [])
        if "relation_id" in entry
    }

    role_index: dict[str, dict[str, Any]] = {
        entry["role_id"]: entry
        for entry in native.get("actors", [])
        if "role_id" in entry
    }

    all_grants: list[dict[str, Any]] = list(native.get("role_relation_grants", []))
    grant_index: dict[tuple[str, str], dict[str, Any]] = {
        (g["role_id"], g["relation_id"]): g
        for g in all_grants
        if "role_id" in g and "relation_id" in g
    }

    matched_relations: dict[str, Any] = {}
    unmatched_relations: list[str] = []
    for rel in candidate_relations:
        digest = derive_relation_id(rel, APPROVED_TARGET_DATABASE, APPROVED_TARGET_SCHEMA)
        if digest in rel_index:
            cat_entry = rel_index[digest]
            rel_grants = [g for g in all_grants if g.get("relation_id") == digest]
            matched_relations[rel] = {
                "relation_id": digest,
                "row_security": cat_entry.get("row_security"),
                "force_row_security": cat_entry.get("force_row_security"),
                "grants": rel_grants,
                "catalog_entry": cat_entry,
            }
        else:
            unmatched_relations.append(rel)

    matched_roles: dict[str, Any] = {}
    unmatched_roles: dict[str, str] = {}
    for role in candidate_roles:
        digest = hashlib.md5(role.encode("utf-8")).hexdigest()
        if digest in role_index:
            matched_roles[role] = {
                "role_id": digest,
                "catalog_entry": role_index[digest],
            }
        else:
            unmatched_roles[role] = digest

    role_grants_for_matched: dict[str, dict[str, Any]] = {}
    for role_name, rinfo in matched_roles.items():
        r_digest = rinfo["role_id"]
        role_grants_for_matched[role_name] = {}
        for rel_name, rel_info in matched_relations.items():
            rel_digest = rel_info["relation_id"]
            if (r_digest, rel_digest) in grant_index:
                role_grants_for_matched[role_name][rel_name] = grant_index[(r_digest, rel_digest)]

    factory_roles = {f.get("target_role", "UNOBSERVED") for f in pool.get("factories", [])}
    return {
        "live_db_metadata_sha256": hashlib.sha256(meta_path.read_bytes()).hexdigest(),
        "pool_factory_source_sha256": hashlib.sha256(pool_path.read_bytes()).hexdigest(),
        "pool_factory_target_role": "UNOBSERVED" if factory_roles <= {"UNOBSERVED"} else sorted(factory_roles),
        "target_database": APPROVED_TARGET_DATABASE,
        "target_schema": APPROVED_TARGET_SCHEMA,
        "relation_id_derivation": RELATION_ID_DERIVATION,
        "relation_id_derivation_evidence_ref": RELATION_ID_DERIVATION_EVIDENCE_REF,
        "role_id_derivation": "md5(rolname)",
        "public_schema_md5": public_schema_md5,
        "matched_relations": matched_relations,
        "unmatched_relations": unmatched_relations,
        "matched_roles": matched_roles,
        "unmatched_roles": unmatched_roles,
        "role_grants_for_matched": role_grants_for_matched,
        "principal_role_binding_closed": bool(factory_roles - {"UNOBSERVED"}),
        "principal_role_binding_blocker": (
            "LIVE-DB-METADATA.json proves table-level role_relation_grants for all 8 default relations via "
            "md5(database||chr(31)||schema||chr(31)||relation) and md5(rolname) "
            "(e.g. role backend_rag_v2=7457cee812eeb67564c33b7acf10e393), but POOL-FACTORY-SOURCE.json "
            "records target_role='UNOBSERVED', leaving runtime principal-to-DB-role binding PARTIAL."
        ),
    }


def _build_garuda_instance(
    consumer_id: str,
    csv_line: int,
    rel_path: str,
    verb: str,
    obj: str,
    tx_val: str,
    effects_val: str,
    idemp_val: str,
    failure_val: str,
) -> dict[str, Any]:
    """Build a canonical 19-key (+ x_evidence_ref) contract instance for a garuda_orders consumer row."""
    ev_ref = "research/operations/udb-wave8/B05/dux-requests/DUX-B05-04.out:L1-L35"
    sql_ref = "apps/backend-rag/backend/db/migrations_v2/284_garuda_orders.sql:L1-L78"
    return {
        "consumer_id": consumer_id,
        "operation_id": f"op:garuda:{verb}:{obj}",
        "store_id": "pg:fly:nuzantara-postgres/public",
        "source_version": BASE_COMMIT_SHA,
        "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
        "evidence_sha256": PINNED_SHA256["284_garuda_orders.sql"],
        "status": "PARTIAL",
        "unknowns": [
            "STATIC_SOURCE_ONLY",
            "RUNTIME_PRINCIPAL_TO_DB_ROLE_UNOBSERVED",
            "RESTORE_DRILL_RECEIPT_MISSING_FOR_RELATION",
        ],
        "principal": make_field(
            f"app:backend-rag:{rel_path} (consumer_matrix_line={csv_line})",
            "PARTIAL",
            ev_ref,
        ),
        "role": make_field(
            "UNOBSERVED_AT_POOL_FACTORY (candidate role in pg_roles MD5 catalog unjoined to DSN)",
            "PARTIAL",
            ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json:L1-L16",
        ),
        "tenant": make_field(
            "single-tenant order scope (customer_email/passport_number columns; LIVE-DB-METADATA.json relation_id=d00ff231bc2883677ba59792bf517bd6 has row_security=false)",
            "EVIDENCED",
            sql_ref,
        ),
        "authorization": make_field(
            "application-layer router/service guard; LIVE-DB-METADATA.json shows row_security=false and grants on relation_id=d00ff231bc2883677ba59792bf517bd6, but runtime pool role is UNOBSERVED",
            "PARTIAL",
            sql_ref,
        ),
        "transaction": make_field(tx_val, "PARTIAL", ev_ref),
        "effects": make_field(effects_val, "PARTIAL", sql_ref),
        "retries": make_field(
            "outbox/worker retry state tracked via status/updated_at columns; caller retry policy not proven at runtime",
            "PARTIAL",
            sql_ref,
        ),
        "idempotency": make_field(idemp_val, "EVIDENCED", sql_ref),
        "failure": make_field(failure_val, "EVIDENCED", sql_ref),
        "retention": make_field(
            "UNSPECIFIED_IN_SCHEMA (no TTL or retention purge job bound to garuda_orders)",
            "UNKNOWN",
            None,
        ),
        "recovery": make_field(
            "UNVERIFIED_RESTORE (garuda_orders relation_id=d00ff231bc2883677ba59792bf517bd6 is present in LIVE-DB-METADATA.json, but is not among the 5 relations verified by restore_drill_verify.py)",
            "BLOCKED",
            "scripts/ci/restore_drill_verify.py:L90-L155",
        ),
        "x_evidence_ref": "apps/backend-rag/backend/db/migrations_v2/284_garuda_orders.sql",
    }


def _build_research_os_instance(
    consumer_id: str,
    csv_line: int,
    rel_path: str,
    verb: str,
    obj: str,
    effects_val: str,
) -> dict[str, Any]:
    """Build a canonical 19-key (+ x_evidence_ref) contract instance for a research_os_objects consumer row."""
    ev_ref = "research/operations/udb-wave8/B05/dux-requests/DUX-B05-04.out:L36-L55"
    sql_ref = "apps/backend-rag/backend/db/migrations_v2/279_research_os_contract_core.sql:L1-L97"
    return {
        "consumer_id": consumer_id,
        "operation_id": f"op:research-os:{verb}:{obj}",
        "store_id": "pg:fly:nuzantara-postgres/public",
        "source_version": BASE_COMMIT_SHA,
        "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
        "evidence_sha256": PINNED_SHA256["279_research_os_contract_core.sql"],
        "status": "PARTIAL",
        "unknowns": [
            "STATIC_SOURCE_ONLY",
            "RUNTIME_PRINCIPAL_TO_DB_ROLE_UNOBSERVED",
            "RESTORE_DRILL_RECEIPT_MISSING_FOR_RELATION",
        ],
        "principal": make_field(
            f"app:backend-rag:{rel_path} (consumer_matrix_line={csv_line})",
            "PARTIAL",
            ev_ref,
        ),
        "role": make_field(
            "UNOBSERVED_AT_POOL_FACTORY (target_role=UNOBSERVED in POOL-FACTORY-SOURCE.json)",
            "PARTIAL",
            ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json:L1-L16",
        ),
        "tenant": make_field(
            "system-wide append-only research OS ledger (owner_lane column; LIVE-DB-METADATA.json relation_id=ffef8ec071b83da3ab9acbb16a9f0633 has row_security=false)",
            "EVIDENCED",
            sql_ref,
        ),
        "authorization": make_field(
            "DB trigger enforce_research_os_append_only blocks UPDATE/DELETE; TRUNCATE guard in migration 280; catalog grants present on relation_id=ffef8ec071b83da3ab9acbb16a9f0633 but runtime pool role is UNOBSERVED",
            "PARTIAL",
            sql_ref,
        ),
        "transaction": make_field(
            "single-statement INSERT / DDL execution; trigger raises exception aborting statement transaction on mutation",
            "EVIDENCED",
            sql_ref,
        ),
        "effects": make_field(effects_val, "EVIDENCED", sql_ref),
        "retries": make_field(
            "caller-dependent; duplicate content_hash or object_id rejected deterministically by UNIQUE/PK constraints",
            "PARTIAL",
            sql_ref,
        ),
        "idempotency": make_field(
            "enforced by PRIMARY KEY (object_id) and UNIQUE (object_kind, slug, version) in 279_research_os_contract_core.sql",
            "EVIDENCED",
            sql_ref,
        ),
        "failure": make_field(
            "append-only trigger raises ERRCODE23514 / exception on UPDATE, DELETE, or TRUNCATE (migrations 279 & 280)",
            "EVIDENCED",
            sql_ref,
        ),
        "retention": make_field(
            "immutable append-only retention (DELETE/TRUNCATE forbidden by DB triggers in migrations 279 and 280)",
            "EVIDENCED",
            sql_ref,
        ),
        "recovery": make_field(
            "UNVERIFIED_RESTORE (research_os_objects relation_id=ffef8ec071b83da3ab9acbb16a9f0633 is present in LIVE-DB-METADATA.json, but is not among the 5 relations verified by restore_drill_verify.py)",
            "BLOCKED",
            "scripts/ci/restore_drill_verify.py:L90-L155",
        ),
        "x_evidence_ref": "apps/backend-rag/backend/db/migrations_v2/279_research_os_contract_core.sql",
    }


def build_b05_operation_contracts() -> list[dict[str, Any]]:
    """Build the 23 deeply-inspected canonical B05 operation contract instances.

    Covers:
      - All 4 Wave-7 `SCOPED_ISOLATED_VERIFICATION_ONLY` rows (including the 2 counterexamples)
      - The 6,030th lead `runtime_mini_46522da0ef79d3aa7422ca41` (`LEAD-DELTA.json`)
      - All 12 non-test `garuda_orders` rows (`DUX-B05-04.out`)
      - All 6 non-test `research_os_objects` rows (`DUX-B05-04.out`)
    """
    instances: list[dict[str, Any]] = [
        # 1. Wave-7 SCOPED_ISOLATED_VERIFICATION_ONLY #1: conversations append/upsert (CONFLICT counterexample)
        {
            "consumer_id": "src_6ad3cb3fa4349521",
            "operation_id": "op:crm-conversations:write:conversation-messages",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": PINNED_SHA256["conversation_repository.py"],
            "status": "CONFLICT",
            "unknowns": [
                "STATIC_SOURCE_ONLY",
                "RUNTIME_PRINCIPAL_TO_DB_ROLE_UNOBSERVED",
                "LOCKING_CLAIM_CONFLICT_NO_ADVISORY_OR_ROW_LOCK_IN_SAVE_MESSAGES",
                "RESTORE_DRILL_CONVERSATIONS_CANNOT_VERIFY",
                "RETENTION_STATUTE_CITATION_UNVERIFIED",
            ],
            "principal": make_field(
                "app:backend-rag:ConversationRepository (src_6ad3cb3fa4349521, consumer-matrix.csv:L545)",
                "PARTIAL",
                "apps/backend-rag/backend/db/repositories/conversation_repository.py:L23-L136",
            ),
            "role": make_field(
                "UNOBSERVED_AT_POOL_FACTORY (candidate role backend_rag_v2=7457cee812eeb67564c33b7acf10e393 in LIVE-DB-METADATA.json; pool target_role=UNOBSERVED)",
                "PARTIAL",
                ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json:L1-L16",
            ),
            "tenant": make_field(
                "user_id + session_id application-scoped filter; Live DB row_security=false on public.conversations",
                "EVIDENCED",
                ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json:L185-L260",
            ),
            "authorization": make_field(
                "FastAPI get_current_user dependency at router; no PostgreSQL RLS (row_security=false)",
                "PARTIAL",
                "apps/backend-rag/backend/db/repositories/conversation_repository.py:L32-L136",
            ),
            "transaction": make_field(
                "CONFLICT: consumer-matrix.csv:L545 claims 'One asyncpg transaction per save; two-int advisory session lock; row lock' (ADAPTED_PARTIAL_VERIFIED), but save_messages (L59-L132) has NO advisory lock and NO FOR UPDATE row lock, and anonymize_user_data (L265-L286) executes without conn.transaction()",
                "CONFLICT",
                "apps/backend-rag/backend/db/repositories/conversation_repository.py:L59-L136",
            ),
            "effects": make_field(
                "SELECT id,messages FROM conversations; UPDATE conversations SET messages=$1::text::jsonb OR INSERT INTO conversations; @cache_invalidating Redis side effect",
                "EVIDENCED",
                "apps/backend-rag/backend/db/repositories/conversation_repository.py:L26-L132",
            ),
            "retries": make_field(
                "no repository-level retry loop; asyncpg pool command_timeout=60s",
                "EVIDENCED",
                "apps/backend-rag/backend/db/repositories/conversation_repository.py:L32-L136",
            ),
            "idempotency": make_field(
                "adjacent-message equality dedup only (L81); NOT_IDEMPOTENT under concurrent saves because SELECT+UPDATE lacks advisory or FOR UPDATE lock",
                "EVIDENCED",
                "apps/backend-rag/backend/db/repositories/conversation_repository.py:L62-L98",
            ),
            "failure": make_field(
                "catches Exception, logs error, and returns sentinel None (save_messages) or 0 (cleanup/anonymize) while @cache_invalidating still fires",
                "EVIDENCED",
                "apps/backend-rag/backend/db/repositories/conversation_repository.py:L134-L136",
            ),
            "retention": make_field(
                "RETENTION_MIN_DAYS=1826 (5-year floor) and CONVERSATION_RETENTION_ALLOW_CLOCK_DELETE gate in retention_policy.py (docstring cites UU PDP Art. 43 — unverified statutory citation)",
                "PARTIAL",
                "apps/backend-rag/backend/core/retention_policy.py:L18-L84",
            ),
            "recovery": make_field(
                "BLOCKED: REAL-RUN-RECEIPT.json records conversations=CANNOT-VERIFY (UNMEASURED_CHECK: 1) and clients=FAIL (VIOLATION: 1); sub-check/SQL error unrecorded in receipt",
                "BLOCKED",
                ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json:L31-L76",
            ),
            "x_evidence_ref": "apps/backend-rag/backend/db/repositories/conversation_repository.py",
        },
        # 2. Wave-7 SCOPED_ISOLATED_VERIFICATION_ONLY #2: agentic_rag router Redis/RAG callsite
        {
            "consumer_id": "src_4c49b82438955ab7",
            "operation_id": "op:rag-router:query:agentic-rag-stream",
            "store_id": "unknown:unknown:unknown",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": PINNED_SHA256["DUX-B05-01.out"],
            "status": "PARTIAL",
            "unknowns": [
                "STATIC_SOURCE_ONLY",
                "STORE_ID_PROPOSED:redis:pro:6379/db0",
                "REDIS_RUNTIME_KEYSPACE_AND_ACL_UNOBSERVED",
                "RESTORE_DRILL_NOT_APPLICABLE_OR_UNPROVEN",
            ],
            "principal": make_field(
                "app:backend-rag:agentic_rag.router (src_4c49b82438955ab7, consumer-matrix.csv:L163)",
                "PARTIAL",
                "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out:L1-L60",
            ),
            "role": make_field(
                "redis default/ACL user unobserved in runtime evidence",
                "UNKNOWN",
                None,
            ),
            "tenant": make_field(
                "authenticated user session scope passed from FastAPI request context",
                "PARTIAL",
                "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out:L1-L60",
            ),
            "authorization": make_field(
                "FastAPI get_current_user dependency on router endpoint",
                "PARTIAL",
                "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out:L1-L60",
            ),
            "transaction": make_field(
                "non-transactional cache/session lookup and RAG stream orchestration",
                "PARTIAL",
                "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out:L1-L60",
            ),
            "effects": make_field(
                "reads/writes ephemeral RAG cache and dispatches hybrid retrieval + conversation persistence",
                "PARTIAL",
                "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out:L1-L60",
            ),
            "retries": make_field(
                "degrades gracefully on cache miss/unavailable; stream errors emitted as SSE events",
                "PARTIAL",
                "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out:L1-L60",
            ),
            "idempotency": make_field(
                "read/query path idempotent; side-effecting conversation log write delegated to repository",
                "PARTIAL",
                "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out:L1-L60",
            ),
            "failure": make_field(
                "HTTPException / SSE error frame on downstream failure; isolated unit test only in Wave 7",
                "PARTIAL",
                "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out:L1-L60",
            ),
            "retention": make_field(
                "ephemeral Redis TTL per cache key; live Redis TTL configuration unobserved",
                "UNKNOWN",
                None,
            ),
            "recovery": make_field(
                "ephemeral cache rebuilt on miss; no live Redis persistence/restore receipt in Wave 7/8",
                "UNKNOWN",
                None,
            ),
            "x_evidence_ref": "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out",
        },
        # 3. Wave-7 SCOPED_ISOLATED_VERIFICATION_ONLY #3: migration_manager.py (CONFLICT counterexample)
        {
            "consumer_id": "src_058ad32e4ad2e6a8",
            "operation_id": "op:db-migrations:apply:pending-migrations",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": PINNED_SHA256["DUX-B05-01.out"],
            "status": "CONFLICT",
            "unknowns": [
                "STATIC_SOURCE_ONLY",
                "RUNTIME_PRINCIPAL_TO_DB_ROLE_UNOBSERVED",
                "LOCK_BUSY_EXIT_CODE_CONFLICT_CLAIMED_NONZERO_ACTUAL_ZERO",
                "RESTORE_DRILL_RECEIPT_MISSING_FOR_RELATION",
            ],
            "principal": make_field(
                "app:backend-rag:MigrationManager.apply_all_pending (src_058ad32e4ad2e6a8, consumer-matrix.csv:L343)",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migration_manager.py:L501-L605",
            ),
            "role": make_field(
                "UNOBSERVED_AT_POOL_FACTORY (requires DDL privileges on public.schema_migrations / public.migration_history)",
                "PARTIAL",
                ".agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json:L1-L16",
            ),
            "tenant": make_field(
                "global cluster-wide schema migration state (public schema)",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migration_manager.py:L501-L605",
            ),
            "authorization": make_field(
                "PostgreSQL session advisory lock pg_try_advisory_lock(73491) + DDL role privileges",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migration_manager.py:L499-L545",
            ),
            "transaction": make_field(
                "per-migration SQL execution with tracking insert into migration ledger under advisory lock",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migration_manager.py:L546-L600",
            ),
            "effects": make_field(
                "executes pending SQL files in migrations_v2/ and records applied version rows",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migration_manager.py:L546-L600",
            ),
            "retries": make_field(
                "no automatic retry when pg_try_advisory_lock returns false; caller must re-invoke",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migration_manager.py:L531-L542",
            ),
            "idempotency": make_field(
                "skips already-applied migration numbers recorded in ledger table",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migration_manager.py:L546-L570",
            ),
            "failure": make_field(
                "CONFLICT: consumer-matrix.csv:L343 claims 'Lock-busy refusal is nonzero; applied numbers skipped' (ADAPTED_ISOLATED_VERIFIED), but MigrationManager.apply_all_pending (migration_manager.py:L501, L539-L541) returns {'applied': [], 'skipped': [], 'failed': []} when not locked, causing cmd_apply (migrate.py:L77 `return len(result['failed']) == 0`) and main (migrate.py:L170 `sys.exit(0 if success is not False else 1)`) to exit 0",
                "CONFLICT",
                "apps/backend-rag/backend/db/migration_manager.py:L501-L541",
            ),
            "retention": make_field(
                "permanent schema migration audit history in PostgreSQL",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migration_manager.py:L546-L600",
            ),
            "recovery": make_field(
                "UNVERIFIED_RESTORE (migration ledger tables not verified in restore_drill_verify.py)",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:L1-L162",
            ),
            "x_evidence_ref": "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out",
        },
        # 4. Wave-7 SCOPED_ISOLATED_VERIFICATION_ONLY #4: migrate.py CLI (CONFLICT counterexample)
        {
            "consumer_id": "src_c8f206461cd9bf69",
            "operation_id": "op:db-migrations:execute:cli-migrate-apply",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": PINNED_SHA256["DUX-B05-01.out"],
            "status": "CONFLICT",
            "unknowns": [
                "STATIC_SOURCE_ONLY",
                "RUNTIME_PRINCIPAL_TO_DB_ROLE_UNOBSERVED",
                "LOCK_BUSY_EXIT_CODE_CONFLICT_CLAIMED_NONZERO_ACTUAL_ZERO",
                "RESTORE_DRILL_RECEIPT_MISSING_FOR_RELATION",
            ],
            "principal": make_field(
                "cli:backend-rag:migrate.cmd_apply (src_c8f206461cd9bf69, consumer-matrix.csv:L4440)",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrate.py:L55-L80",
            ),
            "role": make_field(
                "UNOBSERVED_AT_POOL_FACTORY (reads DATABASE_URL env var at runtime)",
                "PARTIAL",
                "apps/backend-rag/backend/db/migrate.py:L55-L80",
            ),
            "tenant": make_field(
                "global cluster-wide schema migration CLI",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrate.py:L55-L80",
            ),
            "authorization": make_field(
                "requires DATABASE_URL credentials and advisory lock via MigrationManager",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrate.py:L55-L80",
            ),
            "transaction": make_field(
                "delegates per-migration execution to MigrationManager.apply_all_pending",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrate.py:L60-L78",
            ),
            "effects": make_field(
                "applies pending migrations and exits with process return code",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrate.py:L60-L78",
            ),
            "retries": make_field(
                "single-shot CLI invocation; no internal retry loop",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrate.py:L60-L78",
            ),
            "idempotency": make_field(
                "delegates applied-version skip check to MigrationManager",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrate.py:L60-L78",
            ),
            "failure": make_field(
                "CONFLICT: consumer-matrix.csv:L4440 claims 'Lock-busy refusal is nonzero; applied numbers skipped' (ADAPTED_ISOLATED_VERIFIED), but cmd_apply in migrate.py:L77 returns `len(result['failed']) == 0` (True) and main in migrate.py:L170 executes `sys.exit(0 if success is not False else 1)`, exiting 0 on advisory lock refusal",
                "CONFLICT",
                "apps/backend-rag/backend/db/migrate.py:L75-L170",
            ),
            "retention": make_field(
                "permanent migration ledger rows retained in PostgreSQL",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrate.py:L60-L78",
            ),
            "recovery": make_field(
                "UNVERIFIED_RESTORE (migration ledger restore not proven in B01 receipt)",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:L1-L162",
            ),
            "x_evidence_ref": "research/operations/udb-wave8/B05/dux-requests/DUX-B05-01.out",
        },
        # 5. The 6,030th lead from LEAD-DELTA.json: runtime_mini_46522da0ef79d3aa7422ca41
        {
            "consumer_id": LEAD_DELTA_CONSUMER_ID,
            "operation_id": "op:backup-restore:verify:restore-drill",
            "store_id": "unknown:unknown:unknown",
            "source_version": "prior:UNKNOWN",
            "evidence_timestamp": "2026-10-15T08:31:00Z",
            "evidence_sha256": PINNED_SHA256["restore_drill_verify.py"],
            "status": "BLOCKED",
            "unknowns": [
                "STORE_ID_PROPOSED:pg:mini:restore-drill-target/public",
                "RESTORE_DRILL_CLIENTS_FAIL_VIOLATION_1",
                "RESTORE_DRILL_CONVERSATIONS_CANNOT_VERIFY_UNMEASURED_1",
                "SYNTHETIC_PG_HARNESS_SKIPPED_DOCKER_DAEMON_DOWN",
            ],
            "principal": make_field(
                "cron:mini:restore_drill_verify.py (lead_id=runtime_mini_46522da0ef79d3aa7422ca41 in LEAD-DELTA.json:L7)",
                "EVIDENCED",
                ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json:L1-L23",
            ),
            "role": make_field(
                "local restore drill PostgreSQL role passed via --dsn / psql in restore_drill_verify.py",
                "PARTIAL",
                "scripts/ci/restore_drill_verify.py:L35-L90",
            ),
            "tenant": make_field(
                "full-database restore verification across public.clients and public.conversations",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:L90-L155",
            ),
            "authorization": make_field(
                "read-only SQL verification queries executed via psql --no-psqlrc -v ON_ERROR_STOP=1",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:L40-L85",
            ),
            "transaction": make_field(
                "read-only verification queries per table check",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:L90-L155",
            ),
            "effects": make_field(
                "executes SELECT count/null/jsonb_typeof checks on public.clients and public.conversations and emits JSON receipt",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:L90-L162",
            ),
            "retries": make_field(
                "single-shot verification script; no internal retry",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:L1-L162",
            ),
            "idempotency": make_field(
                "idempotent read-only verification queries against target DSN",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:L90-L155",
            ),
            "failure": make_field(
                "marks table FAIL on violation > 0 or CANNOT-VERIFY on unmeasured check / SQL error; exits non-zero if overall != PASS",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:L120-L162",
            ),
            "retention": make_field(
                "emits restore drill JSON receipt; ephemeral scratch restore DB",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:L140-L162",
            ),
            "recovery": make_field(
                "BLOCKED: REAL-RUN-RECEIPT.json (2026-10-15T03:00:43Z) recorded clients=FAIL (VIOLATION: 1) and conversations=CANNOT-VERIFY (UNMEASURED_CHECK: 1); SYNTHETIC-PG-RESULT.json skipped (docker daemon not running)",
                "BLOCKED",
                ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/SYNTHETIC-PG-RESULT.json:L1-L15",
            ),
            "x_evidence_ref": "scripts/ci/restore_drill_verify.py",
        },
    ]

    # Add all 12 non-test garuda_orders rows from DUX-B05-04.out
    garuda_rows = [
        (
            "src_b76fd8a386284d6d",
            510,
            "apps/backend-rag/backend/db/migrations_v2/284_garuda_orders.sql",
            "migrate",
            "garuda-orders-schema",
            "DDL CREATE TABLE IF NOT EXISTS garuda_orders + indexes in migration transaction",
            "creates public.garuda_orders table, status/quote_token/created_at indexes, and CHECK constraints",
            "idempotent DDL via CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS",
            "PostgreSQL DDL error aborts migration 284",
        ),
        (
            "src_a3385c4f03c66ace",
            882,
            "apps/backend-rag/backend/services/garuda/adapters_pg.py",
            "adapt",
            "garuda-orders-pg-adapter",
            "asyncpg connection/transaction adapter calls over public.garuda_orders",
            "executes parameterized SQL reads/writes on public.garuda_orders",
            "enforced by quote_token UNIQUE constraint and PK (order_id) in 284_garuda_orders.sql",
            "raises asyncpg error / constraint violation on invalid state or duplicate key",
        ),
        (
            "src_a59306f68d76608c",
            884,
            "apps/backend-rag/backend/services/garuda/eligibility_lookup.py",
            "read",
            "garuda-orders-eligibility",
            "read-only SELECT query over public.garuda_orders",
            "reads prior order/eligibility status from public.garuda_orders",
            "read-only query is side-effect free and idempotent",
            "propagates database read exception to caller",
        ),
        (
            "src_d5a8b07610fb5247",
            885,
            "apps/backend-rag/backend/services/garuda/idempotency.py",
            "enforce",
            "garuda-orders-idempotency",
            "single-statement or transactional idempotency key lookup/upsert on garuda_orders",
            "prevents duplicate order creation via quote_token / idempotency key constraints",
            "enforced by UNIQUE quote_token / order_id constraints in 284_garuda_orders.sql",
            "rejects duplicate mutation or returns existing order state",
        ),
        (
            "src_ece991c081caeff3",
            886,
            "apps/backend-rag/backend/services/garuda/journal.py",
            "append",
            "garuda-orders-journal",
            "transactional state transition journal write tied to garuda_orders",
            "records order lifecycle transition audit state",
            "keyed by order_id transition sequence",
            "aborts write on CHECK/FK constraint violation",
        ),
        (
            "src_acdbfcfa16458d24",
            887,
            "apps/backend-rag/backend/services/garuda/outbox_alarm.py",
            "scan",
            "garuda-orders-outbox-alarm",
            "read-only diagnostic scan over stalled garuda_orders rows",
            "queries orders stuck in non-terminal statuses past threshold",
            "read-only scan is idempotent",
            "logs/raises alarm on stalled outbox rows or query error",
        ),
        (
            "src_5c137f36a73ef536",
            888,
            "apps/backend-rag/backend/services/garuda/outbox_consumer.py",
            "consume",
            "garuda-orders-outbox",
            "polls and claims pending garuda_orders outbox rows for dispatch",
            "updates order processing state in public.garuda_orders",
            "guarded by status CHECK constraint and state transition predicates",
            "records failure state / leaves row for retry on handler error",
        ),
        (
            "src_efd985c016f29c9e",
            889,
            "apps/backend-rag/backend/services/garuda/outbox_handlers.py",
            "handle",
            "garuda-orders-outbox-event",
            "executes side-effect handler and persists status update on garuda_orders",
            "transitions garuda_orders status column within allowed 14-state CHECK enum",
            "idempotent per terminal state transition check",
            "CHECK constraint in 284_garuda_orders.sql rejects invalid status strings",
        ),
        (
            "src_593c6f23db50d688",
            890,
            "apps/backend-rag/backend/services/garuda/payment_inbox_watch.py",
            "reconcile",
            "garuda-orders-payment-inbox",
            "matches payment inbox events against public.garuda_orders",
            "updates payment status fields on matched garuda_orders row",
            "keyed by payment reference / order_id state guard",
            "unmatched or invalid state transitions rejected by CHECK constraints",
        ),
        (
            "src_d9eac093b51823a0",
            891,
            "apps/backend-rag/backend/services/garuda/reconciliation.py",
            "reconcile",
            "garuda-orders-ledger",
            "reads and reconciles garuda_orders rows against payment/practice state",
            "identifies or repairs drift on public.garuda_orders",
            "idempotent reconciliation pass keyed by order_id",
            "raises/logs discrepancy when order state violates invariants",
        ),
        (
            "src_c903fdf94bfdbcf9",
            892,
            "apps/backend-rag/backend/services/garuda/repository.py",
            "write",
            "garuda-orders-repository",
            "repository CRUD and status transition queries over public.garuda_orders",
            "INSERT/SELECT/UPDATE on public.garuda_orders (PK order_id, UNIQUE quote_token)",
            "UNIQUE (quote_token) and PK (order_id) prevent duplicate order rows",
            "PostgreSQL CHECK constraints enforce valid 14-state status and non-negative amounts",
        ),
        (
            "src_053ab28e395ea84c",
            896,
            "apps/backend-rag/backend/services/portal/practice.py",
            "link",
            "garuda-orders-portal-practice",
            "links portal practice workflow to public.garuda_orders record",
            "reads/updates practice linkage on public.garuda_orders",
            "keyed by order_id / practice reference",
            "propagates DB error if referenced order row is missing or invalid",
        ),
    ]
    for row_args in garuda_rows:
        instances.append(_build_garuda_instance(*row_args))

    # Add all 6 non-test research_os_objects rows from DUX-B05-04.out
    research_os_rows = [
        (
            "src_1db8d65b2fc3a96b",
            506,
            "apps/backend-rag/backend/db/migrations_v2/279_research_os_contract_core.sql",
            "migrate",
            "research-os-objects-schema",
            "DDL CREATE TABLE research_os_objects + append-only trigger enforce_research_os_append_only()",
        ),
        (
            "src_dd9f17226bfa686a",
            507,
            "apps/backend-rag/backend/db/migrations_v2/280_research_os_objects_truncate_guard.sql",
            "migrate",
            "research-os-objects-truncate-guard",
            "DDL BEFORE TRUNCATE trigger blocking TRUNCATE on public.research_os_objects",
        ),
        (
            "src_3c174975c88a0956",
            770,
            "apps/backend-rag/backend/services/events/consul_executor.py",
            "append",
            "consul-executor-research-object",
            "INSERT append-only execution receipt/object into public.research_os_objects",
        ),
        (
            "src_1c425138a2cbdbbc",
            771,
            "apps/backend-rag/backend/services/events/consul_native_broker.py",
            "append",
            "consul-broker-research-object",
            "INSERT append-only broker dispatch object into public.research_os_objects",
        ),
        (
            "src_46744d037fbfe8ea",
            1133,
            "apps/backend-rag/backend/services/rag/naga_backfill.py",
            "backfill",
            "naga-research-os-objects",
            "batch INSERT backfill of historical research objects into public.research_os_objects",
        ),
        (
            "src_1666fcd2655dbe71",
            1134,
            "apps/backend-rag/backend/services/rag/naga_persistence.py",
            "append",
            "naga-persistence-research-object",
            "INSERT runtime NAGA persistence record into public.research_os_objects",
        ),
    ]
    for row_args in research_os_rows:
        instances.append(_build_research_os_instance(*row_args))

    return instances


def build_artifact_payload(repo_root: Path) -> dict[str, Any]:
    """Assemble the complete operation-contracts.json payload with computed denominator accounting."""
    csv_path = repo_root / ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    lead_delta_path = (
        repo_root
        / ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json"
    )

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        csv_rows = list(csv.DictReader(f))
    total_csv_rows = len(csv_rows)
    retained_test_rows = sum(
        1 for r in csv_rows if (r.get("disposition") or "").strip() == "RETAINED_TEST_SOURCE"
    )

    census_buckets = compute_census(csv_path)
    census_bucket_count = len(census_buckets)
    census_sum = sum(b["count"] for b in census_buckets)
    if census_sum != total_csv_rows:
        raise ValueError(f"Census bucket sum {census_sum} != CSV row count {total_csv_rows}")

    lead_delta = json.loads(lead_delta_path.read_text(encoding="utf-8"))
    additions = lead_delta.get("additions", [])
    lead_delta_rows = len(additions)
    baseline_rows_preserved = lead_delta.get("baseline_rows_preserved")
    union_lead_rows = lead_delta.get("union_lead_rows")
    if baseline_rows_preserved != total_csv_rows:
        raise ValueError(
            f"LEAD-DELTA baseline_rows_preserved {baseline_rows_preserved} != CSV rows {total_csv_rows}"
        )
    if lead_delta_rows != union_lead_rows - baseline_rows_preserved:
        raise ValueError(
            f"LEAD-DELTA additions len {lead_delta_rows} != union_lead_rows ({union_lead_rows}) - baseline ({baseline_rows_preserved})"
        )

    valid_ids = {r["consumer_id"] for r in csv_rows} | {
        item["consumer_id"] for item in additions if "consumer_id" in item
    }

    instances = build_b05_operation_contracts()
    for inst in instances:
        errs = validate_operation_instance(inst, valid_consumer_ids=valid_ids)
        if errs:
            raise ValueError(f"Invalid generated instance {inst.get('consumer_id')}: {errs}")

    complete_count = sum(
        1 for inst in instances if is_complete_contract(inst, valid_consumer_ids=valid_ids)
    )
    status_counts: dict[str, int] = {}
    for inst in instances:
        st = inst["status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    total_leads = total_csv_rows + lead_delta_rows
    non_retained_test_plus_delta = (total_csv_rows - retained_test_rows) + lead_delta_rows
    uninstantiated_non_retained = non_retained_test_plus_delta - len(instances)

    return {
        "schema_version": "udb-wave8-b05-v2",
        "conventions_sha256": "a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559",
        "base_commit_sha": BASE_COMMIT_SHA,
        "base_commit_timestamp": BASE_COMMIT_TIMESTAMP,
        "denominator_accounting": {
            "consumer_matrix_csv_rows": total_csv_rows,
            "lead_delta_rows": lead_delta_rows,
            "total_leads": total_leads,
            "retained_test_source_rows": retained_test_rows,
            "non_retained_test_plus_delta": non_retained_test_plus_delta,
            "active_consumer_denominator": lead_delta.get("active_consumer_denominator", "UNKNOWN"),
            "active_consumer_denominator_caveat": (
                f"LEAD-DELTA.json marks active_consumer_denominator='UNKNOWN' pending B03 reconciliation; "
                f"{non_retained_test_plus_delta} is non_retained_test_plus_delta "
                f"(({total_csv_rows} - {retained_test_rows}) + {lead_delta_rows})."
            ),
            "instantiated_operation_contracts": len(instances),
            "instantiated_status_breakdown": status_counts,
            "complete_operation_contracts": complete_count,
            "uninstantiated_non_retained_leads": uninstantiated_non_retained,
            "uninstantiated_reason": (
                f"Remaining {uninstantiated_non_retained} non-retained-test leads (out of "
                f"{non_retained_test_plus_delta} non_retained_test_plus_delta; active_consumer_denominator is "
                f"UNKNOWN in LEAD-DELTA.json) remain in BLOCKED_DISCOVERY / PARTIAL_DISCOVERY / "
                f"BLOCKED_RUNTIME_CONTRACT buckets across {census_bucket_count} computed census buckets in "
                f"consumer-matrix.csv awaiting B02/B03/B06/B07 callsite, runtime unit, and store target resolution."
            ),
            "census_bucket_count": census_bucket_count,
            "census_buckets": census_buckets,
        },
        "ast_counterexamples": {
            "conversation_repository": verify_conversation_repo_ast(repo_root),
            "migration_lock_busy": verify_migration_lock_busy_ast(repo_root),
        },
        "live_db_md5_catalog_join": join_live_db_metadata_md5(repo_root),
        "operation_contracts": instances,
    }


def _csv_fieldnames_for_instances(instances: list[dict[str, Any]]) -> list[str]:
    """Return the 19 required keys followed by any x_-prefixed keys in deterministic order."""
    extra_keys: list[str] = []
    for inst in instances:
        for k in inst:
            if k not in REQUIRED_19_KEYS and EXTENSION_KEY_RE.match(k) and k not in extra_keys:
                extra_keys.append(k)
    return list(REQUIRED_19_KEYS) + extra_keys


def render_csv_text(instances: list[dict[str, Any]]) -> str:
    """Render operation contract instances to canonical CSV text with LF line endings."""
    buf = io.StringIO()
    fieldnames = _csv_fieldnames_for_instances(instances)
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for inst in instances:
        writer.writerow(instance_to_csv_row(inst))
    return buf.getvalue()


def write_artifacts(repo_root: Path, out_dir: Path) -> None:
    """Write operation-contracts.json and operation-contracts.csv to out_dir."""
    payload = build_artifact_payload(repo_root)
    json_path = out_dir / "operation-contracts.json"
    csv_path = out_dir / "operation-contracts.csv"

    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    csv_path.write_text(
        render_csv_text(payload["operation_contracts"]),
        encoding="utf-8",
    )


def validate_artifacts(repo_root: Path, out_dir: Path) -> int:
    """Validate on-disk pins, regenerate payload in memory, and require byte-equality with JSON & CSV."""
    pin_errors = verify_pinned_sha256(repo_root)
    if pin_errors:
        for err in pin_errors:
            sys.stderr.write(f"ERROR: {err}\n")
        return 1

    json_path = out_dir / "operation-contracts.json"
    csv_path = out_dir / "operation-contracts.csv"
    if not json_path.is_file() or not csv_path.is_file():
        sys.stderr.write("ERROR: operation-contracts.json or operation-contracts.csv missing.\n")
        return 1

    try:
        expected_payload = build_artifact_payload(repo_root)
    except Exception as exc:
        sys.stderr.write(f"ERROR building expected payload: {exc}\n")
        return 1

    expected_json_text = json.dumps(expected_payload, indent=2, sort_keys=False) + "\n"
    expected_csv_text = render_csv_text(expected_payload["operation_contracts"])

    actual_json_text = json_path.read_text(encoding="utf-8")
    actual_csv_text = csv_path.read_text(encoding="utf-8")

    try:
        data = json.loads(actual_json_text)
    except Exception as exc:
        sys.stderr.write(f"ERROR parsing JSON: {exc}\n")
        return 1

    valid_ids = load_valid_consumer_ids(repo_root)
    instances = data.get("operation_contracts", [])
    if not instances:
        sys.stderr.write("ERROR: No operation_contracts found in JSON.\n")
        return 1

    for idx, inst in enumerate(instances):
        errs = validate_operation_instance(inst, valid_consumer_ids=valid_ids)
        if errs:
            sys.stderr.write(f"ERROR in JSON instance #{idx} ({inst.get('consumer_id')}): {errs}\n")
            return 1

    if data.get("denominator_accounting") != expected_payload["denominator_accounting"]:
        sys.stderr.write("ERROR: denominator_accounting in JSON does not match re-derived values.\n")
        return 1

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        expected_fieldnames = _csv_fieldnames_for_instances(expected_payload["operation_contracts"])
        if fieldnames != expected_fieldnames:
            sys.stderr.write(f"ERROR: CSV header {fieldnames} != {expected_fieldnames}\n")
            return 1
        csv_instances = [csv_row_to_instance(r) for r in reader]

    if len(csv_instances) != len(instances):
        sys.stderr.write("ERROR: CSV row count does not match JSON instance count.\n")
        return 1

    for idx, c_inst in enumerate(csv_instances):
        errs = validate_operation_instance(c_inst, valid_consumer_ids=valid_ids)
        if errs:
            sys.stderr.write(f"ERROR in CSV instance #{idx}: {errs}\n")
            return 1

    if csv_instances != instances:
        sys.stderr.write("ERROR: Deserialized CSV instances do not equal JSON instances.\n")
        return 1

    if actual_json_text.encode("utf-8") != expected_json_text.encode("utf-8"):
        sys.stderr.write("ERROR: Committed operation-contracts.json is not byte-identical to generated payload.\n")
        return 1

    if actual_csv_text.encode("utf-8") != expected_csv_text.encode("utf-8"):
        sys.stderr.write("ERROR: Committed operation-contracts.csv is not byte-identical to generated CSV.\n")
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B05 Operation Contracts Validator & Generator")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
        help="Path to repository root",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory containing operation-contracts.json and operation-contracts.csv",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Regenerate operation-contracts.json and operation-contracts.csv",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate existing operation-contracts.json and operation-contracts.csv",
    )
    args = parser.parse_args(argv)

    if args.generate:
        write_artifacts(args.repo_root, args.out_dir)

    if args.validate or not args.generate:
        return validate_artifacts(args.repo_root, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
