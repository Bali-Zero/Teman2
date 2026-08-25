"""GARUDA VOA public eligibility funnel — L2 (contract-frozen).

Implements exactly three operations of `products/garuda-voa/contracts/openapi.yaml`
(the only three this lane owns per `products/garuda-voa/LANES.md`):
``createEligibilityCheck``, ``getEligibilityResult``, ``deleteEligibilityResult``.
Every other tag (magic-link, customer intake, payment, staff practice) belongs to
other lanes and has no route here.

The contract is FROZEN and orchestrator-owned — this module implements it and
never edits it. Everything below is a deliberate, literal translation of that
file; where the engine cannot yet honour a contract clause (the three
truth-freshness gates in `openapi.yaml:x-truth-freshness-max-age-days` have no
implementation anywhere in `garuda_flow` today), this module does not invent
one — see the module-level TODO near `_evaluate_and_price`.

Wired into the running app as of 2026-08-25 (`20ef324d1`): a `RouterEntry` in
`router_manifest.py` plus a bare `include_router` in BOTH `include_routers()`
and `include_light_routers()`. This paragraph used to read "Not wired into the
running app", which was true when the lane wrote it and false from the moment
the orchestrator performed the mount — kept visible here because a docstring
that describes a wiring state is exactly the kind that rots without failing
anything.

`GARUDA_PUBLIC_ENABLED` is read directly from the environment (never
`app.core.config.settings` — that registration site is orchestrator-owned,
LANES.md "Shared and therefore forbidden to lanes") and defaults OFF. It is
read PER REQUEST, not at mount: there is deliberately no mount-time condition,
so the flag can be flipped without a restart and there is exactly one gate to
reason about rather than two that can disagree.
"""

from __future__ import annotations

import os
import re
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.utils.cookie_auth import (
    get_cookie_domain,
    get_cookie_secure,
    get_samesite_policy,
)
from backend.app.utils.logging_utils import get_logger
from backend.services.garuda_flow.civil_clock import garuda_today
from backend.services.garuda_flow.eligibility import DeclineCode
from backend.services.garuda_flow.intake import CaseType, Purpose
from backend.services.garuda_flow.public_api import (
    CheckStore,
    EligibilityCheckOutcome,
    IdempotencyConflict,
    PersistencePolicyUnavailable,
    PriceUnresolvable,
    UnconfiguredCheckStore,
    evaluate_public_check,
)

logger = get_logger(__name__)

class _ContractErrorRoute(APIRoute):
    """Rewrite FastAPI's default 422 body into the frozen `errors.yaml` shape.

    `ErrorResponse` is a closed 3-field tuple (`code`/`retryable`/`message_key`)
    — FastAPI's default `{"detail": [...]}` is not contract-valid and would
    echo the field path back to the caller.
    """

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        downstream = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await downstream(request)
            except RequestValidationError:
                return _error("INVALID_REQUEST")

        return handler


router = APIRouter(
    prefix="/api/visa/voa",
    tags=["garuda-voa-public"],
    route_class=_ContractErrorRoute,
)

_FEATURE_FLAG_ENV = "GARUDA_PUBLIC_ENABLED"
_RESULT_SESSION_COOKIE = "garuda_result_session"

#: `#/components/schemas/ResultId` verbatim.
_RESULT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22,128}$")
#: `#/components/parameters/IdempotencyKey` verbatim.
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{16,200}$")

#: `x-public-privacy-response-headers` verbatim — applied to EVERY response,
#: success and error alike (contract test
#: `test_every_public_response_carries_the_privacy_headers`).
_PRIVACY_HEADERS = {
    "Cache-Control": "no-store, private",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}

