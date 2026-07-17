"""
Tests for the liveness-tier normalization in claude_cli_enricher.

Growth-loop sprint B2 (2026-07-18): the additive 0-100 rubric was replaced
with a forced-choice tier (breaking/developing/evergreen) — the additive
rubric structurally amplified central-tendency bias (124/135 real items
scored exactly 0, the rest capped at 30, nothing above; live pool stayed
permanently empty). Research capture:
research/operations/2026-07-18-wr2-liveness-scoring-redesign.md.

Trust direction is now INVERTED from the pre-B2 module: the model's
`liveness_tier` is the validated signal; `live_news_score` is a DERIVED
compatibility value for the selector's `>=40` filter and #2631's
persistence contract — not a measurement. Downstream code still relies on
the invariant `tier == bucket(score)` (90->breaking, 60->developing,
0->evergreen under the existing 80/40 buckets), so score derivation must
keep hitting those exact buckets.
"""
from __future__ import annotations

import sys
from pathlib import Path


# Add scripts dir to path so the enricher imports work standalone (the
# bali-intel-scraper package layout is script-based, not installed).
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from claude_cli_enricher import (  # type: ignore  # noqa: E402
    ENRICHMENT_PROMPT_TEMPLATE,
    _normalize_live_news_fields,
)


# ---------------------------------------------------------------------------
# Guilt: tier drives the derived score deterministically.
# ---------------------------------------------------------------------------

def test_tier_breaking_derives_score_90() -> None:
    out = _normalize_live_news_fields({"liveness_tier": "breaking"})
    assert out["liveness_tier"] == "breaking"
    assert out["live_news_score"] == 90


def test_tier_developing_derives_score_60() -> None:
    out = _normalize_live_news_fields({"liveness_tier": "developing"})
    assert out["liveness_tier"] == "developing"
    assert out["live_news_score"] == 60


def test_tier_evergreen_derives_score_0() -> None:
    out = _normalize_live_news_fields({"liveness_tier": "evergreen"})
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_score"] == 0
    assert out["live_news_reasons"] == []


def test_tier_missing_defaults_to_evergreen() -> None:
    out = _normalize_live_news_fields({})
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_score"] == 0
    assert out["live_news_reasons"] == []


def test_tier_garbage_falls_back_to_evergreen() -> None:
    out = _normalize_live_news_fields({"liveness_tier": "hot"})
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_score"] == 0
    assert out["live_news_reasons"] == []


def test_stray_model_score_is_overridden_tier_wins() -> None:
    """The model MUST NOT output live_news_score anymore, but if it does
    (prompt drift / stray field), the validated tier wins — never the
    number. This is the trust-direction inversion this sprint exists for.
    """
    out = _normalize_live_news_fields({"liveness_tier": "evergreen", "live_news_score": 85})
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_score"] == 0


def test_stray_model_score_overridden_for_breaking_too() -> None:
    """Symmetric case: a stray low score must not downgrade a validated
    breaking tier either."""
    out = _normalize_live_news_fields({"liveness_tier": "breaking", "live_news_score": 5})
    assert out["liveness_tier"] == "breaking"
    assert out["live_news_score"] == 90


# ---------------------------------------------------------------------------
# Innocence: reasons pass through intact for non-evergreen tiers, sanitation
# rules from the pre-B2 module are unchanged.
# ---------------------------------------------------------------------------

def test_developing_reasons_preserved() -> None:
    out = _normalize_live_news_fields({
        "liveness_tier": "developing",
        "live_news_reasons": ["dated arrests at Ngurah Rai", "policy implication cited"],
    })
    assert out["live_news_reasons"] == ["dated arrests at Ngurah Rai", "policy implication cited"]


def test_evergreen_reasons_emptied_even_if_model_invented_some() -> None:
    out = _normalize_live_news_fields({
        "liveness_tier": "evergreen",
        "live_news_reasons": ["some hallucinated signal"],
    })
    assert out["live_news_reasons"] == []


