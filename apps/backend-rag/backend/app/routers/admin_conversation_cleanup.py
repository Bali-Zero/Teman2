"""
Admin Conversation Cleanup Router

POST /api/admin/conversation-cleanup

Reports (and, only under an explicit env opt-in, applies) retention actions on
`conversations`: hard-delete past `delete_after_days`, anonymize past
`anonymize_after_days`.

Both windows are floored at RETENTION_MIN_DAYS and the write path is refused by
default — see the policy block below. Callers get a counting dry run unless they
ask otherwise.

Access: Requires ADMIN_API_KEY (via verify_debug_access)
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.core.retention_policy import (
    ALLOW_CLOCK_DELETE_ENV,
    RETENTION_MIN_DAYS,
    RetentionPolicyViolation,
    clock_delete_allowed,
    enforce_retention_floor,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-conversation-cleanup"])


def verify_admin_key(
    x_debug_key: str | None = Header(default=None, alias="x-debug-key", convert_underscores=False),
) -> bool:
    """Verify ADMIN_API_KEY via X-Debug-Key header."""
    if settings.admin_api_key and x_debug_key == settings.admin_api_key:
        return True
    raise HTTPException(status_code=401, detail="Authentication required")


# Retention policy lives in ONE module — see backend/core/retention_policy.py
# for the decision, the two answers behind it, and what it deliberately does
# NOT cover (per-subject erasure). This endpoint is one of two clock-driven
# doors; the other is the repository. Neither declares the rule itself.
#
# Request defaults sit AT the floor rather than under it. They used to be 90/30
# while the nightly cron asked for 30/7 — the drift that made the floor
# necessary in the first place.
DEFAULT_DELETE_AFTER_DAYS = RETENTION_MIN_DAYS
DEFAULT_ANONYMIZE_AFTER_DAYS = RETENTION_MIN_DAYS


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
        description=(
            f"Hard-delete conversations older than this many days. Floored at {RETENTION_MIN_DAYS}."
        ),
    ),
    anonymize_after_days: int = Query(
        default=DEFAULT_ANONYMIZE_AFTER_DAYS,
        ge=1,
        le=3650,
        description=(
            "Anonymize (strip PII) conversations older than this many days, up to "
            f"delete_after_days. Floored at {RETENTION_MIN_DAYS}. When the two are equal "
            "(the default) the anonymize window is empty by construction."
        ),
    ),
    dry_run: bool = Query(
        # Defaults to TRUE: the destructive reading must be asked for, never
        # inherited by a caller that omitted a parameter.
        default=True,
        description="Count records without modifying them (default). Pass false to act.",
    ),
    _access: bool = Depends(verify_admin_key),
    pool: Any = Depends(get_database_pool),
) -> CleanupResult:
    """
    Report — and, only under an explicit opt-in, apply — retention actions:
    - Hard-delete records older than `delete_after_days`
    - Anonymize (replace user PII with placeholders) records older than `anonymize_after_days`

    Anonymization replaces `messages` JSONB with a stub and clears metadata PII fields.
    It does NOT touch records that will be deleted in the same run.

    Refuses (400) any window below RETENTION_MIN_DAYS, and refuses (409) the
    entire write path unless CONVERSATION_RETENTION_ALLOW_CLOCK_DELETE is set.
    Both refusals happen before any query runs.
    """
    # ── policy floor ─────────────────────────────────────────────────────────
    # Refused BEFORE the dry-run branch on purpose: a dry run that reports
    # "would delete 2" for a window the policy forbids is a proposal to break
    # the policy, and printing that proposal nightly is exactly what the
    # now-disarmed cron did.
    try:
        enforce_retention_floor("delete_after_days", delete_after_days)
        enforce_retention_floor("anonymize_after_days", anonymize_after_days)
    except RetentionPolicyViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Every non-dry-run call reaches the DELETE below — there is no code path
    # that anonymises without first attempting it — so the whole write path is
    # what gets refused here, not "the delete half". Said plainly because the
    # first draft of this comment claimed the anonymise pass still ran, which
    # would have been a comment asserting behaviour the code does not have.
    # Refused rather than silently skipped: a caller must never read `status:
    # ok` and believe rows were removed.
    if not dry_run and not clock_delete_allowed():
        raise HTTPException(
            status_code=409,
            detail=(
                "Clock-driven deletion is disabled by policy ('non cancellare', 2026-08-08), "
                "and every write path here attempts one. Set "
                f"{ALLOW_CLOCK_DELETE_ENV}=1 to re-enable deliberately, or call with "
                "dry_run=true. Data-subject erasure is a separate, per-subject path."
            ),
        )

    start = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    delete_cutoff = now - timedelta(days=delete_after_days)
    anonymize_cutoff = now - timedelta(days=anonymize_after_days)

    deleted_count = 0
    anonymized_count = 0

    async with pool.acquire() as conn:
        if dry_run:
            # Count only — no writes
            deleted_count = (
                await conn.fetchval(
                    "SELECT COUNT(*) FROM conversations WHERE created_at < $1",
                    delete_cutoff,
                )
                or 0
            )

            anonymized_count = (
                await conn.fetchval(
                    """
                SELECT COUNT(*) FROM conversations
                WHERE created_at < $1 AND created_at >= $2
                """,
                    anonymize_cutoff,
                    delete_cutoff,
                )
                or 0
            )

            logger.info(
                "[DRY RUN] Would delete %s conversations, anonymize %s conversations",
                deleted_count,
                anonymized_count,
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
