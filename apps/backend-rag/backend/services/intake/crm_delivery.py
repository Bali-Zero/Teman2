"""Post-commit delivery of intake documents to the canonical Kita CRM path."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import asyncpg

# The canonical projection is SHARED with the CRM dedup and every phone writer
# (backend.db.phone_lock) — "the same phone" has exactly one definition, so the
# round-9 F13 parity requirement holds by construction, not by mirroring.
from backend.db.phone_lock import phone_core as _phone_core
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


def _raw_phone_state(raw: object) -> tuple[str, str | None]:
    """Classify the raw ``phone`` column for the consistency gate.

    Returns ``('absent', None)`` when the value is empty or contains no digits
    at all (free-text garbage is not a phone CLAIM); ``('usable', core)`` when
    it yields a valid core; ``('unusable', None)`` when digits are present but
    below the core threshold — a present-but-garbage phone claim that CANNOT
    cross-check the normalized value, so resolution must fail closed rather
    than trust a possibly-stale phone_normalized (Codex round 10, F11 gap 1
    residual: a raw ``"12345"`` must not be treated as raw-absent).
    """
    s = ("" if raw is None else str(raw)).strip()
    if not s:
        return ("absent", None)
    if not re.search(r"[0-9]", s):
        return ("absent", None)
    core = _phone_core(s)
    if core is None:
        return ("unusable", None)
    return ("usable", core)


# Sole-owner gate over BOTH phone columns (Codex round-8, F11 gaps): historical
# rows carry stale/missing phone_normalized (the CRM dedup code coalesces raw
# `phone` for the same reason), and ARCHIVED rows count too — the Fly resolver
# searches archived rows and can restore one, so a soft-deleted local duplicate
# is still a reachable wrong-attach vector. Comparison is on the CORE (trunk/
# country prefix stripped, mirroring ``_phone_core``): ``0812…`` and ``62812…``
# are the same owner (round-9 F13). $2 is the selected client's core.
_PHONE_DUP_OWNERS_SQL = """
SELECT COUNT(*) FROM (
  SELECT regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g') AS dn,
         regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') AS dr
    FROM clients
   WHERE id <> $1
) t
 WHERE CASE WHEN t.dn LIKE '62%' THEN substr(t.dn, 3)
            WHEN t.dn LIKE '0%'  THEN substr(t.dn, 2)
            ELSE t.dn END = $2
    OR CASE WHEN t.dr LIKE '62%' THEN substr(t.dr, 3)
            WHEN t.dr LIKE '0%'  THEN substr(t.dr, 2)
            ELSE t.dr END = $2
