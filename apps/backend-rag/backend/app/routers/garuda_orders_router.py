"""HTTP shell for GARUDA VOA L3 — checkout + orders.

Implements exactly the operations `products/garuda-voa/LANES.md` scopes to
L3: `createOrderFromCheck`, `getOrderAndPractice` (order half only — the
`practice` field is served null here until L4/L7 wire their part),
`observePaymentBrowserReturn`, `receivePaymentWebhook`, `resolveLateOrder`.

Registered in `router_manifest.py` / `router_registration.py` (_API, mirrors
L2's `garuda_voa_public` — mount unconditionally, GARUDA_PUBLIC_ENABLED
re-checked per-request by this module's own `_require_flag`). The orchestrator
still owns injecting the real `EligibilityCheckLookup` / `PaymentProvider`
adapters onto `app.state` at composition time — `get_repository()` above
fails closed with 503 until that happens.
"""

from __future__ import annotations

import hashlib
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from backend.services.garuda_orders.errors import (
    NoOpenLateCase,
    OrderNotFound,
    OrderNotReady,
    PaymentProviderUnavailable,
    PersistencePolicyUnavailable,
    PriceUnresolvable,
    ResultNotFound,
)
from backend.services.garuda_orders.idempotency import (
    IdempotencyConflict,
    canonical_payload_sha256,
    scoped_key_sha256,
)
from backend.services.garuda_orders.models import Applicant
from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.payments.port import WebhookSignatureInvalid, WebhookUnparseable

router = APIRouter(prefix="/api/visa/voa", tags=["garuda-orders"])

_FLAG_ENV_VAR = "GARUDA_PUBLIC_ENABLED"


def _flag_enabled() -> bool:
    return os.environ.get(_FLAG_ENV_VAR, "false").lower() == "true"


def _require_flag() -> None:
    if not _flag_enabled():
        raise HTTPException(
            status_code=404, detail={"code": "GARUDA_PUBLIC_DISABLED", "retryable": False}
        )


def _privacy_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"


def get_repository(request: Request) -> GarudaOrderRepository:
    """Orchestrator wires the real instance onto `app.state.garuda_order_repository`."""

    repo = getattr(request.app.state, "garuda_order_repository", None)
    if repo is None:
        raise HTTPException(
            status_code=503, detail={"code": "SERVICE_UNAVAILABLE", "retryable": True}
        )
    return repo


async def _require_magic_session_actor(request: Request) -> str:
    """Seam for L4's magic-link session (LANES.md: L4 owns auth).

    Until the orchestrator wires L4's real session verifier onto
    `app.state.garuda_magic_session_verifier`, this fails closed with
    SESSION_REQUIRED rather than accepting an unverified cookie value —
    the same "no caller wired yet, never a silent bypass" shape as
    `UnconfiguredEligibilityCheckLookup` / `UnconfiguredCheckStore`.

    The verifier is `async` — a real (Postgres-backed) implementation
    needs an `await` to look up the session row, and this dependency
    itself is a plain `async def` FastAPI already knows how to await, so
    there is no reason to force the verifier callable to be synchronous.

    The returned value is the session's `result_id`, used by every caller
    for TWO purposes: (1) the `actor` identity `scoped_key_sha256` scopes
    idempotency keys by, and (2) the ownership key every `garuda_orders`
    read/write below must filter on (`garuda_orders.result_id_ref`). See
    `PostgresMagicLinkStore.verify_session`'s docstring for why one string
    correctly carries both — they are the same fact, not two smuggled into
    one field.
    """

    verifier = getattr(request.app.state, "garuda_magic_session_verifier", None)
    cookie = request.cookies.get("garuda_session")
    if verifier is None or not cookie:
        raise HTTPException(
            status_code=401, detail={"code": "SESSION_REQUIRED", "retryable": False}
        )
    actor = await verifier(cookie)
    if actor is None:
        raise HTTPException(
            status_code=401, detail={"code": "SESSION_REQUIRED", "retryable": False}
        )
    return actor


async def _require_staff_actor(request: Request, authorization: str | None) -> str:
    """Twin of `_require_magic_session_actor` for the staff late-resolution
    route — same shape, deliberately kept `async def` even though
    `garuda_staff_session_verifier` is wired nowhere today.

    Converting this at the SAME time the slot gets wired (rather than now,
    while it is inert) is precisely the moment this class of bug gets
    introduced: `verifier(authorization)` on an async verifier returns a
    coroutine object, not `None` — `if actor is None` is False, the coroutine
    is never awaited, and the request proceeds AUTHENTICATED for any
    non-empty `Authorization` header. No exception is raised; the only trace
    is a `RuntimeWarning: coroutine ... was never awaited` in logs, easy to
    miss. Keeping this function's signature identical to its sibling now,
    while the verifier is still `None` (a no-op change — both versions 401
    today), removes that landmine before anyone is under the pressure of
    wiring a real verifier and can make the mistake live.
    """
    verifier = getattr(request.app.state, "garuda_staff_session_verifier", None)
    if verifier is None or not authorization:
        raise HTTPException(
            status_code=401, detail={"code": "SESSION_REQUIRED", "retryable": False}
        )
    actor = await verifier(authorization)
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


