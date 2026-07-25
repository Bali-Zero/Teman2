#!/usr/bin/env python3
"""WR2 Creative Ledger — editorial-intelligence "Move D" (spec
`.claude/skills/wr2/_research/2026-07-21-editorial-intelligence-design.md`
§Mossa-D). A queryable, multi-axis editorial MEMORY assembled from the
EXISTING `war_room_*` columns — NO schema migration (§4 MINOR-7: the ledger
lives in Postgres, never in-process state; the production-cutover GROUND
principle "brief_json or a sensible existing JSON column — least-invasive"
is why arc/spine already live inside `council_debate_json`).

WHAT IT UNIFIES. `wr2_draft_generator` grew one ad-hoc per-axis lookback at a
time (`fetch_recent_arcs`, `fetch_recent_editorial_signatures`,
`fetch_recent_same_domain`), each a separate query keyed on recency. This
module generalizes the AXES that had no unified home — arc, spine, hook_type,
layout families, register — into ONE snapshot per query, and, CLOSED ON RESULT
(§Mossa-D, Kimi red-team objection #1 "open-loop"), LEFT-attaches each deck's
real OUTCOME: was it published (a Legge-5 human act) or only drafted? The
kicker/subhead axis deliberately stays in `fetch_recent_editorial_signatures`
(it already has a working, tested lookback with its own regex) — folding it in
here would duplicate that regex for no gain (reuse-first).

DORMANT-BUT-WIRED (2026-07-25). `war_room_posts` is empty today — 0 rows, 0
decks in `published` status; the IG token AND a first real Legge-5 publish are
both operator-gated (see PENDING-ARMS). So `reward_live_count == 0` and
`reward_by_arc()` returns `{}`, which makes the planner's priors BYTE-IDENTICAL
to the pre-ledger path. The socket activates automatically when rows arrive —
no code change. This is a DECLARED FIREBREAK, not silent-green: the count is
returned and logged by the caller (cicatrix #2 Esiste≠Armato — a dormant organ
must expose its own liveness, never merely look healthy).

DISCIPLINE (mirrors `fetch_recent_editorial_signatures` exactly):
  - best-effort empty on any CONNECTION-level error — generation is NEVER
    blocked by this lookback;
  - per-row isolation — one malformed `council_debate_json`/`slides_json`
    blob is skipped and logged at debug, the other rows survive (the original
    single try/except-around-the-loop shape let one bad legacy row silently
    zero an otherwise-healthy history);
  - cold-start safe — an empty ledger yields empty axes + `reward_by_arc()=={}`,
    never an exception, never a preference invented from no data.
"""
from __future__ import annotations

import json
import logging
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("wr2_creative_ledger")

# Reward boost ceiling (§Mossa-D "chiuso sul risultato"). Comparable in size to
# `wr2_planner_writer._TIER_BOOST` (0.35): a published-heavy arc gets nudged up
# but never forced — the planner-LLM still disposes from content (spec §2).
# ONLY applied when the reward signal is LIVE (>=1 published deck); dormant → 0.
_REWARD_MAX_BOOST = 0.30


@dataclass(frozen=True)
class LedgerEntry:
    """One rendered/published deck, projected onto the editorial axes.

    `arc_source` distinguishes a native planner_writer `arc` (written by
    `_process_one_planner_writer` into `council_debate_json.arc`) from a
    monolith-era deck's `arc` recovered by the LLM backfill
    (`council_debate_json.backfill.arc` — see `wr2_ledger_backfill.py`).
    A pre-backfill monolith deck has neither, so `arc is None` — exactly the
    honest cold-start state, never a malformed row."""

    draft_id: str
    created_at: Any  # datetime | None — passed through, never parsed here
    arc: str | None
    arc_source: str | None  # "native" | "backfill" | None
    spine_gist: str | None
    hook_type: str | None
    register: str | None
    layout_families: list[str] = field(default_factory=list)
    published: bool = False


