"""Visa Check homepage app — 5 endpoints.

POST /api/visa/check/start    → returns which branch the UI should show
POST /api/visa/clock          → persist Clock submission, return hash + timeline
POST /api/visa/match          → persist Match submission, return hash + recommendation
GET  /api/visa/clock/{hash}   → render Clock result
GET  /api/visa/match/{hash}   → render Match result

Nothing here recommends visas by ML — the decision tree is in
`backend.services.visa_check.match_tree`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Path
from jose import jwt
from pydantic import BaseModel, Field, field_validator

from backend.app.core.config import settings
from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.services.pricing.pricing_service import PricingService
from backend.services.visa_check import (
    VisaCheckRepository,
    clock_timeline,
    estimate_match_cost,
    recommend_visa,
)
from backend.services.visa_check.catalogue import (
    VisaType,
)
from backend.services.visa_check.match_tree import BudgetBand, Purpose

logger = get_logger(__name__)

_VISA_FUNNEL_JWT_TTL_SECONDS = 3600


def _issue_visa_funnel_jwt(check_hash: str) -> str:
    """Short-lived token that grants chat access for THIS wizard only."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": check_hash,
        "type": "visa_funnel",
        "iat": now,
        "exp": now + timedelta(seconds=_VISA_FUNNEL_JWT_TTL_SECONDS),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


router = APIRouter(prefix="/api/visa", tags=["visa-check"])


# Module-level PricingService — loads the JSON once at import time.
# If the load failed, we still respond but `estimated_cost_idr` is null.
_pricing = PricingService()


# ============================================================
# Pydantic models
# ============================================================


class BranchStartRequest(BaseModel):
    in_country_now: bool


class BranchStartResponse(BaseModel):
    branch: str  # "clock" | "match"


class ClockRequest(BaseModel):
    visa_type: VisaType
    entry_date: date
    in_country_now: bool = True
    client_fingerprint: str | None = Field(default=None, max_length=32)

    @field_validator("entry_date")
    @classmethod
    def _entry_date_reasonable(cls, v: date) -> date:
        # Entry can be in the past (user is in country) but not > 3y ago,
        # and not > 1 month in the future (form typos).
        today = date.today()
        if (today - v).days > 365 * 3:
            raise ValueError("entry_date too far in the past (>3 years)")
        if (v - today).days > 31:
            raise ValueError("entry_date cannot be more than 1 month in the future")
        return v


class ClockCheckpointPayload(BaseModel):
    label: str
    at: date
    title: str
    body: str


class ClockResponse(BaseModel):
    hash: str
    visa_type: VisaType
    entry_date: date
    expiry_date: date
    extensions_possible: int
    extension_days: int
    checkpoints: list[ClockCheckpointPayload]
    result_url: str
    session_jwt: str | None = None  # populated by POST, absent on GET


class MatchRequest(BaseModel):
    nationality: str = Field(..., min_length=2, max_length=3)
    purpose: Purpose
    duration_months: int = Field(..., ge=1, le=60)
    budget_band: BudgetBand
    expected_arrival_date: date | None = None
    client_fingerprint: str | None = Field(default=None, max_length=32)

    @field_validator("nationality")
    @classmethod
    def _normalise_iso(cls, v: str) -> str:
        return v.strip().upper()


class MatchResponse(BaseModel):
    hash: str
    recommended_visa: VisaType | None
    reason: str
    estimated_cost_idr: int | None
    cost_source: str | None
    processing_days: int | None
    pre_arrival_steps: list[str]
    alternatives: list[VisaType]
    referral_mode: bool
    result_url: str
    nationality: str
    purpose: str
    duration_months: int
    budget_band: str
    session_jwt: str | None = None  # populated by POST, absent on GET


# ============================================================
# Helpers
# ============================================================


def _processing_days(visa_type: VisaType) -> int:
    """Rough processing estimate for the result page; we don't persist it."""
    # Single-entry C-series and short-stay visit visas process in ~10 working days.
    # KITAS / multi-entry / yearly visas process in ~20–30 days.
    if visa_type in {
        VisaType.C1, VisaType.C2, VisaType.C6,
        VisaType.C7, VisaType.C7A, VisaType.C7B,
        VisaType.C18, VisaType.C22A,
    }:
        return 10
    return 25


# ============================================================
# Endpoints
# ============================================================


@router.post("/check/start", response_model=BranchStartResponse)
async def start_branch(payload: BranchStartRequest) -> BranchStartResponse:
    """Branch selector — dumb routing by the yes/no answer from the hero."""
    branch = "clock" if payload.in_country_now else "match"
    return BranchStartResponse(branch=branch)


