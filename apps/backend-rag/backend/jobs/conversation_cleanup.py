"""
Conversation Cleanup Job
Daily cron job to cleanup old conversations and anonymize user data
"""

import asyncio
from datetime import datetime, timezone

from backend.app.core.database import get_db_pool
from backend.app.utils.logging_utils import get_logger, log_error, log_success
from backend.core.retention_policy import RETENTION_MIN_DAYS
from backend.db.repositories.conversation_repository import ConversationRepository

logger = get_logger(__name__)


async def cleanup_conversations(
    retention_days: int = RETENTION_MIN_DAYS,
    anonymize_days: int = RETENTION_MIN_DAYS,
) -> dict:
    """
    Cleanup old conversations and anonymize user data

    Args:
        retention_days: Delete conversations older than this
        anonymize_days: Anonymize user_id for conversations older than this

    Both default to the 5-year retention floor. They used to default to 30 and 7
    — values the repository now refuses outright, so leaving them here would
    have been a signature advertising an argument that always raises.

    The repository refuses timed deletion entirely unless the operator opts in;
    this function reports that refusal as `{"success": False, "error": ...}`
    rather than crashing, so a cron reading the dict still sees the failure.

    Returns:
        Dict with cleanup statistics
    """
    db_pool = None
    try:
        db_pool = await get_db_pool()

        if not db_pool:
            log_error(logger, "Database pool unavailable for cleanup job")
            return {"success": False, "error": "Database unavailable"}

        repo = ConversationRepository(db_pool)

        # Step 1: Anonymize user data past the anonymize window
        anonymized_count = await repo.anonymize_user_data(days=anonymize_days)

        # Step 2: Delete past the retention window (refused by policy by default)
        deleted_count = await repo.cleanup_old_conversations(days=retention_days)

        log_success(
            logger,
            "Conversation cleanup completed",
            deleted_count=deleted_count,
            anonymized_count=anonymized_count,
            retention_days=retention_days,
            anonymize_days=anonymize_days,
        )

        return {
            "success": True,
            "deleted_count": deleted_count,
            "anonymized_count": anonymized_count,
            "retention_days": retention_days,
            "anonymize_days": anonymize_days,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    except Exception as e:
        log_error(logger, "Conversation cleanup job failed", error=e, exc_info=True)
        return {"success": False, "error": str(e)}

    finally:
        if db_pool:
            await db_pool.close()


async def main():
    """Main entry point for cron job"""
    logger.info("🧹 Starting conversation cleanup job...")

    # No overrides: both windows come from the retention floor. Passing 30/7
    # here — what this said until 2026-08-08 — is now refused by the repository.
    result = await cleanup_conversations()

    if result["success"]:
        logger.info(
            f"✅ Cleanup completed: {result['deleted_count']} deleted, {result['anonymized_count']} anonymized",
        )
    else:
        logger.error(f"❌ Cleanup failed: {result.get('error')}")

    return result


if __name__ == "__main__":
    asyncio.run(main())
