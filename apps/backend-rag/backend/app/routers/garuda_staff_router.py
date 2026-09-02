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
from dataclasses import dataclass
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from backend.app.utils.logging_utils import sanitize_for_log
from backend.services.garuda_orders import idempotency, journal
from backend.services.garuda_orders.idempotency import IdempotencyConflict
from backend.services.garuda_portal.staff_auth import require_garuda_staff

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


def _visible_or_403(row: asyncpg.Record, actor: dict[str, Any]) -> None:
    if actor["is_admin"]:
        return
    if (row["assigned_to"] or "").lower() != actor["email"]:
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "retryable": False})


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


@router.get(
    "/practices", operation_id="listStaffPractices", responses=_status_responses("listStaffPractices")
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
    _visible_or_403(row, actor)
    return _staff_practice_view(row)


@router.post(
    "/practices/{practice_id}/assignment",
    operation_id="assignPractice",
    responses=_status_responses("assignPractice"),
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


@dataclass(frozen=True, slots=True)
class _TransitionSpec:
    kind: str
    from_states: tuple[str, ...]
    to_state: str
    event_name: str
    outbox_job_type: str


_TRANSITIONS: dict[str, _TransitionSpec] = {
    "PR-02": _TransitionSpec("begin", ("Received",), "In_review", "practice.in_review", "practice_in_review_email"),
    "PR-03": _TransitionSpec("block", ("Received",), "Blocked", "practice.blocked", "practice_blocked_email"),
    "PR-05": _TransitionSpec("block", ("In_review",), "Blocked", "practice.blocked", "practice_blocked_email"),
    "PR-08": _TransitionSpec("block", ("Submitted",), "Blocked", "practice.blocked", "practice_blocked_email"),
    "PR-04": _TransitionSpec("submit", ("In_review",), "Submitted", "practice.submitted", "practice_submitted_email"),
    "PR-06": _TransitionSpec("approve", ("Submitted",), "Approved", "practice.approved", "practice_approved_email"),
    "PR-07": _TransitionSpec("reject", ("Submitted",), "Rejected", "practice.rejected", "practice_rejected_email"),
    "PR-09": _TransitionSpec("resume", ("Blocked",), "In_review", "practice.resumed", "practice_resumed_email"),
    "PR-10": _TransitionSpec("resume", ("Blocked",), "Submitted", "practice.resumed", "practice_resumed_email"),
    "PR-11": _TransitionSpec("deliver", ("Approved",), "Delivered", "practice.delivered", "practice_delivered_email"),
}

_BLOCK_RESUME_TARGET: dict[str, str] = {"PR-03": "In_review", "PR-05": "In_review", "PR-08": "Submitted"}
_RESUME_EXPECTED_TARGET: dict[str, str] = {"PR-09": "In_review", "PR-10": "Submitted"}
#: `garuda_practice_evidence.kind`'s CHECK constraint (migration 305) —
#: PR-04 files, PR-06 approves, PR-07 rejects, each with its own evidence.
_EVIDENCE_KIND_BY_TRANSITION_KIND: dict[str, str] = {
    "submit": "filing",
    "approve": "approval",
    "reject": "rejection",
}
_REASON_PATTERN = "garuda_voa.practice."
_ACTION_PATTERN = "garuda_voa.action."


def _validate_transition_body(transition_id: str, body: dict) -> dict[str, Any]:
    """PR-02..PR-11 body-shape validation, mirroring the frozen contract's
    `oneOf` discriminated on `transition_id` (`PracticeTransitionRequest`).
    Raises 422 INVALID_REQUEST on any mismatch."""

    def _fail() -> None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})

    spec = _TRANSITIONS.get(transition_id)
    if spec is None:
        _fail()

    if spec.kind == "begin":
        return {}
    if spec.kind == "block":
        reason = body.get("customer_reason_key")
        action = body.get("required_action_key")
        if (
            not isinstance(reason, str)
            or not reason.startswith(_REASON_PATTERN)
            or not isinstance(action, str)
            or not action.startswith(_ACTION_PATTERN)
        ):
            _fail()
        note = body.get("private_staff_note")
        if note is not None and (not isinstance(note, str) or len(note) > 4000):
            _fail()
        return {"customer_reason_key": reason, "required_action_key": action, "private_staff_note": note}
    if spec.kind in ("submit", "approve"):
        evidence_id = body.get("evidence_id")
        if not isinstance(evidence_id, str) or not (16 <= len(evidence_id) <= 128):
            _fail()
        return {"evidence_id": evidence_id}
    if spec.kind == "reject":
        evidence_id = body.get("evidence_id")
        reason = body.get("customer_reason_key")
        if (
            not isinstance(evidence_id, str)
            or not (16 <= len(evidence_id) <= 128)
            or not isinstance(reason, str)
            or not reason.startswith(_REASON_PATTERN)
        ):
            _fail()
        note = body.get("private_staff_note")
        if note is not None and (not isinstance(note, str) or len(note) > 4000):
            _fail()
        return {"evidence_id": evidence_id, "customer_reason_key": reason, "private_staff_note": note}
    if spec.kind == "resume":
        resolved_block_id = body.get("resolved_block_id")
        if not isinstance(resolved_block_id, str) or not (16 <= len(resolved_block_id) <= 128):
            _fail()
        return {"resolved_block_id": resolved_block_id}
    if spec.kind == "deliver":
        artifact_id = body.get("artifact_id")
        artifact_digest = body.get("artifact_digest")
        if (
            not isinstance(artifact_id, str)
            or not (16 <= len(artifact_id) <= 128)
            or not isinstance(artifact_digest, str)
            or len(artifact_digest) != 64
        ):
            _fail()
        return {"artifact_id": artifact_id, "artifact_digest": artifact_digest}
    _fail()  # pragma: no cover - unreachable, spec is None already caught above
    raise AssertionError  # pragma: no cover


