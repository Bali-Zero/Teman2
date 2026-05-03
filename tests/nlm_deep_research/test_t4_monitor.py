"""Tests for T4Monitor fetch layer (mocked HTTP)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import Article, Post, T4Fetcher, T4Monitor
from apps.evaluator.nlm_deep_research.t4_state import T4State, T4StatePersistence


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


WEBSITE_SAMPLE = """<html><body>
  <article>
    <h2><a href="/berita/timpora-bali">Timpora Bali 2026</a></h2>
    <p>Deportasi overstay wna.</p>
  </article>
  <article>
    <h2><a href="https://example.com/berita/kitas-rule">Aturan KITAS Baru</a></h2>
    <p>Peraturan imigrasi terbaru.</p>
  </article>
</body></html>"""

TWITTER_RESPONSE_USER = {"data": {"id": "12345678", "name": "Ditjen Imigrasi"}}
TWITTER_RESPONSE_TWEETS = {
    "data": [
        {"id": "99999", "text": "Timpora razia WNA overstay.", "created_at": "2026-03-28T10:00:00Z"},
        {"id": "99998", "text": "Deportasi WN Korea.", "created_at": "2026-03-27T08:00:00Z"},
    ]
}


class TestT4FetcherWebsite:
    @pytest.mark.asyncio
    async def test_fetch_website_returns_articles(self):
        fetcher = T4Fetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = WEBSITE_SAMPLE
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            articles = await fetcher.fetch_website(
                "https://ditjenimigrasi.go.id/berita/",
                source_handle="ditjen_imigrasi",
            )

        assert len(articles) == 2
        assert all(isinstance(a, Article) for a in articles)
        assert articles[0].platform == "website"
        # Relative URL should be resolved to absolute
        assert articles[0].url.startswith("https://ditjenimigrasi.go.id")

    @pytest.mark.asyncio
    async def test_fetch_website_http_error_returns_empty(self):
        fetcher = T4Fetcher()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
            mock_client_cls.return_value = mock_client

            articles = await fetcher.fetch_website(
                "https://bad.example.com/berita/",
                source_handle="bad",
            )

        assert articles == []


class TestT4FetcherTwitter:
    @pytest.mark.asyncio
    async def test_fetch_twitter_returns_posts(self):
        fetcher = T4Fetcher()

        async def _mock_get(url: str, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            if "users/by/username" in url:
                mock_resp.json = MagicMock(return_value=TWITTER_RESPONSE_USER)
            else:
                mock_resp.json = MagicMock(return_value=TWITTER_RESPONSE_TWEETS)
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = _mock_get
            mock_client_cls.return_value = mock_client

            posts = await fetcher.fetch_twitter(
                "@ditjen_imigrasi",
                bearer_token="test_bearer",
            )

        assert len(posts) == 2
        assert all(isinstance(p, Post) for p in posts)
        assert posts[0].post_id == "99999"
        assert posts[0].platform == "twitter"
        assert posts[0].timestamp is not None

    @pytest.mark.asyncio
    async def test_fetch_twitter_error_returns_empty(self):
        fetcher = T4Fetcher()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
            mock_client_cls.return_value = mock_client

            posts = await fetcher.fetch_twitter(
                "@bad_handle",
                bearer_token="test_bearer",
            )

        assert posts == []


class TestT4MonitorIngest:
    @pytest.mark.asyncio
    async def test_already_seen_article_skipped(self, tmp_path):
        state = T4State(seen_ids={"abc123"})
        persistence = T4StatePersistence(tmp_path / "state.json")
        persistence.save(state)

        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=True)
        ingested = await monitor._maybe_ingest(
            Article(
                source_handle="test",
                article_id="abc123",
                url="https://example.com/1",
                title="Test",
                content="timpora deportasi WNA",
                scraped_at=datetime.now(timezone.utc),
                platform="rss",
            )
        )
        assert ingested is False

    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_nlm(self, tmp_path):
        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=True)
        article = Article(
            source_handle="imngurahrai",
            article_id="new999",
            url="https://ngurahrai.imigrasi.go.id/berita/new",
            title="Deportasi Timpora WNA",
            content="Timpora deportasi WNA overstay visa dicabut.",
            scraped_at=datetime.now(timezone.utc),
            platform="rss",
        )
        with patch(
            "apps.evaluator.nlm_deep_research.t4_monitor.T4Monitor._call_nlm_cli",
            new=AsyncMock(return_value=True),
        ) as mock_nlm:
            await monitor._maybe_ingest(article)
        mock_nlm.assert_not_called()

    @pytest.mark.asyncio
    async def test_budget_exceeded_evicts_oldest(self, tmp_path):
        state = T4State(active_t4_sources=["s"] * 11)
        persistence = T4StatePersistence(tmp_path / "state.json")
        persistence.save(state)

        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=True)
        loaded_state = monitor._persistence.load()
        assert loaded_state.is_over_budget()
        evicted = loaded_state.evict_oldest()
        assert evicted == "s"
        assert len(loaded_state.active_t4_sources) == 10

    @pytest.mark.asyncio
    async def test_nlm_ingest_builds_correct_content_format(self, tmp_path):
        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=False)
        article = Article(
            source_handle="imngurahrai",
            article_id="x1",
            url="https://ngurahrai.imigrasi.go.id/berita/1",
            title="Deportasi WNA",
            content="Timpora razia overstay.",
            scraped_at=datetime(2026, 3, 28, 10, 0, 0, tzinfo=timezone.utc),
            platform="rss",
            svs_score=0.62,
        )
        formatted = monitor._format_for_nlm(article)
        assert "[TITLE]: Deportasi WNA" in formatted
        assert "[SOURCE]: imngurahrai" in formatted
        assert "[SVS]: 0.62" in formatted
        assert "Timpora razia overstay." in formatted