#: `errors.yaml` — (http_status, retryable, message_key), restricted to the
#: codes THIS router can ever emit (its three operations' `x-error-codes`).
_ERROR_CATALOG: dict[str, tuple[int, bool, str]] = {
    "GARUDA_PUBLIC_DISABLED": (404, False, "garuda_voa.error.unavailable"),
    "INVALID_REQUEST": (422, False, "garuda_voa.error.invalid_request"),
    "IDEMPOTENCY_KEY_REQUIRED": (400, False, "garuda_voa.error.idempotency_key_required"),
    "IDEMPOTENCY_CONFLICT": (409, False, "garuda_voa.error.idempotency_conflict"),
    "PERSISTENCE_POLICY_UNAVAILABLE": (503, False, "garuda_voa.error.sale_unavailable"),
    "PRICE_UNRESOLVABLE": (503, False, "garuda_voa.error.sale_unavailable"),
    "NOTICE_ACKNOWLEDGEMENT_REQUIRED": (
        422,
        False,
        "garuda_voa.error.notice_acknowledgement_required",
    ),
    "RESULT_NOT_FOUND": (404, False, "garuda_voa.error.result_not_found"),
    "RATE_LIMITED": (429, True, "garuda_voa.error.rate_limited"),
    "SERVICE_UNAVAILABLE": (503, True, "garuda_voa.error.service_unavailable"),
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


#: Per-operation error-code membership, restricted to what THIS router's
#: three call sites for that operation can ever raise via `_error()` — plus
#: the two codes (`RATE_LIMITED`, `INTERNAL_ERROR`) the frozen contract
#: declares for every operation as emitted by cross-cutting layers this
#: module does not own (rate-limit middleware, the top-level exception
#: handler), never by a call site here. Never hand-typed status codes: the
#: `responses=` dict below is always derived from `_ERROR_CATALOG` through
#: this map, so a new code added to the catalog and referenced here follows
#: into the generated OpenAPI schema without anyone remembering to update it
#: by hand (the drift this whole module exists to stop, one layer up).
_OPERATION_ERROR_CODES: dict[str, tuple[str, ...]] = {
    "createEligibilityCheck": (
        "IDEMPOTENCY_KEY_REQUIRED",
        "GARUDA_PUBLIC_DISABLED",
        "IDEMPOTENCY_CONFLICT",
        "INVALID_REQUEST",
        "NOTICE_ACKNOWLEDGEMENT_REQUIRED",
        "RATE_LIMITED",
        "INTERNAL_ERROR",
        "PERSISTENCE_POLICY_UNAVAILABLE",
        "PRICE_UNRESOLVABLE",
    ),
    "getEligibilityResult": (
        "GARUDA_PUBLIC_DISABLED",
        "RESULT_NOT_FOUND",
        "INTERNAL_ERROR",
        "SERVICE_UNAVAILABLE",
    ),
    "deleteEligibilityResult": (
        "IDEMPOTENCY_KEY_REQUIRED",
        "GARUDA_PUBLIC_DISABLED",
        "IDEMPOTENCY_CONFLICT",
        "INTERNAL_ERROR",
        "SERVICE_UNAVAILABLE",
    ),
}


def _error_responses(operation_id: str) -> dict[int | str, dict[str, object]]:
    """Build a FastAPI `responses=` dict for `operation_id` from
    `_ERROR_CATALOG`, grouped by HTTP status — documentation only, changes no
    behaviour. Two distinct codes sharing a status (e.g.
    `PERSISTENCE_POLICY_UNAVAILABLE` and `PRICE_UNRESOLVABLE`, both 503) fold
    into one schema entry, matching `openapi.yaml`'s own per-status
    `x-error-codes` list shape.
    """
    by_status: dict[int, list[str]] = {}
    for code in _OPERATION_ERROR_CODES[operation_id]:
        status_code, _retryable, _message_key = _ERROR_CATALOG[code]
        by_status.setdefault(status_code, []).append(code)
    return {
        status_code: {"description": " / ".join(codes)}
        for status_code, codes in by_status.items()
    }


# DECIDED 2026-08-25 (Zero/team-lead, option (b) of three): `getEligibilityResult`
# /`deleteEligibilityResult` validate `result_id` with `_RESULT_ID_PATTERN` by
# hand, inside the handler — never as a Pydantic path constraint. FastAPI
# nonetheless auto-documents a 422 "Validation Error" on these routes (any
# route with parameters gets one by default — see
# `fastapi.openapi.utils.get_openapi_path`; there is no per-route `responses=`
# value that opts out of it, only pre-populating the "422"/"4XX"/"default" key
# does, which would be the same misrepresentation). No code path can ever
# raise it here.
#
# Rejected: (a) a per-router `install_router()` helper called from
# `router_registration.py` instead of a bare `include_router` — an earlier
# version of this file had exactly that, nothing ever called it, and the gate
# built against the helper went green on a schema production never served.
# Also rejected on the merits even after that bug was ruled out empirically
# safe (a scoped strip touches 0 of the OTHER 423 operations in the light
# app's 425 that declare a 422): it threads a second per-router calling
# convention through a ~150-router registration file. (c) amending the frozen
# contract to declare the 422 as a known-but-unreachable outcome — rejected
# because this is a contract-first product; a promise that includes an
# outcome which cannot happen teaches the next lane to stop trusting the
# contract, and FastAPI's auto-422 fires on nearly every parameterized route
# in this app, so the same argument would reopen every other endpoint's
# schema precision, not just these two.
#
# Chosen: (b) — this pure, scoped function, called from BOTH app factories
# that mount this router (`app_factory.py::create_app()` and
# `main_api.py::create_api_app()`), chained onto `app.openapi` AFTER any
# existing wrapper, never replacing one. `create_app()` already has exactly
# this pattern for a different reason (`_openapi_with_visa_decision_conditionals`)
# — this reuses that shape rather than inventing a new one.
_NO_VALIDATION_ERROR_OPERATIONS = frozenset({"getEligibilityResult", "deleteEligibilityResult"})


def strip_unreachable_validation_errors(schema: dict) -> dict:
    """Remove the auto-added 422 for the two operations that cannot raise
    one. Scoped strictly by `operationId` — every other operation's
    `responses` dict, its legitimate 422s included, is untouched (measured
    2026-08-25 against the full `include_light_routers` schema: 425
    operations declared a 422, exactly 2 were removed). Mutates and returns
    `schema` for convenient chaining onto an existing `app.openapi` wrapper.
    """
    for methods in schema.get("paths", {}).values():
        if not isinstance(methods, dict):
            continue
        for op in methods.values():
            if isinstance(op, dict) and op.get("operationId") in _NO_VALIDATION_ERROR_OPERATIONS:
                op.get("responses", {}).pop("422", None)
    return schema


def _public_enabled() -> bool:
    return os.environ.get(_FEATURE_FLAG_ENV, "").strip().lower() in {"1", "true", "yes"}


def _valid_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    if _IDEMPOTENCY_KEY_PATTERN.fullmatch(value) is None:
        return None
    return value


# ============================================================
# Persistence dependency — see public_api.py module docstring.
# ============================================================

_default_store = UnconfiguredCheckStore()


def get_garuda_check_store(request: Request) -> CheckStore:
    """Reads `app.state.garuda_check_store`, set by the orchestrator's
    composition wiring (`service_initializer.py`) once migration 286 lands
    and a `PersistencePolicyUnavailable`-capable adapter exists. Falls back
    to the fail-closed default (see public_api.py module docstring) when
    unset — the SAME `getattr(..., None) or default` shape
    `garuda_orders_router.get_repository` uses, deliberately not
    `app.dependency_overrides` (that dict is FastAPI's TEST mechanism and a
    process-wide global one unrelated test's teardown can clear — see PR
    #4910's `garuda_magic_link_store` wiring note for the concrete hazard).
    Tests override this dependency directly via
    `app.dependency_overrides[get_garuda_check_store]`, which remains safe
    for test-scoped use; only a PRODUCTION wiring path avoids that dict.
    """
    return getattr(request.app.state, "garuda_check_store", None) or _default_store


# ============================================================
# Request/response models — literal translation of openapi.yaml
# ============================================================


class EligibilityCheckRequest(BaseModel):
    """`#/components/schemas/EligibilityCheckRequest`, verbatim including the
    `allOf` issuance/extension shape guard."""

    model_config = ConfigDict(extra="forbid")

    case_type: CaseType
    nationality: str = Field(pattern=r"^[A-Z]{3}$")
    entry_date: date
    passport_expiry_date: date
    voa_expiry_date: date | None = None
    purpose: Purpose
    travellers: int = Field(ge=1)
    self_pay: bool
    extension_already_used: bool
    retention_notice_acknowledged: bool

    @model_validator(mode="after")
    def _enforce_case_shape(self) -> EligibilityCheckRequest:
        if self.case_type is CaseType.EXTENSION:
            if self.voa_expiry_date is None:
                raise ValueError("voa_expiry_date is required for an extension case")
        else:
            if self.voa_expiry_date is not None:
                raise ValueError("voa_expiry_date is forbidden for an issuance case")
            if self.extension_already_used is not False:
                raise ValueError("extension_already_used must be false for an issuance case")
        return self


class AcceptedEligibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["ACCEPT"] = "ACCEPT"
    reason_codes: list[DeclineCode] = Field(default_factory=list, max_length=0)
    published_filing_deadline: date
    price_idr: int = Field(ge=1)


class DeclinedEligibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["DECLINE"] = "DECLINE"
    reason_codes: list[DeclineCode] = Field(min_length=1)


def _result_body(outcome: EligibilityCheckOutcome) -> dict[str, object]:
    if outcome.accepted:
        assert outcome.published_filing_deadline is not None
        assert outcome.price_idr is not None
        return AcceptedEligibilityResult(
            published_filing_deadline=outcome.published_filing_deadline,
            price_idr=outcome.price_idr,
        ).model_dump(mode="json")
    return DeclinedEligibilityResult(reason_codes=list(outcome.reason_codes)).model_dump(
        mode="json"
    )


def _set_result_session_cookie(response: Response, secret: str) -> None:
    response.set_cookie(
        key=_RESULT_SESSION_COOKIE,
        value=secret,
        httponly=True,
        secure=get_cookie_secure(),
        samesite=get_samesite_policy(),
        path="/",
        domain=get_cookie_domain(),
    )


# UPDATE (orchestrator, `freshness.py`, G-FRESHNESS-FAIL-CLOSED): the reader
# now exists. `intake.build_verdict` checks nationality_eligibility and
# rule_constants freshness unconditionally and DECLINEs with the new
# `DeclineCode.ELIGIBILITY_UNCONFIRMED` when either is past its window — the SAME
# shape as the calendar precedent immediately below (a 201 DECLINE via the
# closed vocabulary, never a bare error), which is why the outcome reaches
# this router exactly like any other DECLINE and needs no new branch here.
# `pricing.price_for_case` checks price_catalogue freshness and returns its
# EXISTING `(None, None)` fail-closed shape when stale, which this router
# already turns into 503 PRICE_UNRESOLVABLE via `PriceUnresolvable` below —
# also no new branch needed.
#
# Net effect: neither `ELIGIBILITY_UNCONFIRMED` nor `TRUTH_AUTHORITY_UNAVAILABLE`
# in `contracts/openapi.yaml`'s `x-error-codes` (503 shape) is ever emitted
# by this design — they are now the SAME dead-declared-code situation the
# paragraph below already resolved once for CALENDAR_COVERAGE_EXCEEDED.
# Orchestrator-scoped, not this lane's to fix: whether to remove those two
# codes from the frozen contract (contracts/** is orchestrator-only) is a
# call for whoever owns that freeze, not a router change.
#
# The calendar half of this note is CLOSED. It used to name
# CALENDAR_COVERAGE_EXCEEDED, a 503 the contract declared; the lane was right
# that it could not be told apart from a genuine ARRIVAL_DATE_UNCONFIRMED
# decline, and the resolution was that it should not be — the engine's 201
# DECLINE is the correct answer past COVERAGE_END, so the 503 was removed from
# the contract instead. See contracts/REVIEW.md, round 3.


@router.post(
    "/eligibility-checks",
    operation_id="createEligibilityCheck",
    status_code=201,
    responses=_error_responses("createEligibilityCheck"),
)
async def create_eligibility_check(
    payload: EligibilityCheckRequest,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    store: CheckStore = Depends(get_garuda_check_store),
) -> Response:
    if not _public_enabled():
        return _error("GARUDA_PUBLIC_DISABLED")

    key = _valid_idempotency_key(idempotency_key)
    if key is None:
        return _error("IDEMPOTENCY_KEY_REQUIRED")

    if payload.retention_notice_acknowledged is not True:
        return _error("NOTICE_ACKNOWLEDGEMENT_REQUIRED")

    today = garuda_today()
    try:
        outcome = evaluate_public_check(
            case_type=payload.case_type,
            nationality=payload.nationality,
            entry_date=payload.entry_date,
            passport_expiry_date=payload.passport_expiry_date,
            voa_expiry_date=payload.voa_expiry_date,
            purpose=payload.purpose,
            travellers=payload.travellers,
            self_pay=payload.self_pay,
            extension_already_used=payload.extension_already_used,
            today=today,
        )
    except PriceUnresolvable:
        logger.warning("garuda_voa_public: price unresolvable for case_type=%s", payload.case_type)
        return _error("PRICE_UNRESOLVABLE")

    canonical_request = payload.model_dump(mode="json")
    try:
        stored = await store.create(
            idempotency_key=key,
            canonical_request=canonical_request,
            outcome=outcome,
        )
    except IdempotencyConflict:
        return _error("IDEMPOTENCY_CONFLICT")
    except PersistencePolicyUnavailable:
        logger.warning("garuda_voa_public: persistence policy unavailable at create")
        return _error("PERSISTENCE_POLICY_UNAVAILABLE")

    body = _result_body(stored.outcome)
    result = JSONResponse(status_code=201, content=body)
    result.headers.update(_PRIVACY_HEADERS)
    result.headers["Location"] = f"/visa/voa/{stored.result_id}"
    result.headers["Idempotency-Replayed"] = "true" if stored.idempotency_replayed else "false"
    if not stored.idempotency_replayed and stored.session_secret is not None:
        _set_result_session_cookie(result, stored.session_secret)
    return result


@router.get(
    "/eligibility-checks/{result_id}",
    operation_id="getEligibilityResult",
    responses=_error_responses("getEligibilityResult"),
)
async def get_eligibility_result(
    result_id: str,
    garuda_result_session: Annotated[str | None, Cookie()] = None,
    store: CheckStore = Depends(get_garuda_check_store),
) -> Response:
    if not _public_enabled():
        return _error("GARUDA_PUBLIC_DISABLED")

    # Non-enumerating: malformed id, absent cookie, and a real-but-unbound id
    # all take the identical path to RESULT_NOT_FOUND (contract, verbatim).
    if _RESULT_ID_PATTERN.fullmatch(result_id) is None or garuda_result_session is None:
        return _error("RESULT_NOT_FOUND")

    try:
        stored = await store.get(result_id=result_id, session_secret=garuda_result_session)
    except PersistencePolicyUnavailable:
        logger.warning("garuda_voa_public: persistence policy unavailable at get")
        return _error("SERVICE_UNAVAILABLE")

    if stored is None:
        return _error("RESULT_NOT_FOUND")

    result = JSONResponse(status_code=200, content=_result_body(stored.outcome))
    result.headers.update(_PRIVACY_HEADERS)
    return result


@router.delete(
    "/eligibility-checks/{result_id}",
    operation_id="deleteEligibilityResult",
    status_code=204,
    responses=_error_responses("deleteEligibilityResult"),
)
async def delete_eligibility_result(
    result_id: str,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    garuda_result_session: Annotated[str | None, Cookie()] = None,
    store: CheckStore = Depends(get_garuda_check_store),
) -> Response:
    if not _public_enabled():
        return _error("GARUDA_PUBLIC_DISABLED")

    key = _valid_idempotency_key(idempotency_key)
    if key is None:
        return _error("IDEMPOTENCY_KEY_REQUIRED")

    session_secret = (
        garuda_result_session
        if garuda_result_session is not None and _RESULT_ID_PATTERN.fullmatch(result_id)
        else None
    )
    try:
        await store.delete(
            result_id=result_id,
            session_secret=session_secret,
            idempotency_key=key,
        )
    except IdempotencyConflict:
        return _error("IDEMPOTENCY_CONFLICT")
    except PersistencePolicyUnavailable:
        logger.warning("garuda_voa_public: persistence policy unavailable at delete")
        return _error("SERVICE_UNAVAILABLE")

    # Always 204 — a bound deletion and a no-op disclose nothing different
    # (contract, verbatim: "the response reveals no existence oracle").
    result = Response(status_code=204)
    result.headers.update(_PRIVACY_HEADERS)
    result.headers["Idempotency-Replayed"] = "false"
    return result
