"""B08 Cross-Store Operational Guarantees Adapter & Contract Verifier.

Scoped to research/operations/udb-wave8/B08/ per DUX-NOTE-SYNTHESIS.md,
DUX-NOTE-CORRECTION.md, and B08-F5. Consumes only pinned repository files,
.agent-receipts/udb-wave8-inputs/, and research/operations/udb-wave8/B08/dux-requests/
receipts. When those gitignored/untracked inputs are absent (a clean checkout) it falls
back to the committed frozen metadata fixtures in research/operations/udb-wave8/B08/fixtures/,
under the same pinned sha256 checks (see resolve_wave8_inputs). Performs zero network calls,
zero live database/store connections, and zero mutations outside B08.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE_COMMIT_SHA = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
BASE_COMMIT_TIMESTAMP = "2026-10-15T07:06:22Z"

PINNED_DUX_REQ_B08_01_CMD_SHA256 = (
    "ce7d734fe26c48fdbdf0678897c10176e2942f4868fb3c6638be3dd8fc7348d4"
)
PINNED_DUX_REQ_B08_01_OUT_SHA256 = (
    "74d784664ffca2b9b268738641880b9adc0d56e128319e80b61cad9048cbfaf2"
)
PINNED_DUX_REQ_B08_02_CMD_SHA256 = (
    "767b19c75b0fcecef4655c7ef71a0c2a2f050a2909d25dfd09a70de9c5c01a19"
)
PINNED_DUX_REQ_B08_02_OUT_SHA256 = (
    "e3ce0173f333b159ee1d706f35b061f8d81c9cd52fc9b93807b98ff54cc5cc69"
)
PINNED_DUX_REQ_B08_03_CMD_SHA256 = (
    "8f561df0c2e6d58de77ec19997346a6ad99836dd2d54d5fa8a1fafcea51a6b0a"
)
PINNED_DUX_REQ_B08_03_OUT_SHA256 = (
    "dfe2256fd1c51cbbfb1276faa6dd27342209760b5ecbaf2b80e0112551c5df68"
)
PINNED_REAL_RUN_RECEIPT_SHA256 = (
    "9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d"
)
PINNED_STATE_JSON_SHA256 = (
    "caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4"
)
PINNED_RESTORE_DRILL_VERIFY_SHA256 = (
    "3fe0dfc48e5f4e3e2000b0813b59d60a8500503f68c89596e4b09a0b91dad856"
)

# The report remains pinned to BASE_COMMIT_SHA. This exact later source only
# permits replay of that historical report; it does not prove current recovery.
PINNED_COMPATIBLE_MAIN_RESTORE_SHA256 = "19686bb0b0a5d1ced48b1cbdb60c817869529450e2042a4aa5a0207bbf07114a"

# Clean-checkout fallback: committed frozen metadata fixtures. The live inputs
# (.agent-receipts/..., B08/dux-requests/...) are used unchanged whenever present.
B08_REL_DIR = "research/operations/udb-wave8/B08"
LIVE_INPUTS_REL = ".agent-receipts/udb-wave8-inputs"
LIVE_CENSUS_REL = f"{B08_REL_DIR}/dux-requests/DUX-REQ-B08-01.out"
FIXTURES_REL = f"{B08_REL_DIR}/fixtures"
FIXTURE_KIND = "FROZEN_METADATA_TEST_FIXTURES_NOT_NEW_NATIVE_OBSERVATIONS"
FIXTURE_PROVENANCE_NAME = "PROVENANCE.json"
# Byte-identical fixtures reuse the PINNED_* constants above (STATE.json,
# REAL-RUN-RECEIPT.json, DUX-REQ-B08-01.out). The consumer matrix is a PROJECTION,
# so it has its own explicit projected-identity pins:
#   source = .agent-receipts/udb-wave8-inputs/consumer-matrix.csv (36 columns, 6029 rows)
#   projection = fixtures/consumer-matrix.projection.csv (consumer_id,store only)
PINNED_CONSUMER_MATRIX_SOURCE_SHA256 = (
    "c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118"
)
PINNED_CONSUMER_MATRIX_PROJECTION_SHA256 = (
    "496d0897cab7f3b0a3827239caf89c6878dd212419af8f914a662e7e24c1ad50"
)
# sha256 of "\n".join(source header names); guards the recorded source header.
PINNED_CONSUMER_MATRIX_SOURCE_COLUMNS_SHA256 = (
    "f3cf1ed7a1b1508b4556cc1b6096a935dd2b22e75a5892333b41cb816dd3d286"
)
CONSUMER_MATRIX_PROJECTED_COLUMNS: tuple[str, ...] = ("consumer_id", "store")
PINNED_CONSUMER_MATRIX_PROJECTION_ROWS = 6029
PINNED_CONSUMER_MATRIX_SOURCE_COLUMN_COUNT = 36

FROZEN_KEYS: tuple[str, ...] = (
    "consumer_id",
    "operation_id",
    "store_id",
    "source_version",
    "evidence_timestamp",
    "evidence_sha256",
    "status",
    "unknowns",
)

INSTANCE_KEYS: tuple[str, ...] = (
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

REQUIRED_19_KEYS: frozenset[str] = frozenset(FROZEN_KEYS + INSTANCE_KEYS)

VALID_STATUSES: frozenset[str] = frozenset(
    {"EVIDENCED", "PARTIAL", "BLOCKED", "CONFLICT", "UNKNOWN"}
)

VALID_RECORD_KINDS: frozenset[str] = frozenset(
    {"CURRENT_FACT", "DESIRED_GUARANTEE"}
)

VALID_RESTORE_STATUSES: frozenset[str] = frozenset(
    {"PASS", "FAIL", "CANNOT-VERIFY"}
)

EIGHT_DIMENSIONS: tuple[str, ...] = (
    "dependencies",
    "references",
    "versions",
    "time_semantics",
    "retention_erasure_security",
    "recovery_order",
    "workload_cost",
    "analytics_observability",
)

STORE_ID_RE: re.Pattern[str] = re.compile(
    r"^(pg|qdrant|redis|sqlite|graph|object|file|sheet|browser|external|unknown)"
    r":(fly|pro|mini|m5|gcloud|gdrive|github|client|unknown)"
    r":[a-z0-9._-]+(/[a-zA-Z0-9._*-]+)?$"
)

# Exact producer semantics from DUX-REQ-B08-01.cmd.sh:4-6
PRODUCER_FAMILY_SUFFIX_RE: re.Pattern[str] = re.compile(
    r"[-_]?[0-9a-f]{12,24}$"
)
PRODUCER_STORE_KEYWORDS: tuple[str, ...] = (
    "event_delivery",
    "object_storage",
    "external",
)

CLIENTS_LEAD_METADATA_SQL_REF = "scripts/ci/restore_drill_verify.py:221-227"
CLIENTS_INVARIANT_CHECKS_REF = "scripts/ci/restore_drill_verify.py:122"
CLIENTS_VIOLATIONS_DISPATCH_REF = "scripts/ci/restore_drill_verify.py:281-288,345"


class ContractViolationError(ValueError):
    """Raised when a B08 operation instance, receipt, or guarantee record violates conventions."""


class _BoundaryArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractViolationError("B08_E_ARGUMENTS: invalid CLI arguments")


def sha256_file(path: Path) -> str:
    """Compute hex SHA256 of a file on disk."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_field(
    value: Any,
    status: str,
    evidence_ref: str | None,
) -> dict[str, Any]:
    """Build a B05-compliant 11-instance-key field object."""
    if status not in VALID_STATUSES:
        raise ContractViolationError('B08_E_FIELD_STATUS: Invalid field status')
    return {
        "value": value,
        "status": status,
        "evidence_ref": evidence_ref,
    }


def extract_consumer_family(consumer_id: str) -> str:
    """Extract producer family label per DUX-REQ-B08-01.cmd.sh:4-6.

    Removes only a terminal optional hyphen/underscore plus 12-24 lowercase hex
    characters. Preserves complete family labels such as engine_pro, engine_mini,
    runtime-pro-plist, NOTEBOOK-CONTAINER-REFERENCE-NLM, and engine_M5.
    """
    if not isinstance(consumer_id, str) or not consumer_id:
        raise ContractViolationError("consumer_id must be a non-empty string")
    return PRODUCER_FAMILY_SUFFIX_RE.sub("", consumer_id)


def is_multi_store_or_boundary_store(store: str | None) -> bool:
    """Return True iff store matches the exact DUX-REQ-B08-01.cmd.sh:4-6 predicate."""
    s = store or ""
    return ";" in s or any(k in s for k in PRODUCER_STORE_KEYWORDS)


def validate_store_id(store_id: str, unknowns: list[str]) -> None:
    """Enforce CONTRACT-CONVENTIONS.md store_id grammar (Finding X1)."""
    if not isinstance(store_id, str) or not STORE_ID_RE.match(store_id):
        raise ContractViolationError(
            'B08_E_STORE_ID: store_id violates <engine>:<platform>:<instance>[/<subcontainer>]'
        )
    if store_id == "unknown:unknown:unknown":
        has_proposed = any(
            isinstance(u, str) and u.startswith("STORE_ID_PROPOSED:")
            for u in unknowns
        )
        if not has_proposed:
            raise ContractViolationError(
                "store_id 'unknown:unknown:unknown' requires 'STORE_ID_PROPOSED:<value>' in unknowns"
            )


