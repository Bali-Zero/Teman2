"""Tests for T4Monitor fetch layer (mocked HTTP)."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import (
    Article,
    FilterResult,
    Post,
    T4Fetcher,
    T4Monitor,
    T4RelevanceFilter,
)
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


# ---------------------------------------------------------------------------
# T4-monitor-cure (2026-07-16): classifier honesty.
#
# Root cause of the 3-week admit=0 incident: the cron ran without
# CLAUDE_CODE_OAUTH_TOKEN in its env, `claude -p` fell back to the
# macOS-Keychain-stored token (inaccessible headlessly), exited non-zero on
# every call, and _haiku_classify defaulted to a FABRICATED 0.0 — read by
# classify() as a genuine "irrelevant" verdict, REJECTing every article that
# had already passed the L1 keyword gate. The cure: _haiku_classify/
# layer3_haiku return Optional[float] (None on failure, never 0.0), and
# classify() fails OPEN to ADMIT on None (L1 already filtered), tracking the
# fail-open so a fully-blind run can be flagged DEGRADED in the summary.
# ---------------------------------------------------------------------------


class TestHaikuClassifyHonesty:
    """Guilt+innocence for _haiku_classify's None-vs-fabricated-0.0 contract."""

    @pytest.mark.asyncio
    async def test_timeout_returns_none_not_zero(self):
        filt = T4RelevanceFilter()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            score = await filt._haiku_classify("some article text")
        assert score is None

    @pytest.mark.asyncio
    async def test_nonzero_exit_returns_none_not_zero(self):
        """guilt: this is the exact failure mode of the 3-week incident —
        `claude -p` exits 1 ("Not logged in") under a headless Keychain."""
        filt = T4RelevanceFilter()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"Not logged in"))
        mock_proc.returncode = 1
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            score = await filt._haiku_classify("some article text")
        assert score is None

    @pytest.mark.asyncio
    async def test_unparseable_output_returns_none_not_zero(self):
        filt = T4RelevanceFilter()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"I cannot compute a score.", b""))
        mock_proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            score = await filt._haiku_classify("some article text")
        assert score is None

    @pytest.mark.asyncio
    async def test_verbose_output_extracts_leading_float(self):
        """innocence: a real, parseable score is never coerced to None."""
        filt = T4RelevanceFilter()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"0.85\n\nExplanation: highly relevant enforcement news.", b"")
        )
        mock_proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            score = await filt._haiku_classify("some article text")
        assert score == 0.85

    @pytest.mark.asyncio
    async def test_clean_float_output_returns_score(self):
        """innocence: the common-case exact-float response still works."""
        filt = T4RelevanceFilter()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"0.0\n", b""))
        mock_proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            score = await filt._haiku_classify("some article text")
        assert score == 0.0


class TestClassifyFailOpen:
    """Guilt+innocence for classify()'s fail-open-on-unavailable contract."""

    @pytest.mark.asyncio
    async def test_l1_positive_classifier_unavailable_fails_open_to_admit(self):
        """guilt: before this cure, classifier-unavailable == fabricated 0.0 ==
        always REJECT. After: L1-positive + classifier None -> ADMIT, tracked."""
        filt = T4RelevanceFilter()
        with patch.object(filt, "_haiku_classify", new=AsyncMock(return_value=None)):
            result = await filt.classify("Deportasi WNA overstay di Bali")
        assert result == FilterResult.ADMIT
        assert filt.classifier_unavailable_count == 1
        assert filt.classifier_attempts == 1

    @pytest.mark.asyncio
    async def test_l1_positive_real_zero_score_still_rejected(self):
        """innocence: a REAL 0.0 verdict (classifier ran fine, scored low) must
        still REJECT — fail-open only covers unavailability, not low scores."""
        filt = T4RelevanceFilter()
        with patch.object(filt, "_haiku_classify", new=AsyncMock(return_value=0.0)):
            result = await filt.classify("Deportasi WNA overstay di Bali")
        assert result == FilterResult.REJECT
        assert filt.classifier_unavailable_count == 0
        assert filt.classifier_attempts == 1

    @pytest.mark.asyncio
    async def test_l1_negative_never_invokes_haiku(self):
        """innocence: text that fails the keyword gate must not even attempt
        the classifier (no attempt = no possible fail-open)."""
        filt = T4RelevanceFilter()
        mock_haiku = AsyncMock(return_value=0.9)
        with patch.object(filt, "_haiku_classify", new=mock_haiku):
            result = await filt.classify("Harga properti Bali naik tahun ini")
        assert result == FilterResult.REJECT
        mock_haiku.assert_not_called()
        assert filt.classifier_attempts == 0
        assert filt.classifier_unavailable_count == 0


