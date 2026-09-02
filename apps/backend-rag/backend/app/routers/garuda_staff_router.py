"""GARUDA VOA — step 8 staff surface (`products/garuda-voa/journeys/
STATE-MACHINE.md` rows PR-02..PR-11).

Closes the gap `services/garuda_portal/practice.py`'s own module docstring
names: "nothing can move a practice past `Received`". This router owns the
staff-only read/write surface on `garuda_practices` — `garuda_orders_
router.py::get_order_and_practice` remains the CUSTOMER-facing read (L3,
unchanged by this file, LANES.md file-ownership).

Auth: `require_garuda_staff` (`services/garuda_portal/staff_auth.py`)
resolves EITHER the `kita.balizero.com` cookie session (`request.state.
user`, set by `HybridAuthMiddleware`) OR a bearer CRM JWT — never a
customer magic-link session (`garuda_session` cookie), which
`require_garuda_staff` never reads. Visibility: an admin (`crm_utils.
is_crm_admin`) sees every practice; a non-admin CRM team member sees only
`assigned_to = actor`.

Idempotency + journal + outbox: reuses `garuda_orders.idempotency`
(`reserve`/`complete`, keyed by `key_sha256` alone — no `order_id` binding,
since a practice command is not an order command) and
`garuda_orders.journal` (`append_event`/`enqueue_outbox`) exactly as
`repository.py::resolve_late_order` does — no new idempotency/journal
primitive is introduced here (STEP8-SPEC point on reuse).

Error envelope: mirrors `garuda_orders_router.py`'s own
`_ContractErrorRoute` + `_ERROR_CATALOG` + `_error()` pattern (STEP8-SPEC:
"reuse the L3 helpers (PR #5300)") — a same-shaped LOCAL copy, not a shared
import, per LANES.md file-ownership discipline (the same convention
`garuda_voa_public.py`'s own `_ContractErrorRoute` docstring names).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from backend.app.utils.logging_utils import sanitize_for_log
from backend.services.garuda_orders import idempotency
from backend.services.garuda_orders.idempotency import IdempotencyConflict
from backend.services.garuda_portal.staff_auth import (
    is_valid_garuda_assignment_target,
    require_garuda_staff,
)
from backend.services.garuda_portal.staff_transitions import (
    TRANSITIONS,
    apply_transition,
    validate_transition_body,
    visible_or_403,
)

logger = logging.getLogger(__name__)

_FLAG_ENV_VAR = "GARUDA_PUBLIC_ENABLED"


def _flag_enabled() -> bool:
    # Same permissive reader as garuda_orders_router.py / garuda_voa_public.py
    # / garuda_portal_auth.py — pinned identical by
    # test_garuda_public_enabled_readers_agree.py.
    return os.environ.get(_FLAG_ENV_VAR, "").strip().lower() in {"1", "true", "yes"}


def _require_flag() -> None:
    if not _flag_enabled():
        raise HTTPException(
            status_code=404, detail={"code": "GARUDA_PUBLIC_DISABLED", "retryable": False}
        )


class _ContractErrorRoute(APIRoute):
    """Local copy of `garuda_orders_router.py`'s route class — see that
    file's docstring for the full ordering argument (router-level
    dependency resolution happens before body validation, and an
    `HTTPException` raised anywhere in that chain reaches this route's own
    dispatch before Starlette's global exception middleware)."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        downstream = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await downstream(request)
            except HTTPException as exc:
                code = exc.detail.get("code") if isinstance(exc.detail, dict) else None
                if code not in _ERROR_CATALOG:
                    raise
                return _error(code)

        return handler


router = APIRouter(
    prefix="/api/visa/voa/staff",
    tags=["Staff practice"],
    route_class=_ContractErrorRoute,
    dependencies=[Depends(_require_flag)],
)


def _privacy_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"