def test_reasons_capped_at_three() -> None:
    out = _normalize_live_news_fields({
        "liveness_tier": "breaking",
        "live_news_reasons": ["one", "two", "three", "four", "five"],
    })
    assert len(out["live_news_reasons"]) == 3
    assert out["live_news_reasons"] == ["one", "two", "three"]


def test_reasons_truncated_at_200_chars() -> None:
    long = "x" * 500
    out = _normalize_live_news_fields({"liveness_tier": "breaking", "live_news_reasons": [long]})
    assert len(out["live_news_reasons"][0]) == 200


def test_reasons_filter_non_strings() -> None:
    out = _normalize_live_news_fields({
        "liveness_tier": "developing",
        "live_news_reasons": ["valid", None, 42, {"nested": "garbage"}, "also valid"],
    })
    assert out["live_news_reasons"] == ["valid"]
    # Note: cap-3 means we keep first 3 raw, then filter; "also valid" is
    # discarded because it's the 5th raw element. This is intentional —
    # if the model returned junk in slots 2-3 we'd rather keep the empty
    # slots than reach further in.


def test_reasons_filter_empty_strings() -> None:
    out = _normalize_live_news_fields({
        "liveness_tier": "developing",
        "live_news_reasons": ["", "  ", "real reason"],
    })
    # First 3 raw slots: "", "  ", "real reason". After strip-filter only
    # "real reason" survives (cap is applied before filter, then filter).
    assert out["live_news_reasons"] == ["real reason"]


def test_reasons_non_list_falls_back_to_empty() -> None:
    out = _normalize_live_news_fields({"liveness_tier": "developing", "live_news_reasons": "not a list"})
    assert out["live_news_reasons"] == []


def test_normalization_preserves_other_fields() -> None:
    """Mutates only live_news_*/liveness_tier keys; everything else passes
    through untouched."""
    enriched = {
        "headline": "Big News",
        "the_facts": "facts",
        "liveness_tier": "developing",
        "metadata": {"tags": ["foo"]},
    }
    out = _normalize_live_news_fields(enriched)
    assert out["headline"] == "Big News"
    assert out["the_facts"] == "facts"
    assert out["metadata"] == {"tags": ["foo"]}
    assert out["liveness_tier"] == "developing"
    assert out["live_news_score"] == 60


def test_invariant_tier_equals_bucket_of_derived_score() -> None:
    """Downstream WR2 selector code relies on tier == bucket(score) always
    holding after enrichment, under the existing 80/40 buckets."""
    for tier, expected_score in (("breaking", 90), ("developing", 60), ("evergreen", 0)):
        out = _normalize_live_news_fields({"liveness_tier": tier})
        score = out["live_news_score"]
        if score >= 80:
            bucket = "breaking"
        elif score >= 40:
            bucket = "developing"
        else:
            bucket = "evergreen"
        assert out["liveness_tier"] == bucket == tier
        assert score == expected_score


# ---------------------------------------------------------------------------
# Prompt-content assertions: forced-choice section present, calibrated
# anchors present, old additive section gone.
# ---------------------------------------------------------------------------

def test_prompt_has_forced_choice_section() -> None:
    assert "LIVENESS TIER (forced choice)" in ENRICHMENT_PROMPT_TEMPLATE


def test_prompt_has_the_three_real_developing_anchors() -> None:
    assert "15 WNA China dan Vietnam Ditangkap Usai Buka Lowongan Kerja" in ENRICHMENT_PROMPT_TEMPLATE
    assert "Immigration Cuts Visa-Free Entry by 87.91%" in ENRICHMENT_PROMPT_TEMPLATE
    assert "Empat Marketplace Besar Jadi Pemungut Pajak Mulai Agustus" in ENRICHMENT_PROMPT_TEMPLATE


def test_prompt_no_longer_has_additive_scoring_section() -> None:
    assert "LIVE NEWS SCORING" not in ENRICHMENT_PROMPT_TEMPLATE
