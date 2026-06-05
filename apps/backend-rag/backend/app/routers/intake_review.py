"""
FASE 5A — Document-intake HITL review-queue API (READ-ONLY + claim/release).

This router exposes the human-in-the-loop review surface over the
`document_routing_proposal` rows produced by FASE 4 (status='review_pending').
It is the SAFE half of FASE 5:

  * list / detail               → pure READ of intake tables (+ candidate clients).
  * claim / release             → the ONLY writes, and ONLY on
                                  document_routing_proposal (lease columns).
  * approve / reject / commit   → NOT implemented here. Those write the CRM and
                                  live behind FASE 5C feature-flags → 501.

INVARIANTS (06-fase5-hitl-writer-design + CLAUDE.md):
  * ZERO CRM write. Reads clients/practices ONLY to show candidates. Writes ONLY
    document_routing_proposal (claim/release).
  * RBAC (§6e, P0#4): admins (zero@/asya@/antonellosiano@) see everything; a team
    member sees ONLY proposals whose resolved candidate client is assigned to them.
    Proposals with no resolved client (NO_MATCH / AMBIGUOUS) → admin-only.
  * claim_token (P0#5): claim mints an opaque token; FASE 5C mutations must present
    it. release verifies it to avoid a stale reviewer stealing another's claim.
  * Atomic claim: UPDATE ... WHERE status='review_pending' RETURNING. Concurrent
    second claim → 409.

PII: this data lives ONLY on the local Pro Postgres (Law 2 / UU-PDP).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.intake import writer as intake_writer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake/review", tags=["intake-review"])

# How long a single reviewer holds a proposal before it becomes reclaimable.
CLAIM_TTL_MINUTES = 15

# FASE 5C writer endpoints are not active yet — surfaced as explicit 501.
_WRITER_DISABLED_DETAIL = (
    "FASE 5C — writer non ancora attivo. approve/reject/commit scrivono il CRM "
    "e sono dietro feature-flag (INTAKE_WRITER_ENABLED). Non implementato in 5A."
)


# --------------------------------------------------------------------------- #
# Candidate-client extraction (read-only helper)
# --------------------------------------------------------------------------- #
def _candidate_client_ids(entity_resolution: dict[str, Any]) -> list[int]:
    """Best-effort extraction of candidate client ids from the FASE-4 blob.

    FASE 4's entity_resolution shape is still settling; be tolerant. Recognised
    shapes:
      {"candidates": [{"client_id": 412, ...}, ...]}
      {"client_id": 412}
      {"resolved_client_id": 412}
    Returns a de-duplicated list of ints (empty if nothing resolvable).
    """
    ids: list[int] = []
    if not isinstance(entity_resolution, dict):
        return ids

    for key in ("resolved_client_id", "client_id"):
        val = entity_resolution.get(key)
        if isinstance(val, int):
            ids.append(val)

    candidates = entity_resolution.get("candidates")
    if isinstance(candidates, list):
        for cand in candidates:
            if isinstance(cand, dict) and isinstance(cand.get("client_id"), int):
                ids.append(cand["client_id"])

    # de-dup preserving order
    seen: set[int] = set()
    out: list[int] = []
    for cid in ids:
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def _extracted_fields(stage_output: dict[str, Any], routing: dict[str, Any]) -> dict[str, Any]:
    """Pull the human-reviewable extracted fields.

    Preferred source is routing.fields (FASE 4). Fall back to
    stage_output.extract.fields / stage_output.route.fields when present.
    """
    if isinstance(routing, dict) and isinstance(routing.get("fields"), dict):
        return routing["fields"]
    if isinstance(stage_output, dict):
        extract = stage_output.get("extract")
        if isinstance(extract, dict) and isinstance(extract.get("fields"), dict):
            return extract["fields"]
        route = stage_output.get("route")
        if isinstance(route, dict) and isinstance(route.get("fields"), dict):
            return route["fields"]
    return {}


async def _load_candidate_clients(
    conn: asyncpg.Connection, client_ids: list[int]
) -> list[dict[str, Any]]:
    """READ-ONLY lookup of candidate clients (id, name, assigned_to)."""
    if not client_ids:
        return []
    rows = await conn.fetch(
        """
        SELECT id, full_name, assigned_to
        FROM clients
        WHERE id = ANY($1::bigint[]) AND deleted_at IS NULL
        """,
        client_ids,
    )
    return [
        {"client_id": r["id"], "full_name": r["full_name"], "assigned_to": r["assigned_to"]}
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# GET /queue — list review_pending proposals (RBAC-filtered)
# --------------------------------------------------------------------------- #
@router.get("/queue")
async def list_review_queue(
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
    status: str = Query("review_pending", pattern="^(review_pending|review_claimed)$"),
    source: str | None = Query(None, description="Filter by intake source (whatsapp|drive|zoho)"),
    decision: str | None = Query(
        None, description="Filter by entity_resolution.decision (AUTO_ATTACH|LINK_CANDIDATE|AMBIGUOUS|NO_MATCH)"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List proposals awaiting review, filtered by the caller's RBAC scope.

    Admins see everything. Team members see only proposals whose resolved
    candidate client is assigned to them; proposals with no resolved client
    (NO_MATCH / AMBIGUOUS) are admin-only.
    """
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.id            AS proposal_id,
                p.queue_id,
                p.doc_index,
                p.status,
                p.routing_key,
                p.entity_resolution,
                p.routing,
                p.commit_gate,
                p.lease_owner,
                p.lease_expires_at,
                p.created_at,
                q.source,
                q.status        AS queue_status,
                q.stage_output
            FROM document_routing_proposal p
            JOIN intake_queue q ON q.id = p.queue_id
            WHERE p.status = $1
              AND ($2::text IS NULL OR q.source = $2)
            ORDER BY p.created_at ASC, p.id ASC
            """,
            status,
            source,
        )

        items: list[dict[str, Any]] = []
        for row in rows:
            entity_resolution = _as_dict(row["entity_resolution"])
            routing = _as_dict(row["routing"])
            commit_gate = _as_dict(row["commit_gate"])
            stage_output = _as_dict(row["stage_output"])

            row_decision = entity_resolution.get("decision")
            if decision is not None and row_decision != decision:
                continue

            candidate_ids = _candidate_client_ids(entity_resolution)
            candidates = await _load_candidate_clients(conn, candidate_ids)

            # RBAC: non-admins only see items assigned to them.
            if not admin:
                assigned_set = {
                    (c.get("assigned_to") or "").lower().strip() for c in candidates
                }
                # No resolved client → admin-only. Resolved but not assigned to me → hide.
                if not candidates or user_email not in assigned_set:
                    continue

            items.append(
                {
                    "proposal_id": row["proposal_id"],
                    "queue_id": row["queue_id"],
                    "doc_index": row["doc_index"],
                    "status": row["status"],
                    "routing_key": row["routing_key"],
                    "source": row["source"],
                    "queue_status": row["queue_status"],
                    "decision": row_decision,
                    "doc_type": routing.get("doc_type") or stage_output.get("doc_type"),
                    "entity_candidates": candidates,
                    "routing": routing,
                    "commit_gate": commit_gate,
                    "extracted_fields": _extracted_fields(stage_output, routing),
                    "confidence": routing.get("type_confidence")
                    or entity_resolution.get("score"),
                    "lease_owner": row["lease_owner"],
                    "lease_expires_at": _iso(row["lease_expires_at"]),
                    "created_at": _iso(row["created_at"]),
                }
            )

    # Pagination AFTER RBAC filtering (the WHERE can't express assigned-to-me
    # without joining a noisy JSON path; the in-app filter is the safe option).
    total = len(items)
    page = items[offset : offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": page}


# --------------------------------------------------------------------------- #
# GET /{proposal_id} — full detail
# --------------------------------------------------------------------------- #
@router.get("/{proposal_id}")
async def get_review_detail(
    proposal_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Full review detail for a single proposal (READ-ONLY)."""
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                p.id            AS proposal_id,
                p.queue_id,
                p.doc_index,
                p.status,
                p.routing_key,
                p.entity_resolution,
                p.routing,
                p.commit_gate,
                p.lease_owner,
                p.lease_expires_at,
                p.created_at,
                q.source,
                q.source_ref,
                q.status        AS queue_status,
                q.blob_path,
                q.stage_output
            FROM document_routing_proposal p
            JOIN intake_queue q ON q.id = p.queue_id
            WHERE p.id = $1
            """,
            proposal_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Proposal not found")

        entity_resolution = _as_dict(row["entity_resolution"])
        routing = _as_dict(row["routing"])
        commit_gate = _as_dict(row["commit_gate"])
        stage_output = _as_dict(row["stage_output"])

        candidate_ids = _candidate_client_ids(entity_resolution)
        candidates = await _load_candidate_clients(conn, candidate_ids)

        if not admin:
            assigned_set = {(c.get("assigned_to") or "").lower().strip() for c in candidates}
            if not candidates or user_email not in assigned_set:
                # Hide existence from non-authorised team members.
                raise HTTPException(status_code=403, detail="Not authorised for this proposal")

        # OCR text per page (if FASE-3 stored it in stage_output) — for human review.
        ocr = stage_output.get("ocr") if isinstance(stage_output, dict) else None
        ocr_pages = ocr.get("pages") if isinstance(ocr, dict) else None

        return {
            "proposal_id": row["proposal_id"],
            "queue_id": row["queue_id"],
            "doc_index": row["doc_index"],
            "status": row["status"],
            "routing_key": row["routing_key"],
            "source": row["source"],
            "source_ref": row["source_ref"],
            "queue_status": row["queue_status"],
            "blob_path": row["blob_path"],
            "decision": entity_resolution.get("decision"),
            "doc_type": routing.get("doc_type") or stage_output.get("doc_type"),
            "entity_resolution": entity_resolution,
            "entity_candidates": candidates,
            "routing": routing,
            "commit_gate": commit_gate,
            "extracted_fields": _extracted_fields(stage_output, routing),
            "ocr_pages": ocr_pages,
            "stage_output": stage_output,
            "lease_owner": row["lease_owner"],
            "lease_expires_at": _iso(row["lease_expires_at"]),
            "created_at": _iso(row["created_at"]),
        }


# --------------------------------------------------------------------------- #
# POST /{proposal_id}/claim — atomic lease
# --------------------------------------------------------------------------- #
@router.post("/{proposal_id}/claim")
async def claim_review(
    proposal_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Atomically claim a proposal for the current reviewer.

    review_pending → review_claimed. Mints a per-claim opaque token (P0#5).
    A claim succeeds if the proposal is review_pending OR if it is review_claimed
    by someone whose lease has expired (steal-expired). A live, unexpired claim by
    another reviewer → 409.
    """
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()
    token = uuid.uuid4()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=CLAIM_TTL_MINUTES)

    async with pool.acquire() as conn:
        # RBAC gate up-front (cheap read of the candidate scope).
        if not admin:
            prop = await conn.fetchrow(
                "SELECT entity_resolution FROM document_routing_proposal WHERE id = $1",
                proposal_id,
            )
            if prop is None:
                raise HTTPException(status_code=404, detail="Proposal not found")
            candidate_ids = _candidate_client_ids(_as_dict(prop["entity_resolution"]))
            candidates = await _load_candidate_clients(conn, candidate_ids)
            assigned_set = {(c.get("assigned_to") or "").lower().strip() for c in candidates}
            if not candidates or user_email not in assigned_set:
                raise HTTPException(status_code=403, detail="Not authorised for this proposal")

        # Atomic claim: only steal a claim that is unclaimed OR expired.
        updated = await conn.fetchrow(
            """
            UPDATE document_routing_proposal
            SET status = 'review_claimed',
                lease_owner = $2,
                lease_expires_at = $3,
                claim_token = $4,
                claimed_at = $5
            WHERE id = $1
              AND (
                    status = 'review_pending'
                 OR (status = 'review_claimed' AND lease_expires_at < $5)
              )
            RETURNING id, lease_owner, lease_expires_at, claim_token
            """,
            proposal_id,
            user_email,
            expires,
            token,
            now,
        )

    if updated is None:
        # Either it doesn't exist, or it's live-claimed by someone else / terminal.
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT status, lease_owner FROM document_routing_proposal WHERE id = $1",
                proposal_id,
            )
        if existing is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        raise HTTPException(
            status_code=409,
            detail=(
                f"Proposal not claimable (status={existing['status']}, "
                f"lease_owner={existing['lease_owner']})"
            ),
        )

    logger.info(
        "intake.review.claimed",
        extra={"proposal_id": proposal_id, "reviewer": user_email},
    )
    return {
        "proposal_id": updated["id"],
        "status": "review_claimed",
        "lease_owner": updated["lease_owner"],
        "lease_expires_at": _iso(updated["lease_expires_at"]),
        "claim_token": str(updated["claim_token"]),
    }


