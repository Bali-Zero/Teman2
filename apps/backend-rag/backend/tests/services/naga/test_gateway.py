"""Tests for Naga Gateway — fast rule-based query classifier."""

import dataclasses

import pytest

from backend.services.naga.gateway import GatewayResult, classify_query

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def flash_result() -> GatewayResult:
    """A typical flash-tier result."""
    return classify_query("what is KITAS?")


@pytest.fixture
def deep_result() -> GatewayResult:
    """A deep-tier result triggered by complexity signal."""
    return classify_query("analyze the KITAS application process in detail")


@pytest.fixture
def exhaustive_result() -> GatewayResult:
    """An exhaustive-tier result with many complexity signals."""
    return classify_query(
        "provide a comprehensive analysis comparing the impact "
        "and trade-offs of golden visa Indonesia versus retirement visa, "
        "including a timeline and storia delle modifiche normative"
    )


# ---------------------------------------------------------------------------
# GatewayResult dataclass
# ---------------------------------------------------------------------------


class TestGatewayResult:
    """Verify GatewayResult is a frozen dataclass with correct fields."""

    def test_is_frozen_dataclass(self) -> None:
        result = classify_query("hello")
        assert dataclasses.is_dataclass(result)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.tier = "deep"  # type: ignore[misc]

    def test_has_required_fields(self) -> None:
        result = classify_query("hello")
        assert hasattr(result, "tier")
        assert hasattr(result, "domain")
        assert hasattr(result, "mode")
        assert hasattr(result, "ttl_seconds")

    def test_field_types(self) -> None:
        result = classify_query("hello")
        assert isinstance(result.tier, str)
        assert isinstance(result.domain, str)
        assert isinstance(result.mode, str)
        assert isinstance(result.ttl_seconds, int)


# ---------------------------------------------------------------------------
# Domain classification
# ---------------------------------------------------------------------------


class TestDomainClassification:
    """Keyword-based domain routing: indonesia / general / hybrid."""

    def test_indonesia_domain_kitas(self) -> None:
        result = classify_query("qual e il costo del KITAS 2026?")
        assert result.domain == "indonesia"

    def test_indonesia_domain_pt_pma(self) -> None:
        result = classify_query("come aprire una PT PMA a Bali?")
        assert result.domain == "indonesia"

    def test_indonesia_domain_golden_visa(self) -> None:
        result = classify_query("requisiti golden visa Indonesia")
        assert result.domain == "indonesia"

    def test_indonesia_domain_pajak(self) -> None:
        result = classify_query("quanto costa il pajak annuale?")
        assert result.domain == "indonesia"

    def test_indonesia_domain_oss_nib(self) -> None:
        result = classify_query("come ottenere NIB tramite OSS?")
        assert result.domain == "indonesia"

    def test_indonesia_domain_hak_pakai(self) -> None:
        result = classify_query("differenza tra hak pakai e HGB")
        assert result.domain == "indonesia"

    def test_indonesia_domain_kemenkumham(self) -> None:
        result = classify_query("procedura kemenkumham per akta notaris")
        assert result.domain == "indonesia"

    def test_general_domain(self) -> None:
        result = classify_query("explain quantum computing")
        assert result.domain == "general"

    def test_general_domain_short(self) -> None:
        result = classify_query("hello")
        assert result.domain == "general"

    def test_hybrid_domain(self) -> None:
        result = classify_query(
            "confronto golden visa Indonesia vs Portogallo"
        )
        assert result.domain == "hybrid"

    def test_hybrid_domain_compare_countries(self) -> None:
        result = classify_query(
            "compare Indonesia investor visa requirements with "
            "Singapore employment pass process and benefits"
        )
        assert result.domain == "hybrid"

    def test_case_insensitive_keywords(self) -> None:
        result = classify_query("KITAS application BALI")
        assert result.domain == "indonesia"

    def test_single_keyword_is_indonesia(self) -> None:
        """A single Indonesia keyword with no general content -> indonesia."""
        result = classify_query("NPWP")
        assert result.domain == "indonesia"

    def test_multiple_indonesia_keywords(self) -> None:
        result = classify_query("biaya visa KITAS izin tinggal Bali")
        assert result.domain == "indonesia"


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------


class TestTierClassification:
    """Complexity-signal-based tier routing: flash / deep / exhaustive."""

    def test_flash_tier_short_query(self) -> None:
        result = classify_query("what is KITAS?")
        assert result.tier == "flash"

    def test_flash_tier_simple(self) -> None:
        result = classify_query("hello world")
        assert result.tier == "flash"

    def test_deep_tier_single_complexity_signal(self) -> None:
        result = classify_query("analyze the KITAS requirements")
        assert result.tier == "deep"

    def test_deep_tier_word_count_over_15(self) -> None:
        result = classify_query(
            "I need to understand the process for setting up "
            "a business entity in Bali for foreign investors"
        )
        assert result.tier == "deep"

    def test_exhaustive_tier_many_complexity_signals(self) -> None:
        result = classify_query(
            "provide a comprehensive analysis comparing the impact "
            "and trade-offs of visa policies including a research report"
        )
        assert result.tier == "exhaustive"

    def test_exhaustive_tier_long_query(self) -> None:
        """Word count > 40 triggers exhaustive."""
        long_query = " ".join(["word"] * 41)
        result = classify_query(long_query)
        assert result.tier == "exhaustive"

    def test_deep_tier_confronto(self) -> None:
        """Italian complexity signal 'confronto' triggers deep."""
        result = classify_query("confronto tra KITAS e KITAP")
        assert result.tier == "deep"

    def test_deep_tier_dettagliata(self) -> None:
        result = classify_query("analisi dettagliata del processo")
        assert result.tier == "deep"