#: `products/garuda-voa/contracts/errors.yaml` — verbatim copy of each
#: code's (http_status, retryable, message_key), restricted to what this
#: router's own call sites can produce. Same discipline as
#: `garuda_orders_router.py::_ERROR_CATALOG`.
_ERROR_CATALOG: dict[str, tuple[int, bool, str]] = {
    "GARUDA_PUBLIC_DISABLED": (404, False, "garuda_voa.error.unavailable"),
    "SERVICE_UNAVAILABLE": (503, True, "garuda_voa.error.service_unavailable"),
    "SESSION_REQUIRED": (401, False, "garuda_voa.error.session_required"),
    "ACCESS_DENIED": (403, False, "garuda_voa.error.access_denied"),
    "IDEMPOTENCY_KEY_REQUIRED": (400, False, "garuda_voa.error.idempotency_key_required"),
    "IDEMPOTENCY_CONFLICT": (409, False, "garuda_voa.error.idempotency_conflict"),
    "INVALID_REQUEST": (422, False, "garuda_voa.error.invalid_request"),
    "PRACTICE_NOT_FOUND": (404, False, "garuda_voa.error.practice_not_found"),
    "INVALID_STATE_TRANSITION": (409, False, "garuda_voa.error.invalid_state_transition"),
}


def _error(code: str) -> JSONResponse:
    status_code, retryable, message_key = _ERROR_CATALOG[code]
    response = JSONResponse(
        status_code=status_code,
        content={"code": code, "retryable": retryable, "message_key": message_key},
    )
    _privacy_headers(response)
    return response


def get_pool(request: Request) -> asyncpg.Pool:
    """Same shared pool `garuda_orders_router.py::get_order_and_practice`
    reads as `app.state.garuda_db_pool` — a domain-named alias, not a
    second `create_pool()` (see that router's own comment)."""

    pool = getattr(request.app.state, "garuda_db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503, detail={"code": "SERVICE_UNAVAILABLE", "retryable": True}
        )
    return pool


async def _require_actor(request: Request) -> dict[str, Any]:
    actor = await require_garuda_staff(request)
    if actor is None:
        raise HTTPException(
            status_code=401, detail={"code": "SESSION_REQUIRED", "retryable": False}
        )
    return actor


def _idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or len(idempotency_key) < 16 or len(idempotency_key) > 200:
        raise HTTPException(
            status_code=400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "retryable": False}
        )
    return idempotency_key


_DB_TO_WIRE_STATE: dict[str, str] = {
    "Received": "Received",
    "In_review": "In review",
    "Blocked": "Blocked",
    "Submitted": "Submitted",
    "Approved": "Approved",
    "Rejected": "Rejected",
    "Delivered": "Delivered",
}


def _practice_view(row: asyncpg.Record) -> dict[str, Any]:
    """Mirrors `PracticeView` (contract) exactly — customer/public shape,
    reused here as the transitionPractice response body per the frozen
    contract. NEVER includes `private_staff_note`/`resume_target`/
    `assigned_to` (PR-F04)."""

    body: dict[str, Any] = {
        "practice_id": row["practice_id"],
        "state": _DB_TO_WIRE_STATE[row["state"]],
        "artifact_available": row["artifact_available"],
    }
    if row["customer_reason_key"] is not None:
        body["customer_reason_key"] = row["customer_reason_key"]
    if row["required_action_key"] is not None:
        body["required_action_key"] = row["required_action_key"]
    return body


def _list_row_view(row: asyncpg.Record) -> dict[str, Any]:
    """`listStaffPractices` row shape — STEP8-SPEC point 3: NO customer
    PII, NO `private_staff_note`."""

    return {
        "practice_id": row["practice_id"],
        "order_id": row["order_id"],
        "state": _DB_TO_WIRE_STATE[row["state"]],
        "assigned_to": row["assigned_to"],
        "updated_at": row["updated_at"].isoformat(),
        "customer_reason_key": row["customer_reason_key"],
        "required_action_key": row["required_action_key"],
        "artifact_available": row["artifact_available"],
    }


