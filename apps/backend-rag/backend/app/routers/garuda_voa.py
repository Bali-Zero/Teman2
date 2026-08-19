"""GARUDA VOA owner-only historical archive.

GET /api/visa/voa/{hash} reads a row created by the retired public prototype.
There is deliberately no POST route: the active owner workbench uses the
stateless ``services.garuda_flow.internal_preview_cli`` and must not create
archive rows.  The archive GET requires the existing owner dependency, is
hidden from OpenAPI, and is absent from ``backend/app/auth/public_endpoints``;
a result hash is an identifier, never an authentication token.

Archive serialization boundary: only ONE Safe Clock date may be returned —
`published_filing_deadline` (D-7), "paling
lambat 7 hari sebelum masa izin tinggal berakhir", worded identically
everywhere on ngurahrai.imigrasi.go.id. The D-14 filing-window-OPENS date
is deliberately NOT exposed here: that same page states it two
incompatible ways in the same breath — "paling cepat 14 hari sebelum ...
habis" (14 days before expiry) vs. "paling cepat 14 hari setelah
kedatangan" (14 days after arrival) — different dates on a 30-day B1. We
do not serialize, as an official rule, a date the official source itself
cannot agree on. D-10/D-3/D-1 remain purely internal for an unrelated
reason (pilot conservatism, never an external rule). `VoaResponse`
structurally has no field for any of the four — there is no way to
serialize them by accident (see `services.garuda_flow.intake.VoaVerdict`
for the accessor that encodes this split on the object itself). The
engine still computes the D-14 reading internally for staff
(`safe_clock.filing_window_opens_for`) — it just never crosses the wire.

The same boundary applies to decline REASONS, not just dates. Historical
rows created by the retired public prototype may contain English decline
prose in `garuda_voa_checks.decline_reasons`, including internal-checkpoint
wording. This read-only archive never exposes that prose. `VoaResponse`
instead carries `reason_codes: list[str]` — stable, neutral,
language-agnostic machine codes
(`services.garuda_flow.eligibility.DeclineCode`) — and has no raw-prose
`reasons` field. The former public result pages are retired; the neutral
codes remain available only in the authenticated owner archive.

Issuance-only submission-window gate (owner ruling 2026-07-27,
`services.garuda_flow.operating_calendar`): a VOA is issued in a few
hours, so an issuance request is accepted up to the day BEFORE arrival —
Bali Zero's systems being closed weekends and Indonesian national
holidays/cuti bersama. This SUPERSEDES the charter's blanket "urgent case"
exclusion FOR ISSUANCE ONLY; extensions are untouched (in-person
photo/interview since 29 May 2025, own runway gate — now identical to the
published D-7 filing deadline itself, owner ruling 2026-07-27, see
`services.garuda_flow.eligibility.screen`). Two neutral, routing-worded
decline codes
(`DeclineCode.ARRIVAL_TOO_SOON` / `DeclineCode.ARRIVAL_DATE_UNCONFIRMED`)
join the wire-safe set above. `VoaResponse.submit_by_date` carries the one
date this archive can carry — Bali Zero's OWN operational
commitment, never a government deadline — and is `None` when the historical
calculation fell outside materialized calendar coverage. No guessed date is
published.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict

from backend.app.dependencies import get_database_pool
from backend.app.deps.owner import require_owner
from backend.app.utils.logging_utils import get_logger
from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_flow.repository import (
    GarudaVoaRepository,
    VoaCheckResult,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/visa",
    tags=["garuda-voa"],
    include_in_schema=False,
)

# ============================================================
# Pydantic models
# ============================================================


class VoaResponse(BaseModel):
    """Owner-archive verdict. Deliberately has NO field for the D-14
    filing-window-opens date, nor for the D-10/D-3/D-1 internal
    checkpoints — `published_filing_deadline` (D-7) is the ONLY Safe Clock
    date this schema can ever carry. D-14 is withheld not because it is
    internal but because the source is self-contradictory on it (see the
    module docstring above); D-7 is stated identically everywhere and is
    not in doubt.

    Same treatment for decline reasons: `reason_codes` carries ONLY the
    stable neutral codes from `services.garuda_flow.eligibility.DeclineCode`.
    Historical rows may still contain legacy English decline prose, including
    internal-checkpoint wording, but this read-only response has no field for
    it and never exposes it."""

    model_config = ConfigDict(extra="forbid")

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
    # commitment recorded by the retired funnel — never a government deadline. None
    # for extension cases, and when the historical issuance calculation was
    # outside the materialized operating-calendar coverage.
    submit_by_date: date | None
    price_idr: int | None
    price_source: str | None


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
    )


# ============================================================
# Endpoints
# ============================================================


@router.get("/voa/{hash}", response_model=VoaResponse)
async def get_voa(
    hash: str = Path(..., min_length=8, max_length=20),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    _owner: dict[str, Any] = Depends(require_owner),
) -> VoaResponse:
    repo = GarudaVoaRepository(db_pool)
    try:
        saved = await repo.get_voa_check(hash)
    except (asyncpg.PostgresError, asyncpg.InterfaceError):
        logger.exception("garuda_voa: DB read failed for hash=%s", hash)
        raise HTTPException(status_code=500, detail="Could not load VOA check")
    if not saved:
        raise HTTPException(status_code=404, detail="VOA check not found")
    return _build_response(saved)
