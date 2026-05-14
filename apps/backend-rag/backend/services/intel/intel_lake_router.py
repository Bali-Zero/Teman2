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
import re
from typing import TYPE_CHECKING, Any

import asyncpg

if TYPE_CHECKING:
    from backend.services.events.event_bus import EventBus

logger = logging.getLogger(__name__)


# ─── NB-INTEL NotebookLM UUIDs (production, verified) ───────────────────────

NB_INTEL_IMMIGRATION = "1ed02e54-542f-426a-94f8-53c5ffde4b7d"
NB_INTEL_TAX = "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f"
NB_INTEL_REGULATION = "a17f134e-b9ab-42d9-bfc2-5bbc45165c76"
NB_INTEL_PRESS = "9d262101-abeb-4e15-af9c-c38e028c62fe"
NB_INTEL_AI_RESEARCH = "dc5d01cd-e99f-4c8f-aae4-75060b43d0de"


# ─── Routing rules (closed-set, applied top-to-bottom; first match wins) ────

_RULES: list[tuple[re.Pattern[str], str, dict[str, Any], str]] = [
    # Immigration (visa, KITAS, KITAP) → NB-INTEL-Immigration
    (
        re.compile(
            r"^(imigrasi\.go\.id|kanwilkemenkumham|kemenkumham\.go\.id|"
            r"kanim\.|jdih\.kemenkumham)"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_IMMIGRATION]},
        "immigration_govid",
    ),
    # Tax (PMK, PPh, SPT, Coretax) → NB-INTEL-Tax
    (
        re.compile(
            r"^(pajak\.go\.id|ortax\.org|ddtcnews|mucconsulting|"
            r"ikpi\.or\.id|kemenkeu\.go\.id|jdih\.kemenkeu)"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_TAX]},
        "tax_govid",
    ),
    # Regulation/KBLI/PT PMA → NB-INTEL-Regulation
    (
        re.compile(
            r"^(bkpm\.go\.id|oss\.go\.id|kemendag\.go\.id|"
            r"jdih\.bkpm|jdih\.menpan|jdih\.setkab|peraturan\.go\.id)"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_REGULATION]},
        "regulation_govid",
    ),
    # AI research / academic → NB-INTEL-AIResearch
    (
        re.compile(
            r"^(arxiv\.org|github\.com|huggingface\.co|openai\.com|"
            r"anthropic\.com|deepmind\.com|paperswithcode)"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_AI_RESEARCH]},
        "ai_research",
    ),
    # Indonesian press / news → blog
    (
        re.compile(
            r"^(detik|kompas|tempo|tribunnews|jakartapost|antaranews|"
            r"bisnis\.com|cnnindonesia|kontan\.co\.id|katadata)"
        ),
        "blog",
        {},
        "press_indonesian",
    ),
    # OSINT social → archive
    (
        re.compile(r"^(reddit|twitter|x\.com|youtube|t\.co|medium\.com)"),
        "archive",
        {},
        "osint_social",
    ),
]


class IntelLakeRouter:
    """Tier 1 routing service (rules-only, no LLM)."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool

    async def route_event(self, payload: dict[str, Any]) -> None:
        """Handle one `intel_lake.event` payload.

        Idempotent: UPDATE guarded by routing_status='unrouted'.
        """
        item_id = payload.get("item_id")
        source_domain = (payload.get("source_domain") or "").strip().lower()

        if not item_id:
            logger.warning("intel_lake_router: missing item_id in payload")
            return

        decision = self._classify(source_domain)
        new_status = decision["status"]
        new_targets = decision["targets"]
        rule_name = decision["rule"]

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

    def _classify(self, source_domain: str) -> dict[str, Any]:
        """Apply rules, return routing decision. NO DB I/O."""
        for pattern, status, targets, rule_name in _RULES:
            if pattern.match(source_domain):
                return {"status": status, "targets": targets, "rule": rule_name}
        return {"status": "needs_review", "targets": {}, "rule": "no_match"}


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
                SELECT id, source_domain
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
                }
            )
        total += len(rows)
        logger.info("backfill_unrouted: processed %s (total=%s)", len(rows), total)
        if len(rows) < batch_size:
            break
    return total


def register_intel_lake_router_handlers(bus: EventBus, db_pool: asyncpg.Pool) -> None:
    """Register Tier 1 router on `intel_lake.event` channel.

    Called from backend.services.events.handlers._core.register_handlers.
    """
    router = IntelLakeRouter(db_pool)
    bus.subscribe("intel_lake.event", router.route_event)
    logger.info("intel_lake_router: subscribed to intel_lake.event channel")
