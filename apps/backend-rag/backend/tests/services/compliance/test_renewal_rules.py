"""Tests for renewal_rules.py — RenewalRule matching logic."""

import pytest

from backend.services.compliance.renewal_rules import (
    RENEWAL_RULES,
    RenewalRule,
    match_rule,
)


class TestMatchRule:
    def test_investor_kitas_extend_matched_by_visa_type(self) -> None:
        rule = match_rule("visa", "KITAS Investor")
        assert rule.rule_id == "kitas_investor_extend"

    def test_investor_kitas_extend_matched_by_kitas_doc(self) -> None:
        rule = match_rule("kitas", "Investor")
        assert rule.rule_id == "kitas_investor_extend"

    def test_spouse_kitas(self) -> None:
        rule = match_rule("kitas", "Spouse 1 Year")
        assert rule.rule_id == "kitas_spouse_extend"

    def test_dependent_kitas(self) -> None:
        rule = match_rule("kitas", "Dependent")
        assert rule.rule_id == "kitas_dependent_extend"

    def test_remote_worker_e33g(self) -> None:
        rule = match_rule("kitas", "E33G Remote Worker")
        assert rule.rule_id == "kitas_remote_worker_extend"

    def test_remote_worker_digital_nomad(self) -> None:
        rule = match_rule("visa", "digital nomad")
        assert rule.rule_id == "kitas_remote_worker_extend"

    def test_retirement_extend(self) -> None:
        rule = match_rule("kitas", "Retirement")
        assert rule.rule_id == "kitas_retirement_extend"

    def test_working_kitas_by_imta(self) -> None:
        rule = match_rule("kitas", "Working KITAS")
        assert rule.rule_id == "kitas_working_extend"

    def test_kitap_upgrade(self) -> None:
        rule = match_rule("kitas", "KITAP")
        assert rule.rule_id == "kitap_investor_upgrade"

    def test_tourist_visa_c1(self) -> None:
        rule = match_rule("visa", "C1 Tourism")
        assert rule.rule_id == "visa_tourist_extension"

    def test_passport_renewal(self) -> None:
        rule = match_rule("passport", "Indonesian Passport")
        assert rule.rule_id == "passport_renewal"

    def test_unknown_visa_falls_back_to_generic(self) -> None:
        rule = match_rule("visa", "some unknown visa type xyz")
        assert rule.rule_id == "generic_visa_renewal"

    def test_unknown_document_type_falls_back(self) -> None:
        rule = match_rule("unknown_doc", "anything")
        assert rule.rule_id == "generic_visa_renewal"

    def test_none_visa_type_falls_back_gracefully(self) -> None:
        rule = match_rule("visa", None)
        # None visa → generic (no specific pattern matches)
        assert rule.rule_id == "generic_visa_renewal"

    def test_passport_wildcard_matches_any_visa_type(self) -> None:
        rule = match_rule("passport", "KITAS Investor with weird type")
        assert rule.rule_id == "passport_renewal"

    def test_processing_days_are_positive(self) -> None:
        for rule in RENEWAL_RULES.values():
            assert rule.processing_days > 0, f"Rule {rule.rule_id} has non-positive processing_days"

    def test_lead_time_gte_processing_days(self) -> None:
        for rule in RENEWAL_RULES.values():
            assert rule.lead_time_days >= rule.processing_days, (
                f"Rule {rule.rule_id}: lead_time_days ({rule.lead_time_days}) "
                f"< processing_days ({rule.processing_days})"
            )

    def test_recommended_start_gte_lead_time(self) -> None:
        for rule in RENEWAL_RULES.values():
            assert rule.recommended_start_days >= rule.lead_time_days, (
                f"Rule {rule.rule_id}: recommended_start_days ({rule.recommended_start_days}) "
                f"< lead_time_days ({rule.lead_time_days})"
            )

    def test_complexity_in_valid_range(self) -> None:
        for rule in RENEWAL_RULES.values():
            assert 1.0 <= rule.complexity <= 3.0, (
                f"Rule {rule.rule_id} has out-of-range complexity={rule.complexity}"
            )

    def test_all_rules_have_required_docs(self) -> None:
        for rule in RENEWAL_RULES.values():
            assert len(rule.required_docs) > 0, (
                f"Rule {rule.rule_id} has empty required_docs"
            )

    def test_passport_renewal_has_no_pricing_key(self) -> None:
        rule = RENEWAL_RULES["passport_renewal"]
        assert rule.renewal_pricing_key is None

    def test_generic_fallback_has_no_pricing_key(self) -> None:
        rule = RENEWAL_RULES["generic_visa_renewal"]
        assert rule.renewal_pricing_key is None

    def test_kitas_working_has_higher_complexity(self) -> None:
        working = RENEWAL_RULES["kitas_working_extend"]
        investor = RENEWAL_RULES["kitas_investor_extend"]
        assert working.complexity > investor.complexity

    def test_kitap_has_longest_processing_time(self) -> None:
        kitap = RENEWAL_RULES["kitap_investor_upgrade"]
        for rule_id, rule in RENEWAL_RULES.items():
            if rule_id != "kitap_investor_upgrade":
                assert kitap.processing_days >= rule.processing_days, (
                    f"KITAP should have longest processing time but {rule_id} "
                    f"has {rule.processing_days} vs KITAP {kitap.processing_days}"
                )

    def test_case_insensitive_matching(self) -> None:
        rule_lower = match_rule("kitas", "investor kitas 2 years")
        rule_upper = match_rule("KITAS", "INVESTOR KITAS 2 YEARS")
        # Both should match same rule family
        assert rule_lower.rule_id == rule_upper.rule_id