def _staff_practice_view(row: asyncpg.Record) -> dict[str, Any]:
    """`getStaffPractice` shape — `StaffPracticeView`, staff-only, never
    reused by a customer route (STEP8-SPEC point 3). Round-2 disposition
    (item B): also exposes `active_block_id`/`artifact_id`/`artifact_digest`
    — `assigned_to` was already carried by `_list_row_view`."""

    body = _list_row_view(row)
    body["private_staff_note"] = row["private_staff_note"]
    body["resume_target"] = (
        _DB_TO_WIRE_STATE[row["resume_target"]] if row["resume_target"] is not None else None
    )
    body["active_block_id"] = row["active_block_id"]
    body["artifact_id"] = row["artifact_id"]
    body["artifact_digest"] = row["artifact_digest"]
    return body


#: Status codes each operation's own call sites (plus the router-level
#: `_require_flag` dependency) can genuinely produce — same discipline as
#: `garuda_orders_router.py::_OPERATION_STATUS_CODES` /`_status_responses`,
#: mirrored here so `test_garuda_voa_openapi_parity.py` sees a live schema
#: that matches what `openapi.yaml` declares for these four operations
#: byte-for-byte (no gap needs `_KNOWN_STATUS_CODE_GAPS`).
_OPERATION_STATUS_CODES: dict[str, tuple[int, ...]] = {
    "listStaffPractices": (401, 404, 500, 503),
    "getStaffPractice": (401, 403, 404, 500, 503),
    "assignPractice": (400, 401, 403, 404, 422, 500, 503),
    "transitionPractice": (400, 401, 403, 404, 409, 422, 500, 503),
}


def _status_responses(operation_id: str) -> dict[int, dict[str, object]]:
    return {
        status_code: {"description": "See `products/garuda-voa/contracts/errors.yaml`."}
        for status_code in _OPERATION_STATUS_CODES[operation_id]
    }


#: FastAPI never infers a `security` block for a hand-rolled `Authorization`
#: header read via `require_garuda_staff`/`_require_actor` -- there is no
#: `fastapi.security.*` dependency in this router for it to introspect, so
#: the live generated schema had `"security": None` for all four operations
#: until this constant started being merged in via `openapi_extra` below.
#: `deep_dict_update` (FastAPI's own `openapi_extra` merge) sets this key
#: cleanly since nothing else in the generated operation touches it.
_STAFF_SESSION_SECURITY: dict[str, object] = {"security": [{"StaffSession": []}]}


