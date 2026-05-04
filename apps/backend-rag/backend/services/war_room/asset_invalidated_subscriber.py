"""WarRoom asset_invalidated subscriber.

Sprint 4 wiring: when mata-garuda invalidates a war_room_draft or
war_room_post (TTL elapsed via the Pro daily invalidation_sweeper, OR
event-driven invalidation when a reg_alert fires), the WR2 perimeter
needs to know so:

  * draft connectors can flag stale drafts before re-publishing
  * publisher orchestrator can demote outdated posts in the schedule
  * future Sprint 5 dashboards can surface "N war_room assets stale
    pending review" telemetry

Registered on the existing :class:`EventBus` for the
``mata_garuda.asset_invalidated`` event type (mapped from PG channel
``asset_invalidated`` in migration 155 / event_bus PG_CHANNEL_MAP).

Payload shape (from notify_asset_provenance trigger):
    - provenance_id: bigint
    - asset_kind: enum (12 canonical)
    - asset_id: text
    - source: text
    - reliability / credibility / tlp / valid_until / etc.
    - event_type: 'provenance_recorded' | 'provenance_updated'
    - invalidated_at: timestamptz | null
    - invalidated_by: varchar(64) | null   ('ttl_sweeper' | 'event:<topic>')
    - _outbox_id: bigint

We react ONLY to events where:
    1. asset_kind ∈ {war_room_draft, war_room_post}
    2. event_type == 'provenance_updated'
    3. invalidated_at IS NOT NULL  (the row WAS invalidated)

The handler is best-effort (never raises). It updates the war_room_drafts
or war_room_posts row's metadata to record the invalidation, which other
services can read.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


# The 2 asset_kinds we care about (the others are not WR2 assets).
_WR2_ASSET_KINDS = frozenset({"war_room_draft", "war_room_post"})


class AssetInvalidatedSubscriber:
    """Handler registered on EventBus for ``mata_garuda.asset_provenance``.

    Usage:
        subscriber = AssetInvalidatedSubscriber(db_pool=pool)
        bus.subscribe("mata_garuda.asset_provenance", subscriber.handle)

    NOTE: we subscribe to ``asset_provenance`` (not ``asset_invalidated``
    — that's a future channel for the daily sweep summary). The trigger
    in mig 155 emits ``asset_provenance`` events on every INSERT/UPDATE,
    and we filter for the invalidation transition (invalidated_at IS NOT
    NULL + event_type='provenance_updated') in the handler.
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._db_pool = db_pool

    async def handle(self, payload: dict[str, Any]) -> None:
        """EventBus handler. Always returns (never raises)."""
        try:
            await self._handle_inner(payload)
        except Exception:
            logger.exception(
                "AssetInvalidatedSubscriber: unhandled error for payload=%s",
                payload,
            )

    async def _handle_inner(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("event_type")
        if event_type != "provenance_updated":
            # We only care about updates (which include sweeper-triggered
            # invalidations). 'provenance_recorded' (initial INSERT) is
            # the tag-creation event handled elsewhere.
            return

        asset_kind = payload.get("asset_kind")
        if asset_kind not in _WR2_ASSET_KINDS:
            return

        invalidated_at = payload.get("invalidated_at")
        if invalidated_at is None:
            # Other UPDATE (e.g. credibility raised after corroboration).
            # Not an invalidation — ignore.
            return

        asset_id = payload.get("asset_id")
        if not asset_id:
            logger.warning(
                "AssetInvalidatedSubscriber: missing asset_id in payload=%s",
                payload,
            )
            return

        try:
            asset_uuid = UUID(str(asset_id))
        except (TypeError, ValueError):
            logger.warning(
                "AssetInvalidatedSubscriber: bad asset_id %r", asset_id,
            )
            return

        invalidated_by = payload.get("invalidated_by") or "unknown"
        provenance_id = payload.get("provenance_id")

        # Update the WR2 row's brief_json (drafts) or denormalize via a
        # lightweight metadata patch. For Sprint 4 wiring we keep this
        # simple: log the invalidation. Sprint 5 can extend to:
        #   - Update war_room_drafts.brief_json with {provenance_invalidated_at, by}
        #   - Notify Damar via Telegram if a recently-published post got invalidated
        #   - Demote in schedule if WR2 publisher has not yet sent
        logger.info(
            "AssetInvalidatedSubscriber: %s id=%s invalidated by=%s "
            "(provenance_id=%s, _outbox_id=%s)",
            asset_kind,
            asset_uuid,
            invalidated_by,
            provenance_id,
            payload.get("_outbox_id"),
        )

        # Optionally update brief_json / metadata on the source row so
        # downstream readers see the invalidation without a separate
        # provenance lookup. Best-effort — the event already carries the
        # full state, so this is just a denormalization convenience.
        if asset_kind == "war_room_draft":
            await self._patch_draft_metadata(
                draft_id=asset_uuid,
                invalidated_at=invalidated_at,
                invalidated_by=invalidated_by,
            )

    async def _patch_draft_metadata(
        self,
        *,
        draft_id: UUID,
        invalidated_at: Any,
        invalidated_by: str,
    ) -> None:
        """Append provenance_invalidated info to brief_json (best-effort).

        Uses jsonb_set so concurrent writes don't clobber unrelated
        brief_json keys. NEVER raises — failure is logged and the
        invalidation event is still surfaced via the handler log line
        above.
        """
        sql = """
            UPDATE war_room_drafts
            SET brief_json = COALESCE(brief_json, '{}'::jsonb) ||
                jsonb_build_object(
                    'provenance_invalidated_at', $2::text,
                    'provenance_invalidated_by', $3::text
                )
            WHERE id = $1
        """
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute(sql, draft_id, str(invalidated_at), invalidated_by)
        except Exception:
            logger.exception(
                "AssetInvalidatedSubscriber: failed to patch brief_json "
                "for draft=%s",
                draft_id,
            )
