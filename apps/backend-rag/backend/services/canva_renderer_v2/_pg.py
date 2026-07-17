"""PostgreSQL layer for canva_renderer_v2.

Functions:
- is_kill_switch_enabled(conn) — reads system_settings.wr2_canva_renderer_enabled
- fetch_pending_draft_ids(conn, limit) — pre-scan IDs to attempt lease
- acquire_lease_and_fetch(conn, draft_id, lease_owner) — CAS, returns row or None
- inject_hero_paths(conn, draft_id, slides_json) — write hero_image_path into slides_json before cron
- persist_canva_result(conn, ...) — UPDATE status='rendered' + canva_* + clear lease
- release_lease_transient(conn, ...) — revert status='drafts_imaged_checked'
- release_lease_permanent(conn, ..., status=...) — set terminal status
- reset_stale_leases(conn, stale_after_minutes) — watchdog recovery
- requeue_draft_for_rerender(conn, draft_id) — official re-render verb (DB leg)
- rebrief_draft(conn, draft_id) — official remake-hygiene verb: reset to 'briefed'
  + atomically clear fact-check trio + render leg
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


async def is_kill_switch_enabled(conn: asyncpg.Connection) -> bool:
    value = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'wr2_canva_renderer_enabled'"
    )
    return value == "true"


async def fetch_pending_draft_ids(conn: asyncpg.Connection, limit: int = 3) -> list[UUID]:
    rows = await conn.fetch(
        """
        SELECT id FROM war_room_drafts
         WHERE status = 'drafts_imaged_checked'
           AND canva_edit_url IS NULL
           AND lease_owner IS NULL
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )
    return [r["id"] for r in rows]


