import pytest
from unittest.mock import AsyncMock, patch
from mata_garuda.foundations.pasal_id_client import (
    PasalIdClient,
    LawSearchResult,
    LawStatus,
)


@pytest.mark.asyncio
async def test_search_laws_returns_typed_results():
    fake_response = {
        "results": [
            {"id": "uu-2022-27", "title": "UU 27/2022 PDP", "year": 2022, "kind": "UU"}
        ],
        "total": 1,
    }
    with patch("mata_garuda.foundations.pasal_id_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value.json = lambda: fake_response
        mock_client.get.return_value.raise_for_status = lambda: None
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = PasalIdClient()
        result = await client.search_laws(query="PDP", limit=10)

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], LawSearchResult)
    assert result[0].id == "uu-2022-27"


@pytest.mark.asyncio
async def test_get_law_status_returns_active_or_superseded():
    fake_response = {
        "id": "pmk-2024-81",
        "status": "berlaku",
        "superseded_by": None,
    }
    with patch("mata_garuda.foundations.pasal_id_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value.json = lambda: fake_response
        mock_client.get.return_value.raise_for_status = lambda: None
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = PasalIdClient()
        status = await client.get_law_status(law_id="pmk-2024-81")

    assert isinstance(status, LawStatus)
    assert status.status == "berlaku"
    assert status.superseded_by is None
