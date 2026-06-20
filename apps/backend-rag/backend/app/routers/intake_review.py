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
  * RBAC (§6e, P0#4): the axis is OWN-CHAT, not client-assignment. Admins
    (zero@/asya@/antonellosiano@ — is_crm_admin) see the ENTIRE queue (every
    worker's docs, every decision) for supervision. A non-admin sees ONLY rows
    whose `intake_queue.received_by` (the receiving employee's email, set by the
    wa-mirror sweeper) equals the caller's email. This INCLUDES that worker's own
    NO_MATCH / AMBIGUOUS / null-decision docs — "it's my chat" takes PRECEDENCE
    over the client-resolution gate, so the receiver (not an admin) reviews them.
    Docs with `received_by IS NULL` (the shared business-line `whatsapp-live:*`
    feeds + Drive-sourced docs) are admin-only: a NULL received_by never equals a
    non-admin's email, so the `received_by = :email` filter excludes them naturally.
  * claim_token (P0#5): claim mints an opaque token; FASE 5C mutations must present
    it. release verifies it to avoid a stale reviewer stealing another's claim.
  * Atomic claim: UPDATE ... WHERE status='review_pending' RETURNING. Concurrent
    second claim → 409.

PII: this data lives ONLY on the local Pro Postgres (Law 2 / UU-PDP).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from fastapi.responses import FileResponse

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.intake import crm_push as intake_crm_push
from backend.services.intake import writer as intake_writer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake/review", tags=["intake-review"])

# How long a single reviewer holds a proposal before it becomes reclaimable.
CLAIM_TTL_MINUTES = 15

# Which intake sources surface in the human review queue. Per Zero (2026-06-19):
# the review queue is WhatsApp-only "for now" — Drive/Dropbox documents are still
# catalogued into intake_queue + document_routing_proposal (the DB record is kept
# and the worker keeps running), they just must NOT flood the team/admin review
# list. The Dropbox→Drive mirror is the team's whole historical archive (years of
# scans + iPhone camera rolls), so draining it into review buried the ~107 real
# WhatsApp docs under ~19.6k archive proposals. This is the single gate that keeps
# the queue honest; widen it only by setting INTAKE_REVIEW_SOURCES.
#
# Override (CSV, e.g. "whatsapp,drive") to re-admit other sources without a code
# change. An empty/whitespace value falls back to the default allowlist.
_DEFAULT_REVIEW_SOURCES = ("whatsapp",)


def _review_source_allowlist() -> tuple[str, ...]:
    raw = os.getenv("INTAKE_REVIEW_SOURCES", "")
    parsed = tuple(s.strip().lower() for s in raw.split(",") if s.strip())
    return parsed or _DEFAULT_REVIEW_SOURCES

# MIME types a browser can render inline WITHOUT a script-execution surface.
# Deliberately excludes image/svg+xml (can embed <script>) and text/html.
_INLINE_SAFE_MIME = frozenset(
    {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif"}
)


# --------------------------------------------------------------------------- #
# Shared RBAC guard (own-chat axis) — single source of truth
# --------------------------------------------------------------------------- #
async def _require_own_chat_or_admin(
    conn: asyncpg.Connection,
    proposal_id: int,
    *,
    admin: bool,
    user_email: str,
) -> asyncpg.Record:
    """Fetch the proposal's queue context and enforce the own-chat RBAC axis.

    Returns the joined row (proposal + queue context) on success. A non-admin
    may touch a proposal ONLY if it came from their own chat
    (``intake_queue.received_by == caller``). NULL received_by (shared business
    line + Drive, pre-backfill) never matches → admin-only. One helper instead
    of four hand-rolled copies (detail/claim/blob/queue) so the rule cannot drift.
    """
    row = await conn.fetchrow(
        """
        SELECT p.id AS proposal_id, q.id AS queue_id, q.received_by,
               q.blob_path, q.source, q.source_ref,
               di.mime_type, di.byte_size
        FROM document_routing_proposal p
        JOIN intake_queue q ON q.id = p.queue_id
        LEFT JOIN document_instances di ON di.id = q.instance_id
        WHERE p.id = $1
        """,
        proposal_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if not admin:
        received_by = (row["received_by"] or "").lower().strip()
        if received_by != user_email:
            # Hide existence from non-authorised team members.
            raise HTTPException(status_code=403, detail="Not authorised for this proposal")
    return row



# --------------------------------------------------------------------------- #
# Candidate-client extraction (read-only helper)
# --------------------------------------------------------------------------- #
def _candidate_client_ids(
    entity_resolution: dict[str, Any], routing: dict[str, Any] | None = None
) -> list[int]:
    """Best-effort extraction of candidate client ids from the FASE-4 blob.

    FASE 4's entity_resolution shape is still settling; be tolerant. Recognised
    shapes:
      {"candidates": [{"client_id": 412, ...}, ...]}
      {"candidates": [{"id": 412, "table": "clients", ...}, ...]}   <- LIVE shape
      {"client_id": 412}
      {"resolved_client_id": 412}
    plus the routing blob's resolved target ({"client_id": 412}) as fallback.

    The ``id``+``table`` variant is what the production resolver actually
    writes (every live proposal sampled 2026-06-11 used it) — recognising only
    ``client_id`` left entity_candidates empty and the UI radio list dead.
    Returns a de-duplicated list of ints (empty if nothing resolvable).
    """
    ids: list[int] = []
    if not isinstance(entity_resolution, dict):
        entity_resolution = {}

    for key in ("resolved_client_id", "client_id"):
        val = entity_resolution.get(key)
        if isinstance(val, int):
            ids.append(val)

    candidates = entity_resolution.get("candidates")
    if isinstance(candidates, list):
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            if isinstance(cand.get("client_id"), int):
                ids.append(cand["client_id"])
            elif isinstance(cand.get("id"), int) and cand.get("table") in (None, "clients"):
                ids.append(cand["id"])

    if isinstance(routing, dict) and isinstance(routing.get("client_id"), int):
        ids.append(routing["client_id"])

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


def _ocr_pages(stage_output: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Per-page OCR text for human review, normalised to the UI shape.

    The UI (review/page.tsx) renders items as ``{page_number, text}``. OCR text
    can live in two places depending on pipeline version:

      * ``stage_output.ocr.pages`` — the dedicated FASE-3 OCR stage (older docs).
      * ``stage_output.classify.ocr_text_per_page`` — the CURRENT pipeline runs
        OCR inside the *classify* stage; the ``ocr`` stage only writes a marker
        ``{"deferred_to": "classify"}`` with NO ``pages``. Without this fallback
        the review text area was empty even though OCR ran (the bug).

    Prefer ``ocr.pages`` when it is a non-empty list; otherwise fall back to
    ``classify.ocr_text_per_page``. Each source item may be a dict carrying
    ``text`` (+ an optional ``page``/``page_number``) or a plain string
    (defensive). ``page_number`` is surfaced 1-based positionally so the human
    label is consistent across both sources (classify stores a 0-indexed
    ``page``; ocr.pages stores a 1-based ``page``) and never shows "page 0".
    Returns ``None`` when neither source has any text — an empty area is correct
    for a truly OCR-less document.
    """
    if not isinstance(stage_output, dict):
        return None

    def _normalise(items: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                text = item.get("text")
            else:
                continue
            if not text:
                continue
            out.append({"page_number": len(out) + 1, "text": text})
        return out

    ocr = stage_output.get("ocr")
    if isinstance(ocr, dict):
        pages = ocr.get("pages")
        if isinstance(pages, list) and pages:
            normalised = _normalise(pages)
            if normalised:
                return normalised

    classify = stage_output.get("classify")
    if isinstance(classify, dict):
        per_page = classify.get("ocr_text_per_page")
        if isinstance(per_page, list) and per_page:
            normalised = _normalise(per_page)
            if normalised:
                return normalised

    return None


async def _load_candidate_clients(
    conn: asyncpg.Connection, client_ids: list[int]
) -> list[dict[str, Any]]:
    """READ-ONLY lookup of candidate clients, with the disambiguators a human
    needs to tell homonyms apart (phone/email/nationality — the "tanti Walter"
    problem: 10 clients named Walter, distinguishable only by phone)."""
    if not client_ids:
        return []
    rows = await conn.fetch(
        """
        SELECT id, full_name, assigned_to, email, phone, nationality
        FROM clients
        WHERE id = ANY($1::bigint[]) AND deleted_at IS NULL
        """,
        client_ids,
    )
    return [
        {
            "client_id": r["id"],
            "full_name": r["full_name"],
            "assigned_to": r["assigned_to"],
            "email": r["email"],
            "phone": r["phone"],
            "nationality": r["nationality"],
        }
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
    source: str | None = Query(
        None,
        description=(
            "Filter by intake source. Must be within the review allowlist "
            "(WhatsApp-only by default; see INTAKE_REVIEW_SOURCES). An out-of-"
            "allowlist source returns an empty page, never Drive/Dropbox docs."
        ),
    ),
    decision: str | None = Query(
        None, description="Filter by entity_resolution.decision (AUTO_ATTACH|LINK_CANDIDATE|AMBIGUOUS|NO_MATCH)"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List proposals awaiting review, filtered by the caller's RBAC scope.

    Admins see the entire queue. A non-admin sees ONLY rows from their own chats
    (`intake_queue.received_by == caller`), including their own NO_MATCH /
    AMBIGUOUS docs. NULL-received_by docs (shared business line + Drive) are
    admin-only.
    """
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()

    # Source gate (WhatsApp-only by default): an explicit ?source= still wins for
    # ad-hoc inspection, but MUST be inside the allowlist — a caller cannot ask
    # for ?source=drive unless INTAKE_REVIEW_SOURCES admits it. With no ?source=,
    # the queue is scoped to the whole allowlist. Both go through the same
    # `q.source = ANY($2)` clause so Drive/Dropbox proposals never surface here.
    allowlist = _review_source_allowlist()
    if source is not None and source.lower() not in allowlist:
        # Asking for a source the queue doesn't admit → an empty, honest page
        # (not an error: the proposal exists in the DB, it's just not reviewable).
        return {"total": 0, "limit": limit, "offset": offset, "items": []}
    source_filter = [source.lower()] if source is not None else list(allowlist)

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
                q.received_by,
                q.status        AS queue_status,
                q.stage_output
            FROM document_routing_proposal p
            JOIN intake_queue q ON q.id = p.queue_id
            WHERE p.status = $1
              AND q.source = ANY($2::text[])
              AND ($3::boolean OR q.received_by = $4)
            ORDER BY p.created_at ASC, p.id ASC
            """,
            status,
            source_filter,
            admin,
            user_email,
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

            candidate_ids = _candidate_client_ids(entity_resolution, routing)
            candidates = await _load_candidate_clients(conn, candidate_ids)

            # RBAC: the own-chat gate (received_by) is enforced in the SQL WHERE
            # above — non-admins see ONLY their received docs (incl. NO_MATCH /
            # AMBIGUOUS); NULL received_by never matches a non-admin's email, so
            # the shared business-line + Drive docs stay admin-only.

            items.append(
                {
                    "proposal_id": row["proposal_id"],
                    "queue_id": row["queue_id"],
                    "doc_index": row["doc_index"],
                    "status": row["status"],
                    "routing_key": row["routing_key"],
                    "source": row["source"],
                    "received_by": row["received_by"],
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

    # Pagination AFTER the in-app `decision` filter (the RBAC own-chat gate is
    # already applied in the SQL WHERE; `decision` lives in a JSONB path so it is
    # filtered in Python, hence the post-fetch slice).
    total = len(items)
    page = items[offset : offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": page}


# --------------------------------------------------------------------------- #
# Destination pickers (STATIC routes — registered BEFORE /{proposal_id} so the
# int path-converter never swallows them)
# --------------------------------------------------------------------------- #
@router.get("/document-categories")
async def list_document_categories(
    _user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Active CRM document categories for the two-level review destination picker.

    The review UI needs the canonical ``document_categories`` table, not a
    hardcoded copy, so the reviewer can choose both the folder-level group and
    the precise CRM document subtype before approve.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT code, name, category_group, description, has_expiry
            FROM document_categories
            WHERE active = true
            ORDER BY sort_order, name
            """
        )
    return {"items": [dict(row) for row in rows]}


@router.get("/clients/search")
async def search_clients(
    q: str = Query(..., min_length=2, max_length=120, description="Client name fragment"),
    limit: int = Query(10, ge=1, le=25),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Name/phone/email lookup over local CRM clients for the destination picker.

    Projection includes the HUMAN DISAMBIGUATORS (phone/email/nationality):
    the CRM holds many homonyms (10 bare "Walter"s) distinguishable only by
    contact data — a name-only list forces blind guessing. Phone matching
    activates when the query carries >=5 digits. This is a routing affordance,
    not client access: a reviewer redirecting a NO_MATCH document must find ANY
    client. pg_trgm-ranked, ILIKE-gated. READ-ONLY, Pro reader, local DB only.
    """
    needle = q.strip()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, full_name, assigned_to, email, phone, nationality,
                   similarity(full_name, $1) AS sim
            FROM clients
            WHERE deleted_at IS NULL
              AND (full_name ILIKE '%' || $1 || '%'
                   OR phone LIKE '%' || regexp_replace($1, '[^0-9+]', '', 'g') || '%'
                       AND length(regexp_replace($1, '[^0-9]', '', 'g')) >= 5
                   OR email ILIKE '%' || $1 || '%')
            ORDER BY sim DESC, full_name ASC
            LIMIT $2
            """,
            needle,
            limit,
        )
    return {
        "items": [
            {
                "client_id": r["id"],
                "full_name": r["full_name"],
                "assigned_to": r["assigned_to"],
                "email": r["email"],
                "phone": r["phone"],
                "nationality": r["nationality"],
                "score": round(float(r["sim"] or 0.0), 4),
            }
            for r in rows
        ]
    }


@router.get("/clients/{client_id}/practices")
async def list_client_practices(
    client_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Open/recent practices of a client — the practice picker for approve.

    READ-ONLY, minimal projection. Sorted: open practices first, then recency.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, practice_type_code, title, status, created_at
            FROM practices
            WHERE client_id = $1
            ORDER BY (status NOT IN ('completed','cancelled')) DESC,
                     created_at DESC
            LIMIT 20
            """,
            client_id,
        )
    return {
        "items": [
            {
                "practice_id": r["id"],
                "practice_type_code": r["practice_type_code"],
                "title": r["title"],
                "status": r["status"],
                "created_at": _iso(r["created_at"]),
            }
            for r in rows
        ]
    }


# --------------------------------------------------------------------------- #
# GET /{proposal_id}/blob — stream the ORIGINAL document for visual review
# --------------------------------------------------------------------------- #
@router.get("/{proposal_id}/blob")
async def get_review_blob(
    proposal_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> FileResponse:
    """Stream the original blob (image/PDF) so the reviewer SEES the document.

    OCR text alone is not review-grade: the human must compare the proposal
    against the actual scan. Same RBAC as detail (own-chat or admin). Served
    by the Pro reader straight off the local filesystem — the blob never
    persists anywhere else; ``no-store`` keeps every proxy/browser cache out
    (Law 2: PII in transit to the authenticated reviewer only).
    """
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()

    async with pool.acquire() as conn:
        row = await _require_own_chat_or_admin(
            conn, proposal_id, admin=admin, user_email=user_email
        )

    blob_path = row["blob_path"]
    if not blob_path or not os.path.isfile(blob_path):
        raise HTTPException(status_code=404, detail="Blob not on disk")

    # XSS hardening: blobs are UNTRUSTED uploads (WhatsApp/Drive). Only types a
    # browser cannot script render inline (no SVG — it can embed <script>, no
    # HTML); anything else is rewritten to an opaque octet-stream ATTACHMENT.
    # nosniff everywhere kills content-sniffing; CSP sandbox guards the
    # attachment path (not sent on inline PDF — it breaks browser PDF viewers,
    # and the allowlist already excludes every scriptable type).
    inline_safe = row["mime_type"] in _INLINE_SAFE_MIME
    headers = {
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
    }
    if not inline_safe:
        headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return FileResponse(
        blob_path,
        media_type=row["mime_type"] if inline_safe else "application/octet-stream",
        headers=headers,
        filename=os.path.basename(blob_path),
        content_disposition_type="inline" if inline_safe else "attachment",
    )


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
                q.received_by,
                q.status        AS queue_status,
                q.blob_path,
                q.stage_output,
                di.mime_type,
                di.byte_size
            FROM document_routing_proposal p
            JOIN intake_queue q ON q.id = p.queue_id
            LEFT JOIN document_instances di ON di.id = q.instance_id
            WHERE p.id = $1
            """,
            proposal_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Proposal not found")

        # RBAC (own-chat axis): a non-admin may open a proposal ONLY if it came
        # from their own chat (intake_queue.received_by == caller). NULL
        # received_by (shared business line + Drive) never matches → admin-only.
        if not admin:
            received_by = (row["received_by"] or "").lower().strip()
            if received_by != user_email:
                # Hide existence from non-authorised team members.
                raise HTTPException(status_code=403, detail="Not authorised for this proposal")

        entity_resolution = _as_dict(row["entity_resolution"])
        routing = _as_dict(row["routing"])
        commit_gate = _as_dict(row["commit_gate"])
        stage_output = _as_dict(row["stage_output"])

        candidate_ids = _candidate_client_ids(entity_resolution, routing)
        candidates = await _load_candidate_clients(conn, candidate_ids)

        # OCR text per page — for human review. The current pipeline runs OCR
        # in the *classify* stage (ocr stage only writes a marker), so the
        # reader must look in classify.ocr_text_per_page as well as ocr.pages.
        ocr_pages = _ocr_pages(stage_output)

        return {
            "proposal_id": row["proposal_id"],
            "queue_id": row["queue_id"],
            "doc_index": row["doc_index"],
            "status": row["status"],
            "routing_key": row["routing_key"],
            "source": row["source"],
            "source_ref": row["source_ref"],
            "received_by": row["received_by"],
            "queue_status": row["queue_status"],
            "blob_path": row["blob_path"],
            "mime_type": row["mime_type"],
            "byte_size": row["byte_size"],
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
    A claim succeeds if the proposal is review_pending, OR if it is review_claimed
    by someone whose lease has expired (steal-expired), OR if it is review_claimed
    by the SAME caller on a still-live lease (P0#4 — idempotent re-claim: re-opening
    your own claimed document renews the lease and returns a fresh token instead of
    409). A live, unexpired claim by a DIFFERENT reviewer → 409.
    """
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()
    token = uuid.uuid4()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=CLAIM_TTL_MINUTES)

    async with pool.acquire() as conn:
        # RBAC gate up-front (own-chat axis, shared helper): a non-admin may
        # claim ONLY a proposal that came from their own chat.
        await _require_own_chat_or_admin(
            conn, proposal_id, admin=admin, user_email=user_email
        )

        # Atomic claim: steal a claim that is unclaimed OR expired, OR renew
        # the caller's OWN still-live claim (P0#4 idempotent re-claim). A live
        # claim owned by a DIFFERENT reviewer never matches → 409 below.
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
                 OR (status = 'review_claimed' AND lease_owner = $2)
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
# Shared claim/lease guard (P0#5) — used by approve AND reject
# --------------------------------------------------------------------------- #
async def _require_active_claim(
    prop: asyncpg.Record,
    *,
    admin: bool,
    user_email: str,
    claim_token: str | None,
) -> None:
    """Raise unless the caller holds the active, unexpired claim on ``prop``.

    P0#5: the proposal must be ``review_claimed`` with a non-expired lease; a
    non-admin must own the lease AND present the matching ``claim_token`` UUID.
    Admins bypass the owner/token checks but NOT the status/expiry checks.

    The caller must have already ``SELECT ... FOR UPDATE``'d ``prop`` (so this is a
    pure in-memory check on the locked row). Mirrors the original inline guard in
    ``approve_review`` exactly — extracted so ``reject_review`` enforces the
    identical rule without drift.
    """
    now = datetime.now(timezone.utc)
    if prop["status"] != "review_claimed":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal must be review_claimed (status={prop['status']}).",
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


# --------------------------------------------------------------------------- #
# Post-commit Pro→Fly CRM delivery (Drive folder + Fly documents row)
# --------------------------------------------------------------------------- #
async def _deliver_committed_to_crm(
    *,
    pool: asyncpg.Pool,
    request: Request,
    queue_id: int | None,
    plan: intake_writer.CommitPlan,
    result: intake_writer.CommitResult,
) -> dict[str, Any]:
    """Best-effort delivery of a COMMITTED document to the Fly CRM.

    Runs AFTER the local commit transaction succeeded (the local Pro Postgres
    commit stays the source of truth for the approve outcome). Reuses the Fly
    base64 upload endpoint, authenticated with the reviewer's own bearer JWT
    (forwarded by the Fly proxy on the incoming request). On success the LOCAL
    ``documents`` row is enriched with the Drive file_id/file_url; either way
    the push status is appended to the ``intake_commit_audit.plan`` jsonb of
    this commit's audit row. NEVER raises — a failed delivery leaves the
    approve outcome 'committed' and surfaces {status, detail} to the caller.
    """
    import json as _json

    if not intake_crm_push.push_enabled():
        return {"status": "disabled"}

    # Reviewer's bearer JWT — reused for the Pro→Fly call (same RBAC actor).
    auth_header = request.headers.get("authorization") or ""
    bearer = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else None

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
        # Idempotent re-approve guard: if the local row already carries a Drive
        # file (previous successful push, or Drive-sourced intake), do NOT
        # upload again — that would duplicate the file in the client's folder.
        if result.doc_id is not None:
            already = await conn.fetchrow(
                "SELECT file_id, file_url FROM documents WHERE id = $1", result.doc_id
            )

    payload = plan.payload
    if already is not None and (already["file_id"] or already["file_url"]):
        push = intake_crm_push.CrmPushResult(
            ok=False,
            status="already_delivered",
            file_id=already["file_id"],
            file_url=already["file_url"],
            detail="local documents row already has a Drive file — skipping re-upload",
        )
    elif not blob_path:
        push = intake_crm_push.CrmPushResult(
            ok=False, status="missing_blob", detail="no blob_path on intake_queue row"
        )
    else:
        push = await intake_crm_push.push_committed_document(
            bearer_token=bearer,
            client_id=int(plan.client_id),  # type: ignore[arg-type]  # committed ⇒ non-None
            practice_id=plan.practice_id,
            document_type=payload.get("document_type") or "unknown",
            document_category=payload.get("document_category"),
            file_name=payload.get("file_name") or os.path.basename(blob_path),
            blob_path=blob_path,
            mime_type=mime_type,
            expiry_date=payload.get("expiry_date"),
            notes=payload.get("notes"),
        )

    crm_info: dict[str, Any] = {
        "status": push.status,
        "fly_doc_id": push.fly_doc_id,
        "file_url": push.file_url,
    }
    if push.detail:
        crm_info["detail"] = push.detail

    # Post-delivery bookkeeping (best-effort, outside the commit TX by design).
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
                    _json.dumps({"crm_push": crm_info}),
                )
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as exc:
        logger.error(
            "intake.review.crm_push.bookkeeping_failed proposal=%s err=%s",
            plan.proposal_id,
            exc,
        )

    if not push.ok and push.status not in ("disabled", "already_delivered"):
        logger.warning(
            "intake.review.crm_push.failed proposal=%s doc=%s status=%s detail=%s",
            plan.proposal_id,
            result.doc_id,
            push.status,
            push.detail,
        )
    return crm_info


# --------------------------------------------------------------------------- #
# approve (dry-run 5B / real commit 5C) + reject (terminal, queue-management)
# --------------------------------------------------------------------------- #
def _clean_destination_value(value: Any) -> str | None:
    """Normalise an optional destination override value from the approve body."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def _apply_document_destination_override(
    plan: intake_writer.CommitPlan,
    *,
    document_category: Any,
    document_subtype: Any,
) -> None:
    """Apply reviewer-selected destination to payload and planned write ops.

    ``plan_commit`` derives a best-effort document category from the intake
    doc_type. The review UI can now override both the folder-level category
    (``documents.document_category``) and exact subtype
    (``documents.document_type``). Mutating the plan here keeps dry-run audit
    output and real writes aligned without touching the shared writer module.
    """
    category = _clean_destination_value(document_category)
    subtype = _clean_destination_value(document_subtype)

    if category:
        plan.payload["document_category"] = category
    if subtype:
        plan.payload["document_type"] = subtype
        plan.doc_type = subtype

    for op in plan.ops:
        if op.table == "documents":
            if category:
                op.values["document_category"] = category
            if subtype:
                op.values["document_type"] = subtype
        elif op.table == "practices.documents[]" and subtype:
            op.values["name"] = subtype


@router.post("/{proposal_id}/approve")
async def approve_review(
    request: Request,
    proposal_id: int = Path(..., ge=1),
    body: dict[str, Any] = Body(default_factory=dict),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Approve a proposal — dry-run (5B) OR real commit (5C, flag-gated).

    Builds the full CommitPlan and runs it through ``execute_commit``. The
    ``dry_run`` argument is ``not writer_enabled()``:

    * **Flag OFF (default — 5B behaviour):** dry-run. Records ONE
      ``intake_commit_audit(dry_run=true)`` row, writes NOTHING to the CRM, and
      leaves the proposal ``review_claimed`` (P0#9).
    * **Flag ON (5C go-live):** the real atomic path runs inside THIS request's
      transaction — document UPSERT + practice link + proposal advanced to
      ``routed`` + audit ``committed`` — all-or-nothing. A blocked plan still writes
      nothing and stays ``review_claimed``.

    P0#5: the caller must hold the active claim — non-admins must present the
    matching ``claim_token`` on a non-expired lease.

    body: {client_id?, practice_id?, document_category?, document_subtype?,
           final_fields?, claim_token?}
    """
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()
    claim_token = body.get("claim_token")
    override_client_id = body.get("client_id")
    # Practice override distinguishes ABSENT ("use routing's hint") from an
    # EXPLICIT null ("reviewer chose: archive only, no practice").
    practice_explicit = "practice_id" in body
    override_practice_id = body.get("practice_id")
    final_fields = body.get("final_fields") if isinstance(body.get("final_fields"), dict) else None

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

            # P0#5 — claim/lease enforcement (shared with reject).
            await _require_active_claim(
                prop, admin=admin, user_email=user_email, claim_token=claim_token,
            )

            plan = await intake_writer.plan_commit(
                prop,
                conn,
                committed_by=user_email or "system:hitl",
                override_client_id=override_client_id,
                override_practice_id=override_practice_id,
                practice_explicit=practice_explicit,
                final_fields=final_fields,
            )
            _apply_document_destination_override(
                plan,
                document_category=body.get("document_category"),
                document_subtype=body.get("document_subtype"),
            )
            # FASE 5C gate: dry-run UNLESS INTAKE_WRITER_ENABLED is truthy. With the
            # flag OFF (default) this stays True → simulate + audit-only, exactly as
            # 5B. With the flag ON the real atomic path runs INSIDE this transaction
            # (write document + append practice + advance proposal + audit), so a
            # failure anywhere rolls the WHOLE approve back.
            dry_run = not intake_writer.writer_enabled()
            result = await intake_writer.execute_commit(plan, conn, dry_run=dry_run)

    # Response status reflects what actually happened: a committed real write
    # advanced the proposal to 'routed'; a dry-run (or a blocked plan) left it
    # review_claimed (P0#9).
    advanced = result.outcome == "committed"
    response_status = "routed" if advanced else "review_claimed"

    # Pro→Fly CRM delivery — ONLY after a REAL committed write (never dry-run,
    # never blocked). The local commit above is final regardless of delivery.
    crm_push_info: dict[str, Any] | None = None
    if advanced and not result.dry_run:
        crm_push_info = await _deliver_committed_to_crm(
            pool=pool,
            request=request,
            queue_id=prop["queue_id"],
            plan=plan,
            result=result,
        )
        # Visibility (intake message-journey TAC 2026-06-15): the local commit
        # is final but the Fly/Drive delivery leg is best-effort and NEVER
        # raises. A failed delivery means the document exists in the Pro DB but
        # is ABSENT from kita.balizero (Drive + Fly CRM) — a silent
        # config↔reality divergence (superscar #2 "green ≠ working"). Surface it
        # in the top-level status so the operator/front-end knows the doc did
        # NOT land in kita, instead of seeing a success "routed".
        response_status = _delivery_aware_status(response_status, crm_push_info)

    logger.info(
        "intake.review.approve proposal=%s reviewer=%s dry_run=%s outcome=%s status=%s",
        proposal_id, user_email, result.dry_run, result.outcome, response_status,
    )
    response: dict[str, Any] = {
        "proposal_id": proposal_id,
        "dry_run": result.dry_run,
        "status": response_status,
        "outcome": result.outcome,
        "would_commit": plan.to_dict(),
        "result": result.to_dict(),
    }
    if crm_push_info is not None:
        response["crm_push"] = crm_push_info
    return response


@router.post("/{proposal_id}/reject")
async def reject_review(
    proposal_id: int = Path(..., ge=1),
    body: dict[str, Any] = Body(default_factory=dict),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Reject a proposal — terminal transition ``review_claimed`` → ``rejected``.

    This is a **queue-management** operation: it writes ONLY the proposal status +
    clears the lease. It touches NO CRM data (no ``documents``, no ``practices``),
    so — unlike ``approve`` — it is NOT gated by ``INTAKE_WRITER_ENABLED``: reviewers
    must be able to dispose of garbage/NO_MATCH proposals in every phase (5B and 5C),
    exactly like ``claim``/``release`` (which are also un-gated).

    P0#5: identical claim/lease enforcement as ``approve`` (shared helper).
    Writes ONE forensic ``intake_commit_audit(outcome='rejected')`` row (who
    rejected what + the reviewer's ``reason``, migration 224) — a rejection is a
    HITL decision and deserves the same audit trail as an approve. Idempotent
    under concurrency / re-reject: the ``status='review_claimed'`` guard makes a
    second reject a 409 no-op, never a double-write.

    body: {claim_token?, reason?}  — ``reason`` is persisted in the audit plan.
    """
    admin = is_crm_admin(user)
    user_email = (user.get("email") or "").lower().strip()
    claim_token = body.get("claim_token")
    reason = body.get("reason")

    async with pool.acquire() as conn:
        async with conn.transaction():
            prop = await conn.fetchrow(
                """
                SELECT id, queue_id, status, lease_owner, lease_expires_at, claim_token
                FROM document_routing_proposal
                WHERE id = $1
                FOR UPDATE
                """,
                proposal_id,
            )
            if prop is None:
                raise HTTPException(status_code=404, detail="Proposal not found")

            await _require_active_claim(
                prop, admin=admin, user_email=user_email, claim_token=claim_token,
            )

            # Terminal transition + lease clear. Reuse the release_review lease-clear
            # UPDATE but set status='rejected' (terminal per chk_rp_status), NOT
            # 'review_pending'. The status='review_claimed' guard makes a concurrent
            # loser / re-reject a no-op (RETURNING NULL → 409 below).
            updated = await conn.fetchrow(
                """
                UPDATE document_routing_proposal
                   SET status = 'rejected',
                       lease_owner = NULL,
                       lease_expires_at = NULL,
                       claim_token = NULL,
                       claimed_at = NULL
                 WHERE id = $1 AND status = 'review_claimed'
                RETURNING id
                """,
                proposal_id,
            )

            if updated is not None:
                # Forensic audit (same TX as the transition): outcome='rejected'
                # per migration 224. decision stays NULL (chk_ica_decision).
                import json as _json

                await conn.execute(
                    """
                    INSERT INTO intake_commit_audit (
                        proposal_id, queue_id, committed_by, dry_run,
                        outcome, plan
                    ) VALUES ($1, $2, $3, false, 'rejected', $4::jsonb)
                    """,
                    proposal_id,
                    prop["queue_id"],
                    user_email or "system:hitl",
                    _json.dumps({"reason": (reason or "")[:500]}),
                )

    if updated is None:
        # Lost the race or already terminal (the guard above passed at SELECT time
        # but the row changed) — surface as conflict.
        raise HTTPException(status_code=409, detail="Proposal no longer review_claimed.")

    logger.info(
        "intake.review.rejected proposal=%s reviewer=%s admin=%s reason=%s",
        proposal_id, user_email, admin, (reason or "")[:200],
    )
    return {"proposal_id": proposal_id, "status": "rejected"}


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


# CrmPushResult.status values that do NOT mean "the document failed to reach
# kita". `pushed` = delivered to Fly+Drive; `disabled` = push leg intentionally
# off (writer/push OFF by design); `already_delivered` = the local row already
# carries a Drive file (re-upload skipped). Every other status (`unreachable`,
# `server_error`, `denied_rbac`, `rejected`, `too_large`, `no_token`,
# `missing_blob`, `error`) means: committed in the Pro DB but ABSENT from
# kita.balizero — a divergence the operator must see.
_DELIVERY_OK_OR_NEUTRAL: frozenset[str] = frozenset(
    {"pushed", "disabled", "already_delivered"}
)

DELIVERY_FAILED_STATUS = "committed_local_delivery_failed"


def _delivery_aware_status(
    base_status: str, crm_push_info: dict[str, Any] | None
) -> str:
    """Downgrade a 'routed' approve to a delivery-failure status when the
    Pro→Fly/Drive push did not actually deliver the committed document.

    Pure function (no I/O) so it is unit-testable across the full CrmPushResult
    status space. Only rewrites the success case: a non-'routed' base status
    (e.g. 'review_claimed' for a dry-run/blocked plan) is returned untouched,
    and a missing/None push_info (delivery leg never ran) is left as-is.
    """
    if base_status != "routed" or not crm_push_info:
        return base_status
    push_status = crm_push_info.get("status")
    if push_status in _DELIVERY_OK_OR_NEUTRAL:
        return base_status
    return DELIVERY_FAILED_STATUS
