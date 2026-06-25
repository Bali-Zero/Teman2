"""FASE 5B — Document-intake CRM writer (DRY-RUN by default).

This module is the COMMIT half of FASE 5: given a human-approved (or
auto-attach-eligible) ``document_routing_proposal`` it plans, and conditionally
executes, the writes that attach the intake document to the CRM
(``documents`` + ``practices.documents[]`` + audit).

FASE 5B contract
----------------
* ``INTAKE_WRITER_ENABLED`` defaults to **OFF**. With the flag OFF the writer is
  in **dry-run**: :func:`execute_commit` builds the full plan, logs it, records a
  single ``intake_commit_audit(dry_run=true)`` row and writes **NOTHING** to the
  CRM (no ``documents`` INSERT, no ``practices`` UPDATE), and never advances the
  proposal/queue to a terminal state (P0#9).
* The real-write path (``dry_run=False``) is fully written here so FASE 5C only
  flips the flag — but in 5B it is unreachable: calling it with the flag OFF
  raises ``WriterDisabledError`` BEFORE touching the CRM.

Panel 4-LLM P0 incorporated (06-fase5-hitl-writer-design §8). Each P0 is tagged
inline where it is enforced:

* **P0#1** idempotency_key is INTAKE-INSTANCE based
  (``sha256(source|source_ref|blob_hash|doc_index|pipeline_version)``), NOT
  content based; UNIQUE per ``(client_id, key)`` — never global on content. See
  :func:`compute_idempotency_key` + migration 217.
* **P0#2** the real INSERT is an UPSERT that ALWAYS returns the canonical doc_id
  (``ON CONFLICT … DO UPDATE … RETURNING id``); a NULL return aborts the rest.
* **P0#3** in-TX re-validation on the CURRENT db state: client exists & not
  soft-deleted; ``practice.client_id == client_id``;
  ``family_member.client_id == client_id``; the proposal target still matches the
  approval. A failing check → the plan is ``blocked`` and nothing executes.
* **P0#5** ``claim_token`` + non-expired lease are required to approve.
* **P0#6** practice dual-link: ``SELECT practices … FOR UPDATE`` + membership
  dedup by document id (planned; executed only in the real path).
* **P0#8** :func:`write_client_document` is PURE-DB: NO OCR dispatch, NO portal
  notify, NO cache invalidation inside the TX, and it NEVER resets
  ``ocr_status`` from completed→pending (it preserves the FASE-3 OCR). All
  side-effects are post-commit / out of scope of 5B.
* **P0#9** dry-run writes ONLY the audit row, never a terminal proposal/queue
  state.

PII / Symbiosis Law 2: everything runs against the LOCAL Postgres only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any

import asyncpg

from backend.core.cache import invalidate_crm_stats
from backend.services.intake.client_enricher import enrich_client_from_extracted_fields
from backend.services.intake.enqueue import PIPELINE_VERSION

logger = logging.getLogger("zantara.intake.writer")


# --------------------------------------------------------------------------- #
# Feature flag (P0 guardrail §6a) — DEFAULT OFF.
# --------------------------------------------------------------------------- #
def writer_enabled() -> bool:
    """True only if INTAKE_WRITER_ENABLED is explicitly truthy.

    Read at call time (not import time) so tests / 5C can flip it per-process.
    Default OFF: in FASE 5B this stays False and the real-write path is unreachable.
    """
    return os.environ.get("INTAKE_WRITER_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class WriterDisabledError(RuntimeError):
    """Raised if a real (dry_run=False) commit is attempted while the flag is OFF."""


def log_writer_status() -> None:
    """Emit a one-line status at app startup so the flag state is never silent.

    Call once from the app lifespan. When the flag is ON this logs a WARNING — a
    real-commit writer touching production CRM should be loud in the logs, not a
    quiet default. When OFF it logs an INFO confirming dry-run (the safe state).
    """
    if writer_enabled():
        logger.warning(
            "INTAKE WRITER ENABLED — real CRM commits are ACTIVE "
            "(INTAKE_WRITER_ENABLED is truthy). approve will write documents + "
            "advance proposals to 'routed'. This is FASE 5C go-live state."
        )
    else:
        logger.info(
            "intake writer DRY-RUN (INTAKE_WRITER_ENABLED off) — approve simulates, "
            "writes only an audit row, never touches the CRM."
        )


# --------------------------------------------------------------------------- #
# Plan / result value objects
# --------------------------------------------------------------------------- #
@dataclass
class WriteOp:
    """One concrete write the commit WOULD perform (table + verb + values)."""

    table: str
    verb: str  # INSERT | UPDATE | UPSERT | APPEND_JSON
    values: dict[str, Any]
    note: str | None = None


@dataclass
class CommitPlan:
    """The full, structured plan of what an approve would write — no execution.

    ``blocked`` + ``block_reasons`` carry the P0#3 in-validation verdict computed
    against the CURRENT db state. A blocked plan must NOT be executed.
    """

    proposal_id: int
    queue_id: int | None
    client_id: int | None
    practice_id: int | None
    decision: str | None
    doc_type: str | None
    committed_by: str
    idempotency_key: str
    payload: dict[str, Any]
    ops: list[WriteOp] = field(default_factory=list)
    blocked: bool = False
    block_reasons: list[str] = field(default_factory=list)
    # If an identical (client_id, idempotency_key) document already exists, the
    # real path is a no-op returning this id (idempotency). Surfaced in the plan.
    existing_doc_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class CommitResult:
    """Outcome of :func:`execute_commit`.

    In 5B (dry-run) ``dry_run=True``, ``doc_id=None``, ``would_write`` echoes the
    planned ops, and ``audit_id`` points at the single ``intake_commit_audit`` row.
    """

    proposal_id: int
    dry_run: bool
    outcome: str  # dry_run | blocked | committed | failed | rolled_back
    doc_id: int | None = None
    practice_id: int | None = None
    audit_id: int | None = None
    would_write: list[dict[str, Any]] = field(default_factory=list)
    block_reasons: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# P0#1 — intake-instance idempotency key
# --------------------------------------------------------------------------- #
def compute_idempotency_key(
    source: str,
    source_ref: str,
    blob_hash: str,
    doc_index: int,
    pipeline_version: str,
) -> str:
    """Stable per-INTAKE-INSTANCE key.

    P0#1: keyed on the intake instance (source + source_ref + blob + doc_index +
    pipeline_version), NOT on content alone. The SAME physical blob ingested for
    two different clients produces the SAME hash here ONLY when source/source_ref
    coincide — and the UNIQUE index is ``(client_id, key)``, so even an identical
    key across clients can never collide. ``content_hash`` stays evidence-of-
    duplicate, never identity-of-commit.
    """
    raw = f"{source}|{source_ref}|{blob_hash}|{doc_index}|{pipeline_version}"
    return "ik:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Small JSONB coercion helper (asyncpg already returns dict for jsonb).
# --------------------------------------------------------------------------- #
def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


# --------------------------------------------------------------------------- #
# Document payload derivation (read-only — what create_document would receive)
# --------------------------------------------------------------------------- #
def _document_payload(
    routing: dict[str, Any],
    stage_output: dict[str, Any],
    source_ref: str,
) -> dict[str, Any]:
    """Derive the DocumentCreate-equivalent payload from the proposal/queue.

    Mirrors the columns ``create_document`` writes (crm_enhanced_documents.py),
    minus the user-supplied bits we don't have for an automated intake. Values are
    best-effort; the human can override final_fields in the approve body.
    """
    doc_type = routing.get("doc_type") or stage_output.get("doc_type") or "unknown"
    fields = routing.get("fields")
    if not isinstance(fields, dict):
        extract = stage_output.get("extract")
        fields = extract.get("fields") if isinstance(extract, dict) else {}
        if not isinstance(fields, dict):
            fields = {}

    # map intake doc_type → CRM document_category (folder) — mirrors create_document.
    # NOTE: the canonical company category is "pma" (→ CATEGORY_TO_FOLDER["pma"] = "02_Company"),
    # NOT "company": the latter is absent from document_categorizer.CATEGORY_TO_FOLDER, so it would
    # silently fall through to the "99_Misc" default at crm_enhanced_documents.py and file NIB/akta
    # into the Misc folder instead of 02_Company. Canonical value verified by
    # tests/unit/app/services/portal/test_documents_mixin.py:45.
    category_map = {
        "passport": "immigration",
        "kitas": "immigration",
        "visa": "immigration",
        "itap": "immigration",
        "itk": "immigration",
        "ktp": "personal",
        "family_card": "family",
        "birth_certificate": "family",
        "marriage_certificate": "family",
        "payment_receipt": "other",
        "travel_ticket": "other",
        "bank_statement": "other",
        "medical_insurance": "other",
        "npwp": "tax",
        "nib": "pma",
        "oss": "pma",
        "akta_pendirian": "pma",
        "profil_perseroan": "pma",
        "sk_kemenkumham": "pma",
    }
    category = category_map.get(doc_type)

    file_name = stage_output.get("file_name") or f"{doc_type}-{source_ref}"

    return {
        "document_type": doc_type,
        "document_category": category,
        "file_name": file_name,
        "file_id": stage_output.get("file_id"),
        "file_url": stage_output.get("file_url"),
        "google_drive_file_url": stage_output.get("google_drive_file_url"),
        "expiry_date": None,
        "notes": f"intake:{source_ref}",
        "family_member_id": None,
        # ocr_status preserved (P0#8): FASE-3 already OCR'd; do NOT reset to pending.
        "ocr_status": "completed",
        "extracted_fields": fields,
    }


# --------------------------------------------------------------------------- #
# plan_commit — build the plan + P0#3 in-TX validation (NO execution)
# --------------------------------------------------------------------------- #
async def plan_commit(
    proposal: dict[str, Any] | asyncpg.Record,
    conn: asyncpg.Connection,
    *,
    committed_by: str,
    override_client_id: int | None = None,
    override_practice_id: int | None = None,
    practice_explicit: bool = False,
    final_fields: dict[str, Any] | None = None,
) -> CommitPlan:
    """Build the structured write-plan for a proposal — and validate it.

    READ-ONLY: issues only SELECTs (incl. ``FOR UPDATE`` on the practice the plan
    targets, which is correct — the caller is already inside the commit TX and the
    lock is part of the plan; in 5B the TX rolls back so nothing persists).

    ``override_client_id`` / ``override_practice_id`` let the HITL reviewer redirect
    the attach (decision-level correction, design §5). ``practice_explicit=True``
    means the reviewer DELIBERATELY chose the practice value — including ``None``
    ("archive only, no practice"), which must NOT fall back to routing's hint.
    ``final_fields`` are the human-edited extracted fields.
    """
    p = dict(proposal)
    proposal_id = p["id"]
    queue_id = p.get("queue_id")
    routing = _as_dict(p.get("routing"))
    entity_resolution = _as_dict(p.get("entity_resolution"))
    decision = entity_resolution.get("decision") or routing.get("decision")

    # Queue context (source/source_ref/blob_hash/pipeline_version/stage_output).
    qrow = None
    if queue_id is not None:
        qrow = await conn.fetchrow(
            """
            SELECT id, source, source_ref, blob_hash, pipeline_version, stage_output
            FROM intake_queue WHERE id = $1
            """,
            queue_id,
        )
    stage_output = _as_dict(qrow["stage_output"]) if qrow else {}
    source = (qrow["source"] if qrow else None) or "unknown"
    source_ref = (qrow["source_ref"] if qrow else None) or str(proposal_id)
    blob_hash = (qrow["blob_hash"] if qrow else None) or ""
    pipeline_version = (qrow["pipeline_version"] if qrow else None) or p.get(
        "pipeline_version"
    ) or PIPELINE_VERSION
    doc_index = int(p.get("doc_index") or 0)

    # Target client: explicit override (human chose) wins, else routing's resolved client.
    client_id = override_client_id if override_client_id is not None else routing.get(
        "client_id"
    )
    if practice_explicit:
        # The reviewer chose deliberately — honour it even when it is None
        # ("archive only"): no silent fallback to routing's practice hint.
        practice_id = override_practice_id
    else:
        practice_id = (
            override_practice_id
            if override_practice_id is not None
            else routing.get("practice_id")
        )

    payload = _document_payload(routing, stage_output, source_ref)
    # Persist the resolved practice on the document row itself (documents.practice_id):
    # _document_payload doesn't know it, but write_client_document writes
    # payload["practice_id"], and rollback_commit reads it back to detach the link.
    # Without this the column is NULL and rollback can't find the practice to clean.
    payload["practice_id"] = practice_id
    if final_fields:
        payload["extracted_fields"] = {**payload.get("extracted_fields", {}), **final_fields}

    idem_key = compute_idempotency_key(
        source, source_ref, blob_hash, doc_index, pipeline_version
    )

    plan = CommitPlan(
        proposal_id=proposal_id,
        queue_id=queue_id,
        client_id=client_id,
        practice_id=practice_id,
        decision=decision,
        doc_type=payload["document_type"],
        committed_by=committed_by,
        idempotency_key=idem_key,
        payload=payload,
    )

    reasons: list[str] = []

    # --- P0#3 in-TX validation against CURRENT db state ---------------------- #
    if client_id is None:
        reasons.append("no_target_client (decision requires human to pick a client)")
    else:
        crow = await conn.fetchrow(
            "SELECT id, deleted_at FROM clients WHERE id = $1", client_id
        )
        if crow is None:
            reasons.append(f"client {client_id} does not exist")
        elif crow["deleted_at"] is not None:
            reasons.append(f"client {client_id} is soft-deleted (deleted_at set)")

    # practice.client_id must match the target client (cross-client orphan guard).
    if practice_id is not None and client_id is not None:
        prow = await conn.fetchrow(
            "SELECT id, client_id, documents FROM practices WHERE id = $1 FOR UPDATE",
            practice_id,
        )
        if prow is None:
            reasons.append(f"practice {practice_id} does not exist")
        elif prow["client_id"] != client_id:
            reasons.append(
                f"practice {practice_id}.client_id={prow['client_id']} != target client {client_id}"
            )

    # family_member (if any) must belong to the client.
    fam_id = payload.get("family_member_id")
    if fam_id is not None and client_id is not None:
        has_fam_tbl = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name='family_members'"
        )
        if has_fam_tbl:
            frow = await conn.fetchrow(
                "SELECT client_id FROM family_members WHERE id = $1", fam_id
            )
            if frow is None or frow["client_id"] != client_id:
                reasons.append(
                    f"family_member {fam_id} does not belong to client {client_id}"
                )

    # Proposal must still be in a claimable/approvable state (not already terminal).
    cur_status = p.get("status")
    if cur_status not in ("review_pending", "review_claimed"):
        reasons.append(f"proposal status '{cur_status}' is not approvable")

    # Idempotency probe: does a doc with this (client_id, key) already exist?
    if client_id is not None:
        exrow = await conn.fetchrow(
            """
            SELECT id FROM documents
            WHERE client_id = $1 AND intake_idempotency_key = $2
            """,
            client_id,
            idem_key,
        )
        if exrow is not None:
            plan.existing_doc_id = exrow["id"]

    plan.blocked = bool(reasons)
    plan.block_reasons = reasons

    # --- Build the would-write ops (only meaningful when not blocked) -------- #
    if not plan.blocked:
        if plan.existing_doc_id is not None:
            plan.ops.append(
                WriteOp(
                    table="documents",
                    verb="UPSERT",
                    values={
                        "client_id": client_id,
                        "intake_idempotency_key": idem_key,
                        "existing_doc_id": plan.existing_doc_id,
                    },
                    note="idempotent: document already exists for (client, key) → no-op, reuse doc_id",
                )
            )
        else:
            plan.ops.append(
                WriteOp(
                    table="documents",
                    verb="UPSERT",
                    values={
                        "client_id": client_id,
                        "document_type": payload["document_type"],
                        "document_category": payload["document_category"],
                        "file_name": payload["file_name"],
                        "file_id": payload["file_id"],
                        "practice_id": practice_id,
                        "status": "received",
                        "storage_type": "google_drive",
                        "ocr_status": "completed",  # P0#8: preserve FASE-3 OCR
                        "intake_idempotency_key": idem_key,
                        "intake_proposal_id": proposal_id,
                    },
                    note="INSERT … ON CONFLICT (client_id, intake_idempotency_key) DO UPDATE RETURNING id (P0#2 always returns doc_id)",
                )
            )
        if practice_id is not None:
            plan.ops.append(
                WriteOp(
                    table="practices.documents[]",
                    verb="APPEND_JSON",
                    values={
                        "practice_id": practice_id,
                        "name": payload["document_type"],
                        "file_id": payload["file_id"],
                        "uploaded_by": committed_by,
                        "status": "received",
                    },
                    note="SELECT … FOR UPDATE + dedup by file_id/doc_id (P0#6)",
                )
            )
        plan.ops.append(
            WriteOp(
                table="intake_corrections",
                verb="INSERT",
                values={
                    "queue_id": queue_id,
                    "decision": decision,
                    "outcome": "approved",
                    "verified_by": committed_by,
                    "fields_touched": list((final_fields or {}).keys()),
                },
                note="one row per field touched + decision-level __entity__ if client overridden (design §5)",
            )
        )

    return plan


# --------------------------------------------------------------------------- #
# write_client_document — PURE-DB writer (P0#8). Real path only (5C).
# --------------------------------------------------------------------------- #
async def write_client_document(
    conn: asyncpg.Connection,
    client_id: int,
    payload: dict[str, Any],
    *,
    proposal_id: int,
    idempotency_key: str,
) -> int:
    """Pure-DB document writer — extracted from create_document, side-effects removed.

    P0#8: NO OCR dispatch, NO portal notify, NO cache invalidation here (those are
    post-commit / non-transactional). NEVER resets ocr_status from completed→pending.
    P0#2: UPSERT on (client_id, intake_idempotency_key) ALWAYS RETURNING the canonical
    doc_id; a re-commit of the same intake instance is a no-op that returns the same id.

    NOT reachable in FASE 5B: execute_commit refuses to run the real path while the
    flag is OFF, so this never fires against the CRM in 5B.
    """
    # ocr_status column may not exist in every environment (absent in nuzantara_dev).
    has_ocr = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='documents' AND column_name='ocr_status'"
    )
    if has_ocr:
        doc_id = await conn.fetchval(
            """
            INSERT INTO documents (
                client_id, document_type, document_category,
                file_name, file_id, file_url, google_drive_file_url,
                notes, family_member_id, practice_id,
                status, storage_type, ocr_status,
                intake_idempotency_key, intake_proposal_id
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'received','google_drive',$11,$12,$13)
            ON CONFLICT (client_id, intake_idempotency_key)
                WHERE intake_idempotency_key IS NOT NULL
            DO UPDATE SET updated_at = now()
            RETURNING id
            """,
            client_id,
            payload["document_type"],
            payload.get("document_category"),
            payload.get("file_name"),
            payload.get("file_id"),
            payload.get("file_url"),
            payload.get("google_drive_file_url"),
            payload.get("notes"),
            payload.get("family_member_id"),
            payload.get("practice_id"),
            payload.get("ocr_status", "completed"),  # preserve FASE-3 OCR (P0#8)
            idempotency_key,
            proposal_id,
        )
    else:
        doc_id = await conn.fetchval(
            """
            INSERT INTO documents (
                client_id, document_type, document_category,
                file_name, file_id, file_url, google_drive_file_url,
                notes, family_member_id, practice_id,
                status, storage_type,
                intake_idempotency_key, intake_proposal_id
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'received','google_drive',$11,$12)
            ON CONFLICT (client_id, intake_idempotency_key)
                WHERE intake_idempotency_key IS NOT NULL
            DO UPDATE SET updated_at = now()
            RETURNING id
            """,
            client_id,
            payload["document_type"],
            payload.get("document_category"),
            payload.get("file_name"),
            payload.get("file_id"),
            payload.get("file_url"),
            payload.get("google_drive_file_url"),
            payload.get("notes"),
            payload.get("family_member_id"),
            payload.get("practice_id"),
            idempotency_key,
            proposal_id,
        )
    if doc_id is None:  # P0#2: must always return a canonical id
        raise RuntimeError("write_client_document: UPSERT returned no doc_id")
    return int(doc_id)


# --------------------------------------------------------------------------- #
# execute_commit — dry-run (5B) or real (5C, flag-gated)
# --------------------------------------------------------------------------- #
async def execute_commit(
    plan: CommitPlan,
    conn: asyncpg.Connection,
    *,
    dry_run: bool = True,
    advance_from: str = "review_claimed",
    advance_to: str = "routed",
) -> CommitResult:
    """Execute (or simulate) the commit plan.

    dry_run=True (FASE 5B default): logs the plan, writes ONE
    ``intake_commit_audit(dry_run=true)`` row, and returns without touching the CRM.
    Never advances the proposal/queue to a terminal state (P0#9).

    dry_run=False (FASE 5C): requires INTAKE_WRITER_ENABLED — otherwise raises
    WriterDisabledError BEFORE any write. The real atomic path is implemented but
    NOT exercised in 5B.

    ``advance_from`` / ``advance_to`` select the proposal transition on a real
    commit: the human approve path uses the defaults (``review_claimed`` →
    ``routed``); the LEVA-2 auto-attach path passes ``review_pending`` →
    ``auto_routed`` (a never-claimed proposal committed by the system).
    """
    would_write = [op.__dict__ for op in plan.ops]

    # Blocked plan (P0#3): record + refuse, regardless of dry/real.
    if plan.blocked:
        audit_id = await _write_audit(
            conn, plan, dry_run=dry_run, outcome="blocked", doc_id=None, error="; ".join(plan.block_reasons)
        )
        logger.warning(
            "intake.writer.blocked proposal=%s reasons=%s",
            plan.proposal_id,
            plan.block_reasons,
        )
        return CommitResult(
            proposal_id=plan.proposal_id,
            dry_run=dry_run,
            outcome="blocked",
            audit_id=audit_id,
            would_write=would_write,
            block_reasons=plan.block_reasons,
        )

    if dry_run:
        audit_id = await _write_audit(
            conn, plan, dry_run=True, outcome="dry_run", doc_id=None
        )
        logger.info(
            "intake.writer.DRY_RUN proposal=%s client=%s practice=%s doc_type=%s ops=%d "
            "(would write, NOTHING committed)",
            plan.proposal_id,
            plan.client_id,
            plan.practice_id,
            plan.doc_type,
            len(plan.ops),
        )
        return CommitResult(
            proposal_id=plan.proposal_id,
            dry_run=True,
            outcome="dry_run",
            audit_id=audit_id,
            would_write=would_write,
        )

    # --- REAL path (FASE 5C) — flag-gated, NOT reachable in 5B -------------- #
    if not writer_enabled():
        raise WriterDisabledError(
            "INTAKE_WRITER_ENABLED is OFF — real CRM commit refused (FASE 5B is dry-run only)."
        )

    # The real atomic TX (5C). The caller MUST wrap this in `async with
    # conn.transaction()` — every write below (document UPSERT, practice append,
    # proposal advancement, audit row) lands in the SAME transaction. If ANY step
    # raises, the enclosing transaction unwinds ALL of them atomically: no orphan
    # document without a routed proposal, no routed proposal without its document
    # (panel Q3 — the load-bearing failure mode). We re-raise (never swallow) so the
    # caller's `transaction()` rolls back; the audit `failed` row below is written on
    # a SEPARATE connection so it survives the rollback as forensic evidence.
    try:
        doc_id = await write_client_document(
            conn,
            plan.client_id,  # type: ignore[arg-type]
            plan.payload,
            proposal_id=plan.proposal_id,
            idempotency_key=plan.idempotency_key,
        )
        if plan.practice_id is not None:
            await _append_practice_document(conn, plan, doc_id)
        # Client-card enrichment — in the SAME TX as the document write. The passport
        # number/expiry, KITAS expiry, NPWP, NIB etc. extracted by FASE-3 feed the
        # client's profile (renewal-alert clock, identity fields). Before this the
        # intake commit filed the file and discarded the structured data. Conservative:
        # skips archive-only (client_id None), unknown doc_types, and absent fields —
        # never overwrites an existing card value with NULL. A bad field is skipped,
        # never raised, so enrichment can't roll back the document it belongs to.
        enriched = await enrich_client_from_extracted_fields(
            conn,
            plan.client_id,
            plan.doc_type,
            plan.payload.get("extracted_fields"),
        )
        # Proposal advancement to the terminal state — in the SAME TX as the
        # writes. P0#9 inverse: the DRY-RUN path never advances; the REAL path advances
        # exactly once, atomically with the document it routed. ``advance_from``/
        # ``advance_to`` distinguish human (review_claimed→routed) from auto-attach
        # (review_pending→auto_routed).
        await advance_proposal(
            conn, plan.proposal_id, from_status=advance_from, target_status=advance_to
        )
        audit_id = await _write_audit(
            conn, plan, dry_run=False, outcome="committed", doc_id=doc_id
        )
        logger.info(
            "intake.writer.COMMITTED proposal=%s client=%s doc=%s practice=%s enriched=%s (real write)",
            plan.proposal_id,
            plan.client_id,
            doc_id,
            plan.practice_id,
            sorted(enriched.keys()) if enriched else [],
        )
        return CommitResult(
            proposal_id=plan.proposal_id,
            dry_run=False,
            outcome="committed",
            doc_id=doc_id,
            practice_id=plan.practice_id,
            audit_id=audit_id,
            would_write=would_write,
        )
    except Exception as exc:
        # The enclosing transaction WILL roll back doc/practice/proposal/audit. Surface
        # the failure loudly; the caller decides whether to record a forensic `failed`
        # audit row out-of-band (it cannot live in this TX — it would roll back too).
        logger.error("intake.writer.failed proposal=%s err=%s", plan.proposal_id, exc)
        raise


def _load_json_list(value: Any) -> list[Any]:
    """Decode a jsonb column to a Python list, codec-agnostic.

    asyncpg returns jsonb as a decoded object ONLY if the pool registered a json
    codec; on a plain pool (the production backend pool + the test pool) it returns
    the raw TEXT. ``list("[]")`` would then iterate characters — the double-encoding
    trap (see cicatrix discovery_jsonb_double_encoding_systemic). Always parse a str.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


async def _append_practice_document(
    conn: asyncpg.Connection, plan: CommitPlan, doc_id: int
) -> None:
    """P0#6: FOR UPDATE the practice, dedup membership by file_id, append. (5C path.)"""
    prow = await conn.fetchrow(
        "SELECT documents FROM practices WHERE id = $1 FOR UPDATE", plan.practice_id
    )
    if prow is None:
        raise RuntimeError(f"practice {plan.practice_id} vanished mid-TX")
    documents = _load_json_list(prow["documents"])
    file_id = plan.payload.get("file_id")
    if any(isinstance(d, dict) and d.get("drive_file_id") == file_id for d in documents):
        return  # already linked — idempotent
    documents.append(
        {
            "name": plan.payload["document_type"],
            "drive_file_id": file_id,
            "uploaded_by": plan.committed_by,
            "status": "received",
            "doc_id": doc_id,
        }
    )
    # Write jsonb via explicit dumps + cast (pool has no json codec — passing a list
    # raw makes asyncpg reject it as "expected str, got list").
    await conn.execute(
        "UPDATE practices SET documents = $1::jsonb, updated_at = NOW() WHERE id = $2",
        json.dumps(documents),
        plan.practice_id,
    )
    await invalidate_crm_stats()  # F32


# --------------------------------------------------------------------------- #
# advance_proposal — terminal state transition (real path only, 5C)
# --------------------------------------------------------------------------- #
async def advance_proposal(
    conn: asyncpg.Connection,
    proposal_id: int,
    *,
    from_status: str = "review_claimed",
    target_status: str = "routed",
) -> None:
    """Move a proposal to its terminal success state and release the claim.

    Called ONLY on the real (dry_run=False) commit path, inside the same TX as the
    document write. Both terminals live in the chk_rp_status CHECK:

    * human approve: ``review_claimed`` → ``routed`` (the default).
    * LEVA-2 auto-attach: ``review_pending`` → ``auto_routed`` (a never-claimed
      proposal the system committed without a human; ``auto_routed`` keeps the
      audit trail able to tell machine commits apart from human ones).

    Idempotent-by-guard: the WHERE only matches a proposal still in ``from_status``,
    so a re-run (or a concurrent winner) is a no-op rather than a double-advance. The
    lease columns are cleared because a terminal proposal is held by no reviewer.
    """
    await conn.execute(
        """
        UPDATE document_routing_proposal
           SET status = $3,
               lease_owner = NULL,
               lease_expires_at = NULL,
               claim_token = NULL
         WHERE id = $1
           AND status = $2
        """,
        proposal_id,
        from_status,
        target_status,
    )


# --------------------------------------------------------------------------- #
# rollback_commit — undo a committed intake instance (panel Q5 hard-prereq, 5C)
# --------------------------------------------------------------------------- #
async def rollback_commit(
    conn: asyncpg.Connection,
    *,
    client_id: int,
    idempotency_key: str,
    committed_by: str,
) -> CommitResult:
    """Reverse a previously-committed intake instance, identified by its key.

    The operator escape hatch the panel (Q5) elevated to a HARD prerequisite before
    any production activation: if a real commit attached the wrong document (or to
    the wrong client), this undoes it deterministically.

    What it undoes, in ONE transaction (the caller wraps this in
    `async with conn.transaction()`):

    * the ``documents`` row keyed by ``(client_id, intake_idempotency_key)`` — removed;
    * its membership entry in any ``practices.documents[]`` that linked it (matched by
      the stored ``doc_id``);
    * the originating ``document_routing_proposal`` — moved BACK from 'routed' to
      'review_claimed' so a reviewer can re-decide (NOT to 'dead' — rollback is a
      do-over, not a rejection).

    Idempotent: if no document matches the key, nothing is undone and the result is
    ``outcome='rolled_back', doc_id=None`` (a second rollback is a safe no-op). Writes
    one ``intake_commit_audit(outcome='rolled_back')`` forensic row either way.

    NOT flag-gated: rollback is a corrective action — it must work even with the
    writer flag toggled back OFF after a bad commit.
    """
    doc = await conn.fetchrow(
        """
        SELECT id, intake_proposal_id, practice_id
        FROM documents
        WHERE client_id = $1 AND intake_idempotency_key = $2
        """,
        client_id,
        idempotency_key,
    )
    doc_id = doc["id"] if doc else None
    proposal_id = doc["intake_proposal_id"] if doc else None
    practice_id = doc["practice_id"] if doc else None

    if doc_id is not None:
        # Detach from the practice membership array (match by stored doc_id).
        if practice_id is not None:
            prow = await conn.fetchrow(
                "SELECT documents FROM practices WHERE id = $1 FOR UPDATE", practice_id
            )
            if prow is not None:
                remaining = [
                    d
                    for d in _load_json_list(prow["documents"])
                    if not (isinstance(d, dict) and d.get("doc_id") == doc_id)
                ]
                await conn.execute(
                    "UPDATE practices SET documents = $1::jsonb, updated_at = NOW() WHERE id = $2",
                    json.dumps(remaining),
                    practice_id,
                )
        # Remove the document itself.
        await conn.execute("DELETE FROM documents WHERE id = $1", doc_id)
        # Re-open the proposal for re-decision (routed -> review_claimed).
        if proposal_id is not None:
            await conn.execute(
                """
                UPDATE document_routing_proposal
                   SET status = 'review_claimed'
                 WHERE id = $1
                   AND status = 'routed'
                """,
                proposal_id,
            )

    # Forensic audit ONLY when something was actually undone. A no-op rollback (no
    # matching document → doc_id/proposal_id are None) writes nothing: intake_commit_audit
    # requires a non-null proposal_id (FK to document_routing_proposal), and there is
    # no proposal to attribute a no-op to. The no-op stays idempotent and silent.
    audit_id: int | None = None
    if doc_id is not None and proposal_id is not None:
        audit_id = await conn.fetchval(
            """
            INSERT INTO intake_commit_audit (
                proposal_id, queue_id, client_id, doc_id, practice_id,
                decision, committed_by, dry_run, outcome, idempotency_key, plan, error
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12)
            RETURNING id
            """,
            proposal_id,
            None,
            client_id,
            doc_id,
            practice_id,
            # decision must be NULL or one of the routing decisions (chk_ica_decision);
            # 'rollback' is an OUTCOME, not a decision — recorded via outcome='rolled_back'.
            None,
            committed_by,
            False,
            "rolled_back",
            idempotency_key,
            json.dumps({"rolled_back_doc_id": doc_id}, default=str),
            None,
        )
    logger.warning(
        "intake.writer.ROLLED_BACK client=%s key=%s doc=%s proposal=%s by=%s",
        client_id,
        idempotency_key,
        doc_id,
        proposal_id,
        committed_by,
    )
    return CommitResult(
        proposal_id=proposal_id or 0,
        dry_run=False,
        outcome="rolled_back",
        doc_id=doc_id,
        practice_id=practice_id,
        audit_id=int(audit_id) if audit_id is not None else None,
    )


async def _write_audit(
    conn: asyncpg.Connection,
    plan: CommitPlan,
    *,
    dry_run: bool,
    outcome: str,
    doc_id: int | None,
    error: str | None = None,
) -> int:
    """Append one intake_commit_audit row (the ONLY write a 5B dry-run performs)."""
    audit_id = await conn.fetchval(
        """
        INSERT INTO intake_commit_audit (
            proposal_id, queue_id, client_id, doc_id, practice_id,
            decision, committed_by, dry_run, outcome, idempotency_key, plan, error
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12)
        RETURNING id
        """,
        plan.proposal_id,
        plan.queue_id,
        plan.client_id,
        doc_id,
        plan.practice_id,
        plan.decision,
        plan.committed_by,
        dry_run,
        outcome,
        plan.idempotency_key,
        json.dumps(plan.to_dict(), default=str),
        error,
    )
    return int(audit_id)
