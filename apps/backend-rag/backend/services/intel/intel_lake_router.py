"""Intel Lake Tier 1 Router — rules-based routing for incoming intel_items.

Subscribes to PG channel `intel_lake_event` via EventBus (event_type
`intel_lake.event`). On each new item, applies regex rules to source_domain
to set `routing_status` and `routing_targets`.

Routing categories:
- nb-intel: Indonesian regulatory/legal/AI research → push to NotebookLM NB-INTEL
- blog:    Indonesian press/news → eligible for balizero.com blog
- archive: OSINT social/reddit/twitter/youtube → keep for trend analysis only
- skip:    explicit drop (no current rules)
- needs_review: NO rule matched → Tier 2 LLM (weekly)

Key invariants:

1. Trigger loop prevention: PG trigger `trg_notify_intel_lake_event` is
   AFTER INSERT only (mig 168). Router does UPDATE, NOT INSERT.

2. Idempotency: UPDATE guarded by `WHERE routing_status='unrouted'`.

3. Hot-loop prevention: regex anchored at ^ on source_domain (already
   canonicalized lowercase by IntelLakeService).

4. Multi-process safety: idempotency guard handles parallel listeners.

5. Cold-start: existing pre-deploy unrouted rows handled by
   `backfill_unrouted()` one-shot helper.

6. Audit: every routing decision logged with producer_name='router',
   request_path='router/tier1'.

Design: research/symbiosis/2026-05-13-intel-lake-router-tier1-design.md
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import asyncpg

from backend.services.intel.intel_lake_rules import (
    _PRESS_GENERAL_RE,
    classify,
)
from backend.services.intel.intel_lake_rules import (
    NB_INTEL_AI_RESEARCH as NB_INTEL_AI_RESEARCH,
)
from backend.services.intel.intel_lake_rules import (
    NB_INTEL_IMMIGRATION as NB_INTEL_IMMIGRATION,
)
from backend.services.intel.intel_lake_rules import (
    NB_INTEL_PRESS as NB_INTEL_PRESS,
)
from backend.services.intel.intel_lake_rules import (
    NB_INTEL_REGULATION as NB_INTEL_REGULATION,
)
from backend.services.intel.intel_lake_rules import (
    NB_INTEL_TAX as NB_INTEL_TAX,
)
from backend.services.intel.intel_lake_rules import (
    NB_PROBE_SANDBOX as NB_PROBE_SANDBOX,
)
from backend.services.intel.intel_lake_rules import (
    _press_content_gate as _press_content_gate,
)

if TYPE_CHECKING:
    from backend.services.events.event_bus import EventBus

logger = logging.getLogger(__name__)

# Routing rules (NB-INTEL UUIDs, `_RULES`, press content gate) moved to
# `intel_lake_rules.py` — the single source of truth shared with the
# Pro-local fallback cron. Re-exported above for existing importers
# (`test_intel_lake_router.py`); see that module for rule definitions.

# Shadow-mode flag (PR-B1a 2026-05-20): if set, the router logs the NEW
# classification but does NOT update the DB — used to validate the 2-stage
# fix on real traffic before bulk backfill. Set via Fly secret or local env:
#   fly secrets set INTEL_LAKE_ROUTING_SHADOW=1 -a nuzantara-rag
# Unset (default) → normal classification.
_SHADOW_MODE = os.environ.get("INTEL_LAKE_ROUTING_SHADOW", "").lower() in (
    "1",
    "true",
    "yes",
)


class IntelLakeRouter:
    """Tier 1 routing service (rules-only, no LLM)."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool

    async def route_event(self, payload: dict[str, Any]) -> None:
        """Handle one `intel_lake.event` payload.

        Idempotent: UPDATE guarded by routing_status='unrouted'.

        Payload (from PG trigger ``trg_notify_intel_lake_event``):
          - item_id (uuid str)
          - canonical_url (str)
          - source_domain (str, lowercase)
          - topic_tags (list[str])
          - routing_status (str)
          - first_seen_at (iso str)

        For stage-2 content-gate (press_general rule), also reads ``title``
        and ``canonical_url`` from the payload. Missing fields → conservative
        fallback to ``blog`` (preserves pre-B1a behavior).
        """
        item_id = payload.get("item_id")
        source_domain = (payload.get("source_domain") or "").strip().lower()
        # Trigger NOTIFY payload does NOT include title (size optimization in
        # migration 168). For the 2-stage press_general content gate we need
        # title — fetch lazily from DB only when domain matches press_general.
        # No-op for all other rules (no extra query).
        canonical_url = payload.get("canonical_url")
        title = payload.get("title")

        if not item_id:
            logger.warning("intel_lake_router: missing item_id in payload")
            return

        # Lazy title fetch only when needed (content-gate eligibility check)
        if title is None and source_domain and _PRESS_GENERAL_RE.match(source_domain):
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT title, canonical_url FROM intel_items WHERE id = $1::uuid",
                        item_id,
                    )
                    if row is not None:
                        title = row["title"]
                        canonical_url = canonical_url or row["canonical_url"]
            except Exception as exc:
                logger.warning(
                    "intel_lake_router: title lookup failed item_id=%s: %s",
                    item_id,
                    exc,
                )

        decision = self._classify(source_domain, title, canonical_url)
        new_status = decision["status"]
        new_targets = decision["targets"]
        rule_name = decision["rule"]

        # Shadow-mode: log but do not write. Phase-C empirical validation.
        if _SHADOW_MODE:
            logger.info(
                "intel_lake_router SHADOW item_id=%s domain=%s rule=%s status=%s",
                item_id,
                source_domain,
                rule_name,
                new_status,
            )
            return

        try:
            async with self._pool.acquire() as conn:
                # NOTE: bind ``new_targets`` as a raw dict, NOT json.dumps(...).
                # The pool's jsonb codec (``backend/app/core/database.py``)
                # registers ``encoder=json.dumps`` — pre-serializing here
                # double-encodes and lands a jsonb *string* ("{}") instead of
                # a jsonb *object* ({}). Regression fixed 2026-05-14.
                affected = await conn.fetchval(
                    """
                    UPDATE intel_items
                       SET routing_status = $2,
                           routing_targets = $3::jsonb
                     WHERE id = $1::uuid
                       AND routing_status = 'unrouted'
                    RETURNING id
                    """,
                    item_id,
                    new_status,
                    new_targets,
                )
                await conn.execute(
                    """
                    INSERT INTO intel_lake_audit_log
                        (producer_name, client_ip, request_path, status_code,
                         payload_size, error_message)
                    VALUES ($1, NULL, $2, $3, NULL, $4)
                    """,
                    "router",
                    "router/tier1",
                    200 if affected else 304,
                    f"rule={rule_name} status={new_status}",
                )
        except Exception as exc:
            logger.exception(
                "intel_lake_router: UPDATE failed item_id=%s domain=%s: %s",
                item_id,
                source_domain,
                exc,
            )
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO intel_lake_audit_log
                            (producer_name, client_ip, request_path, status_code,
                             payload_size, error_message)
                        VALUES ('router', NULL, 'router/tier1', 500, NULL, $1)
                        """,
                        f"item_id={item_id} domain={source_domain}: {exc}"[:200],
                    )
            except Exception:
                pass

    def _classify(
        self,
        source_domain: str,
        title: str | None = None,
        canonical_url: str | None = None,
    ) -> dict[str, Any]:
        """Apply rules, return routing decision. NO DB I/O.

        Delegates to `intel_lake_rules.classify` — see that module for the
        2-stage `press_general` content-gate logic.
        """
        return classify(source_domain, title, canonical_url)


async def backfill_unrouted(db_pool: asyncpg.Pool, batch_size: int = 100) -> int:
    """Apply Tier 1 rules to all existing `routing_status='unrouted'` rows.

    One-shot manual run after first deploy. Idempotent.
    """
    router = IntelLakeRouter(db_pool)
    total = 0
    while True:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, source_domain, title, canonical_url
                  FROM intel_items
                 WHERE routing_status = 'unrouted'
                 LIMIT $1
                """,
                batch_size,
            )
        if not rows:
            break
        for row in rows:
            await router.route_event(
                {
                    "item_id": str(row["id"]),
                    "source_domain": row["source_domain"],
                    "title": row["title"],
                    "canonical_url": row["canonical_url"],
                }
            )
        total += len(rows)
        logger.info("backfill_unrouted: processed %s (total=%s)", len(rows), total)
        if len(rows) < batch_size:
            break
    return total


