"""CRM-Guardian summary queue enqueue helpers.

Inserts pending jobs into crm_guardian_summary_queue (migration 130) for the
gemini CLI worker to consume. Phase 1 cross-folder semantics: a file change
in EITHER the client root folder OR a linked company folder triggers enqueue
for the client(s) involved.

Public API:
  - enqueue_client(conn, client_id): single client (idempotent)
  - enqueue_clients_for_company_folder(conn, drive_folder_id): cascading
    enqueue of all clients linked to a company whose Drive folder changed

Idempotency: relies on the UNIQUE INDEX ux_crm_guardian_queue_client_pending
defined in migration 130 (one row per client while status IN ('pending',
'running')). ON CONFLICT DO NOTHING for safe repeated calls.

Priority follows migration 180 config:
  VIP      → 1   (clients.ai_summary->profile->>'tier' = 'VIP')
  standard → 50  (default for clients without a prior summary)
  archive  → 100

Activation gate: enqueue is a no-op when crm_guardian_state.enabled is false
for invariant 'I10b_summary_queue'. This lets Phase 1 ship the cascading
trigger in drive_poll_service.py without inflating the queue before the
worker LaunchAgent is deployed at Day 7.
"""
from __future__ import annotations

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

PRIORITY_VIP = 1
PRIORITY_STANDARD = 50
PRIORITY_ARCHIVE = 100


async def is_enqueue_enabled(conn: asyncpg.Connection) -> bool:
    """Check if I10b_summary_queue is enabled in crm_guardian_state.

    Returns True only if (enabled=true). The dry_run flag does NOT block
    enqueue — dry_run controls whether the WORKER writes clients.ai_summary,
    not whether jobs get enqueued.
    """
    row = await conn.fetchrow(
        "SELECT enabled FROM crm_guardian_state WHERE invariant_id = 'I10b_summary_queue'",
    )
    return bool(row and row["enabled"])


def _priority_for_tier(tier: str | None) -> int:
    """Map clients.ai_summary->profile->>'tier' to queue priority int."""
    if tier == "VIP":
        return PRIORITY_VIP
    if tier == "archive":
        return PRIORITY_ARCHIVE
    return PRIORITY_STANDARD


async def enqueue_client(
    conn: asyncpg.Connection,
    client_id: int,
    *,
    enqueued_by: str = "drive_poll_service",
    force: bool = False,
) -> dict[str, Any]:
    """Enqueue a single client for L1 summary generation.

    Idempotent: if a 'pending' or 'running' row exists, returns it untouched.
    No-op if I10b_summary_queue invariant is disabled (unless force=True).

    Returns:
      {
        "client_id": int,
        "queue_id": int | None,
        "action": "inserted" | "already_pending" | "skipped_disabled" | "client_not_found",
        "priority": int | None,
      }
    """
    if not force:
        if not await is_enqueue_enabled(conn):
            logger.debug("enqueue skipped: I10b_summary_queue disabled")
            return {
                "client_id": client_id,
                "queue_id": None,
                "action": "skipped_disabled",
                "priority": None,
            }

    # Verify client exists + read tier from existing summary (if any)
    client_row = await conn.fetchrow(
        """
        SELECT id, google_drive_folder_id,
               (ai_summary -> 'profile' ->> 'tier') AS tier
        FROM clients WHERE id = $1
        """,
        client_id,
    )
    if not client_row:
        logger.warning("enqueue_client: client_id %d not found", client_id)
        return {
            "client_id": client_id,
            "queue_id": None,
            "action": "client_not_found",
            "priority": None,
        }
    if not client_row["google_drive_folder_id"]:
        logger.debug(
            "enqueue_client: client %d has no google_drive_folder_id, skipping",
            client_id,
        )
        return {
            "client_id": client_id,
            "queue_id": None,
            "action": "client_not_found",  # treat as missing prerequisite
            "priority": None,
        }

    priority = _priority_for_tier(client_row["tier"])

    # Check if a pending/running row already exists (UNIQUE INDEX guards this
    # but we also want to surface "already_pending" without an INSERT attempt)
    existing = await conn.fetchrow(
        """
        SELECT id FROM crm_guardian_summary_queue
        WHERE client_id = $1 AND status IN ('pending', 'running')
        """,
        client_id,
    )
    if existing:
        return {
            "client_id": client_id,
            "queue_id": existing["id"],
            "action": "already_pending",
            "priority": priority,
        }

    row = await conn.fetchrow(
        """
        INSERT INTO crm_guardian_summary_queue (
            client_id, status, priority, drive_folder_id, notes, enqueued_at
        )
        VALUES ($1, 'pending', $2, $3, $4, NOW())
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        client_id,
        priority,
        client_row["google_drive_folder_id"],
        f"enqueued_by={enqueued_by}",
    )

    if row is None:
        # Race: another caller inserted between our SELECT and INSERT
        existing = await conn.fetchrow(
            """
            SELECT id FROM crm_guardian_summary_queue
            WHERE client_id = $1 AND status IN ('pending', 'running')
            """,
            client_id,
        )
        return {
            "client_id": client_id,
            "queue_id": existing["id"] if existing else None,
            "action": "already_pending",
            "priority": priority,
        }

    logger.info(
        "enqueue_client: client %d → queue_id %d priority %d (%s)",
        client_id, row["id"], priority, enqueued_by,
    )
    return {
        "client_id": client_id,
        "queue_id": row["id"],
        "action": "inserted",
        "priority": priority,
    }


async def enqueue_clients_for_company_folder(
    conn: asyncpg.Connection,
    drive_folder_id: str,
    *,
    enqueued_by: str = "drive_poll_service:company_cascade",
    force: bool = False,
) -> list[dict[str, Any]]:
    """Cascading enqueue for all clients linked to a company whose Drive
    folder changed.

    Phase 1 trigger: a file change inside a company's google_drive_folder_id
    invalidates the cross-folder fingerprint of every client linked to that
    company via client_company_links (status='active'). Re-enqueue all of
    them so the worker regenerates their summaries with the fresh corporate
    document state.

    Returns list of per-client enqueue results (see enqueue_client docstring).
    Empty list if drive_folder_id is not a known company folder.

    Performance note: clients linked to a popular shared company (e.g. a
    holding entity with 10+ shareholders) get N enqueues per file change.
    Idempotency via unique-pending-index prevents queue blowup; the worker
    processes each row once and skips fingerprint-unchanged downstream.
    """
    # Resolve company by Drive folder
    company_row = await conn.fetchrow(
        """
        SELECT id, company_name FROM companies
        WHERE google_drive_folder_id = $1
        """,
        drive_folder_id,
    )
    if not company_row:
        logger.debug(
            "enqueue cascade: folder %s not mapped to any company", drive_folder_id,
        )
        return []

    # Find all active client links
    client_rows = await conn.fetch(
        """
        SELECT DISTINCT ccl.client_id
        FROM client_company_links ccl
        WHERE ccl.company_id = $1
          AND ccl.status = 'active'
        """,
        company_row["id"],
    )
    if not client_rows:
        logger.info(
            "enqueue cascade: company %d (%s) has no active client links",
            company_row["id"], company_row["company_name"],
        )
        return []

    logger.info(
        "enqueue cascade: folder %s → company %d (%s) → %d active clients",
        drive_folder_id, company_row["id"], company_row["company_name"],
        len(client_rows),
    )

    results: list[dict[str, Any]] = []
    for r in client_rows:
        result = await enqueue_client(
            conn, r["client_id"], enqueued_by=enqueued_by, force=force,
        )
        results.append(result)
    return results