@dataclass(frozen=True)
class LedgerSnapshot:
    """The result of one ledger query. `entries` is newest-first (the SQL
    orders by `created_at DESC`). `reward_live_count` is the number of entries
    that carry a real outcome (a `war_room_posts` row) — 0 == the reward loop
    is dormant, and every reward-derived signal below is inert by construction."""

    entries: list[LedgerEntry]
    reward_live_count: int

    def recent_arcs(self, limit: int | None = None) -> list[str]:
        """Arcs (native OR backfilled), newest-first, `None`-arcs dropped —
        the exact shape `wr2_planner_writer.build_arc_priors` consumes. This
        REPLACES `fetch_recent_arcs` at the call site: same contract, but a
        backfilled monolith deck now contributes its recovered arc, so the
        cooldown finally sees the deck history that predates planner_writer."""
        arcs = [e.arc for e in self.entries if e.arc]
        return arcs[:limit] if limit is not None else arcs

    def reward_by_arc(self) -> dict[str, float]:
        """Per-arc reward boost derived from which arcs get PUBLISHED (the
        Legge-5 human signal — §Mossa-D "il ledger registra anche l'ESITO").

        DORMANT CONTRACT: returns `{}` whenever `reward_live_count == 0`, so a
        caller that folds this into `build_arc_priors` gets a byte-identical
        result to the no-reward path until real publishes exist. When live, the
        boost is proportional to how often each arc appears among published
        decks, capped at `_REWARD_MAX_BOOST` (a nudge, never a mask)."""
        if self.reward_live_count == 0:
            return {}
        published = Counter(e.arc for e in self.entries if e.published and e.arc)
        if not published:
            return {}
        top = max(published.values())
        return {arc: _REWARD_MAX_BOOST * (n / top) for arc, n in published.items()}


def _coerce_blob(raw: Any) -> dict[str, Any] | None:
    """`council_debate_json`/`slides_json` arrive as a dict OR a JSON string
    depending on whether a jsonb codec is registered on this connection —
    mirrors the exact defensive pattern `fetch_recent_editorial_signatures`
    and `wr2_daily_reconciler`/`wr2_fact_checker` already use. Returns None
    for anything that isn't a dict after parsing (never raises)."""
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = json.loads(raw)  # caller isolates per-row; a bad string raises here
    return raw if isinstance(raw, dict) else None


