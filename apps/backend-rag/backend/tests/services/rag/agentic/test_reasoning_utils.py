"""
Unit tests for backend.services.rag.agentic.reasoning_utils

Coverage target: uncovered branches and edge cases NOT already exercised by:
  - backend/tests/services/rag/test_evidence_scoring_abstain.py
  - backend/tests/unit/services/rag/agentic/test_reasoning.py
  - backend/tests/unit/services/rag/agentic/test_reasoning_comprehensive.py

Specifically covers:
  - Priority-order collisions in get_critical_domain_type / classify_query_domain
  - Edge inputs (empty, whitespace, None, non-string) for every public function
  - is_valid_tool_call: empty-dict args (valid), empty-list args (valid), bare object()
  - calculate_evidence_score: stop-words-only query, short-word strip, dedup,
    non-dict sources, missing score field, company-vs-visa mismatch, semantic
    penalty guard conditions
  - _parse_domain_threshold_overrides: uppercase keys, whitespace, extra colon,
    boundary float values (0.0, 1.0)
  - get_abstain_threshold: env override, partial override leaving others intact
  - detect_team_query: non-string input, dynamic company_name marker, email
    beats role, name article stripping, 3-word cap, unicode quote stripping
"""

from __future__ import annotations

import types
from unittest.mock import patch

import pytest

