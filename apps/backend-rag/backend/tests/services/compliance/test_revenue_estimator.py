"""Tests for revenue_estimator.py — IDR parsing and pricing lookup."""

from backend.services.compliance.renewal_rules import RENEWAL_RULES
from backend.services.compliance.revenue_estimator import (
    _parse_idr,
    estimate_renewal_revenue,
    estimate_urgent_surcharge,
)

# ── Minimal pricing fixture (mirrors bali_zero_official_prices_2026.json shape) ──
# 2026 schema:
#   * ``visa_extensions`` dropped — C1 Tourism Extension lives in single_entry_visas
#   * ``urgent_services`` renamed to ``urgent_processing``

SAMPLE_PRICES: dict = {
    "services": {
        "single_entry_visas": {
            "C1 Tourism Extension": {"price": "1.700.000 IDR"},
        },
        "kitas_permits": {
            "Investor KITAS 2 Years (Extend)": {"price": "18.000.000 IDR"},
            "Spouse 1 Year (Extend)": {"price": "9.000.000 IDR"},
            "E33G Remote Worker (Extend)": {"price": "10.000.000 IDR"},
            "Retirement (Extend)": {"price": "10.000.000 IDR"},
            "Dependent 1 Year (Extend)": {"price": "9.000.000 IDR"},
            "Freelance E23 (Altus/Onshore)": {"price": "27.500.000 IDR"},
            "Working KITAS (Extend)": {"price": "31.500.000 IDR"},
        },
        "kitap_permits": {
            "Investor KITAP + MERP": {"price": "55.000.000 IDR"},
        },
        "urgent_processing": {
            "Urgent 1 Hari": {"price": "3.000.000 IDR"},
            "Urgent 2 Hari": {"price": "2.500.000 IDR"},
            "Urgent 3 Hari": {"price": "1.000.000 IDR"},
        },
        "company_services": {
            "Revision Company": {"price": "Depend (Contact for quote)"},
        },
    }
}


class TestParseIDR:
    def test_standard_format(self) -> None:
        assert _parse_idr("18.000.000 IDR") == 18_000_000

    def test_no_currency_suffix(self) -> None:
        assert _parse_idr("9.000.000") == 9_000_000

    def test_comma_separated(self) -> None:
        assert _parse_idr("18,000,000 IDR") == 18_000_000

    def test_small_amount(self) -> None:
        assert _parse_idr("500.000 IDR") == 500_000

    def test_depend_returns_none(self) -> None:
        assert _parse_idr("Depend (Contact for quote)") is None

    def test_contact_for_quote_returns_none(self) -> None:
        assert _parse_idr("Contact for quote") is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_idr("") is None

    def test_none_string_returns_none(self) -> None:
        assert _parse_idr(None) is None  # type: ignore[arg-type]


class TestEstimateRenewalRevenue:
    def test_investor_kitas_returns_18m(self) -> None:
        rule = RENEWAL_RULES["kitas_investor_extend"]
        assert estimate_renewal_revenue(rule, SAMPLE_PRICES) == 18_000_000

    def test_spouse_kitas_returns_9m(self) -> None:
        rule = RENEWAL_RULES["kitas_spouse_extend"]
        assert estimate_renewal_revenue(rule, SAMPLE_PRICES) == 9_000_000

    def test_kitap_upgrade_returns_55m(self) -> None:
        rule = RENEWAL_RULES["kitap_investor_upgrade"]
        assert estimate_renewal_revenue(rule, SAMPLE_PRICES) == 55_000_000

    def test_tourist_extension_returns_1_7m(self) -> None:
        rule = RENEWAL_RULES["visa_tourist_extension"]
        assert estimate_renewal_revenue(rule, SAMPLE_PRICES) == 1_700_000

    def test_working_kitas_returns_31_5m(self) -> None:
        rule = RENEWAL_RULES["kitas_working_extend"]
        assert estimate_renewal_revenue(rule, SAMPLE_PRICES) == 31_500_000

    def test_passport_renewal_returns_none(self) -> None:
        # Not a BZ service
        rule = RENEWAL_RULES["passport_renewal"]
        assert estimate_renewal_revenue(rule, SAMPLE_PRICES) is None

    def test_generic_fallback_returns_none(self) -> None:
        rule = RENEWAL_RULES["generic_visa_renewal"]
        assert estimate_renewal_revenue(rule, SAMPLE_PRICES) is None

    def test_missing_key_returns_none(self) -> None:
        rule = RENEWAL_RULES["kitas_investor_extend"]
        # Empty pricing dict
        assert estimate_renewal_revenue(rule, {}) is None

    def test_depend_price_returns_none(self) -> None:
        # "Revision Company" has "Depend" price
        from backend.services.compliance.renewal_rules import RenewalRule
        custom_rule = RenewalRule(
            rule_id="test_rule",
            document_types=("license",),
            visa_type_patterns=("revision",),
            processing_days=7,
            lead_time_days=14,
            recommended_start_days=21,
            renewal_pricing_key="Revision Company",
            required_docs=("docs",),
        )
        assert estimate_renewal_revenue(custom_rule, SAMPLE_PRICES) is None


class TestEstimateUrgentSurcharge:
    def test_1_day_processing_returns_urgent_1(self) -> None:
        result = estimate_urgent_surcharge(1, SAMPLE_PRICES)
        assert result == 3_000_000

    def test_2_day_processing_returns_urgent_2(self) -> None:
        result = estimate_urgent_surcharge(2, SAMPLE_PRICES)
        assert result == 2_500_000

    def test_3_day_processing_returns_urgent_3(self) -> None:
        result = estimate_urgent_surcharge(3, SAMPLE_PRICES)
        assert result == 1_000_000

    def test_14_day_processing_returns_urgent_3(self) -> None:
        result = estimate_urgent_surcharge(14, SAMPLE_PRICES)
        assert result == 1_000_000

    def test_empty_urgent_services_returns_none(self) -> None:
        result = estimate_urgent_surcharge(1, {})
        assert result is None

    def test_legacy_urgent_services_key_still_works(self) -> None:
        # Defensive: transitional fixtures may still pass the legacy
        # ``urgent_services`` key. The estimator should accept both.
        legacy = {
            "services": {
                "urgent_services": {
                    "Urgent 1 Hari": {"price": "3.000.000 IDR"},
                }
            }
        }
        assert estimate_urgent_surcharge(1, legacy) == 3_000_000
