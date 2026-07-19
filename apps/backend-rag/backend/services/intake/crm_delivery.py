"""Post-commit delivery of intake documents to the canonical Kita CRM path."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import asyncpg

from backend.services.intake import crm_push
from backend.services.intake import writer as intake_writer

logger = logging.getLogger("zantara.intake.crm_delivery")


def crm_write_key_from_env() -> str | None:
    """Return the scoped service-write key for headless intake delivery, if set."""
    for name in ("INTAKE_CRM_PUSH_WRITE_KEY", "WA_MIRROR_CRM_WRITE_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


async def deliver_committed_to_crm(
    *,
    pool: asyncpg.Pool,
    queue_id: int | None,
    plan: intake_writer.CommitPlan,
    result: intake_writer.CommitResult,
    bearer_token: str | None = None,
    crm_write_key: str | None = None,
) -> dict[str, Any]:
    """Best-effort delivery of a COMMITTED local intake document to Kita.

    Runs AFTER the local commit transaction succeeded. The local Pro commit stays
    final; this service only pushes the original blob to Fly/Drive and annotates
    local bookkeeping with the delivery result. It never raises for delivery
    failures.
    """
    if not crm_push.push_enabled():
        return {"status": "disabled"}

    if not bearer_token and crm_write_key is None:
        crm_write_key = crm_write_key_from_env()

    blob_path: str | None = None
    mime_type: str | None = None
    resolution_phone: str | None = None
    client_full_name: str | None = None
    already: asyncpg.Record | None = None
    async with pool.acquire() as conn:
        if queue_id is not None:
            qrow = await conn.fetchrow(
                """
                SELECT q.blob_path, di.mime_type
                FROM intake_queue q
                LEFT JOIN document_instances di ON di.id = q.instance_id
                WHERE q.id = $1
                """,
                queue_id,
            )
            if qrow is not None:
                blob_path = qrow["blob_path"]
                mime_type = qrow["mime_type"]
        # Identity resolution is keyed on the SELECTED client's own canonical
        # phone — NEVER the transport sender phone (Codex 2026-07-19 round 6,
        # F5): a forwarder A can send B's document; after the reviewer assigns
        # it to B, resolving Fly by A's phone would deliver B's PII to A. The
        # committed plan.client_id is the reviewed identity ground truth; if
        # that client has no phone on the local card, delivery fails CLOSED
        # (identity_unresolved) rather than guessing. The name is used ONLY to
        # label a fresh Fly lead (placeholder "Lead +<phone>" names skipped).
        if plan.client_id is not None:
            crow = await conn.fetchrow(
                "SELECT full_name, phone_normalized FROM clients WHERE id = $1",
                int(plan.client_id),
            )
            if crow is not None:
                _name = (crow["full_name"] or "").strip()
                if _name and not _name.lower().startswith("lead "):
                    client_full_name = _name
                _phone = (crow["phone_normalized"] or "").strip()
                if _phone:
                    resolution_phone = _phone
        if result.doc_id is not None:
            already = await conn.fetchrow(
                "SELECT file_id, file_url FROM documents WHERE id = $1", result.doc_id
            )

    payload = plan.payload
    if already is not None and (already["file_id"] or already["file_url"]):
        push = crm_push.CrmPushResult(
            ok=False,
            status="already_delivered",
            file_id=already["file_id"],
            file_url=already["file_url"],
            detail="local documents row already has a Drive file - skipping re-upload",
        )
    elif not blob_path:
        push = crm_push.CrmPushResult(
            ok=False, status="missing_blob", detail="no blob_path on intake_queue row"
        )
    else:
        push = await crm_push.push_committed_document(
            bearer_token=bearer_token,
            crm_write_key=crm_write_key,
            client_id=int(plan.client_id),  # type: ignore[arg-type]  # committed means non-None
            practice_id=plan.practice_id,
            document_type=payload.get("document_type") or "unknown",
            document_category=payload.get("document_category"),
            file_name=payload.get("file_name") or os.path.basename(blob_path),
            blob_path=blob_path,
            mime_type=mime_type,
            expiry_date=payload.get("expiry_date"),
            notes=payload.get("notes"),
            sender_phone=resolution_phone,
            client_full_name=client_full_name,
        )

    crm_info: dict[str, Any] = {
        "status": push.status,
        "fly_doc_id": push.fly_doc_id,
        "file_url": push.file_url,
    }
    if push.detail:
        crm_info["detail"] = push.detail

    if push.status == "identity_unresolved":
        # Distinct, greppable marker (round-5 F8): the document IS committed
        # locally but could not be delivered to Kita because no unambiguous
        # Fly identity exists (no phone / shared phone / no service key).
        # There is deliberately NO auto-requeue: a retry cannot succeed until
        # the identity mapping itself changes — these rows are found via this
        # marker + the persisted delivery status, not by blind redelivery.
        logger.warning(
            "intake.delivery.identity_unresolved queue=%s doc=%s client=%s detail=%s",
            queue_id,
            result.doc_id,
            plan.client_id,
            push.detail,
        )

    try:
        async with pool.acquire() as conn:
            if push.ok and result.doc_id is not None:
                await conn.execute(
                    """
                    UPDATE documents
                       SET file_id = COALESCE($2, file_id),
                           file_url = COALESCE($3, file_url),
                           google_drive_file_url = COALESCE($3, google_drive_file_url),
                           storage_type = 'google_drive',
                           updated_at = NOW()
                     WHERE id = $1
                    """,
                    result.doc_id,
                    push.file_id,
                    push.file_url,
                )
            if result.audit_id is not None:
                await conn.execute(
                    """
                    UPDATE intake_commit_audit
                       SET plan = COALESCE(plan, '{}'::jsonb) || $2::jsonb
                     WHERE id = $1
                    """,
                    result.audit_id,
                    json.dumps({"crm_push": crm_info}),
                )
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as exc:
        logger.error(
            "intake.crm_delivery.bookkeeping_failed proposal=%s err=%s",
            plan.proposal_id,
            exc,
        )

    if not push.ok and push.status not in ("disabled", "already_delivered"):
        logger.warning(
            "intake.crm_delivery.failed proposal=%s doc=%s status=%s detail=%s",
            plan.proposal_id,
            result.doc_id,
            push.status,
            push.detail,
        )
    return crm_info