import backend.services.rag.agentic.reasoning_utils as mod
from backend.services.rag.agentic.reasoning_utils import (
    _parse_domain_threshold_overrides,
    calculate_evidence_score,
    classify_query_domain,
    detect_team_query,
    get_abstain_threshold,
    get_critical_domain_type,
    is_critical_domain,
    is_valid_tool_call,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool(tool_name=None, arguments=None, *, set_arguments=True):
    """Build a simple namespace object that mimics a ToolCall."""
    obj = types.SimpleNamespace()
    if tool_name is not None:
        obj.tool_name = tool_name
    if set_arguments:
        obj.arguments = arguments
    return obj


# ===========================================================================
# get_critical_domain_type
# ===========================================================================

class TestGetCriticalDomainType:

    def test_visa_keyword_kitas_uppercase(self):
        assert get_critical_domain_type("My KITAS expires next month") == "visa"

    def test_visa_keyword_b211(self):
        assert get_critical_domain_type("What is a B211 visa?") == "visa"

    def test_legal_keyword_pasal_bahasa(self):
        assert get_critical_domain_type("Pasal 36 ayat 2 of the regulation") == "legal"

    def test_priority_visa_over_pricing_harga_kitas(self):
        # "harga" is pricing, "kitas" is visa — visa wins (listed first)
        assert get_critical_domain_type("Berapa harga untuk KITAS?") == "visa"

    def test_priority_legal_over_pricing_fee_compliance(self):
        # "fee" is pricing, "compliance" is legal — legal wins
        assert get_critical_domain_type("What is the compliance fee?") == "legal"

    def test_priority_legal_over_procedure_legal_document(self):
        # "legal" is legal, "document" is procedure — legal wins
        assert get_critical_domain_type("What legal documents do I need?") == "legal"

    def test_procedure_keyword_documentation(self):
        assert get_critical_domain_type("What documentation is needed?") == "procedure"

    def test_empty_string_returns_business_complex(self):
        assert get_critical_domain_type("") == "business_complex"

    def test_whitespace_only_returns_business_complex(self):
        assert get_critical_domain_type("   ") == "business_complex"

    def test_unrelated_topic_returns_business_complex(self):
        assert get_critical_domain_type("What restaurants are open in Bali?") == "business_complex"

    def test_unicode_non_keyword_does_not_crash(self):
        result = get_critical_domain_type("Perché è importante? può darsi")
        assert result == "business_complex"


# ===========================================================================
# is_critical_domain
# ===========================================================================

class TestIsCriticalDomain:

    def test_business_complex_intent_overrides_empty_query(self):
        assert is_critical_domain("Hello", "business_complex") is True

    def test_business_strategic_intent_overrides_empty_query(self):
        assert is_critical_domain("Good morning", "business_strategic") is True

    def test_critical_keyword_in_query_overrides_simple_intent(self):
        assert is_critical_domain("My visa expired", "simple") is True

    def test_no_keyword_non_critical_intent_returns_false(self):
        assert is_critical_domain("How are you?", "greeting") is False

    def test_empty_query_non_critical_intent_returns_false(self):
        assert is_critical_domain("", "simple") is False

    def test_case_insensitive_keyword_match(self):
        assert is_critical_domain("COMPLIANCE check required", "simple") is True

    def test_multiple_keywords_still_true(self):
        assert is_critical_domain("fee and document requirements", "other") is True


# ===========================================================================
# is_valid_tool_call
# ===========================================================================

class TestIsValidToolCall:

    def test_empty_dict_arguments_is_valid(self):
        # {} is not None — an empty dict is a legitimate (no-args) call
        obj = _make_tool("vector_search", {})
        assert is_valid_tool_call(obj) is True

    def test_empty_list_arguments_is_valid(self):
        # [] is not None either
        obj = _make_tool("some_tool", [])
        assert is_valid_tool_call(obj) is True

    def test_bare_object_no_attributes_returns_false(self):
        assert is_valid_tool_call(object()) is False

    def test_missing_tool_name_attribute(self):
        obj = types.SimpleNamespace(arguments={"key": "val"})
        assert is_valid_tool_call(obj) is False

    def test_missing_arguments_attribute(self):
        obj = _make_tool("my_tool", set_arguments=False)
        assert is_valid_tool_call(obj) is False

    def test_integer_tool_name_returns_false(self):
        obj = _make_tool(42, {"q": "x"})
        assert is_valid_tool_call(obj) is False

    def test_nested_arguments_still_valid(self):
        obj = _make_tool("vector_search", {"query": "kitas", "limit": 5})
        assert is_valid_tool_call(obj) is True


# ===========================================================================
# calculate_evidence_score
# ===========================================================================

class TestCalculateEvidenceScore:

    # --- guard conditions ---

    def test_both_none_and_empty_returns_zero(self):
        assert calculate_evidence_score(None, [], "test") == 0.0

    def test_sources_none_context_present_no_crash(self):
        # sources=None must not crash; score driven purely by semantic relevance
        score = calculate_evidence_score(
            None,
            ["kitas immigration stay permit renewal process"],
            "kitas renewal procedure",
        )
        assert score > 0.0

    def test_sources_empty_list_no_crash(self):
        score = calculate_evidence_score(
            [],
            ["kitas immigration permit"],
            "kitas permit",
        )
        assert score >= 0.0  # valid, no crash

    # --- stop-words-only query →  query_keywords empty → ratio = 0.0 ---

    def test_stop_words_only_query_keyword_ratio_zero(self):
        score = calculate_evidence_score(
            [{"score": 0.8}],
            ["kitas immigration visa stay permit renewal"],
            "what is the",
        )
        # semantic_relevance == 0.0 → final_score capped at min(0.4*0.2, 0.1)
        assert score <= 0.10

    # --- short words stripped (all ≤ 3 chars after strip) ---

    def test_short_words_only_yields_near_zero(self):
        score = calculate_evidence_score(
            [{"score": 0.8}],
            ["kitas visa permit"],
            "go to a spa",  # all ≤ 3 chars: go(2), to(2), a(1), spa(3)
        )
        assert score <= 0.10

    # --- keyword deduplication ---

    def test_duplicate_keywords_are_deduplicated(self):
        # "kitas" repeated 4 times — after dedup query_keywords has just ["kitas"]
        # context has "kitas" → keyword_hits=1, ratio=1/1=1.0 → semantic_relevance=0.6
        score_dedup = calculate_evidence_score(
            None,
            ["kitas immigration permit"],
            "kitas kitas kitas kitas",
        )
        score_single = calculate_evidence_score(
            None,
            ["kitas immigration permit"],
            "kitas",
        )
        assert score_dedup == score_single

    # --- source without 'score' field ---

    def test_source_missing_score_field_no_crash(self):
        # .get("score", 0.0) returns 0.0 — source_quality stays 0
        score = calculate_evidence_score(
            [{"id": 1, "content": "kitas visa permit renewal"}],
            ["kitas visa permit renewal"],
            "kitas renewal",
        )
        assert 0.0 <= score <= 1.0

    # --- non-dict items in sources list ---

    def test_source_list_with_non_dict_items_no_crash(self):
        score = calculate_evidence_score(
            [None, "string", 42, {"score": 0.7}],
            ["kitas immigration permit"],
            "kitas permit",
        )
        assert 0.0 <= score <= 1.0

    # --- entity mismatch: company vs visa ---

    def test_entity_mismatch_company_vs_visa(self):
        # query about PT/PMA company, context about visa/immigration only
        score = calculate_evidence_score(
            [{"score": 0.6}],
            ["visa immigration permit stay kitas renewal"],
            "PT PMA company setup registration",
        )
        assert score < 0.15

    # --- semantic-cosine penalty guard conditions ---

    def test_semantic_penalty_not_applied_when_cosine_is_zero(self):
        # top_source_cosine == 0 → condition `0 < cosine` is False → no penalty
        before_penalty = calculate_evidence_score(
            None,
            ["kitas immigration permit"],
            "kitas permit",
        )
        after_zero_source = calculate_evidence_score(
            [{"score": 0.0}],
            ["kitas immigration permit"],
            "kitas permit",
        )
        # With cosine=0 and no actual source quality, scores should be equal
        # (source_quality_score=0 either way)
        assert after_zero_source == before_penalty

    def test_semantic_penalty_not_applied_when_final_score_at_or_below_015(self):
        # Even if cosine is < 0.5, penalty only fires when final_score > 0.15
        # Craft a case with zero semantic relevance → final_score ≤ 0.10 → no penalty
        score = calculate_evidence_score(
            [{"score": 0.35}],   # cosine 0.35 < 0.5, would trigger penalty
            ["completely unrelated content about something else"],
            "xyzabc123",          # no meaningful keywords → semantic_relevance = 0.0
        )
        # final_score already ≤ 0.10; verify penalty didn't make it negative
        assert 0.0 <= score <= 0.10

    def test_semantic_penalty_not_applied_when_cosine_above_05(self):
        # cosine >= 0.5 → condition `cosine < 0.5` is False → no penalty
        score_high_cosine = calculate_evidence_score(
            [{"score": 0.75}],
            ["kitas immigration permit renewal"],
            "kitas permit renewal",
        )
        score_no_sources = calculate_evidence_score(
            None,
            ["kitas immigration permit renewal"],
            "kitas permit renewal",
        )
        # high cosine should not degrade the score (penalty absent)
        assert score_high_cosine >= score_no_sources

    def test_result_rounded_to_two_decimals(self):
        score = calculate_evidence_score(
            [{"score": 0.55}],
            ["kitas immigration permit renewal process"],
            "kitas renewal procedure",
        )
        assert score == round(score, 2)

    def test_result_never_exceeds_one(self):
        score = calculate_evidence_score(
            [{"score": 0.99}],
            ["kitas immigration permit renewal kitas stay residence visa b211"],
            "kitas immigration permit renewal",
        )
        assert score <= 1.0


# ===========================================================================
# _parse_domain_threshold_overrides
# ===========================================================================

class TestParseDomainThresholdOverrides:

    def test_valid_single_entry(self):
        result = _parse_domain_threshold_overrides("tax:0.10")
        assert result == {"tax": 0.10}

    def test_valid_multiple_entries(self):
        result = _parse_domain_threshold_overrides("tax:0.10,kbli:0.20,visa:0.12")
        assert result == {"tax": 0.10, "kbli": 0.20, "visa": 0.12}

    def test_empty_string_returns_empty_dict(self):
        assert _parse_domain_threshold_overrides("") == {}

    def test_none_input_returns_empty_dict(self):
        assert _parse_domain_threshold_overrides(None) == {}

    def test_entry_without_colon_is_skipped(self):
        result = _parse_domain_threshold_overrides("tax:0.10,broken,kbli:0.20")
        assert result == {"tax": 0.10, "kbli": 0.20}

    def test_non_numeric_value_is_skipped_and_warned(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            result = _parse_domain_threshold_overrides("kbli:notanumber")
        assert result == {}
        assert any("notanumber" in r.message or "skipping" in r.message.lower()
                   for r in caplog.records)

    def test_uppercase_keys_normalized_to_lowercase(self):
        result = _parse_domain_threshold_overrides("TAX:0.10,KBLI:0.20")
        assert "tax" in result and "kbli" in result

    def test_whitespace_trimmed(self):
        result = _parse_domain_threshold_overrides("  tax : 0.10 , kbli : 0.20 ")
        assert result.get("tax") == pytest.approx(0.10)
        assert result.get("kbli") == pytest.approx(0.20)

    def test_value_zero_is_valid(self):
        result = _parse_domain_threshold_overrides("tax:0.0")
        assert result == {"tax": 0.0}

    def test_value_one_is_valid(self):
        result = _parse_domain_threshold_overrides("default:1.0")
        assert result == {"default": 1.0}

    def test_extra_colon_in_value_is_skipped(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            result = _parse_domain_threshold_overrides("tax:0.10:extra")
        assert result == {}


# ===========================================================================
# classify_query_domain  (priority collisions not covered by existing tests)
# ===========================================================================

class TestClassifyQueryDomain:

    def test_none_query_returns_default(self):
        assert classify_query_domain(None) == "default"

    def test_empty_query_returns_default(self):
        assert classify_query_domain("") == "default"

    def test_case_insensitive_uppercase(self):
        assert classify_query_domain("PPH21 RATE?") == "tax"

    def test_bahasa_keyword_pajak(self):
        assert classify_query_domain("Berapa pajak untuk PT?") == "tax"

    def test_bahasa_keyword_ppn(self):
        assert classify_query_domain("PPN registration deadline") == "tax"

    def test_multi_word_visa_permesso_soggiorno(self):
        assert classify_query_domain("Ho bisogno di un permesso di soggiorno") == "visa"

    def test_multi_word_kbli_kegiatan_usaha(self):
        assert classify_query_domain("Kode kegiatan usaha untuk villa") == "kbli"

    def test_multi_word_pricing_berapa_biaya(self):
        assert classify_query_domain("Berapa biaya setup PT?") == "pricing"

    # Priority collisions
    def test_priority_tax_before_visa(self):
        # "pajak" (tax) and "kitas" (visa) — tax is checked first
        assert classify_query_domain("pajak untuk KITAS holders") == "tax"

    def test_priority_tax_before_kbli(self):
        assert classify_query_domain("pajak KBLI code") == "tax"

    def test_priority_visa_before_kbli(self):
        # visa checked before kbli
        assert classify_query_domain("KITAS KBLI registration") == "visa"

    def test_priority_visa_before_pricing(self):
        # "kitas" (visa) and "cost" (pricing) — visa wins
        assert classify_query_domain("How much does KITAS cost?") == "visa"

    def test_priority_kbli_before_pricing(self):
        # "kbli" and "price" — kbli wins
        assert classify_query_domain("KBLI code price") == "kbli"

    def test_generic_greeting_returns_default(self):
        assert classify_query_domain("Ciao come stai?") == "default"


# ===========================================================================
# get_abstain_threshold  (env override scenarios)
# ===========================================================================

class TestGetAbstainThreshold:

    def test_env_override_changes_tax_threshold(self, monkeypatch):
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", "tax:0.05")
        monkeypatch.setattr(mod, "_DOMAIN_THRESHOLDS", mod._build_domain_thresholds())
        assert get_abstain_threshold("Berapa pajak?") == pytest.approx(0.05)

    def test_partial_override_leaves_other_domains_unchanged(self, monkeypatch):
        monkeypatch.setenv("DOMAIN_ABSTAIN_THRESHOLDS", "kbli:0.30")
        monkeypatch.setattr(mod, "_DOMAIN_THRESHOLDS", mod._build_domain_thresholds())
        # visa and tax should keep their defaults
        assert get_abstain_threshold("KITAS renewal") == pytest.approx(0.12)
        assert get_abstain_threshold("pajak tahunan") == pytest.approx(0.10)

    def test_default_domain_returns_015(self):
        # no env override, generic query
        assert get_abstain_threshold("Hello") == pytest.approx(0.15)


# ===========================================================================
# detect_team_query
# ===========================================================================

class TestDetectTeamQuery:

    # --- input validation ---

    def test_non_string_int_returns_false(self):
        assert detect_team_query(123) == (False, "", "")

    def test_non_string_none_returns_false(self):
        assert detect_team_query(None) == (False, "", "")

    def test_whitespace_only_returns_false(self):
        assert detect_team_query("   ") == (False, "", "")

    # --- list_all: dynamic company name marker ---

    def test_dynamic_company_name_marker_matches(self):
        from backend.app.core.config import settings
        query = f"i dipendenti {settings.COMPANY_NAME}"
        is_team, qtype, term = detect_team_query(query)
        assert is_team is True
        assert qtype == "list_all"
        assert term == ""

    def test_dynamic_company_name_uppercase_in_query(self):
        from backend.app.core.config import settings
        query = f"I DIPENDENTI {settings.COMPANY_NAME.upper()}"
        is_team, qtype, _ = detect_team_query(query)
        assert is_team is True
        assert qtype == "list_all"

    # --- email lookup beats role lookup ---

    def test_email_in_list_all_context_email_not_matched_first(self):
        # "tutti i membri" is a list_all marker — list_all is checked first
        is_team, qtype, term = detect_team_query("tutti i membri email@team.com")
        assert qtype == "list_all"
        assert term == ""

    def test_email_beats_role_lookup(self):
        # query has team context marker AND an email — email lookup comes second
        # in the function, so if list_all doesn't match, email regex fires
        is_team, qtype, term = detect_team_query(
            "chi gestisce taxation? contact tax@balizero.com"
        )
        # "chi gestisce" is a team context marker, but re.search for email runs
        # at step 2 (before role lookup at step 3) so email wins
        assert is_team is True
        assert qtype == "search_by_email"
        assert term == "tax@balizero.com"

    # --- role lookup with team context ---

    def test_role_without_team_context_does_not_match_role_branch(self):
        # "tax" appears in role_map but no team context marker → role branch skipped
        # Should fall through to name patterns or return False
        is_team, qtype, _ = detect_team_query("What is the tax rate?")
        # must not return "search_by_role" from the role branch
        assert qtype != "search_by_role" or not is_team

    def test_role_ceo_with_chi_e_il(self):
        is_team, qtype, term = detect_team_query("Chi è il CEO?")
        assert is_team is True
        assert qtype == "search_by_role"
        assert term == "ceo"

    def test_role_visa_who_manages(self):
        is_team, qtype, term = detect_team_query("Who manages visa applications?")
        assert is_team is True
        assert qtype == "search_by_role"
        assert term == "visa"

    # --- name patterns: article stripping ---

    def test_name_leading_article_stripped(self):
        # "il responsabile" → "il" is a leading article that gets stripped
        is_team, qtype, term = detect_team_query("Chi è il responsabile?")
        assert is_team is True
        assert qtype == "search_by_name"
        assert not term.startswith("il ")

    def test_who_is_name(self):
        is_team, qtype, term = detect_team_query("Who is Sarah?")
        assert is_team is True
        assert qtype == "search_by_name"
        assert "sarah" in term.lower()

    # --- name patterns: 3-word cap ---

    def test_name_capped_at_three_words(self):
        is_team, qtype, term = detect_team_query(
            "Chi è Marco Antonio Rossi Bianchi?"
        )
        assert is_team is True
        assert qtype == "search_by_name"
        words = term.split()
        assert len(words) <= 3

    # --- unicode quote stripping ---

    def test_unicode_quotes_stripped_from_name(self):
        # U+201C " and U+201D " around a name
        is_team, qtype, term = detect_team_query(
            "Chi è “Marco”?"
        )
        assert is_team is True
        assert qtype == "search_by_name"
        assert "“" not in term and "”" not in term

    # --- conosci pattern: lowercase excluded ---

    def test_conosci_lowercase_generic_excluded(self):
        # "qualche" is in the conosci exclusion list
        is_team, _, _ = detect_team_query("conosci qualche ristorante a Bali?")
        # should not match the conosci pattern
        # (might still return False from all branches)
        result = detect_team_query("conosci qualche ristorante a Bali?")
        assert result[1] != "search_by_name" or not result[0]

    # --- generic non-team query ---

    def test_generic_non_team_query_returns_false(self):
        assert detect_team_query("What are the office hours?") == (False, "", "")

    def test_kitas_query_not_team(self):
        assert detect_team_query("How do I renew my KITAS?") == (False, "", "")
