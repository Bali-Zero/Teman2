"""Unit tests for T4 SVS scoring."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import Article, T4SVSScorer


def make_article(**kwargs) -> Article:
    defaults = dict(
        source_handle="imngurahrai",
        article_id="abc123",
        url="https://ngurahrai.imigrasi.go.id/berita/1",
        title="Imigrasi Ngurah Rai Deportasi WN Korea",
        content="Timpora razia overstay WNA Korea daftar cekal.",
        scraped_at=datetime.now(timezone.utc),
        platform="rss",
    )
    defaults.update(kwargs)
    return Article(**defaults)


class TestT4SVSScorer:
    def test_enforcement_article_scores_above_threshold(self):
        scorer = T4SVSScorer()
        article = make_article(
            title="Imigrasi Deportasi 5 WNA Overstay",
            content="Timpora razia wna blacklist cegah tangkal deportasi."
        )
        score = scorer.score(article)
        assert score >= 0.35

    def test_ceremony_article_scores_below_threshold(self):
        scorer = T4SVSScorer()
        article = make_article(
            title="Selamat Ulang Tahun Imigrasi ke-73",
            content="Acara ulang tahun dihadiri seluruh pegawai kantor.",
            platform="website",
        )
        score = scorer.score(article)
        assert score < 0.35

    def test_fresh_article_scores_higher_than_old(self):
        scorer = T4SVSScorer()
        fresh = make_article(
            scraped_at=datetime.now(timezone.utc),
            content="Timpora deportasi WNA overstay",
        )
        old = make_article(
            scraped_at=datetime.now(timezone.utc) - timedelta(days=20),
            content="Timpora deportasi WNA overstay",
        )
        assert scorer.score(fresh) > scorer.score(old)

    def test_rss_source_scores_higher_than_website(self):
        scorer = T4SVSScorer()
        rss = make_article(platform="rss", content="Deportasi timpora WNA overstay")
        web = make_article(platform="website", content="Deportasi timpora WNA overstay")
        assert scorer.score(rss) >= scorer.score(web)

    def test_score_clamped_between_0_and_1(self):
        scorer = T4SVSScorer()
        article = make_article(content="timpora " * 100)
        score = scorer.score(article)
        assert 0.0 <= score <= 1.0

    def test_score_returns_float(self):
        scorer = T4SVSScorer()
        score = scorer.score(make_article())
        assert isinstance(score, float)
