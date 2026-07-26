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


# ══════════════════════════════════════════════════════════════════════════
# Fase 4b — AXIS-ENGAGEMENT reward (per-axis SOFT nudge from the review queue)
# ══════════════════════════════════════════════════════════════════════════


def _post(
    *,
    reach,
    layout: str | None = None,
    tone: str | None = None,
    domain: str | None = None,
    metrics: bool = True,
) -> dict:
    d: dict = {"state": "published"}
    if metrics:
        d["engagement_metrics"] = {"reach": reach}
    if layout is not None:
        d["layout_family_primary"] = layout
    if tone is not None:
        d["tone_register_primary"] = tone
    if domain is not None:
        d["domain"] = domain
    return d


def _write_queue(tmp_path, posts) -> Path:
    import json
    p = tmp_path / "queue.json"
    p.write_text(json.dumps(posts))
    return p


def test_axis_engagement_aggregates_ranks_and_drops_noise(tmp_path) -> None:
    # guilt: median reach per axis value, sorted high→low; noise-guard drops n<3.
    # (Every value in a group is identical here, so mean == median — this test is
    # deliberately estimator-BLIND. The estimator itself is pinned by the skew
    # tests below, which is exactly what this one could never catch.)
    posts = (
        [_post(reach=30000, layout="cover-photo") for _ in range(3)]        # mean 30k, n=3
        + [_post(reach=5000, layout="dark-status-list") for _ in range(4)]  # mean 5k,  n=4
        + [_post(reach=99999, layout="rare-once") for _ in range(2)]        # n=2 → dropped
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    lf = ae.by_axis["layout_family_primary"]
    vals = [v for v, _, _ in lf]
    assert vals == ["cover-photo", "dark-status-list"]   # sorted high→low
    assert "rare-once" not in vals                        # n<_MIN_AXIS_SAMPLES dropped
    assert lf[0][2] == 3                                  # n reported
    assert abs(lf[0][1] - 30000) < 1                      # reach statistic reported
    assert ae.total_posts == 9                            # every reach>0 post counted
    assert ae.has_signal


# ── SKEW: rank by MEDIAN, not mean (2026-07-25 study on the real corpus) ────
# These four reproduce the measured shape: one viral post was 31.6% of all reach
# in the live corpus, and the mean therefore ranked its CARRIER. Every assertion
# below FAILS under `sum(rs)/len(rs)` — that is the point (a test that passes
# under both estimators pins nothing; the 31 pre-existing ones all did).

# Verbatim reach vectors measured on the Pro's review queue, 2026-07-25.
_REAL_COVER_PHOTO = [141240, 23704, 1360, 1220, 1193, 1185, 1140]   # mean 24,435 · median 1,220
_REAL_STATEMENT_BOMB = [47284, 34088, 30383, 23160, 13402, 2835, 1830, 683]  # mean 19,208 · median 18,281


def test_axis_engagement_ranks_by_median_not_mean_on_skewed_corpus(tmp_path) -> None:
    """GUILT (the scar): one viral post must not crown its layout.

    Under the old mean ranking cover-photo (24,435) outranked statement-bomb
    (19,208) purely on the 141,240 outlier, while its TYPICAL post (1,220) is
    below the corpus median. Median inverts it — correctly."""
    posts = (
        [_post(reach=r, layout="cover-photo") for r in _REAL_COVER_PHOTO]
        + [_post(reach=r, layout="statement-bomb") for r in _REAL_STATEMENT_BOMB]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    vals = [v for v, _, _ in ae.by_axis["layout_family_primary"]]
    assert vals[0] == "statement-bomb", "the consistently-strong layout must rank first"
    assert vals[-1] == "cover-photo", "the outlier-carried layout must rank LAST, not first"


def test_axis_engagement_reports_the_median_value_not_the_mean(tmp_path) -> None:
    """The NUMBER handed to the planner must be the typical post, not the average."""
    posts = [_post(reach=r, layout="cover-photo") for r in _REAL_COVER_PHOTO]
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    _, stat, n = ae.by_axis["layout_family_primary"][0]
    assert n == 7
    assert abs(stat - 1220) < 1, f"expected the median 1,220, got {stat}"
    assert stat < 2000, "the 24,435 mean would be a 20x overstatement of a typical post"


def test_axis_engagement_exposes_corpus_median_baseline(tmp_path) -> None:
    """The corpus baseline must be carried so the hint cannot overstate a tie."""
    posts = (
        [_post(reach=1000, layout="a") for _ in range(3)]
        + [_post(reach=3000, layout="b") for _ in range(3)]
        + [_post(reach=9000, layout="c") for _ in range(3)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    assert abs(ae.corpus_median - 3000) < 1     # median of the 9 counted posts
    assert ae.total_posts == 9


def test_axis_engagement_unskewed_corpus_still_ranks_the_higher_value_first(tmp_path) -> None:
    """INNOCENCE: where mean and median agree, the fix changes nothing."""
    posts = (
        [_post(reach=r, layout="strong") for r in (9000, 10000, 11000)]
        + [_post(reach=r, layout="weak") for r in (1000, 1100, 1200)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    vals = [v for v, _, _ in ae.by_axis["layout_family_primary"]]
    assert vals == ["strong", "weak"]


def test_engagement_hint_declares_median_and_states_the_corpus_baseline(tmp_path) -> None:
    """The prompt must not call a median an 'avg', and must give the baseline."""
    posts = (
        [_post(reach=r, layout="cover-photo", tone="rituale") for r in _REAL_COVER_PHOTO]
        + [_post(reach=r, layout="statement-bomb", tone="militante") for r in _REAL_STATEMENT_BOMB]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    hint = wcl.build_engagement_hint(ae)
    assert "typical reach" in hint
    assert "avg reach" not in hint, "a median labelled 'avg' misinforms the planner"
    assert "MEDIAN" in hint
    assert f"~{int(ae.corpus_median):,}" in hint, "corpus baseline must be stated"
    # The outlier-carried layout is not merely demoted — with a below-baseline
    # median (1,220 vs a 2,835 corpus median here) it is not named AT ALL.
    # Under the old mean it ranked FIRST and would appear: this is the assertion
    # that makes this test non-vacuous.
    assert "statement-bomb" in hint
    assert "cover-photo" not in hint


def test_hint_never_calls_a_below_baseline_value_higher_reaching(tmp_path) -> None:
    """GUILT: rank is not strength — the #2 of a weak axis can sit AT or BELOW the
    typical post. Measured on the real corpus: `analitico` ranked #2 among tones
    with median 2,237 while the corpus median was 2,288. Naming it "higher-
    reaching" would have been false, and the planner acts on that word."""
    posts = (
        [_post(reach=9000, tone="genuinely-strong") for _ in range(3)]
        + [_post(reach=3000, tone="exactly-baseline") for _ in range(3)]
        + [_post(reach=2000, tone="below-baseline") for _ in range(3)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    assert abs(ae.corpus_median - 3000) < 1
    # all three are RANKED (each has n=3, so they survive the noise guard)…
    assert [v for v, _, _ in ae.by_axis["tone_register_primary"]] == [
        "genuinely-strong", "exactly-baseline", "below-baseline",
    ]
    # …but only the one that BEATS the baseline may be named to the planner.
    assert [v for v, _, _ in ae.above_baseline("tone_register_primary")] == ["genuinely-strong"]
    hint = wcl.build_engagement_hint(ae)
    assert "genuinely-strong" in hint
    assert "below-baseline" not in hint
    assert "exactly-baseline" not in hint, "a TIE with the typical post is not 'higher-reaching'"


def test_hint_is_empty_when_nothing_beats_the_baseline(tmp_path) -> None:
    """INNOCENCE/safe-state: an axis with no real winner is simply not named, and
    a corpus with no winner anywhere degrades to the byte-identical no-hint path
    rather than inventing a recommendation."""
    posts = [_post(reach=5000, tone="only-one-value") for _ in range(6)]
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    assert ae.has_signal                      # the axis IS aggregated…
    assert ae.above_baseline("tone_register_primary") == []   # …but nothing beats itself
    assert wcl.build_engagement_hint(ae) == ""


def test_engagement_hint_has_no_baseline_clause_without_signal() -> None:
    """INNOCENCE: no signal → empty hint (byte-identical pre-Fase-4b path)."""
    assert wcl.build_engagement_hint(wcl.AxisEngagement(by_axis={}, total_posts=0)) == ""


def test_unknown_baseline_degrades_to_rank_only_and_states_no_baseline() -> None:
    """`corpus_median == 0.0` is the 'baseline unknown' sentinel (cold corpus, or
    a non-finite median guarded upstream): above_baseline must NOT filter — it
    degrades to rank-only, the pre-baseline behaviour — and the hint must not
    print a bogus '~0' baseline clause. Discriminates the `corpus_median > 0`
    guards: without them this filters everything out / prints '~0'."""
    ae = wcl.AxisEngagement(
        by_axis={"layout_family_primary": [("a", 900.0, 3), ("b", 100.0, 3)]},
        total_posts=6,
        corpus_median=0.0,
    )
    assert [v for v, _, _ in ae.above_baseline("layout_family_primary")] == ["a", "b"]
    hint = wcl.build_engagement_hint(ae)
    assert "a (~900 typical reach, n=3)" in hint
    assert "TYPICAL post in this corpus" not in hint, "no baseline known → no baseline claim"
    assert "~0" not in hint


def test_non_finite_median_from_finite_elements_is_dropped_not_crashed(tmp_path) -> None:
    """GUILT (red-team #3, reproduced on disk): every ELEMENT can be finite while
    the MEDIAN overflows — statistics.median of an even-sized group averages the
    two middle values and 1e308 + 1e308 == inf. `int(inf)` raises OverflowError
    inside build_engagement_hint, whose production caller does not wrap it, so
    element-level isfinite is not enough to keep the never-blocks promise."""
    import math as _m
    posts = (
        [_post(reach=1e308, layout="overflows") for _ in range(4)]   # median -> inf
        + [_post(reach=5000, layout="sane") for _ in range(3)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    vals = [v for v, _, _ in ae.by_axis.get("layout_family_primary", [])]
    assert "overflows" not in vals, "a non-finite median must be dropped, not ranked"
    assert vals == ["sane"]
    assert ae.total_posts == 7          # the posts themselves ARE counted (finite reach)
    assert _m.isfinite(ae.corpus_median)
    wcl.build_engagement_hint(ae)       # must not raise — this is the whole point


def test_axis_engagement_missing_queue_is_empty(tmp_path) -> None:
    # innocence: cold/absent queue → empty signal, empty hint (byte-identical path).
    ae = wcl.fetch_axis_engagement(queue_path=tmp_path / "does-not-exist.json")
    assert not ae.has_signal
    assert ae.total_posts == 0
    assert wcl.build_engagement_hint(ae) == ""


def test_axis_engagement_malformed_queue_is_empty(tmp_path) -> None:
    # best-effort: a broken queue never raises, never blocks generation.
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json ")
    ae = wcl.fetch_axis_engagement(queue_path=p)
    assert not ae.has_signal
    assert ae.total_posts == 0


def test_axis_engagement_skips_zero_and_missing_reach(tmp_path) -> None:
    posts = (
        [_post(reach=0, layout="cover-photo") for _ in range(5)]                       # reach 0 → skip
        + [_post(reach=1, metrics=False, layout="cover-photo") for _ in range(5)]      # no metrics → skip
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    assert ae.total_posts == 0
    assert not ae.has_signal


def test_hint_names_layout_and_tone_but_not_domain(tmp_path) -> None:
    posts = (
        [_post(reach=30000, layout="cover-photo", tone="rituale", domain="visa") for _ in range(4)]
        + [_post(reach=1000, layout="dark-status-list", tone="analitico", domain="tax") for _ in range(4)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    assert "domain" in ae.by_axis            # domain IS aggregated (carried for topic-selection)
    hint = wcl.build_engagement_hint(ae)
    assert "layout families" in hint
    assert "tone registers" in hint
    assert "domains" not in hint             # ...but never surfaced to the planner
    assert "cover-photo" in hint
    assert "visa" not in hint                # a domain VALUE never leaks into the planner nudge


def test_hint_states_sample_size_and_goodhart_caveat(tmp_path) -> None:
    # Needs CONTRAST: a single-value corpus has no winner by construction (the one
    # value IS the corpus median, so nothing beats the baseline) and correctly
    # yields an empty hint. The weak arm below supplies the baseline to beat.
    posts = (
        [_post(reach=30000, layout="cover-photo", tone="rituale") for _ in range(4)]
        + [_post(reach=1000, layout="dark-status-list", tone="analitico") for _ in range(5)]
    )
    hint = wcl.build_engagement_hint(wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts)))
    assert "n=4" in hint          # sample size stated inline (weak-signal honesty)
    assert "NOT a rule" in hint   # Goodhart caveat present
    assert "CONTENT-FIT" in hint


def test_domain_is_aggregated_but_not_a_planner_hint_axis() -> None:
    # drift pin (scar #9): domain is topic-driven, not planner-controllable — it
    # must stay OUT of the planner hint even though it is aggregated in the object.
    assert "domain" not in wcl._PLANNER_HINT_AXES
    assert "domain" in wcl._ENGAGEMENT_AXES


# ── cross-family red-team (Kimi K3, 2026-07-25) confirmed-defect guilt corpus ─


def test_axis_engagement_excludes_nan_and_inf_reach_without_crashing(tmp_path) -> None:
    # D1: json.loads accepts NaN/Infinity by default; they survive `<= 0` and would
    # poison the mean AND crash int(mean) in build_engagement_hint. They must be
    # excluded at the source, and the hint must render without raising.
    import math as _m
    posts = (
        [_post(reach=_m.nan, layout="nan-poison") for _ in range(3)]
        + [_post(reach=_m.inf, layout="inf-poison") for _ in range(3)]
        + [_post(reach=5000, layout="clean") for _ in range(3)]
        + [_post(reach=500, layout="modest") for _ in range(4)]  # baseline to beat
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    vals = [v for v, _, _ in ae.by_axis.get("layout_family_primary", [])]
    assert vals == ["clean", "modest"]    # only finite-reach values survive
    assert "nan-poison" not in vals and "inf-poison" not in vals
    assert ae.total_posts == 7            # nan/inf posts never counted
    hint = wcl.build_engagement_hint(ae)  # int(nan) would raise here without the guard
    assert "clean" in hint
    assert "poison" not in hint


def test_axis_engagement_non_list_queue_never_raises(tmp_path) -> None:
    # D2 (end-to-end): a JSON null/scalar queue yields empty signal, never raises.
    for payload in ("null", "42", '"just a string"'):
        p = tmp_path / "q.json"
        p.write_text(payload)
        ae = wcl.fetch_axis_engagement(queue_path=p)
        assert not ae.has_signal
        assert ae.total_posts == 0


def test_axis_engagement_guard_survives_loader_returning_non_list(tmp_path, monkeypatch) -> None:
    # D2 (defense-in-depth): even if a FUTURE load_queue returns None/non-list
    # (contract drift, scar #9), fetch_axis_engagement returns empty, not TypeError.
    import wr2_queue_writer as qw
    p = _write_queue(tmp_path, [])
    monkeypatch.setattr(qw, "load_queue", lambda _p: None)
    ae = wcl.fetch_axis_engagement(queue_path=p)
    assert not ae.has_signal
    assert ae.total_posts == 0


def test_axis_engagement_bool_reach_is_not_counted(tmp_path) -> None:
    # D3: a JSON `true` reach is a bool (int subclass) — must NOT count as reach 1.0.
    posts = (
        [_post(reach=True, layout="boolish") for _ in range(3)]
        + [_post(reach=4000, layout="clean") for _ in range(3)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    vals = [v for v, _, _ in ae.by_axis.get("layout_family_primary", [])]
    assert vals == ["clean"]     # boolish excluded (no bogus 1.0 sample)
    assert ae.total_posts == 3


# ── planner threading (byte-identical dormant path + live injection) ───────


def test_planner_prompt_byte_identical_when_hint_empty() -> None:
    priors = pw.build_arc_priors(["news_alert"], "breaking")
    default = pw._build_planner_prompt("BRIEF", "breaking", ["news_alert"], priors)
    empty = pw._build_planner_prompt("BRIEF", "breaking", ["news_alert"], priors, "")
    assert default == empty
    assert "ENGAGEMENT HINT" not in default


def test_planner_prompt_places_hint_before_output_block() -> None:
    priors = pw.build_arc_priors(["news_alert"], "breaking")
    hint = "\n\nENGAGEMENT HINT (weak signal — ...):\n  - higher-reaching layout families: X"
    prompt = pw._build_planner_prompt("BRIEF", "breaking", ["news_alert"], priors, hint)
    assert "ENGAGEMENT HINT" in prompt
    assert prompt.index("ENGAGEMENT HINT") < prompt.index("OUTPUT — ONE JSON")


def test_plan_deck_threads_engagement_hint_into_prompt() -> None:
    seen: list[str] = []

    def call_fn(p: str) -> str:
        seen.append(p)
        return "not json"  # force validation failure — no valid plan needed here

    with pytest.raises(pw.PlanValidationExhausted):
        pw.plan_deck(
            "BRIEF", "breaking", ["news_alert"], call_fn,
            max_retries=1, engagement_hint="ZZZ_UNIQUE_HINT_MARKER",
        )
    assert seen, "call_fn was never invoked"
    assert "ZZZ_UNIQUE_HINT_MARKER" in seen[0]


def test_plan_deck_empty_hint_leaves_prompt_without_hint_block() -> None:
    seen: list[str] = []

    def call_fn(p: str) -> str:
        seen.append(p)
        return "not json"

    with pytest.raises(pw.PlanValidationExhausted):
        pw.plan_deck("BRIEF", "breaking", ["news_alert"], call_fn, max_retries=1)
    assert seen
    assert "ENGAGEMENT HINT" not in seen[0]


# ── materiality bar (+25%, Zero 2026-07-25) ──────────────────────────────────


def test_a_marginal_edge_over_the_baseline_is_not_named(tmp_path) -> None:
    """GUILT: the exact hole the >baseline version shipped with — 30 posts at
    5,000 and 3 at 5,100 would name the 3-post value on a +2% edge. It clears
    `> corpus_median` and must NOT clear the materiality bar."""
    posts = (
        [_post(reach=5000, tone="the-whole-corpus") for _ in range(30)]
        + [_post(reach=5100, tone="marginal-winner") for _ in range(3)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    assert abs(ae.corpus_median - 5000) < 1
    # It IS ranked first, and it DOES beat the bare baseline…
    assert ae.by_axis["tone_register_primary"][0][0] == "marginal-winner"
    assert 5100 > ae.corpus_median
    # …but +2% is not a finding.
    assert ae.above_baseline("tone_register_primary") == []
    assert "marginal-winner" not in wcl.build_engagement_hint(ae)


def test_a_material_edge_is_still_named(tmp_path) -> None:
    """INNOCENCE: the bar must not silence a real signal. Same shape, real gap."""
    posts = (
        [_post(reach=5000, tone="the-whole-corpus") for _ in range(30)]
        + [_post(reach=9000, tone="genuine-winner") for _ in range(3)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    assert [v for v, _, _ in ae.above_baseline("tone_register_primary")] == ["genuine-winner"]
    assert "genuine-winner" in wcl.build_engagement_hint(ae)


def test_the_bar_is_exclusive_at_exactly_the_multiplier(tmp_path) -> None:
    """EDGE: sitting exactly ON the bar is not beating it (strict `>`), and one
    reach unit above it is. Pins the comparison operator, not just the constant."""
    base = 1000.0
    bar = base * wcl._MATERIALITY_MULTIPLIER
    posts = (
        [_post(reach=base, tone="corpus") for _ in range(9)]
        + [_post(reach=bar, tone="exactly-on-the-bar") for _ in range(3)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    assert abs(ae.corpus_median - base) < 1
    assert ae.above_baseline("tone_register_primary") == []

    posts2 = (
        [_post(reach=base, tone="corpus") for _ in range(9)]
        + [_post(reach=bar + 1, tone="just-over-the-bar") for _ in range(3)]
    )
    ae2 = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts2))
    assert [v for v, _, _ in ae2.above_baseline("tone_register_primary")] == ["just-over-the-bar"]


def test_hint_states_the_bar_and_never_calls_a_listed_value_marginal(tmp_path) -> None:
    """The prompt must size the claim. It must NOT keep saying values may beat
    the baseline 'only marginally' — with the bar armed that is false, and it
    would tell the planner to discount exactly the material ones."""
    posts = (
        [_post(reach=1000, tone="corpus", layout="dark-status-list") for _ in range(9)]
        + [_post(reach=9000, tone="strong", layout="statement-bomb") for _ in range(3)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    hint = wcl.build_engagement_hint(ae)
    pct = int(round((wcl._MATERIALITY_MULTIPLIER - 1) * 100))
    assert f"at least {pct}%" in hint, "the bar must be stated, not implied"
    assert "only marginally" not in hint
    # Absence is explained, so the planner does not read a silent axis as "no data".
    assert "withheld as noise" in hint


def test_one_axis_can_go_silent_while_the_other_survives_the_bar(tmp_path) -> None:
    """The MEASURED consequence Zero accepted on 2026-07-25, pinned so it cannot
    regress silently.

    On the real corpus (50 posts, baseline 2,288) the best TONE — `militante`,
    median 2,835 — sits at 1.24x and misses the +25% bar by 26 reach, while the
    LAYOUT axis is untouched (statement-bomb 7.99x). The two axes are
    INDEPENDENT groupings over the same posts, so a two-arm fixture cannot
    reproduce it; this reproduces the measured RATIO instead (1,240 over a
    baseline of 1,000 = the same 1.24x), which is what the assertion is about.
    Lower the bar and this test says so."""
    posts = (
        # bulk: sets the corpus baseline at 1,000
        [_post(reach=1000, layout="dark-status-list", tone="analitico") for _ in range(9)]
        # top tone — beats the baseline, misses the bar (the real militante shape)
        + [_post(reach=1240, layout="qa-dialogue", tone="militante") for _ in range(3)]
        # a genuinely strong LAYOUT, whose tones are singletons (n<_MIN_AXIS_SAMPLES)
        # so they are noise-guarded out and cannot rescue the tone axis
        + [_post(reach=8000, layout="statement-bomb", tone=f"one-off-{i}") for i in range(3)]
    )
    ae = wcl.fetch_axis_engagement(queue_path=_write_queue(tmp_path, posts))
    assert abs(ae.corpus_median - 1000) < 1

    tone_rows = {v: m for v, m, _ in ae.by_axis["tone_register_primary"]}
    assert tone_rows["militante"] > ae.corpus_median, "it DOES beat the bare baseline…"
    assert tone_rows["militante"] < ae.corpus_median * wcl._MATERIALITY_MULTIPLIER, "…not the bar"
    assert ae.above_baseline("tone_register_primary") == [], "tone axis goes silent"

    hint = wcl.build_engagement_hint(ae)
    assert "militante" not in hint
    assert "statement-bomb" in hint, "the layout signal must survive the bar"
    assert "qa-dialogue" not in hint, "1.24x does not earn the word on either axis"
