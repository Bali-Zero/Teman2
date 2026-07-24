"""Tests for wr2_creative_ledger.py — the Creative Ledger read-model + the
DORMANT reward socket (WR2 editorial-intelligence Fase 4, spec §Mossa-D).

Batteries (mirroring the best-effort + per-row-isolation + cold-start
discipline `test_wr2_draft_generator_kicker_variety.py` already uses for
`fetch_recent_editorial_signatures`):

  - fetch_creative_ledger extraction: native arc, backfilled arc, layout
    families, register, published flag, reward_live_count.
  - best-effort + per-row isolation: connection error → empty snapshot; one
    malformed row skipped without zeroing the healthy rows.
  - cold-start: no arcs → entries with arc=None (never a crash, never a
    malformed row).
  - reward DORMANCY (the load-bearing invariant): reward_live_count==0 ⇒
    reward_by_arc()=={} ; a synthetic published deck ⇒ non-empty boosts.
  - build_arc_priors dormant identity: reward None vs {} both byte-identical
    to the pre-Fase-4 path; a real reward dict shifts the named arc UP and
    never below the cooldown floor.
  - drift tripwire: the backfill's RATIFIED_ARCS == ir.ARCS (scar #9).

Zero network, zero real DB — conn is an AsyncMock, exactly the module-under-
test's own I/O discipline (it only READS via conn.fetch, best-effort).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_carousel_ir as ir  # noqa: E402
import wr2_creative_ledger as wcl  # noqa: E402
import wr2_planner_writer as pw  # noqa: E402


def _row(
    *,
    draft_id: str = "d1",
    created_at: str = "2026-07-25T00:00:00Z",
    register: str | None = "analitico",
    slides_json=None,
    council_debate_json=None,
    published: bool = False,
) -> dict:
    return {
        "id": draft_id,
        "created_at": created_at,
        "register": register,
        "slides_json": slides_json,
        "council_debate_json": council_debate_json,
        "published": published,
    }


def _conn(rows: list[dict]) -> MagicMock:
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows)
    return conn


# ── fetch_creative_ledger extraction ──────────────────────────────────────


@pytest.mark.asyncio
async def test_native_arc_and_axes_are_extracted() -> None:
    conn = _conn([
        _row(
            council_debate_json={"arc": "news_alert", "spine": "the rule changed today", "hook_type": "stat"},
            slides_json={"slides": [
                {"layout_family": "cover-photo"},
                {"layout_family": "evidence-carved"},
                {"layout_family": "evidence-carved"},  # dup → deduped
            ]},
            register="militante",
            published=False,
        )
    ])
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    assert len(snap.entries) == 1
    e = snap.entries[0]
    assert e.arc == "news_alert"
    assert e.arc_source == "native"
    assert e.spine_gist == "the rule changed today"
    assert e.hook_type == "stat"
    assert e.register == "militante"
    assert e.layout_families == ["cover-photo", "evidence-carved"]
    assert e.published is False
    assert snap.reward_live_count == 0


@pytest.mark.asyncio
async def test_backfilled_arc_is_recovered_when_no_native_arc() -> None:
    conn = _conn([
        _row(council_debate_json={
            "some_monolith_key": "x",
            "backfill": {"arc": "deadline", "spine_gist": "act before the SPT date", "hook_type": "list"},
        })
    ])
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    e = snap.entries[0]
    assert e.arc == "deadline"
    assert e.arc_source == "backfill"
    assert e.spine_gist == "act before the SPT date"
    assert e.hook_type == "list"


@pytest.mark.asyncio
async def test_native_arc_wins_over_backfill() -> None:
    conn = _conn([
        _row(council_debate_json={
            "arc": "explainer",
            "backfill": {"arc": "news_alert", "spine_gist": "x", "hook_type": "stat"},
        })
    ])
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    assert snap.entries[0].arc == "explainer"
    assert snap.entries[0].arc_source == "native"


@pytest.mark.asyncio
async def test_json_string_blobs_are_parsed() -> None:
    import json
    conn = _conn([
        _row(
            council_debate_json=json.dumps({"arc": "comparison"}),
            slides_json=json.dumps({"slides": [{"layout_family": "stat-card-hero"}]}),
        )
    ])
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    assert snap.entries[0].arc == "comparison"
    assert snap.entries[0].layout_families == ["stat-card-hero"]


@pytest.mark.asyncio
async def test_published_flag_counts_reward_live() -> None:
    conn = _conn([
        _row(draft_id="d1", council_debate_json={"arc": "news_alert"}, published=True),
        _row(draft_id="d2", council_debate_json={"arc": "deadline"}, published=False),
    ])
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    assert snap.reward_live_count == 1
    assert [e.published for e in snap.entries] == [True, False]


# ── best-effort + per-row isolation + cold-start ──────────────────────────


@pytest.mark.asyncio
async def test_connection_error_returns_empty_snapshot() -> None:
    conn = MagicMock()
    conn.fetch = AsyncMock(side_effect=RuntimeError("connection reset"))
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    assert snap.entries == []
    assert snap.reward_live_count == 0
    assert snap.recent_arcs() == []
    assert snap.reward_by_arc() == {}


@pytest.mark.asyncio
async def test_one_malformed_row_does_not_zero_the_healthy_rows() -> None:
    conn = _conn([
        _row(draft_id="good1", council_debate_json={"arc": "news_alert"}),
        _row(draft_id="bad", council_debate_json="{not valid json at all"),
        _row(draft_id="good2", council_debate_json={"arc": "deadline"}),
    ])
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    ids = [e.draft_id for e in snap.entries]
    assert ids == ["good1", "good2"]
    assert snap.recent_arcs() == ["news_alert", "deadline"]


@pytest.mark.asyncio
async def test_cold_start_monolith_deck_has_arc_none_not_a_crash() -> None:
    conn = _conn([
        _row(council_debate_json={"register_reason": "monolith-era blob, no arc key"}),
        _row(council_debate_json=None),
    ])
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    assert len(snap.entries) == 2
    assert all(e.arc is None and e.arc_source is None for e in snap.entries)
    assert snap.recent_arcs() == []  # None arcs dropped


@pytest.mark.asyncio
async def test_empty_db_is_cold_start_not_error() -> None:
    snap = await wcl.fetch_creative_ledger(_conn([]), limit=8)
    assert snap.entries == []
    assert snap.reward_by_arc() == {}


# ── reward DORMANCY (the invariant) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_reward_dormant_when_nothing_published() -> None:
    conn = _conn([
        _row(draft_id="d1", council_debate_json={"arc": "news_alert"}, published=False),
        _row(draft_id="d2", council_debate_json={"arc": "news_alert"}, published=False),
    ])
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    assert snap.reward_live_count == 0
    assert snap.reward_by_arc() == {}  # DORMANT — no reward signal


@pytest.mark.asyncio
async def test_reward_active_when_a_deck_is_published() -> None:
    conn = _conn([
        _row(draft_id="d1", council_debate_json={"arc": "deadline"}, published=True),
        _row(draft_id="d2", council_debate_json={"arc": "deadline"}, published=True),
        _row(draft_id="d3", council_debate_json={"arc": "explainer"}, published=False),
    ])
    snap = await wcl.fetch_creative_ledger(conn, limit=8)
    assert snap.reward_live_count == 2
    reward = snap.reward_by_arc()
    assert "deadline" in reward and reward["deadline"] > 0
    assert "explainer" not in reward  # never published → no boost


# ── build_arc_priors DORMANT IDENTITY (falsifiable, spec invariant) ───────


def test_priors_reward_none_equals_reward_empty_equals_pre_fase4() -> None:
    recent = ["news_alert", "deadline"]
    base = pw.build_arc_priors(recent, "breaking")  # pre-Fase-4 2-arg call still works
    with_none = pw.build_arc_priors(recent, "breaking", None)
    with_empty = pw.build_arc_priors(recent, "breaking", {})
    assert base == with_none == with_empty


def test_priors_shift_up_under_a_live_reward() -> None:
    recent = ["news_alert"]
    dormant = pw.build_arc_priors(recent, None, {})
    live = pw.build_arc_priors(recent, None, {"explainer": 0.30})
    assert live["explainer"] > dormant["explainer"]
    # every OTHER arc is untouched by the reward
    for arc in ir.ARCS:
        if arc != "explainer":
            assert live[arc] == dormant[arc]


def test_reward_boost_never_pulls_a_cooled_arc_below_floor() -> None:
    # a reward only ADDS — it can never push a weight below _MIN_WEIGHT
    live = pw.build_arc_priors(["news_alert"], None, {"news_alert": 0.30})
    assert live["news_alert"] >= pw._MIN_WEIGHT


# ── drift tripwire (scar #9) ──────────────────────────────────────────────


def test_backfill_ratified_arcs_match_ir_arcs_ssot() -> None:
    import wr2_ledger_backfill as bf
    assert bf.RATIFIED_ARCS == tuple(ir.ARCS.keys())


def test_ledger_sql_keeps_the_null_council_filter() -> None:
    # Regression pin (2026-07-25 cross-family red-team): the LIMIT-8 arc window
    # must exclude NULL-council rows exactly as the old fetch_recent_arcs did,
    # or recent_arcs() diverges from the pre-Fase-4 cooldown input. This filter
    # was dropped once and caught by review — pin it so it can't silently vanish.
    assert "council_debate_json IS NOT NULL" in wcl._LEDGER_SQL
    assert "ORDER BY d.created_at DESC" in wcl._LEDGER_SQL
