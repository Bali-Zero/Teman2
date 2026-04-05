"""Tests for Intel Quality Gate — 4-dimension scoring."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.quality_gate import (
    GateDecision,
    QualityGate,
    QualityGateConfig,
    QualityGateResult,
    evaluate_batch,
    score_business_impact,
    score_relevance,
    score_reliability,
    score_urgency,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "quality_gate.yaml"


@pytest.fixture
def config() -> QualityGateConfig:
    """Load real config from quality_gate.yaml."""
    return QualityGateConfig.load(CONFIG_PATH)


@pytest.fixture
def gate(config: QualityGateConfig) -> QualityGate:
    return QualityGate(config)


@pytest.fixture
def default_config() -> QualityGateConfig:
    """Bare config with no keywords — tests pure logic."""
    return QualityGateConfig()


# ---------------------------------------------------------------------------
# Sample articles
# ---------------------------------------------------------------------------


def _visa_breaking() -> dict:
    """High-impact breaking visa news from T1 source."""
    return {
        "title": "New KITAS regulation effective immediately — all WNA must comply",
        "content": (
            "Direktorat Jenderal Imigrasi announced a new regulation on KITAS "
            "perpanjangan visa requirements. All foreign nationals (WNA) with "
            "izin tinggal terbatas must submit updated documents by the deadline. "
            "Failure to comply may result in deportasi. This peraturan baru is "
            "effective immediately and affects B211 and KITAP holders as well."
        ),
        "category": "immigration",
        "source_name": "Ditjen Imigrasi",
        "source_url": "https://ditjenimigrasi.go.id/berita/kitas-baru",
        "tier": "T1",
        "svs_score": 0.82,
        "published_at": datetime.now(timezone.utc) - timedelta(hours=2),
        "scraped_at": datetime.now(timezone.utc) - timedelta(hours=1),
    }


def _generic_bali_tourism() -> dict:
    """Low-impact tourism fluff from blog."""
    return {
        "title": "Top 10 beaches in Bali for digital nomads",
        "content": (
            "Bali has amazing beaches perfect for remote work. From Canggu to "
            "Uluwatu, here are our top picks for digital nomad-friendly cafes "
            "near the beach. Great wifi, good vibes, sunset views."
        ),
        "category": "lifestyle",
        "source_name": "BaliNomadBlog",
        "source_url": "https://balinomad.blog/top-beaches",
        "tier": "T3",
        "svs_score": None,
        "published_at": datetime.now(timezone.utc) - timedelta(days=14),
    }


def _tax_regulation_t2() -> dict:
    """Mid-impact tax news from major outlet."""
    return {
        "title": "Indonesia revises PPh rates for foreign investors in 2026",
        "content": (
            "The Direktorat Jenderal Pajak has revised withholding tax (PPh) rates "
            "for foreign investors. The new rates under the tax treaty provisions "
            "affect NPWP holders and SPT filing requirements. Companies with PT PMA "
            "status should review their tax compliance by the deadline."
        ),
        "category": "tax",
        "source_name": "Jakarta Post",
        "source_url": "https://www.thejakartapost.com/business/2026/04/tax-rates",
        "tier": "T2",
        "svs_score": 0.65,
        "published_at": datetime.now(timezone.utc) - timedelta(hours=18),
    }


def _old_property_news() -> dict:
    """Old property article — stale."""
    return {
        "title": "Hak Pakai changes for WNA property ownership",
        "content": (
            "BPN announced updates to Hak Pakai regulations affecting WNA "
            "property ownership in Bali. New sertifikat requirements and BPHTB "
            "calculations apply. Notaris PPAT offices are processing changes."
        ),
        "category": "property",
        "source_name": "Bali Property News",
        "source_url": "https://baliproperty.example.com/hak-pakai-update",
        "tier": "T3",
        "svs_score": 0.45,
        "published_at": datetime.now(timezone.utc) - timedelta(days=30),
    }


# ---------------------------------------------------------------------------
# Test Dimension 1: Relevance
# ---------------------------------------------------------------------------


class TestRelevance:
    def test_visa_keywords_high_score(self, config: QualityGateConfig) -> None:
        score, details = score_relevance(
            "New KITAS regulation for WNA",
            "All foreign nationals with izin tinggal must comply with visa requirements",
            "immigration",
            config,
        )
        assert score > 0.4, f"Visa-heavy article should score high, got {score}"
        assert details["keyword_hits"] > 3

    def test_irrelevant_content_low_score(self, config: QualityGateConfig) -> None:
        score, _ = score_relevance(
            "Celebrity gossip update",
            "Famous actor spotted at restaurant eating noodles with friends",
            "entertainment",
            config,
        )
        assert score < 0.2, f"Irrelevant content should score low, got {score}"

    def test_category_bonus_applied(self, config: QualityGateConfig) -> None:
        score_with, _ = score_relevance("Tax news", "pajak update", "tax", config)
        score_without, _ = score_relevance("Tax news", "pajak update", "sports", config)
        assert score_with > score_without

    def test_empty_content(self, config: QualityGateConfig) -> None:
        score, _ = score_relevance("", "", "general", config)
        assert score == 0.0

    def test_multi_topic_picks_best(self, config: QualityGateConfig) -> None:
        """Article covering both visa and tax should use highest topic score."""
        score, details = score_relevance(
            "KITAS holders face new tax deadline",
            "visa KITAS pajak NPWP tax return SPT perpanjangan visa izin tinggal",
            "immigration",
            config,
        )
        assert score > 0.4
        assert details["best_topic"] is not None


# ---------------------------------------------------------------------------
# Test Dimension 2: Urgency
# ---------------------------------------------------------------------------


class TestUrgency:
    def test_fresh_article_high_urgency(self, config: QualityGateConfig) -> None:
        now = datetime.now(timezone.utc)
        score, details = score_urgency(
            "Breaking: new regulation effective immediately",
            "Peraturan baru berlaku mulai hari ini, segera comply",
            now - timedelta(hours=1),
            now,
            config,
        )
        assert score > 0.5, f"Fresh breaking news should be urgent, got {score}"
        assert details["freshness"] > 0.9

    def test_old_article_low_urgency(self, config: QualityGateConfig) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=30)
        score, _ = score_urgency("Old news", "Something happened long ago", old, old, config)
        assert score < 0.3, f"30-day-old article should have low urgency, got {score}"

    def test_urgency_keywords_boost(self, config: QualityGateConfig) -> None:
        now = datetime.now(timezone.utc) - timedelta(hours=6)
        score_with, _ = score_urgency(
            "Breaking: urgent deadline",
            "segera comply with new regulation, darurat",
            now, now, config,
        )
        score_without, _ = score_urgency(
            "General update",
            "Here is some background information about policy",
            now, now, config,
        )
        assert score_with > score_without

    def test_no_timestamps_uses_now(self, config: QualityGateConfig) -> None:
        score, details = score_urgency("Test", "content", None, None, config)
        assert details["age_hours"] < 1  # should be ~0 since it defaults to now

    def test_half_life_decay(self, config: QualityGateConfig) -> None:
        """After one half-life, freshness should be ~0.5."""
        half_life_hours = config.freshness_half_life_hours
        ts = datetime.now(timezone.utc) - timedelta(hours=half_life_hours)
        _, details = score_urgency("Test", "content", ts, ts, config)
        assert 0.4 < details["freshness"] < 0.6


# ---------------------------------------------------------------------------
# Test Dimension 3: Reliability
# ---------------------------------------------------------------------------


class TestReliability:
    def test_gov_t1_source(self, config: QualityGateConfig) -> None:
        score, details = score_reliability(
            "Ditjen Imigrasi",
            "https://ditjenimigrasi.go.id/berita/update",
            "T1",
            0.80,
            config,
        )
        assert score > 0.7, f"T1 gov source with high SVS should score well, got {score}"
        assert details["resolved_tier"] == "T1"
        assert details["gov_boost"] > 0

    def test_unknown_source_t3(self, config: QualityGateConfig) -> None:
        score, details = score_reliability(
            "Random Blog",
            "https://randomblog.com/post/123",
            "",
            None,
            config,
        )
        assert score < 0.5, f"Unknown source should score low, got {score}"
        assert details["resolved_tier"] == "T3"

    def test_t2_news_outlet(self, config: QualityGateConfig) -> None:
        score, details = score_reliability(
            "Jakarta Post",
            "https://www.thejakartapost.com/news/visa",
            "T2",
            0.65,
            config,
        )
        assert 0.4 < score < 0.8
        assert details["resolved_tier"] == "T2"

    def test_svs_integration(self, config: QualityGateConfig) -> None:
        score_high, _ = score_reliability("X", "https://x.go.id", "T1", 0.95, config)
        score_low, _ = score_reliability("X", "https://x.go.id", "T1", 0.20, config)
        assert score_high > score_low


# ---------------------------------------------------------------------------
# Test Dimension 4: Business Impact
# ---------------------------------------------------------------------------


class TestBusinessImpact:
    def test_visa_high_impact(self, config: QualityGateConfig) -> None:
        score, details = score_business_impact(
            "KITAS regulation change",
            "All visa KITAS holders affected, perpanjangan visa wajib deadline deportasi",
            "visa",
            config,
        )
        assert score > 0.4, f"Visa article should have high impact, got {score}"
        assert "visa" in details["matched_services"] or "immigration" in details["matched_services"]

    def test_irrelevant_low_impact(self, config: QualityGateConfig) -> None:
        score, details = score_business_impact(
            "Celebrity news",
            "Famous person did something interesting at a party",
            "entertainment",
            config,
        )
        assert score <= 0.15, f"Irrelevant article should have minimal impact, got {score}"
        assert details["severity"] == "low"

    def test_severity_keywords_boost(self, config: QualityGateConfig) -> None:
        score_severe, details_severe = score_business_impact(
            "Mandatory compliance deadline",
            "wajib comply, denda penalty for non-compliance, sanksi dicabut",
            "immigration",
            config,
        )
        score_mild, _ = score_business_impact(
            "General info update",
            "Here is some background on the topic for your reference",
            "immigration",
            config,
        )
        assert score_severe > score_mild
        assert details_severe["severity"] in ("medium", "high")

    def test_custom_distribution(self, config: QualityGateConfig) -> None:
        custom = {"visa": 0.90, "tax": 0.05}
        score, details = score_business_impact(
            "Visa update",
            "KITAS perpanjangan visa affected",
            "visa",
            config,
            client_distribution=custom,
        )
        assert details["client_overlap"] > 0.5  # 90% of clients have visa


# ---------------------------------------------------------------------------
# Test Composite / Gate
# ---------------------------------------------------------------------------


class TestQualityGate:
    def test_visa_breaking_auto_publish(self, gate: QualityGate) -> None:
        art = _visa_breaking()
        result = gate.evaluate(
            title=art["title"],
            content=art["content"],
            category=art["category"],
            source_name=art["source_name"],
            source_url=art["source_url"],
            tier=art["tier"],
            svs_score=art["svs_score"],
            published_at=art["published_at"],
            scraped_at=art["scraped_at"],
        )
        assert result.decision in (GateDecision.AUTO_PUBLISH, GateDecision.REVIEW)
        assert result.composite > 0.4
        assert result.relevance > 0.3
        assert result.reliability > 0.5

    def test_generic_tourism_archive(self, gate: QualityGate) -> None:
        art = _generic_bali_tourism()
        result = gate.evaluate(
            title=art["title"],
            content=art["content"],
            category=art["category"],
            source_name=art["source_name"],
            source_url=art["source_url"],
            tier=art["tier"],
            svs_score=art["svs_score"],
            published_at=art["published_at"],
        )
        assert result.decision == GateDecision.ARCHIVE
        assert result.composite < 0.40

    def test_tax_news_review(self, gate: QualityGate) -> None:
        art = _tax_regulation_t2()
        result = gate.evaluate(
            title=art["title"],
            content=art["content"],
            category=art["category"],
            source_name=art["source_name"],
            source_url=art["source_url"],
            tier=art["tier"],
            svs_score=art["svs_score"],
            published_at=art["published_at"],
        )
        # Should be review or auto_publish — definitely not archive
        assert result.decision != GateDecision.ARCHIVE
        assert result.composite >= 0.40

    def test_old_property_lower_score(self, gate: QualityGate) -> None:
        art = _old_property_news()
        result = gate.evaluate(
            title=art["title"],
            content=art["content"],
            category=art["category"],
            source_name=art["source_name"],
            source_url=art["source_url"],
            tier=art["tier"],
            svs_score=art["svs_score"],
            published_at=art["published_at"],
        )
        # Old + T3 source → lower composite
        assert result.urgency < 0.3  # 30 days old
        assert result.reliability < 0.5  # T3

    def test_result_to_dict(self, gate: QualityGate) -> None:
        art = _visa_breaking()
        result = gate.evaluate(
            title=art["title"],
            content=art["content"],
            category=art["category"],
            source_name=art["source_name"],
            source_url=art["source_url"],
            tier=art["tier"],
        )
        d = result.to_dict()
        assert "relevance" in d
        assert "urgency" in d
        assert "reliability" in d
        assert "business_impact" in d
        assert "composite" in d
        assert "decision" in d
        assert isinstance(d["decision"], str)

    def test_weights_sum_to_one(self, config: QualityGateConfig) -> None:
        total = (
            config.w_relevance
            + config.w_urgency
            + config.w_reliability
            + config.w_business_impact
        )
        assert abs(total - 1.0) < 0.001, f"Weights should sum to 1.0, got {total}"


# ---------------------------------------------------------------------------
# Test Batch
# ---------------------------------------------------------------------------


class TestBatch:
    def test_batch_sorted_by_composite(self, config: QualityGateConfig) -> None:
        articles = [
            _generic_bali_tourism(),
            _visa_breaking(),
            _tax_regulation_t2(),
        ]
        results = evaluate_batch(articles, config)
        composites = [r.composite for _, r in results]
        assert composites == sorted(composites, reverse=True)

    def test_batch_empty(self, config: QualityGateConfig) -> None:
        results = evaluate_batch([], config)
        assert results == []

    def test_batch_all_fields_present(self, config: QualityGateConfig) -> None:
        articles = [_visa_breaking()]
        results = evaluate_batch(articles, config)
        assert len(results) == 1
        art, result = results[0]
        assert isinstance(result, QualityGateResult)
        assert 0.0 <= result.composite <= 1.0


# ---------------------------------------------------------------------------
# Test Config Loading
# ---------------------------------------------------------------------------


class TestConfig:
    def test_load_from_yaml(self) -> None:
        config = QualityGateConfig.load(CONFIG_PATH)
        assert config.w_relevance == 0.35
        assert config.threshold_auto_publish == 0.70
        assert "visa" in config.topic_keywords
        assert len(config.topic_keywords["visa"]) > 5
        assert "ditjenimigrasi.go.id" in config.source_tiers

    def test_defaults_when_missing(self, tmp_path: Path) -> None:
        config = QualityGateConfig.load(tmp_path / "nonexistent.yaml")
        assert config.w_relevance == 0.35
        assert config.threshold_auto_publish == 0.70

    def test_tier_scores_complete(self) -> None:
        config = QualityGateConfig.load(CONFIG_PATH)
        assert "T1" in config.tier_scores
        assert "T2" in config.tier_scores
        assert "T3" in config.tier_scores
        assert config.tier_scores["T1"] > config.tier_scores["T2"] > config.tier_scores["T3"]
