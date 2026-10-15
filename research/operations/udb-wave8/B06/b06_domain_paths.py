"""B06 Business-Domain Paths Adapter and Operation-Instance Generator.

Hermetic, stdlib-only adapter for campaign ``universal-db-wave8-20261015``
block ``B06`` (business-domain research lines ``D04``--``D10``).

Responsibilities:
1. Reproduce the pinned source-taxonomy census (``DUX-REQ-B06-01.cmd.sh`` ->
   ``DUX-REQ-B06-01.out``) and six-prefix census (``DUX-REQ-B06-03.cmd.sh`` ->
   ``DUX-REQ-B06-03.out``) from ``.agent-receipts/udb-wave8-inputs/consumer-matrix.csv``
   and compare every counter and total against the pinned receipts.
2. Keep the source-taxonomy census strictly separate from the ``D04``--``D10``
   business-domain operation-instance inventory (unmapped source taxonomy stays
   explicit ``UNKNOWN``).
3. Emit 21 ``B05``-compatible operation-instance records conforming to
   ``.agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md`` (19 canonical keys
   in order, ``{value, status, evidence_ref}`` instance-field objects,
   ``UPPER_SNAKE`` unknowns, ``2026-10-15T07:06:22Z`` + ``STATIC_SOURCE_ONLY``,
   and ``evidence_sha256`` computed directly from each record's ``x_evidence_ref``
   source file).
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

BASE_COMMIT_SHA = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
STATIC_EVIDENCE_TIMESTAMP = "2026-10-15T07:06:22Z"

CONSUMER_MATRIX_REL_PATH = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
CONSUMER_MATRIX_SHA256 = "c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118"

DUX_REQ_DIR_REL_PATH = "research/operations/udb-wave8/B06/dux-requests"
DUX_REQ_B06_01_CMD_SHA256 = "2ab0a482d1c8b4d31e82f6588083992e67b8031d447d11d501c36409a9f47fad"
DUX_REQ_B06_01_SHA256 = "1551433483cb28444c7729aef228a351edc0a644880ec01d8b77546bb20f5cbb"
DUX_REQ_B06_03_CMD_SHA256 = "03ac55218419d807d0f2f54f9e133e96600a9de8c2fcb60021ddd9b4795011ec"
DUX_REQ_B06_03_SHA256 = "e30e1c44d8e6ab797e20dc7722eb27854cc1e04a2feab325db2d0a1f3c9d10aa"

FROZEN_8_KEYS: tuple[str, ...] = (
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

CANONICAL_19_KEYS: tuple[str, ...] = FROZEN_8_KEYS + INSTANCE_11_KEYS

ALLOWED_STATUS_VALUES: frozenset[str] = frozenset(
    {
        "EVIDENCED",
        "PARTIAL",
        "BLOCKED",
        "CONFLICT",
        "UNKNOWN",
    }
)

REQUIRED_CSV_HEADERS: tuple[str, ...] = (
    "domain",
    "domain_hint",
    "disposition",
    "blocker",
    "activation_status",
    "contract_coverage_status",
    "phase_source_scope_status",
    "phase_source_path_evidence",
    "phase_factory_candidate_count",
    "entry_point",
    "consumer_id",
)

PREFIX_CENSUS_PREFIXES: tuple[str, ...] = (
    "apps/backend-rag/backend/app/routers/",
    "apps/backend-rag/backend/services/",
    "apps/bali-intel-scraper/",
    "packages/cell/",
    "packages/cell-core/",
    "packages/research-os-core/",
)

STORE_ID_GRAMMAR_RE = re.compile(
    r"^(?:unknown:unknown:unknown|"
    r"(?:pg|qdrant|redis|sqlite|graph|object|file|sheet|browser|external):"
    r"(?:fly|pro|mini|m5|gcloud|gdrive|github|client|unknown):"
    r"[a-z0-9_-]+(?:/[a-z0-9_.-]+)*)$"
)
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
UNKNOWN_TOKEN_RE = re.compile(r"^[A-Z0-9_]+(?::[A-Za-z0-9_.:/-]+)?$")

SYNTHETIC_PHONE_FIXTURE = "+00-000-0000"
SYNTHETIC_EMAIL_FIXTURE = "user@example.invalid"


def normalize_phone_digits(raw_phone: str | None) -> str:
    """Mirror ``client_core.py:293-305`` ``REGEXP_REPLACE(phone, '[^0-9]', '', 'g')``."""
    if not raw_phone:
        return ""
    return re.sub(r"[^0-9]", "", raw_phone)


def evaluate_phone_duplicate_gate(
    candidate_phone: str | None,
    existing_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mirror ``client_core.py:293-309`` pre-INSERT phone duplicate check.

    Demonstrates ``CE-B06-01``: ``client_core.py`` runs a non-atomic ``SELECT``
    comparing ``REGEXP_REPLACE(phone, '[^0-9]', '', 'g')`` for ``length >= 7``
    without a database-level ``UNIQUE`` constraint or table lock.
    """
    norm_candidate = normalize_phone_digits(candidate_phone)
    if len(norm_candidate) < 7:
        return {
            "checked": False,
            "normalized_digits": norm_candidate,
            "duplicate_client_id": None,
            "atomic_db_constraint": False,
        }
    for row in existing_rows:
        if row.get("deleted_at") is not None:
            continue
        existing_norm = normalize_phone_digits(str(row.get("phone") or ""))
        if existing_norm == norm_candidate:
            return {
                "checked": True,
                "normalized_digits": norm_candidate,
                "duplicate_client_id": row.get("id"),
                "atomic_db_constraint": False,
            }
    return {
        "checked": True,
        "normalized_digits": norm_candidate,
        "duplicate_client_id": None,
        "atomic_db_constraint": False,
    }


def _validate_csv_headers(fieldnames: list[str] | tuple[str, ...] | None, csv_path: Path) -> None:
    """Validate that all required consumer-matrix.csv headers are present."""
    if not fieldnames:
        raise ValueError(f"CSV file {csv_path} has no header row.")
    present = set(fieldnames)
    missing = [h for h in REQUIRED_CSV_HEADERS if h not in present]
    if missing:
        raise ValueError(
            f"CSV file {csv_path} is missing required headers: {missing}"
        )


def compute_source_census(csv_path: Path) -> dict[str, Any]:
    """Reproduce ``DUX-REQ-B06-01.cmd.sh`` exactly over ``csv_path``.

    Counts ``domain``, ``domain_hint``, and ``disposition|contract_coverage_status``
    using ``"EMPTY"`` for empty values, keeping source taxonomy separate from the
    ``D04``--``D10`` business-domain inventory.
    """
    raw_bytes = csv_path.read_bytes()
    sha = hashlib.sha256(raw_bytes).hexdigest()
    by_domain: Counter[str] = Counter()
    by_hint: Counter[str] = Counter()
    by_dc: Counter[str] = Counter()

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _validate_csv_headers(reader.fieldnames, csv_path)
        for row in reader:
            by_domain[row["domain"] or "EMPTY"] += 1
            by_hint[row["domain_hint"] or "EMPTY"] += 1
            dc_key = (row["disposition"] or "EMPTY") + "|" + (
                row["contract_coverage_status"] or "EMPTY"
            )
            by_dc[dc_key] += 1

    return {
        "sha256": sha,
        "total": sum(by_domain.values()),
        "by_domain": dict(by_domain.most_common()),
        "by_domain_hint": dict(by_hint.most_common()),
        "by_disposition_contract_status": dict(by_dc.most_common()),
    }


