"""Tests for ConsiglioV1 orchestrator — claims, voting, Gate 6 predicate."""

from __future__ import annotations

from backend.services.research.consiglio_orchestrator import (
    ConsiglioClaim,
    ConsiglioResult,
    ConsiglioV1,
)


def test_claim_agreement_count():
    c = ConsiglioClaim(
        key="cadence_instagram_posts_per_day",
        value=1.0,
        votes={"claude": True, "gemini": True, "deepseek": True, "notebooklm": False},
    )
    assert c.agreement_count() == 3
    assert c.is_disputed() is False


def test_claim_disputed_when_below_3():
    c = ConsiglioClaim(
        key="format_linkedin_authority_tecnico",
        value="long_post",
        votes={"claude": True, "gemini": True, "deepseek": False, "notebooklm": False},
    )
    assert c.agreement_count() == 2
    assert c.is_disputed() is True


def test_claim_is_disputed_respects_custom_threshold():
    """3-LLM minimum is default; with only 2 responding LLMs, 2/2 passes."""
    c = ConsiglioClaim(
        key="x",
        value="y",
        votes={"claude": True, "deepseek": True},  # gemini + notebooklm missing
    )
    # With 2 present votes + both True → agreement=2. Default threshold
    # is 3, so this is disputed. But lowered to 2, it's not.
    assert c.agreement_count() == 2
    assert c.is_disputed(min_agreement=3) is True
    assert c.is_disputed(min_agreement=2) is False


def test_result_gate_6_passes_when_all_claims_reach_quorum():
    claims = [
        ConsiglioClaim(
            key="k1", value="v",
            votes={"claude": True, "gemini": True, "deepseek": True, "notebooklm": True},
        ),
        ConsiglioClaim(
            key="k2", value="v",
            votes={"claude": True, "gemini": True, "deepseek": True, "notebooklm": False},
        ),
    ]
    result = ConsiglioResult(claims=claims, meta={})
    assert result.gate_6_passes()


def test_result_gate_6_fails_if_any_claim_disputed():
    claims = [
        ConsiglioClaim(
            key="k1", value="v",
            votes={"claude": True, "gemini": True, "deepseek": True, "notebooklm": False},
        ),
        ConsiglioClaim(
            key="k2", value="v",
            votes={"claude": True, "gemini": False, "deepseek": False, "notebooklm": False},
        ),
    ]
    result = ConsiglioResult(claims=claims, meta={})
    assert result.gate_6_passes() is False
    assert result.disputed_keys() == ["k2"]


def test_result_gate_6_adapts_to_available_voters():
    """If only 2 LLMs responded across all claims, Gate 6 requires 2/2."""
    claims = [
        ConsiglioClaim(
            key="k1", value="v",
            votes={"claude": True, "deepseek": True},
        ),
        ConsiglioClaim(
            key="k2", value="v",
            votes={"claude": True, "deepseek": False},
        ),
    ]
    result = ConsiglioResult(claims=claims, meta={"active_llms": 2})
    # With only 2 voters, threshold auto-adjusts to 2 (full agreement required)
    assert result.gate_6_passes(min_agreement=2) is False  # k2 has only 1/2
    assert result.disputed_keys(min_agreement=2) == ["k2"]


def test_values_agree_fuzzy_strings():
    assert ConsiglioV1._values_agree("long_post", "long_post") is True
    assert ConsiglioV1._values_agree("Long_Post ", "long_post") is True
    assert ConsiglioV1._values_agree("long_post", "carousel") is False


def test_values_agree_scalars():
    assert ConsiglioV1._values_agree(1.0, 1.0) is True
    assert ConsiglioV1._values_agree(1.0, 1.0001) is False  # strict equality
    assert ConsiglioV1._values_agree([1, 2], [1, 2]) is True
    assert ConsiglioV1._values_agree(None, None) is True


def test_values_agree_type_mismatch():
    assert ConsiglioV1._values_agree("1.0", 1.0) is False