def validate_operation_instance(
    record: dict[str, Any],
    known_consumer_ids: set[str],
    allow_b05_assigned: bool = False,
) -> None:
    """Validate a 19-key + x_-prefixed operation instance per CONTRACT-CONVENTIONS.md."""
    keys = set(record.keys())
    missing = REQUIRED_19_KEYS - keys
    if missing:
        raise ContractViolationError(
            'B08_E_REQUIRED_FIELDS: Missing required 19-key contract fields'
        )

    extra_keys = keys - REQUIRED_19_KEYS
    illegal_extras = [k for k in extra_keys if not k.startswith("x_")]
    if illegal_extras:
        raise ContractViolationError(
            "B08_E_EXTRA_KEYS: Extra keys without 'x_' prefix are forbidden (Finding X4)"
        )

    consumer_id = record["consumer_id"]
    if consumer_id not in known_consumer_ids:
        raise ContractViolationError(
            'B08_E_CONSUMER_ID: consumer_id not found in consumer-matrix.csv + LEAD-DELTA.json (Finding X10)'
        )

    unknowns = record["unknowns"]
    if not isinstance(unknowns, list) or not all(
        isinstance(item, str) for item in unknowns
    ):
        raise ContractViolationError("unknowns must be a list of strings")

    operation_id = record["operation_id"]
    if not allow_b05_assigned:
        if operation_id != "UNASSIGNED_B05":
            raise ContractViolationError(
                "B08_E_OPERATION_ID: B08 operation_id must be 'UNASSIGNED_B05' (Finding X2)"
            )
        if "OPERATION_ID_PENDING_B05" not in unknowns:
            raise ContractViolationError(
                "operation_id 'UNASSIGNED_B05' requires 'OPERATION_ID_PENDING_B05' in unknowns (Finding X2)"
            )

    validate_store_id(record["store_id"], unknowns)

    status = record["status"]
    if status not in VALID_STATUSES:
        raise ContractViolationError(
            'B08_E_STATUS: Invalid top-level status (Finding X3)'
        )

    source_version = record["source_version"]
    evidence_timestamp = record["evidence_timestamp"]
    if not isinstance(source_version, str) or not source_version:
        raise ContractViolationError("source_version must be a non-empty string")
    if not isinstance(evidence_timestamp, str) or not evidence_timestamp:
        raise ContractViolationError("evidence_timestamp must be a non-empty string")
    if (
        source_version == BASE_COMMIT_SHA
        and evidence_timestamp == BASE_COMMIT_TIMESTAMP
        and "STATIC_SOURCE_ONLY" not in unknowns
    ):
        raise ContractViolationError(
            "Static repo evidence at base commit requires 'STATIC_SOURCE_ONLY' in unknowns (Finding X5)"
        )

    evidence_sha256 = record["evidence_sha256"]
    if not isinstance(evidence_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", evidence_sha256
    ):
        raise ContractViolationError(
            'B08_E_EVIDENCE_HASH: evidence_sha256 must be a 64-char lowercase hex string'
        )

    for ikey in INSTANCE_KEYS:
        fobj = record[ikey]
        if not isinstance(fobj, dict):
            raise ContractViolationError(
                'B08_E_INSTANCE_OBJECT: Instance key must be a dict object'
            )
        if set(fobj.keys()) != {"value", "status", "evidence_ref"}:
            raise ContractViolationError(
                "B08_E_INSTANCE_KEYS: Instance key must have exact keys {'value', 'status', 'evidence_ref'}"
            )
        if fobj["status"] not in VALID_STATUSES:
            raise ContractViolationError(
                'B08_E_INSTANCE_STATUS: Instance key has invalid status'
            )
        if fobj["evidence_ref"] is not None and not isinstance(
            fobj["evidence_ref"], str
        ):
            raise ContractViolationError(
                'B08_E_INSTANCE_REFERENCE: Instance key evidence_ref must be str or None'
            )

    record_kind = record.get("x_record_kind")
    if record_kind not in VALID_RECORD_KINDS:
        raise ContractViolationError(
            'B08_E_RECORD_KIND: x_record_kind must be one of CURRENT_FACT or DESIRED_GUARANTEE'
        )
    if record_kind == "DESIRED_GUARANTEE" and status == "EVIDENCED":
        raise ContractViolationError(
            "DESIRED_GUARANTEE record cannot have status='EVIDENCED' without proved runtime closure"
        )

    dim = record.get("x_guarantee_dimension")
    if dim not in EIGHT_DIMENSIONS:
        raise ContractViolationError(
            'B08_E_DIMENSION: x_guarantee_dimension must be one of the eight dimensions'
        )


def validate_sibling_gate_constraints(
    records: list[dict[str, Any]],
    state_json: dict[str, Any],
    block_closed: bool,
) -> None:
    """Enforce fail-closed rules when B01, B02, B03, or B04 evidence is unclosed (Findings X8, B08-F3)."""
    obs = state_json.get("observations", {})
    restore_ok = bool(
        state_json.get(
            "real_backup_restore_success_proved",
            obs.get("real_backup_restore_success_proved", False),
        )
    )
    qdrant_ok = bool(
        state_json.get(
            "qdrant_model_binding_proved",
            obs.get("qdrant_model_binding_proved", False),
        )
    )
    redis_obs = state_json.get("redis", obs.get("redis", {}))
    redis_ok = (
        isinstance(redis_obs, dict)
        and redis_obs.get("pro") == "EVIDENCED"
        and redis_obs.get("mini") == "EVIDENCED"
    )
    denom_ok = state_json.get("active_consumer_denominator") not in (None, "UNKNOWN")

    if block_closed and not (restore_ok and qdrant_ok and redis_ok and denom_ok):
        raise ContractViolationError(
            "block_closed cannot be True while B01 recovery, B02 Redis, B03 denominator, or B04 Qdrant remain unclosed"
        )

    for rec in records:
        dim = rec.get("x_guarantee_dimension")
        status = rec.get("status")
        unknowns = rec.get("unknowns", [])
        store_id = rec.get("store_id", "")
        targets = rec.get("x_target_store_ids", [])
        all_stores = [store_id] + (targets if isinstance(targets, list) else [])

        if dim == "recovery_order" and not restore_ok:
            if status == "EVIDENCED":
                raise ContractViolationError(
                    "recovery_order record cannot be EVIDENCED while real_backup_restore_success_proved is False"
                )
            if "B01_RECOVERY_EVIDENCE_MISSING" not in unknowns:
                raise ContractViolationError(
                    "recovery_order record must carry 'B01_RECOVERY_EVIDENCE_MISSING' in unknowns"
                )

        if any(s.startswith("redis:") for s in all_stores) and not redis_ok:
            if status == "EVIDENCED":
                raise ContractViolationError(
                    "Redis cross-store record cannot be EVIDENCED while B02 Redis observer is AUTHORIZATION_REQUIRED"
                )
            if "B02_REDIS_OBSERVER_EVIDENCE_MISSING" not in unknowns:
                raise ContractViolationError(
                    "Redis cross-store record must carry 'B02_REDIS_OBSERVER_EVIDENCE_MISSING' in unknowns"
                )

        if any(s.startswith("qdrant:") for s in all_stores) and not qdrant_ok:
            if status == "EVIDENCED":
                raise ContractViolationError(
                    "Qdrant cross-store record cannot be EVIDENCED while qdrant_model_binding_proved is False"
                )
            if "B04_QDRANT_PROD_METADATA_MISSING" not in unknowns:
                raise ContractViolationError(
                    "Qdrant cross-store record must carry 'B04_QDRANT_PROD_METADATA_MISSING' in unknowns"
                )


def normalize_restore_receipt(receipt_json: dict[str, Any]) -> dict[str, Any]:
    """Normalize REAL-RUN-RECEIPT.json from its single TERMINAL event's verifier_summary.

    Raises ContractViolationError when:
    - receipt_json is not a dict or 'events' list is missing/empty
    - there are zero or more than one TERMINAL events
    - 'verifier_summary' or 'invariants' is missing, empty, or malformed
    - 'aggregate' is missing or outside {PASS, FAIL, CANNOT-VERIFY}
    - a relation appears twice or has status outside {PASS, FAIL, CANNOT-VERIFY}
    - a relation's reason_classes is not a dict of str -> non-negative int
    - a relation has status=='PASS' with non-zero reason_classes or non-PASS with zero reason_classes
    """
    if not isinstance(receipt_json, dict):
        raise ContractViolationError("Restore receipt must be a JSON object")

    events = receipt_json.get("events")
    if not isinstance(events, list) or not events:
        raise ContractViolationError("Restore receipt missing non-empty 'events' list")

    terminal_events = [
        ev
        for ev in events
        if isinstance(ev, dict) and ev.get("event") == "TERMINAL"
    ]
    if len(terminal_events) != 1:
        raise ContractViolationError(
            'B08_E_TERMINAL_COUNT: Restore receipt must contain exactly 1 TERMINAL event'
        )

    terminal = terminal_events[0]
    verifier_summary = terminal.get("verifier_summary")
    if not isinstance(verifier_summary, dict):
        raise ContractViolationError(
            "TERMINAL event missing dict 'verifier_summary'"
        )

    aggregate = verifier_summary.get("aggregate")
    if aggregate not in VALID_RESTORE_STATUSES:
        raise ContractViolationError(
            'B08_E_RESTORE_AGGREGATE: Invalid or missing verifier_summary.aggregate'
        )

    invariants = verifier_summary.get("invariants")
    if not isinstance(invariants, list) or not invariants:
        raise ContractViolationError(
            "verifier_summary.invariants must be a non-empty list"
        )

    relations: dict[str, dict[str, Any]] = {}
    for item in invariants:
        if not isinstance(item, dict):
            raise ContractViolationError("Each invariant entry must be a dict")
        relation = item.get("relation")
        if not isinstance(relation, str) or not relation.strip():
            raise ContractViolationError(
                'B08_E_RESTORE_RELATION: Invariant entry has invalid relation name'
            )
        if relation in relations:
            raise ContractViolationError(
                'B08_E_RESTORE_DUPLICATE: Duplicate relation in verifier_summary.invariants'
            )

        rel_status = item.get("status")
        if rel_status not in VALID_RESTORE_STATUSES:
            raise ContractViolationError(
                'B08_E_RESTORE_STATUS: Relation has invalid status'
            )

        reason_classes = item.get("reason_classes")
        if not isinstance(reason_classes, dict):
            raise ContractViolationError(
                'B08_E_RESTORE_REASONS: Relation reason_classes must be a dict'
            )

        normalized_reasons: dict[str, int] = {}
        for rkey, rval in reason_classes.items():
            if (
                not isinstance(rkey, str)
                or not rkey
                or isinstance(rval, bool)
                or not isinstance(rval, int)
                or rval < 0
            ):
                raise ContractViolationError(
                    'B08_E_RESTORE_REASON: Relation has malformed reason_class'
                )
            normalized_reasons[rkey] = rval

        total_reasons = sum(normalized_reasons.values())
        if rel_status == "PASS" and total_reasons > 0:
            raise ContractViolationError(
                'B08_E_RESTORE_PASS: Relation is PASS but has non-zero reason_classes'
            )
        if rel_status in {"FAIL", "CANNOT-VERIFY"} and total_reasons == 0:
            raise ContractViolationError(
                'B08_E_RESTORE_FAILURE: Relation is non-PASS but has zero positive reason_classes'
            )

        relations[relation] = {
            "status": rel_status,
            "reason_classes": normalized_reasons,
        }

    return {
        "aggregate": aggregate,
        "relations": relations,
        "terminal_status": terminal.get("status"),
        "top_level_error_present": bool(
            verifier_summary.get("top_level_error_present", False)
        ),
        "rows_counts_and_raw_errors_exported": bool(
            verifier_summary.get("rows_counts_and_raw_errors_exported", False)
        ),
    }