# --------------------------------------------------------------------------- #
# POST /{proposal_id}/release — give back the claim
# --------------------------------------------------------------------------- #
@router.post("/{proposal_id}/release")
async def release_review(
    proposal_id: int = Path(..., ge=1),
    claim_token: str | None = Query(None, description="Token returned by /claim (required for non-admins)"),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Release a claimed proposal back to review_pending.

    The claim-holder must present the claim_token (P0#5). Admins may force-release
    without a token (lease-reaper / abandoned reviewer).
    """
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()

    token_uuid: uuid.UUID | None = None
    if claim_token:
        try:
            token_uuid = uuid.UUID(claim_token)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid claim_token") from exc

    async with pool.acquire() as conn:
        if admin:
            # Admin force-release: any claimed proposal.
            updated = await conn.fetchrow(
                """
                UPDATE document_routing_proposal
                SET status = 'review_pending',
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    claim_token = NULL,
                    claimed_at = NULL
                WHERE id = $1 AND status = 'review_claimed'
                RETURNING id
                """,
                proposal_id,
            )
        else:
            # Holder release: must match owner + token.
            if token_uuid is None:
                raise HTTPException(status_code=400, detail="claim_token required")
            updated = await conn.fetchrow(
                """
                UPDATE document_routing_proposal
                SET status = 'review_pending',
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    claim_token = NULL,
                    claimed_at = NULL
                WHERE id = $1
                  AND status = 'review_claimed'
                  AND lease_owner = $2
                  AND claim_token = $3
                RETURNING id
                """,
                proposal_id,
                user_email,
                token_uuid,
            )

    if updated is None:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT status, lease_owner FROM document_routing_proposal WHERE id = $1",
                proposal_id,
            )
        if existing is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        raise HTTPException(
            status_code=409,
            detail=(
                "Release failed: proposal not claimed by you with a valid token "
                f"(status={existing['status']}, lease_owner={existing['lease_owner']})"
            ),
        )

    logger.info(
        "intake.review.released",
        extra={"proposal_id": proposal_id, "reviewer": user_email, "admin_force": admin},
    )
    return {"proposal_id": updated["id"], "status": "review_pending"}


# --------------------------------------------------------------------------- #
# FASE 5C stubs — writer not active in 5A
# --------------------------------------------------------------------------- #
@router.post("/{proposal_id}/approve")
async def approve_review(
    proposal_id: int = Path(..., ge=1),
    body: dict[str, Any] = Body(default_factory=dict),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Approve a proposal — FASE 5B DRY-RUN.

    Builds the full CommitPlan (what the writer WOULD do) and runs it through
    ``execute_commit(dry_run=True)``: it records ONE ``intake_commit_audit(dry_run=true)``
    row and writes NOTHING to the CRM (no documents INSERT, no practices UPDATE).

    P0#5: the caller must hold the active claim — non-admins must present the
    matching ``claim_token`` on a non-expired lease. The proposal status is NOT
    advanced to a terminal state in dry-run (P0#9): it stays ``review_claimed``.

    body: {client_id?, practice_id?, final_fields?, claim_token?}
    """
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()
    claim_token = body.get("claim_token")
    override_client_id = body.get("client_id")
    override_practice_id = body.get("practice_id")
    final_fields = body.get("final_fields") if isinstance(body.get("final_fields"), dict) else None

    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        async with conn.transaction():
            prop = await conn.fetchrow(
                """
                SELECT id, queue_id, doc_index, pipeline_version, status,
                       entity_resolution, routing, commit_gate,
                       lease_owner, lease_expires_at, claim_token
                FROM document_routing_proposal
                WHERE id = $1
                FOR UPDATE
                """,
                proposal_id,
            )
            if prop is None:
                raise HTTPException(status_code=404, detail="Proposal not found")

            # P0#5 — claim/lease enforcement.
            if prop["status"] != "review_claimed":
                raise HTTPException(
                    status_code=409,
                    detail=f"Proposal must be review_claimed to approve (status={prop['status']}).",
                )
            lease_exp = prop["lease_expires_at"]
            if lease_exp is None or lease_exp < now:
                raise HTTPException(status_code=409, detail="Claim lease expired - re-claim first.")
            if not admin:
                if (prop["lease_owner"] or "").lower().strip() != user_email:
                    raise HTTPException(status_code=403, detail="You do not hold this claim.")
                if claim_token is None:
                    raise HTTPException(status_code=400, detail="claim_token required.")
                try:
                    tok = uuid.UUID(str(claim_token))
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail="Invalid claim_token.") from exc
                if prop["claim_token"] != tok:
                    raise HTTPException(status_code=403, detail="claim_token does not match active claim.")

            plan = await intake_writer.plan_commit(
                prop,
                conn,
                committed_by=user_email or "system:hitl",
                override_client_id=override_client_id,
                override_practice_id=override_practice_id,
                final_fields=final_fields,
            )
            result = await intake_writer.execute_commit(plan, conn, dry_run=True)

    logger.info(
        "intake.review.approve.dry_run proposal=%s reviewer=%s outcome=%s",
        proposal_id, user_email, result.outcome,
    )
    return {
        "proposal_id": proposal_id,
        "dry_run": True,
        "status": "review_claimed",  # P0#9: NOT advanced in dry-run
        "outcome": result.outcome,
        "would_commit": plan.to_dict(),
        "result": result.to_dict(),
    }


@router.post("/{proposal_id}/reject", status_code=501)
async def reject_review_stub(
    proposal_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Stub — terminal/dead-state write, lives in FASE 5C."""
    raise HTTPException(status_code=501, detail=_WRITER_DISABLED_DETAIL)


# --------------------------------------------------------------------------- #
# small internal helpers
# --------------------------------------------------------------------------- #
def _as_dict(value: Any) -> dict[str, Any]:
    """asyncpg returns JSONB as a Python dict already; coerce defensively."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