def compute_prefix_census(csv_path: Path) -> dict[str, Any]:
    """Reproduce ``DUX-REQ-B06-03.cmd.sh`` over the six prefixes on ``csv_path``."""
    counter: Counter[str] = Counter()
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _validate_csv_headers(reader.fieldnames, csv_path)
        for row in reader:
            ep = row["entry_point"] or ""
            pre = next((x for x in PREFIX_CENSUS_PREFIXES if ep.startswith(x)), None)
            if pre:
                key = (
                    pre
                    + " | "
                    + (row["phase_source_path_evidence"] or "EMPTY")
                    + " | "
                    + (row["phase_source_scope_status"] or "EMPTY")
                    + " | fc="
                    + (row["phase_factory_candidate_count"] or "EMPTY")
                )
                counter[key] += 1

    return {
        "total_rows_in_prefixes": sum(counter.values()),
        "prefix|phase_source_path_evidence|phase_source_scope_status|factory_count": dict(
            counter.most_common()
        ),
    }


def summarize_prefix_scope_status(prefix_census: dict[str, Any]) -> dict[str, int]:
    """Aggregate ``phase_source_scope_status`` counts from ``compute_prefix_census``."""
    buckets = prefix_census.get(
        "prefix|phase_source_path_evidence|phase_source_scope_status|factory_count",
        {},
    )
    by_scope_status: Counter[str] = Counter()
    for composite_key, count in buckets.items():
        parts = [p.strip() for p in composite_key.split("|")]
        scope_status = parts[2] if len(parts) >= 3 else "UNKNOWN"
        by_scope_status[scope_status] += int(count)
    return dict(by_scope_status.most_common())


def verify_pinned_receipt_files(repo_root: Path) -> dict[str, str]:
    """Verify the SHA-256 digests of the 4 pinned DUX-REQ-B06-01/03 files on disk."""
    req_dir = repo_root / DUX_REQ_DIR_REL_PATH
    expected = {
        "DUX-REQ-B06-01.cmd.sh": DUX_REQ_B06_01_CMD_SHA256,
        "DUX-REQ-B06-01.out": DUX_REQ_B06_01_SHA256,
        "DUX-REQ-B06-03.cmd.sh": DUX_REQ_B06_03_CMD_SHA256,
        "DUX-REQ-B06-03.out": DUX_REQ_B06_03_SHA256,
    }
    observed: dict[str, str] = {}
    for filename, exp_sha in expected.items():
        fpath = req_dir / filename
        actual_sha = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if actual_sha != exp_sha:
            raise ValueError(
                f"Pinned receipt SHA-256 mismatch for {filename}: "
                f"expected {exp_sha}, got {actual_sha}"
            )
        observed[filename] = actual_sha
    return observed


def load_pinned_census_receipts(repo_root: Path) -> dict[str, Any]:
    """Verify and parse ``DUX-REQ-B06-01.out`` and ``DUX-REQ-B06-03.out``."""
    shas = verify_pinned_receipt_files(repo_root)
    req_dir = repo_root / DUX_REQ_DIR_REL_PATH
    receipt_01 = json.loads((req_dir / "DUX-REQ-B06-01.out").read_text(encoding="utf-8"))
    receipt_03 = json.loads((req_dir / "DUX-REQ-B06-03.out").read_text(encoding="utf-8"))
    return {
        "shas": shas,
        "receipt_01": receipt_01,
        "receipt_03": receipt_03,
    }


def compare_census_to_receipts(
    source_census: dict[str, Any],
    prefix_census: dict[str, Any],
    receipt_01: dict[str, Any],
    receipt_03: dict[str, Any],
) -> list[str]:
    """Compare computed source and prefix censuses to pinned receipts for exact equality."""
    errors: list[str] = []
    for key in (
        "sha256",
        "total",
        "by_domain",
        "by_domain_hint",
        "by_disposition_contract_status",
    ):
        if source_census.get(key) != receipt_01.get(key):
            errors.append(
                f"source_census[{key!r}] mismatch: computed={source_census.get(key)!r} "
                f"!= receipt_01={receipt_01.get(key)!r}"
            )

    for key in (
        "total_rows_in_prefixes",
        "prefix|phase_source_path_evidence|phase_source_scope_status|factory_count",
    ):
        if prefix_census.get(key) != receipt_03.get(key):
            errors.append(
                f"prefix_census[{key!r}] mismatch: computed={prefix_census.get(key)!r} "
                f"!= receipt_03={receipt_03.get(key)!r}"
            )
    return errors


def _field_obj(
    value: Any,
    status: str = "PARTIAL",
    evidence_ref: str | None = None,
) -> dict[str, Any]:
    """Construct a CONTRACT-CONVENTIONS.md §Row-layout instance field object."""
    if status not in ALLOWED_STATUS_VALUES:
        raise ValueError(f"Invalid field status: {status}")
    return {
        "value": value,
        "status": status,
        "evidence_ref": evidence_ref,
    }


def _compute_ref_file_sha256(repo_root: Path, x_evidence_ref: str) -> str:
    """Compute SHA-256 of the repository file named in ``x_evidence_ref``."""
    rel_file = x_evidence_ref.split(":", 1)[0]
    file_path = repo_root / rel_file
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def _build_canonical_record(
    repo_root: Path,
    *,
    consumer_id: str,
    store_id: str,
    proposed_store_id: str | None,
    status: str,
    extra_unknowns: list[str],
    principal: str,
    role: str,
    role_status: str,
    tenant: str,
    authorization: str,
    transaction: str,
    effects: list[str],
    retries: str,
    idempotency: str,
    failure: str,
    retention: str,
    recovery: str,
    recovery_status: str,
    x_domain_line: str,
    x_entry_point: str,
    x_source_line_span: str,
    x_evidence_ref: str,
    x_counterexample_id: str,
    x_contract_posture: str,
    x_proposed_operation_slug: str,
) -> dict[str, Any]:
    """Construct an operation-instance dict conforming to CONTRACT-CONVENTIONS.md."""
    evidence_sha256 = _compute_ref_file_sha256(repo_root, x_evidence_ref)

    unknowns: list[str] = [
        "STATIC_SOURCE_ONLY",
        "OPERATION_ID_PENDING_B05",
    ]
    if proposed_store_id:
        unknowns.append(f"STORE_ID_PROPOSED:{proposed_store_id}")
    for tok in extra_unknowns:
        if tok not in unknowns:
            unknowns.append(tok)

    role_ref = x_evidence_ref if role_status != "UNKNOWN" else None
    recovery_ref = (
        "scripts/restore_drill_verify.py"
        if "RESTORE_DRILL" in " ".join(unknowns)
        else x_evidence_ref
    )

    return {
        "consumer_id": consumer_id,
        "operation_id": "UNASSIGNED_B05",
        "store_id": store_id,
        "source_version": BASE_COMMIT_SHA,
        "evidence_timestamp": STATIC_EVIDENCE_TIMESTAMP,
        "evidence_sha256": evidence_sha256,
        "status": status,
        "unknowns": unknowns,
        "principal": _field_obj(principal, "PARTIAL", x_evidence_ref),
        "role": _field_obj(role, role_status, role_ref),
        "tenant": _field_obj(tenant, "PARTIAL", x_evidence_ref),
        "authorization": _field_obj(authorization, "PARTIAL", x_evidence_ref),
        "transaction": _field_obj(transaction, "PARTIAL", x_evidence_ref),
        "effects": _field_obj(effects, "PARTIAL", x_evidence_ref),
        "retries": _field_obj(retries, "PARTIAL", x_evidence_ref),
        "idempotency": _field_obj(idempotency, "PARTIAL", x_evidence_ref),
        "failure": _field_obj(failure, "PARTIAL", x_evidence_ref),
        "retention": _field_obj(retention, "PARTIAL", x_evidence_ref),
        "recovery": _field_obj(recovery, recovery_status, recovery_ref),
        "x_domain_line": x_domain_line,
        "x_entry_point": x_entry_point,
        "x_source_line_span": x_source_line_span,
        "x_evidence_ref": x_evidence_ref,
        "x_counterexample_id": x_counterexample_id,
        "x_contract_posture": x_contract_posture,
        "x_proposed_operation_slug": x_proposed_operation_slug,
    }


