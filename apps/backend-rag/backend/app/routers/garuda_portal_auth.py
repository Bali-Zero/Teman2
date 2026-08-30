"""GARUDA VOA magic-link authentication — L4 (contract-frozen).

Implements exactly the two ``Magic-link authentication`` operations of
`products/garuda-voa/contracts/openapi.yaml` this lane owns per
`products/garuda-voa/LANES.md`: ``requestMagicLink`` and ``exchangeMagicLink``.
Every other tag (public eligibility, customer intake, payment, staff
practice) belongs to other lanes and has no route here.

This is a deliberately SEPARATE router file from `garuda_voa_public.py`
(owned by L2, `garuda_voa*.py` glob) even though both mount under the same
`/api/visa/voa` prefix — LANES.md reserves that filename pattern to L2, and a
lane that needs a file it does not own asks the orchestrator rather than
taking it (LANES.md, "File ownership — disjoint by construction"). Wiring
both routers into the same running app is the orchestrator's sequencing step
at landing time, not this lane's — this module follows the exact
"Not wired into the running app" posture `garuda_voa_public.py` already
documents for the same reason: `GARUDA_PUBLIC_ENABLED` is read directly from
the environment, never `app.core.config.settings`.

The contract is FROZEN and orchestrator-owned — this module implements it and
never edits it.
"""

from __future__ import annotations

import os
import re
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.app.core.config import settings
from backend.app.utils.cookie_auth import (
    get_cookie_domain,
    get_samesite_policy,
)
from backend.app.utils.logging_utils import get_logger
from backend.services.garuda_portal.magic_link import (
    ExchangeOutcome,
    IdempotencyConflict,
    MagicLinkStore,
    PersistencePolicyUnavailable,
    RateLimited,
    UnconfiguredMagicLinkStore,
)

logger = get_logger(__name__)


class _FeatureDisabled(Exception):
    """Sentinel raised by the router-level `_require_public_enabled`
    dependency below — identical rationale to `garuda_voa_public.py`'s
    twin, duplicated rather than imported per LANES.md file-ownership
    discipline."""


class _ContractErrorRoute(APIRoute):
    """Rewrite FastAPI's default 422 body into the frozen `errors.yaml` shape.

    Identical rationale/shape to `garuda_voa_public.py`'s route class —
    duplicated rather than imported because `garuda_voa*.py` is L2's file and
    this lane does not couple to another lane's private implementation
    detail (LANES.md file-ownership discipline).

    Also catches `_FeatureDisabled` (Gear-3 gate finding B, PR #4959) —
    both handlers below take a Pydantic body model, validated BEFORE the
    handler runs; see `_require_public_enabled`'s docstring.
    """

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        downstream = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await downstream(request)
            except RequestValidationError:
                return _error("INVALID_REQUEST")
            except _FeatureDisabled:
                return _error("GARUDA_PUBLIC_DISABLED")

        return handler


_FEATURE_FLAG_ENV = "GARUDA_PUBLIC_ENABLED"
_RESULT_SESSION_COOKIE = "garuda_result_session"
_ACCOUNT_SESSION_COOKIE = "garuda_session"

#: `#/components/schemas/ResultId` verbatim (same pattern as `garuda_voa_public.py`).
_RESULT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22,128}$")
#: `#/components/parameters/IdempotencyKey` verbatim.
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{16,200}$")

#: `x-public-privacy-response-headers` verbatim — applied to EVERY response.
_PRIVACY_HEADERS = {
    "Cache-Control": "no-store, private",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}

#: `errors.yaml` — (http_status, retryable, message_key), restricted to the
#: codes THIS router can ever emit (its two operations' `x-error-codes`).
_ERROR_CATALOG: dict[str, tuple[int, bool, str]] = {
    "GARUDA_PUBLIC_DISABLED": (404, False, "garuda_voa.error.unavailable"),
    "INVALID_REQUEST": (422, False, "garuda_voa.error.invalid_request"),
    "IDEMPOTENCY_KEY_REQUIRED": (400, False, "garuda_voa.error.idempotency_key_required"),
    "IDEMPOTENCY_CONFLICT": (409, False, "garuda_voa.error.idempotency_conflict"),
    "MAGIC_LINK_INVALID": (401, False, "garuda_voa.error.magic_link_invalid"),
    "RATE_LIMITED": (429, True, "garuda_voa.error.rate_limited"),
    "SERVICE_UNAVAILABLE": (503, True, "garuda_voa.error.service_unavailable"),
    "PERSISTENCE_POLICY_UNAVAILABLE": (503, False, "garuda_voa.error.sale_unavailable"),
    "INTERNAL_ERROR": (500, True, "garuda_voa.error.internal"),
}


