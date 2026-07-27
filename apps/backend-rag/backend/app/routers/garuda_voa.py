"""GARUDA VOA public request funnel (Slice A) — 2 endpoints.

POST /api/visa/voa        → validate, run intake, price via PricingService,
                             persist, return the verdict
GET  /api/visa/voa/{hash} → re-render the stored row

No auth dependency (mirrors `visa_check.py`) — the whole PII surface is
enum/date/bool/ISO-code only (BUILD-SPEC-SLICE-A-2026-07-27.md §5). Both
routes are registered public in `backend/app/auth/public_endpoints.py`.

Client-facing boundary (charter, non-negotiable): only ONE Safe Clock date
may ever reach a visitor — `published_filing_deadline` (D-7), "paling
lambat 7 hari sebelum masa izin tinggal berakhir", worded identically
everywhere on ngurahrai.imigrasi.go.id. The D-14 filing-window-OPENS date
is deliberately NOT exposed here: that same page states it two
incompatible ways in the same breath — "paling cepat 14 hari sebelum ...
habis" (14 days before expiry) vs. "paling cepat 14 hari setelah
kedatangan" (14 days after arrival) — different dates on a 30-day B1. We
do not publish, as an official rule, a date the official source itself
cannot agree on. D-10/D-3/D-1 remain purely internal for an unrelated
reason (pilot conservatism, never a public rule). `VoaResponse`
structurally has no field for any of the four — there is no way to
serialize them by accident (see `services.garuda_flow.intake.VoaVerdict`
for the accessor that encodes this split on the object itself). The
engine still computes the D-14 reading internally for staff
(`safe_clock.filing_window_opens_for`) — it just never crosses the wire.

The same boundary applies to decline REASONS, not just dates (fix
2026-07-27, cross-family review): `services.garuda_flow.eligibility.screen()`
composes its ``decline_reasons`` as English audit prose at runtime — it can
name an internal checkpoint (e.g. "below D-10 pilot threshold") because
that string is meant for the case sheet, not a visitor, and constants.py /
safe_clock.py are explicit that D-10 is "NEVER quoted to a client". Those
strings are also untranslated English on a page that serves id/it too.
`VoaResponse` therefore carries `reason_codes: list[str]` — stable,
neutral, language-agnostic machine codes
(`services.garuda_flow.eligibility.DeclineCode`) — and NO LONGER a
`reasons` field of raw prose. The prose is still computed and PERSISTED
(`garuda_voa_checks.decline_reasons`) for audit; it simply never leaves
this process. The frontend (`apps/mouth/.../visa/voa/[hash]/page.tsx`)
looks up each code in `i18n/locales/{en,id,it}.json` to render a localized,
routing-not-rejection sentence.

Issuance-only submission-window gate (owner ruling 2026-07-27,
`services.garuda_flow.operating_calendar`): a VOA is issued in a few
hours, so an issuance request is accepted up to the day BEFORE arrival —
Bali Zero's systems being closed weekends and Indonesian national
holidays/cuti bersama. This SUPERSEDES the charter's blanket "urgent case"
exclusion FOR ISSUANCE ONLY; extensions are untouched (in-person
photo/interview since 29 May 2025, own D-10 runway gate, own D-7 published
deadline). Two neutral, routing-worded decline codes
(`DeclineCode.ARRIVAL_TOO_SOON` / `DeclineCode.ARRIVAL_DATE_UNCONFIRMED`)
join the wire-safe set above. `VoaResponse.submit_by_date` carries the one
date this gate can ever show a visitor — Bali Zero's OWN operational
commitment, never a government deadline — and is `None` when it cannot be
computed (arrival past the decreed 2026 calendar; fail-closed, never
guessed).
"""

from __future__ import annotations

from datetime import date

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.services.garuda_flow.intake import (
    CaseType,
    Purpose,
    VoaIntakeRequest,
    build_verdict,
)
from backend.services.garuda_flow.repository import (
    GarudaVoaRepository,
    VoaCheckResult,
)
from backend.services.pricing.pricing_service import PricingService
from backend.services.visa_check.pricing_bridge import _best_pricing_candidate

