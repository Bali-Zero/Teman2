"""POST /api/visa-oracle/evaluate — the Visa Oracle v2 evaluate read-path (W1).

Public, exact-path, rate-limited endpoint: canonical ``ApplicantFacts`` JSON
in, the Kimi-spec B.2 envelope out (``{mode, decision, sources, display}`` —
``research/visa/2026-07-19-kimi-uiux-adaptation-spec.md`` §A.4.1/B.2), one
full-fact SHADOW ``visa_decisions`` audit row persisted per evaluation. The
engine orchestration lives in ``services/visa_engine/evaluate_path.py`` —
this module is the thin HTTP shell: request validation, abuse controls, and
the synthetic-``traffic_source`` trust gate.

Abuse controls (Codex red-team, binding per the W1 brief):

- Body-size cap: 32 KB (``MAX_EVALUATE_BODY_BYTES``) enforced on BOTH the
  declared Content-Length and the actual body — a canonical all-KNOWN facts
  payload is ~4 KB, so 32 KB is generous headroom, not a functional limit.
- Content-Type enforcement: ``application/json`` only (parameters such as
  ``; charset=utf-8`` accepted) — anything else is a 415.
- Schema validation: the body IS the canonical ApplicantFacts contract
  (``services/visa_engine/contracts/applicant-facts.schema.json`` —
  validated via ``models.ApplicantFacts``, the contract's executable form;
  ``test_schema_contracts.py`` pins the two to parity). Thin facts are NEVER
  rejected: an all-UNKNOWN payload is valid (unknowns carry explicit
  reasons; the engine abstains — ``NEEDS_INPUT`` is an answer, not an
  error). Validation errors are 422 with loc/type only — pydantic's
  ``include_input=False``, so no fact value is ever echoed back.
- Rate limit: dedicated 30/min bucket in ``RateLimitMiddleware.RATE_LIMITS``
  (exact-path entry, beats the generic ``/api/`` 120/min prefix).
- ``traffic_source`` (query param, default ``real``): synthetic classes are
  accepted only when the server-side allowlist env
  (``evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV``) arms them — anonymous
  callers can never self-label synthetic (400 otherwise).
- ``request_category`` (query param, optional): the v2 interview tile hint;
  validated against migration 257's 10-value enum. See
  ``evaluate_path.derive_request_category`` for why the hint exists
  (diaspora is otherwise inexpressible) and how facts-derivation falls back.
- No raw PII in any log line: facts stay out; the request trace is a
  truncated SHA-256 of the raw body and the persisted correlator is the
  HMAC facts-fingerprint (migration 255 pattern).

CORS note (web seat, W1 brief): same-origin today. This router adds NO
preflight handling of its own and does not widen the app-level CORS config;
if partner embeds become a goal, add explicit preflight handling for THIS
path only, in a separate reviewed change.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.services.visa_engine import evaluate_path
from backend.services.visa_engine.models import ApplicantFacts

logger = get_logger(__name__)

router = APIRouter(prefix="/api/visa-oracle", tags=["visa-oracle-evaluate"])

#: Hard cap on the request body (bytes) — see module docstring.
MAX_EVALUATE_BODY_BYTES = 32 * 1024


class TrafficSourceParam(str, Enum):
    """Migration 256's ``traffic_source`` CHECK classes, verbatim (wire type
    for the query parameter — an invalid value is a 422 before the handler
    ever runs)."""

    REAL = "real"
    SYNTHETIC_GOLD = "synthetic_gold"
    SYNTHETIC_DRIVER = "synthetic_driver"


class RequestCategoryParam(str, Enum):
    """Migration 257's ``request_category`` CHECK values, verbatim (the v2
    interview's 10 tiles mapped to the enum, W1 brief Item 3)."""

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


@router.post("/evaluate")
async def evaluate_applicant(
    request: Request,
    traffic_source: TrafficSourceParam = TrafficSourceParam.REAL,
    request_category: RequestCategoryParam | None = None,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Evaluate canonical applicant facts through the active rule pack.

    Always HTTP 200 for well-formed requests — including the fail-closed
    TEMPORARILY_UNAVAILABLE shape (surface disabled, no active pack,
    crypto/evaluation fail-close), so the v2 UI can degrade to its curated
    experience without special-casing errors (Kimi spec §B.3/B.4). Only
    request-shape defects are 4xx.
    """
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("application/json"):
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json",
        )

    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            declared = int(declared_length)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header") from None
        if declared > MAX_EVALUATE_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Request body too large")

    body = await request.body()
    if len(body) > MAX_EVALUATE_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Request body too large")

    try:
        raw = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Body must be valid JSON") from None

    try:
        facts = ApplicantFacts.model_validate(raw)
    except ValidationError as exc:
        # loc/type/msg only — never the offending input value (PII boundary).
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": [str(part) for part in error["loc"]],
                    "type": error["type"],
                    "msg": error["msg"],
                }
                for error in exc.errors(include_url=False, include_input=False)
            ],
        ) from exc

    if (
        traffic_source is not TrafficSourceParam.REAL
        and traffic_source.value not in evaluate_path.resolve_allowed_synthetic_sources()
    ):
        raise HTTPException(
            status_code=400,
            detail="Synthetic traffic_source classes are not accepted from anonymous callers",
        )

    # Non-reversible log correlator; the raw body (facts) itself is never logged.
    request_trace = hashlib.sha256(body).hexdigest()[:12]

    return await evaluate_path.run_evaluation(
        db_pool,
        facts=facts,
        traffic_source=traffic_source.value,
        request_category_hint=request_category.value if request_category is not None else None,
        request_trace=request_trace,
    )
