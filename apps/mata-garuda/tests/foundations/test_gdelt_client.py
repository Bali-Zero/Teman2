import pytest
from unittest.mock import AsyncMock, patch
from mata_garuda.foundations.gdelt_client import (
    GdeltClient,
    GdeltArticle,
)


@pytest.mark.asyncio
async def test_search_articles_indonesia_filters_country_id():
    fake_response = {
        "articles": [
            {
                "url": "https://kompas.com/article/1",
                "title": "Kabinet reshuffle Indonesia",
                "seendate": "20260508T100000Z",
                "domain": "kompas.com",
                "language": "Indonesian",
                "sourcecountry": "Indonesia",
            }
        ]
    }
    with patch("mata_garuda.foundations.gdelt_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value.json = lambda: fake_response
        mock_client.get.return_value.raise_for_status = lambda: None
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = GdeltClient()
        articles = await client.search_indonesia(query="kabinet", max_results=10)

    assert len(articles) == 1
    assert isinstance(articles[0], GdeltArticle)
    assert articles[0].source_country == "Indonesia"


@pytest.mark.asyncio
async def test_search_articles_handles_empty_response():
    fake_response = {"articles": []}
    with patch("mata_garuda.foundations.gdelt_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value.json = lambda: fake_response
        mock_client.get.return_value.raise_for_status = lambda: None
        mock_cls.return_value.__aenter__.return_value = mock_client

        client = GdeltClient()
        articles = await client.search_indonesia(query="zzzznotrending", max_results=10)

    assert articles == []
