"""Team-only CRM intelligence endpoints."""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Query

from backend.app.dependencies import get_database_pool, require_team_member
from backend.services.crm.evidence_dossier import build_evidence_dossiers
from backend.services.crm.tax_company_pilot import TaxCompanyPilotMap

router = APIRouter(prefix="/api/crm/intelligence", tags=["crm-intelligence"])


@router.get("/evidence-dossiers", response_model=list[TaxCompanyPilotMap])
async def get_evidence_dossiers(
    company: Annotated[
        list[str] | None,
        Query(description="Optional company filters; repeat for multiple values."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _current_user: dict = Depends(require_team_member),
) -> list[TaxCompanyPilotMap]:
    """Return person-first evidence dossiers for the team workspace."""
    return await build_evidence_dossiers(pool, companies=company, limit=limit)
