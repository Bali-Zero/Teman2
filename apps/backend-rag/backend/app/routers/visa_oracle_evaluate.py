"""POST /api/visa-oracle/evaluate — the Visa Oracle v2 evaluate read-path (W1).

Public, exact-path, rate-limited endpoint: canonical
``VisaOracleEvaluateRequest`` JSON in, the typed v2 envelope out
(``{mode, decision, sources, display}`` —
``research/visa/2026-07-19-kimi-uiux-adaptation-spec.md`` §A.4.1/B.2), with
durable, privacy-preserving audit persistence for completed evaluations. The
engine orchestration lives in ``services/visa_engine/evaluate_path.py`` —
this module is the thin HTTP shell: request validation, abuse controls, and
the synthetic-``traffic_source`` trust gate.

Abuse controls (Codex red-team, binding per the W1 brief):

- Body-size cap: 32 KB (``MAX_EVALUATE_BODY_BYTES``) enforced INCREMENTALLY
  via ``request.stream()`` — the declared Content-Length is an early-exit
  pre-check only; the actual body is read chunk-by-chunk and aborted with
  413 the moment the cap is exceeded, so a chunked-encoding caller (no
  Content-Length) can never make this endpoint buffer an unbounded payload
  (Gemini adversarial pass 2026-07-24, adjudicated HIGH — a post-hoc
  ``len(await request.body())`` check buffers the whole body FIRST).
- Content-Type enforcement: ``application/json`` only (parameters such as
  ``; charset=utf-8`` accepted) — anything else is a 415.
- Strict JSON ingestion: duplicate property names at any nesting depth and
  non-finite number tokens are rejected before Pydantic. The body model is
  ``VisaOracleEvaluateRequest``: canonical ApplicantFacts plus a closed,
  monotone ``disclosed_review_flags`` vocabulary. Thin facts remain valid.
  Validation errors are sanitized to loc/type/msg only; applicant values are
  never echoed.
- Rate limit: dedicated 30/min bucket in ``RateLimitMiddleware.RATE_LIMITS``
  (exact-path entry, beats the generic ``/api/`` 120/min prefix).
- ``traffic_source`` (required query param; no implicit default): callers must
  label every request explicitly. Synthetic classes
  require BOTH (a) the server-side allowlist env
  (``evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV``) arming the class AND
  (b) the ``X-Visa-Driver-Token`` header matching the
  ``VISA_ENGINE_DRIVER_TOKEN`` shared secret (constant-time compare) —
  that token IS the W4 gold-corpus replay driver credential: it lets an
  operator-armed deployment label corpus traffic honestly WITHOUT opening
  the synthetic label to every anonymous caller (Gemini adversarial pass,
  adjudicated HIGH). Missing/mismatched token, unarmed class, or unset
  secret env: 400, with a single generic message that never reveals which
  layer failed.
- Canary mode override (``X-Visa-Canary-Mode`` + ``X-Visa-Canary-Token``):
  the per-request rollout lever. Presence of the MODE header is the only
  thing that opens the branch, so a request without it runs the identical
  statement it ran before the lever existed. When it is present, the mode
  must be ``SHADOW``/``ENFORCE`` AND the token must match
  ``VISA_ENGINE_EVALUATE_CANARY_TOKEN`` (constant-time) — otherwise 400,
  with one generic message covering every failure layer. On success the
  request's ``traffic_source`` is FORCED to ``synthetic_driver`` before the
  canonical request is built, so a canary decision is never counted as real
  production demand and the idempotency binding records the true label.
  This is a separate secret from the driver credential on purpose: holding
  the replay-driver token must not confer the authority to change mode.
- ``request_category`` (query param, optional): the v2 interview tile
  hint; validated against migration 257's 10-value enum. See
  ``evaluate_path.derive_request_category`` for why the hint exists
  (diaspora is otherwise inexpressible) and when it is honored (only when
  facts derive ``other`` — facts speak first).
- Query params are validated IN-ROUTE as raw strings (400 on invalid,
  never echoing the received value): FastAPI's default enum-param 422
  would reflect the attacker's input back in the error body (Gemini
  adversarial pass, adjudicated MEDIUM).
- No raw PII in any log line: facts stay out; the request trace is a random,
  PII-independent attempt identifier and the persisted correlator is the HMAC
  facts-fingerprint (migration 255 pattern).

CORS note (web seat, W1 brief): same-origin today. This router adds NO
preflight handling of its own and does not widen the app-level CORS config;
if partner embeds become a goal, add explicit preflight handling for THIS
path only, in a separate reviewed change.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Awaitable, Callable
from contextlib import nullcontext
from enum import Enum
from typing import Annotated, Any, cast

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.responses import Response

from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.services.visa_engine import evaluate_path
from backend.services.visa_engine.api_models import (
    VisaOracleErrorResponse,
    VisaOracleEvaluateRequest,
    VisaOracleEvaluateResponse,
    VisaOracleValidationErrorResponse,
)
from backend.services.visa_engine.bundle import JsonValue, canonicalize_json
from backend.services.visa_engine.idempotency import IdempotencyConflictError

logger = get_logger(__name__)

#: Hard cap on the request body (bytes) — see module docstring.
MAX_EVALUATE_BODY_BYTES = 32 * 1024

# Bound decimal parsing before ``int()``. Python deliberately rejects integer
# strings above its global digit limit; an HTTP header must never turn that
# interpreter guard into a 500.
MAX_CONTENT_LENGTH_DIGITS = 20

#: The W4 gold-corpus replay driver credential header (see module docstring).
DRIVER_TOKEN_HEADER = "x-visa-driver-token"

#: Per-request canary mode override (see module docstring). BOTH headers are
#: required: the mode header states the intent, the token header proves the
#: authority. Neither alone does anything.
CANARY_MODE_HEADER = "x-visa-canary-mode"
CANARY_TOKEN_HEADER = "x-visa-canary-token"

#: Opaque caller token accepted for durable replay. A closed ASCII alphabet
#: avoids normalization ambiguity between proxies and PostgreSQL.
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

_STATIC_VALIDATION_MESSAGES = {
    "missing": "Required field is missing",
    "extra_forbidden": "Unexpected field",
    "literal_error": "Value is outside the allowed vocabulary",
    "enum": "Value is outside the allowed vocabulary",
}


class _DuplicateJsonKeyError(ValueError):
    """Raised without carrying the key so PII never reaches an error body."""


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise _DuplicateJsonKeyError("duplicate JSON property")
        parsed[key] = value
    return parsed


def _reject_non_finite_number(_token: str) -> None:
    raise ValueError("non-finite JSON number")


def _parse_strict_json(body: bytes) -> Any:
    """Parse I-JSON's security-critical subset before model validation."""

    text = body.decode("utf-8", errors="strict")
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_object_pairs,
        parse_constant=_reject_non_finite_number,
    )


