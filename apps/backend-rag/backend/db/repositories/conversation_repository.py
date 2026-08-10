"""
Conversation Repository
Handles all database operations for conversation persistence
"""

from datetime import datetime, timedelta, timezone

from backend.app.utils.json_utils import to_jsonb
from backend.app.utils.logging_utils import get_logger, log_error, log_success
from backend.core.retention_policy import (
    ALLOW_CLOCK_DELETE_ENV,
    RETENTION_MIN_DAYS,
    RetentionPolicyViolation,
    clock_delete_allowed,
    enforce_retention_floor,
)
from backend.db.base_repository import BaseRepository
from backend.services.common.cache import cache_invalidating

logger = get_logger(__name__)


class ConversationRepository(BaseRepository):
    """Repository for conversation persistence operations"""

    @cache_invalidating(
        [
            lambda self, session_id, *a, **k: f"zantara:conversations:{session_id}:*",
            "zantara:conversations:*",
        ]
    )
    async def save_messages(
        self,
        session_id: str,
        user_id: str,
        messages: list[dict],
        metadata: dict | None = None,
    ) -> int | None:
        """
        Save or update conversation messages for a session

        Args:
            session_id: Session identifier
            user_id: User identifier (email)
            messages: List of message dicts with role and content
            metadata: Optional metadata dict

        Returns:
            conversation_id if successful, None otherwise
        """
        try:
            # Suppressed, not fixed: SIM117 (combine the two `async with`)
            # predates this branch on origin/main and is inherited here only
            # because the staged-file lint gate is per FILE, not per line.
            # Combining them is a correct but 78-line pure re-indentation of a
            # hot path, which does not belong in a retention-policy diff.
            # (This comment must not open with the suppression keyword — ruff
            # reads that as a blanket directive on the comment's own line.)
            async with self.db_pool.acquire() as conn:  # noqa: SIM117
                async with conn.transaction():
                    # Check if conversation exists for this session
                    existing = await conn.fetchrow(
                        """
                    SELECT id, messages FROM conversations
                    WHERE session_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                        session_id,
                    )

                    if existing:
                        # Update existing conversation (append new messages)
                        conversation_id = existing["id"]
                        existing_messages = existing["messages"] or []

                        # Merge messages (avoid duplicates by checking last message)
                        merged_messages = list(existing_messages)
                        for msg in messages:
                            # Simple deduplication: only add if not identical to last message
                            if not merged_messages or merged_messages[-1] != msg:
                                merged_messages.append(msg)

                        await conn.execute(
                            """
                        UPDATE conversations
                        SET messages = $1::text::jsonb,
                            metadata = COALESCE(metadata, '{}'::jsonb) || $2::text::jsonb
                        WHERE id = $3
                        """,
                            # ::text::jsonb — the app pools register a jsonb
                            # codec (encoder=json.dumps); a param inferred as
                            # jsonb double-encodes to_jsonb()'s already-
                            # serialized string into a jsonb string scalar.
                            to_jsonb(merged_messages),
                            to_jsonb(metadata or {}),
                            conversation_id,
                        )

                        log_success(
                            logger,
                            "Updated conversation",
                            conversation_id=conversation_id,
                            session_id=session_id,
                            total_messages=len(merged_messages),
                        )
                    else:
                        # Create new conversation
                        row = await conn.fetchrow(
                            """
                        INSERT INTO conversations (user_id, session_id, messages, metadata, created_at)
                        VALUES ($1, $2, $3::text::jsonb, $4::text::jsonb, $5)
                        RETURNING id
                        """,
                            user_id,
                            session_id,
                            to_jsonb(messages),
                            to_jsonb(metadata or {}),
                            datetime.now(tz=timezone.utc),
                        )

                        conversation_id = row["id"] if row else None

                        log_success(
                            logger,
                            "Created new conversation",
                            conversation_id=conversation_id,
                            session_id=session_id,
                            messages_count=len(messages),
                        )

                    return conversation_id

        except Exception as e:
            log_error(logger, "Failed to save conversation", error=e, exc_info=True)
            return None

    async def get_messages(
        self,
        session_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        Retrieve conversation messages for a session

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return (0 = all)

        Returns:
            List of message dicts
        """
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT messages FROM conversations
                    WHERE session_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    session_id,
                )

                if row and row["messages"]:
                    messages = row["messages"]
                    if limit > 0 and len(messages) > limit:
                        # Return last N messages
                        return messages[-limit:]
                    return messages

                return []

        except Exception as e:
            log_error(logger, "Failed to retrieve messages", error=e, exc_info=True)
            return []

    @cache_invalidating(
        [
            "zantara:conversations:*",
        ]
    )
    async def cleanup_old_conversations(self, days: int = RETENTION_MIN_DAYS) -> int:
        """
        Delete conversations older than specified days

        Args:
            days: Number of days to keep (default: the 5-year retention floor)

        Returns:
            Number of conversations deleted

        Raises:
            RetentionPolicyViolation: if `days` is below the floor, or if timed
                deletion is disabled (it is, by default — see
                backend/core/retention_policy.py). This is the ONLY thing here
                that escapes: the `except Exception` below returns 0, so a
                refusal raised inside it would reach the caller as a successful
                "0 rows deleted". The guards therefore sit above the try.
        """
        enforce_retention_floor("days", days)
        if not clock_delete_allowed():
            raise RetentionPolicyViolation(
                "Clock-driven deletion of conversations is disabled by policy "
                f"('non cancellare', 2026-08-08). Set {ALLOW_CLOCK_DELETE_ENV}=1 to re-enable "
                "deliberately. Per-subject erasure (DELETE /api/conversations/clear) is a "
                "separate path and is NOT affected by this."
            )

        try:
            cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=days)

            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM conversations
                    WHERE created_at < $1
                    """,
                    cutoff_date,
                )

                # Extract count from "DELETE N" string
                deleted_count = int(result.split()[-1]) if result else 0

                log_success(
                    logger,
                    "Cleaned up old conversations",
                    deleted_count=deleted_count,
                    cutoff_days=days,
                )

                return deleted_count

        except Exception as e:
            log_error(logger, "Failed to cleanup conversations", error=e, exc_info=True)
            return 0

    @cache_invalidating(
        [
            "zantara:conversations:*",
        ]
    )
    async def anonymize_user_data(self, days: int = RETENTION_MIN_DAYS) -> int:
        """
        Anonymize user_id for conversations older than specified days

        Args:
            days: Number of days before anonymization (default: the 5-year floor)

        Returns:
            Number of conversations anonymized

        Raises:
            RetentionPolicyViolation: if `days` is below the floor. Anonymising
                at 7 days — the previous default — destroys the five-year
                reconstruction requirement within a week, which is why this is
                floored even though it is not a deletion. Raised above the try
                for the same reason as the sibling method.
        """
        enforce_retention_floor("days", days)

        try:
            cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=days)

            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE conversations
                    SET user_id = 'anonymized_' || id::text
                    WHERE created_at < $1
                    AND user_id NOT LIKE 'anonymized_%'
                    """,
                    cutoff_date,
                )

                # Extract count from "UPDATE N" string
                anonymized_count = int(result.split()[-1]) if result else 0

                log_success(
                    logger,
                    "Anonymized user data",
                    anonymized_count=anonymized_count,
                    cutoff_days=days,
                )

                return anonymized_count

        except Exception as e:
            log_error(logger, "Failed to anonymize user data", error=e, exc_info=True)
            return 0