async def backfill_needs_review(
    db_pool: asyncpg.Pool, batch_size: int = 100, dry_run: bool = True
) -> dict[str, int]:
    """Re-classify ``needs_review`` items with the new 2-stage rules (PR-B1a).

    Mirrors ``backfill_unrouted`` but targets the ``needs_review`` pool.
    DEFAULT IS DRY-RUN — set ``dry_run=False`` after panel validates the
    shadow-mode output on a sample.

    Returns counts dict: ``{selected, reclassified, nb_intel, blog, archive,
    needs_review, skipped}``.

    Usage (one-shot, after PR-B1a deploys):
        python -c "import asyncio; from backend.services.intel.intel_lake_router \
import backfill_needs_review; from backend.app.core.database import \
get_db_pool; asyncio.run(backfill_needs_review(await get_db_pool(), \
dry_run=False))"
    """
    counts: dict[str, int] = {
        "selected": 0,
        "reclassified": 0,
        "nb-intel": 0,
        "blog": 0,
        "archive": 0,
        "needs_review": 0,
        "skipped": 0,
    }
    router = IntelLakeRouter(db_pool)
    last_seen_id: str | None = None
    while True:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, source_domain, title, canonical_url
                  FROM intel_items
                 WHERE routing_status = 'needs_review'
                   AND ($2::uuid IS NULL OR id > $2::uuid)
                 ORDER BY id
                 LIMIT $1
                """,
                batch_size,
                last_seen_id,
            )
        if not rows:
            break
        counts["selected"] += len(rows)
        last_seen_id = str(rows[-1]["id"])
        for row in rows:
            decision = router._classify(
                (row["source_domain"] or "").strip().lower(),
                row["title"],
                row["canonical_url"],
            )
            new_status = decision["status"]
            counts[new_status] = counts.get(new_status, 0) + 1
            if new_status == "needs_review":
                counts["skipped"] += 1
                continue
            counts["reclassified"] += 1
            if dry_run:
                continue
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE intel_items
                       SET routing_status = $2,
                           routing_targets = $3::jsonb
                     WHERE id = $1::uuid
                       AND routing_status = 'needs_review'
                    """,
                    row["id"],
                    new_status,
                    decision["targets"],
                )
        if len(rows) < batch_size:
            break
    logger.info(
        "backfill_needs_review (%s): %s",
        "DRY-RUN" if dry_run else "APPLIED",
        counts,
    )
    return counts


def register_intel_lake_router_handlers(bus: EventBus, db_pool: asyncpg.Pool) -> None:
    """Register Tier 1 router on `intel_lake.event` channel.

    Called from backend.services.events.handlers._core.register_handlers.
    """
    router = IntelLakeRouter(db_pool)
    bus.subscribe("intel_lake.event", router.route_event)
    logger.info("intel_lake_router: subscribed to intel_lake.event channel")