@router.post("/clock", response_model=ClockResponse, status_code=201)
async def submit_clock(
    payload: ClockRequest,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ClockResponse:
    if not payload.in_country_now:
        # The UI should have redirected them to Match; guard anyway.
        raise HTTPException(
            status_code=400,
            detail="Clock is for people already in Indonesia. Use /api/visa/match.",
        )

    timeline = clock_timeline(visa_type=payload.visa_type, entry_date=payload.entry_date)

    repo = VisaCheckRepository(db_pool)
    try:
        saved = await repo.save_clock(
            visa_type=timeline.visa_type,
            entry_date=timeline.entry_date,
            expiry_date=timeline.expiry_date,
            extensions_possible=timeline.extensions_possible,
            extension_days=timeline.extension_days,
            client_fp=payload.client_fingerprint,
        )
    except asyncpg.PostgresError:
        logger.exception("visa_clock: DB insert failed")
        raise HTTPException(status_code=500, detail="Could not save timeline")

    return ClockResponse(
        hash=saved.hash,
        visa_type=saved.visa_type,
        entry_date=saved.entry_date,
        expiry_date=saved.expiry_date,
        extensions_possible=saved.extensions_possible,
        extension_days=saved.extension_days,
        checkpoints=[
            ClockCheckpointPayload(label=c.label, at=c.at, title=c.title, body=c.body)
            for c in timeline.checkpoints
        ],
        result_url=f"/visa/clock/{saved.hash}",
        session_jwt=_issue_visa_funnel_jwt(saved.hash),
    )


@router.post("/match", response_model=MatchResponse, status_code=201)
async def submit_match(
    payload: MatchRequest,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> MatchResponse:
    result = recommend_visa(
        nationality=payload.nationality,
        purpose=payload.purpose,
        duration_months=payload.duration_months,
        budget_band=payload.budget_band,
    )

    cost: int | None = None
    cost_source: str | None = None
    if result.recommended_visa is not None:
        cost, cost_source = estimate_match_cost(
            visa_type=result.recommended_visa,
            pricing=_pricing,
        )

    repo = VisaCheckRepository(db_pool)
    try:
        saved = await repo.save_match(
            nationality=payload.nationality,
            purpose=payload.purpose.value,
            duration_months=payload.duration_months,
            budget_band=payload.budget_band.value,
            recommended_visa=result.recommended_visa,
            recommendation_reason=result.reason,
            pre_arrival_steps=result.pre_arrival_steps,
            alternatives=[v.value for v in result.alternatives],
            expected_arrival_date=payload.expected_arrival_date,
            estimated_cost_idr=cost,
            client_fp=payload.client_fingerprint,
        )
    except asyncpg.PostgresError:
        logger.exception("visa_match: DB insert failed")
        raise HTTPException(status_code=500, detail="Could not save match result")

    proc_days = _processing_days(result.recommended_visa) if result.recommended_visa else None

    return MatchResponse(
        hash=saved.hash,
        recommended_visa=saved.recommended_visa,
        reason=saved.recommendation_reason,
        estimated_cost_idr=saved.estimated_cost_idr,
        cost_source=cost_source,
        processing_days=proc_days,
        pre_arrival_steps=saved.pre_arrival_steps,
        alternatives=[VisaType(v) for v in saved.alternatives],
        referral_mode=result.referral_mode,
        result_url=f"/visa/match/{saved.hash}",
        nationality=saved.nationality,
        purpose=saved.purpose,
        duration_months=saved.duration_months,
        budget_band=saved.budget_band,
        session_jwt=_issue_visa_funnel_jwt(saved.hash),
    )


@router.get("/clock/{hash}", response_model=ClockResponse)
async def get_clock(
    hash: str = Path(..., min_length=8, max_length=20),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ClockResponse:
    repo = VisaCheckRepository(db_pool)
    saved = await repo.load_clock(hash)
    if not saved:
        raise HTTPException(status_code=404, detail="Visa check not found")
    await repo.bump_view_count(hash)

    timeline = clock_timeline(visa_type=saved.visa_type, entry_date=saved.entry_date)
    return ClockResponse(
        hash=saved.hash,
        visa_type=saved.visa_type,
        entry_date=saved.entry_date,
        expiry_date=saved.expiry_date,
        extensions_possible=saved.extensions_possible,
        extension_days=saved.extension_days,
        checkpoints=[
            ClockCheckpointPayload(label=c.label, at=c.at, title=c.title, body=c.body)
            for c in timeline.checkpoints
        ],
        result_url=f"/visa/clock/{saved.hash}",
        # Same rationale as get_match: result page loads via GET, needs
        # a JWT to authenticate chat.
        session_jwt=_issue_visa_funnel_jwt(saved.hash),
    )


@router.get("/match/{hash}", response_model=MatchResponse)
async def get_match(
    hash: str = Path(..., min_length=8, max_length=20),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> MatchResponse:
    repo = VisaCheckRepository(db_pool)
    saved = await repo.load_match(hash)
    if not saved:
        raise HTTPException(status_code=404, detail="Visa check not found")
    await repo.bump_view_count(hash)

    proc_days = _processing_days(saved.recommended_visa) if saved.recommended_visa else None
    return MatchResponse(
        hash=saved.hash,
        recommended_visa=saved.recommended_visa,
        reason=saved.recommendation_reason,
        estimated_cost_idr=saved.estimated_cost_idr,
        cost_source=None,  # not persisted; rebuildable if needed
        processing_days=proc_days,
        pre_arrival_steps=saved.pre_arrival_steps,
        alternatives=[VisaType(v) for v in saved.alternatives],
        referral_mode=(saved.recommended_visa is None),
        result_url=f"/visa/match/{saved.hash}",
        # Re-issue a fresh JWT so the result page (shareable URL, loaded
        # via GET) can authenticate chat requests. The hash is already
        # the public token to access this row; JWT confirms the caller
        # has the hash within 1h. No additional info leak vs the URL.
        session_jwt=_issue_visa_funnel_jwt(saved.hash),
        nationality=saved.nationality,
        purpose=saved.purpose,
        duration_months=saved.duration_months,
        budget_band=saved.budget_band,
    )