@router.get(
    "/practices",
    operation_id="listStaffPractices",
    responses=_status_responses("listStaffPractices"),
    openapi_extra=_STAFF_SESSION_SECURITY,
)
async def list_staff_practices(
    request: Request,
    response: Response,
    state: str | None = None,
    assigned: str = "all",
    cursor: str | None = None,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """Admin sees all; non-admin sees only `assigned_to = actor`
    regardless of the `assigned` query param — `assigned=me` is a
    convenience filter for an admin, never a way for a non-admin to widen
    their own visibility."""

    _privacy_headers(response)
    actor = await _require_actor(request)

    conditions: list[str] = []
    params: list[Any] = []

    def _param(value: Any) -> str:
        params.append(value)
        return f"${len(params)}"

    if not actor["is_admin"]:
        conditions.append(f"assigned_to = {_param(actor['email'])}")
    elif assigned == "me":
        conditions.append(f"assigned_to = {_param(actor['email'])}")

    if state is not None:
        db_state = {v: k for k, v in _DB_TO_WIRE_STATE.items()}.get(state, state)
        conditions.append(f"state = {_param(db_state)}")

    if cursor is not None:
        conditions.append(f"practice_id > {_param(cursor)}")

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT practice_id, order_id, state, assigned_to, updated_at,
               customer_reason_key, required_action_key, artifact_available
          FROM garuda_practices
          {where_sql}
         ORDER BY practice_id ASC
         LIMIT 50
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    items = [_list_row_view(row) for row in rows]
    next_cursor = items[-1]["practice_id"] if len(items) == 50 else None
    return {"items": items, "next_cursor": next_cursor}


@router.get(
    "/practices/{practice_id}",
    operation_id="getStaffPractice",
    responses=_status_responses("getStaffPractice"),
    openapi_extra=_STAFF_SESSION_SECURITY,
)
async def get_staff_practice(
    practice_id: str,
    request: Request,
    response: Response,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    _privacy_headers(response)
    actor = await _require_actor(request)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT practice_id, order_id, state, assigned_to, updated_at,
                   customer_reason_key, required_action_key, artifact_available,
                   private_staff_note, resume_target, active_block_id,
                   artifact_id, artifact_digest
              FROM garuda_practices WHERE practice_id = $1
            """,
            practice_id,
        )
    if row is None:
        raise HTTPException(
            status_code=404, detail={"code": "PRACTICE_NOT_FOUND", "retryable": False}
        )
    visible_or_403(row, actor)
    return _staff_practice_view(row)


@router.post(
    "/practices/{practice_id}/assignment",
    operation_id="assignPractice",
    responses=_status_responses("assignPractice"),
    openapi_extra=_STAFF_SESSION_SECURITY,
)
async def assign_practice(
    practice_id: str,
    request: Request,
    response: Response,
    body: dict,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """Admin only. `body.assigned_to` is either a staff email or `null`
    (unassign)."""

    _privacy_headers(response)
    actor = await _require_actor(request)
    if not actor["is_admin"]:
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "retryable": False})
    key = _idempotency_key(idempotency_key)

    # Cross-family refuter (Gemini) MAJOR finding #2: `body.get("assigned_to")`
    # cannot tell an OMITTED key from an explicit `{"assigned_to": null}` --
    # both evaluate to `None`. The contract's `PracticeAssignmentRequest`
    # requires the key; only an explicit null means "unassign".
    if "assigned_to" not in body:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})
    assigned_to_raw = body.get("assigned_to")
    if assigned_to_raw is not None and not isinstance(assigned_to_raw, str):
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})
    assigned_to = assigned_to_raw.strip().lower() if assigned_to_raw else None

    # Round-2 disposition item F: same idempotency.reserve/complete pair as
    # transitionPractice — assignPractice previously only validated the
    # HEADER's shape (`_idempotency_key`) without ever reserving the key,
    # so a retried assignment (e.g. a client timeout-and-retry) could
    # silently re-run the UPDATE and clobber a concurrent hand-off with no
    # replay protection at all.
    key_digest = idempotency.scoped_key_sha256(
        actor=actor["email"], operation="assignPractice", raw_key=key
    )
    payload_digest = idempotency.canonical_payload_sha256(
        {"practice_id": practice_id, "assigned_to": assigned_to}
    )

    async with pool.acquire() as conn:
        # Round-4 disposition item 2 (Codex finding #2): the ASSIGNMENT
        # TARGET must itself be a real GARUDA operator (admin OR an active
        # team_members row with a staff role) -- checked BEFORE reserving
        # the idempotency key, so an invalid target never burns a key slot.
        if assigned_to is not None and not await is_valid_garuda_assignment_target(
            conn, assigned_to
        ):
            raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})
        try:
            outcome = await idempotency.reserve(
                conn, key_sha256=key_digest, payload_sha256=payload_digest
            )
        except IdempotencyConflict as exc:
            raise HTTPException(
                status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "retryable": False}
            ) from exc
        if outcome.replayed:
            assert outcome.response_body is not None
            response.headers["Idempotency-Replayed"] = "true"
            return outcome.response_body

        # Cross-family refuter (Codex) MAJOR finding #5: `idempotency.
        # complete()` used to run as a SEPARATE statement AFTER this
        # `async with conn.transaction():` block had already committed --
        # a crash between the two left the business write committed but the
        # idempotency row permanently "reserved, never completed", so a
        # retry re-ran the UPDATE and got a spurious conflict instead of the
        # committed outcome. Completion now runs INSIDE the same
        # transaction: either both commit, or neither does.
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE garuda_practices
                   SET assigned_to = $2::text,
                       assigned_at = CASE WHEN $2::text IS NULL THEN NULL ELSE statement_timestamp() END,
                       assigned_by = CASE WHEN $2::text IS NULL THEN NULL ELSE $3::text END
                 WHERE practice_id = $1
                 RETURNING practice_id, order_id, state, assigned_to, updated_at,
                           customer_reason_key, required_action_key, artifact_available
                """,
                practice_id,
                assigned_to,
                actor["email"],
            )
            if row is None:
                raise HTTPException(
                    status_code=404, detail={"code": "PRACTICE_NOT_FOUND", "retryable": False}
                )
            response_body = _list_row_view(row)
            await idempotency.complete(
                conn, key_sha256=key_digest, response_status=200, response_body=response_body
            )
    logger.info(
        "garuda_staff.practice_assigned",
        extra={
            "practice_id": sanitize_for_log(practice_id),
            "assigned_to": sanitize_for_log(assigned_to or "none"),
        },
    )
    return response_body


#: `deep_dict_update` merges nested dicts key-by-key rather than replacing
#: them wholesale, so adding `responses.200.headers` here does not disturb
#: FastAPI's own auto-generated `200.description`/`200.content` for this
#: operation's return type -- only transitionPractice's 200 declares
#: `Idempotency-Replayed` in the frozen contract (assignPractice's 200 does
#: not, even though the router sets the same header on an assignPractice
#: replay too — a pre-existing contract/behavior gap this file does not
#: introduce or fix).
_TRANSITION_OPENAPI_EXTRA: dict[str, object] = {
    **_STAFF_SESSION_SECURITY,
    "responses": {
        "200": {
            "headers": {
                "Idempotency-Replayed": {
                    "description": "\"true\" on an exact command replay, absent otherwise.",
                    "schema": {"type": "string", "enum": ["true"]},
                }
            }
        }
    },
}


@router.post(
    "/practices/{practice_id}/transitions",
    operation_id="transitionPractice",
    responses=_status_responses("transitionPractice"),
    openapi_extra=_TRANSITION_OPENAPI_EXTRA,
)
async def transition_practice(
    practice_id: str,
    request: Request,
    response: Response,
    body: dict,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """Thin HTTP-shape layer (round-3 disposition item E): body parsing,
    idempotency reserve/complete and the contract's error mapping live here;
    the guarded UPDATE, evidence write, journal append and outbox enqueue
    live in `services/garuda_portal/staff_transitions.py::apply_transition`,
    which this handler calls INSIDE the same transaction/idempotency
    envelope `resolve_late_order` uses (STEP8-SPEC point on reuse)."""

    _privacy_headers(response)
    actor = await _require_actor(request)
    key = _idempotency_key(idempotency_key)

    transition_id = body.get("transition_id")
    if not isinstance(transition_id, str) or transition_id not in TRANSITIONS:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})
    fields = validate_transition_body(transition_id, body)

    key_digest = idempotency.scoped_key_sha256(
        actor=actor["email"], operation="transitionPractice", raw_key=key
    )
    payload_digest = idempotency.canonical_payload_sha256(
        {"practice_id": practice_id, "transition_id": transition_id, **fields}
    )

    async with pool.acquire() as conn:
        try:
            outcome = await idempotency.reserve(
                conn, key_sha256=key_digest, payload_sha256=payload_digest
            )
        except IdempotencyConflict as exc:
            raise HTTPException(
                status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "retryable": False}
            ) from exc
        if outcome.replayed:
            assert outcome.response_body is not None
            response.headers["Idempotency-Replayed"] = "true"
            return outcome.response_body

        # Cross-family refuter (Codex) MAJOR finding #5: same atomicity fix
        # as assign_practice above -- idempotency completion now runs
        # INSIDE the same transaction as apply_transition's state/journal/
        # outbox writes, so a crash between them can never leave a
        # committed business effect with a permanently-unresolved
        # idempotency reservation.
        async with conn.transaction():
            updated = await apply_transition(
                conn,
                practice_id=practice_id,
                transition_id=transition_id,
                actor=actor,
                fields=fields,
                key_digest=key_digest,
                payload_digest=payload_digest,
            )
            response_body = _practice_view(updated)
            await idempotency.complete(
                conn, key_sha256=key_digest, response_status=200, response_body=response_body
            )
    logger.info(
        "garuda_staff.practice_transitioned",
        extra={
            "practice_id": sanitize_for_log(practice_id),
            "transition_id": sanitize_for_log(transition_id),
        },
    )
    return response_body


__all__ = ["router"]
