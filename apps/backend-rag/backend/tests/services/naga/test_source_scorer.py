"""Tests for Naga source scorer — credibility + freshness + relevance scoring."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.services.naga.config import NagaConfig
from backend.services.naga.quality.source_scorer import score_source, score_sources
from backend.services.naga.search_agents.base import SearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(
    url: str = "https://example.com/page",
    title: str = "Test",
    content: str = "body",
    source_type: str | None = None,
    freshness_date: date | None = None,
    relevance_score: float = 0.0,
    metadata: dict | None = None,
) -> SearchResult:
    return SearchResult(
        url=url,
        title=title,
        content=content,
        source_type=source_type,
        freshness_date=freshness_date,
        relevance_score=relevance_score,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config() -> NagaConfig:
    return NagaConfig()


@pytest.fixture
def today() -> date:
    return date.today()


# ---------------------------------------------------------------------------
# Credibility scoring
# ---------------------------------------------------------------------------

class TestCredibilityScoring:
    """Credibility is resolved via domain_overrides > .go.id > source_type > unknown."""

    def test_gov_go_id_domain_gets_high_credibility(self, config: NagaConfig) -> None:
        """Any .go.id domain should resolve to the 'gov' default weight."""
        src = _result(url="https://pajak.go.id/info", source_type="gov")
        # pajak.go.id is an explicit override at 0.95
        s = score_source(src, relevance=0.5, config=config)
        assert s > 0.6

    def test_domain_override_takes_precedence(self, config: NagaConfig) -> None:
        """An exact domain_overrides match beats the source_type default."""
        # pajak.go.id override is 0.95 vs generic gov 0.9
        src_override = _result(url="https://pajak.go.id/info", source_type="gov")
        src_generic = _result(url="https://unknown-dept.go.id/info", source_type="gov")
        s_override = score_source(src_override, relevance=0.5, config=config)
        s_generic = score_source(src_generic, relevance=0.5, config=config)
        assert s_override >= s_generic

    def test_blog_source_gets_low_credibility(self, config: NagaConfig) -> None:
        """Blog source_type should use the 'blog' default weight (0.4)."""
        src = _result(url="https://randomblog.com/post", source_type="blog")
        s = score_source(src, relevance=0.5, config=config)
        # blog weight is 0.4 vs gov 0.9 — blog combined score should be lower
        gov_src = _result(url="https://imigrasi.go.id/info", source_type="gov")
        s_gov = score_source(gov_src, relevance=0.5, config=config)
        assert s < s_gov

    def test_academic_arxiv_gets_high_credibility(self, config: NagaConfig) -> None:
        """arxiv.org should use its domain override (0.85)."""
        src = _result(url="https://arxiv.org/abs/2401.00001", source_type="academic")
        s = score_source(src, relevance=0.5, config=config)
        # arxiv override is 0.85 — combined should be relatively high
        blog_src = _result(url="https://someblog.com/post", source_type="blog")
        s_blog = score_source(blog_src, relevance=0.5, config=config)
        assert s > s_blog

    def test_unknown_go_id_uses_gov_default(self, config: NagaConfig) -> None:
        """A .go.id domain not in overrides should fall back to 'gov' default."""
        src = _result(url="https://newagency.go.id/page", source_type=None)
        s = score_source(src, relevance=0.5, config=config)
        # gov default is 0.9 — should be decent
        unknown_src = _result(url="https://randomsite.xyz/page", source_type=None)
        s_unknown = score_source(unknown_src, relevance=0.5, config=config)
        assert s > s_unknown

    def test_no_source_type_no_match_uses_unknown(self, config: NagaConfig) -> None:
        """When source_type is None and domain has no override, use 'unknown' default."""
        src = _result(url="https://obscure-site.xyz/page", source_type=None)
        s = score_source(src, relevance=0.5, config=config)
        # unknown default is 0.3
        # combined = 0.3*0.4 + 0.5*0.25 + 0.5*0.35 = 0.12+0.125+0.175 = 0.42
        assert 0.35 < s < 0.55


# ---------------------------------------------------------------------------
# Freshness scoring
# ---------------------------------------------------------------------------

class TestFreshnessScoring:
    """Freshness score depends on the age of freshness_date."""

    def test_recent_source_gets_high_freshness(self, config: NagaConfig, today: date) -> None:
        """A source published within the last 30 days should score 1.0 freshness."""
        src = _result(
            url="https://example.com/new",
            source_type="blog",
            freshness_date=today - timedelta(days=5),
        )
        s = score_source(src, relevance=0.5, config=config)
        # freshness=1.0, credibility=0.4 (blog), relevance=0.5
        # combined = 0.4*0.4 + 1.0*0.25 + 0.5*0.35 = 0.16+0.25+0.175 = 0.585
        assert s > 0.55

    def test_old_source_gets_low_freshness(self, config: NagaConfig) -> None:
        """A source older than 3 years should score 0.3 freshness."""
        old_date = date.today() - timedelta(days=1500)
        src = _result(
            url="https://example.com/ancient",
            source_type="blog",
            freshness_date=old_date,
        )
        s_old = score_source(src, relevance=0.5, config=config)
        # freshness=0.3, credibility=0.4, relevance=0.5
        # combined = 0.4*0.4 + 0.3*0.25 + 0.5*0.35 = 0.16+0.075+0.175 = 0.41
        recent_src = _result(
            url="https://example.com/new",
            source_type="blog",
            freshness_date=date.today() - timedelta(days=10),
        )
        s_recent = score_source(recent_src, relevance=0.5, config=config)
        assert s_old < s_recent

    def test_no_date_gets_neutral_freshness(self, config: NagaConfig) -> None:
        """A source with no freshness_date should get 0.5 (neutral)."""
        src_no_date = _result(url="https://example.com/a", source_type="blog")
        src_recent = _result(
            url="https://example.com/b",
            source_type="blog",
            freshness_date=date.today() - timedelta(days=5),
        )
        s_no_date = score_source(src_no_date, relevance=0.5, config=config)
        s_recent = score_source(src_recent, relevance=0.5, config=config)
        # No date (0.5 freshness) < recent (1.0 freshness)
        assert s_no_date < s_recent

    def test_one_year_old_gets_mid_freshness(self, config: NagaConfig) -> None:
        """A source ~6 months old (<=365 days) should get 0.7 freshness."""
        src = _result(
            url="https://example.com/page",
            source_type="blog",
            freshness_date=date.today() - timedelta(days=180),
        )
        s = score_source(src, relevance=0.5, config=config)
        # freshness=0.7, credibility=0.4, relevance=0.5
        # combined = 0.4*0.4 + 0.7*0.25 + 0.5*0.35 = 0.16+0.175+0.175 = 0.51
        assert 0.45 < s < 0.60

    def test_two_year_old_gets_lower_freshness(self, config: NagaConfig) -> None:
        """A 2-year-old source (<=1095 days) should get 0.5 freshness."""
        src = _result(
            url="https://example.com/page",
            source_type="blog",
            freshness_date=date.today() - timedelta(days=730),
        )
        s = score_source(src, relevance=0.5, config=config)
        # freshness=0.5, credibility=0.4, relevance=0.5
        # combined = 0.4*0.4 + 0.5*0.25 + 0.5*0.35 = 0.16+0.125+0.175 = 0.46
        assert 0.40 < s < 0.55


# ---------------------------------------------------------------------------
# Combined score
# ---------------------------------------------------------------------------

class TestCombinedScore:
    """Combined formula: credibility * 0.40 + freshness * 0.25 + relevance * 0.35."""

    def test_score_is_between_zero_and_one(self, config: NagaConfig) -> None:
        src = _result(url="https://example.com/p", source_type="gov")
        s = score_source(src, relevance=0.8, config=config)
        assert 0.0 <= s <= 1.0

    def test_perfect_source_near_one(self, config: NagaConfig) -> None:
        """High credibility + recent + high relevance should approach 1.0."""
        src = _result(
            url="https://pajak.go.id/regulation",
            source_type="gov",
            freshness_date=date.today() - timedelta(days=1),
        )
        s = score_source(src, relevance=1.0, config=config)
        # credibility=0.95, freshness=1.0, relevance=1.0
        # combined = 0.95*0.4 + 1.0*0.25 + 1.0*0.35 = 0.38+0.25+0.35 = 0.98
        assert s >= 0.95

    def test_worst_source_near_minimum(self, config: NagaConfig) -> None:
        """Low credibility + old + zero relevance should be very low."""
        src = _result(
            url="https://randomforum.xyz/thread",
            source_type="forum",
            freshness_date=date.today() - timedelta(days=2000),
        )
        s = score_source(src, relevance=0.0, config=config)
        # credibility=0.2 (forum), freshness=0.3 (old), relevance=0.0
        # combined = 0.2*0.4 + 0.3*0.25 + 0.0*0.35 = 0.08+0.075+0 = 0.155
        assert s < 0.25

    def test_default_relevance_is_half(self, config: NagaConfig) -> None:
        """When no relevance is provided, default should be 0.5."""
        src = _result(url="https://example.com/p", source_type="blog")
        s = score_source(src, config=config)
        # default relevance=0.5
        # credibility=0.4 (blog), freshness=0.5 (no date), relevance=0.5
        expected = 0.4 * 0.40 + 0.5 * 0.25 + 0.5 * 0.35
        assert abs(s - expected) < 0.01


# ---------------------------------------------------------------------------
# score_sources (batch)
# ---------------------------------------------------------------------------

class TestScoreSources:
    """Batch scoring: filters, sorts, stores metadata."""

    def test_filters_below_threshold(self, config: NagaConfig) -> None:
        """Sources scoring below source_score_min should be removed."""
        good = _result(
            url="https://pajak.go.id/info",
            source_type="gov",
            freshness_date=date.today() - timedelta(days=5),
        )
        bad = _result(
            url="https://randomforum.xyz/thread",
            source_type="forum",
            freshness_date=date.today() - timedelta(days=2000),
        )
        results = score_sources([good, bad], config=config)
        urls = [r.url for r in results]
        assert "https://pajak.go.id/info" in urls
        # Forum old source with 0 relevance could be filtered
        # relevance default from relevances dict: None provided means use agent's relevance_score
        # For the bad source: credibility=0.2, freshness=0.3, relevance=0.0
        # combined = 0.2*0.4 + 0.3*0.25 + 0.0*0.35 = 0.155 < 0.30 threshold
        assert "https://randomforum.xyz/thread" not in urls

    def test_sorts_descending_by_score(self, config: NagaConfig) -> None:
        """Results should be sorted by combined score, highest first."""
        high = _result(url="https://pajak.go.id/a", source_type="gov")
        mid = _result(url="https://reuters.com/b", source_type="major_news")
        low = _result(url="https://someblog.com/c", source_type="blog")
        results = score_sources([low, high, mid], config=config)
        scores = [r.metadata["source_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_stores_score_in_metadata(self, config: NagaConfig) -> None:
        """Each result should have metadata['source_score'] after scoring."""
        src = _result(
            url="https://imigrasi.go.id/info",
            source_type="gov",
            relevance_score=0.5,
        )
        results = score_sources([src], config=config)
        assert len(results) >= 1
        assert "source_score" in results[0].metadata
        assert isinstance(results[0].metadata["source_score"], float)
        assert 0.0 <= results[0].metadata["source_score"] <= 1.0

    def test_uses_relevances_dict(self, config: NagaConfig) -> None:
        """Explicit relevances dict should override source's relevance_score."""
        src = _result(
            url="https://imigrasi.go.id/info",
            source_type="gov",
            relevance_score=0.1,
            freshness_date=date.today() - timedelta(days=5),
        )
        # Without override
        results_low = score_sources([src], config=config)
        s_low = results_low[0].metadata["source_score"]

        # With high relevance override
        results_high = score_sources(
            [src],
            relevances={"https://imigrasi.go.id/info": 0.95},
            config=config,
        )
        s_high = results_high[0].metadata["source_score"]
        assert s_high > s_low

    def test_empty_input_returns_empty(self, config: NagaConfig) -> None:
        """Empty source list should return empty list."""
        results = score_sources([], config=config)
        assert results == []

    def test_preserves_original_metadata(self, config: NagaConfig) -> None:
        """Original metadata keys should be preserved alongside source_score."""
        src = _result(
            url="https://example.com/p",
            source_type="gov",
            metadata={"agent": "brave", "query": "visa"},
        )
        results = score_sources([src], config=config)
        assert results[0].metadata["agent"] == "brave"
        assert results[0].metadata["query"] == "visa"
        assert "source_score" in results[0].metadata

    def test_custom_threshold_filters_more(self) -> None:
        """A higher source_score_min should filter out more sources."""
        strict_config = NagaConfig(source_score_min=0.80)
        src = _result(
            url="https://someblog.com/post",
            source_type="blog",
            freshness_date=date.today() - timedelta(days=200),
        )
        results = score_sources([src], config=strict_config)
        # Blog (0.4 credibility) will never reach 0.80 combined
        assert len(results) == 0