def _sanitized_validation_detail(exc: RequestValidationError) -> list[dict[str, Any]]:
    """Return structural diagnostics only, excluding attacker/applicant input."""

    sanitized: list[dict[str, Any]] = []
    for error in exc.errors():
        error_type = str(error["type"])
        raw_location = tuple(error.get("loc", ()))
        scope = (
            str(raw_location[0])
            if raw_location and raw_location[0] in {"body", "query", "path", "header", "cookie"}
            else "request"
        )
        sanitized.append(
            {
                # Pydantic includes unknown JSON property names in ``loc``
                # for extra_forbidden. Those names are attacker-controlled
                # and may themselves contain applicant PII, so expose only a
                # static structural scope and the fact that a field failed.
                "loc": [scope, "field"] if len(raw_location) > 1 else [scope],
                "type": error_type,
                "msg": _STATIC_VALIDATION_MESSAGES.get(error_type, "Invalid request field"),
            }
        )
    return sanitized


class StrictEvaluateJsonRoute(APIRoute):
    """Validate raw request bytes before FastAPI's typed body parser.

    The endpoint can therefore expose a normal Pydantic request component in
    OpenAPI while retaining incremental size enforcement and duplicate-key
    rejection at the actual wire boundary.
    """

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        downstream = super().get_route_handler()

        async def strict_route_handler(request: Request) -> Response:
            content_types = request.headers.getlist("content-type")
            if len(content_types) > 1:
                raise HTTPException(
                    status_code=400,
                    detail="Multiple Content-Type headers are not allowed",
                )
            content_type = content_types[0] if content_types else ""
            mime_essence = content_type.split(";", 1)[0].strip().lower()
            if mime_essence != "application/json":
                raise HTTPException(
                    status_code=415,
                    detail="Content-Type must be application/json",
                )

            declared_lengths = request.headers.getlist("content-length")
            if len(declared_lengths) > 1:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Content-Length header",
                )
            if declared_lengths:
                declared_length = declared_lengths[0]
                if (
                    len(declared_length) > MAX_CONTENT_LENGTH_DIGITS
                    or not declared_length.isascii()
                    or not declared_length.isdecimal()
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid Content-Length header",
                    )
                if int(declared_length) > MAX_EVALUATE_BODY_BYTES:
                    raise HTTPException(status_code=413, detail="Request body too large")

            body = await _read_capped_body(request)
            try:
                _parse_strict_json(body)
            except (UnicodeDecodeError, ValueError, RecursionError):
                raise HTTPException(status_code=400, detail="Body must be valid JSON") from None

            # FastAPI's typed parser reads Request.body(). The capped bytes are
            # cached only after strict parsing, so it never consumes the raw
            # transport stream independently or past the route limit.
            request._body = body
            try:
                return await downstream(request)
            except RequestValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=_sanitized_validation_detail(exc),
                ) from exc

        return strict_route_handler


