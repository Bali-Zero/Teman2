"""Shared evaluator for the INTAKE login gate (3 gates) — F4 single source of truth.

Both the status probe (`GET /api/intake/gate/status`) and the enforcement
dependency (`require_gate_cleared`) call `evaluate_gate_status()` so the count
logic lives in exactly one place (panel fix F4 — no probe/dependency drift).

The three gates (spec 2026-06-06-intake-login-gate-spec.md §2):

  1. Documents 📄 — intake documents the user RECEIVED (by-receiver, Q1 v1) that
     still need approve/reject. Pending = document_routing_proposal.status in
     {review_pending} OR {review_claimed by THIS user} OR {review_claimed but the
     lease has expired = reclaimable}. Docs LIVE-claimed by someone else do NOT
     block you (F3); an expired foreign claim DOES count (it's reclaimable, F7).
  2. Late note ⏰ — attendance_late_incidents for this user's email in a pending
     state, for ALL dates not just today (F2 — else you escape by waiting a day).
  3. Client deadlines 🚨 — compliance_alerts on clients assigned to this user,
     status in {pending, sent}, deadline within 7 days, not yet acknowledged.

Counts only (no PII rows) — target < 50 ms via existing indexes.

Fail-OPEN (F4): if the evaluator hits its OWN internal error it returns a
non-blocking, error-flagged result and logs/alerts, rather than bricking the
whole company out of kita on a probe bug. The hard-gate guarantee comes from
this computing LIVE counts on the happy path, not from a cached value.

PII / Law 2: this reads only LOCAL Postgres and returns integers. No row content
leaves the function.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Deadlines within this many days count toward gate 3.
DEADLINE_HORIZON_DAYS = 7

# Pending states per gate (terminal states leave the pending set).
_DOC_PENDING_STATUSES = ("review_pending", "review_claimed")
_LATE_PENDING_STATES = ("AWAITING_REPLY", "REMINDER_SENT", "ESCALATED")
_DEADLINE_PENDING_STATUSES = ("pending", "sent")

# How old a mirrored doc-count row may be before it is treated as 0 (stale).
# Protects against a dead Pro pusher leaving a worker permanently gate-1-blocked.
_MIRROR_STALE_HOURS = 6


def _use_mirror() -> bool:
    """True on Fly (intake PII absent locally) → read the Pro→Fly count mirror.

    Set INTAKE_GATE_USE_MIRROR=1 on the Fly app. Unset on the Pro, where the
    live intake tables are the source of truth.
    """
    return os.getenv("INTAKE_GATE_USE_MIRROR", "").strip().lower() in {"1", "true", "yes", "on"}


async def _count_documents_mirror(conn: asyncpg.Connection, user_email: str) -> int:
    """Gate 1 on Fly — read the non-PII mirror pushed by the Pro (migration 219).

    A row older than _MIRROR_STALE_HOURS is treated as 0 (the pusher may be down;
    do not hard-block a worker on a stale signal — graceful, consistent with F4).
    """
    val = await conn.fetchval(
        """
        SELECT pending_count
          FROM intake_gate_doc_counts
         WHERE lower(user_email) = $1
           AND updated_at >= now() - ($2 || ' hours')::interval
        """,
        user_email,
        str(_MIRROR_STALE_HOURS),
    )
    return int(val or 0)


async def _count_documents(conn: asyncpg.Connection, user_email: str) -> int:
    """Gate 1 — documents the user received, still needing disposal.

    On Fly (INTAKE_GATE_USE_MIRROR) reads the Pro→Fly count mirror; on the Pro it
    queries the live local intake tables. Scope = by-receiver
    (intake_queue.received_by), the Q1-v1 decision. A doc blocks the receiver if
    it is unclaimed (review_pending) OR claimed by them OR claimed by someone else
    but the lease has expired (reclaimable, F7). A live foreign claim is excluded
    (F3).
    """
    if _use_mirror():
        return await _count_documents_mirror(conn, user_email)
    return int(
        await conn.fetchval(
            """
            SELECT count(*)
              FROM document_routing_proposal p
              JOIN intake_queue q ON q.id = p.queue_id
             WHERE lower(q.received_by) = $1
               AND p.status = ANY($2::text[])
               AND (
                     p.status = 'review_pending'
                  OR p.lease_owner = $1
                  OR p.lease_expires_at < now()
               )
            """,
            user_email,
            list(_DOC_PENDING_STATUSES),
        )
        or 0
    )


async def _count_late(conn: asyncpg.Connection, user_email: str) -> int:
    """Gate 2 — unexplained late notes for this user, ALL dates (F2)."""
    return int(
        await conn.fetchval(
            """
            SELECT count(*)
              FROM attendance_late_incidents
             WHERE lower(email) = $1
               AND state = ANY($2::text[])
               AND reply_received_at IS NULL
            """,
            user_email,
            list(_LATE_PENDING_STATES),
        )
        or 0
    )


async def _count_deadlines(conn: asyncpg.Connection, user_email: str) -> int:
    """Gate 3 — assigned-client statutory deadlines within the horizon, unack'd."""
    return int(
        await conn.fetchval(
            """
            SELECT count(*)
              FROM compliance_alerts a
              JOIN clients c ON c.id = a.client_id
             WHERE lower(c.assigned_to) = $1
               AND a.status = ANY($2::text[])
               AND a.deadline <= (CURRENT_DATE + ($3 || ' days')::interval)
            """,
            user_email,
            list(_DEADLINE_PENDING_STATUSES),
            str(DEADLINE_HORIZON_DAYS),
        )
        or 0
    )


