from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_get_evidence_dossiers_returns_service_result() -> None:
    from backend.app.routers.crm_intelligence import get_evidence_dossiers
    from backend.services.crm.tax_company_pilot import get_tax_company_pilot_map

    pilot = get_tax_company_pilot_map("ocean")
    assert pilot is not None

    with patch(
        "backend.app.routers.crm_intelligence.build_evidence_dossiers",
        new=AsyncMock(return_value=[pilot]),
    ) as build:
        result = await get_evidence_dossiers(
            company=["ocean"],
            limit=5,
            pool=MagicMock(),
            _current_user={"email": "team@balizero.com", "role": "team"},
        )

    assert result == [pilot]
    build.assert_awaited_once()
    assert build.await_args.kwargs["companies"] == ["ocean"]
    assert build.await_args.kwargs["limit"] == 5


def test_evidence_dossiers_dependency_rejects_client_role() -> None:
    from backend.app.dependencies import require_team_member

    with pytest.raises(HTTPException) as exc:
        require_team_member({"email": "client@example.com", "role": "client"})

    assert exc.value.status_code == 403