router = APIRouter(
    prefix="/api/visa-oracle",
    tags=["visa-oracle-evaluate"],
    route_class=StrictEvaluateJsonRoute,
)


class TrafficSourceParam(str, Enum):
    """Migration 256's ``traffic_source`` CHECK classes, verbatim — the
    validation vocabulary for the query parameter (validated in-route; NOT
    a FastAPI parameter type, so an invalid value can never be echoed back
    by the default RequestValidationError handler)."""

    REAL = "real"
    SYNTHETIC_GOLD = "synthetic_gold"
    SYNTHETIC_DRIVER = "synthetic_driver"


class RequestCategoryParam(str, Enum):
    """Migration 257's ``request_category`` CHECK values, verbatim (the v2
    interview's 10 tiles mapped to the enum, W1 brief Item 3) — same
    in-route-validation role as ``TrafficSourceParam``."""

    LONG_TOURISM = "long_tourism"
    WORK_EMPLOYEE = "work_employee"
    WORK_REMOTE = "work_remote"
    INVESTOR = "investor"
    BUSINESS = "business"
    FAMILY = "family"
    RETIREMENT = "retirement"
    STUDENT = "student"
    DIASPORA = "diaspora"
    OTHER = "other"


_TRAFFIC_SOURCE_VALUES = frozenset(member.value for member in TrafficSourceParam)
_REQUEST_CATEGORY_VALUES = frozenset(member.value for member in RequestCategoryParam)


