import pytest
from unittest.mock import AsyncMock, patch
from mata_garuda.foundations.opensanctions_id import (
    OpenSanctionsClient,
    SanctionEntity,
)


@pytest.mark.asyncio
async def test_fetch_dttot_dataset_returns_entities():
    fake_jsonlines = (
        '{"id":"id-dttot-1","schema":"Person","caption":"Suspected Person 1",'
        '"properties":{"name":["Suspected Person 1"]}}\n'
        '{"id":"id-dttot-2","schema":"Person","caption":"Suspected Person 2",'
        '"properties":{"name":["Suspected Person 2"]}}\n'
    )
    with patch("mata_garuda.foundations.opensanctions_id.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value.text = fake_jsonlines
        mock_client.get.return_value.raise_for_status = lambda: None
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = OpenSanctionsClient()
        entities = await client.fetch_dttot()

    assert len(entities) == 2
    assert isinstance(entities[0], SanctionEntity)
    assert entities[0].id == "id-dttot-1"


@pytest.mark.asyncio
async def test_match_entity_by_name_substring():
    fake_jsonlines = (
        '{"id":"id-dttot-1","schema":"Person","caption":"Marina Pinyaylova",'
        '"properties":{"name":["Marina Pinyaylova"]}}\n'
        '{"id":"id-dttot-2","schema":"Person","caption":"Other",'
        '"properties":{"name":["Other Person"]}}\n'
    )
    with patch("mata_garuda.foundations.opensanctions_id.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value.text = fake_jsonlines
        mock_client.get.return_value.raise_for_status = lambda: None
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = OpenSanctionsClient()
        matches = await client.match_name("Marina")

    assert len(matches) == 1
    assert matches[0].caption == "Marina Pinyaylova"
