"""
Conversation Cleanup Job
Daily cron job to cleanup old conversations and anonymize user data
"""

import asyncio
from datetime import datetime, timezone

from backend.app.dependencies import get_database_pool_direct
from backend.app.utils.logging_utils import get_logger, log_error, log_success
from backend.db.repositories.conversation_repository import ConversationRepository

logger = get_logger(__name__)


async def cleanup_conversations(
    retention_days: int = 30,
    anonymize_days: int = 7,
) -> dict:
    """
    Cleanup old conversations and anonymize user data

    Args:
        retention_days: Delete conversations older than this (default: 30)
        anonymize_days: Anonymize user_id for conversations older than this (default: 7)

    Returns:
        Dict with cleanup statistics
    """
    db_pool = None
    try:
        db_pool = await get_database_pool_direct()

        if not db_pool:
            log_error(logger, "Database pool unavailable for cleanup job")
            return {"success": False, "error": "Database unavailable"}

        repo = ConversationRepository(db_pool)

        # Step 1: Anonymize user data for conversations older than 7 days
        anonymized_count = await repo.anonymize_user_data(days=anonymize_days)

        # Step 2: Delete conversations older than 30 days
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

    result = await cleanup_conversations(
        retention_days=30,  # Delete after 30 days
        anonymize_days=7,  # Anonymize after 7 days
    )

    if result["success"]:
        logger.info(
            f"✅ Cleanup completed: {result['deleted_count']} deleted, {result['anonymized_count']} anonymized",
        )
    else:
        logger.error(f"❌ Cleanup failed: {result.get('error')}")

    return result


if __name__ == "__main__":
    asyncio.run(main())