"""


async def _resolve_and_push_locked(
    *,
    pool: asyncpg.Pool,
    plan: intake_writer.CommitPlan,
    payload: dict[str, Any],
    queue_id: int | None,
    blob_path: str,
    mime_type: str | None,
    bearer_token: str | None,
    crm_write_key: str | None,
) -> crm_push.CrmPushResult:
    """Resolve the Fly identity and upload while holding the LOCAL phone lock.

    Identity resolution is keyed on the SELECTED client's own canonical phone —
    NEVER the transport sender phone (Codex round 6, F5): a forwarder A can send
    B's document; after the reviewer assigns it to B, resolving Fly by A's phone
    would deliver B's PII to A. The committed ``plan.client_id`` is the reviewed
    identity ground truth; if that client has no phone on the local card,
    delivery fails CLOSED (identity_unresolved) rather than guessing. The name
    is used ONLY to label a fresh Fly lead (placeholder "Lead +" names skipped).

    The whole resolve→push sequence runs inside ONE local transaction holding
    ``pg_advisory_xact_lock(hashtext(<digits>))`` — the SAME key the
    upsert-by-phone endpoint takes — so lock-respecting local phone writers are
    serialized against the cross-DB resolution window (Codex round 8, F12).
    Writers that bypass the lock (direct UPDATEs) are caught best-effort by the
    post-upload divergence re-check, which flags the delivery for HITL review.

    The sole-owner gate (round 7 F11, widened round 8): the selected client
    must be the ONLY row — live or archived — owning the digits across BOTH
    ``phone_normalized`` and raw ``phone``. Any other owner → no resolution
    phone → delivery fails CLOSED. Digits-canonical comparison is stricter
    than Fly's exact-string match on purpose: formatting variants of the same
    number also fail closed. (Duplicate-phone groups are a real population:
    migration 246 recorded 622 at authoring; 41 in the post-dedup dev book,
    probed 2026-07-19; the schema deliberately has no uniqueness constraint.)
    """
    resolution_phone: str | None = None
    client_full_name: str | None = None
    phone_digits: str | None = None
    phone_core: str | None = None
    async with pool.acquire() as conn:
        async with conn.transaction():
            if plan.client_id is not None:
                crow = await conn.fetchrow(
                    "SELECT full_name, phone_normalized, phone FROM clients WHERE id = $1",
                    int(plan.client_id),
                )
                if crow is not None:
                    _name = (crow["full_name"] or "").strip()
                    if _name and not _name.lower().startswith("lead "):
                        client_full_name = _name
                    digits = re.sub(r"[^0-9]", "", crow["phone_normalized"] or "")
                    core_norm = _phone_core(crow["phone_normalized"])
                    raw_state, core_raw = _raw_phone_state(crow["phone"])
                    # Round-9/10 F11 gap 1: the selected client's OWN card must
                    # be internally consistent — a stale non-null
                    # phone_normalized diverging from raw `phone` means neither
                    # value can prove the identity. Fail CLOSED on divergence,
                    # on an unusable normalized value with a raw present, AND on
                    # a present-but-unusable raw (short/garbage digits cannot
                    # cross-check the normalized value — round-10 residual).
                    reason: str | None = None
                    if core_norm is None or not digits:
                        if raw_state != "absent":
                            reason = "unusable_normalized_phone"
                        # else: plain no-phone card → silent fail-closed (as before)
                    elif raw_state == "unusable":
                        reason = "unusable_raw_phone"
                    elif core_raw is not None and core_raw != core_norm:
                        reason = "phone_columns_diverged"
                    if reason is not None:
                        logger.warning(
                            "intake.delivery.local_phone_ambiguous queue=%s client=%s "
                            "reason=%s",
                            queue_id,
                            plan.client_id,
                            reason,
                        )
                    elif core_norm is not None and digits:
                        # Two lock keys, lexicographic order (digits key sorts
                        # before 'phonecore:…' — deadlock-safe total order shared
                        # by every participant): the exact-digits key converges
                        # with upsert-by-phone's legacy lock; the canonical
                        # 'phonecore:' key converges with prefix-variant writers
                        # (PATCH phone updates, 0812… payloads) — round-9 F12/F13.
                        for _key in sorted([digits, f"phonecore:{core_norm}"]):
                            await conn.execute(
                                "SELECT pg_advisory_xact_lock(hashtext($1))", _key
                            )
                        # Re-read BOTH columns under the lock: pre-lock reads may
                        # be stale.
                        fresh = await conn.fetchrow(
                            "SELECT phone_normalized, phone FROM clients WHERE id = $1",
                            int(plan.client_id),
                        )
                        _f_state, _f_core = (
                            _raw_phone_state(fresh["phone"])
                            if fresh is not None
                            else ("absent", None)
                        )
                        stable = (
                            fresh is not None
                            and re.sub(r"[^0-9]", "", fresh["phone_normalized"] or "")
                            == digits
                            and _f_state != "unusable"
                            and _f_core in (None, core_norm)
                        )
                        dup_owners = 0
                        if stable:
                            dup_owners = await conn.fetchval(
                                _PHONE_DUP_OWNERS_SQL, int(plan.client_id), core_norm
                            )
                        if stable and not dup_owners:
                            resolution_phone = digits
                            phone_digits = digits
                            phone_core = core_norm
                        else:
                            logger.warning(
                                "intake.delivery.local_phone_ambiguous queue=%s client=%s "
                                "shared_with=%s stable=%s",
                                queue_id,
                                plan.client_id,
                                dup_owners,
                                stable,
                            )
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
            if phone_digits is not None and phone_core is not None:
                # Divergence detection for lock-BYPASSING writers: if ownership
                # changed between the gate and the upload, the upload may have
                # landed on a resolution that no longer holds — it cannot be
                # unwound here, so flag loudly for HITL review (ids only).
                fresh = await conn.fetchrow(
                    "SELECT phone_normalized, phone FROM clients WHERE id = $1",
                    int(plan.client_id),
                )
                dup_after = await conn.fetchval(
                    _PHONE_DUP_OWNERS_SQL, int(plan.client_id), phone_core
                )
                _p_state, _p_core = (
                    _raw_phone_state(fresh["phone"]) if fresh is not None else ("absent", None)
                )
                changed = (
                    fresh is None
                    or re.sub(r"[^0-9]", "", fresh["phone_normalized"] or "") != phone_digits
                    or _p_state == "unusable"
                    or _p_core not in (None, phone_core)
                )
                if changed or dup_after:
                    logger.error(
                        "intake.delivery.phone_owner_diverged_post_upload queue=%s "
                        "client=%s push_status=%s — review this delivery",
                        queue_id,
                        plan.client_id,
                        push.status,
                    )
    return push


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
        push = await _resolve_and_push_locked(
            pool=pool,
            plan=plan,
            payload=payload,
            queue_id=queue_id,
            blob_path=blob_path,
            mime_type=mime_type,
            bearer_token=bearer_token,
            crm_write_key=crm_write_key,
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
