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
from collections import Counter
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