class TestT4RunDegradedSummary:
    """The EMENDAMENTO: a fully-blind run (every Haiku attempt failed) must
    say so explicitly in the summary, not just log a per-article warning —
    3 weeks of invisible per-article warnings is what caused this incident to
    go unnoticed in the first place."""

    @pytest.mark.asyncio
    async def test_run_flags_degraded_when_every_attempt_fails(self, tmp_path, caplog, monkeypatch):
        monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
        monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=False)
        rss_article = Article(
            source_handle="imngurahrai",
            article_id="rss-blind-1",
            url="https://ngurahrai.imigrasi.go.id/berita/deportasi-2",
            title="Deportasi WNA 2",
            content="Timpora deportasi WNA overstay.",
            scraped_at=datetime.now(timezone.utc),
            platform="rss",
        )
        with patch.object(T4Fetcher, "fetch_rss", new=AsyncMock(return_value=[rss_article])), \
             patch.object(T4Fetcher, "fetch_website", new=AsyncMock(return_value=[])), \
             patch.object(T4RelevanceFilter, "_haiku_classify", new=AsyncMock(return_value=None)), \
             patch.object(T4RelevanceFilter, "_embed", new=AsyncMock(side_effect=RuntimeError("no key in test"))), \
             patch.object(T4Monitor, "_call_nlm_cli", new=AsyncMock(return_value=True)), \
             caplog.at_level(logging.INFO, logger="apps.evaluator.nlm_deep_research.t4_monitor"):
            result = await monitor.run()

        assert result.classifier_unavailable == 1
        assert result.ingested == 1  # fail-open admitted it (already L1-positive)
        assert "(DEGRADED)" in caplog.text

    @pytest.mark.asyncio
    async def test_run_not_degraded_when_classifier_healthy(self, tmp_path, caplog, monkeypatch):
        """innocence: a healthy run (classifier answers) must never be
        flagged DEGRADED, even though it also ends up admitting."""
        monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
        monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=False)
        rss_article = Article(
            source_handle="imngurahrai",
            article_id="rss-healthy-1",
            url="https://ngurahrai.imigrasi.go.id/berita/deportasi-3",
            title="Deportasi WNA 3",
            content="Timpora deportasi WNA overstay.",
            scraped_at=datetime.now(timezone.utc),
            platform="rss",
        )
        with patch.object(T4Fetcher, "fetch_rss", new=AsyncMock(return_value=[rss_article])), \
             patch.object(T4Fetcher, "fetch_website", new=AsyncMock(return_value=[])), \
             patch.object(T4RelevanceFilter, "_haiku_classify", new=AsyncMock(return_value=0.9)), \
             patch.object(T4RelevanceFilter, "_embed", new=AsyncMock(side_effect=RuntimeError("no key in test"))), \
             patch.object(T4Monitor, "_call_nlm_cli", new=AsyncMock(return_value=True)), \
             caplog.at_level(logging.INFO, logger="apps.evaluator.nlm_deep_research.t4_monitor"):
            result = await monitor.run()

        assert result.classifier_unavailable == 0
        assert result.ingested == 1
        assert "(DEGRADED)" not in caplog.text


class TestWebsiteErrorDoesNotBlockRSSIngestion:
    @pytest.mark.asyncio
    async def test_website_connect_error_does_not_block_rss_ingestion(self, tmp_path, monkeypatch):
        """A website source being down must not starve ingestion from a
        healthy RSS source (root-cause item 3's secondary symptom).

        fetch_rss is stubbed directly rather than exercised through httpx:
        feedparser is not installed in this venv (pre-existing, unrelated
        environment gap — out of scope for this cure) so the real fetch_rss
        path is untestable here regardless of this fix.
        """
        monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
        monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=False)
        rss_article = Article(
            source_handle="imngurahrai",
            article_id="rss-ok-1",
            url="https://ngurahrai.imigrasi.go.id/berita/deportasi-4",
            title="Deportasi WNA 4",
            content="Timpora deportasi WNA overstay.",
            scraped_at=datetime.now(timezone.utc),
            platform="rss",
        )

        async def _website_get(url, **kwargs):
            raise httpx.ConnectError("website down")

        with patch.object(T4Fetcher, "fetch_rss", new=AsyncMock(return_value=[rss_article])), \
             patch("httpx.AsyncClient") as mock_client_cls, \
             patch.object(T4RelevanceFilter, "_haiku_classify", new=AsyncMock(return_value=0.9)), \
             patch.object(T4RelevanceFilter, "_embed", new=AsyncMock(side_effect=RuntimeError("no key in test"))), \
             patch.object(T4Monitor, "_call_nlm_cli", new=AsyncMock(return_value=True)):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = _website_get
            mock_client_cls.return_value = mock_client

            result = await monitor.run()

        assert result.ingested >= 1
        assert result.errors == 0
