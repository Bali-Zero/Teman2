"""Tests for renewal_rules.py — RenewalRule matching logic."""

import json
from pathlib import Path

from backend.services.compliance.renewal_rules import (
    RENEWAL_RULES,
    RULE_PRIORITY_ORDER,
    match_rule,
)

# .../backend/tests/services/compliance/this_file.py -> parents[3] == backend/
_PRICES_FILE = (
    Path(__file__).resolve().parents[3] / "data" / "bali_zero_official_prices_2026.json"
)


def _known_pricing_keys() -> set[str]:
    """Every service key in the price catalogue.

    ``tax_accounting`` nests one level deeper than the other categories, so we
    walk instead of assuming a flat two-level shape: an entry is any dict that
    carries a ``name`` field.
    """
    assert _PRICES_FILE.is_file(), f"price catalogue not found at {_PRICES_FILE}"
    catalogue = json.loads(_PRICES_FILE.read_text())

    keys: set[str] = set()

    def walk(node: object) -> None:
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if isinstance(value, dict):
                if "name" in value:
                    keys.add(key)
                else:
                    walk(value)

    walk(catalogue["services"])
    assert keys, "walked the price catalogue and found no service entries"
    return keys


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
            assert len(rule.required_docs) > 0, f"Rule {rule.rule_id} has empty required_docs"

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


# ── E33 senior routes (55+) ────────────────────────────────────────────────────
#
# The harm being prevented: "e33" and "second home" are substrings of every
# senior string, so before these rules existed a senior client was handed the
# main-route checklist and asked to prove a USD 130,000 deposit (E33F has NO
# deposit at all) or a USD 1M property title (no such route for seniors).
#
# Superscar #3 discipline: every rule below carries BOTH a guilt test (it fires
# on the case it owns) and an innocence test (it does NOT steal a neighbour).


class TestE33SeniorRoutes:
    # ── Guilt: the senior rules fire on their own cases ───────────────────────

    def test_e33e_code_matches_senior_5y_rule(self) -> None:
        rule = match_rule("kitas", "E33E")
        assert rule.rule_id == "e33e_senior_renewal"

    def test_e33f_code_matches_senior_1y_rule(self) -> None:
        rule = match_rule("kitas", "E33F")
        assert rule.rule_id == "e33f_senior_renewal"

    def test_e33e_full_pricing_name_matches_by_code_not_prose(self) -> None:
        # The code wins even though the string also contains "second home senior".
        rule = match_rule("kitas", "E33E Second Home Senior (5 Years)")
        assert rule.rule_id == "e33e_senior_renewal"

    def test_e33f_extend_pricing_name_matches(self) -> None:
        rule = match_rule("kitas", "E33F Second Home Senior (Extend)")
        assert rule.rule_id == "e33f_senior_renewal"

    def test_catalogue_english_name_without_code_hits_unspecified(self) -> None:
        # catalogue.py name_en for E33F — carries no E-code.
        rule = match_rule("kitas", "Second Home Visa Elderly for 1 Year")
        assert rule.rule_id == "e33_senior_route_unspecified"

    def test_catalogue_indonesian_name_hits_unspecified(self) -> None:
        # W82: the guard must not be blind to the Indonesian surface.
        rule = match_rule("kitas", "Visa Rumah Kedua Lansia Untuk 5 Tahun")
        assert rule.rule_id == "e33_senior_route_unspecified"

    # ── Innocence: the senior rules steal nothing from their neighbours ───────

    def test_main_route_e33_still_matches_main_rule(self) -> None:
        rule = match_rule("kitas", "E33 Second Home")
        assert rule.rule_id == "e33_second_home_renewal"

    def test_remote_worker_e33g_not_stolen(self) -> None:
        rule = match_rule("kitas", "E33G Remote Worker")
        assert rule.rule_id == "kitas_remote_worker_extend"

    def test_retirement_kitas_not_stolen(self) -> None:
        rule = match_rule("kitas", "Retirement")
        assert rule.rule_id == "kitas_retirement_extend"

    def test_working_kitas_not_stolen(self) -> None:
        rule = match_rule("kitas", "Working KITAS")
        assert rule.rule_id == "kitas_working_extend"

    def test_investor_kitas_not_stolen(self) -> None:
        rule = match_rule("kitas", "KITAS Investor")
        assert rule.rule_id == "kitas_investor_extend"

    # ── The defect itself: which documents each route asks for ────────────────

    def test_e33f_never_asks_for_a_deposit_or_guarantee(self) -> None:
        docs = RENEWAL_RULES["e33f_senior_renewal"].required_docs
        for doc in docs:
            assert "deposit" not in doc, f"E33F has no deposit; {doc!r} asks for one"
            assert "guarantee" not in doc, f"E33F has no deposit; {doc!r} asks for a guarantee"
            assert "property_title" not in doc, f"E33F has no property route; {doc!r}"
        assert "passive_income_proof_usd_3k_per_month" in docs

    def test_the_two_routes_diverge_on_sponsor_as_well_as_deposit(self) -> None:
        """The axes are CROSSED, and that is the whole reason for two rules.

        imigrasi.go.id states each one outright and in opposite terms:
        E33E "Anda TIDAK membutuhkan penjamin/sponsor" + USD 50,000 deposit;
        E33F "Anda membutuhkan penjamin/sponsor" + no deposit at all.

        Reading only the deposit axis is what produces the plausible-and-wrong
        summary "E33F is the income-only route" — it is not: it trades the
        deposit for a sponsor. A client sent away to prepare the wrong one of
        these two loses the same weeks either way.
        """
        e33e = RENEWAL_RULES["e33e_senior_renewal"].required_docs
        e33f = RENEWAL_RULES["e33f_senior_renewal"].required_docs

        assert "deposit_proof_usd_50k_own_name_bumn_bank" in e33e
        assert not [d for d in e33e if "sponsor" in d or "penjamin" in d], (
            "E33E requires no sponsor — asking for one sends the client after a "
            "document their route does not have"
        )

        assert [d for d in e33f if "sponsor" in d or "penjamin" in d], (
            "E33F requires a penjamin/sponsor — omitting it is how a renewal "
            "gets filed incomplete"
        )
        assert not [d for d in e33f if "deposit" in d]

    def test_both_senior_routes_ask_for_the_3_month_2k_statement(self) -> None:
        """Published on BOTH pages, so it is the one financial document that is
        safe to request before the route is even known."""
        for rule_id in (
            "e33e_senior_renewal",
            "e33f_senior_renewal",
            "e33_senior_route_unspecified",
        ):
            docs = RENEWAL_RULES[rule_id].required_docs
            assert [d for d in docs if d.startswith("bank_statement_3m_usd_2k")], (
                f"{rule_id} omits the USD 2,000 3-month rekening koran that "
                "imigrasi.go.id publishes for both senior routes"
            )

    def test_e33e_asks_for_its_own_50k_deposit_not_the_main_route_one(self) -> None:
        docs = RENEWAL_RULES["e33e_senior_renewal"].required_docs
        assert "deposit_proof_usd_50k_own_name_bumn_bank" in docs
        assert "passive_income_proof_usd_3k_per_month" in docs
        # The main-route checklist item must not leak onto the senior route.
        assert "guarantee_proof_bank_confirmation_or_property_title" not in docs

    def test_main_route_still_asks_for_its_guarantee(self) -> None:
        docs = RENEWAL_RULES["e33_second_home_renewal"].required_docs
        assert "guarantee_proof_bank_confirmation_or_property_title" in docs

    def test_unspecified_route_asks_to_confirm_the_route_before_documents(self) -> None:
        rule = RENEWAL_RULES["e33_senior_route_unspecified"]
        assert (
            "route_confirmation_e33e_deposit_no_sponsor_or_e33f_sponsor_no_deposit"
            in rule.required_docs
        )
        # Safe on both senior routes; the two DIVERGENT documents are not.
        assert "passive_income_proof_usd_3k_per_month" in rule.required_docs
        for doc in rule.required_docs:
            assert "deposit_proof" not in doc, f"route unknown — {doc!r} presumes E33E"
            assert "sponsor_penjamin" not in doc, f"route unknown — {doc!r} presumes E33F"
        # Quoting a price would presume the route.
        assert rule.renewal_pricing_key is None

    def test_e33f_annual_lead_time_is_not_the_five_year_one(self) -> None:
        # E33F is a 1-year permit: a 150-day contact window would fire ~7 months
        # after issue. The 5-year routes keep the long runway.
        e33f = RENEWAL_RULES["e33f_senior_renewal"]
        e33e = RENEWAL_RULES["e33e_senior_renewal"]
        assert e33f.recommended_start_days < 180
        assert e33e.recommended_start_days > e33f.recommended_start_days