def get_domain_operation_instances(
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return the 21 deep domain operation instances (3 per line D04..D10)."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[4]

    return [
        # --- D04: CRM, cases/practices, visa/company/tax/property ---
        _build_canonical_record(
            repo_root,
            consumer_id="src_a7ceb266c9ec6438",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.clients",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "MISSING_DB_UNIQUE_NORMALIZED_PHONE_CONSTRAINT",
                "RESTORE_DRILL_CLIENTS_FAIL",
            ],
            principal="service:backend-rag:crm.client_core",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_single_tenant",
            authorization="FastAPI get_current_user + RBAC check at router boundary; SQL lacks RLS",
            transaction="asyncpg pool.acquire() explicit conn.transaction() for create/update/soft-delete",
            effects=[
                "INSERT INTO clients (full_name, email, phone, status, assigned_to, custom_fields, created_by)",
                "INSERT INTO audit_logs (action, resource_type='client', resource_id, changes)",
                "Out-of-tx Google Drive folder provisioning (create_client_folder)",
            ],
            retries="None in client_core.py; caller-dependent HTTP retry",
            idempotency="Non-atomic SELECT on REGEXP_REPLACE(phone, '[^0-9]', '', 'g') >= 7 digits before INSERT; concurrent requests can duplicate",
            failure="Raises ValueError on application-level duplicate email/phone; Drive folder failure leaves client row with drive_folder_id=NULL",
            retention="Soft-delete via status='inactive' and deleted_at=NOW() (lines 558-608); no automated purge",
            recovery="scripts/restore_drill_verify.py records clients: FAIL due to schema drift",
            recovery_status="BLOCKED",
            x_domain_line="D04",
            x_entry_point="apps/backend-rag/backend/services/crm/client_core.py",
            x_source_line_span="261-346,466-608",
            x_evidence_ref="apps/backend-rag/backend/services/crm/client_core.py:261-608",
            x_counterexample_id="CE-B06-01",
            x_contract_posture="transitional",
            x_proposed_operation_slug="d04.crm.client_core.lifecycle_write",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_36852546767b6d1b",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.practices",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "PRACTICE_INVOICE_SIDE_EFFECT_SPLIT_TX",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="http:router:crm_practices",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_single_tenant",
            authorization="Depends(get_current_user) + team_member/admin role check in router",
            transaction="create_practice (lines 775-1045) uses single conn.fetchrow; patch_practice (lines 1590-1745) wraps UPDATE + status_transitions in conn.transaction()",
            effects=[
                "INSERT INTO practices (...) RETURNING id, uuid",
                "UPDATE practices SET status, payment_status, completion_date, updated_at",
                "INSERT INTO activity_log / audit_logs on state transition",
                "Side-effect trigger to invoice_service.trigger_on_sending_invoice when status='sending_invoice'",
            ],
            retries="None on practice mutation; downstream invoice trigger is fire-and-forget",
            idempotency="Non-idempotent POST /api/crm/practices (no client idempotency key); PATCH is state-conditional",
            failure="HTTPException(400/404/500); downstream invoice_service failure logs error without rolling back practice status",
            retention="Soft-delete via status='cancelled' or deleted_at; retained indefinitely in public.practices",
            recovery="Backed by Fly Postgres volume snapshot; public.practices omitted from restore_drill_verify.py 6-table subset",
            recovery_status="UNKNOWN",
            x_domain_line="D04",
            x_entry_point="apps/backend-rag/backend/app/routers/crm_practices.py",
            x_source_line_span="775-1045,1590-1745",
            x_evidence_ref="apps/backend-rag/backend/app/routers/crm_practices.py:775-1745",
            x_counterexample_id="CE-B06-02",
            x_contract_posture="transitional",
            x_proposed_operation_slug="d04.crm.practices.mutate_and_transition",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_3cfe047e6c2ec7f8",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.visa_oracle_sessions",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "VISA_ORACLE_SESSION_PERSISTENCE_SWALLOWED",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="http:router:visa_oracle_evaluate",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="public_funnel:visa_oracle",
            authorization="Public/session-scoped funnel endpoint with rate limiting; E33 case actions require authenticated user",
            transaction="Single-statement UPSERT into visa_oracle_sessions inside evaluate_path.py:240-285; E33 case router e33_cases.py uses conn.transaction()",
            effects=[
                "INSERT INTO visa_oracle_sessions (session_id, answers_json, recommendation_json, updated_at) ON CONFLICT (session_id) DO UPDATE",
                "Companion e33_cases.py writes public.e33_cases and public.e33_documents",
            ],
            retries="None; best-effort persistence on evaluate_path",
            idempotency="Idempotent on session_id via ON CONFLICT (session_id) DO UPDATE",
            failure="DB exception caught and logged as warning in evaluate_path.py; returns computed decision tree result with non-durable session",
            retention="No automated TTL purge found in evaluate_path.py for visa_oracle_sessions",
            recovery="visa_oracle_sessions and e33_cases omitted from scripts/restore_drill_verify.py",
            recovery_status="UNKNOWN",
            x_domain_line="D04",
            x_entry_point="apps/backend-rag/backend/app/routers/visa_oracle_evaluate.py",
            x_source_line_span="137-285",
            x_evidence_ref="apps/backend-rag/backend/services/visa_engine/evaluate_path.py:137-285",
            x_counterexample_id="NONE",
            x_contract_posture="bug",
            x_proposed_operation_slug="d04.visa_oracle.evaluate_and_persist_session",
        ),
        # --- D05: Pricing, quoting, invoicing, payments, reconciliation ---
        _build_canonical_record(
            repo_root,
            consumer_id="src_55053b267fa8ea4a",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.invoices",
            status="PARTIAL",
            extra_unknowns=[
                "NOT_ENRICHED_THIS_PHASE",
                "INVOICE_EMAIL_DRIVE_DB_SPLIT_COMMIT",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="service:backend-rag:invoicing.invoice_service",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_single_tenant",
            authorization="Internal service invoked by crm_practices router after RBAC check",
            transaction="Unwrapped sequential writes across email_send_log (lines 152-192), Drive upload (lines 229-248), and _update_practice_with_invoice (lines 440-611: practices.documents, invoices UPSERT, activity_log) without conn.transaction()",
            effects=[
                "INSERT/UPDATE email_send_log via log_email_attempt and record_email_result (lines 152-192)",
                "External Google Drive PDF upload via upload_file_to_folder (lines 229-248)",
                "UPDATE practices SET documents = $1, updated_at = NOW() WHERE id = $2 (lines 490-497)",
                "INSERT INTO invoices (practice_id, client_id, invoice_number, amount_idr, discount_amount_idr, ...) ON CONFLICT (practice_id) DO UPDATE (lines 531-595)",
                "INSERT INTO activity_log (entity_type='practice', action='invoice_generated', ...) (lines 598-609)",
            ],
            retries="Manual retry via regenerate_invoice (lines 613-627) re-runs trigger_on_sending_invoice",
            idempotency="invoices table uses ON CONFLICT (practice_id) DO UPDATE, but re-triggering re-sends email and uploads a duplicate PDF to Google Drive",
            failure="Partial failure between email send, Drive upload, UPDATE practices, and INSERT INTO invoices leaves split state across practices.documents and public.invoices",
            retention="Financial records retained indefinitely in public.invoices, public.activity_log, and Google Drive",
            recovery="Manual reconciliation via regenerate_invoice; public.invoices omitted from restore_drill_verify.py",
            recovery_status="UNKNOWN",
            x_domain_line="D05",
            x_entry_point="apps/backend-rag/backend/services/invoicing/invoice_service.py",
            x_source_line_span="62-270,440-628",
            x_evidence_ref="apps/backend-rag/backend/services/invoicing/invoice_service.py:62-628",
            x_counterexample_id="CE-B06-02",
            x_contract_posture="bug",
            x_proposed_operation_slug="d05.invoicing.trigger_on_sending_invoice",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_fe7d40f6ffa95a8b",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.garuda_orders",
            status="PARTIAL",
            extra_unknowns=[
                "NOT_ENRICHED_THIS_PHASE",
                "XENDIT_STATIC_CALLBACK_TOKEN_AUTH",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="service:backend-rag:payments.xendit",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_garuda_commerce",
            authorization="Xendit callback token verification (x-callback-token == XENDIT_WEBHOOK_TOKEN) via constant-time comparison",
            transaction="Delegates webhook state transition to garuda_orders/repository.py handle_paid_event inside conn.transaction() with SELECT ... FOR UPDATE",
            effects=[
                "Outbound HTTP POST https://api.xendit.co/v2/invoices (create_checkout_session lines 192-233)",
                "Inbound parse_event (lines 248-318) -> garuda_payment_inbox / UPDATE garuda_orders SET status='PAID', paid_at=NOW()",
                "INSERT INTO garuda_order_events (order_id, event_type, payload_json)",
            ],
            retries="Xendit webhook delivery retries on non-2xx; outbound httpx calls use 20s timeout without automatic retry",
            idempotency="Webhook replay guarded by SELECT ... FOR UPDATE on garuda_orders and terminal state check in handle_paid_event",
            failure="Raises PaymentSignatureError on invalid callback token or PaymentProviderError on Xendit HTTP >= 400",
            retention="Order and payment event logs retained indefinitely in garuda_orders, garuda_payment_inbox, and garuda_order_events",
            recovery="Recoverable by replaying Xendit webhook event or querying Xendit invoice status API",
            recovery_status="PARTIAL",
            x_domain_line="D05",
            x_entry_point="apps/backend-rag/backend/services/payments/xendit.py",
            x_source_line_span="192-380",
            x_evidence_ref="apps/backend-rag/backend/services/payments/xendit.py:192-380",
            x_counterexample_id="NONE",
            x_contract_posture="intentional",
            x_proposed_operation_slug="d05.payments.xendit_checkout_and_webhook",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_a3385c4f03c66ace",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.reconciliation_log",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "RECONCILE_UNARMED_BANK_TXN_LOCK_AND_DECOMPOSITION_WARNING",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="service:backend-rag:garuda_ops.adapters_pg",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_single_tenant",
            authorization="Internal ops/accounting service invoked by authenticated admin/accounting endpoints",
            transaction="reconcile_service.py confirm_payment wraps all 5 table writes in async with conn.transaction() at line 102 with SELECT ... FROM practices WHERE id = $1 FOR UPDATE (line 105)",
            effects=[
                "UPDATE practices SET payment_status = $1, paid_amount = $2, updated_at = now() WHERE id = $3 (line 117)",
                "UPDATE invoices SET paid_date = now(), payment_method = $1, payment_reference = $2, paid_amount_idr = COALESCE(paid_amount_idr, 0) + $3 WHERE id = $4 (line 130)",
                "UPDATE bank_transactions SET reconciled_status = 'matched', matched_practice_id = $1, matched_invoice_id = $2 WHERE id = $3 (line 147)",
                "INSERT INTO weekly_cashout (...) RETURNING id (lines 163, 195)",
                "INSERT INTO reconciliation_log (...) RETURNING id (line 226)",
            ],
            retries="None in reconcile_service.py",
            idempotency="Locks practices row FOR UPDATE (line 105), but does not lock bank_transactions or reject already-matched bank_txn_id; duplicate confirm_payment call increments practices.paid_amount and invoices.paid_amount_idr twice and inserts duplicate weekly_cashout and reconciliation_log rows",
            failure="Raises ReconcileError on invalid status or missing practice (rolling back conn.transaction()); D4 guard at lines 85-92 logs warning without raising when decomposition_sum != amount_applied_idr",
            retention="Indefinite financial audit retention in practices, invoices, bank_transactions, weekly_cashout, and reconciliation_log",
            recovery="Transactional rollback protects against partial mid-tx failure; duplicate confirm requires manual ledger reversal",
            recovery_status="PARTIAL",
            x_domain_line="D05",
            x_entry_point="apps/backend-rag/backend/services/garuda_ops/adapters_pg.py",
            x_source_line_span="51-250",
            x_evidence_ref="apps/backend-rag/backend/services/accounting/reconcile_service.py:51-250",
            x_counterexample_id="CE-B06-03",
            x_contract_posture="transitional",
            x_proposed_operation_slug="d05.accounting.reconcile_and_garuda_ledger",
        ),
        # --- D06: Conversations, chat, RAG sessions, WhatsApp/Telegram/portal ---
        _build_canonical_record(
            repo_root,
            consumer_id="src_4c49b82438955ab7",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.conversations",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "SSE_POST_YIELD_PERSISTENCE_SWALLOWED",
                "RESTORE_DRILL_CONVERSATIONS_CANNOT_VERIFY",
            ],
            principal="http:router:agentic_rag",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_rag_session",
            authorization="Authenticated user/session dependency on /stream and /workspace-stream",
            transaction="Autocommit single INSERT INTO conversations inside SSE generator post-yield block (lines 515-555, 1480-1525)",
            effects=[
                "SSE token stream yielded to HTTP client first",
                "INSERT INTO conversations (user_id, session_id, messages, metadata, created_at)",
                "Async fire-and-forget memory extraction to memory_facts",
            ],
            retries="None on conversation persistence after stream completion",
            idempotency="Non-idempotent append per stream turn; duplicate retry creates new conversation row if session_id not deduplicated",
            failure="Broad try/except Exception logs warning/error and swallows DB write failure AFTER client already received full streamed answer (split-brain chat history)",
            retention="Retained in public.conversations; subject to user clear/delete endpoints in conversations.py",
            recovery="scripts/restore_drill_verify.py records conversations: CANNOT-VERIFY",
            recovery_status="BLOCKED",
            x_domain_line="D06",
            x_entry_point="apps/backend-rag/backend/app/routers/agentic_rag.py",
            x_source_line_span="315-560,1185-1535",
            x_evidence_ref="apps/backend-rag/backend/app/routers/agentic_rag.py:515-555",
            x_counterexample_id="CE-B06-04",
            x_contract_posture="bug",
            x_proposed_operation_slug="d06.rag.stream_conversation_persistence",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_d88734f39509787b",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.whatsapp_message_dedup",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "WHATSAPP_WAMID_DEDUP_FAIL_OPEN",
            ],
            principal="http:router:whatsapp_chat",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="channel:meta_whatsapp_business",
            authorization="Meta webhook HMAC-SHA256 X-Hub-Signature-256 verification on POST /webhook",
            transaction="Autocommit single-statement INSERT ... ON CONFLICT for wamid claim (lines 341-374) and wa_outbox enqueue (lines 660-762)",
            effects=[
                "INSERT INTO whatsapp_message_dedup (wamid, phone, created_at) ON CONFLICT (wamid) DO NOTHING RETURNING wamid",
                "INSERT INTO wa_outbox (idempotency_key, phone, payload_json, status='pending', next_attempt_at)",
            ],
            retries="Meta retries webhook delivery on non-200; internal outbox worker retries outbound sends up to 6 attempts",
            idempotency="Idempotent on wamid when Postgres is healthy; FAILS OPEN (returns True) on DB exception at lines 369-374, permitting duplicate LLM execution",
            failure="On DB error in _claim_wamid_for_reply, logs warning and returns True (fail-open); if _enqueue_wa_outbox also fails, falls back to direct _send_whatsapp_Interactive",
            retention="whatsapp_message_dedup rows pruned after 7 days; wa_outbox retained for delivery audit",
            recovery="Outbox pending rows re-claimed on worker restart; in-flight direct fallback sends are not replayable",
            recovery_status="PARTIAL",
            x_domain_line="D06",
            x_entry_point="apps/backend-rag/backend/app/routers/whatsapp_chat.py",
            x_source_line_span="341-374,660-910",
            x_evidence_ref="apps/backend-rag/backend/app/routers/whatsapp_chat.py:341-374",
            x_counterexample_id="CE-B06-05",
            x_contract_posture="bug",
            x_proposed_operation_slug="d06.whatsapp.claim_wamid_and_enqueue_outbox",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_54faf2d6d680ab0d",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.wa_outbox",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="worker:backend-rag:integrations.wa_outbox_worker",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="channel:meta_whatsapp_business",
            authorization="Internal background daemon loop holding backend Postgres pool",
            transaction="Short CTE claim transaction using FOR UPDATE SKIP LOCKED (lines 635-680); external Meta Graph API call outside DB transaction; final status UPDATE in separate connection acquisition",
            effects=[
                "UPDATE wa_outbox SET status='claimed', locked_at=NOW(), attempts=attempts+1 WHERE id IN (SELECT id FROM wa_outbox WHERE status IN ('pending','generating') AND next_attempt_at <= NOW() FOR UPDATE SKIP LOCKED)",
                "Outbound HTTP POST to Meta Graph API /{phone_number_id}/messages",
                "UPDATE wa_outbox SET status='done' | 'pending' | 'failed', provider_message_id=$2, last_error=$3 (206_wa_meta_inbox.sql:79)",
            ],
            retries="Bounded exponential backoff [5, 30, 120, 600, 1800, 3600] seconds across max_attempts=6 before terminal status='failed'",
            idempotency="Enforced at enqueue via UNIQUE(idempotency_key); crash between Meta HTTP 200 and UPDATE status='done' can re-send after stale lock timeout",
            failure="Moves exhausted rows to terminal status='failed' with last_error populated; alerts via internal logger",
            retention="Done and failed rows retained in public.wa_outbox",
            recovery="Stale 'claimed' rows older than lock timeout are re-claimed by worker poll loop",
            recovery_status="PARTIAL",
            x_domain_line="D06",
            x_entry_point="apps/backend-rag/backend/services/integrations/wa_outbox_worker.py",
            x_source_line_span="635-860",
            x_evidence_ref="apps/backend-rag/backend/services/integrations/wa_outbox_worker.py:635-860",
            x_counterexample_id="NONE",
            x_contract_posture="intentional",
            x_proposed_operation_slug="d06.whatsapp.outbox_claim_and_dispatch",
        ),
        # --- D07: Knowledge, KBLI, legal, tax, visa, property corpora & KG ---
        _build_canonical_record(
            repo_root,
            consumer_id="src_c0f6810d71583357",
            store_id="unknown:unknown:unknown",
            proposed_store_id="qdrant:unknown:qdrant-cloud/kbli_2025_final_hybrid",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
            ],
            principal="http:router:kbli_notebook",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="corpus:kbli_2025_public",
            authorization="Public/API key read-only endpoints; query sanitization and rate limiting",
            transaction="Read-only cross-store fan-out across Postgres public.kbli_documents, public.kg_nodes/kg_edges, and Qdrant kbli_2025_final_hybrid (lines 60-735)",
            effects=[
                "SELECT FROM kbli_documents WHERE code = $1",
                "SELECT FROM kg_nodes / kg_edges for KBLI regulatory neighbourhood",
                "Qdrant hybrid search on kbli_2025_final_hybrid (1536-dim text-embedding-3-small)",
            ],
            retries="Qdrant client internal retry on transient transport errors; Postgres single-query read",
            idempotency="Pure read path; idempotent",
            failure="Degrades gracefully to PG-only or Qdrant-only results if companion store times out; raises HTTPException(404/503) if primary lookup fails",
            retention="Immutable reference corpus until KBLI rebuild migration",
            recovery="Rebuilt deterministically from KBLI 2025 source corpus and gold_kbli_2025.json",
            recovery_status="PARTIAL",
            x_domain_line="D07",
            x_entry_point="apps/backend-rag/backend/app/routers/kbli_notebook.py",
            x_source_line_span="60-735",
            x_evidence_ref="apps/backend-rag/backend/app/routers/kbli_notebook.py:60-735",
            x_counterexample_id="NONE",
            x_contract_posture="intentional",
            x_proposed_operation_slug="d07.kbli.hybrid_notebook_lookup",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_68fe091af1bf456a",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.kg_nodes",
            status="PARTIAL",
            extra_unknowns=[
                "NOT_ENRICHED_THIS_PHASE",
                "KG_WATERMARK_COMMIT_SPLIT_FROM_BATCH_UPSERT",
            ],
            principal="service:backend-rag:knowledge_graph.incremental_builder",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="corpus:knowledge_graph_global",
            authorization="Internal background builder guarded by Redis distributed lock kg:incremental_builder:lock",
            transaction="Per-batch conn.transaction() for kg_nodes/kg_edges UPSERTs, followed by separate system_settings watermark update (lines 300-480)",
            effects=[
                "Redis SET NX EX on kg:incremental_builder:lock",
                "Qdrant scroll over legal_unified_hybrid / tax_genius_hybrid / visa_inchen_hybrid",
                "INSERT INTO kg_nodes (...) ON CONFLICT (entity_id) DO UPDATE",
                "INSERT INTO kg_edges (...) ON CONFLICT (source_id, target_id, relation_type) DO UPDATE",
                "INSERT INTO system_settings (key, value) ON CONFLICT (key) DO UPDATE (watermark)",
            ],
            retries="Next scheduled incremental builder tick retries from last committed watermark in system_settings",
            idempotency="Node/edge writes are idempotent via ON CONFLICT DO UPDATE; watermark lag causes redundant LLM extraction work",
            failure="Releases or expires Redis lock; uncommitted batch rolls back while committed batches persist ahead of watermark",
            retention="Permanent KG storage in public.kg_nodes (108k+ nodes) and public.kg_edges (242k+ edges)",
            recovery="Replayable from Qdrant collections by resetting watermark in public.system_settings",
            recovery_status="PARTIAL",
            x_domain_line="D07",
            x_entry_point="apps/backend-rag/backend/services/knowledge_graph/incremental_builder.py",
            x_source_line_span="300-480",
            x_evidence_ref="apps/backend-rag/backend/services/knowledge_graph/incremental_builder.py:300-480",
            x_counterexample_id="CE-B06-06",
            x_contract_posture="transitional",
            x_proposed_operation_slug="d07.kg.incremental_builder_upsert",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_990f416b23c04a69",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.kbli_documents",
            status="PARTIAL",
            extra_unknowns=[
                "NOT_ENRICHED_THIS_PHASE",
            ],
            principal="service:backend-rag:kbli_catalogue_membership",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="corpus:kbli_2025_public",
            authorization="Internal service checking KBLI 5-digit membership across PG and Qdrant; companion kg_auto_expansion writes staging tables only",
            transaction="Read-only membership verification across public.kbli_documents and Qdrant kbli_2025_final_hybrid (lines 39-125); companion kg_auto_expansion.py:472-640 writes public.kg_nodes_staging / kg_edges_staging",
            effects=[
                "SELECT code FROM kbli_documents WHERE code = ANY($1)",
                "Qdrant retrieve/scroll check on kbli_2025_final_hybrid",
                "Companion kg_auto_expansion INSERT INTO kg_nodes_staging / kg_edges_staging (quarantine gate before production kg_nodes)",
            ],
            retries="None; synchronous verification helper",
            idempotency="Idempotent read verification and ON CONFLICT DO NOTHING on staging tables",
            failure="Returns membership mismatch report when PG kbli_documents and Qdrant kbli_2025_final_hybrid drift",
            retention="Reference catalogue in kbli_documents; staging rows retained until reviewed/promoted",
            recovery="Re-sync script restores parity from canonical KBLI 2025 dataset",
            recovery_status="PARTIAL",
            x_domain_line="D07",
            x_entry_point="apps/backend-rag/backend/services/kbli_catalogue_membership.py",
            x_source_line_span="39-125",
            x_evidence_ref="apps/backend-rag/backend/services/kbli_catalogue_membership.py:39-125",
            x_counterexample_id="NONE",
            x_contract_posture="intentional",
            x_proposed_operation_slug="d07.kbli.catalogue_membership_and_kg_staging",
        ),
        # --- D08: Document ingestion, OCR, Drive, artifacts & storage ---
        _build_canonical_record(
            repo_root,
            consumer_id="src_fbda17e1dfb27de7",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.intake_commit_audit",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="service:backend-rag:intake.writer",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_single_tenant",
            authorization="Operator-approved intake review commit with optimistic version lock",
            transaction="Single explicit conn.transaction(isolation='repeatable_read') across clients, documents, document_routing_proposal, intake_commit_audit, and intake_queue (lines 220-325, 660-1135)",
            effects=[
                "INSERT/UPDATE public.clients (matched or created subject)",
                "INSERT INTO public.documents (client_id, document_type, file_url, extracted_data)",
                "UPDATE public.document_routing_proposal SET status='committed'",
                "INSERT INTO public.intake_commit_audit (intake_id, committed_by, diff_json)",
                "UPDATE public.intake_queue SET status='committed', version=version+1",
            ],
            retries="No automatic retry on conflict; operator must reload on optimistic lock version mismatch",
            idempotency="Idempotent against double-commit via optimistic version check on intake_queue and unique audit guard",
            failure="Full transactional rollback across all 5 tables on any constraint, serialization, or version error",
            retention="Permanent compliance audit trail in intake_commit_audit and documents",
            recovery="Transactional atomicity prevents partial DB state; backed by Fly Postgres volume",
            recovery_status="PARTIAL",
            x_domain_line="D08",
            x_entry_point="apps/backend-rag/backend/services/intake/writer.py",
            x_source_line_span="220-325,660-1135",
            x_evidence_ref="apps/backend-rag/backend/services/intake/writer.py:660-1135",
            x_counterexample_id="NONE",
            x_contract_posture="intentional",
            x_proposed_operation_slug="d08.intake.atomic_review_commit",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_56b35953c85895b6",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.intake_queue",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "INTAKE_CRM_DELIVERY_OUT_OF_TX_WINDOW",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="service:backend-rag:intake.crm_delivery",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_single_tenant",
            authorization="Internal intake delivery service invoked by intake_review router / worker",
            transaction="Phase 1 holds pg_try_advisory_xact_lock inside conn.transaction() (lines 82-240); Phase 2 calls push_IntakeItem_to_crm outside the transaction (lines 245-360) and then writes delivery status",
            effects=[
                "SELECT pg_try_advisory_xact_lock(hashtext(intake_id))",
                "Out-of-tx HTTP/service call push_IntakeItem_to_crm (creates/updates CRM client & documents)",
                "UPDATE intake_queue status/delivery outcome (terminal failure state 'dead' per 212_intake_unified.sql:57)",
            ],
            retries="Retryable via intake_review retry endpoint when delivery fails before terminal 'dead' state",
            idempotency="Advisory lock serializes Phase 1, but if Phase 2 succeeds in CRM and crashes before final UPDATE intake_queue, retry re-pushes to CRM",
            failure="Records failure detail if push_IntakeItem_to_crm raises; crash window between Phase 1 and Phase 2 leaves delivery outcome unrecorded",
            retention="Retained in public.intake_queue",
            recovery="Operator retry via intake_review router after verifying whether CRM client was already created",
            recovery_status="PARTIAL",
            x_domain_line="D08",
            x_entry_point="apps/backend-rag/backend/services/intake/crm_delivery.py",
            x_source_line_span="82-360",
            x_evidence_ref="apps/backend-rag/backend/services/intake/crm_delivery.py:82-360",
            x_counterexample_id="CE-B06-07",
            x_contract_posture="transitional",
            x_proposed_operation_slug="d08.intake.crm_delivery_resolve_and_push",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_d3e3b6647a4d9614",
            store_id="unknown:unknown:unknown",
            proposed_store_id="object:fly:tigris-garuda-artifacts",
            status="PARTIAL",
            extra_unknowns=[
                "NOT_ENRICHED_THIS_PHASE",
            ],
            principal="service:backend-rag:garuda_artifacts.tigris_store",
            role="s3_iam:tigris_bucket_credentials",
            role_status="PARTIAL",
            tenant="workspace:balizero_garuda_artifacts",
            authorization="AWS S3v4 signed credentials scoped to Tigris bucket",
            transaction="Single-object atomic S3 PutObject with IfNoneMatch='*' conditional header (lines 210-355)",
            effects=[
                "S3 PutObject(Bucket, Key=sha256_addressed_key, Body, IfNoneMatch='*')",
                "On PreconditionFailed/412, S3 HeadObject verifies existing ETag/content length matches content hash",
            ],
            retries="boto3 standard retry mode on transient 5xx/network errors; 412 handled deterministically via HeadObject",
            idempotency="Strictly idempotent content-addressed write-once store (IfNoneMatch='*' + ETag verification)",
            failure="Raises ArtifactImmutabilityError if existing key has mismatched ETag/size; raises storage error on S3 outage",
            retention="Immutable content-addressed objects retained in Tigris S3 bucket",
            recovery="Content-addressed keys allow safe re-put from source bytes without overwrite risk",
            recovery_status="PARTIAL",
            x_domain_line="D08",
            x_entry_point="apps/backend-rag/backend/services/garuda_artifacts/tigris_store.py",
            x_source_line_span="210-355",
            x_evidence_ref="apps/backend-rag/backend/services/garuda_artifacts/tigris_store.py:210-355",
            x_counterexample_id="NONE",
            x_contract_posture="intentional",
            x_proposed_operation_slug="d08.artifacts.tigris_write_once_put",
        ),
        # --- D09: Editorial, News Room, WR2, social & publishing ---
        _build_canonical_record(
            repo_root,
            consumer_id="src_0634ad7a081c6d3f",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.news_items",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "NEWS_PUBLISH_AND_QUEUE_SPLIT_AUTOCOMMIT",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="http:router:news",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="editorial:balizero_news_room",
            authorization="API key / editorial JWT guard + Legge 5 approval_state gate",
            transaction="Separate autocommit statements on public.news_items and public.post_publish_queue (lines 115-295, 415-555)",
            effects=[
                "UPDATE public.news_items SET status='published', published_at=NOW(), position=$2",
                "INSERT INTO public.post_publish_queue (article_id, action, status='pending') ON CONFLICT DO NOTHING",
            ],
            retries="Poller retries post_publish_queue items up to 3 attempts; router publish endpoint is caller-retried",
            idempotency="post_publish_queue uses ON CONFLICT DO NOTHING; news_items UPDATE is state-idempotent",
            failure="If process dies after UPDATE news_items before INSERT post_publish_queue, article is marked published in DB without MDX/GitHub sync queued",
            retention="Permanent editorial archive in public.news_items",
            recovery="Re-enqueue missing post_publish_queue row via editorial repair endpoint",
            recovery_status="PARTIAL",
            x_domain_line="D09",
            x_entry_point="apps/backend-rag/backend/app/routers/news.py",
            x_source_line_span="115-295,415-555",
            x_evidence_ref="apps/backend-rag/backend/app/routers/news.py:415-555",
            x_counterexample_id="CE-B06-08",
            x_contract_posture="transitional",
            x_proposed_operation_slug="d09.editorial.news_publish_and_enqueue",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_59070a3d3043fb26",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.war_room_drafts",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="service:backend-rag:canva_renderer_v2._pg",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="editorial:balizero_war_room_wr2",
            authorization="Internal WR2 pipeline service; outward Instagram publish gated by explicit human approval_state (Legge 5)",
            transaction="Per-method connection acquisition in canva_renderer_v2/_pg.py and war_room/repository.py:72-355",
            effects=[
                "INSERT/UPDATE public.war_room_drafts (topic, slides_json, render_urls, status)",
                "INSERT INTO public.war_room_posts (draft_id, platform, external_post_id, published_at)",
                "Optional notification enqueue into public.wa_outbox for editorial review",
            ],
            retries="Stage-level retries in WR2 orchestrator",
            idempotency="Draft updates keyed by draft_id; published post registration keyed by draft_id + platform",
            failure="Marks war_room_drafts.status='failed' with error log on render or publish failure",
            retention="Retained in public.war_room_drafts and public.war_room_posts",
            recovery="Failed drafts can be re-rendered from stored slides_json in public.war_room_drafts",
            recovery_status="PARTIAL",
            x_domain_line="D09",
            x_entry_point="apps/backend-rag/backend/services/canva_renderer_v2/_pg.py",
            x_source_line_span="72-355",
            x_evidence_ref="apps/backend-rag/backend/services/war_room/repository.py:72-355",
            x_counterexample_id="NONE",
            x_contract_posture="intentional",
            x_proposed_operation_slug="d09.wr2.draft_render_and_post_registry",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_737479819e0beeb6",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.post_publish_queue",
            status="PARTIAL",
            extra_unknowns=[
                "NOT_ENRICHED_THIS_PHASE",
                "POST_PUBLISH_POLLER_GIT_PUSH_CALLBACK_SPLIT",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="daemon:pro:bali-intel-scraper.post_publish_poller",
            role="http_api_key:X_API_Key_editorial_poller",
            role_status="PARTIAL",
            tenant="editorial:balizero_news_room",
            authorization="Pro LaunchAgent com.balizero.post-publish-poller authenticating to backend API via X-API-Key",
            transaction="Distributed 3-step workflow: HTTP GET /pending -> local git branch + MDX write + git push -> HTTP POST /{id}/done or /{id}/failed (lines 1681-1840)",
            effects=[
                "GET /api/intel/post-publish-queue/pending reads public.post_publish_queue (default status='pending')",
                "Local filesystem write to apps/mouth/src/content/articles/<category>/<slug>.mdx",
                "git push origin editorial branch + PR creation on GitHub",
                "POST /api/intel/post-publish-queue/{id}/done updates status='done', attempts=attempts+1",
            ],
            retries="Polls every 300s via LaunchAgent; retries up to 3 attempts before status='failed'",
            idempotency="Non-atomic across git push and /done callback; retry after mid-flight crash encounters existing remote git branch/PR",
            failure="Calls POST /api/intel/post-publish-queue/{id}/failed with error message; increments attempts up to 3",
            retention="Queue history retained in public.post_publish_queue; MDX files committed in git history",
            recovery="Manual git branch cleanup or marking queue item done after verifying PR exists on GitHub",
            recovery_status="PARTIAL",
            x_domain_line="D09",
            x_entry_point="apps/bali-intel-scraper/scripts/post_publish_poller.py",
            x_source_line_span="1681-1840",
            x_evidence_ref="apps/bali-intel-scraper/scripts/post_publish_poller.py:1681-1840",
            x_counterexample_id="CE-B06-08",
            x_contract_posture="transitional",
            x_proposed_operation_slug="d09.editorial.post_publish_poller_sync",
        ),
        # --- D10: Research-OS, NAGA, intelligence, memory & autonomous cells ---
        _build_canonical_record(
            repo_root,
            consumer_id="src_b3bccbae2cc91a8c",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id='pg:fly:nuzantara-postgres/public.naga_sessions',
            status="PARTIAL",
            extra_unknowns=['ACTOR_IDENTITY_UNRESOLVED', 'RESTORE_DRILL_TABLE_OMITTED', 'REPLAY_IDEMPOTENCY_UNPROVED', 'CLAIM_EXPIRY_NOT_ERASURE_PROOF', 'PERSISTENCE_FAILURE_RETURNS_NONE'],
            principal="service:backend-rag:naga.persist",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="intelligence:naga_research_os",
            authorization='Internal save_session(pool, state); this function performs no authorization check.',
            transaction='Explicit pool.acquire() and conn.transaction() in apps/backend-rag/backend/services/naga/persist.py:24-217; one transaction covers the four naga_* tables.',
            effects=['INSERT INTO naga_sessions', 'INSERT INTO naga_sources; ON CONFLICT (url, session_id) DO NOTHING', 'INSERT INTO naga_claims', 'INSERT INTO naga_claim_evidence; ON CONFLICT (claim_id, source_id, relation) DO NOTHING'],
            retries='No retry loop inside save_session; caught failure returns None to the caller.',
            idempotency='Each call allocates a new session UUID and claim UUIDs; ON CONFLICT DO NOTHING only deduplicates source URLs within a session and claim-evidence links.',
            failure='The transaction context rolls back on errors; except Exception logs the failure and returns None.',
            retention='Claim expires_at is set to 30 days for visa/immigration and 90 days otherwise; expiry metadata does not prove erasure.',
            recovery='No replay or restore procedure is implemented in save_session; recovery for naga_* tables remains unproved.',
            recovery_status="PARTIAL",
            x_domain_line="D10",
            x_entry_point="apps/backend-rag/backend/services/naga/persist.py",
            x_source_line_span='24-217',
            x_evidence_ref='apps/backend-rag/backend/services/naga/persist.py:24-217',
            x_counterexample_id="NONE",
            x_contract_posture="intentional",
            x_proposed_operation_slug='d10.naga.save_session',
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_e2cc71af6590d0d0",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.memory_facts",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "VOLATILE_RAM_FALLBACK_WITHOUT_POSTGRES_RESYNC",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="service:backend-rag:memory.memory_service_postgres",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_user_memory",
            authorization="Internal memory service scoped by user_id",
            transaction="Per-statement autocommit on public.memory_facts and public.user_stats (lines 82-188, 228-315); volatile RAM fallback when pool is None or raises",
            effects=[
                "INSERT INTO public.memory_facts (user_id, fact_text, category, confidence, created_at) ON CONFLICT DO NOTHING",
                "INSERT INTO public.user_stats (user_id, interaction_count, last_active) ON CONFLICT (user_id) DO UPDATE",
                "Fallback mutation of process-local dict self.in_memory_storage[user_id] on DB failure",
            ],
            retries="None; falls back immediately to volatile self.in_memory_storage",
            idempotency="Postgres path deduplicates via ON CONFLICT DO NOTHING; RAM fallback appends in-memory list with zero write-back on DB recovery",
            failure="Swallows Postgres outage into volatile RAM dict, causing silent memory loss on process restart and split-brain reads",
            retention="Retained in public.memory_facts; volatile fallback lost on worker restart",
            recovery="Volatile RAM writes are unrecoverable after process exit; Postgres rows backed by Fly volume",
            recovery_status="PARTIAL",
            x_domain_line="D10",
            x_entry_point="apps/backend-rag/backend/services/memory/memory_service_postgres.py",
            x_source_line_span="82-188,228-315",
            x_evidence_ref="apps/backend-rag/backend/services/memory/memory_service_postgres.py:228-315",
            x_counterexample_id="CE-B06-09",
            x_contract_posture="bug",
            x_proposed_operation_slug="d10.memory.user_memory_facts_upsert",
        ),
        _build_canonical_record(
            repo_root,
            consumer_id="src_d9f387b7f19b73dd",
            store_id="pg:fly:nuzantara-postgres/public",
            proposed_store_id="pg:fly:nuzantara-postgres/public.collective_memories",
            status="PARTIAL",
            extra_unknowns=[
                "ACTOR_IDENTITY_UNRESOLVED",
                "RESTORE_DRILL_TABLE_OMITTED",
            ],
            principal="service:backend-rag:memory.collective_memory_service",
            role="UNKNOWN_RUNTIME_DB_ROLE",
            role_status="UNKNOWN",
            tenant="workspace:balizero_collective_memory",
            authorization="Internal collective memory service + autonomous cell-core SQLite WAL stores",
            transaction="Postgres conn.transaction() for collective_memories + collective_memory_sources (lines 70-265) paired with Qdrant vector upsert; cell-core memory_sqlite.py:30-120 uses SQLite WAL autocommit on local tables stm and episodes",
            effects=[
                "INSERT INTO public.collective_memories (content, category, importance, embedding_id) ON CONFLICT DO UPDATE",
                "INSERT INTO public.collective_memory_sources (memory_id, source_session_id)",
                "Companion cell-core SQLite WAL writes into local tables stm (TTL-pruned) and episodes (capped at 1000 rows)",
            ],
            retries="None on PG write; cell-core SQLite busy_timeout handles local lock contention",
            idempotency="Idempotent via content similarity/key check on collective_memories; cell-core STM key-value overwrite",
            failure="Logs error and skips collective memory promotion if Postgres or Qdrant is unreachable",
            retention="Collective memories retained in PG; cell-core SQLite episodes capped at 1000 rows and stm pruned by TTL",
            recovery="PG collective_memories backed by Fly volume; local cell-core SQLite files live on host disk without cross-host replication",
            recovery_status="PARTIAL",
            x_domain_line="D10",
            x_entry_point="apps/backend-rag/backend/services/memory/collective_memory_service.py",
            x_source_line_span="70-265",
            x_evidence_ref="apps/backend-rag/backend/services/memory/collective_memory_service.py:70-265",
            x_counterexample_id="NONE",
            x_contract_posture="intentional",
            x_proposed_operation_slug="d10.memory.collective_and_cell_episodic_store",
        ),
    ]