@router.post("/orders", status_code=201)
async def create_order_from_check(
    request: Request,
    response: Response,
    body: dict,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    repository: GarudaOrderRepository = Depends(get_repository),
) -> dict:
    _require_flag()
    _privacy_headers(response)
    actor = await _require_magic_session_actor(request)
    key = _idempotency_key(idempotency_key)

    result_id = body.get("result_id")
    applicant_raw = body.get("applicant") or {}
    review_confirmed = body.get("review_confirmed")
    if not isinstance(result_id, str) or review_confirmed is not True:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})
    if result_id != actor:
        # `actor` IS the session's result_id (see `_require_magic_session_
        # actor`'s docstring) -- a body result_id that doesn't match it is
        # a session for result A trying to create an order against result
        # B. Same 404 RESULT_NOT_FOUND shape `ResultNotFound` already maps
        # to below, deliberately: `ResultNotFound`'s own docstring already
        # names "non-owned source check" as one of the cases it covers, so
        # this is not a new error shape, just a new place that raises it —
        # and it keeps "wrong owner" and "no such result" indistinguishable
        # to the caller, closing the enumeration oracle a distinct status
        # code would open.
        raise HTTPException(status_code=404, detail={"code": "RESULT_NOT_FOUND", "retryable": False})
    try:
        applicant = Applicant(
            full_name=applicant_raw["full_name"],
            email=applicant_raw["email"],
            phone=applicant_raw["phone"],
            passport_number=applicant_raw["passport_number"],
        )
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False}
        ) from exc

    key_digest = scoped_key_sha256(actor=actor, operation="createOrderFromCheck", raw_key=key)
    payload_digest = canonical_payload_sha256({"result_id": result_id, "applicant": applicant_raw})

    try:
        body_out, replayed = await repository.create_order_and_checkout(
            result_id=result_id,
            applicant=applicant,
            review_confirmed=True,
            idempotency_key_sha256=key_digest,
            canonical_payload_sha256=payload_digest,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(
            status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "retryable": False}
        ) from exc
    except ResultNotFound as exc:
        raise HTTPException(
            status_code=404, detail={"code": "RESULT_NOT_FOUND", "retryable": False}
        ) from exc
    except OrderNotReady as exc:
        raise HTTPException(
            status_code=409, detail={"code": "ORDER_NOT_READY", "retryable": False}
        ) from exc
    except PersistencePolicyUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "PERSISTENCE_POLICY_UNAVAILABLE", "retryable": False}
        ) from exc
    except PriceUnresolvable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "PRICE_UNRESOLVABLE", "retryable": False}
        ) from exc
    except PaymentProviderUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "PAYMENT_PROVIDER_UNAVAILABLE", "retryable": True}
        ) from exc

    if replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return body_out


@router.get("/orders/{order_id}")
async def get_order_and_practice(
    order_id: str,
    request: Request,
    response: Response,
    repository: GarudaOrderRepository = Depends(get_repository),
) -> dict:
    _require_flag()
    _privacy_headers(response)
    actor = await _require_magic_session_actor(request)
    pool = getattr(request.app.state, "garuda_db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503, detail={"code": "SERVICE_UNAVAILABLE", "retryable": True}
        )
    # `result_id_ref = $2` is the ownership predicate: an order that exists
    # but belongs to a different session's result_id must 404 exactly like
    # an order that doesn't exist at all (`OrderNotFound`'s own docstring
    # already calls this shape "non-enumerating") -- a distinct status code
    # for "exists but not yours" is the enumeration oracle this closes.
    row = await pool.fetchrow(
        "SELECT order_id, state, price_idr, browser_observation "
        "FROM garuda_orders WHERE order_id = $1 AND result_id_ref = $2",
        order_id,
        actor,
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "retryable": False})
    return {
        "order_id": row["order_id"],
        "order_state": row["state"],
        "price_idr": row["price_idr"],
        "browser_observation": row["browser_observation"],
        # Practice is L4/L7 territory — served null here rather than guessed.
        "practice": None,
    }


