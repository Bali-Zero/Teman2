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

B2 red-team round (Codex, 2026-07-18) added 5 hardening fixes (F1-F5):
F1 — normalize raw_tier defensively BEFORE membership check (case/whitespace,
never crash on a non-str type like list/dict). F2 — legacy/truncated
score-only output (`{"live_news_score": 85}`, no tier) still derives a tier
via the pre-B2 80/40 buckets instead of collapsing to evergreen. F3 — the
prompt's OUTPUT FORMAT no longer shows a literal `"evergreen"` default
(anchoring risk now that tier is authoritative) — a bracket placeholder
instead. F4 — prompt-only: AS OF context + relative dates in the breaking
anchors + enforcement-vs-pattern disambiguation for arrests. F5 — reasons
truncation buffer lowered from 200 to 120 chars.
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
# F1 (HIGH, Codex red-team): raw_tier must be normalized (case/whitespace)
# BEFORE the membership check, and must never crash on a non-str type — the
# pre-fix code did `raw_tier in _TIER_TO_SCORE` directly, which raises
# TypeError: unhashable type for a list/dict value.
# ---------------------------------------------------------------------------

def test_tier_case_insensitive() -> None:
    out = _normalize_live_news_fields({"liveness_tier": "Developing"})
    assert out["liveness_tier"] == "developing"
    assert out["live_news_score"] == 60


def test_tier_whitespace_stripped() -> None:
    out = _normalize_live_news_fields({"liveness_tier": " developing "})
    assert out["liveness_tier"] == "developing"
    assert out["live_news_score"] == 60


def test_tier_list_value_no_crash() -> None:
    """Pre-fix: `["breaking"] in _TIER_TO_SCORE` raises TypeError (unhashable
    type: 'list'). Post-fix: non-str tier values are never used as a dict
    membership key — they fall through to evergreen (no score to derive
    from) without an exception."""
    out = _normalize_live_news_fields({"liveness_tier": ["breaking"]})
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_score"] == 0


def test_tier_dict_value_no_crash() -> None:
    """Same TypeError class as the list case, dict is unhashable too."""
    out = _normalize_live_news_fields({"liveness_tier": {"tier": "x"}})
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_score"] == 0


# ---------------------------------------------------------------------------
# F2 (HIGH, Codex red-team): legacy/truncated score-only output — a model
# response that dropped `liveness_tier` but still carries `live_news_score`
# (e.g. a truncated JSON parse, or a #2631-era output) must not collapse to
# evergreen/0 and silently discard the signal. Fall back to deriving the
# tier from the score via the pre-B2 80/40 buckets, then re-derive the
# canonical score from THAT tier so the tier==bucket(score) invariant holds.
# ---------------------------------------------------------------------------

def test_score_only_legacy_output_85_derives_breaking() -> None:
    out = _normalize_live_news_fields({"live_news_score": 85})
    assert out["liveness_tier"] == "breaking"
    assert out["live_news_score"] == 90


def test_score_only_legacy_output_55_derives_developing() -> None:
    out = _normalize_live_news_fields({"live_news_score": 55})
    assert out["liveness_tier"] == "developing"
    assert out["live_news_score"] == 60


def test_score_only_legacy_output_garbage_falls_back_to_evergreen() -> None:
    out = _normalize_live_news_fields({"live_news_score": "high"})
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_score"] == 0


def test_score_only_fallback_never_fires_when_tier_is_valid() -> None:
    """Regression guard: the F2 fallback must only trigger when the tier is
    ABSENT/invalid — a valid tier (even 'evergreen') always wins over any
    score, matching test_stray_model_score_is_overridden_tier_wins above."""
    out = _normalize_live_news_fields({"liveness_tier": "evergreen", "live_news_score": 85})
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_score"] == 0


# ---------------------------------------------------------------------------
# F3 (HIGH, Codex red-team): the OUTPUT FORMAT template used to show a
# literal `"liveness_tier": "evergreen"` default — an anchoring risk now
# that the tier is authoritative (same central-tendency-bias shape as the
# additive rubric this sprint replaced). Must be a bracket placeholder.
# ---------------------------------------------------------------------------

def test_prompt_template_does_not_default_to_evergreen_literal() -> None:
    assert '"liveness_tier": "evergreen"' not in ENRICHMENT_PROMPT_TEMPLATE


def test_prompt_template_has_tier_placeholder() -> None:
    assert '"liveness_tier": "<breaking|developing|evergreen>"' in ENRICHMENT_PROMPT_TEMPLATE


def test_normalizer_handles_literal_placeholder_copy() -> None:
    """If Claude echoes the template placeholder literally instead of
    picking a real tier, the normalizer must not crash and must fall back
    to evergreen (passes through the F1 str-normalize + F2 score-fallback
    path — no live_news_score present here, so lands on evergreen)."""
    out = _normalize_live_news_fields({"liveness_tier": "<breaking|developing|evergreen>"})
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_score"] == 0


# ---------------------------------------------------------------------------
# F4 (MEDIUM/partial, Codex red-team): prompt-only. AS OF context anchors
# "last ~48h" to the actual current date instead of nothing; breaking
# anchors use relative dates (a frozen absolute date goes stale as the
# calendar moves and mis-anchors the corpus); arrests are disambiguated —
# breaking only for <48h enforcement with immediate effect, dated arrests
# as part of a broader pattern are developing. (Selector-side change is
# NOT needed — MAX_ARTICLE_AGE_HOURS=72 hard cutoff on fresh_items already
# covers the downstream staleness concern Codex raised.)
# ---------------------------------------------------------------------------

def test_prompt_has_as_of_context() -> None:
    assert "AS OF" in ENRICHMENT_PROMPT_TEMPLATE
    assert "{as_of}" in ENRICHMENT_PROMPT_TEMPLATE


def test_prompt_formats_with_as_of_parameter() -> None:
    """enrich_article_claude_cli must pass as_of (UTC ISO date) into the
    template — this is what anchors the breaking/developing 48h window to
    today instead of to whatever date happened to be baked into the
    calibrated anchors at prompt-authoring time."""
    formatted = ENRICHMENT_PROMPT_TEMPLATE.format(
        title="t", source="s", category="c", published_date="p", content="x",
        nlm_legal_basis="", nlm_web_findings="",
        as_of="2026-07-18T00:00:00+00:00",
    )
    assert "2026-07-18T00:00:00+00:00" in formatted


def test_prompt_breaking_anchor_has_no_frozen_absolute_date() -> None:
    """The original B2 breaking anchor baked in a literal 2026-07-17 date —
    exactly the staleness trap AS OF exists to avoid. Anchors must use
    relative time language instead."""
    assert "2026-07-17" not in ENRICHMENT_PROMPT_TEMPLATE


def test_prompt_disambiguates_dated_arrests_as_pattern() -> None:
    assert "pattern" in ENRICHMENT_PROMPT_TEMPLATE.lower()


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


def test_reasons_truncated_at_120_chars() -> None:
    """F5: buffer lowered from 200 to 120 — still well above the prompt's
    ≤80-char instruction (tolerates minor model overshoot) but bounded
    tighter than the old 200 to keep the reasons list actually short."""
    long = "x" * 500
    out = _normalize_live_news_fields({"liveness_tier": "breaking", "live_news_reasons": [long]})
    assert len(out["live_news_reasons"][0]) == 120


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
