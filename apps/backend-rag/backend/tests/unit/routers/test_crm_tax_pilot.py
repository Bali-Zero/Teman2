import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_get_tax_company_pilot_returns_ocean_map() -> None:
    from backend.app.routers.crm_tax_pilot import get_tax_company_pilot

    pilot_map = await get_tax_company_pilot(company="ocean")

    assert pilot_map.company.name == "OCEAN CLOTHES AND SHOES PT"
    assert pilot_map.tax_member.name == "DEA"
    assert pilot_map.read_only is True


@pytest.mark.asyncio
async def test_get_tax_company_pilot_rejects_unknown_company() -> None:
    from backend.app.routers.crm_tax_pilot import get_tax_company_pilot

    with pytest.raises(HTTPException) as exc_info:
        await get_tax_company_pilot(company="unknown")

    assert exc_info.value.status_code == 404
    assert "Unknown tax company pilot" in str(exc_info.value.detail)
