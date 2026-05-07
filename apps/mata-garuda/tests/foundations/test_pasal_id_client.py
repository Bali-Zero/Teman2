import pytest
from unittest.mock import AsyncMock, patch
from mata_garuda.foundations.pasal_id_client import (
    PasalIdClient,
    LawSearchResult,
    LawStatus,
    PasalIdAuthError,
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


@pytest.mark.asyncio
async def test_search_laws_parses_nested_work_shape():
    """External-review fix (Codex 2026-05-08): live API nests title/year/type
    under `work`. Parser must tolerate both flat and nested shapes."""
    fake_response = {
        "results": [
            {
                "id": "uu-2022-27",
                "work": {
                    "title": "UU 27/2022 PDP",
                    "year": 2022,
                    "type": "UU",
                },
            }
        ]
    }
    with patch("mata_garuda.foundations.pasal_id_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        resp = mock_client.get.return_value
        resp.status_code = 200
        resp.json = lambda: fake_response
        resp.raise_for_status = lambda: None
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = PasalIdClient(api_token="fake-token")
        results = await client.search_laws(query="PDP")

    assert len(results) == 1
    assert results[0].title == "UU 27/2022 PDP"
    assert results[0].year == 2022
    assert results[0].kind == "UU"


@pytest.mark.asyncio
async def test_search_laws_raises_pasal_id_auth_error_on_401():
    """External-review fix: 401 must surface as PasalIdAuthError, not a generic
    httpx.HTTPStatusError. This makes ingestion pipelines fail fast with a
    clear message instead of crashing on raise_for_status."""
    with patch("mata_garuda.foundations.pasal_id_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        resp = mock_client.get.return_value
        resp.status_code = 401
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = PasalIdClient()  # no token
        with pytest.raises(PasalIdAuthError, match="auth failed"):
            await client.search_laws(query="anything")


@pytest.mark.asyncio
async def test_search_laws_sends_bearer_token_when_set():
    fake_response = {"results": []}
    with patch("mata_garuda.foundations.pasal_id_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        resp = mock_client.get.return_value
        resp.status_code = 200
        resp.json = lambda: fake_response
        resp.raise_for_status = lambda: None
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = PasalIdClient(api_token="my-token")
        await client.search_laws(query="visa")

        call_kwargs = mock_client.get.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer my-token"


@pytest.mark.asyncio
async def test_search_laws_handles_explicit_null_work_field():
    """Wave 2 fix (DeepSeek W2 + Codex W2 2026-05-08): old fallback
    `item.get("work", item)` returns None when JSON has explicit
    `"work": null`, then `.get()` crashes with AttributeError. New code
    must fall back to top-level fields cleanly."""
    fake_response = {
        "results": [
            {
                "id": "uu-2022-27",
                "work": None,  # explicit null — must not crash
                "title": "UU 27/2022 PDP (flat fallback)",
                "year": 2022,
                "kind": "UU",
            }
        ]
    }
    with patch("mata_garuda.foundations.pasal_id_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        resp = mock_client.get.return_value
        resp.status_code = 200
        resp.json = lambda: fake_response
        resp.raise_for_status = lambda: None
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = PasalIdClient()
        results = await client.search_laws(query="PDP")

    assert len(results) == 1
    assert results[0].title == "UU 27/2022 PDP (flat fallback)"
    assert results[0].year == 2022
