"""
Portal Matters Router.

Returns the client's "matters" — a normalized view of practices (visa, company,
tax, property) shaped for the MatterCard UI component.

No migration required: builds the matter list at query time from the existing
`practices` table joined with `practice_types`. Graceful degradation keeps
empty-list semantics when the tables/columns are missing.

Matter shape matches @balizero/core MatterCardProps:
  { id, title, type, progress, pending_docs, next_deadline, next_step }
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/matters", tags=["portal-matters"])


# Map practice_types.category → MatterCard `type` union
_CATEGORY_TO_MATTER_TYPE = {
    "visa": "visa",
    "company": "company",
    "tax": "tax",
    "property": "property",
}

# Heuristic: progress ramps 10/50/90 based on status. Keeps UI lively without a
# dedicated `progress_percent` column (which doesn't exist in practices today).
_STATUS_TO_PROGRESS = {
    "inquiry": 10,
    "waiting_documents": 30,
    "in_progress": 60,
    "under_review": 80,
    "approved": 100,
    "completed": 100,
    "rejected": 0,
    "cancelled": 0,
}


def _shape_matter(row: asyncpg.Record) -> dict[str, Any]:
    category = (row["category"] or "").lower()
    matter_type = _CATEGORY_TO_MATTER_TYPE.get(category, "other")

    missing = row["missing_documents"]
    # `missing_documents` in practices is TEXT (comma-separated) or JSON-ish;
    # split on commas when it's a string, else pass through empty list.
    pending: list[str] = []
    if missing:
        if isinstance(missing, str):
            pending = [s.strip() for s in missing.split(",") if s.strip()]
        elif isinstance(missing, list):
            pending = [str(s) for s in missing]

    return {
        "id": row["id"],
        "title": row["title"],
        "type": matter_type,
        "progress": _STATUS_TO_PROGRESS.get(row["status"], 50),
        "pending_docs": pending,
        "next_deadline": row["expiry_date"].isoformat() if row["expiry_date"] else None,
        "next_step": row["status"],
    }


@router.get("")
async def list_matters(
    client: dict = Depends(get_current_client),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    client_id = client["client_id"]
    matters: list[dict[str, Any]] = []
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT p.id,
                       pt.name AS title,
                       pt.category,
                       p.status,
                       p.missing_documents,
                       p.expiry_date,
                       p.updated_at
                FROM practices p
                JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE p.client_id = $1
                  AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                  AND p.status NOT IN ('cancelled', 'rejected')
                ORDER BY p.updated_at DESC NULLS LAST
                """,
                client_id,
            )
            matters = [_shape_matter(r) for r in rows]
        except Exception as e:  # table/column may not yet exist in dev
            logger.warning(f"matters list fetch failed: {e}")
            matters = []

    return {"matters": matters}