# ---------------------------------------------------------------------------
# Mode classification
# ---------------------------------------------------------------------------


class TestModeClassification:
    """Conversational vs. oneshot mode routing."""

    def test_oneshot_default(self) -> None:
        result = classify_query("what is KITAS?")
        assert result.mode == "oneshot"

    def test_conversational_signal_esplora(self) -> None:
        result = classify_query("esplora le opzioni per il visto")
        assert result.mode == "conversational"

    def test_conversational_signal_explore(self) -> None:
        result = classify_query("explore the visa options available")
        assert result.mode == "conversational"

    def test_conversational_signal_investigate(self) -> None:
        result = classify_query("investigate the tax implications")
        assert result.mode == "conversational"

    def test_conversational_signal_non_sono_sicuro(self) -> None:
        result = classify_query("non sono sicuro quale visto scegliere")
        assert result.mode == "conversational"

    def test_conversational_signal_diverse_prospettive(self) -> None:
        result = classify_query("vorrei diverse prospettive sul tema")
        assert result.mode == "conversational"

    def test_exhaustive_forces_conversational(self) -> None:
        result = classify_query(
            "provide a comprehensive analysis comparing the impact "
            "and trade-offs of visa policies including a research report"
        )
        assert result.tier == "exhaustive"
        assert result.mode == "conversational"


# ---------------------------------------------------------------------------
# TTL handling
# ---------------------------------------------------------------------------


class TestTTL:
    """TTL must honour channel overrides and tier defaults."""

    def test_no_channel_uses_tier_default_flash(self) -> None:
        result = classify_query("hello")
        assert result.tier == "flash"
        assert result.ttl_seconds == 15  # flash default

    def test_no_channel_uses_tier_default_deep(self) -> None:
        result = classify_query("analyze the visa options carefully")
        assert result.tier == "deep"
        assert result.ttl_seconds == 300  # deep default

    def test_telegram_channel_ttl(self) -> None:
        result = classify_query("what is KITAS?", channel="telegram")
        assert result.ttl_seconds == 30

    def test_telegram_forces_flash(self) -> None:
        """Telegram channel forces flash tier."""
        result = classify_query(
            "analyze the comprehensive impact of visa policies",
            channel="telegram",
        )
        assert result.tier == "flash"
        assert result.ttl_seconds == 30

    def test_telegram_force_tier_overrides_flash(self) -> None:
        """force_tier overrides telegram's flash forcing."""
        result = classify_query(
            "analyze something",
            channel="telegram",
            force_tier="deep",
        )
        assert result.tier == "deep"
        assert result.ttl_seconds == 30  # channel TTL still applies

    def test_cron_channel_ttl(self) -> None:
        result = classify_query("run daily analysis", channel="cron")
        assert result.ttl_seconds == 3600

    def test_web_chat_channel_ttl(self) -> None:
        result = classify_query("hello", channel="web_chat")
        assert result.ttl_seconds == 60

    def test_claude_code_channel_ttl(self) -> None:
        result = classify_query("analyze this code", channel="claude_code")
        assert result.ttl_seconds == 1800

    def test_unknown_channel_uses_tier_default(self) -> None:
        result = classify_query("hello", channel="unknown_channel")
        assert result.tier == "flash"
        assert result.ttl_seconds == 15  # falls back to tier default


# ---------------------------------------------------------------------------
# Force overrides
# ---------------------------------------------------------------------------


class TestForceOverrides:
    """force_tier and force_domain must override classification."""

    def test_force_tier_overrides_classification(self) -> None:
        result = classify_query("hello", force_tier="exhaustive")
        assert result.tier == "exhaustive"

    def test_force_domain_overrides_classification(self) -> None:
        result = classify_query(
            "explain quantum computing", force_domain="indonesia"
        )
        assert result.domain == "indonesia"

    def test_force_tier_and_domain_together(self) -> None:
        result = classify_query(
            "hello",
            force_tier="deep",
            force_domain="hybrid",
        )
        assert result.tier == "deep"
        assert result.domain == "hybrid"

    def test_force_tier_invalid_value_ignored(self) -> None:
        """Invalid force_tier falls back to classification."""
        result = classify_query("hello", force_tier="nonexistent")
        assert result.tier in {"flash", "deep", "exhaustive"}

    def test_force_domain_invalid_value_ignored(self) -> None:
        """Invalid force_domain falls back to classification."""
        result = classify_query("hello", force_domain="nonexistent")
        assert result.domain in {"indonesia", "general", "hybrid"}


# ---------------------------------------------------------------------------
# Performance expectation
# ---------------------------------------------------------------------------


class TestPerformance:
    """Gateway must be sub-millisecond — no LLM, no network."""

    def test_classify_is_fast(self) -> None:
        """1000 classifications should complete well under 1 second."""
        import time

        start = time.perf_counter()
        for _ in range(1000):
            classify_query(
                "comprehensive analysis of KITAS requirements and trade-offs"
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"1000 classifications took {elapsed:.3f}s (expected <1s)"
