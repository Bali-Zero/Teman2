"""
Tests for the live-news scoring additions to scripts/wr2_topic_selector.py.

Locks down PR-1 §C behaviors:
  - score_item bonus = live_news_score / 2 (0..50 range)
  - score_item penalty = -20 when title matches a routine/evergreen pattern
  - liveness_tier passes through to detail rules (and falls back to
    "evergreen" on missing/garbage values, matching the enricher's
    normalization invariant from §B)
  - the score_item caller path tolerates legacy items with no
    live_news_score / liveness_tier fields (returns 0 bonus, no penalty
    unless the title pattern fires)

These are the rules a downstream operator needs to be able to reason
about when triaging "why did the selector pick draft X over Y today?"
from the scored top-5 log line, so we lock the specific point values.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

# Make scripts/ importable. wr2_topic_selector.py imports asyncpg/httpx at
# module load — both are in the backend-rag venv so the test runner picks
# them up via PYTHONPATH=. from repo root.
SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_topic_selector import (  # noqa: E402
    LIVE_NEWS_BONUS_DIVISOR,
    ROUTINE_TITLE_PENALTY,
    score_item,
)


def _base_item(**overrides) -> dict:
    """A minimal staging item that scores to ~5 base points (T3, no kw, stale).

    Tests override only the fields they care about — keeping the base
    constant means the asserted deltas come from §C bonuses/penalties only.
    """
    item = {
        "title": "Generic news item from Indonesia",
        "content": "lorem ipsum",
        "tier": "T3",
        # No detected_at / published_at → falls back to age=24h, fresh_score≈20
    }
    item.update(overrides)
    return item


def test_evergreen_item_gets_no_live_bonus() -> None:
    score, detail = score_item(_base_item())
    assert detail["rules"]["live_news_score"] == 0
    assert detail["rules"]["live_news_bonus"] == 0
    assert detail["rules"]["liveness_tier"] == "evergreen"


def test_breaking_score_80_gets_40_point_bonus() -> None:
    score, detail = score_item(_base_item(
        live_news_score=80,
        liveness_tier="breaking",
    ))
    assert detail["rules"]["live_news_score"] == 80
    assert detail["rules"]["live_news_bonus"] == 80 / LIVE_NEWS_BONUS_DIVISOR  # 40
    assert detail["rules"]["liveness_tier"] == "breaking"


def test_developing_score_60_gets_30_point_bonus() -> None:
    score, detail = score_item(_base_item(
        live_news_score=60,
        liveness_tier="developing",
    ))
    assert detail["rules"]["live_news_bonus"] == 60 / LIVE_NEWS_BONUS_DIVISOR  # 30


def test_breaking_score_100_gets_50_point_bonus() -> None:
    score, detail = score_item(_base_item(
        live_news_score=100,
        liveness_tier="breaking",
    ))
    assert detail["rules"]["live_news_bonus"] == 50.0


def test_score_clamped_above_100() -> None:
    """Defense-in-depth: even if upstream missed it, selector clamps to 100."""
    _, detail = score_item(_base_item(live_news_score=250))
    assert detail["rules"]["live_news_score"] == 100
    assert detail["rules"]["live_news_bonus"] == 50.0


def test_score_clamped_below_0() -> None:
    _, detail = score_item(_base_item(live_news_score=-30))
    assert detail["rules"]["live_news_score"] == 0
    assert detail["rules"]["live_news_bonus"] == 0


def test_score_string_coerced() -> None:
    _, detail = score_item(_base_item(live_news_score="55"))
    assert detail["rules"]["live_news_score"] == 55
    assert detail["rules"]["live_news_bonus"] == 27.5


def test_score_garbage_falls_back_to_zero() -> None:
    _, detail = score_item(_base_item(live_news_score="not a number"))
    assert detail["rules"]["live_news_score"] == 0
    assert detail["rules"]["live_news_bonus"] == 0


def test_invalid_liveness_tier_falls_back_to_evergreen() -> None:
    _, detail = score_item(_base_item(
        live_news_score=85,
        liveness_tier="hot",  # not in {breaking,developing,evergreen}
    ))
    # Tier passes through normalized to evergreen, but the bonus from the
    # numeric score is still applied — the selector trusts the score, not
    # the (possibly drifted) tier label.
    assert detail["rules"]["liveness_tier"] == "evergreen"
    assert detail["rules"]["live_news_bonus"] == 42.5


@pytest.mark.parametrize("title", [
    "How to apply for KITAS in 2026",
    "Guide to PT PMA company setup",
    "The Complete Guide to Bali Property Investment",
    "KITAS Renewal Explained",
    "Indonesian Tax Code Decoded",
    "Step-by-step KBLI 2026 navigator",
    "Step by step KBLI 2026 navigator",
    "Everything you need to know about NPWP",
])
def test_routine_title_pattern_triggers_penalty(title: str) -> None:
    _, detail = score_item(_base_item(title=title))
    assert detail["rules"]["routine_penalty"] == ROUTINE_TITLE_PENALTY


@pytest.mark.parametrize("title", [
    "BKPM tightens foreign investment rules",
    "Indonesia deports 12 nationals over visa fraud",
    "New PNBP fees announced for 2026",
    "Bali property market: Q1 2026 numbers",
])
def test_news_title_no_penalty(title: str) -> None:
    _, detail = score_item(_base_item(title=title))
    assert detail["rules"]["routine_penalty"] == 0


def test_routine_penalty_subtracted_from_total() -> None:
    """Two items with identical keyword/tier/freshness — only the title
    pattern differs. The routine title pays the -20 penalty, the news
    title doesn't. This is the only place where the penalty contribution
    can be measured cleanly.
    """
    # Identical keyword content — only the title prefix differs (routine vs
    # news shape). Other scoring inputs (kw match, tier, freshness) match
    # exactly, so the score delta isolates the penalty contribution.
    base = {
        "content": "kitas visa imigrasi",  # same kw matches both items
        "tier": "T2",
    }
    score_routine, detail_routine = score_item({
        "title": "How to renew status",  # routine pattern, no kw in title
        **base,
    })
    score_news, detail_news = score_item({
        "title": "Officials confirm policy change",  # news, no kw in title
        **base,
    })
    assert detail_routine["rules"]["routine_penalty"] == ROUTINE_TITLE_PENALTY
    assert detail_news["rules"]["routine_penalty"] == 0
    assert detail_routine["rules"]["keywords_points"] == detail_news["rules"]["keywords_points"]
    # Same base, different penalty → exactly ROUTINE_TITLE_PENALTY apart
    assert score_routine == pytest.approx(score_news - ROUTINE_TITLE_PENALTY)


def test_breaking_news_outscores_routine_guide_with_same_keywords() -> None:
    """The end-to-end intent of §C: a breaking news item with score 85 must
    beat a routine guide on the same topic."""
    breaking_score, _ = score_item({
        "title": "BKPM raids 5 unlicensed PT PMAs in Jakarta",
        "content": "kitas visa investor pma kbli",
        "tier": "T1",
        "live_news_score": 85,
        "liveness_tier": "breaking",
    })
    routine_score, _ = score_item({
        "title": "The Complete Guide to PT PMA in 2026",
        "content": "kitas visa investor pma kbli",
        "tier": "T1",
        # No live_news_score → 0
    })
    assert breaking_score > routine_score
    # And by a wide margin: bonus +42.5 plus penalty +20 of separation
    assert (breaking_score - routine_score) >= 60


def test_legacy_item_without_live_news_fields_works() -> None:
    """Items predating §B (no live_news_score in payload) must still score
    cleanly with the bonus = 0 and the tier defaulting to evergreen."""
    item = {
        "title": "Indonesian rupiah hits 16,500 against dollar",
        "content": "rupiah dollar exchange",
        "tier": "T2",
    }
    score, detail = score_item(item)
    assert detail["rules"]["live_news_score"] == 0
    assert detail["rules"]["liveness_tier"] == "evergreen"
    assert detail["rules"]["routine_penalty"] == 0
    assert score > 0  # base scoring still gives points
