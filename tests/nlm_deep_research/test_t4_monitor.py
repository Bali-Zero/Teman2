"""Tests for T4Monitor fetch layer (mocked HTTP)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import Article, T4Fetcher


RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Kantor Imigrasi Ngurah Rai</title>
    <link>https://ngurahrai.imigrasi.go.id</link>
    <item>
      <title>Imigrasi Ngurah Rai Deportasi WN Korea</title>
      <link>https://ngurahrai.imigrasi.go.id/berita/deportasi-korea</link>
      <description>WN Korea Selatan dideportasi akibat overstay 60 hari.</description>
      <pubDate>Thu, 26 Mar 2026 10:00:00 +0800</pubDate>
      <guid>https://ngurahrai.imigrasi.go.id/berita/deportasi-korea</guid>
    </item>
    <item>
      <title>Timpora Kuta Selatan Perkuat Pengawasan WNA</title>
      <link>https://ngurahrai.imigrasi.go.id/berita/timpora-kuta</link>
      <description>Operasi timpora dilakukan untuk menekan angka overstay.</description>
      <pubDate>Wed, 25 Mar 2026 08:00:00 +0800</pubDate>
      <guid>https://ngurahrai.imigrasi.go.id/berita/timpora-kuta</guid>
    </item>
  </channel>
</rss>"""


class TestT4FetcherRSS:
    @pytest.mark.asyncio
    async def test_fetch_rss_returns_articles(self):
        fetcher = T4Fetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = RSS_SAMPLE
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            articles = await fetcher.fetch_rss(
                "https://ngurahrai.imigrasi.go.id/feed/",
                source_handle="imngurahrai",
            )

        assert len(articles) == 2
        assert all(isinstance(a, Article) for a in articles)
        assert articles[0].title == "Imigrasi Ngurah Rai Deportasi WN Korea"
        assert articles[0].platform == "rss"
        assert articles[0].article_id != ""

    @pytest.mark.asyncio
    async def test_fetch_rss_http_error_returns_empty(self):
        fetcher = T4Fetcher()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
            mock_client_cls.return_value = mock_client

            articles = await fetcher.fetch_rss(
                "https://bad-url.example.com/feed/",
                source_handle="bad",
            )

        assert articles == []

    @pytest.mark.asyncio
    async def test_article_id_is_url_hash(self):
        fetcher = T4Fetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = RSS_SAMPLE
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            articles = await fetcher.fetch_rss(
                "https://ngurahrai.imigrasi.go.id/feed/",
                source_handle="imngurahrai",
            )

        expected_id = hashlib.sha1(
            articles[0].url.encode()
        ).hexdigest()[:16]
        assert articles[0].article_id == expected_id
