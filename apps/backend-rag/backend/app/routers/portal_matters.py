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

import json
import re
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

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
    "on_process": 60,
    "sending_invoice": 40,
    "under_review": 80,
    "approved": 100,
    "completed": 100,
    "rejected": 0,
    "cancelled": 0,
}

_STATUS_COPY = {
    "inquiry": ("New request", "We are reviewing the request and confirming the first step."),
    "waiting_documents": ("Waiting for documents", "We are waiting for the documents listed below."),
    "in_progress": ("In progress", "We are working on this now."),
    "on_process": ("In progress", "We are working on this now."),
    "sending_invoice": ("Invoice pending", "The invoice is being prepared."),
    "under_review": ("Under review", "The team is checking the current result."),
    "approved": ("Approved", "This matter has been approved."),
    "completed": ("Completed", "This matter is complete."),
}

_NEXT_STEP_COPY = {
    "inquiry": "Confirm the first step",
    "waiting_documents": "Upload requested documents",
    "in_progress": "Team is processing this matter",
    "on_process": "Team is processing this matter",
    "sending_invoice": "Review invoice when issued",
    "under_review": "Wait for review result",
    "approved": "Approved",
    "completed": "Completed",
}

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _empty_client_safe_intelligence() -> dict[str, Any]:
    return {
        "available": False,
        "status": "pending",
        "company_name": None,
        "summary": None,
        "last_reviewed_at": None,
        "facts": [],
        "missing_items": [],
        "next_steps": [],
    }


def _shape_matter(row: asyncpg.Record) -> dict[str, Any]:
    category = (row["category"] or "").lower()
    matter_type = _CATEGORY_TO_MATTER_TYPE.get(category, "other")
    status = row["status"]

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
        "progress": _STATUS_TO_PROGRESS.get(status, 50),
        "pending_docs": pending,
        "next_deadline": row["expiry_date"].isoformat() if row["expiry_date"] else None,
        "next_step": _NEXT_STEP_COPY.get(status, "Wait for the next update"),
    }


def _shape_matter_detail(row: asyncpg.Record) -> dict[str, Any]:
    matter = _shape_matter(row)
    status = row["status"]
    status_label, description = _STATUS_COPY.get(
        status,
        ("In review", "We are reviewing the latest status."),
    )
    return {
        **matter,
        "status_label": status_label,
        "description": description,
        "approved_intelligence": _empty_client_safe_intelligence(),
    }


def _sanitize_client_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    direct_replacements = {
        "Run OCR on the source folder before client approval.": (
            "Review the document on the document record before client approval."
        ),
    }
    if text in direct_replacements:
        return direct_replacements[text]

    text = _URL_RE.sub("", text)
    replacements = (
        (r"\bGoogle Drive\b", "document record"),
        (r"\bDrive\b", "document record"),
        (r"\bsource_file_ids?\b", "document references"),
        (r"\bsource folder\b", "document record"),
        (r"\bsource documents\b", "documents"),
        (r"\bsource\b", "document"),
        (r"\bKG\b", "relationship map"),
        (r"\bOCR\b", "document review"),
        (r"\bNotebookLM\b", "team review"),
        (r"\bGemini\b", "team review"),
        (r"\bbackend\b", "team"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text)
    text = text.replace(" .", ".").replace(" ,", ",")
    return text.strip(" -")


def _parse_facts(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [fact for fact in parsed if isinstance(fact, dict)]


def _client_safe_intelligence_from_rows(rows: list[Any]) -> dict[str, Any]:
    safe = _empty_client_safe_intelligence()
    if not rows:
        return safe
    if len(rows) > 1:
        logger.warning(
            "Multiple approved intelligence candidates found for portal matter; withholding client-safe summary"
        )
        return safe

    company_name = _sanitize_client_text(rows[0].get("company_name"))
    approved_at = rows[0].get("approved_at")
    safe.update(
        {
            "available": True,
            "status": "approved",
            "company_name": company_name or None,
            "last_reviewed_at": approved_at.isoformat()
            if hasattr(approved_at, "isoformat")
            else approved_at,
        }
    )

    for row in rows:
        for fact in _parse_facts(row.get("facts")):
            category = fact.get("category")
            detail = _sanitize_client_text(fact.get("detail"))
            label = _sanitize_client_text(fact.get("label"))
            confidence = _sanitize_client_text(fact.get("confidence") or "medium")
            if not detail:
                continue
            if category == "gap":
                safe["missing_items"].append(detail)
            elif category == "next_action":
                safe["next_steps"].append(detail)
            elif category in {"identity", "person", "compliance"}:
                safe["facts"].append(
                    {
                        "category": category,
                        "label": label or "Reviewed item",
                        "detail": detail,
                        "confidence": confidence,
                    }
                )

    if safe["facts"]:
        safe["summary"] = safe["facts"][0]["detail"]

    safe["facts"] = safe["facts"][:5]
    safe["missing_items"] = safe["missing_items"][:5]
    safe["next_steps"] = safe["next_steps"][:5]
    return safe


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


@router.get("/{matter_id}")
async def get_matter_detail(
    matter_id: int,
    client: dict = Depends(get_current_client),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    client_id = client["client_id"]
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
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
            WHERE p.id = $1
              AND p.client_id = $2
              AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
              AND p.status NOT IN ('cancelled', 'rejected')
            """,
            matter_id,
            client_id,
        )

        if row is None:
            raise HTTPException(status_code=404, detail="Matter not found")

        matter = _shape_matter_detail(row)

        rows = []
        category = str(row["category"] or "").lower()
        if category in {"company", "tax", "property"}:
            try:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (snap.company_id)
                           c.company_name,
                           snap.facts,
                           snap.approved_at,
                           snap.created_at
                    FROM crm_workspace_ai_snapshots snap
                    JOIN companies c ON c.id = snap.company_id
                    JOIN client_company_links ccl ON ccl.company_id = snap.company_id
                    WHERE ccl.client_id = $1
                      AND snap.status = 'approved'
                    ORDER BY snap.company_id,
                             snap.approved_at DESC NULLS LAST,
                             snap.created_at DESC NULLS LAST
                    LIMIT 3
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"approved intelligence fetch failed: {e}")
                rows = []

    matter["approved_intelligence"] = _client_safe_intelligence_from_rows(
        [dict(row) for row in rows]
    )
    return {"matter": matter}