async def evaluate_gate_status(
    pool: asyncpg.Pool,
    *,
    user_email: str,
    is_admin: bool = False,
) -> dict[str, Any]:
    """Compute the per-user gate clearance state.

    Returns the §3.1 contract shape:
        {
          "blocked": bool,              # true iff ANY section count > 0
          "sections": {
            "documents": {"count": int, "blocking": True},
            "late_note": {"count": int, "blocking": True},
            "deadlines": {"count": int, "blocking": True},
          },
          "as_of": "<iso8601 UTC>",
          "degraded": bool,             # True iff evaluator failed → fail-OPEN
        }

    F4 fail-OPEN: any internal error → blocked=False + degraded=True (logged),
    never an exception to the caller. F6 admin scoping: an admin is scoped to the
    items they personally received / are assigned to (same queries) — NOT the
    company-wide queue — so admins are not trapped behind hundreds of items. The
    visible "Admin override" is a frontend affordance (F6), not a count change.
    """
    email = (user_email or "").lower().strip()
    as_of = datetime.now(timezone.utc).isoformat()

    if not email:
        # No identity → cannot scope; fail OPEN (defensive, should never happen
        # because get_current_user already guarantees an email).
        logger.warning("gate_evaluator: empty user_email, failing OPEN")
        return _degraded(as_of)

    # F6: admins are scoped IDENTICALLY (by-receiver / assigned-to) — NOT the
    # company-wide queue — so they are never trapped behind hundreds of items.
    # is_admin therefore does not change the counts; it is logged for audit and
    # consumed by the frontend "Admin override" affordance, not here.
    logger.debug("gate_evaluator: user=%s is_admin=%s", email, is_admin)

    try:
        async with pool.acquire() as conn:
            documents = await _count_documents(conn, email)
            late = await _count_late(conn, email)
            deadlines = await _count_deadlines(conn, email)
    except Exception:
        logger.exception(
            "gate_evaluator: internal error for user=%s — failing OPEN", email
        )
        return _degraded(as_of)

    sections = {
        "documents": {"count": documents, "blocking": True},
        "late_note": {"count": late, "blocking": True},
        "deadlines": {"count": deadlines, "blocking": True},
    }
    # F6 (TAC 2026-06-19): admins/owners see the counts (badge) but are
    # NEVER walled by the gate — they reach /review when they choose, not
    # by coercion. Operational reviewers (non-admin) stay gated until clear.
    blocked = (not is_admin) and any(s["count"] > 0 for s in sections.values())
    return {
        "blocked": blocked,
        "sections": sections,
        "as_of": as_of,
        "degraded": False,
    }


def _degraded(as_of: str) -> dict[str, Any]:
    """Fail-OPEN result: never blocks, flags degraded so the probe can alert."""
    return {
        "blocked": False,
        "sections": {
            "documents": {"count": 0, "blocking": True},
            "late_note": {"count": 0, "blocking": True},
            "deadlines": {"count": 0, "blocking": True},
        },
        "as_of": as_of,
        "degraded": True,
    }
