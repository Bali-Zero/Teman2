"""
Tests for backend.services.scraping.url_scraper (TODO #78).

The scraper backs the POST /api/dream/scrape endpoint. It must:
- fetch the URL via shared httpx client (timeout 10s default),
- extract <title>, <p> tags as keyPoints, <blockquote> as quotes,
- strip <script>/<style> noise,
- reject non-http(s) URLs (basic SSRF defense),
- never crash the request on HTTP failure (return success=False).

No paid Firecrawl dependency.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.services.scraping.url_scraper import (
    ScrapedContent,
    scrape_url,
)


@pytest.mark.asyncio
async def test_url_scraper_extracts_title() -> None:
    html = "<html><head><title>Hello World</title></head><body></body></html>"
    response = httpx.Response(200, text=html, request=httpx.Request("GET", "https://x.com"))

    mock_client = AsyncMock()
    mock_client.get.return_value = response

    with patch(
        "backend.services.scraping.url_scraper._get_http_client",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await scrape_url("https://example.com")

    assert isinstance(result, ScrapedContent)
    assert result.success is True
    assert result.title == "Hello World"


@pytest.mark.asyncio
async def test_url_scraper_extracts_paragraphs_as_key_points() -> None:
    html = """
    <html><head><title>x</title></head><body>
      <p>First paragraph.</p>
      <p>Second paragraph.</p>
      <p>Third.</p>
      <p>Fourth.</p>
      <p>Fifth.</p>
      <p>Sixth — should be dropped.</p>
    </body></html>
    """
    response = httpx.Response(200, text=html, request=httpx.Request("GET", "https://x.com"))
    mock_client = AsyncMock()
    mock_client.get.return_value = response
    with patch(
        "backend.services.scraping.url_scraper._get_http_client",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await scrape_url("https://example.com")

    # First 5 paragraphs only (UX cap — Dream Room shows a small ribbon).
    assert len(result.keyPoints) == 5
    assert result.keyPoints[0] == "First paragraph."
    assert result.keyPoints[-1] == "Fifth."


@pytest.mark.asyncio
async def test_url_scraper_extracts_blockquotes_as_quotes() -> None:
    html = """
    <html><body>
      <blockquote cite="Plato">The unexamined life is not worth living.</blockquote>
      <blockquote>Anonymous wisdom.</blockquote>
    </body></html>
    """
    response = httpx.Response(200, text=html, request=httpx.Request("GET", "https://x.com"))
    mock_client = AsyncMock()
    mock_client.get.return_value = response
    with patch(
        "backend.services.scraping.url_scraper._get_http_client",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await scrape_url("https://example.com")

    assert len(result.quotes) == 2
    assert result.quotes[0]["text"] == "The unexamined life is not worth living."
    assert result.quotes[0]["author"] == "Plato"
    assert result.quotes[1]["text"] == "Anonymous wisdom."
    assert result.quotes[1]["author"] == "Unknown"


@pytest.mark.asyncio
async def test_url_scraper_strips_scripts_and_styles() -> None:
    html = """
    <html><body>
      <script>alert('xss')</script>
      <style>.x{color:red}</style>
      <p>Real content.</p>
    </body></html>
    """
    response = httpx.Response(200, text=html, request=httpx.Request("GET", "https://x.com"))
    mock_client = AsyncMock()
    mock_client.get.return_value = response
    with patch(
        "backend.services.scraping.url_scraper._get_http_client",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await scrape_url("https://example.com")

    assert result.keyPoints == ["Real content."]
    # Script + style content must never leak into the response.
    assert all("alert" not in kp for kp in result.keyPoints)


@pytest.mark.asyncio
async def test_url_scraper_rejects_non_http_url() -> None:
    with pytest.raises(ValueError, match="http"):
        await scrape_url("file:///etc/passwd")
    with pytest.raises(ValueError, match="http"):
        await scrape_url("javascript:alert(1)")
    with pytest.raises(ValueError, match="http"):
        await scrape_url("")


@pytest.mark.asyncio
async def test_url_scraper_handles_http_error_gracefully() -> None:
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPError("connection refused")
    with patch(
        "backend.services.scraping.url_scraper._get_http_client",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await scrape_url("https://example.com")

    assert result.success is False
    assert result.title == ""
    assert result.keyPoints == []
    assert result.quotes == []


@pytest.mark.asyncio
async def test_url_scraper_handles_404_gracefully() -> None:
    response = httpx.Response(404, request=httpx.Request("GET", "https://x.com"))
    mock_client = AsyncMock()
    mock_client.get.return_value = response
    with patch(
        "backend.services.scraping.url_scraper._get_http_client",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await scrape_url("https://example.com")

    assert result.success is False


@pytest.mark.asyncio
async def test_url_scraper_handles_missing_title() -> None:
    html = "<html><body><p>No title here.</p></body></html>"
    response = httpx.Response(200, text=html, request=httpx.Request("GET", "https://x.com"))
    mock_client = AsyncMock()
    mock_client.get.return_value = response
    with patch(
        "backend.services.scraping.url_scraper._get_http_client",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await scrape_url("https://example.com")

    # Missing title falls back to the URL — keeps the contract `title: str` honest.
    assert result.success is True
    assert result.title == "https://example.com"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