def _error(code: str) -> JSONResponse:
    """One error tuple, one call site — the body is EXACTLY the 3 contract fields."""
    status_code, retryable, message_key = _ERROR_CATALOG[code]
    response = JSONResponse(
        status_code=status_code,
        content={"code": code, "retryable": retryable, "message_key": message_key},
    )
    response.headers.update(_PRIVACY_HEADERS)
    return response


#: Per-operation error-code membership — identical rationale and shape to
#: `garuda_voa_public.py`'s twin (duplicated, not imported, per LANES.md
#: file-ownership discipline). `RATE_LIMITED`/`INTERNAL_ERROR` are included
#: for both operations even where no call site below raises them directly:
#: they are cross-cutting (rate-limit middleware, the top-level exception
#: handler) per that same established convention. Never hand-typed status
#: codes elsewhere: `_error_responses()` below always derives from
#: `_ERROR_CATALOG` through this map.
_OPERATION_ERROR_CODES: dict[str, tuple[str, ...]] = {
    "requestMagicLink": (
        "IDEMPOTENCY_KEY_REQUIRED",
        "GARUDA_PUBLIC_DISABLED",
        "IDEMPOTENCY_CONFLICT",
        "INVALID_REQUEST",
        "RATE_LIMITED",
        "INTERNAL_ERROR",
        "PERSISTENCE_POLICY_UNAVAILABLE",
    ),
    "exchangeMagicLink": (
        "IDEMPOTENCY_KEY_REQUIRED",
        "MAGIC_LINK_INVALID",
        "GARUDA_PUBLIC_DISABLED",
        "IDEMPOTENCY_CONFLICT",
        "INVALID_REQUEST",
        "RATE_LIMITED",
        "INTERNAL_ERROR",
        "PERSISTENCE_POLICY_UNAVAILABLE",
    ),
}


def _error_responses(operation_id: str) -> dict[int | str, dict[str, object]]:
    """Build a FastAPI `responses=` dict for `operation_id` from
    `_ERROR_CATALOG`, grouped by HTTP status — documentation only, changes no
    behaviour. Identical shape to `garuda_voa_public.py`'s twin.

    Measured 2026-08-30 (`test_garuda_voa_openapi_parity.py` widening): without
    this, neither route below documented anything past the decorator's own
    success code and the framework's automatic 422 — the exact drift that
    test file's docstring already describes for L2, reproduced here for L4.
    """
    by_status: dict[int, list[str]] = {}
    for code in _OPERATION_ERROR_CODES[operation_id]:
        status_code, _retryable, _message_key = _ERROR_CATALOG[code]
        by_status.setdefault(status_code, []).append(code)
    return {
        status_code: {"description": " / ".join(codes)} for status_code, codes in by_status.items()
    }


def _public_enabled() -> bool:
    return os.environ.get(_FEATURE_FLAG_ENV, "").strip().lower() in {"1", "true", "yes"}


def _require_public_enabled() -> None:
    """Router-level dependency (Gear-3 gate finding B, PR #4959) — identical
    rationale to `garuda_voa_public._require_public_enabled`: both handlers
    below take a Pydantic body model (`MagicLinkRequest` / `MagicLinkExchange`),
    validated by FastAPI BEFORE the handler function runs, so the
    `if not _public_enabled(): return _error(...)` that used to open each
    handler body was too late — an empty/malformed body with the flag OFF
    leaked a 422 INVALID_REQUEST instead of the dark-launch 404. A
    router-level `dependencies=` entry is solved before body validation;
    see the sibling docstring for the exact FastAPI mechanics and the test
    that proves the ordering empirically
    (`test_garuda_voa_flag_ordering.py`).
    """
    if not _public_enabled():
        raise _FeatureDisabled()


router = APIRouter(
    prefix="/api/visa/voa/auth",
    tags=["garuda-voa-magic-link"],
    route_class=_ContractErrorRoute,
    dependencies=[Depends(_require_public_enabled)],
)


class _IdempotencyKeyAbsent(Exception):
    """Sentinel: the header was not sent at all. Maps to 400
    IDEMPOTENCY_KEY_REQUIRED — the contract reserves that status to this ONE
    case, distinct from a present-but-malformed key (422 INVALID_REQUEST,
    refuter finding #6: both used to collapse into the same 400)."""


