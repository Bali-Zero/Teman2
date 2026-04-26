"""
Tests for the live_news_score normalization in claude_cli_enricher.

Locks down the post-Claude defensive normalization: clamping the score,
deriving the tier deterministically from the score, and sanitizing the
reasons list. This is the boundary downstream WR2 selector relies on:
after enrichment, `tier == bucket(score)` always holds and reasons is
always a list of clean strings (or empty).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add scripts dir to path so the enricher imports work standalone (the
# bali-intel-scraper package layout is script-based, not installed).
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from claude_cli_enricher import _normalize_live_news_fields  # type: ignore  # noqa: E402


def test_score_below_40_is_evergreen() -> None:
    out = _normalize_live_news_fields({"live_news_score": 30, "liveness_tier": "ignored"})
    assert out["live_news_score"] == 30
    assert out["liveness_tier"] == "evergreen"


def test_score_40_is_developing() -> None:
    """40 is the breaking-down threshold; must round into developing not evergreen."""
    out = _normalize_live_news_fields({"live_news_score": 40})
    assert out["liveness_tier"] == "developing"


def test_score_79_is_developing() -> None:
    out = _normalize_live_news_fields({"live_news_score": 79})
    assert out["liveness_tier"] == "developing"


def test_score_80_is_breaking() -> None:
    out = _normalize_live_news_fields({"live_news_score": 80})
    assert out["liveness_tier"] == "breaking"


def test_score_100_is_breaking() -> None:
    out = _normalize_live_news_fields({"live_news_score": 100})
    assert out["liveness_tier"] == "breaking"


def test_score_clamped_above_100() -> None:
    """Claude occasionally returns 250 when prompted to sum signals."""
    out = _normalize_live_news_fields({"live_news_score": 250})
    assert out["live_news_score"] == 100
    assert out["liveness_tier"] == "breaking"


def test_score_clamped_below_0() -> None:
    out = _normalize_live_news_fields({"live_news_score": -10})
    assert out["live_news_score"] == 0
    assert out["liveness_tier"] == "evergreen"


def test_score_string_coerced() -> None:
    """Some model outputs return numbers as strings."""
    out = _normalize_live_news_fields({"live_news_score": "55"})
    assert out["live_news_score"] == 55
    assert out["liveness_tier"] == "developing"


def test_score_garbage_falls_back_to_zero() -> None:
    out = _normalize_live_news_fields({"live_news_score": "high"})
    assert out["live_news_score"] == 0
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_reasons"] == []


def test_score_float_rounded() -> None:
    """Bayesian-leaning models sometimes return 78.4."""
    out = _normalize_live_news_fields({"live_news_score": 78.6})
    assert out["live_news_score"] == 79


def test_missing_score_defaults_to_zero() -> None:
    out = _normalize_live_news_fields({})
    assert out["live_news_score"] == 0
    assert out["liveness_tier"] == "evergreen"
    assert out["live_news_reasons"] == []


def test_tier_recomputed_even_when_model_disagrees() -> None:
    """Don't trust Claude's tier — recompute from score deterministically.

    The downstream WR2 selector reads tier and assumes it's bucket(score).
    If Claude returned score=85 but tier='evergreen' (we've seen this), the
    selector would silently route a breaking story to the routine queue.
    """
    out = _normalize_live_news_fields({"live_news_score": 85, "liveness_tier": "evergreen"})
    assert out["liveness_tier"] == "breaking"


def test_reasons_capped_at_three() -> None:
    out = _normalize_live_news_fields({
        "live_news_score": 80,
        "live_news_reasons": ["one", "two", "three", "four", "five"],
    })
    assert len(out["live_news_reasons"]) == 3
    assert out["live_news_reasons"] == ["one", "two", "three"]


def test_reasons_truncated_at_200_chars() -> None:
    long = "x" * 500
    out = _normalize_live_news_fields({"live_news_score": 80, "live_news_reasons": [long]})
    assert len(out["live_news_reasons"][0]) == 200


def test_reasons_filter_non_strings() -> None:
    out = _normalize_live_news_fields({
        "live_news_score": 50,
        "live_news_reasons": ["valid", None, 42, {"nested": "garbage"}, "also valid"],
    })
    assert out["live_news_reasons"] == ["valid"]
    # Note: cap-3 means we keep first 3 raw, then filter; "also valid" is
    # discarded because it's the 5th raw element. This is intentional —
    # if the model returned junk in slots 2-3 we'd rather keep the empty
    # slots than reach further in.


def test_reasons_filter_empty_strings() -> None:
    out = _normalize_live_news_fields({
        "live_news_score": 50,
        "live_news_reasons": ["", "  ", "real reason"],
    })
    # First 3 raw slots: "", "  ", "real reason". After strip-filter only
    # "real reason" survives (cap is applied before filter, then filter).
    assert out["live_news_reasons"] == ["real reason"]


def test_reasons_zeroed_when_score_is_zero() -> None:
    """If we couldn't find any signals, reasons must be empty even if model invented some."""
    out = _normalize_live_news_fields({
        "live_news_score": 0,
        "live_news_reasons": ["some hallucinated signal"],
    })
    assert out["live_news_reasons"] == []


def test_reasons_non_list_falls_back_to_empty() -> None:
    out = _normalize_live_news_fields({"live_news_score": 50, "live_news_reasons": "not a list"})
    assert out["live_news_reasons"] == []


def test_normalization_preserves_other_fields() -> None:
    """Mutates only live_news_* keys; everything else passes through untouched."""
    enriched = {
        "headline": "Big News",
        "the_facts": "facts",
        "live_news_score": 50,
        "metadata": {"tags": ["foo"]},
    }
    out = _normalize_live_news_fields(enriched)
    assert out["headline"] == "Big News"
    assert out["the_facts"] == "facts"
    assert out["metadata"] == {"tags": ["foo"]}
    assert out["live_news_score"] == 50
    assert out["liveness_tier"] == "developing"