logger = get_logger(__name__)

router = APIRouter(prefix="/api/visa", tags=["garuda-voa"])

# Module-level PricingService — loads the JSON once at import time, same
# pattern as visa_check.py.
_pricing = PricingService()

# The two exact price-catalogue keys this pilot ever quotes (see
# backend/data/bali_zero_official_prices_2026.json). `PricingService.search_service`
# does a broad keyword match — both rows surface for EITHER hint because they
# share the "B1 Visa on Arrival" prefix — so `_best_pricing_candidate` (the
# precedent's own disambiguation logic, reused here rather than reinvented)
# is what actually picks the right one.
_ISSUANCE_PRICE_HINT = "B1 Visa on Arrival (VOA)"
_EXTENSION_PRICE_HINT = "B1 Visa on Arrival Extension"


def _price_for_case(case_type: CaseType) -> tuple[int | None, str | None]:
    """Server-side price lookup via `PricingService` — exactly the pattern
    `visa_check/pricing_bridge.py::estimate_match_cost` uses, specialised to
    the one known VisaType.B1 hint pair (issuance vs extension) instead of
    the generic per-VisaType hint table (B1 alone has 2 price rows, one per
    case_type, which the generic table does not distinguish)."""
    hint = _EXTENSION_PRICE_HINT if case_type is CaseType.EXTENSION else _ISSUANCE_PRICE_HINT
    results = _pricing.search_service(hint)
    if not isinstance(results, dict):
        return None, None
    services = results.get("results") or results.get("services") or results
    candidate = _best_pricing_candidate(services, hint)
    if candidate is None:
        logger.warning("garuda_voa: no price match for hint=%s", hint)
        return None, None
    return candidate


# ============================================================
# Pydantic models
# ============================================================