def load_consumer_matrix_index(repo_root: Path) -> dict[str, Any]:
    """Compute source and prefix censuses from ``consumer-matrix.csv`` and compare to receipts."""
    csv_path = repo_root / CONSUMER_MATRIX_REL_PATH
    pinned = load_pinned_census_receipts(repo_root)
    source_census = compute_source_census(csv_path)
    prefix_census = compute_prefix_census(csv_path)
    comparison_errors = compare_census_to_receipts(
        source_census,
        prefix_census,
        pinned["receipt_01"],
        pinned["receipt_03"],
    )

    all_consumer_ids: set[str] = set()
    rows_by_consumer_id: dict[str, dict[str, str]] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _validate_csv_headers(reader.fieldnames, csv_path)
        for row in reader:
            cid = row["consumer_id"]
            all_consumer_ids.add(cid)
            rows_by_consumer_id[cid] = row

    prefix_scope_status_counts = summarize_prefix_scope_status(prefix_census)

    return {
        "csv_sha256": source_census["sha256"],
        "total_rows": source_census["total"],
        "all_consumer_ids": all_consumer_ids,
        "rows_by_consumer_id": rows_by_consumer_id,
        "source_census": source_census,
        "prefix_census": prefix_census,
        "prefix_scope_status_counts": prefix_scope_status_counts,
        "receipt_shas": pinned["shas"],
        "comparison_errors": comparison_errors,
    }