class _IdempotencyKeyMalformed(Exception):
    """Sentinel: the header was sent but does not match the contract's
    pattern. Maps to 422 INVALID_REQUEST, never 400."""


def _require_idempotency_key(value: str | None) -> str:
    if value is None:
        raise _IdempotencyKeyAbsent
    if _IDEMPOTENCY_KEY_PATTERN.fullmatch(value) is None:
        raise _IdempotencyKeyMalformed
    return value


# ============================================================
# Persistence dependency — see magic_link.py module docstring.
# ============================================================

_default_store = UnconfiguredMagicLinkStore()


def get_garuda_magic_link_store(request: Request) -> MagicLinkStore:
    """Reads the orchestrator-wired store off `app.state.garuda_magic_link_
    store`, falling back to `UnconfiguredMagicLinkStore` (fails closed) when
    absent. `app.state` is the production wiring mechanism here, matching
    the sibling `garuda_magic_session_verifier` / `garuda_db_pool` slots
    `service_initializer.py` sets alongside this one -- deliberately NOT
    `app.dependency_overrides` (an earlier version of this wiring used that
    dict). `dependency_overrides` is FastAPI's TEST mechanism: a single
    process-wide dict with no scoping, and `backend/tests/unit/routers/
    test_dashboard_coverage.py` already calls
    `app.dependency_overrides.clear()` unconditionally in its teardown
    against the SAME `main_cloud.app` object production code shares (found
    by team-lead review, 2026-08-25). That call is harmless today only
    because that test file never triggers `initialize_services` and so
    never installs anything into the dict to clear -- but the moment
    anything DOES wire a production override there, that indiscriminate
    `.clear()` would silently erase it, producing exactly the half-wired
    state this module's docstring already calls out as worse than fully
    unwired: `garuda_magic_session_verifier` (a separate app.state slot,
    unaffected by dependency_overrides) stays live while session-MINTING
    silently reverts to `UnconfiguredMagicLinkStore`. Tests may still use
    `app.dependency_overrides[get_garuda_magic_link_store] = lambda: store`
    (FastAPI replaces the callable outright, so this function's own body
    never runs in that case) -- only the PRODUCTION wiring path moved.
    """
    return getattr(request.app.state, "garuda_magic_link_store", None) or _default_store


# ============================================================
# Request models — literal translation of openapi.yaml
# ============================================================


class MagicLinkRequest(BaseModel):
    """`#/components/schemas/MagicLinkRequest`, verbatim."""

    model_config = ConfigDict(extra="forbid")

    result_id: str = Field(pattern=r"^[A-Za-z0-9_-]{22,128}$")
    email: EmailStr = Field(max_length=320)