class VoaRequest(BaseModel):
    case_type: CaseType
    nationality: str = Field(..., min_length=3, max_length=3)
    entry_date: date
    passport_expiry_date: date
    purpose: Purpose
    travellers: int = Field(..., ge=1, le=10)
    self_pay: bool
    voa_expiry_date: date | None = None  # required iff case_type == extension
    extension_already_used: bool = False

    @field_validator("nationality")
    @classmethod
    def _normalise_iso(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("entry_date")
    @classmethod
    def _entry_date_reasonable(cls, v: date) -> date:
        today = date.today()
        if (today - v).days > 365 * 3:
            raise ValueError("entry_date too far in the past (>3 years)")
        if (v - today).days > 365:
            raise ValueError("entry_date cannot be more than 1 year in the future")
        return v

    @model_validator(mode="after")
    def _extension_requires_voa_expiry(self) -> VoaRequest:
        if self.case_type is CaseType.EXTENSION and self.voa_expiry_date is None:
            raise ValueError("voa_expiry_date is required for an extension case")
        return self


class VoaResponse(BaseModel):
    """Client-facing verdict. Deliberately has NO field for the D-14
    filing-window-opens date, nor for the D-10/D-3/D-1 internal
    checkpoints — `published_filing_deadline` (D-7) is the ONLY Safe Clock
    date this schema can ever carry. D-14 is withheld not because it is
    internal but because the source is self-contradictory on it (see the
    module docstring above); D-7 is stated identically everywhere and is
    not in doubt.

    Same treatment for decline reasons: `reason_codes` carries ONLY the
    stable neutral codes from `services.garuda_flow.eligibility.DeclineCode`
    — never the engine-internal English audit prose
    (`VoaVerdict.decline_reasons`), which can name an internal checkpoint
    (e.g. "D-10 pilot threshold") and is never translated. That prose is
    still persisted server-side for audit; it has no field here."""

    hash: str
    decision: str  # "ACCEPT" | "DECLINE"
    reason_codes: list[str]
    case_type: CaseType
    nationality: str
    entry_date: date
    expiry_date: date
    last_legal_day: date
    expiry_is_estimated: bool
    published_filing_deadline: date  # D-7 — published Ngurah Rai filing deadline
    # Issuance-only (owner ruling 2026-07-27): Bali Zero's OWN submit-by
    # commitment for the online funnel — never a government deadline. None
    # for extension cases, and for an issuance case whose entry_date falls
    # past the decreed 2026 calendar (fail-closed, never guessed).
    submit_by_date: date | None
    price_idr: int | None
    price_source: str | None
    result_url: str


# ============================================================
# Helpers
# ============================================================


def _build_response(saved: VoaCheckResult) -> VoaResponse:
    return VoaResponse(
        hash=saved.hash,
        decision=saved.decision.value,
        reason_codes=saved.decline_codes,
        case_type=saved.case_type,
        nationality=saved.nationality,
        entry_date=saved.entry_date,
        expiry_date=saved.expiry_date,
        last_legal_day=saved.last_legal_day,
        expiry_is_estimated=saved.expiry_is_estimated,
        published_filing_deadline=saved.published_filing_deadline,
        submit_by_date=saved.submit_by_date,
        price_idr=saved.price_idr,
        price_source=saved.price_source,
        result_url=f"/visa/voa/{saved.hash}",
    )


# ============================================================
# Endpoints
# ============================================================


@router.post("/voa", response_model=VoaResponse, status_code=201)
async def submit_voa(
    payload: VoaRequest,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> VoaResponse:
    intake = VoaIntakeRequest(
        case_type=payload.case_type,
        nationality=payload.nationality,
        entry_date=payload.entry_date,
        passport_expiry_date=payload.passport_expiry_date,
        purpose=payload.purpose,
        travellers=payload.travellers,
        self_pay=payload.self_pay,
        voa_expiry_date=payload.voa_expiry_date,
        extension_already_used=payload.extension_already_used,
    )
    verdict = build_verdict(intake, today=date.today())
    price_idr, price_source = _price_for_case(payload.case_type)

    repo = GarudaVoaRepository(db_pool)
    try:
        saved = await repo.save_voa_check(
            case_type=payload.case_type,
            nationality=payload.nationality,
            entry_date=payload.entry_date,
            passport_expiry_date=payload.passport_expiry_date,
            voa_expiry_date=payload.voa_expiry_date,
            extension_already_used=payload.extension_already_used,
            purpose=payload.purpose,
            travellers=payload.travellers,
            self_pay=payload.self_pay,
            decision=verdict.decision,
            decline_reasons=verdict.decline_reasons,
            decline_codes=verdict.decline_codes,
            expiry_date=verdict.stay_window.expiry_date,
            last_legal_day=verdict.stay_window.last_legal_day,
            expiry_is_estimated=verdict.stay_window.expiry_is_estimated,
            published_filing_deadline=verdict.published_filing_deadline,
            submit_by_date=verdict.submit_by_date,
            price_idr=price_idr,
            price_source=price_source,
        )
    except (asyncpg.PostgresError, asyncpg.InterfaceError):
        logger.exception("garuda_voa: DB insert failed")
        raise HTTPException(status_code=500, detail="Could not save VOA check")

    return _build_response(saved)


@router.get("/voa/{hash}", response_model=VoaResponse)
async def get_voa(
    hash: str = Path(..., min_length=8, max_length=20),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> VoaResponse:
    repo = GarudaVoaRepository(db_pool)
    try:
        saved = await repo.get_voa_check(hash)
        if saved is not None:
            await repo.bump_view_count(hash)
    except (asyncpg.PostgresError, asyncpg.InterfaceError):
        logger.exception("garuda_voa: DB read failed for hash=%s", hash)
        raise HTTPException(status_code=500, detail="Could not load VOA check")
    if not saved:
        raise HTTPException(status_code=404, detail="VOA check not found")
    return _build_response(saved)