def _arc_from_council(council: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """Return (arc, arc_source). Native planner_writer `arc` wins; else the
    backfilled `backfill.arc`; else (None, None) = cold start."""
    if not council:
        return None, None
    native = council.get("arc")
    if isinstance(native, str) and native.strip():
        return native.strip(), "native"
    backfill = council.get("backfill")
    if isinstance(backfill, dict):
        recovered = backfill.get("arc")
        if isinstance(recovered, str) and recovered.strip():
            return recovered.strip(), "backfill"
    return None, None


def _str_axis(council: dict[str, Any] | None, key: str, backfill_key: str | None = None) -> str | None:
    """Read a string axis from council, preferring the native key, falling
    back to `council['backfill'][backfill_key]` (default same key)."""
    if not council:
        return None
    native = council.get(key)
    if isinstance(native, str) and native.strip():
        return native.strip()
    backfill = council.get("backfill")
    if isinstance(backfill, dict):
        val = backfill.get(backfill_key or key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _layout_families(slides_blob: dict[str, Any] | None) -> list[str]:
    """Ordered, deduped list of the deck's `layout_family` values (a surface
    axis — §Mossa-D). Best-effort: missing/odd shapes contribute nothing."""
    if not slides_blob:
        return []
    slides = slides_blob.get("slides") if isinstance(slides_blob, dict) else slides_blob
    if not isinstance(slides, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        fam = str(slide.get("layout_family") or "").strip()
        if fam and fam not in seen:
            seen.add(fam)
            out.append(fam)
    return out


# The one query: rendered/published decks, newest-first, with a per-deck
# published flag via EXISTS (one row per draft — a multi-platform deck with
# several war_room_posts rows must NOT duplicate the ledger entry).
#
# `council_debate_json IS NOT NULL` is LOAD-BEARING, not incidental (2026-07-25
# cross-family red-team, Kimi K3): the standalone `fetch_recent_arcs` this call
# site replaces carried the same filter, and dropping it changes the LIMIT-8
# window — a NULL-council row (there IS one live: 1/67 rendered decks) would
# consume a window slot and push an arc-bearing row out, so `recent_arcs()`
# would diverge from the pre-Fase-4 cooldown input. Keeping the filter makes
# the arc window BYTE-IDENTICAL to the old path today (a NULL-council deck has
# no arc/spine/hook axis anyway — nothing to lose), and the ledger's ONLY added
# behavior is reading `backfill.arc` (empty today → identical; richer after the
# backfill pass — the intended, declared activation).
_LEDGER_SQL = """
    SELECT d.id,
           d.created_at,
           d.register,
           d.slides_json,
           d.council_debate_json,
           EXISTS (
               SELECT 1 FROM war_room_posts p WHERE p.draft_id = d.id
           ) AS published
      FROM war_room_drafts d
     WHERE d.status IN ('rendered', 'published')
       AND d.council_debate_json IS NOT NULL
     ORDER BY d.created_at DESC
     LIMIT $1
"""


async def fetch_creative_ledger(conn: Any, limit: int = 8) -> LedgerSnapshot:
    """Assemble the Creative Ledger snapshot for the last `limit` rendered/
    published decks. Best-effort + per-row isolated + cold-start safe (see
    module docstring). Never raises; on a connection-level failure returns an
    empty snapshot so generation proceeds exactly as with no history."""
    try:
        rows = await conn.fetch(_LEDGER_SQL, limit)
    except Exception as exc:  # noqa: BLE001 — connection-level, never block generation
        logger.warning("fetch_creative_ledger failed: %s", exc)
        return LedgerSnapshot(entries=[], reward_live_count=0)

    entries: list[LedgerEntry] = []
    for row in rows:
        try:
            council = _coerce_blob(row.get("council_debate_json") if hasattr(row, "get") else row["council_debate_json"])
            slides_blob = _coerce_blob(row.get("slides_json") if hasattr(row, "get") else row["slides_json"])
            arc, arc_source = _arc_from_council(council)
            published = bool(row["published"])
            entries.append(
                LedgerEntry(
                    draft_id=str(row["id"]),
                    created_at=row["created_at"],
                    arc=arc,
                    arc_source=arc_source,
                    spine_gist=_str_axis(council, "spine", "spine_gist"),
                    hook_type=_str_axis(council, "hook_type"),
                    register=(str(row["register"]).strip() or None) if row["register"] else None,
                    layout_families=_layout_families(slides_blob),
                    published=published,
                )
            )
        except Exception as exc:  # noqa: BLE001 — isolate one bad row, keep the rest
            logger.debug("fetch_creative_ledger: skipping malformed row: %s", exc)
            continue

    # Derive the liveness count from the ENTRIES that actually survived (not a
    # mid-loop counter) — the self-probe must match exactly what the snapshot
    # exposes, so a row that increments then fails to append can never desync it.
    reward_live = sum(1 for e in entries if e.published)
    return LedgerSnapshot(entries=entries, reward_live_count=reward_live)


# ═══════════════════════════════════════════════════════════════════════════
# Fase 4b — AXIS-ENGAGEMENT reward (spec §Mossa-D, closed on the OUTCOME)
# ═══════════════════════════════════════════════════════════════════════════
# The war_room_posts-based reward socket above stays DORMANT (0 rows), but a
# YEAR of real IG engagement DOES exist — in the review queue, on ~45 published
# carousels whose editorial axes (layout_family/tone_register/domain) were
# LLM-inferred 2026-06-23. Those posts are NOT war_room_drafts (46/47 carry no
# draft_id) and carry NO arc, so they cannot feed the ARC reward — but they CAN
# feed a per-AXIS engagement prior (which layout/tone historically drove reach).
#
# HONEST CAVEATS baked into the design (spec §5 Goodhart warning is load-bearing
# here — the top layouts are the hero-visual ones, and blindly chasing them
# would collapse the very variety the anti-sameness steer builds):
#   - the labels are LLM-INFERRED, not ground truth (a guessed layout_family);
#   - the winners often have TINY n (ironico n=2) — a 2-sample mean is noise;
#   - so this is a SOFT, INFORMATIONAL hint to the planner, never a numeric
#     weight on selection, and every axis value below `_MIN_AXIS_SAMPLES` is
#     dropped as too-noisy-to-rank.
#
# RANK BY MEDIAN, NOT MEAN (2026-07-25 — measured, not theorised). The first
# retrospective study over the real corpus (50 posts with reach, run read-only
# on the Pro) found IG reach is extremely long-tailed: min 516 / median 2,288 /
# mean 8,936 / max 141,240 — a SINGLE post is 31.6% of all reach in the corpus.
# Ranking by mean therefore ranked the outlier's carrier, not the layout:
#   cover-photo n=7 -> [141240, 23704, 1360, 1220, 1193, 1185, 1140]
#                      mean 24,435 (#1)  but median 1,220 (LAST)
#   rituale     n=5 -> [141240, 1360, 1220, 1193, 1185]
#                      mean 29,240 (#1)  but median 1,220 (LAST)
#   statement-bomb n=8 -> median 18,281 — 5 of 8 above 13k, robustly strong.
# So the hint was naming the two WEAKEST typical performers as the winners. The
# `n >= _MIN_AXIS_SAMPLES` guard defends against small samples but NOT against
# SKEW: rituale has n=5, passes the guard, and its typical post (1,220) is BELOW
# the corpus median. Median is the estimable statistic here; with one
# observation carrying a third of the corpus the mean is not estimable at all.
# KNOWN TENSION (deliberate, documented not hidden): median discards tail upside
# — a layout that goes viral 1-in-7 could win on TOTAL reach while losing on the
# typical post. That is an EDITORIAL objective choice (reliable reach per post vs
# expected total), not a statistical one, and it is Zero's call; until it is made,
# the defensible default is the robust statistic. `corpus_median` is carried into
# the hint so "higher-reaching" cannot overstate a value that merely ties the
# corpus baseline.
# Source of truth is the review-queue JSON (`wr2_queue_writer._resolve_queue_
# path`), read best-effort: any error → empty signal, generation never blocked.

# Axes the planner can actually act on (domain is topic-driven — carried in the
# object for topic-selection use, but NOT pushed into the planner hint).
_ENGAGEMENT_AXES: tuple[str, ...] = ("layout_family_primary", "tone_register_primary", "domain")
_PLANNER_HINT_AXES: tuple[str, ...] = ("layout_family_primary", "tone_register_primary")
# Below this many published samples an axis value is too noisy to rank (a
# 1-2 sample mean reach is a coin flip, not a signal — noise guard).
_MIN_AXIS_SAMPLES = 3
# Cap how many high performers we name per axis in the hint (keep it a nudge).
_HINT_TOP_N = 2


@dataclass(frozen=True)
class AxisEngagement:
    """Per-axis engagement summary from the review queue's published history.

    `by_axis[axis]` is a list of `(value, MEDIAN_reach, n)` sorted high→low,
    restricted to values with `n >= _MIN_AXIS_SAMPLES`. Empty everywhere when
    there is no usable signal (cold start / unreadable queue) — a caller then
    gets an empty hint and the planner behaves exactly as before (falsifiable).

    `corpus_median` is the median reach over ALL counted posts (0.0 when there
    are none) — the baseline a per-value median must be judged against, so the
    hint cannot present a value that merely ties the corpus as "higher-reaching"."""

    by_axis: dict[str, list[tuple[str, float, int]]]
    total_posts: int
    corpus_median: float = 0.0

    def top(self, axis: str, n: int = _HINT_TOP_N) -> list[tuple[str, float, int]]:
        return (self.by_axis.get(axis) or [])[:n]

    def above_baseline(self, axis: str, n: int = _HINT_TOP_N) -> list[tuple[str, float, int]]:
        """Top-n values that actually BEAT the corpus median.

        Ranking alone is not evidence of strength: the top-2 of a weak axis are
        still the top-2. Measured 2026-07-25 on the real corpus — `analitico`
        (median 2,237) ranked #2 among tones while the TYPICAL post of the whole
        corpus reaches 2,288, so the hint was about to call a BELOW-baseline
        value "higher-reaching". Absolute comparison against the baseline, not
        just rank, is what makes the claim true. An axis where nothing beats the
        baseline is simply not named (→ possibly an empty hint → the planner
        falls back to the byte-identical no-hint path, the designed safe state).

        DECLARED LIMITS (cross-family red-team #2, 2026-07-25 — known, not hidden):
          - the groups ARE the corpus, so a value holding the MAJORITY of posts
            is structurally unnameable: it defines the baseline it would have to
            beat. Defensible (it has no contrast to be better THAN), but it means
            absence here is NOT evidence of weakness;
          - there is NO materiality threshold. 30 posts at 5,000 + 3 at 5,100
            names the 3-post value on a +2% edge. Mitigated, not eliminated, by
            the hint stating the baseline, the n, and "only marginally" inline —
            the planner is given what it needs to discount it. A minimum edge
            (e.g. >=1.25x baseline) would close it, but on the real corpus that
            bar would also silence the tone axis entirely (militante 2,835 vs a
            2,288 baseline = +24%), so WHERE to put it is an EDITORIAL call for
            Zero, not a statistical one. Ledgered, deliberately not decided here.

        `corpus_median == 0.0` means "baseline unknown" (cold corpus, or a
        non-finite median guarded upstream) and degrades to rank-only — exactly
        the pre-baseline behaviour, never a raise."""
        rows = self.by_axis.get(axis) or []
        if self.corpus_median > 0:
            rows = [r for r in rows if r[1] > self.corpus_median]
        return rows[:n]

    @property
    def has_signal(self) -> bool:
        return any(self.by_axis.get(a) for a in self.by_axis)


def _resolve_queue_path(explicit: Any) -> Any:
    """Reuse wr2_queue_writer's own resolver (env WR2_QUEUE_PATH → default) so
    the ledger reads the SAME queue file the writer/server use — never a second
    hard-coded path (scar #1 HOME-fork). Lazy import keeps this module importable
    even where wr2_queue_writer's deps are absent (returns None → empty signal)."""
    try:
        import wr2_queue_writer as qw  # lazy: avoid a load-time dependency
        return qw._resolve_queue_path(explicit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("axis-engagement: cannot resolve queue path: %s", exc)
        return None


def fetch_axis_engagement(queue_path: Any = None) -> AxisEngagement:
    """Aggregate MEDIAN reach per editorial axis from the review queue's PUBLISHED
    posts that carry engagement_metrics. Best-effort: a missing/unreadable queue
    → empty signal (never raises, never blocks generation). External-only posts
    are included (they are still real IG engagement for the axis), but items
    with no reach are skipped."""
    path = queue_path if queue_path is not None else _resolve_queue_path(None)
    if path is None:
        return AxisEngagement(by_axis={}, total_posts=0)
    try:
        import wr2_queue_writer as qw  # lazy
        items = qw.load_queue(path)
    except FileNotFoundError:
        return AxisEngagement(by_axis={}, total_posts=0)
    except Exception as exc:  # noqa: BLE001 — never block generation on the lookback
        logger.warning("fetch_axis_engagement failed: %s", exc)
        return AxisEngagement(by_axis={}, total_posts=0)

    # load_queue raises on a non-list today, but the best-effort "never blocks
    # generation" promise must not DEPEND on that contract (scar #9 drift): a JSON
    # `null`/`42` reaching the loop below would raise TypeError uncaught. Guard it
    # here so this function owns its own promise (cross-family red-team D2, 2026-07-25).
    if not isinstance(items, list):
        return AxisEngagement(by_axis={}, total_posts=0)

    reach_by: dict[str, dict[str, list[float]]] = {a: defaultdict(list) for a in _ENGAGEMENT_AXES}
    all_reaches: list[float] = []
    total = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        m = it.get("engagement_metrics")
        if not isinstance(m, dict):
            continue
        reach_raw = m.get("reach")
        # bool is an int subclass — a JSON `true` reach must NOT be counted as 1.0
        # (cross-family red-team D3, 2026-07-25).
        if isinstance(reach_raw, bool):
            continue
        try:
            reach = float(reach_raw or 0)
        except (TypeError, ValueError):
            continue
        # NaN/Infinity survive `<= 0` (every nan/inf comparison is False) and would
        # both poison the statistic AND crash int(...) in build_engagement_hint —
        # json.loads accepts NaN/Infinity by default, so a Python-written queue can
        # legitimately carry them (cross-family red-team D1, 2026-07-25). isfinite is
        # the single guard that keeps the best-effort "never blocks generation" promise.
        if not math.isfinite(reach) or reach <= 0:
            continue
        total += 1
        all_reaches.append(reach)
        for axis in _ENGAGEMENT_AXES:
            val = it.get(axis)
            if isinstance(val, str) and val.strip():
                reach_by[axis][val.strip()].append(reach)

    by_axis: dict[str, list[tuple[str, float, int]]] = {}
    for axis, buckets in reach_by.items():
        ranked = []
        for val, rs in buckets.items():
            if len(rs) < _MIN_AXIS_SAMPLES:
                continue
            # MEDIAN, not mean — one viral post is 31.6% of this corpus's reach
            # and the mean simply ranked its carrier (see the block comment above).
            med = statistics.median(rs)
            # Every ELEMENT is finite (guarded in the loop above), but the median
            # of an EVEN-sized group averages the two middle values and
            # 1e308 + 1e308 == inf. `int(inf)` then raises OverflowError inside
            # build_engagement_hint, whose caller does NOT wrap it
            # (wr2_draft_generator.py:2237) — that would break this module's
            # "never blocks generation" promise. Element-level isfinite is NOT
            # sufficient; the computed statistic needs its own guard.
            # (cross-family red-team finding #3, 2026-07-25, reproduced on disk.)
            if not math.isfinite(med):
                continue
            ranked.append((val, med, len(rs)))
        ranked.sort(key=lambda t: t[1], reverse=True)
        if ranked:
            by_axis[axis] = ranked
    corpus_median = statistics.median(all_reaches) if all_reaches else 0.0
    if not math.isfinite(corpus_median):
        # Same overflow path. 0.0 is the honest "baseline unknown" sentinel:
        # above_baseline() then degrades to rank-only instead of raising.
        corpus_median = 0.0
    return AxisEngagement(by_axis=by_axis, total_posts=total, corpus_median=corpus_median)


_AXIS_LABEL = {
    "layout_family_primary": "layout families",
    "tone_register_primary": "tone registers",
    "domain": "domains",
}


def build_engagement_hint(ae: AxisEngagement) -> str:
    """Render a SOFT, informational hint for the planner prompt from the
    per-axis engagement history. Empty string when there is no usable signal
    (so the prompt is byte-identical to the no-hint path — falsifiable). Frames
    the signal as a WEAK nudge with its caveats stated inline, so the planner
    weights it appropriately and does not collapse variety onto the top values
    (spec §5 Goodhart guard)."""
    lines: list[str] = []
    for axis in _PLANNER_HINT_AXES:
        # above_baseline, NOT top: the top-2 of a weak axis are still the top-2,
        # and calling a below-corpus-median value "higher-reaching" is a lie the
        # planner would act on (see AxisEngagement.above_baseline).
        top = ae.above_baseline(axis)
        if not top:
            continue
        named = ", ".join(f"{val} (~{int(mr):,} typical reach, n={n})" for val, mr, n in top)
        lines.append(f"  - higher-reaching {_AXIS_LABEL.get(axis, axis)}: {named}")
    if not lines:
        return ""
    # State the corpus baseline so a value that merely TIES the typical post
    # cannot read as a winner (militante measured 2,835 vs a 2,288 corpus median
    # — "higher-reaching" would badly overstate a 24% edge without this line).
    baseline = (
        f" For scale, the TYPICAL post in this corpus reaches ~{int(ae.corpus_median):,}; "
        "only values that actually beat that are listed, and some beat it only marginally."
        if ae.corpus_median > 0
        else ""
    )
    return (
        "\n\nENGAGEMENT HINT (weak signal — LLM-inferred labels over a small "
        f"sample of {ae.total_posts} past posts. Reach is the MEDIAN (typical) "
        "post, NOT the mean: this corpus is long-tailed and a single viral post "
        "otherwise dominates every average. Treat as a gentle nudge, NOT a rule."
        f"{baseline}):\n"
        + "\n".join(lines)
        + "\nWhen the story genuinely fits one of these, it is worth reaching "
        "for — but CONTENT-FIT and VARIETY still decide. Do not force a "
        "high-reach layout/tone onto a story that calls for another; a fresh, "
        "well-matched choice beats chasing past engagement."
    )