class MagicLinkExchange(BaseModel):
    """`#/components/schemas/MagicLinkExchange`, verbatim."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=2048)


#: Loopback hostnames a request can genuinely arrive on during local dev.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _account_session_cookie_secure(request: Request) -> bool:
    """Secure-by-default transport policy for `garuda_session` (L4 only).

    Deliberately NOT `cookie_auth.get_cookie_secure()`. That shared helper
    returns `False` for every `settings.environment != "production"` —
    staging, preview, container networks, anything reachable over a real
    network that merely isn't the prod env string — which sends this
    session bearer in the clear (CodeQL `py/clear-text-storage-sensitive-data`,
    2026-08-25, refuter-confirmed REAL_DEFECT at `_set_account_session_cookie`).
    `HttpOnly` blocks JS access, not network interception, and `SameSite`
    governs cross-site request behaviour, not confidentiality — neither
    substitutes for `Secure` here.

    CORRECTED 2026-08-25 (round 2): the first cut of this function read
    `request.url.hostname`, which Starlette derives from the client-supplied
    `Host` header (`starlette.datastructures.URL.__init__`), NOT from the
    socket. Measured: a scope with `server=("10.0.0.7", 443)` and header
    `Host: localhost` still yields `Request(scope).url.hostname == "localhost"`.
    That made the "loopback" check spoofable by anyone who can set a header —
    including a MITM rewriting a request on a staging/preview deploy, exactly
    the threat model this fix exists for. This version reads ONLY ASGI
    transport facts the client cannot forge via any header:
    `request.scope["scheme"]` (set by the server from the actual connection,
    not from `X-Forwarded-*` or `Host`) and `request.scope["server"]` (the
    socket the connection is bound to). `request.url`/`request.url.hostname`
    must never be used in this function again.

    Rule: `Secure=True` unless the connection is plain `http` AND the ASGI
    `server` socket host is loopback (`localhost` / `127.0.0.1` / `::1`) —
    i.e. `uvicorn --host 127.0.0.1` with no TLS, the one genuine local-dev
    shape. An already-`https` connection is always `Secure=True` (free, and
    correct regardless of host). Every other case — including non-production
    environments reached over `http` on a non-loopback socket — gets
    `Secure=True`. `cookie_auth.get_cookie_secure()` itself is left
    untouched: its existing callers (`cookie_auth.py`'s own JWT/CSRF cookies,
    `garuda_voa_public.py`) are out of scope for this fix and are pinned by
    `test_cookie_auth.py`.
    """
    if settings.environment == "production":
        return getattr(settings, "cookie_secure", True)
    if request.scope.get("scheme") == "https":
        return True
    server = request.scope.get("server")
    server_host = (server[0] if server else "") or ""
    return server_host.lower() not in _LOOPBACK_HOSTS


def _set_account_session_cookie(response: Response, request: Request, secret: str) -> None:
    response.set_cookie(
        key=_ACCOUNT_SESSION_COOKIE,
        value=secret,
        httponly=True,
        secure=_account_session_cookie_secure(request),
        samesite=get_samesite_policy(),
        path="/",
        domain=get_cookie_domain(),
    )


@router.post(
    "/magic-links",
    operation_id="requestMagicLink",
    status_code=202,
    responses=_error_responses("requestMagicLink"),
)
async def request_magic_link(
    payload: MagicLinkRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    garuda_result_session: Annotated[str | None, Cookie(alias=_RESULT_SESSION_COOKIE)] = None,
    store: MagicLinkStore = Depends(get_garuda_magic_link_store),
) -> Response:
    """Always 202 for an unknown or non-owned result and never returns the
    token (contract, verbatim). Exact replay returns the original 202
    without another email."""
    try:
        key = _require_idempotency_key(idempotency_key)
    except _IdempotencyKeyAbsent:
        return _error("IDEMPOTENCY_KEY_REQUIRED")
    except _IdempotencyKeyMalformed:
        return _error("INVALID_REQUEST")

    result = JSONResponse(status_code=202, content={})
    result.headers.update(_PRIVACY_HEADERS)

    # Non-enumerating: no ResultSession cookie, or a malformed result_id,
    # never reach the store — an absent/garbage cookie must be
    # indistinguishable from "a link was queued" to the caller. This mirrors
    # `garuda_voa_public.py::get_eligibility_result`'s identical short-circuit
    # for the same reason.
    if garuda_result_session is None or _RESULT_ID_PATTERN.fullmatch(payload.result_id) is None:
        result.headers["Idempotency-Replayed"] = "false"
        return result

    try:
        issued = await store.issue(
            idempotency_key=key,
            result_id=payload.result_id,
            email=str(payload.email),
            result_session_secret=garuda_result_session,
        )
    except IdempotencyConflict:
        return _error("IDEMPOTENCY_CONFLICT")
    except RateLimited:
        # Team-lead review, 2026-08-25: RATE_LIMITED is declared in the
        # frozen contract for this operation and was unreachable on any
        # code path before this. Observable by design (unlike the
        # enumeration-safe 202 below) — see magic_link.RateLimited's
        # docstring for why this does not leak email existence.
        logger.warning("garuda_portal_auth: issue rate limit exceeded")
        return _error("RATE_LIMITED")
    except PersistencePolicyUnavailable:
        logger.warning("garuda_portal_auth: persistence policy unavailable at issue")
        return _error("PERSISTENCE_POLICY_UNAVAILABLE")
    except Exception as exc:
        # Refuter finding #4: an unmapped store exception must never leak as
        # a bare framework 500 — fail closed into the contract's own shape.
        #
        # `logger.error` (not `.exception`), deliberately, since 2026-08-25
        # (Sentry gate #8755): `.exception` attaches `exc_info`, which Sentry's
        # LoggingIntegration turns into a full stacktrace WITH FRAME LOCALS —
        # and this frame holds `garuda_result_session`/the store's kwargs,
        # which can include `result_session_secret`. Key-based redaction in
        # `sentry_config._scrub` cannot reach a value that only exists inside
        # a captured frame's local-variable dump, so the cheapest real
        # mitigation for *this* handler is to never capture that dump at all.
        # CORRECTED 2026-08-30, falsified in production. The sentence that
        # stood here — "the exception type/message is still worth nothing
        # here anyway" — conflated the RESPONSE (rightly opaque) with the
        # LOG (which is the only place the cause can live). On 2026-08-30
        # every call to this endpoint answered INTERNAL_ERROR, and the whole
        # record of it was this one message repeated: no type, no stack, no
        # way to tell an absent SQL function from a bad parameter cast from
        # a dead pool. The privacy mitigation had blinded the diagnosis.
        #
        # The exception's CLASS NAME is logged, and nothing else. It is not
        # PII, not a message that could quote a value, and not a frame-locals
        # dump — `exc_info` stays off for exactly the reason above. A name
        # like `UndefinedFunctionError` or `PostgresSyntaxError` names the
        # cause on sight and can hold no caller data.
        logger.error(
            "garuda_portal_auth: unexpected error at issue (%s)",
            type(exc).__name__,
        )
        return _error("INTERNAL_ERROR")

    result.headers["Idempotency-Replayed"] = "true" if issued.idempotency_replayed else "false"
    return result


@router.post(
    "/sessions",
    operation_id="exchangeMagicLink",
    status_code=204,
    responses=_error_responses("exchangeMagicLink"),
)
async def exchange_magic_link(
    request: Request,
    payload: MagicLinkExchange,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    store: MagicLinkStore = Depends(get_garuda_magic_link_store),
) -> Response:
    """Invalid, expired, and consumed tokens return ONE non-enumerating
    error (DECISIONS.md Q1 — a consumed and an expired token MUST be
    indistinguishable to the caller). An exact Idempotency-Key replay returns
    the original 204 but creates no second session and emits no second
    Set-Cookie; a consumed token under a new key is invalid."""
    try:
        key = _require_idempotency_key(idempotency_key)
    except _IdempotencyKeyAbsent:
        return _error("IDEMPOTENCY_KEY_REQUIRED")
    except _IdempotencyKeyMalformed:
        return _error("INVALID_REQUEST")

    try:
        outcome: ExchangeOutcome = await store.exchange(
            idempotency_key=key,
            token=payload.token,
        )
    except IdempotencyConflict:
        return _error("IDEMPOTENCY_CONFLICT")
    except PersistencePolicyUnavailable:
        logger.warning("garuda_portal_auth: persistence policy unavailable at exchange")
        return _error("PERSISTENCE_POLICY_UNAVAILABLE")
    except Exception as exc:
        # `logger.error`, not `.exception` — see the identical rationale at
        # the `issue` handler above: this frame can hold `payload.token` and
        # a future adapter's `account_session_secret`, and `.exception`'s
        # captured frame-locals dump is a leak vector key-based redaction
        # cannot close. The exception's CLASS NAME is logged for the reason
        # given at the `issue` handler above (a blind handler cost a full
        # production outage its diagnosis on 2026-08-30); a class name can
        # hold no caller data.
        logger.error(
            "garuda_portal_auth: unexpected error at exchange (%s)",
            type(exc).__name__,
        )
        return _error("INTERNAL_ERROR")

    # `outcome.security_counter` is internal telemetry ONLY — logged here,
    # never serialized into the response. Whether the counter reads
    # magic_link_expired / magic_link_replay / magic_link_invalid, the HTTP
    # shape below is byte-identical: one 401, no other field.
    if not outcome.authorized:
        logger.info("garuda_portal_auth: exchange denied (counter=%s)", outcome.security_counter)
        return _error("MAGIC_LINK_INVALID")

    # Refuter finding #8: a store MUST NOT report authorized=True on a FRESH
    # exchange (not a replay) without a session secret — that combination is
    # an impossible/inconsistent adapter state, not a valid "no cookie"
    # outcome. Fail closed rather than silently return 204 with no session.
    if not outcome.idempotency_replayed and not outcome.account_session_secret:
        logger.error(
            "garuda_portal_auth: store reported authorized fresh exchange with no "
            "session secret — refusing to honour an inconsistent outcome"
        )
        return _error("INTERNAL_ERROR")

    logger.info("garuda_portal_auth: exchange authorized (counter=%s)", outcome.security_counter)
    result = Response(status_code=204)
    result.headers.update(_PRIVACY_HEADERS)
    result.headers["Idempotency-Replayed"] = "true" if outcome.idempotency_replayed else "false"
    if not outcome.idempotency_replayed and outcome.account_session_secret is not None:
        _set_account_session_cookie(result, request, outcome.account_session_secret)
    return result