@router.post(
    "/practices/{practice_id}/transitions",
    operation_id="transitionPractice",
    responses=_status_responses("transitionPractice"),
)
async def transition_practice(
    practice_id: str,
    request: Request,
    response: Response,
    body: dict,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    _privacy_headers(response)
    actor = await _require_actor(request)
    key = _idempotency_key(idempotency_key)

    transition_id = body.get("transition_id")
    if not isinstance(transition_id, str) or transition_id not in _TRANSITIONS:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})
    fields = _validate_transition_body(transition_id, body)
    spec = _TRANSITIONS[transition_id]

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

        async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT practice_id, order_id, state, assigned_to, resume_target,
                           customer_reason_key, required_action_key, artifact_available,
                           active_block_id
                      FROM garuda_practices WHERE practice_id = $1 FOR UPDATE
                    """,
                    practice_id,
                )
                if row is None:
                    raise HTTPException(
                        status_code=404, detail={"code": "PRACTICE_NOT_FOUND", "retryable": False}
                    )
                _visible_or_403(row, actor)

                if row["state"] not in spec.from_states:
                    raise HTTPException(
                        status_code=409,
                        detail={"code": "INVALID_STATE_TRANSITION", "retryable": False},
                    )
                if spec.kind == "resume" and row["resume_target"] != _RESUME_EXPECTED_TARGET[
                    transition_id
                ]:
                    raise HTTPException(
                        status_code=409,
                        detail={"code": "INVALID_STATE_TRANSITION", "retryable": False},
                    )
                # Round-2 disposition item B: `resume_target` above only
                # proves the FROM/TO state pairing is legal (PR-09 resumes
                # to In_review, PR-10 to Submitted) -- it says nothing about
                # WHICH block the staff caller believes they are resolving.
                # `active_block_id` (the journal event_id set below when the
                # matching PR-03/05/08 ran) is the identity check: a staff
                # caller resolving a stale/unrelated block reference gets
                # 422 INVALID_REQUEST, never silently resumes the CURRENT
                # block under a mismatched reference.
                if spec.kind == "resume" and fields["resolved_block_id"] != row["active_block_id"]:
                    raise HTTPException(
                        status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False}
                    )
                # PR-04/06/07: an evidence_id already bound to a DIFFERENT
                # practice is a client-side mistake (evidence identifiers
                # are meant to be practice-scoped), not a genuine conflict
                # worth 409 -- disposition item B calls this out explicitly
                # as 422 INVALID_REQUEST. A replay of the SAME
                # (practice_id, evidence_id) pair is handled by the
                # INSERT ... ON CONFLICT DO NOTHING below, not here.
                if spec.kind in ("submit", "approve", "reject"):
                    other_owner = await conn.fetchval(
                        """
                        SELECT practice_id FROM garuda_practice_evidence
                         WHERE evidence_id = $1 AND practice_id != $2
                         LIMIT 1
                        """,
                        fields["evidence_id"],
                        practice_id,
                    )
                    if other_owner is not None:
                        raise HTTPException(
                            status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False}
                        )

                # $1=practice_id, $2=to_state, $3=allowed-source-states array
                # (the WHERE-clause CAS guard). Every SET-clause value past
                # those three is numbered by `_add`, in the exact order it
                # is appended to `params` — never computed from `len(params)`
                # before the $3 array reservation, which was this block's
                # first-draft bug (a $3/$4 off-by-one that bound the array
                # where a real column value belonged).
                set_clauses = ["state = $2"]
                params: list[Any] = [practice_id, spec.to_state, list(spec.from_states)]

                def _add(column: str, value: Any) -> None:
                    params.append(value)
                    set_clauses.append(f"{column} = ${len(params)}")

                if spec.kind == "block":
                    _add("customer_reason_key", fields["customer_reason_key"])
                    _add("required_action_key", fields["required_action_key"])
                    _add("private_staff_note", fields["private_staff_note"])
                    _add("resume_target", _BLOCK_RESUME_TARGET[transition_id])
                elif spec.kind == "reject":
                    _add("customer_reason_key", fields["customer_reason_key"])
                    _add("private_staff_note", fields["private_staff_note"])
                elif spec.kind == "resume":
                    set_clauses += [
                        "resume_target = NULL",
                        "customer_reason_key = NULL",
                        "required_action_key = NULL",
                        "private_staff_note = NULL",
                        "active_block_id = NULL",
                    ]
                elif spec.kind == "deliver":
                    _add("artifact_id", fields["artifact_id"])
                    _add("artifact_digest", fields["artifact_digest"])
                    set_clauses.append("artifact_available = TRUE")

                updated = await conn.fetchrow(
                    f"""
                    UPDATE garuda_practices SET {', '.join(set_clauses)}
                     WHERE practice_id = $1 AND state = ANY($3::text[])
                     RETURNING practice_id, state, customer_reason_key, required_action_key,
                               artifact_available
                    """,
                    *params,
                )
                if updated is None:  # pragma: no cover - defensive, FOR UPDATE prevents this
                    raise HTTPException(
                        status_code=409,
                        detail={"code": "INVALID_STATE_TRANSITION", "retryable": False},
                    )

                event_id = await journal.append_event(
                    conn,
                    event_name=spec.event_name,
                    aggregate_type="practice",
                    aggregate_id=practice_id,
                    transition_id=transition_id,
                    customer_visible=True,
                    idempotency_key_digest=key_digest,
                    canonical_payload_digest=payload_digest,
                    detail={k: v for k, v in fields.items() if k != "private_staff_note"},
                )
                await journal.enqueue_outbox(
                    conn,
                    order_id=row["order_id"],
                    journal_event_id=event_id,
                    job_type=spec.outbox_job_type,
                )

                # Round-2 disposition item B: `active_block_id` = this
                # journal event's own id -- only knowable AFTER
                # `append_event` returns, hence a follow-up UPDATE rather
                # than a value in the CAS UPDATE above. Same transaction,
                # same row-level lock already held by the FOR UPDATE select.
                if spec.kind == "block":
                    await conn.execute(
                        "UPDATE garuda_practices SET active_block_id = $2 WHERE practice_id = $1",
                        practice_id,
                        event_id,
                    )

                # PR-04/06/07: bind the evidence to this practice AND this
                # transition, in the same transaction as the CAS UPDATE
                # (disposition item #8). `ON CONFLICT DO NOTHING` makes an
                # exact idempotent replay of the same command a no-op here
                # too -- the outer `idempotency.reserve`/`complete` pair
                # already short-circuits a replay before this code runs,
                # so this is defense-in-depth, not the primary guard.
                if spec.kind in ("submit", "approve", "reject"):
                    await conn.execute(
                        """
                        INSERT INTO garuda_practice_evidence
                            (practice_id, transition_id, evidence_id, kind, recorded_by)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (practice_id, evidence_id) DO NOTHING
                        """,
                        practice_id,
                        transition_id,
                        fields["evidence_id"],
                        _EVIDENCE_KIND_BY_TRANSITION_KIND[spec.kind],
                        actor["email"],
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
