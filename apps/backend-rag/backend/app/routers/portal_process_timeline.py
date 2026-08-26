"""
Portal Process Timeline Router.

Exposes practice status history as a visual timeline for the client portal.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/process", tags=["portal-process"])

# Canonical status ordering for visual stepper
STATUS_ORDER = [
    "inquiry",
    "quotation_sent",
    "sending_invoice",
    "payment_pending",
    "waiting_payment",
    "waiting_documents",
    "in_progress",
    "on_process",
    "submitted_to_gov",
    "approved",
    "completed",
]

STATUS_LABELS = {
    "inquiry": "Inquiry",
    "quotation_sent": "Quotation Sent",
    "sending_invoice": "Sending Invoice",
    "payment_pending": "Payment Pending",
    "waiting_payment": "Waiting for Payment",
    "waiting_documents": "Waiting for Documents",
    "in_progress": "In Progress",
    "on_process": "On Process",
    "submitted_to_gov": "Submitted to Government",
    "approved": "Approved",
    "completed": "Completed",
    "cancelled": "Cancelled",
}


async def _build_timeline(
    pool: asyncpg.Pool,
    practice_id: int,
    client_id: int,
) -> dict[str, Any] | None:
    """Build timeline data for a practice. Returns None if not found."""
    async with pool.acquire() as conn:
        # NOTE: this query is client-portal-only (see get_current_client
        # dependency below) — it must never select staff-identity columns
        # (practice_status_log.changed_by, clients.assigned_to). Those are
        # internal actor emails, not something to hand to a client. See
        # PR fixing the identity leak for the incident this guards against.
        practice = await conn.fetchrow(
            """
            SELECT p.id, p.client_id, p.status, p.start_date, p.completion_date,
                   p.expiry_date, p.notes, pt.name as practice_name,
                   pt.category as practice_category
            FROM practices p
            JOIN practice_types pt ON pt.id = p.practice_type_id
            WHERE p.id = $1
              AND p.client_id = $2
              AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
            """,
            practice_id,
            client_id,
        )

        if not practice:
            return None

        # Status history. Migration 289 creates practice_status_log and the
        # trigger that fills it; before that migration this query raised
        # UndefinedTableError on every request and the old code swallowed it
        # with a bare `except Exception: pass`, so the tracker answered 200
        # with a one-step timeline and no surface anywhere went red. Prod was
        # measured in exactly that state on 2026-08-27.
        #
        # The narrow except stays, because a database that has not run 289 yet
        # must still serve the practice's current status rather than 500 — but
        # it now catches ONLY "the table is absent" and says so out loud. Every
        # other failure (permissions, a dropped connection, a bad plan) is a
        # real fault and is logged as one instead of being spelled as an empty
        # history, which is indistinguishable from a practice that never moved.
        history_rows: list[dict] = []
        try:
            history_rows = [
                dict(r)
                for r in await conn.fetch(
                    """
                    SELECT old_status, new_status, changed_at
                    FROM practice_status_log
                    WHERE practice_id = $1
                    ORDER BY changed_at ASC
                    """,
                    practice_id,
                )
            ]
        except asyncpg.UndefinedTableError:
            logger.warning(
                "practice_status_log is absent — serving a single-step timeline. "
                "Migration 289 has not been applied to this database."
            )
        except asyncpg.PostgresError:
            logger.exception(
                "practice_status_log query failed for practice %s; serving a single-step timeline",
                practice_id,
            )

        current_status = practice["status"]

        if history_rows:
            steps = []
            for i, row in enumerate(history_rows):
                status = row["new_status"]
                is_current = status == current_status and i == len(history_rows) - 1
                steps.append(
                    {
                        "status": status,
                        "label": STATUS_LABELS.get(status, status.replace("_", " ").title()),
                        "completed": not is_current,
                        "is_current": is_current,
                        "changed_at": str(row["changed_at"]) if row["changed_at"] else None,
                    }
                )
        else:
            steps = [
                {
                    "status": current_status,
                    "label": STATUS_LABELS.get(
                        current_status, current_status.replace("_", " ").title()
                    ),
                    "completed": current_status in ("completed", "approved"),
                    "is_current": current_status not in ("completed", "approved", "cancelled"),
                    "changed_at": str(practice["start_date"]) if practice["start_date"] else None,
                }
            ]

        return {
            "practice_id": practice["id"],
            "practice_name": practice["practice_name"],
            "practice_category": practice["practice_category"],
            "current_status": current_status,
            "start_date": str(practice["start_date"]) if practice["start_date"] else None,
            "completion_date": str(practice["completion_date"])
            if practice["completion_date"]
            else None,
            "expiry_date": str(practice["expiry_date"]) if practice["expiry_date"] else None,
            "steps": steps,
        }


@router.get("/{practice_id}/timeline")
async def get_process_timeline(
    practice_id: int,
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get timeline of status changes for a specific practice."""
    result = await _build_timeline(db_pool, practice_id, client["client_id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    return {"success": True, "data": result}
