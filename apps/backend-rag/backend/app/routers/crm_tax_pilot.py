"""Read-only CRM tax company pilot endpoints."""

from fastapi import APIRouter, HTTPException, Query

from backend.services.crm.tax_company_pilot import TaxCompanyPilotMap, get_tax_company_pilot_map

router = APIRouter(prefix="/api/crm/pilot", tags=["crm-pilot"])


@router.get("/tax-company-map", response_model=TaxCompanyPilotMap)
async def get_tax_company_pilot(
    company: str = Query(..., min_length=1, description="Pilot key: ocean or bimala"),
) -> TaxCompanyPilotMap:
    """Return one read-only tax company pilot map."""
    pilot_map = get_tax_company_pilot_map(company)
    if pilot_map is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tax company pilot: {company}",
        )
    return pilot_map