async def fetch_pending_html_draft_ids(conn: asyncpg.Connection, limit: int = 3) -> list[UUID]:
    """HTML-lane fetch: selects on drive_url, NOT canva_edit_url.

    Pre-cutover drafts carry a canva_edit_url from old Canva runs; filtering
    on it (as the Canva-lane fetch does) starves them forever in
    drafts_imaged_checked while the supervisor reconcile keeps kicking them.
    Mirrors the guard already used by acquire_html_lease_and_fetch.
    """
    rows = await conn.fetch(
        """
        SELECT id FROM war_room_drafts
         WHERE status = 'drafts_imaged_checked'
           AND drive_url IS NULL
           AND lease_owner IS NULL
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )
    return [r["id"] for r in rows]


async def requeue_draft_for_rerender(conn: asyncpg.Connection, draft_id: UUID | str) -> bool:
    """Official re-render verb (DB leg): put a finished draft back into the HTML lane.

    The HTML-lane fetch gates on `drive_url IS NULL`, so once a draft has been
    rendered+uploaded a fixed brief/layout can never re-enter the pipeline —
    the row EXISTS but its refreshed content is unreachable (W82 exist-not-content).
    This resets exactly the two fields that gate re-entry.

    Guards:
    - status whitelist: only drafts that already passed image-check may re-enter
      ('rendered', 'render_failed', or a drive_url-starved 'drafts_imaged_checked');
      a pre-image draft must never be jumped forward in the pipeline.
    - CAS on `lease_owner IS NULL`: a draft mid-render is never yanked from
      under its worker (same discipline as the stale-lease watchdog).
    - `html_render_attempts` resets to 0: a re-render is a NEW retry budget —
      without this, a draft that previously exhausted its attempts (or spent
      some) re-enters with a burned circuit breaker and the first transient
      error of the new cycle goes terminal (Codex review 2026-07-13).

    Returns True when the draft re-entered the lane, False otherwise.
    """
    row = await conn.fetchrow(
        """
        UPDATE war_room_drafts
           SET status = 'drafts_imaged_checked',
               drive_url = NULL,
               html_render_attempts = 0
         WHERE id = $1
           AND lease_owner IS NULL
           AND status IN ('rendered', 'render_failed', 'drafts_imaged_checked')
        RETURNING id
        """,
        draft_id,
    )
    if row is None:
        logger.warning(
            "requeue_draft_for_rerender: draft %s NOT requeued (leased or wrong status)", draft_id
        )
        return False
    logger.info("requeue_draft_for_rerender: draft %s back in HTML lane", draft_id)
    return True


async def rebrief_draft(conn: asyncpg.Connection, draft_id: UUID | str) -> bool:
    """Official remake-hygiene verb: reset a COMPOSED draft back to 'briefed' so it
    recomposes cleanly from its existing brief_json, atomically clearing every
    downstream field a stale draft would otherwise leave dangling. Same W82
    exist-not-content shape as `requeue_draft_for_rerender` above: the row EXISTS
    at a later pipeline stage but its content is now stale relative to the fresh
    recompose the operator wants — the gates below decide who re-runs on it.

    Why each field is cleared (every one gates a downstream worker's fetch):
    - status = 'briefed': the draft-generator fetches on this status — the draft
      recomposes from brief_json instead of dragging forward the old slides.
    - fact_check_json/status/at = NULL: the fact-EXTRACTOR gates on
      `fact_check_json IS NULL` to decide whether to run. A stale (non-NULL) JSON
      from the PREVIOUS compose makes it skip — the checker then runs against
      facts that no longer describe the recomposed content.
    - drive_url = NULL: the HTML lane's fetch gates on `drive_url IS NULL` — a
      stale url from a PREVIOUS render starves re-entry forever (identical W82
      shape to the one `requeue_draft_for_rerender` cures for the render-only leg).
    - html_render_attempts = 0: a rebrief is a NEW retry budget — carrying a
      previously-burned attempts counter forward would let the first transient
      error of the new cycle go terminal (same reasoning as the sibling fn).

    Guards:
    - CAS on `lease_owner IS NULL`: a draft mid-lane (fact-check/image/render) is
      never yanked from under its worker.
    - status whitelist: only drafts that already reached compose-or-later may be
      rebriefed — a pre-compose draft ('briefed'/'briefed_facted'/'researched'/
      'concept') is a no-op, it's already at/before this state — and only
      mid-pipeline or failure-retry states, NEVER a deliberate human/terminal
      state ('rejected'/'parked'/'published'/'approved'/'pending_review'/
      'missed'). Every literal below is validated against the
      `war_room_drafts_status_check` CHECK constraint in
      migrations_v2/245_war_room_drafts_parked_status.sql — the SSOT — NOT the
      ORM DraftStatus enum, which is a strict subset (omits drafts_imaged*,
      drafts_checked, fact_check_failed, image_failed).

    Out of scope: hero-image fields / image lease. Recomposition regenerates
    slides and the image lane re-runs on the new slides — if a hero-image field
    also goes stale, that's a follow-up, not this verb's job.

    Returns True when the draft was reset, False (leased, wrong status, or not
    found) otherwise.
    """
    row = await conn.fetchrow(
        """
        UPDATE war_room_drafts
           SET status = 'briefed',
               fact_check_json = NULL,
               fact_check_status = NULL,
               fact_check_at = NULL,
               drive_url = NULL,
               html_render_attempts = 0
         WHERE id = $1
           AND lease_owner IS NULL
           AND status IN ('drafts', 'drafts_checked', 'drafts_imaged',
                           'drafts_imaged_facted', 'drafts_imaged_checked',
                           'rendering', 'rendered', 'render_failed',
                           'fact_check_failed', 'image_failed')
        RETURNING id
        """,
        draft_id,
    )
    if row is None:
        logger.warning(
            "rebrief_draft: draft %s NOT rebriefed (leased or wrong status)", draft_id
        )
        return False
    logger.info("rebrief_draft: draft %s reset to briefed (remake hygiene)", draft_id)
    return True


async def acquire_lease_and_fetch(
    conn: asyncpg.Connection,
    *,
    draft_id: UUID | str,
    lease_owner: str,
) -> dict[str, Any] | None:
    """CAS lease + return row payload, or None if another process won."""
    row = await conn.fetchrow(
        """
        UPDATE war_room_drafts
           SET status = 'rendering',
               lease_owner = $1,
               lease_acquired_at = NOW(),
               updated_at = NOW()
         WHERE id = $2
           AND status = 'drafts_imaged_checked'
           AND canva_edit_url IS NULL
           AND lease_owner IS NULL
        RETURNING id, topic, register AS tone, slides_json
        """,
        lease_owner,
        draft_id,
    )
    if row is None:
        logger.info("Draft %s lease lost to another process", draft_id)
    return dict(row) if row else None


async def inject_hero_paths(
    conn: asyncpg.Connection,
    *,
    draft_id: UUID | str,
    slides_json: dict[str, Any],
) -> None:
    """Write slides_json (with hero_image_path on each is_hero_image slide) to PG.

    Called by wr2-design-architect after Codex imagegen completes for ALL hero
    slides, BEFORE setting status='drafts_imaged_checked'. The orchestrator cron
    reads slides_json at render time — hero_image_path must be present then.

    Idempotent: safe to call multiple times (last write wins).
    """
    import json as _json

    await conn.execute(
        """
        UPDATE war_room_drafts
           SET slides_json = $2::jsonb,
               updated_at = NOW()
         WHERE id = $1
           AND status NOT IN ('rendering', 'rendered')
        """,
        draft_id,
        _json.dumps(slides_json),
    )
    logger.info("Draft %s slides_json updated with hero_image_path fields", draft_id)


async def persist_canva_result(
    conn: asyncpg.Connection,
    *,
    draft_id: UUID | str,
    canva_design_id: str,
    canva_edit_url: str,
    canva_view_url: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET canva_design_id = $2,
               canva_edit_url = $3,
               canva_view_url = $4,
               canva_applied_at = NOW(),
               status = 'rendered',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id,
        canva_design_id,
        canva_edit_url,
        canva_view_url,
    )


async def release_lease_transient(
    conn: asyncpg.Connection,
    *,
    draft_id: UUID | str,
    reason: str,
) -> None:
    """Revert to drafts_imaged_checked for natural retry on next tick."""
    logger.info("Draft %s released as transient: %s", draft_id, reason)
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET status = 'drafts_imaged_checked',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id,
    )


async def release_lease_permanent(
    conn: asyncpg.Connection,
    *,
    draft_id: UUID | str,
    status: str,
    reason: str,
) -> None:
    """Mark terminal failure status. Not picked up by next tick."""
    logger.warning("Draft %s permanent failure (%s): %s", draft_id, status, reason)
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET status = $2,
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id,
        status,
    )


async def reset_stale_leases(
    conn: asyncpg.Connection,
    *,
    stale_after_minutes: int = 15,
) -> list[UUID]:
    """Watchdog: revert status='rendering' rows with old lease_acquired_at."""
    rows = await conn.fetch(
        """
        UPDATE war_room_drafts
           SET status = 'drafts_imaged_checked',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE status = 'rendering'
           AND lease_acquired_at < NOW() - ($1 || ' minutes')::interval
        RETURNING id
        """,
        str(stale_after_minutes),
    )
    return [r["id"] for r in rows]


# ── WR2 HTML lane (v4 wiring) ────────────────────────────────────────────────
# Parallel to the Canva functions above; does NOT touch them. The HTML renderer
# (scripts/wr2_html_renderer) replaces Canva at the apply chokepoint. Canva stays
# intact as a clean rollback target. Kill-switch key: wr2_html_renderer_enabled.

HTML_KILL_SWITCH_KEY = "wr2_html_renderer_enabled"


async def is_html_kill_switch_enabled(conn: asyncpg.Connection) -> bool:
    """HTML lane gate — reads system_settings.wr2_html_renderer_enabled.

    Returns False (disabled) unless the row exists AND value == 'true'. A missing
    row means OFF — the lane no-ops until an operator flips it on after the shadow run.
    """
    value = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = $1",
        HTML_KILL_SWITCH_KEY,
    )
    return value == "true"


async def acquire_html_lease_and_fetch(
    conn: asyncpg.Connection,
    *,
    draft_id: UUID | str,
    lease_owner: str,
) -> dict[str, Any] | None:
    """CAS claim for the HTML lane + return row payload, or None if lost.

    Same gate as the Canva lane (status='drafts_imaged_checked', no active lease) so
    the two never double-render a row — distinct lease_owner per worker. Sets
    lease_heartbeat_at=NOW() so the heartbeat-based stale-reset has an initial value.
    drive_url IS NULL guards against re-claiming an already-delivered HTML draft.
    """
    row = await conn.fetchrow(
        """
        UPDATE war_room_drafts
           SET status = 'rendering',
               lease_owner = $1,
               lease_acquired_at = NOW(),
               lease_heartbeat_at = NOW(),
               updated_at = NOW()
         WHERE id = $2
           AND status = 'drafts_imaged_checked'
           AND drive_url IS NULL
           AND lease_owner IS NULL
        RETURNING id, topic, register AS tone, slides_json
        """,
        lease_owner,
        draft_id,
    )
    if row is None:
        logger.info("HTML draft %s lease lost to another process", draft_id)
    return dict(row) if row else None


async def heartbeat_html_lease(
    conn: asyncpg.Connection,
    *,
    draft_id: UUID | str,
    lease_owner: str,
) -> bool:
    """Renew the HTML lease mid-render. Returns False if the lease is no longer ours
    (status moved off 'rendering' OR lease_owner changed — e.g. stale-reset stole it).
    The worker MUST abort rendering before any Drive write when this returns False
    (condition C4: heartbeat loss is fatal, prevents concurrent WR2-{draft_id} folders).
    """
    result = await conn.execute(
        """
        UPDATE war_room_drafts
           SET lease_heartbeat_at = NOW(), updated_at = NOW()
         WHERE id = $1 AND lease_owner = $2 AND status = 'rendering'
        """,
        draft_id,
        lease_owner,
    )
    # asyncpg returns e.g. "UPDATE 1" / "UPDATE 0"
    return result.endswith(" 1")


async def reset_stale_html_leases(
    conn: asyncpg.Connection,
    *,
    stale_after_minutes: int = 10,
) -> list[UUID]:
    """Watchdog for the HTML lane: revert 'rendering' rows whose HEARTBEAT (not start)
    is older than the window. A live worker heartbeats every ~60s so it is never
    reclaimed regardless of total render time; only a dead worker is freed.
    Scoped to HTML-lane rows (drive_url IS NULL) so it never disturbs a Canva lease
    (Canva rows reach 'rendering' too, but the Canva watchdog keys off lease_acquired_at).
    """
    rows = await conn.fetch(
        """
        UPDATE war_room_drafts
           SET status = 'drafts_imaged_checked',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               lease_heartbeat_at = NULL,
               updated_at = NOW()
         WHERE status = 'rendering'
           AND drive_url IS NULL
           AND lease_heartbeat_at IS NOT NULL
           AND lease_heartbeat_at < NOW() - ($1 || ' minutes')::interval
        RETURNING id
        """,
        str(stale_after_minutes),
    )
    return [r["id"] for r in rows]


async def persist_html_result_and_enqueue_notifications(
    conn: asyncpg.Connection,
    *,
    draft_id: UUID | str,
    lease_owner: str,
    drive_url: str,
    recipients: list[str],
    message_body: str,
    customer_window_hours: int = 24,
) -> dict[str, Any]:
    """Atomic terminal step (condition C1 + C7): in ONE transaction —
      1. promote the draft to status='rendered' + drive_url, ONLY if WE still own the
         lease (WHERE lease_owner=$x AND status='rendering'). If 0 rows → lease was
         stolen mid-render → raise so the worker aborts WITHOUT Drive/outbox side effects
         already committed (caller must not have written Drive after a failed heartbeat).
      2. per recipient: upsert meta_inbox_threads(counterpart_phone), insert an OUTBOUND
         bot message with idempotency_key='wr2:{draft_id}:{recipient}' using the EXACT
         ON CONFLICT (thread_id, idempotency_key) WHERE idempotency_key IS NOT NULL
         DO NOTHING shape from wa_inbox.py, then INSERT wa_outbox ONLY when a row was
         returned (skip-on-conflict). If the 24h window is CLOSED, the row is still
         enqueued; the existing wa_outbox_worker marks it failed + the caller alerts ops
         (C6 — never delivered via Telegram; the carousel link lives on Drive regardless).

    Returns a per-recipient report: {recipient: {"enqueued": bool, "window_open": bool}}.
    Raises RuntimeError("lease_lost") if the promote affected 0 rows.
    """
    report: dict[str, Any] = {}
    async with conn.transaction():
        promoted = await conn.execute(
            """
            UPDATE war_room_drafts
               SET status = 'rendered',
                   drive_url = $3,
                   lease_owner = NULL,
                   lease_acquired_at = NULL,
                   lease_heartbeat_at = NULL,
                   updated_at = NOW()
             WHERE id = $1 AND lease_owner = $2 AND status = 'rendering'
            """,
            draft_id,
            lease_owner,
            drive_url,
        )
        if not promoted.endswith(" 1"):
            raise RuntimeError("lease_lost")

        for recipient in recipients:
            idem = f"wr2:{draft_id}:{recipient}"
            thread = await conn.fetchrow(
                """
                INSERT INTO meta_inbox_threads (counterpart_phone)
                VALUES ($1)
                ON CONFLICT (counterpart_phone) DO UPDATE
                    SET counterpart_phone = EXCLUDED.counterpart_phone
                RETURNING thread_id,
                          (last_customer_at IS NOT NULL
                           AND NOW() - last_customer_at < ($2 * INTERVAL '1 hour')) AS window_open
                """,
                recipient,
                customer_window_hours,
            )
            thread_id = thread["thread_id"]
            window_open = bool(thread["window_open"])

            ledger = await conn.fetchrow(
                """
                INSERT INTO meta_inbox_messages (
                    thread_id, direction, sender_role, body, status, idempotency_key
                )
                VALUES ($1, 'outbound', 'bot', $2, 'queued', $3)
                ON CONFLICT (thread_id, idempotency_key)
                    WHERE idempotency_key IS NOT NULL DO NOTHING
                RETURNING id
                """,
                thread_id,
                message_body,
                idem,
            )
            if ledger is None:
                # Already enqueued for this draft+recipient (idempotent replay) — skip.
                report[recipient] = {"enqueued": False, "window_open": window_open, "duplicate": True}
                continue

            await conn.execute(
                """
                INSERT INTO wa_outbox (thread_id, message_id, needs_generation, status)
                VALUES ($1, $2, false, 'pending')
                ON CONFLICT (message_id) DO NOTHING
                """,
                thread_id,
                ledger["id"],
            )
            report[recipient] = {"enqueued": True, "window_open": window_open, "duplicate": False}
    return report