async def _read_capped_body(request: Request) -> bytes:
    """Read the request body incrementally, enforcing MAX_EVALUATE_BODY_BYTES.

    Aborts with 413 the moment the running total exceeds the cap — at most
    MAX + one transport chunk is ever in flight, instead of the whole
    payload being buffered before a post-hoc length check could run.
    """

    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > MAX_EVALUATE_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Request body too large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/evaluate",
    operation_id="evaluateVisaOracleV2",
    response_model=VisaOracleEvaluateResponse,
    responses={
        400: {"model": VisaOracleErrorResponse, "description": "Malformed or conflicting input"},
        409: {"model": VisaOracleErrorResponse, "description": "Idempotency key conflict"},
        413: {"model": VisaOracleErrorResponse, "description": "Request body too large"},
        415: {"model": VisaOracleErrorResponse, "description": "Unsupported media type"},
        422: {
            "model": VisaOracleValidationErrorResponse,
            "description": "Schema validation failed without echoing input values",
        },
    },
)
async def evaluate_applicant(
    request_body: VisaOracleEvaluateRequest,
    request: Request,
    traffic_source: Annotated[
        str,
        Query(json_schema_extra={"enum": sorted(_TRAFFIC_SOURCE_VALUES)}),
    ],
    request_category: Annotated[
        str | None,
        Query(json_schema_extra={"enum": sorted(_REQUEST_CATEGORY_VALUES)}),
    ] = None,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", description="Opaque durable replay key (max 128 ASCII)"),
    ] = None,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> VisaOracleEvaluateResponse:
    """Evaluate canonical applicant facts through the active rule pack.

    Always HTTP 200 for well-formed requests — including the fail-closed
    TEMPORARILY_UNAVAILABLE shape (surface disabled, no active pack,
    crypto/evaluation fail-close). The response ``mode`` tells the v2 UI
    whether the result is comparison-only CURATED or authoritative ENGINE;
    it must never fabricate a result from an outage. Only request-shape
    defects are 4xx.
    """
    # In-route query-param validation: 400 with a static message, NEVER
    # echoing the received value back (see module docstring).
    if traffic_source not in _TRAFFIC_SOURCE_VALUES:
        raise HTTPException(
            status_code=400,
            detail="traffic_source is not an accepted value",
        )
    if request_category is not None and request_category not in _REQUEST_CATEGORY_VALUES:
        raise HTTPException(
            status_code=400,
            detail="request_category is not an accepted value",
        )

    # Canary mode override. Presence of the mode header is the ONLY thing
    # that opens this branch: a request without it takes the exact path it
    # took before this lever existed, whether or not the secret is
    # provisioned. Rejection is 400 with a single generic message, for the
    # same reason as the synthetic gate below — the caller learns nothing
    # about which layer said no.
    canary_mode = None
    if request.headers.get(CANARY_MODE_HEADER) is not None:
        canary_mode = evaluate_path.parse_canary_mode(request.headers.get(CANARY_MODE_HEADER))
        if canary_mode is None or not evaluate_path.verify_canary_token(
            request.headers.get(CANARY_TOKEN_HEADER)
        ):
            raise HTTPException(
                status_code=400,
                detail="Canary mode override is not accepted from anonymous callers",
            )
        # A canary evaluation is never real traffic. Forced server-side and
        # unconditionally, so the caller cannot both hold the canary
        # credential and have its rows counted as production demand — and
        # cannot self-label `synthetic_gold` either. This overwrite happens
        # BEFORE the canonical request is built, so the idempotency binding
        # records the label the row will actually carry.
        traffic_source = TrafficSourceParam.SYNTHETIC_DRIVER.value

    if (
        canary_mode is None
        and traffic_source != TrafficSourceParam.REAL.value
        and (
            traffic_source not in evaluate_path.resolve_allowed_synthetic_sources()
            or not evaluate_path.verify_driver_token(request.headers.get(DRIVER_TOKEN_HEADER))
        )
    ):
        # One generic message for every failure layer (unarmed class, unset
        # secret env, missing token, mismatched token) — an attacker learns
        # nothing about which layer rejected them.
        raise HTTPException(
            status_code=400,
            detail="Synthetic traffic_source classes are not accepted from anonymous callers",
        )

    idempotency_values = request.headers.getlist("idempotency-key")
    if len(idempotency_values) > 1 or (
        idempotency_key is not None and IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key) is None
    ):
        raise HTTPException(status_code=400, detail="Idempotency-Key is not an accepted value")

    # Random, PII-independent per-attempt correlator. Never derive log IDs
    # from applicant facts, even through an unkeyed hash.
    request_trace = uuid.uuid4().hex

    canonical_request = {
        "body": request_body.model_dump(mode="json", by_alias=True),
        "request_category": request_category,
        "traffic_source": traffic_source,
    }
    canonical_request_bytes = canonicalize_json(cast(dict[str, JsonValue], canonical_request))

    # `nullcontext` keeps ONE call path: a non-canary request is not merely
    # equivalent to the pre-canary code, it executes the same statement.
    authority = (
        nullcontext() if canary_mode is None else evaluate_path.canary_mode_override(canary_mode)
    )
    try:
        with authority:
            return await evaluate_path.run_public_evaluation(
                db_pool,
                request=request_body,
                traffic_source=traffic_source,
                request_category_hint=request_category,
                request_trace=request_trace,
                canonical_request=canonical_request_bytes,
                idempotency_key=idempotency_key,
            )
    except IdempotencyConflictError:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key is already bound to a different request",
        ) from None