# ── Structural tripwires over the whole rule table ─────────────────────────────


class TestRuleTableIntegrity:
    def test_every_rule_is_reachable_from_the_priority_order(self) -> None:
        # A rule absent from RULE_PRIORITY_ORDER is dead code: match_rule never
        # returns it, and the omission is silent.
        missing = set(RENEWAL_RULES) - set(RULE_PRIORITY_ORDER)
        assert not missing, f"rules unreachable by match_rule: {sorted(missing)}"

    def test_voa_extension_is_reachable(self) -> None:
        # visa_voa_extension was defined but absent from RULE_PRIORITY_ORDER, so
        # every B1/VOA fell through to generic_visa_renewal: a 105-day contact
        # window on a 30-day visa, and no price. B1 VOA is a live product.
        rule = match_rule("visa", "B1 Visa on Arrival")
        assert rule.rule_id == "visa_voa_extension"
        assert rule.renewal_pricing_key == "B1 Visa on Arrival Extension"

    def test_voa_does_not_steal_the_c1_tourist_extension(self) -> None:
        rule = match_rule("visa", "C1 Tourism")
        assert rule.rule_id == "visa_tourist_extension"

    def test_priority_order_has_no_phantom_rule_ids(self) -> None:
        phantom = set(RULE_PRIORITY_ORDER) - set(RENEWAL_RULES)
        assert not phantom, f"RULE_PRIORITY_ORDER references undefined rules: {sorted(phantom)}"

    def test_senior_rules_precede_the_generic_e33_rule(self) -> None:
        order = list(RULE_PRIORITY_ORDER)
        generic = order.index("e33_second_home_renewal")
        for senior in (
            "e33e_senior_renewal",
            "e33f_senior_renewal",
            "e33_senior_route_unspecified",
        ):
            assert order.index(senior) < generic, (
                f"{senior} must be matched before e33_second_home_renewal, whose "
                f'"e33"/"second home" patterns would otherwise capture it'
            )

    def test_every_renewal_pricing_key_exists_in_the_price_catalogue(self) -> None:
        # A typo'd key does not raise — it silently yields no price on the alert.
        known = _known_pricing_keys()
        for rule in RENEWAL_RULES.values():
            if rule.renewal_pricing_key is None:
                continue
            assert rule.renewal_pricing_key in known, (
                f"{rule.rule_id} points at pricing key "
                f"{rule.renewal_pricing_key!r}, which is not in "
                f"bali_zero_official_prices_2026.json"
            )