@router.post("/orders/{order_id}/browser-return-observations", status_code=204)
async def observe_payment_browser_return(
    order_id: str,
    request: Request,
    response: Response,
    body: dict,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    repository: GarudaOrderRepository = Depends(get_repository),
) -> None:
    _require_flag()
    _privacy_headers(response)
    actor = await _require_magic_session_actor(request)
    _idempotency_key(idempotency_key)
    return_nonce = body.get("return_nonce")
    if not isinstance(return_nonce, str) or not (16 <= len(return_nonce) <= 2048):
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})
    try:
        await repository.record_browser_return_observation(
            order_id=order_id, result_id=actor, return_nonce=return_nonce
        )
    except OrderNotFound as exc:
        raise HTTPException(
            status_code=404, detail={"code": "ORDER_NOT_FOUND", "retryable": False}
        ) from exc


@router.post("/webhooks/payment", status_code=204)
async def receive_payment_webhook(
    request: Request,
    response: Response,
    repository: GarudaOrderRepository = Depends(get_repository),
) -> None:
    # CORRECTED (gate finding): this path was requiring an Idempotency-Key
    # header, per the frozen contract's `$ref` on this operation. Xendit
    # Invoices callbacks authenticate with a static `x-callback-token`
    # (xendit.py:9-13, verify_signature below) -- Xendit has no reason to
    # send `Idempotency-Key`, that header is a request-idempotency pattern
    # for commands WE issue, never for an inbound provider callback. In
    # production the route 400'd before signature verification ran,
    # handle_paid_event never fired, and the order sat in awaiting_payment
    # forever while OP-04 reconciliation saw the real charge and only
    # logged a warning (repository.py, no page). The contract's own
    # `$ref` here is the orchestrator's fix (frozen contract, not this
    # lane's to edit) -- this router-side removal is the corresponding fix
    # on the implementation.
    _require_flag()
    _privacy_headers(response)
    raw_body = await request.body()
    provider = getattr(request.app.state, "garuda_payment_provider", None)
    if provider is None:
        raise HTTPException(
            status_code=503, detail={"code": "SERVICE_UNAVAILABLE", "retryable": True}
        )

    try:
        provider.verify_signature(raw_body=raw_body, headers=dict(request.headers))
    except WebhookSignatureInvalid as exc:
        raise HTTPException(
            status_code=401, detail={"code": "WEBHOOK_SIGNATURE_INVALID", "retryable": False}
        ) from exc

    try:
        event = provider.parse_event(raw_body=raw_body, headers=dict(request.headers))
    except WebhookUnparseable as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False}
        ) from exc

    digest = hashlib.sha256(raw_body).digest()
    from backend.services.payments.port import (
        NormalizedFailureEvent,
        NormalizedPaidEvent,
        NormalizedRefundEvent,
    )

    if isinstance(event, NormalizedPaidEvent):
        await repository.handle_paid_event(event, canonical_payload_sha256=digest)
    elif isinstance(event, NormalizedFailureEvent):
        await repository.handle_failure_event(event, canonical_payload_sha256=digest)
    elif isinstance(event, NormalizedRefundEvent):
        await repository.handle_refund_event(event, canonical_payload_sha256=digest)


@router.post("/staff/orders/{order_id}/late-resolution")
async def resolve_late_order(
    order_id: str,
    request: Request,
    response: Response,
    body: dict,
    authorization: str | None = Header(None),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    repository: GarudaOrderRepository = Depends(get_repository),
) -> dict:
    _require_flag()
    _privacy_headers(response)
    actor = await _require_staff_actor(request, authorization)
    key = _idempotency_key(idempotency_key)

    resolution = body.get("resolution")
    staff_reference = body.get("staff_reference")
    if resolution not in ("honoured", "refunded_in_full") or not isinstance(staff_reference, str):
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})

    key_digest = scoped_key_sha256(actor=actor, operation="resolveLateOrder", raw_key=key)
    payload_digest = canonical_payload_sha256(
        {"order_id": order_id, "resolution": resolution, "staff_reference": staff_reference}
    )

    try:
        body_out, replayed = await repository.resolve_late_order(
            order_id=order_id,
            resolution=resolution,
            staff_reference=staff_reference,
            idempotency_key_sha256=key_digest,
            canonical_payload_sha256=payload_digest,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(
            status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "retryable": False}
        ) from exc
    except OrderNotFound as exc:
        raise HTTPException(
            status_code=404, detail={"code": "ORDER_NOT_FOUND", "retryable": False}
        ) from exc
    except NoOpenLateCase as exc:
        raise HTTPException(
            status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "retryable": False}
        ) from exc
    except PaymentProviderUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "PAYMENT_PROVIDER_UNAVAILABLE", "retryable": True}
        ) from exc

    if replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return body_out


__all__ = ["router"]
