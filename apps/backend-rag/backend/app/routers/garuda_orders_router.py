"""HTTP shell for GARUDA VOA L3 — checkout + orders.

Implements exactly the operations `products/garuda-voa/LANES.md` scopes to
L3: `createOrderFromCheck`, `getOrderAndPractice`, `observePaymentBrowserReturn`,
`receivePaymentWebhook`, `resolveLateOrder`.

`getOrderAndPractice`'s `practice` field is served by L4's
`PracticeRepository` (services/garuda_portal/practice.py) — the order half
stays this file's own ownership-filtered query, but the practice half is no
longer hardcoded `None` (corrected once L4's practice module shipped;
`practice.py`'s own docstring covers PR-01's scope and lazy-materialization
design in full).

Registered in `router_manifest.py` / `router_registration.py` (_API, mirrors
L2's `garuda_voa_public` — mount unconditionally, GARUDA_PUBLIC_ENABLED
re-checked per-request by this module's own `_require_flag`, wired as a
ROUTER-LEVEL dependency so it resolves before every other Depends() and
before body validation — see the comment above `router = APIRouter(...)`
below). The orchestrator
still owns injecting the real `EligibilityCheckLookup` / `PaymentProvider`
adapters onto `app.state` at composition time — `get_repository()` above
fails closed with 503 until that happens.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

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
from backend.services.garuda_portal.practice import PracticeRepository
from backend.services.payments.port import WebhookSignatureInvalid, WebhookUnparseable

_FLAG_ENV_VAR = "GARUDA_PUBLIC_ENABLED"


def _flag_enabled() -> bool:
    # CORRECTED (Gear-3 gate finding D, PR #4959): this used to read
    # `os.environ.get(_FLAG_ENV_VAR, "false").lower() == "true"` — a
    # strict-exact-"true" reader that disagreed with the permissive reader
    # `garuda_voa_public._public_enabled()` / `garuda_portal_auth._public_
    # enabled()` already use (trimmed, case-insensitive, accepts "1"/"yes").
    # `GARUDA_PUBLIC_ENABLED=1` opened L2/L4 and left L3 dark — a customer
    # could get a quote and then never check out. All three readers now
    # share this exact body (kept as local per-file copies, not a shared
    # import, per LANES.md file-ownership discipline); see
    # `test_garuda_public_enabled_readers_agree.py` for the value matrix
    # that pins the three copies identical.
    return os.environ.get(_FLAG_ENV_VAR, "").strip().lower() in {"1", "true", "yes"}


def _require_flag() -> None:
    if not _flag_enabled():
        raise HTTPException(
            status_code=404, detail={"code": "GARUDA_PUBLIC_DISABLED", "retryable": False}
        )


# CORRECTED (Gear-3 gate finding B, PR #4959): `_require_flag()` used to be
# the first statement INSIDE each handler body below. That is too late —
# FastAPI resolves a path-operation's parameter dependencies (here, every
# handler's `Depends(get_repository)`) BEFORE the handler function ever
# runs, and `get_repository` 503s when `app.state.garuda_order_repository`
# is unset (production's state until the orchestrator wires it). Net
# effect: with the flag OFF and no repository wired, every route here
# leaked a live 503 instead of a dark 404 — an anonymous existence-and-
# liveness oracle.
#
# A router-level `dependencies=` entry is solved BEFORE a path operation's
# own parameter dependencies (`fastapi/routing.py::_build_dependant_with_
# parameterless_dependencies` inserts router-level deps at index 0 of the
# dependant's dependency list; `fastapi/dependencies/utils.py::solve_
# dependencies` walks that list in order and raises immediately on the
# first exception) — proved empirically, not assumed, by
# `test_garuda_voa_flag_ordering.py`, which fails red against the OLD
# per-handler-body placement and passes green here.


class _ContractErrorRoute(APIRoute):
    """Rewrite every `HTTPException` this router raises into the frozen
    `errors.yaml` envelope, with the SAME privacy headers success paths get
    (Gear-3 gate finding on PR #4959's follow-up: the 28 bare
    `raise HTTPException(status_code=X, detail={"code": Y, "retryable": Z})`
    call sites below — spread across the router-level dependency
    (`_require_flag`), a parameter dependency (`get_repository`), plain
    helper coroutines called directly from handler bodies
    (`_require_magic_session_actor`, `_require_staff_actor`,
    `_idempotency_key`), and the five handler bodies themselves — each
    produced FastAPI's default `{"detail": {...}}` envelope instead of the
    contract's flat `{"code", "retryable", "message_key"}` shape, AND lost
    the `_privacy_headers()` a success response gets, because raising builds
    a brand-new `Response` FastAPI's own exception handling constructs,
    never the `response` object handlers mutate.

    `garuda_voa_public.py`'s `_ContractErrorRoute` (the model this
    replicates, per LANES.md file-ownership discipline — this is a
    same-shaped LOCAL copy, not a shared import) catches two SPECIFIC
    exception types because neither one carries a reusable `code` (a
    framework `RequestValidationError` and a bespoke `_FeatureDisabled`
    sentinel with none). Every one of THIS file's exceptions already IS an
    `HTTPException` whose `detail` already names the exact contract `code`
    — so catching `HTTPException` itself and reading `detail["code"]` is
    the direct generalisation of that same idea to 28 call sites through
    ONE catch, instead of converting each `raise` to a hand-written
    `return _error(...)` with 28 chances for a status/code typo to drift
    from the `errors.yaml` entry it is supposed to mirror. Whichever layer
    raises — router-level dependency, parameter dependency, a plain
    `await helper(...)` inside a handler body, or the handler body itself —
    the exception propagates through THIS route's own dispatch (dependency
    resolution included; same ordering argument as
    `garuda_voa_public._require_public_enabled`'s docstring) before
    Starlette's global `ExceptionMiddleware` ever sees it, so catching it
    here is exactly as complete as a bespoke sentinel per site would be.

    A caught `HTTPException` whose `detail` is not one of `_ERROR_CATALOG`'s
    codes (defensive — nothing in this file raises one today) is re-raised
    untouched rather than guessed at.
    """

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
    prefix="/api/visa/voa",
    tags=["garuda-orders"],
    route_class=_ContractErrorRoute,
    dependencies=[Depends(_require_flag)],
)


def _privacy_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"


#: `errors.yaml` — (http_status, retryable, message_key), restricted to the
#: codes THIS router's own 28 `raise HTTPException(...)` call sites can ever
#: emit. Each tuple is a verbatim copy of that code's `x-http-status` /
#: `retryable` / `message_key` consts in
#: `products/garuda-voa/contracts/errors.yaml` (frozen, orchestrator-owned)
#: — never hand-typed independently of the `raise` sites below, whose
#: `detail={"code": ..., "retryable": ...}` values `_ContractErrorRoute`
#: cross-checks against this table at request time.
_ERROR_CATALOG: dict[str, tuple[int, bool, str]] = {
    "GARUDA_PUBLIC_DISABLED": (404, False, "garuda_voa.error.unavailable"),
    "SERVICE_UNAVAILABLE": (503, True, "garuda_voa.error.service_unavailable"),
    "SESSION_REQUIRED": (401, False, "garuda_voa.error.session_required"),
    "IDEMPOTENCY_KEY_REQUIRED": (400, False, "garuda_voa.error.idempotency_key_required"),
    "INVALID_REQUEST": (422, False, "garuda_voa.error.invalid_request"),
    "RESULT_NOT_FOUND": (404, False, "garuda_voa.error.result_not_found"),
    "IDEMPOTENCY_CONFLICT": (409, False, "garuda_voa.error.idempotency_conflict"),
    "ORDER_NOT_READY": (409, False, "garuda_voa.error.order_not_ready"),
    "PERSISTENCE_POLICY_UNAVAILABLE": (503, False, "garuda_voa.error.sale_unavailable"),
    "PRICE_UNRESOLVABLE": (503, False, "garuda_voa.error.sale_unavailable"),
    "PAYMENT_PROVIDER_UNAVAILABLE": (503, True, "garuda_voa.error.payment_provider_unavailable"),
    "ORDER_NOT_FOUND": (404, False, "garuda_voa.error.order_not_found"),
    "WEBHOOK_SIGNATURE_INVALID": (401, False, "garuda_voa.error.webhook_signature_invalid"),
    "INVALID_STATE_TRANSITION": (409, False, "garuda_voa.error.invalid_state_transition"),
}


def _error(code: str) -> JSONResponse:
    """One error tuple, one call site — the body is EXACTLY the 3 contract
    fields. Privacy headers go through the SAME `_privacy_headers()` helper
    every success response already uses, so there is one place (not two)
    that can drift from the contract's `x-public-privacy-response-headers`.
    """
    status_code, retryable, message_key = _ERROR_CATALOG[code]
    response = JSONResponse(
        status_code=status_code,
        content={"code": code, "retryable": retryable, "message_key": message_key},
    )
    _privacy_headers(response)
    return response


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


#: Status codes THIS router's own call sites (plus the router-level
#: `_require_flag` dependency and the top-level exception handler /
#: rate-limit middleware every route shares) can genuinely produce today,
#: per operation. Documentation only, changes no behaviour — without this,
#: FastAPI only knows each decorator's own success `status_code` plus its
#: automatic 422, which is the exact drift class
#: `test_garuda_voa_openapi_parity.py` measured for this router on
#: 2026-08-30 (the same disease that file's docstring already describes for
#: `garuda_voa_public.py`, reproduced here for L3).
#:
#: Three of these five sets are deliberately NOT a full transcription of the
#: frozen contract's declared codes for that operationId — the gaps are
#: real, separate defects (not an OpenAPI-documentation oversight), and
#: documenting a status this router cannot yet produce would be exactly the
#: false-schema-entry mistake `garuda_voa_public.py::_error_responses`'s
#: docstring warns against. Each omission is named, cited, and pinned by
#: `_KNOWN_STATUS_CODE_GAPS` in the parity test rather than silently closed
#: here:
#:   - `observePaymentBrowserReturn` has no `409` — `GarudaOrderRepository.
#:     record_browser_return_observation` (repository.py) unconditionally
#:     overwrites `browser_return_nonce` on a mismatch instead of raising an
#:     `IdempotencyConflict`, so the contract's declared conflict code can
#:     never fire.
#:   - `receivePaymentWebhook` has no `202`/`400`/`409` — `202` (quarantine)
#:     is a response shape this handler's body never constructs, and
#:     `400`/`409` are Idempotency-Key-shaped codes for a parameter this
#:     operation deliberately stopped taking (see the handler's own comment
#:     above); the frozen contract's `responses` block was not updated to
#:     match, and this module never edits the contract.
#:   - `resolveLateOrder` has no `403` — `_require_staff_actor` only ever
#:     returns 401 or a verified actor (see its docstring: the real staff
#:     authority verifier is "wired nowhere today"), so `ACCESS_DENIED` has
#:     no code path that can raise it yet.
_OPERATION_STATUS_CODES: dict[str, tuple[int, ...]] = {
    "createOrderFromCheck": (400, 401, 404, 409, 422, 429, 500, 503),
    "getOrderAndPractice": (401, 404, 500, 503),
    "observePaymentBrowserReturn": (400, 401, 404, 422, 500, 503),
    "receivePaymentWebhook": (401, 404, 422, 500, 503),
    "resolveLateOrder": (400, 401, 404, 409, 422, 500, 503),
}


def _status_responses(operation_id: str) -> dict[int, dict[str, object]]:
    """Build a minimal FastAPI `responses=` dict from `_OPERATION_STATUS_CODES`
    — status codes only, no message-key detail, since this router raises bare
    `HTTPException(detail={"code": ..., "retryable": ...})` rather than the
    catalog-driven `_error()` helper `garuda_voa_public.py`/`garuda_portal_
    auth.py` use (see PR #5300 for the in-flight fix to this router's error
    envelope itself — orthogonal to this OpenAPI-schema-documentation fix)."""
    return {
        status_code: {"description": "See `products/garuda-voa/contracts/errors.yaml`."}
        for status_code in _OPERATION_STATUS_CODES[operation_id]
    }


@router.post(
    "/orders",
    status_code=201,
    operation_id="createOrderFromCheck",
    responses=_status_responses("createOrderFromCheck"),
)
async def create_order_from_check(
    request: Request,
    response: Response,
    body: dict,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    repository: GarudaOrderRepository = Depends(get_repository),
) -> dict:
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
        raise HTTPException(
            status_code=404, detail={"code": "RESULT_NOT_FOUND", "retryable": False}
        )
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


@router.get(
    "/orders/{order_id}",
    operation_id="getOrderAndPractice",
    responses=_status_responses("getOrderAndPractice"),
)
async def get_order_and_practice(
    order_id: str,
    request: Request,
    response: Response,
) -> dict:
    """Read-only tracker. Deliberately NOT `Depends(get_repository)`.

    It used to declare that dependency and never reference it: the handler
    answers entirely from `PracticeRepository(pool)` below. FastAPI resolves a
    parameter dependency before the handler body runs, so the declaration was
    not inert -- `get_repository` 503s whenever
    `app.state.garuda_order_repository` is unset, and that object is only ever
    constructed when `GARUDA_XENDIT_SECRET_KEY` is present
    (`service_initializer.py` §5.7). Net effect: a customer who had ALREADY
    PAID could not see their own order the moment the payment credential was
    absent, rotated badly, or the provider wiring raised -- on a route whose
    real work needs nothing but the database pool.

    Measured in production 2026-08-27, before the Xendit sandbox account
    exists: `GET /api/visa/voa/orders/{id}` answered `503
    SERVICE_UNAVAILABLE`, indistinguishable from the checkout routes that
    genuinely do need the provider. An availability coupling that buys nothing
    is the whole defect; removing the parameter is the whole fix.

    The `pool is None` guard below still 503s, correctly: that IS this route's
    only real dependency.
    """
    _privacy_headers(response)
    actor = await _require_magic_session_actor(request)
    pool = getattr(request.app.state, "garuda_db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503, detail={"code": "SERVICE_UNAVAILABLE", "retryable": True}
        )
    # `result_id_ref = actor` is the ownership predicate (#4910): an order
    # that exists but belongs to a different session's result_id must 404
    # exactly like an order that doesn't exist at all (`OrderNotFound`'s own
    # docstring already calls this shape "non-enumerating") -- a distinct
    # status code for "exists but not yours" is the enumeration oracle this
    # closes. `PracticeRepository` (L4, services/garuda_portal/practice.py)
    # applies the SAME predicate in its own query and serves the real
    # practice view (lazily materializing PR-01 for a paid order on first
    # read) instead of the `None` this route used to hardcode.
    body_out = await PracticeRepository(pool).get_order_and_practice_view(
        order_id=order_id, result_id_ref=actor
    )
    if body_out is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "retryable": False})
    return body_out


@router.post(
    "/orders/{order_id}/browser-return-observations",
    status_code=204,
    operation_id="observePaymentBrowserReturn",
    responses=_status_responses("observePaymentBrowserReturn"),
)
async def observe_payment_browser_return(
    order_id: str,
    request: Request,
    response: Response,
    body: dict,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    repository: GarudaOrderRepository = Depends(get_repository),
) -> None:
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


@router.post(
    "/webhooks/payment",
    status_code=204,
    operation_id="receivePaymentWebhook",
    responses=_status_responses("receivePaymentWebhook"),
)
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


@router.post(
    "/staff/orders/{order_id}/late-resolution",
    operation_id="resolveLateOrder",
    responses=_status_responses("resolveLateOrder"),
)
async def resolve_late_order(
    order_id: str,
    request: Request,
    response: Response,
    body: dict,
    authorization: str | None = Header(None),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    repository: GarudaOrderRepository = Depends(get_repository),
) -> dict:
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