def evaluate_ce01_restore_verdict_and_epistemology(
    receipt_json: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate CE-01 restore precedence and subcheck epistemology on normalized receipt.

    Enforces DUX-NOTE-CORRECTION.md §2:
    - Normalizes the single TERMINAL event's verifier_summary.invariants.
    - Computes overall status with CANNOT-VERIFY > FAIL > PASS precedence (empty set raises).
    - Requires computed overall to equal producer verifier_summary.aggregate.
    - Attributes VIOLATION strictly per relation: only clients' own VIOLATION count
      (with MISSING_COLUMN == 0 on clients) supports the inference that lead_metadata
      existed on clients, bound to scripts/ci/restore_drill_verify.py:221-227.
    - Keeps exact_failing_clients_subcheck_known=False and exact_conversations_sql_error_known=False.
    """
    normalized = normalize_restore_receipt(receipt_json)
    relations = normalized["relations"]
    if not relations:
        raise ContractViolationError("Empty relation set cannot become PASS")

    statuses = {rel_info["status"] for rel_info in relations.values()}
    if "CANNOT-VERIFY" in statuses:
        computed_overall = "CANNOT-VERIFY"
    elif "FAIL" in statuses:
        computed_overall = "FAIL"
    elif statuses == {"PASS"}:
        computed_overall = "PASS"
    else:
        raise ContractViolationError('B08_E_RESTORE_STATUSES: Unexpected relation statuses')

    producer_aggregate = normalized["aggregate"]
    if computed_overall != producer_aggregate:
        raise ContractViolationError(
            'B08_E_RESTORE_CONTRADICTION: Aggregate contradiction'
        )

    clients_info = relations.get("clients")
    if clients_info is None:
        raise ContractViolationError(
            "Required relation 'clients' missing from verifier_summary.invariants"
        )

    clients_status = clients_info["status"]
    clients_reasons = clients_info["reason_classes"]
    clients_violation_count = clients_reasons.get("VIOLATION", 0)
    clients_missing_col_count = clients_reasons.get("MISSING_COLUMN", 0)

    lead_metadata_existed = (
        clients_status == "FAIL"
        and clients_violation_count >= 1
        and clients_missing_col_count == 0
    )

    conversations_info = relations.get(
        "conversations", {"status": "UNKNOWN", "reason_classes": {}}
    )
    conversations_unmeasured = conversations_info["reason_classes"].get(
        "UNMEASURED_CHECK", 0
    )
    total_unmeasured = sum(
        r["reason_classes"].get("UNMEASURED_CHECK", 0)
        for r in relations.values()
    )

    return {
        "overall_status": computed_overall,
        "producer_aggregate": producer_aggregate,
        "aggregate_matches_producer": True,
        "fail_masked_by_cannot_verify": (
            "CANNOT-VERIFY" in statuses and "FAIL" in statuses
        ),
        "relations": relations,
        "clients_status": clients_status,
        "clients_violation_count": clients_violation_count,
        "clients_lead_metadata_column_existed_in_backup": lead_metadata_existed,
        "clients_lead_metadata_evidence_ref": (
            CLIENTS_LEAD_METADATA_SQL_REF if lead_metadata_existed else None
        ),
        "clients_invariant_checks_ref": CLIENTS_INVARIANT_CHECKS_REF,
        "clients_violations_dispatch_ref": CLIENTS_VIOLATIONS_DISPATCH_REF,
        "exact_failing_clients_subcheck_known": False,
        "exact_conversations_sql_error_known": False,
        "conversations_unmeasured_check_count": conversations_unmeasured,
        "unmeasured_check_count": total_unmeasured,
    }


def evaluate_ce02_polymorphic_provenance(
    migration_sql: str,
) -> dict[str, Any]:
    """Evaluate CE-02 on 154_asset_provenance.sql for polymorphic cross-store refs."""
    has_asset_kind_enum = all(
        token in migration_sql
        for token in (
            "'war_room_draft'",
            "'intel_finding'",
            "'kg_entity'",
            "'crm_enrichment_lookup'",
            "'compliance_alert'",
        )
    )
    has_text_asset_id = "asset_id TEXT NOT NULL" in migration_sql
    has_foreign_key = "REFERENCES " in migration_sql.upper()
    return {
        "polymorphic_asset_types_present": has_asset_kind_enum,
        "unconstrained_text_asset_id": has_text_asset_id,
        "has_db_foreign_key": has_foreign_key,
        "cross_store_dangling_pointer_possible": (
            has_asset_kind_enum and has_text_asset_id and not has_foreign_key
        ),
        "status": (
            "CONFLICT"
            if (has_asset_kind_enum and not has_foreign_key)
            else "PARTIAL"
        ),
    }


def evaluate_ce03_organism_bridge(
    bridge_source: str,
) -> dict[str, Any]:
    """Evaluate CE-03 on scripts/pg-to-organism-bridge.py."""
    truncates_2000 = (
        "if len(serialised) <= 2000:" in bridge_source
        and 'truncated["_pg_bridge_truncated"] = True' in bridge_source
    )
    wallclock_fallback = (
        'f"pg-{channel}-{datetime.now(timezone.utc).timestamp()}"'
        in bridge_source
    )
    redis_best_effort = (
        "redis XADD failed (non-fatal, stream degraded)" in bridge_source
    )
    return {
        "payload_truncated_at_2000_bytes": truncates_2000,
        "wallclock_correlation_fallback": wallclock_fallback,
        "redis_xadd_non_atomic_best_effort": redis_best_effort,
        "lossy_fanout_detected": (
            truncates_2000 and wallclock_fallback and redis_best_effort
        ),
    }


def evaluate_ce04_qdrant_health_probe(
    health_source: str,
) -> dict[str, Any]:
    """Evaluate CE-04 on unified_health_service.py check_qdrant."""
    checks_only_url_attr = (
        "if client.qdrant_url and client.collection_name:" in health_source
    )
    has_network_call_in_check_qdrant = False
    match = re.search(
        r"async def check_qdrant\(self\)\s*->\s*HealthCheckResult:(.*?)(?:\n    async def |\Z)",
        health_source,
        flags=re.DOTALL,
    )
    if match:
        body = match.group(1)
        has_network_call_in_check_qdrant = "await " in body or "httpx" in body
    return {
        "checks_only_url_attribute": checks_only_url_attr,
        "performs_live_io": has_network_call_in_check_qdrant,
        "false_positive_ok_possible": (
            checks_only_url_attr and not has_network_call_in_check_qdrant
        ),
    }


def evaluate_ce05_war_room_cost_masking(
    route_ts_source: str,
) -> dict[str, Any]:
    """Evaluate CE-05 on apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts."""
    catches_42p01 = '.code === "42P01"' in route_ts_source
    returns_zero_grand_total = "grand_total_usd: 0" in route_ts_source
    return {
        "catches_undefined_table_42p01": catches_42p01,
        "returns_zero_usd_on_missing_table": returns_zero_grand_total,
        "false_zero_cost_telemetry": catches_42p01 and returns_zero_grand_total,
    }


def evaluate_ce06_outbox_and_cost_retention(
    outbox_py_source: str,
    outbox_prune_sh_source: str,
    llm_cost_recorder_source: str,
) -> dict[str, Any]:
    """Evaluate CE-06 on outbox.py, outbox-prune.sh, and llm_cost_recorder.py."""
    claims_60m_window = (
        "max_age_minutes: int = 60" in outbox_py_source
        and "created_at > NOW() - INTERVAL '{int(max_age_minutes)} minutes'"
        in outbox_py_source
    )
    prunes_only_consumed = (
        "WHERE consumed_at IS NOT NULL" in outbox_py_source
        and "prune_consumed" in outbox_prune_sh_source
    )
    claims_90d_retention = (
        'os.getenv("LLM_COST_JSONL_RETENTION_DAYS", "90")'
        in llm_cost_recorder_source
    )
    retention_attr_uses = len(
        re.findall(r"\bself\.retention_days\b", llm_cost_recorder_source)
    )
    has_jsonl_prune_logic = retention_attr_uses > 1
    return {
        "outbox_claim_window_60m": claims_60m_window,
        "outbox_prune_requires_processed_at_not_null": prunes_only_consumed,
        "unconsumed_older_than_60m_orphaned_forever": (
            claims_60m_window and prunes_only_consumed
        ),
        "llm_cost_jsonl_claims_90d_retention": claims_90d_retention,
        "llm_cost_jsonl_prune_implemented": has_jsonl_prune_logic,
        "llm_cost_retention_unimplemented": (
            claims_90d_retention and not has_jsonl_prune_logic
        ),
    }


def scan_consumer_matrix(csv_path: Path) -> dict[str, Any]:
    """Scan consumer-matrix.csv using the exact DUX-REQ-B08-01.cmd.sh producer semantics."""
    known_ids: set[str] = {"mini.restore_drill"}
    rows_by_id: dict[str, dict[str, str]] = {}
    by_store: dict[str, int] = {}
    by_family: dict[str, int] = {}
    total_rows = 0
    multi_store_rows = 0

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        for row in reader:
            total_rows += 1
            cid = row["consumer_id"]
            known_ids.add(cid)
            rows_by_id[cid] = row
            store = row.get("store") or ""
            if is_multi_store_or_boundary_store(store):
                multi_store_rows += 1
                by_store[store] = by_store.get(store, 0) + 1
                fam = extract_consumer_family(cid)
                by_family[fam] = by_family.get(fam, 0) + 1

    sorted_by_store = dict(
        sorted(by_store.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    sorted_by_family = dict(
        sorted(by_family.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    top_stores = dict(list(sorted_by_store.items())[:25])
    return {
        "total_rows": total_rows,
        "column_count": len(columns),
        "columns": columns,
        "multi_store_or_boundary_rows": multi_store_rows,
        "by_store": sorted_by_store,
        "by_family": sorted_by_family,
        "top_by_store": top_stores,
        "known_consumer_ids": known_ids,
        "rows_by_id": rows_by_id,
    }


def load_pinned_census_receipt(
    receipt_path: Path,
    expected_sha256: str | None = PINNED_DUX_REQ_B08_01_OUT_SHA256,
) -> dict[str, Any]:
    """Load DUX-REQ-B08-01.out and verify its SHA256 against the pinned table."""
    if not receipt_path.is_file():
        raise ContractViolationError(
            'B08_E_CENSUS_MISSING: Pinned census receipt not found'
        )
    actual_sha = sha256_file(receipt_path)
    if expected_sha256 is not None and actual_sha != expected_sha256:
        raise ContractViolationError(
            'B08_E_CENSUS_PIN: SHA256 mismatch for census receipt'
        )
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ContractViolationError(
            'B08_E_CENSUS_JSON: Invalid JSON in census receipt'
        ) from None
    if not isinstance(data, dict):
        raise ContractViolationError("Census receipt root must be a dict")
    return data


def compare_census_to_receipt(
    scanned: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    """Require exact equality of total_rows, multi_store_or_boundary_rows, by_store, and by_family."""
    for key in (
        "total_rows",
        "multi_store_or_boundary_rows",
        "by_store",
        "by_family",
    ):
        if scanned.get(key) != receipt.get(key):
            raise ContractViolationError(
                'B08_E_CENSUS_MISMATCH: Census mismatch'
            )


@dataclass(frozen=True)
class Wave8Inputs:
    """Resolved Wave 8 input paths and where each came from ("live" or "fixture")."""

    state_path: Path
    receipt_path: Path
    matrix_path: Path
    census_path: Path
    matrix_source_columns: tuple[str, ...] | None
    origins: dict[str, str]


def _require_fixture_sha(path: Path, expected_sha256: str, label: str) -> None:
    """Byte-identical fixture check: same pinned sha256 as the live input it stands in for."""
    if not path.is_file():
        raise ContractViolationError('B08_E_FIXTURE_MISSING: Committed fixture missing')
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ContractViolationError(
            'B08_E_FIXTURE_PIN: Fixture SHA256 mismatch'
        )


def verify_projected_consumer_matrix_fixture(fixtures_dir: Path) -> tuple[str, ...]:
    """Projected-identity check for the consumer-matrix fixture; returns the source header.

    The fixture keeps only the columns the adapter reads (consumer_id, store), so it can
    never equal the source bytes. Its identity is the pinned projection sha256 plus a
    PROVENANCE.json entry that must name the pinned source sha256, row count and source
    header (itself pinned by hash) so csv_column_count stays the measured source value.
    """
    projection = fixtures_dir / "consumer-matrix.projection.csv"
    _require_fixture_sha(
        projection,
        PINNED_CONSUMER_MATRIX_PROJECTION_SHA256,
        "consumer-matrix projection",
    )
    provenance_path = fixtures_dir / FIXTURE_PROVENANCE_NAME
    if not provenance_path.is_file():
        raise ContractViolationError(
            'B08_E_PROVENANCE_MISSING: Committed fixture provenance missing'
        )
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ContractViolationError(
            'B08_E_PROVENANCE_JSON: Invalid JSON in fixture provenance'
        ) from None
    entries = provenance.get("entries") if isinstance(provenance, dict) else None
    entry = next(
        (
            item
            for item in (entries if isinstance(entries, list) else [])
            if isinstance(item, dict) and item.get("fixture") == projection.name
        ),
        None,
    )
    if entry is None or provenance.get("kind") != FIXTURE_KIND:
        raise ContractViolationError(
            "B08_E_PROVENANCE_ENTRY: Fixture provenance has no 'consumer-matrix.projection.csv' entry of required kind"
        )
    expected = {
        "kind": FIXTURE_KIND,
        "transform": "projection",
        "source_sha256": PINNED_CONSUMER_MATRIX_SOURCE_SHA256,
        "output_sha256": PINNED_CONSUMER_MATRIX_PROJECTION_SHA256,
        "projected_columns": list(CONSUMER_MATRIX_PROJECTED_COLUMNS),
        "rows": PINNED_CONSUMER_MATRIX_PROJECTION_ROWS,
        "source_column_count": PINNED_CONSUMER_MATRIX_SOURCE_COLUMN_COUNT,
        "source_columns_sha256": PINNED_CONSUMER_MATRIX_SOURCE_COLUMNS_SHA256,
    }
    for key, wanted in expected.items():
        if entry.get(key) != wanted:
            raise ContractViolationError(
                'B08_E_PROJECTION_IDENTITY: Projected-identity mismatch'
            )
    source_columns = entry.get("source_columns")
    if (
        not isinstance(source_columns, list)
        or not all(isinstance(col, str) for col in source_columns)
        or len(source_columns) != PINNED_CONSUMER_MATRIX_SOURCE_COLUMN_COUNT
        or hashlib.sha256("\n".join(source_columns).encode("utf-8")).hexdigest()
        != PINNED_CONSUMER_MATRIX_SOURCE_COLUMNS_SHA256
        or not set(CONSUMER_MATRIX_PROJECTED_COLUMNS) <= set(source_columns)
    ):
        raise ContractViolationError(
            'B08_E_PROJECTION_HEADER: Recorded source header fails the pinned header hash'
        )
    return tuple(source_columns)


def scan_projected_consumer_matrix(
    csv_path: Path, source_columns: tuple[str, ...]
) -> dict[str, Any]:
    """Scan the committed projection with the exact scan_consumer_matrix semantics.

    columns/column_count report the recorded source header (the live value); rows_by_id
    holds only the projected columns.
    """
    scanned = scan_consumer_matrix(csv_path)
    if tuple(scanned["columns"]) != CONSUMER_MATRIX_PROJECTED_COLUMNS:
        raise ContractViolationError(
            'B08_E_MATRIX_HEADER: Projected consumer matrix header differs from required fields'
        )
    if scanned["total_rows"] != PINNED_CONSUMER_MATRIX_PROJECTION_ROWS:
        raise ContractViolationError(
            'B08_E_MATRIX_ROWS: Projected consumer matrix has unexpected row count'
        )
    scanned["columns"] = list(source_columns)
    scanned["column_count"] = len(source_columns)
    return scanned


def resolve_wave8_inputs(repo_root: Path) -> Wave8Inputs:
    """Use the live inputs when present, else the committed fixtures (same pinned checks)."""
    live_inputs = repo_root / LIVE_INPUTS_REL
    fixtures_dir = repo_root / FIXTURES_REL
    origins: dict[str, str] = {}

    def pick(name: str, live: Path, fixture_name: str, pinned_sha256: str) -> Path:
        if live.is_file():
            origins[name] = "live"
            return live
        fixture = fixtures_dir / fixture_name
        _require_fixture_sha(fixture, pinned_sha256, fixture_name)
        origins[name] = "fixture"
        return fixture

    state_path = pick(
        "state", live_inputs / "STATE.json", "STATE.json", PINNED_STATE_JSON_SHA256
    )
    receipt_path = pick(
        "receipt",
        live_inputs / "REAL-RUN-RECEIPT.json",
        "REAL-RUN-RECEIPT.json",
        PINNED_REAL_RUN_RECEIPT_SHA256,
    )
    census_path = pick(
        "census",
        repo_root / LIVE_CENSUS_REL,
        "DUX-REQ-B08-01.out",
        PINNED_DUX_REQ_B08_01_OUT_SHA256,
    )
    live_matrix = live_inputs / "consumer-matrix.csv"
    matrix_columns: tuple[str, ...] | None
    if live_matrix.is_file():
        matrix_path, matrix_columns, origins["matrix"] = live_matrix, None, "live"
    else:
        matrix_columns = verify_projected_consumer_matrix_fixture(fixtures_dir)
        matrix_path = fixtures_dir / "consumer-matrix.projection.csv"
        origins["matrix"] = "fixture"
    return Wave8Inputs(
        state_path=state_path,
        receipt_path=receipt_path,
        matrix_path=matrix_path,
        census_path=census_path,
        matrix_source_columns=matrix_columns,
        origins=origins,
    )


def scan_wave8_consumer_matrix(inputs: Wave8Inputs) -> dict[str, Any]:
    """Scan the resolved consumer matrix: the live file as-is, or the verified projection."""
    if inputs.matrix_source_columns is None:
        return scan_consumer_matrix(inputs.matrix_path)
    return scan_projected_consumer_matrix(
        inputs.matrix_path, inputs.matrix_source_columns
    )


def build_b08_operation_instances(
    repo_root: Path,
    state_sha: str = PINNED_STATE_JSON_SHA256,
    receipt_sha: str = PINNED_REAL_RUN_RECEIPT_SHA256,
    restore_source: Path | None = None,
) -> list[dict[str, Any]]:
    """Construct the B08 19-key + x_-prefixed operation instances for current facts & desired guarantees."""
    file_hashes = {
        rel: sha256_file(
            restore_source
            if rel == "scripts/ci/restore_drill_verify.py" and restore_source is not None
            else repo_root / rel
        )
        for rel in (
            "scripts/pg-to-organism-bridge.py",
            "apps/backend-rag/backend/services/events/outbox.py",
            "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql",
            "apps/backend-rag/backend/db/migrations_v2/165_reconcile_schema_migrations_duplicates.sql",
            "scripts/outbox-prune.sh",
            "scripts/ci/restore_drill_verify.py",
            "apps/backend-rag/backend/services/observability/llm_cost_recorder.py",
            "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts",
        )
    }

    instances: list[dict[str, Any]] = [
        # 1. D12 Dependencies (Current Fact): Outbox PG -> pg_notify -> replay_unconsumed
        {
            "consumer_id": "src_e23395130cffca55",
            "operation_id": "UNASSIGNED_B05",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": file_hashes[
                "apps/backend-rag/backend/services/events/outbox.py"
            ],
            "status": "PARTIAL",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "B02_REDIS_OBSERVER_EVIDENCE_MISSING",
                "B03_DENOMINATOR_UNCLOSED",
            ],
            "principal": make_field(
                "backend-rag:events_outbox",
                "EVIDENCED",
                "apps/backend-rag/backend/services/events/outbox.py:181-236",
            ),
            "role": make_field("db_app_role_unverified", "UNKNOWN", None),
            "tenant": make_field("single_tenant_system", "PARTIAL", None),
            "authorization": make_field(
                "asyncpg_connection",
                "PARTIAL",
                "apps/backend-rag/backend/services/events/outbox.py:181-236",
            ),
            "transaction": make_field(
                "INSERT INTO events_outbox + SELECT pg_notify($1, $2) in caller tx",
                "EVIDENCED",
                "apps/backend-rag/backend/services/events/outbox.py:210-228",
            ),
            "effects": make_field(
                "Writes public.events_outbox, fires pg_notify, replays unconsumed within 60m window",
                "EVIDENCED",
                "apps/backend-rag/backend/services/events/outbox.py:210-419",
            ),
            "retries": make_field(
                "replay_unconsumed fetches consumed_at IS NULL AND created_at > NOW() - 60m",
                "EVIDENCED",
                "apps/backend-rag/backend/services/events/outbox.py:278-353",
            ),
            "idempotency": make_field(
                "acknowledge guards WHERE consumed_at IS NULL; handlers must dedupe _outbox_id",
                "PARTIAL",
                "apps/backend-rag/backend/services/events/outbox.py:239-275",
            ),
            "failure": make_field(
                "Unconsumed rows older than 60m are excluded by replay_unconsumed and never pruned by prune_consumed",
                "CONFLICT",
                "apps/backend-rag/backend/services/events/outbox.py:332-335",
            ),
            "retention": make_field(
                "prune_consumed deletes only consumed_at IS NOT NULL older than 30d; unconsumed >60m retained forever",
                "CONFLICT",
                "apps/backend-rag/backend/services/events/outbox.py:422-448",
            ),
            "recovery": make_field(
                "Outbox table checked in restore drill but downstream Redis/JSONL bus state unrecovered",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:43-50",
            ),
            "x_guarantee_dimension": "dependencies",
            "x_record_kind": "CURRENT_FACT",
            "x_counterexample_id": "CE-06",
            "x_target_store_ids": [
                "pg:fly:nuzantara-postgres/public",
                "redis:pro:6379/db0",
            ],
            "x_evidence_ref": "apps/backend-rag/backend/services/events/outbox.py:181-448",
        },
        # 2. D14 References (Current Fact): 154_asset_provenance.sql polymorphic pointers
        {
            "consumer_id": "src_54ed3c033ab03a89",
            "operation_id": "UNASSIGNED_B05",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": file_hashes[
                "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql"
            ],
            "status": "CONFLICT",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "B04_QDRANT_PROD_METADATA_MISSING",
                "LIVE_PROVENANCE_ROW_COUNT_UNPROVED",
            ],
            "principal": make_field(
                "migration_v2:154_asset_provenance",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:44-136",
            ),
            "role": make_field("migration_runner", "PARTIAL", None),
            "tenant": make_field(
                "global_provenance",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:44-136",
            ),
            "authorization": make_field("pg_schema_owner", "PARTIAL", None),
            "transaction": make_field(
                "Single-table polymorphic DDL (asset_kind + opaque asset_id TEXT); 8/12 asset_kinds lack PG target tables",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:26-30",
            ),
            "effects": make_field(
                "Defines public.asset_provenance(asset_kind, asset_id TEXT) across PG, Qdrant, KG, and external sources; split authority vs SQLite provenance.db",
                "CONFLICT",
                "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:44-73",
            ),
            "retries": make_field(
                "none",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:37-38",
            ),
            "idempotency": make_field(
                "CREATE TABLE IF NOT EXISTS / UNIQUE (asset_kind, asset_id)",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:44-136",
            ),
            "failure": make_field(
                "Polymorphic FK is unverifiable in DDL; external store deletion leaves dangling TEXT pointers until weekly orphan-GC backlog",
                "CONFLICT",
                "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:26-30",
            ),
            "retention": make_field(
                "valid_until + invalidation_mode columns defined without cross-store cascade proof",
                "PARTIAL",
                "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:107-114",
            ),
            "recovery": make_field(
                "Not included in restore_drill_verify.py REQUIRED_TABLES",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:43-50",
            ),
            "x_guarantee_dimension": "references",
            "x_record_kind": "CURRENT_FACT",
            "x_counterexample_id": "CE-02",
            "x_target_store_ids": [
                "pg:fly:nuzantara-postgres/public",
                "qdrant:gcloud:nuzantara-qdrant/unknown",
                "sqlite:pro:mata-garuda/provenance",
                "object:gdrive:balizero_root/clients",
                "external:gcloud:notebooklm/container",
            ],
            "x_evidence_ref": "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:26-136",
        },
        # 3. D14 Versions (Current Fact): 299_schema_versions_provenance.sql & Qdrant model binding unproved
        {
            "consumer_id": "src_da55e7bec3535c6e",
            "operation_id": "UNASSIGNED_B05",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": "2026-10-15T03:28:29.868658+00:00",
            "evidence_sha256": state_sha,
            "status": "BLOCKED",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "B04_QDRANT_PROD_METADATA_MISSING",
                "QDRANT_MODEL_BINDING_UNPROVED",
            ],
            "principal": make_field(
                "migration_v2:299_schema_versions_provenance",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/299_schema_versions_provenance.sql:1-58",
            ),
            "role": make_field("migration_runner", "PARTIAL", None),
            "tenant": make_field(
                "system_schema_ledger",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/299_schema_versions_provenance.sql:1-58",
            ),
            "authorization": make_field("pg_schema_owner", "PARTIAL", None),
            "transaction": make_field(
                "Backfills _schema_versions from schema_migrations; no cross-store Qdrant embedding version lock",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/299_schema_versions_provenance.sql:15-55",
            ),
            "effects": make_field(
                "Reconciles PG migration ledger; local Qdrant has 2 collections (af100a6d) and qdrant_model_binding_proved=false",
                "BLOCKED",
                ".agent-receipts/udb-wave8-inputs/STATE.json:42-43",
            ),
            "retries": make_field(
                "idempotent SQL migration",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/299_schema_versions_provenance.sql:15-55",
            ),
            "idempotency": make_field(
                "ON CONFLICT DO NOTHING",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/299_schema_versions_provenance.sql:25-55",
            ),
            "failure": make_field(
                "Backup dump failed verification on clients VIOLATION:1 and conversations UNMEASURED_CHECK:1",
                "BLOCKED",
                ".agent-receipts/udb-wave8-inputs/STATE.json:80-130",
            ),
            "retention": make_field(
                "permanent schema ledger",
                "EVIDENCED",
                "apps/backend-rag/backend/db/migrations_v2/299_schema_versions_provenance.sql:1-58",
            ),
            "recovery": make_field(
                "Restore drill failed on clients VIOLATION:1 and conversations UNMEASURED_CHECK:1",
                "BLOCKED",
                ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json:27-76",
            ),
            "x_guarantee_dimension": "versions",
            "x_record_kind": "CURRENT_FACT",
            "x_counterexample_id": "CE-01",
            "x_target_store_ids": [
                "pg:fly:nuzantara-postgres/public",
                "qdrant:pro:local/sha8-af100a6d",
            ],
            "x_evidence_ref": ".agent-receipts/udb-wave8-inputs/STATE.json:42-130",
        },
        # 4. D15 Time Semantics (Current Fact): pg-to-organism-bridge.py LISTEN/NOTIFY -> JSONL + Redis
        {
            "consumer_id": "src_a725ee3bebe31d76",
            "operation_id": "UNASSIGNED_B05",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": file_hashes["scripts/pg-to-organism-bridge.py"],
            "status": "CONFLICT",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "B02_REDIS_OBSERVER_EVIDENCE_MISSING",
            ],
            "principal": make_field(
                "Nuzantara:com.nuzantara.pg-organism-bridge",
                "EVIDENCED",
                ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv:3728",
            ),
            "role": make_field(
                "launchd_daemon_pro",
                "EVIDENCED",
                "scripts/pg-to-organism-bridge.py:82-89",
            ),
            "tenant": make_field(
                "system_organism_bus",
                "EVIDENCED",
                "scripts/pg-to-organism-bridge.py:82-85",
            ),
            "authorization": make_field(
                "DATABASE_URL+REDIS_PASSWORD",
                "PARTIAL",
                "scripts/pg-to-organism-bridge.py:93-107",
            ),
            "transaction": make_field(
                "Ephemeral PG LISTEN/NOTIFY -> local JSONL append -> best-effort redis-cli XADD",
                "EVIDENCED",
                "scripts/pg-to-organism-bridge.py:190-222",
            ),
            "effects": make_field(
                "Truncates payload >2000B (_truncate_payload), mints wall-clock correlation_id pg-{channel}-{ts}, logs Redis XADD failure as non-fatal",
                "CONFLICT",
                "scripts/pg-to-organism-bridge.py:138-222",
            ),
            "retries": make_field(
                "Exponential reconnect backoff (1s..60s); notifications during disconnect are lost on bridge path",
                "CONFLICT",
                "scripts/pg-to-organism-bridge.py:238-260",
            ),
            "idempotency": make_field(
                "Fallback correlation_id uses datetime.now(timezone.utc).timestamp() when _outbox_id absent",
                "CONFLICT",
                "scripts/pg-to-organism-bridge.py:172-176",
            ),
            "failure": make_field(
                "Silent divergence between ~/.organism/events/pg-bridge.jsonl and Redis stream organism:events on XADD failure",
                "CONFLICT",
                "scripts/pg-to-organism-bridge.py:215-222",
            ),
            "retention": make_field(
                "Unbounded append to ~/.organism/events/pg-bridge.jsonl without Redis stream parity check",
                "PARTIAL",
                "scripts/pg-to-organism-bridge.py:82-85",
            ),
            "recovery": make_field(
                "No outbox replay invoked inside pg-to-organism-bridge.py reconnect loop",
                "CONFLICT",
                "scripts/pg-to-organism-bridge.py:238-260",
            ),
            "x_guarantee_dimension": "time_semantics",
            "x_record_kind": "CURRENT_FACT",
            "x_counterexample_id": "CE-03",
            "x_target_store_ids": [
                "pg:fly:nuzantara-postgres/public",
                "file:pro:organism/events",
                "redis:pro:6379/db0",
            ],
            "x_evidence_ref": "scripts/pg-to-organism-bridge.py:138-260",
        },
        # 5. D16 Retention/Erasure/Security (Current Fact): outbox-prune.sh 30d consumed prune vs 60m unconsumed orphan gap
        {
            "consumer_id": "src_05d88b7c837c1309",
            "operation_id": "UNASSIGNED_B05",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": file_hashes["scripts/outbox-prune.sh"],
            "status": "CONFLICT",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "LIVE_ORPHAN_OUTBOX_COUNT_UNPROVED",
            ],
            "principal": make_field(
                "Nuzantara:com.nuzantara.outbox-prune.daily",
                "EVIDENCED",
                ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv:3722",
            ),
            "role": make_field(
                "launchd_cron_pro",
                "EVIDENCED",
                "scripts/outbox-prune.sh:8-10",
            ),
            "tenant": make_field(
                "system_maintenance",
                "EVIDENCED",
                "scripts/outbox-prune.sh:1-12",
            ),
            "authorization": make_field(
                "DATABASE_URL_via_pg_proxy_15432",
                "PARTIAL",
                "scripts/outbox-prune.sh:38-56",
            ),
            "transaction": make_field(
                "Calls prune_consumed(conn, older_than_days=30) executing single DELETE on public.events_outbox",
                "EVIDENCED",
                "scripts/outbox-prune.sh:72-88",
            ),
            "effects": make_field(
                "Deletes only WHERE consumed_at IS NOT NULL AND consumed_at < NOW() - 30 days",
                "EVIDENCED",
                "apps/backend-rag/backend/services/events/outbox.py:437-441",
            ),
            "retries": make_field(
                "daily cron at 03:15; exits 0 with warning if pg-proxy :15432 unreachable",
                "PARTIAL",
                "scripts/outbox-prune.sh:46-55",
            ),
            "idempotency": make_field(
                "idempotent DELETE by predicate",
                "EVIDENCED",
                "apps/backend-rag/backend/services/events/outbox.py:437-441",
            ),
            "failure": make_field(
                "Leaves unconsumed rows (consumed_at IS NULL) older than 60m abandoned by replay_unconsumed and never pruned",
                "CONFLICT",
                "apps/backend-rag/backend/services/events/outbox.py:332-441",
            ),
            "retention": make_field(
                "30d for consumed rows; infinite retention leak for unconsumed >60m orphans",
                "CONFLICT",
                "scripts/outbox-prune.sh:66-88",
            ),
            "recovery": make_field("N/A maintenance prune", "PARTIAL", None),
            "x_guarantee_dimension": "retention_erasure_security",
            "x_record_kind": "CURRENT_FACT",
            "x_counterexample_id": "CE-06",
            "x_target_store_ids": ["pg:fly:nuzantara-postgres/public"],
            "x_evidence_ref": "scripts/outbox-prune.sh:66-88",
        },
        # 6. D16/D17 Recovery Order (Current Fact): restore_drill_verify.py & mini.restore_drill receipt
        {
            "consumer_id": "src_d073f505ff1671ad",
            "operation_id": "UNASSIGNED_B05",
            "store_id": "pg:mini:restore-drill/nuzantara_restore_drill",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": "2026-10-15T03:02:11+00:00",
            "evidence_sha256": receipt_sha,
            "status": "BLOCKED",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "B01_RECOVERY_EVIDENCE_MISSING",
                "CLIENTS_FAILING_SUBCHECK_UNDISAMBIGUATED",
                "CONVERSATIONS_UNMEASURED_SQL_CAUSE_UNKNOWN",
            ],
            "principal": make_field(
                "mini.restore_drill",
                "EVIDENCED",
                ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json:27-36",
            ),
            "role": make_field(
                "restore_drill_verifier",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:111-187",
            ),
            "tenant": make_field(
                "ephemeral_docker_pg16_mini",
                "EVIDENCED",
                ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json:27-36",
            ),
            "authorization": make_field(
                "local_ephemeral_container",
                "EVIDENCED",
                "scripts/restore_drill/run_drill.sh:20-50",
            ),
            "transaction": make_field(
                "Read-only verification queries against restored PG dump",
                "EVIDENCED",
                "scripts/ci/restore_drill_verify.py:221-356",
            ),
            "effects": make_field(
                "Verifies 5 PG tables only; Qdrant, Redis, SQLite, GDrive excluded; aggregate=CANNOT-VERIFY masks clients=FAIL",
                "BLOCKED",
                ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json:37-73",
            ),
            "retries": make_field(
                "manual/cron drill invocation",
                "PARTIAL",
                "scripts/restore_drill/run_drill.sh:1-76",
            ),
            "idempotency": make_field(
                "ephemeral container destroyed on exit via trap cleanup EXIT",
                "EVIDENCED",
                "scripts/restore_drill/run_drill.sh:66-76",
            ),
            "failure": make_field(
                "clients=FAIL (VIOLATION:1 via _CLIENTS_VIOLATIONS_SQL), conversations=CANNOT-VERIFY (UNMEASURED_CHECK:1), aggregate=CANNOT-VERIFY",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:221-227",
            ),
            "retention": make_field(
                "$WORK_DIR/verify.json deleted on exit; sanitized TERMINAL verifier_summary only",
                "EVIDENCED",
                "scripts/restore_drill/run_drill.sh:66-76",
            ),
            "recovery": make_field(
                "real_backup_restore_success_proved=false",
                "BLOCKED",
                ".agent-receipts/udb-wave8-inputs/STATE.json:41",
            ),
            "x_guarantee_dimension": "recovery_order",
            "x_record_kind": "CURRENT_FACT",
            "x_counterexample_id": "CE-01",
            "x_target_store_ids": [
                "pg:mini:restore-drill/nuzantara_restore_drill",
                "pg:fly:nuzantara-postgres/public",
            ],
            "x_evidence_ref": ".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json:27-76",
        },
        # 7. Workload/Cost (Current Fact): llm_cost_recorder.py triple-sink PG + JSONL + Prometheus
        {
            "consumer_id": "src_787bbadb9e6dca52",
            "operation_id": "UNASSIGNED_B05",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": file_hashes[
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py"
            ],
            "status": "CONFLICT",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "LIVE_LLM_COST_EVENTS_TABLE_EXISTENCE_UNPROVED",
            ],
            "principal": make_field(
                "backend-rag:llm_cost_recorder",
                "EVIDENCED",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:102-120",
            ),
            "role": make_field(
                "app_telemetry_writer",
                "EVIDENCED",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:239-299",
            ),
            "tenant": make_field(
                "system_cost_ledger",
                "EVIDENCED",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:1-28",
            ),
            "authorization": make_field(
                "local_fs+get_db_pool",
                "PARTIAL",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:154-210",
            ),
            "transaction": make_field(
                "Independent parallel writes to Prometheus, PG llm_cost_events, and /data/llm_cost_log.YYYY-MM-DD.jsonl without reconciliation",
                "EVIDENCED",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:239-298",
            ),
            "effects": make_field(
                "Writes /data/llm_cost_log.YYYY-MM-DD.jsonl and public.llm_cost_events; partial sink failure does not roll back or backfill",
                "CONFLICT",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:255-285",
            ),
            "retries": make_field(
                "none on PG or JSONL failure",
                "EVIDENCED",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:259-285",
            ),
            "idempotency": make_field(
                "append-only event log without UNIQUE(request_id) dedup constraint",
                "PARTIAL",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:181-210",
            ),
            "failure": make_field(
                "Single-sink failure logs warning and returns False for that sink; PG and JSONL diverge permanently",
                "CONFLICT",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:272-285",
            ),
            "retention": make_field(
                "DEFAULT_RETENTION_DAYS=90 stored on self.retention_days (line 112) but never referenced by any pruning logic",
                "CONFLICT",
                "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:58-60",
            ),
            "recovery": make_field(
                "llm_cost_events not in restore_drill_verify.py REQUIRED_TABLES",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:43-50",
            ),
            "x_guarantee_dimension": "workload_cost",
            "x_record_kind": "CURRENT_FACT",
            "x_counterexample_id": "CE-06",
            "x_target_store_ids": [
                "pg:fly:nuzantara-postgres/public",
                "file:fly:data/llm_cost_log",
            ],
            "x_evidence_ref": "apps/backend-rag/backend/services/observability/llm_cost_recorder.py:55-299",
        },
        # 8. Analytics/Observability (Current Fact): war-room/metrics/costs/route.ts 42P01 -> $0 masking
        {
            "consumer_id": "src_af8a65192e15e595",
            "operation_id": "UNASSIGNED_B05",
            "store_id": "pg:fly:nuzantara-postgres/public",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": file_hashes[
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts"
            ],
            "status": "CONFLICT",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "LIVE_WAR_ROOM_COSTS_TABLE_STATE_UNPROVED",
            ],
            "principal": make_field(
                "admin-dashboard:api/war-room/metrics/costs",
                "EVIDENCED",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:20-97",
            ),
            "role": make_field(
                "dashboard_reader",
                "EVIDENCED",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:7-20",
            ),
            "tenant": make_field(
                "admin_war_room",
                "EVIDENCED",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:20-97",
            ),
            "authorization": make_field(
                "DATABASE_URL",
                "PARTIAL",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:7-9",
            ),
            "transaction": make_field(
                "Read-only SELECT joining war_room_costs and war_room_drafts",
                "EVIDENCED",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:29-59",
            ),
            "effects": make_field(
                "Catches PostgreSQL 42P01 (undefined_table) at lines 84-89 and returns HTTP 200 with grand_total_usd: 0",
                "CONFLICT",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:82-89",
            ),
            "retries": make_field(
                "none",
                "EVIDENCED",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:82-94",
            ),
            "idempotency": make_field(
                "read-only",
                "EVIDENCED",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:29-59",
            ),
            "failure": make_field(
                "Conflates missing schema table (42P01) with $0.00 spend under HTTP 200",
                "CONFLICT",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:84-89",
            ),
            "retention": make_field(
                "N/A reader",
                "EVIDENCED",
                "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:20-97",
            ),
            "recovery": make_field(
                "war_room_costs not in restore drill REQUIRED_TABLES",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:43-50",
            ),
            "x_guarantee_dimension": "analytics_observability",
            "x_record_kind": "CURRENT_FACT",
            "x_counterexample_id": "CE-05",
            "x_target_store_ids": ["pg:fly:nuzantara-postgres/public"],
            "x_evidence_ref": "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:82-89",
        },
        # 9. Desired Guarantee Specimen (Recovery Order): Multi-store ordered recovery contract
        {
            "consumer_id": "src_d073f505ff1671ad",
            "operation_id": "UNASSIGNED_B05",
            "store_id": "pg:mini:restore-drill/nuzantara_restore_drill",
            "source_version": BASE_COMMIT_SHA,
            "evidence_timestamp": BASE_COMMIT_TIMESTAMP,
            "evidence_sha256": file_hashes["scripts/ci/restore_drill_verify.py"],
            "status": "BLOCKED",
            "unknowns": [
                "OPERATION_ID_PENDING_B05",
                "STATIC_SOURCE_ONLY",
                "B01_RECOVERY_EVIDENCE_MISSING",
                "B02_REDIS_OBSERVER_EVIDENCE_MISSING",
                "B04_QDRANT_PROD_METADATA_MISSING",
            ],
            "principal": make_field(
                "target:multi_store_restore_verifier",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:451-457",
            ),
            "role": make_field("restore_drill_verifier", "BLOCKED", None),
            "tenant": make_field("system_recovery", "BLOCKED", None),
            "authorization": make_field(
                "keyless_observer_and_ephemeral_pg", "BLOCKED", None
            ),
            "transaction": make_field(
                "Target order: 1.PG base + _schema_versions -> 2.SQLite/GDrive provenance -> 3.Qdrant collection/model parity -> 4.Redis stream watermark -> 5.Outbox replay",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:43-50",
            ),
            "effects": make_field(
                "Target guarantee: emit distinct subcheck counts and FAIL+CANNOT-VERIFY compound status without masking",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:451-457",
            ),
            "retries": make_field("deterministic drill retry", "BLOCKED", None),
            "idempotency": make_field(
                "ephemeral isolated restore", "BLOCKED", None
            ),
            "failure": make_field(
                "Target guarantee: any table FAIL or CANNOT-VERIFY blocks release closure",
                "BLOCKED",
                "scripts/ci/restore_drill_verify.py:451-457",
            ),
            "retention": make_field(
                "Persist sanitized per-subcheck counters via B01 admission",
                "BLOCKED",
                None,
            ),
            "recovery": make_field(
                "Awaiting B01 restore admission, B02 Redis observer, and B04 Qdrant metadata",
                "BLOCKED",
                ".agent-receipts/udb-wave8-inputs/STATE.json:41-47",
            ),
            "x_guarantee_dimension": "recovery_order",
            "x_record_kind": "DESIRED_GUARANTEE",
            "x_counterexample_id": "CE-01",
            "x_target_store_ids": [
                "pg:mini:restore-drill/nuzantara_restore_drill",
                "pg:fly:nuzantara-postgres/public",
                "qdrant:pro:local/sha8-af100a6d",
                "redis:pro:6379/db0",
                "redis:mini:6379/db0",
            ],
            "x_evidence_ref": "scripts/ci/restore_drill_verify.py:451-457",
        },
    ]
    return instances


def build_dimensions_ledger(
    instances: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build the 8-dimension cross-store ledger separating current_facts and desired_guarantees."""
    desired_specs: dict[str, dict[str, Any]] = {
        "dependencies": {
            "dimension_id": "D12_dependencies",
            "x_record_kind": "DESIRED_GUARANTEE",
            "target_status_until_proved": "PARTIAL",
            "invariant": (
                "Every cross-store fan-out edge (PG -> Redis, PG -> Qdrant, PG -> JSONL) "
                "must declare explicit transaction boundary, downstream idempotency key, "
                "and dead-letter/orphan sweep covering all unconsumed ages."
            ),
            "blocking_siblings": ["B02", "B03", "B05"],
        },
        "references": {
            "dimension_id": "D14_references",
            "x_record_kind": "DESIRED_GUARANTEE",
            "target_status_until_proved": "CONFLICT",
            "invariant": (
                "Cross-store references (public.asset_provenance, Qdrant point_id/source_id, "
                "GDrive file IDs, NotebookLM container refs) must have a single declared "
                "authority and periodic dangling-pointer verification."
            ),
            "blocking_siblings": ["B04", "B06", "B07"],
        },
        "versions": {
            "dimension_id": "D14_versions",
            "x_record_kind": "DESIRED_GUARANTEE",
            "target_status_until_proved": "BLOCKED",
            "invariant": (
                "PG _schema_versions and schema_migrations must match backup dump schema "
                "expectations, and Qdrant collections must prove embedding model + 1536-dim binding."
            ),
            "blocking_siblings": ["B01", "B04", "B07"],
        },
        "time_semantics": {
            "dimension_id": "D15_time_semantics",
            "x_record_kind": "DESIRED_GUARANTEE",
            "target_status_until_proved": "CONFLICT",
            "invariant": (
                "Cross-store event propagation must preserve producer event_id and UTC timestamp "
                "without wall-clock fallback IDs or silent 2000-byte payload truncation."
            ),
            "blocking_siblings": ["B02", "B05"],
        },
        "retention_erasure_security": {
            "dimension_id": "D16_retention_erasure_security",
            "x_record_kind": "DESIRED_GUARANTEE",
            "target_status_until_proved": "CONFLICT",
            "invariant": (
                "PII erasure and TTL policies (visa_decision_retention_policies, events_outbox, "
                "llm_cost_log.jsonl) must cascade across PG, Qdrant, Redis, and JSONL with zero orphan gap."
            ),
            "blocking_siblings": ["B01", "B02", "B04", "B06"],
        },
        "recovery_order": {
            "dimension_id": "D17_recovery_order",
            "x_record_kind": "DESIRED_GUARANTEE",
            "target_status_until_proved": "BLOCKED",
            "invariant": (
                "Restore verification must prove PASS across all 5 PG tables on Mini without "
                "CANNOT-VERIFY masking FAIL, and order recovery across PG -> SQLite/GDrive -> Qdrant -> Redis."
            ),
            "blocking_siblings": ["B01", "B02", "B04"],
        },
        "workload_cost": {
            "dimension_id": "D16_workload_cost",
            "x_record_kind": "DESIRED_GUARANTEE",
            "target_status_until_proved": "CONFLICT",
            "invariant": (
                "Dual-sink cost telemetry (/data/llm_cost_log.jsonl and public.llm_cost_events) "
                "must reconcile row counts and enforce declared 90-day file pruning."
            ),
            "blocking_siblings": ["B04", "B07"],
        },
        "analytics_observability": {
            "dimension_id": "D17_analytics_observability",
            "x_record_kind": "DESIRED_GUARANTEE",
            "target_status_until_proved": "CONFLICT",
            "invariant": (
                "Health and cost endpoints (check_qdrant, war-room/metrics/costs) must never "
                "report status='ok' on zero-I/O checks or grand_total_usd=0 on SQL 42P01 errors."
            ),
            "blocking_siblings": ["B02", "B04"],
        },
    }

    ledger: dict[str, dict[str, Any]] = {}
    for dim in EIGHT_DIMENSIONS:
        current_rows = [
            inst
            for inst in instances
            if inst.get("x_guarantee_dimension") == dim
            and inst.get("x_record_kind") == "CURRENT_FACT"
        ]
        desired_rows = [
            inst
            for inst in instances
            if inst.get("x_guarantee_dimension") == dim
            and inst.get("x_record_kind") == "DESIRED_GUARANTEE"
        ]
        ledger[dim] = {
            "current_facts": current_rows,
            "desired_guarantees": [desired_specs[dim]] + desired_rows,
        }
    return ledger


def verify_historical_restore_source(repo_root: Path) -> Path:
    """Check the exact live revision and retain the declared historical evidence."""
    live = repo_root / "scripts/ci/restore_drill_verify.py"
    actual = sha256_file(live)
    if actual == PINNED_RESTORE_DRILL_VERIFY_SHA256:
        return live
    if actual != PINNED_COMPATIBLE_MAIN_RESTORE_SHA256:
        raise ContractViolationError(
            "B08_E_RESTORE_SOURCE_PIN: SHA256 mismatch on restore verifier source"
        )
    # The recognized B01 correction changed source locations and invariant SQL.
    # Its hash is not substituted into the historical ledger or its assertions.
    historical = (repo_root / B08_REL_DIR / "source-compatibility"
                  / "restore-drill-base-source.txt")
    _require_fixture_sha(
        historical, PINNED_RESTORE_DRILL_VERIFY_SHA256, "historical restore source"
    )
    return historical


def generate_b08_report(repo_root: Path) -> dict[str, Any]:
    """Generate the complete, validated B08 cross-store ledger from pinned inputs."""
    inputs = resolve_wave8_inputs(repo_root)
    state_path = inputs.state_path
    receipt_path = inputs.receipt_path
    pinned_census_path = inputs.census_path
    restore_source = verify_historical_restore_source(repo_root)

    pinned_census = load_pinned_census_receipt(
        pinned_census_path,
        expected_sha256=PINNED_DUX_REQ_B08_01_OUT_SHA256,
    )

    state_sha = sha256_file(state_path)
    if state_sha != PINNED_STATE_JSON_SHA256:
        raise ContractViolationError("B08_E_STATE_PIN: SHA256 mismatch on state input")
    state_json = json.loads(state_path.read_text(encoding="utf-8"))
    receipt_json = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_sha = sha256_file(receipt_path)
    if receipt_sha != PINNED_REAL_RUN_RECEIPT_SHA256:
        raise ContractViolationError(
            'B08_E_RESTORE_RECEIPT_PIN: SHA256 mismatch on restore receipt'
        )

    if (
        inputs.origins["matrix"] == "live"
        and sha256_file(inputs.matrix_path) != PINNED_CONSUMER_MATRIX_SOURCE_SHA256
    ):
        raise ContractViolationError(
            "B08_E_MATRIX_PIN: SHA256 mismatch on live consumer matrix"
        )

    matrix_summary = scan_wave8_consumer_matrix(inputs)
    compare_census_to_receipt(matrix_summary, pinned_census)
    known_ids = matrix_summary["known_consumer_ids"]

    instances = build_b08_operation_instances(
        repo_root=repo_root,
        state_sha=state_sha,
        receipt_sha=receipt_sha,
        restore_source=restore_source,
    )

    for inst in instances:
        validate_operation_instance(inst, known_consumer_ids=known_ids)

    validate_sibling_gate_constraints(
        records=instances,
        state_json=state_json,
        block_closed=False,
    )

    ce01 = evaluate_ce01_restore_verdict_and_epistemology(receipt_json)
    ce02 = evaluate_ce02_polymorphic_provenance(
        (
            repo_root
            / "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql"
        ).read_text(encoding="utf-8")
    )
    ce03 = evaluate_ce03_organism_bridge(
        (repo_root / "scripts/pg-to-organism-bridge.py").read_text(encoding="utf-8")
    )
    ce04 = evaluate_ce04_qdrant_health_probe(
        (
            repo_root
            / "apps/backend-rag/backend/services/monitoring/unified_health_service.py"
        ).read_text(encoding="utf-8")
    )
    ce05 = evaluate_ce05_war_room_cost_masking(
        (
            repo_root
            / "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts"
        ).read_text(encoding="utf-8")
    )
    ce06 = evaluate_ce06_outbox_and_cost_retention(
        outbox_py_source=(
            repo_root / "apps/backend-rag/backend/services/events/outbox.py"
        ).read_text(encoding="utf-8"),
        outbox_prune_sh_source=(repo_root / "scripts/outbox-prune.sh").read_text(
            encoding="utf-8"
        ),
        llm_cost_recorder_source=(
            repo_root
            / "apps/backend-rag/backend/services/observability/llm_cost_recorder.py"
        ).read_text(encoding="utf-8"),
    )

    dimensions_ledger = build_dimensions_ledger(instances)

    return {
        "block_id": "B08",
        "campaign_id": state_json.get("campaign_id", "universal-db-wave8-20261015"),
        "base_commit": BASE_COMMIT_SHA,
        "base_commit_timestamp": BASE_COMMIT_TIMESTAMP,
        "block_closed": False,
        "status": "PARTIAL",
        "census_summary": {
            "baseline_leads_preserved": state_json.get("baseline_leads_preserved"),
            "additional_runtime_observations": state_json.get(
                "additional_runtime_observations"
            ),
            "union_lead_rows": state_json.get("union_lead_rows"),
            "active_consumer_denominator": state_json.get(
                "active_consumer_denominator"
            ),
            "csv_total_rows": matrix_summary["total_rows"],
            "csv_column_count": matrix_summary["column_count"],
            "multi_store_or_boundary_rows": matrix_summary[
                "multi_store_or_boundary_rows"
            ],
            "by_family": matrix_summary["by_family"],
            "by_store": matrix_summary["by_store"],
            "top_by_store": matrix_summary["top_by_store"],
        },
        "missing_sibling_evidence": {
            "B01": "Real-backup restore drill PASS proof missing (real_backup_restore_success_proved=false; clients=FAIL with VIOLATION:1, conversations=CANNOT-VERIFY with UNMEASURED_CHECK:1).",
            "B02": "Keyless Redis observer admission missing on Pro and Mini (redis.pro=AUTHORIZATION_REQUIRED, redis.mini=AUTHORIZATION_REQUIRED).",
            "B03": "Active-consumer denominator remains UNKNOWN across the 6,030 union leads.",
            "B04": "Production Qdrant live collection/vector/model binding proof missing (qdrant_model_binding_proved=false; local Pro has only 2 collections).",
            "B05": "Canonical operation_id minting owned by B05; all B08 operation instances carry UNASSIGNED_B05 + OPERATION_ID_PENDING_B05.",
        },
        "dimensions": dimensions_ledger,
        "operation_instances": instances,
        "counterexamples": {
            "CE-01_restore_precedence_and_epistemology": ce01,
            "CE-02_polymorphic_provenance": ce02,
            "CE-03_organism_bridge_truncation_and_correlation": ce03,
            "CE-04_qdrant_zero_io_health_probe": ce04,
            "CE-05_war_room_42p01_false_zero_cost": ce05,
            "CE-06_outbox_orphan_gap_and_jsonl_retention": ce06,
        },
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for generating b08_crossstore_ledger.json."""
    parser = _BoundaryArgumentParser(
        description="Generate B08 cross-store operational guarantees ledger."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Path to repository root.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("research/operations/udb-wave8/B08/b08_crossstore_ledger.json"),
        help="Output JSON path inside research/operations/udb-wave8/B08/.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    out_path = args.out if args.out.is_absolute() else (repo_root / args.out)
    b08_dir = (repo_root / "research/operations/udb-wave8/B08").resolve()
    out_path = out_path.resolve()
    if not out_path.is_relative_to(b08_dir):
        raise ContractViolationError(
            'B08_E_OUTPUT_SCOPE: Output path must stay inside B08 (Finding B08-F1/B08-F5)'
        )

    report = generate_b08_report(repo_root)
    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except ContractViolationError:
        # Rejected values and paths must never enter CLI diagnostics or traceback.
        print("B08_E_CONTRACT: input or destination rejected", file=sys.stderr)
        exit_code = 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError, csv.Error, RuntimeError):
        # OS/parser exceptions can embed paths, raw bytes, keys or input fragments.
        print("B08_E_INPUT: input or destination could not be processed", file=sys.stderr)
        exit_code = 1
    raise SystemExit(exit_code)