def verify_all(repo_root: Path) -> dict[str, Any]:
    """Run B06 census parity and instance generation checks."""
    pinned = load_pinned_census_receipts(repo_root)
    instances = get_domain_operation_instances(repo_root)

    by_domain_line: dict[str, int] = {}
    errors: list[str] = []
    for idx, inst in enumerate(instances):
        dline = str(inst.get("x_domain_line", ""))
        by_domain_line[dline] = by_domain_line.get(dline, 0) + 1
        ref_sha = _compute_ref_file_sha256(repo_root, inst["x_evidence_ref"])
        if inst["evidence_sha256"] != ref_sha:
            errors.append(
                f"instance[{idx}] ({inst['consumer_id']}) sha mismatch: "
                f"{inst['evidence_sha256']} != {ref_sha}"
            )

    for expected_line in ("D04", "D05", "D06", "D07", "D08", "D09", "D10"):
        if by_domain_line.get(expected_line, 0) < 3:
            errors.append(
                f"Domain line {expected_line} has {by_domain_line.get(expected_line, 0)} instances; expected >= 3."
            )

    csv_path = repo_root / CONSUMER_MATRIX_REL_PATH
    csv_present = csv_path.exists()
    prefix_scope_status_counts = summarize_prefix_scope_status(pinned["receipt_03"])

    if csv_present:
        matrix_info = load_consumer_matrix_index(repo_root)
        errors.extend(matrix_info["comparison_errors"])
        for idx, inst in enumerate(instances):
            cid = inst["consumer_id"]
            if cid not in matrix_info["all_consumer_ids"]:
                errors.append(
                    f"instance[{idx}] consumer_id {cid!r} not in consumer-matrix.csv"
                )

    return {
        "ok": len(errors) == 0,
        "csv_present": csv_present,
        "instance_count": len(instances),
        "by_domain_line": by_domain_line,
        "receipt_shas": pinned["shas"],
        "source_census_total": pinned["receipt_01"]["total"],
        "prefix_census_total": pinned["receipt_03"]["total_rows_in_prefixes"],
        "prefix_scope_status_counts": prefix_scope_status_counts,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for B06 domain paths generator and census verifier."""
    parser = argparse.ArgumentParser(
        description="B06 Business-Domain Paths Adapter and Generator"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
        help="Path to repository root",
    )
    parser.add_argument(
        "--emit-json",
        type=Path,
        default=None,
        help="Optional path to write domain-operation-instances.json",
    )
    args = parser.parse_args(argv)

    if args.emit_json is not None:
        instances = get_domain_operation_instances(args.repo_root)
        args.emit_json.write_text(
            json.dumps(instances, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    summary = verify_all(args.repo_root)
    sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
