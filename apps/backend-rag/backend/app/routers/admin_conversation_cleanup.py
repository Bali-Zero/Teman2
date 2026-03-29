"""
Admin Conversation Cleanup Router

POST /api/admin/conversation-cleanup

Deletes conversations older than a configurable retention period and
anonymizes conversations that fall within a secondary window.

Access: Requires ADMIN_API_KEY (via verify_debug_access)
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-conversation-cleanup"])


def verify_admin_key(x_debug_key: str | None = Header(default=None, alias="X-Debug-Key")) -> bool:
    """Verify ADMIN_API_KEY via X-Debug-Key header."""
    if settings.admin_api_key and x_debug_key == settings.admin_api_key:
        return True
    raise HTTPException(status_code=401, detail="Authentication required")

# Default retention windows
DEFAULT_DELETE_AFTER_DAYS = 90       # Hard delete conversations older than 90 days
DEFAULT_ANONYMIZE_AFTER_DAYS = 30    # Anonymize conversations older than 30 days


# =============================================================================
# Response Models
# =============================================================================


class CleanupResult(BaseModel):
    """Result of a conversation cleanup run."""
    deleted_count: int
    anonymized_count: int
    delete_cutoff: datetime
    anonymize_cutoff: datetime
    duration_ms: float
    status: str


# =============================================================================
# Endpoint
# =============================================================================


@router.post("/conversation-cleanup", response_model=CleanupResult)
async def run_conversation_cleanup(
    delete_after_days: int = Query(
        default=DEFAULT_DELETE_AFTER_DAYS,
        ge=1,
        le=3650,
        description="Hard-delete conversations older than this many days",
    ),
    anonymize_after_days: int = Query(
        default=DEFAULT_ANONYMIZE_AFTER_DAYS,
        ge=1,
        le=3650,
        description="Anonymize (strip PII) conversations older than this many days (must be < delete_after_days)",
    ),
    dry_run: bool = Query(
        default=False,
        description="If true, count records but do not modify them",
    ),
    _access: bool = Depends(verify_admin_key),
    pool: Any = Depends(get_database_pool),
) -> CleanupResult:
    """
    Clean up old conversations:
    - Hard-delete records older than `delete_after_days`
    - Anonymize (replace user PII with placeholders) records older than `anonymize_after_days`

    Anonymization replaces `messages` JSONB with a stub and clears metadata PII fields.
    It does NOT touch records that will be deleted in the same run.
    """
    start = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    delete_cutoff = now - timedelta(days=delete_after_days)
    anonymize_cutoff = now - timedelta(days=anonymize_after_days)

    deleted_count = 0
    anonymized_count = 0

    async with pool.acquire() as conn:
        if dry_run:
            # Count only — no writes
            deleted_count = await conn.fetchval(
                "SELECT COUNT(*) FROM conversations WHERE created_at < $1",
                delete_cutoff,
            ) or 0

            anonymized_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM conversations
                WHERE created_at < $1 AND created_at >= $2
                """,
                anonymize_cutoff,
                delete_cutoff,
            ) or 0

            logger.info(
                f"[DRY RUN] Would delete {deleted_count} conversations, "
                f"anonymize {anonymized_count} conversations"
            )
        else:
            # 1. Hard-delete old conversations
            result = await conn.execute(
                "DELETE FROM conversations WHERE created_at < $1",
                delete_cutoff,
            )
            # asyncpg returns "DELETE N" as a string
            try:
                deleted_count = int(result.split()[-1])
            except (ValueError, IndexError, AttributeError):
                deleted_count = 0

            logger.info(f"Deleted {deleted_count} conversations older than {delete_cutoff.date()}")

            # 2. Anonymize remaining conversations in the anonymize window
            # (older than anonymize_cutoff but not deleted above)
            anon_result = await conn.execute(
                """
                UPDATE conversations
                SET
                    messages = '[]'::jsonb,
                    metadata = jsonb_build_object(
                        'anonymized', true,
                        'anonymized_at', $3::text
                    )
                WHERE created_at < $1
                  AND created_at >= $2
                  AND (metadata->>'anonymized') IS DISTINCT FROM 'true'
                """,
                anonymize_cutoff,
                delete_cutoff,
                now.isoformat(),
            )
            try:
                anonymized_count = int(anon_result.split()[-1])
            except (ValueError, IndexError, AttributeError):
                anonymized_count = 0

            logger.info(
                f"Anonymized {anonymized_count} conversations between "
                f"{delete_cutoff.date()} and {anonymize_cutoff.date()}"
            )

    duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    return CleanupResult(
        deleted_count=deleted_count,
        anonymized_count=anonymized_count,
        delete_cutoff=delete_cutoff,
        anonymize_cutoff=anonymize_cutoff,
        duration_ms=round(duration_ms, 2),
        status="dry_run" if dry_run else "ok",
    )
