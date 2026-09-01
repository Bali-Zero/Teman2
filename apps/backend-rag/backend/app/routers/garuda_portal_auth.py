"""GARUDA VOA magic-link authentication — L4 (contract-frozen).

Implements the two ``Magic-link authentication`` operations of
`products/garuda-voa/contracts/openapi.yaml` this lane owns per
`products/garuda-voa/LANES.md`: ``requestMagicLink`` and ``exchangeMagicLink``,
plus one additional operation this file mounts but the frozen contract does
NOT declare -- ``previewMagicLink`` (see its own docstring below for the
non-consuming lookup it performs and why it exists). Every other tag
(public eligibility, customer intake, payment, staff practice) belongs to
other lanes and has no route here.

``previewMagicLink`` is deliberately NOT added to `openapi.yaml`:
`LANES.md` states plainly that `products/garuda-voa/contracts/**` is
"Orchestrator-only, never edited by a lane," and that "business-visible
changes go through the owner" -- this lane builds against the frozen
contract, it does not amend it. Leaving the operation out of the frozen
file costs nothing at the parity gate: `test_garuda_voa_openapi_parity.py`
only asserts every FROZEN operationId is mounted and status-code-matching,
never the converse, so an extra live operation the contract does not know
about is invisible to it by construction. If this lookup is judged worth
promoting into the stable wire contract, that is the orchestrator's and
the owner's call to make in a future freeze, not this module's to decide
unilaterally.

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
from backend.services.garuda_flow.public_api import (
    CheckStore,
    UnconfiguredCheckStore,
)
from backend.services.garuda_flow.public_api import (
    PersistencePolicyUnavailable as CheckStorePersistencePolicyUnavailable,
)
from backend.services.garuda_portal.magic_link import (
    ExchangeOutcome,
    IdempotencyConflict,
    MagicLinkStore,
    PeekOutcome,
    PersistencePolicyUnavailable,
    RateLimited,
    UnconfiguredMagicLinkStore,
)
from backend.services.garuda_portal.masking import mask_email

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
    # Not in the frozen contract (see module docstring) -- no
    # IDEMPOTENCY_KEY_REQUIRED/IDEMPOTENCY_CONFLICT/RATE_LIMITED here on
    # purpose: this operation mutates nothing (no Idempotency-Key is even
    # read) and carries no store-level throttle of its own (see the
    # handler's docstring on why the generic per-IP middleware bucket is
    # the considered choice, not an oversight).
    "previewMagicLink": (
        "GARUDA_PUBLIC_DISABLED",
        "INVALID_REQUEST",
        "MAGIC_LINK_INVALID",
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


_default_check_store = UnconfiguredCheckStore()


def get_garuda_check_store(request: Request) -> CheckStore:
    """Reads `app.state.garuda_check_store` -- the SAME slot L2's
    `garuda_voa_public.get_garuda_check_store` reads and
    `service_initializer.py` wires -- duplicated rather than imported per
    this module's LANES.md file-ownership discipline (see the module
    docstring and `_FeatureDisabled`'s identical rationale above: this lane
    does not couple to `garuda_voa*.py`, L2's reserved filename pattern;
    `garuda_flow.public_api` is the shared PORT module, not that router
    file, so importing the Protocol/exception types from it is the seam,
    not a boundary violation).

    Used ONLY to re-verify, in `request_magic_link` below, that the
    caller's `garuda_result_session` cookie actually owns the `result_id`
    it is requesting a magic link for -- the same persistence port
    `getEligibilityResult` already reads for the identical purpose.
    """
    return getattr(request.app.state, "garuda_check_store", None) or _default_check_store


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


class MagicLinkPreviewResult(BaseModel):
    """Response body for ``previewMagicLink`` -- NOT in the frozen contract
    (see module docstring). `masked_email` is produced by
    `backend.services.garuda_portal.masking.mask_email`; this model never
    carries the raw address."""

    model_config = ConfigDict(extra="forbid")

    masked_email: str


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
    check_store: CheckStore = Depends(get_garuda_check_store),
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

    # Ownership check (security fix, 2026-08-30): a cookie's mere PRESENCE
    # used to be treated as sufficient to request a magic link for ANY
    # result_id in the request body -- the cookie was forwarded to
    # `store.issue` as `result_session_secret` and discarded there
    # unverified (`MagicLinkStore.issue` never persists or compares it; see
    # `magic_link_store.py::PostgresMagicLinkStore.issue`'s `del` and the
    # Protocol docstring it points back to). That let anyone who knows or
    # guesses a `result_id` they do NOT own -- using only their own,
    # unrelated session cookie -- have that OTHER result's magic link
    # mailed to an email address they control.
    #
    # `CheckStore.get` re-verifies the (result_id, session_secret) pair
    # against the hash persisted at check-creation time
    # (`garuda_flow/check_store.py::PostgresCheckStore.get`) -- the exact
    # primitive `garuda_voa_public.get_eligibility_result` already calls for
    # the identical ownership question. An unrecognised pair MUST take the
    # SAME non-enumerating 202 path as the absent-cookie/malformed-id case
    # above: a non-owned result_id has to be indistinguishable from a
    # non-existent one to the caller, or the endpoint becomes an oracle for
    # "does this result_id exist and belong to someone".
    try:
        owns_result = await check_store.get(
            result_id=payload.result_id, session_secret=garuda_result_session
        )
    except CheckStorePersistencePolicyUnavailable:
        # Same mapping `garuda_voa_public.get_eligibility_result` uses for
        # this identical unconfigured-check-store state: a configuration
        # gap must surface as an OBSERVABLE 503 (`SERVICE_UNAVAILABLE` is
        # already declared for this operation in the frozen contract), never
        # silently collapse into the enumeration-safe 202 below -- that
        # would read as "no magic link is ever issued", with no signal that
        # anything is misconfigured, rather than a dark-launch gap.
        logger.warning(
            "garuda_portal_auth: persistence policy unavailable at ownership check"
        )
        return _error("SERVICE_UNAVAILABLE")

    if owns_result is None:
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


@router.post(
    "/magic-links/preview",
    operation_id="previewMagicLink",
    status_code=200,
    responses=_error_responses("previewMagicLink"),
    response_model=MagicLinkPreviewResult,
)
async def preview_magic_link(
    payload: MagicLinkExchange,
    store: MagicLinkStore = Depends(get_garuda_magic_link_store),
) -> Response:
    """Answers "whose application does this link open?" WITHOUT consuming
    the token -- the residual login-CSRF finding
    `continue/page.tsx` (`apps/mouth/src/app/visa/voa/auth/`) has carried
    since 2026-08-28: a generic "Continue" button behind an unbound landing
    GET lets an attacker mail a victim the attacker's OWN link, and the
    victim's click plants the attacker's session in the victim's browser.
    Showing the customer whose application they are about to open, before
    they commit, is the mitigation; `MagicLinkStore.peek` (never `exchange`)
    is what makes it safe to call from an unauthenticated GET-adjacent flow
    without spending the very credential it describes.

    NOT part of the frozen contract (`products/garuda-voa/contracts/
    openapi.yaml`) -- see this module's own docstring for why a lane does
    not fold a new operation into that file unilaterally. Takes the exact
    same request shape as `exchangeMagicLink` (`MagicLinkExchange`, a
    `token` field) rather than inventing a second one for an operation that
    asks the identical question of the store, just without consuming the
    answer.

    Non-enumerating like `exchangeMagicLink`: an absent, malformed,
    expired, already-consumed, or foreign token all answer the identical
    401 `MAGIC_LINK_INVALID` -- `store.peek`'s own docstring is the
    authority on why those cases collapse into one `PeekOutcome(valid=
    False)` rather than a router-level distinction being layered back on
    top of it.

    No `Idempotency-Key`: unlike `issue`/`exchange`, this mutates nothing
    (see `PostgresMagicLinkStore.peek`'s docstring), so the contract's
    "every mutation requires Idempotency-Key" rule (`openapi.yaml`
    `info.description`) does not apply, and a caller may retry freely.

    Rate limiting: no store-level throttle here, the same considered choice
    `PostgresMagicLinkStore.exchange` already documents for the identical
    anonymous-token-guessing shape -- this Protocol carries no client IP to
    key a per-identity limit on. This path answers under the generic
    per-IP `/api/` `RateLimitMiddleware` bucket (120 req/min,
    `backend/middleware/rate_limiter.py`), the SAME bucket `/magic-links`
    and `/sessions` already answer under today (neither has a more specific
    entry in `RATE_LIMITS`).
    """
    try:
        outcome: PeekOutcome = await store.peek(token=payload.token)
    except PersistencePolicyUnavailable:
        logger.warning("garuda_portal_auth: persistence policy unavailable at preview")
        return _error("PERSISTENCE_POLICY_UNAVAILABLE")
    except Exception as exc:
        # Same rationale as the `issue`/`exchange` handlers above: log the
        # exception CLASS NAME only, never `.exception()` (frame-locals
        # capture) and never the message (it can quote the token).
        logger.error(
            "garuda_portal_auth: unexpected error at preview (%s)",
            type(exc).__name__,
        )
        return _error("INTERNAL_ERROR")

    if not outcome.valid or outcome.email is None:
        return _error("MAGIC_LINK_INVALID")

    result = JSONResponse(
        status_code=200,
        content=MagicLinkPreviewResult(masked_email=mask_email(outcome.email)).model_dump(),
    )
    result.headers.update(_PRIVACY_HEADERS)
    return result
