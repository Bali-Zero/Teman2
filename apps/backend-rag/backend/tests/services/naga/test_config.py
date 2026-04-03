"""Tests for Naga research engine configuration."""

import json
from pathlib import Path

import pytest

from backend.services.naga.config.naga_config import (
    NagaConfig,
    TierBudget,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config() -> NagaConfig:
    """Return a default NagaConfig instance."""
    return NagaConfig()


@pytest.fixture
def source_weights_path() -> Path:
    """Return the path to source_weights.json."""
    return (
        Path(__file__).resolve().parents[3]
        / "services"
        / "naga"
        / "config"
        / "source_weights.json"
    )


# ---------------------------------------------------------------------------
# TierBudget dataclass
# ---------------------------------------------------------------------------

class TestTierBudget:
    """Verify TierBudget dataclass construction and defaults."""

    def test_tier_budget_fields(self) -> None:
        tb = TierBudget(
            max_searches=10,
            max_gemini_sources=5,
            max_iterations=2,
            default_ttl_seconds=60,
        )
        assert tb.max_searches == 10
        assert tb.max_gemini_sources == 5
        assert tb.max_iterations == 2
        assert tb.default_ttl_seconds == 60


# ---------------------------------------------------------------------------
# Tier budgets
# ---------------------------------------------------------------------------

class TestTierBudgets:
    """All three tiers must exist with their documented limits."""

    def test_all_three_tiers_exist(self, config: NagaConfig) -> None:
        assert "flash" in config.tier_budgets
        assert "deep" in config.tier_budgets
        assert "exhaustive" in config.tier_budgets

    def test_flash_limits(self, config: NagaConfig) -> None:
        flash = config.tier_budgets["flash"]
        assert flash.max_searches == 3
        assert flash.max_gemini_sources == 0
        assert flash.max_iterations == 1
        assert flash.default_ttl_seconds == 15

    def test_deep_limits(self, config: NagaConfig) -> None:
        deep = config.tier_budgets["deep"]
        assert deep.max_searches == 25
        assert deep.max_gemini_sources == 20
        assert deep.max_iterations == 3
        assert deep.default_ttl_seconds == 300

    def test_exhaustive_limits(self, config: NagaConfig) -> None:
        exhaustive = config.tier_budgets["exhaustive"]
        assert exhaustive.max_searches == 80
        assert exhaustive.max_gemini_sources == 50
        assert exhaustive.max_iterations == 5
        assert exhaustive.default_ttl_seconds == 1800

    def test_flash_has_no_gemini(self, config: NagaConfig) -> None:
        """Flash tier must never use Gemini grounding sources."""
        assert config.tier_budgets["flash"].max_gemini_sources == 0


# ---------------------------------------------------------------------------
# Convergence thresholds
# ---------------------------------------------------------------------------

class TestConvergenceThresholds:
    """Thresholds must be in [0, 1] and match documented defaults."""

    def test_coverage_threshold_value(self, config: NagaConfig) -> None:
        assert config.convergence_coverage_threshold == 0.80

    def test_novelty_threshold_value(self, config: NagaConfig) -> None:
        assert config.convergence_novelty_threshold == 0.10

    def test_coverage_threshold_in_range(self, config: NagaConfig) -> None:
        assert 0.0 <= config.convergence_coverage_threshold <= 1.0

    def test_novelty_threshold_in_range(self, config: NagaConfig) -> None:
        assert 0.0 <= config.convergence_novelty_threshold <= 1.0

    def test_source_score_min_value(self, config: NagaConfig) -> None:
        assert config.source_score_min == 0.30

    def test_source_score_min_in_range(self, config: NagaConfig) -> None:
        assert 0.0 <= config.source_score_min <= 1.0


# ---------------------------------------------------------------------------
# Channel TTLs
# ---------------------------------------------------------------------------

class TestChannelTTLs:
    """Per-channel TTL overrides must be present and positive."""

    def test_telegram_ttl(self, config: NagaConfig) -> None:
        assert config.channel_ttls["telegram"] == 30

    def test_web_chat_ttl(self, config: NagaConfig) -> None:
        assert config.channel_ttls["web_chat"] == 60

    def test_claude_code_ttl(self, config: NagaConfig) -> None:
        assert config.channel_ttls["claude_code"] == 1800

    def test_openclaw_ttl(self, config: NagaConfig) -> None:
        assert config.channel_ttls["openclaw"] == 1800

    def test_api_ttl(self, config: NagaConfig) -> None:
        assert config.channel_ttls["api"] == 3600

    def test_cron_ttl(self, config: NagaConfig) -> None:
        assert config.channel_ttls["cron"] == 3600

    def test_all_ttls_positive(self, config: NagaConfig) -> None:
        for channel, ttl in config.channel_ttls.items():
            assert ttl > 0, f"TTL for channel '{channel}' must be positive"


# ---------------------------------------------------------------------------
# source_weights.json — file-level checks
# ---------------------------------------------------------------------------

class TestSourceWeightsFile:
    """source_weights.json must exist, parse, and contain required keys."""

    def test_file_exists(self, source_weights_path: Path) -> None:
        assert source_weights_path.exists(), (
            f"source_weights.json not found at {source_weights_path}"
        )

    def test_valid_json(self, source_weights_path: Path) -> None:
        data = json.loads(source_weights_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_has_required_top_level_keys(self, source_weights_path: Path) -> None:
        data = json.loads(source_weights_path.read_text(encoding="utf-8"))
        for key in ("default", "domain_overrides", "freshness_weights"):
            assert key in data, f"Missing top-level key: {key}"

    def test_default_categories_present(self, source_weights_path: Path) -> None:
        data = json.loads(source_weights_path.read_text(encoding="utf-8"))
        defaults = data["default"]
        for cat in ("gov", "academic", "major_news", "blog", "forum", "unknown"):
            assert cat in defaults, f"Missing default category: {cat}"

    def test_go_id_domains_in_overrides(self, source_weights_path: Path) -> None:
        """Indonesian government .go.id domains must be present."""
        data = json.loads(source_weights_path.read_text(encoding="utf-8"))
        overrides = data["domain_overrides"]
        go_id_domains = [d for d in overrides if d.endswith(".go.id")]
        assert len(go_id_domains) >= 5, (
            f"Expected at least 5 .go.id domains, found {len(go_id_domains)}: {go_id_domains}"
        )

    def test_freshness_weight_keys(self, source_weights_path: Path) -> None:
        data = json.loads(source_weights_path.read_text(encoding="utf-8"))
        fw = data["freshness_weights"]
        for key in ("days_30", "days_365", "days_1095", "older"):
            assert key in fw, f"Missing freshness_weights key: {key}"

    def test_all_weights_between_0_and_1(self, source_weights_path: Path) -> None:
        data = json.loads(source_weights_path.read_text(encoding="utf-8"))
        for section in ("default", "domain_overrides", "freshness_weights"):
            for key, val in data[section].items():
                assert 0.0 <= val <= 1.0, (
                    f"{section}.{key} = {val} is outside [0, 1]"
                )


# ---------------------------------------------------------------------------
# NagaConfig.load_source_weights()
# ---------------------------------------------------------------------------

class TestLoadSourceWeights:
    """NagaConfig must be able to load and return source weights."""

    def test_load_returns_dict(self, config: NagaConfig) -> None:
        weights = config.load_source_weights()
        assert isinstance(weights, dict)

    def test_load_has_required_keys(self, config: NagaConfig) -> None:
        weights = config.load_source_weights()
        for key in ("default", "domain_overrides", "freshness_weights"):
            assert key in weights

    def test_load_domain_override_value(self, config: NagaConfig) -> None:
        weights = config.load_source_weights()
        assert weights["domain_overrides"]["pajak.go.id"] == 0.95

    def test_load_default_gov_value(self, config: NagaConfig) -> None:
        weights = config.load_source_weights()
        assert weights["default"]["gov"] == 0.90
