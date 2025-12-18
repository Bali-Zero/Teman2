"""
Session Service - Redis-based conversation history storage for ZANTARA

Eliminates URL length constraints by storing conversation history in Redis
and passing only session_id in requests. Supports 50+ message conversations.

Author: ZANTARA AI Code (Bali Zero Team)
Date: November 5, 2025
"""

import json
import logging
import uuid
from datetime import timedelta

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SessionService:
    """
    Manages conversation sessions in Redis for extended context support.

    Features:
    - Create/Read/Update/Delete sessions
    - 24-hour TTL with auto-extension on activity
    - JSON serialization of conversation history
    - Automatic cleanup of expired sessions
    """

    def __init__(self, redis_url: str, ttl_hours: int = 24):
        """
        Initialize SessionService

        Args:
            redis_url: Redis connection URL (e.g., redis://host:port)
            ttl_hours: Session expiry time in hours (default: 24)
        """
        try:
            self.redis = redis.from_url(
                redis_url,
                decode_responses=True,
                encoding="utf-8",
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self.ttl = timedelta(hours=ttl_hours)
            logger.info(f"✅ SessionService initialized with {ttl_hours}h TTL")
        except Exception as e:
            logger.error(f"❌ Failed to initialize SessionService: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy"""
        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"❌ Redis health check failed: {e}")
            return False

    async def create_session(self) -> str:
        """
        Create a new conversation session

        Returns:
            str: UUID session ID
        """
        session_id = str(uuid.uuid4())
        try:
            # Initialize with empty history
            await self.redis.setex(f"session:{session_id}", self.ttl, json.dumps([]))
            logger.info(f"🆕 Created session: {session_id}")
            return session_id
        except Exception as e:
            logger.error(f"❌ Failed to create session: {e}")
            raise

    async def get_history(self, session_id: str) -> list[dict] | None:
        """
        Get conversation history for a session

        Args:
            session_id: Session UUID

        Returns:
            List[Dict] or None if session not found/expired
        """
        try:
            data = await self.redis.get(f"session:{session_id}")
            if not data:
                logger.warning(f"⚠️ Session not found or expired: {session_id}")
                return None

            history = json.loads(data)
            logger.info(f"📚 Retrieved {len(history)} messages from session {session_id}")
            return history
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse session data: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get session: {e}")
            return None

    async def update_history(self, session_id: str, history: list[dict]) -> bool:
        """
        Update conversation history for a session

        Args:
            session_id: Session UUID
            history: List of conversation messages [{role, content}, ...]

        Returns:
            bool: True if successful
        """
        try:
            # Validate history format
            if not isinstance(history, list):
                logger.error(f"❌ Invalid history format: expected list, got {type(history)}")
                return False

            # Serialize and save
            await self.redis.setex(f"session:{session_id}", self.ttl, json.dumps(history))
            logger.info(f"💾 Updated session {session_id} with {len(history)} messages")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update session: {e}")
            return False

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session

        Args:
            session_id: Session UUID

        Returns:
            bool: True if session existed and was deleted
        """
        try:
            deleted = await self.redis.delete(f"session:{session_id}")
            if deleted > 0:
                logger.info(f"🗑️ Deleted session: {session_id}")
                return True
            else:
                logger.warning(f"⚠️ Session not found for deletion: {session_id}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to delete session: {e}")
            return False

    async def extend_ttl(self, session_id: str) -> bool:
        """
        Extend session TTL (reset to full TTL duration)

        Automatically called when a session is accessed to keep
        active conversations alive.

        Args:
            session_id: Session UUID

        Returns:
            bool: True if TTL was extended
        """
        try:
            extended = await self.redis.expire(f"session:{session_id}", self.ttl)
            if extended:
                logger.debug(f"⏰ Extended TTL for session {session_id}")
            return extended
        except Exception as e:
            logger.error(f"❌ Failed to extend TTL: {e}")
            return False

    async def get_session_info(self, session_id: str) -> dict | None:
        """
        Get session metadata (TTL, message count, etc.)

        Args:
            session_id: Session UUID

        Returns:
            Dict with session info or None if not found
        """
        try:
            key = f"session:{session_id}"

            # Get TTL
            ttl_seconds = await self.redis.ttl(key)
            if ttl_seconds == -2:  # Key doesn't exist
                return None

            # Get history
            data = await self.redis.get(key)
            if not data:
                return None

            history = json.loads(data)

            return {
                "session_id": session_id,
                "message_count": len(history),
                "ttl_seconds": ttl_seconds,
                "ttl_hours": round(ttl_seconds / 3600, 2),
            }
        except Exception as e:
            logger.error(f"❌ Failed to get session info: {e}")
            return None

    async def cleanup_expired_sessions(self) -> int:
        """
        Cleanup expired sessions (Redis handles this automatically via TTL)
        This is a no-op but kept for API completeness

        Returns:
            int: Number of sessions cleaned (always 0, Redis auto-cleans)
        """
        logger.info("ℹ️ Session cleanup is handled automatically by Redis TTL")
        return 0

    async def get_analytics(self) -> dict:
        """
        Get analytics about all sessions in Redis

        Returns:
            Dict with:
            - total_sessions: total number of sessions
            - active_sessions: sessions with >0 messages
            - avg_messages_per_session: average message count
            - top_session: session with most messages
            - sessions_by_range: distribution by message count
        """
        try:
            # Get all session keys
            keys = []
            async for key in self.redis.scan_iter("session:*"):
                keys.append(key)

            total_sessions = len(keys)
            if total_sessions == 0:
                return {
                    "total_sessions": 0,
                    "active_sessions": 0,
                    "avg_messages_per_session": 0,
                    "top_session": None,
                    "sessions_by_range": {},
                }

            # Analyze each session
            message_counts = []
            top_session = {"id": None, "messages": 0}
            ranges = {"0-10": 0, "11-20": 0, "21-50": 0, "51+": 0}

            for key in keys:
                session_id = key.replace("session:", "")
                data = await self.redis.get(key)
                if data:
                    try:
                        history = json.loads(data)
                        msg_count = len(history)
                        message_counts.append(msg_count)

                        # Track top session
                        if msg_count > top_session["messages"]:
                            top_session = {"id": session_id, "messages": msg_count}

                        # Categorize by range
                        if msg_count <= 10:
                            ranges["0-10"] += 1
                        elif msg_count <= 20:
                            ranges["11-20"] += 1
                        elif msg_count <= 50:
                            ranges["21-50"] += 1
                        else:
                            ranges["51+"] += 1
                    except json.JSONDecodeError:
                        pass

            active_sessions = len([c for c in message_counts if c > 0])
            avg_messages = sum(message_counts) / len(message_counts) if message_counts else 0

            analytics = {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "avg_messages_per_session": round(avg_messages, 2),
                "top_session": top_session if top_session["id"] else None,
                "sessions_by_range": ranges,
            }

            logger.info(f"📊 Analytics: {total_sessions} sessions, avg {avg_messages:.1f} messages")
            return analytics

        except Exception as e:
            logger.error(f"❌ Failed to get analytics: {e}")
            return {
                "error": str(e),
                "total_sessions": 0,
                "active_sessions": 0,
                "avg_messages_per_session": 0,
                "top_session": None,
                "sessions_by_range": {},
            }

    async def update_history_with_ttl(
        self, session_id: str, history: list[dict], ttl_hours: int | None = None
    ) -> bool:
        """
        Update conversation history with custom TTL

        Args:
            session_id: Session UUID
            history: List of conversation messages
            ttl_hours: Custom TTL in hours (default: use service default)

        Returns:
            bool: True if successful
        """
        try:
            if not isinstance(history, list):
                logger.error(f"❌ Invalid history format: expected list, got {type(history)}")
                return False

            # Use custom TTL or default
            ttl = timedelta(hours=ttl_hours) if ttl_hours else self.ttl

            await self.redis.setex(f"session:{session_id}", ttl, json.dumps(history))
            logger.info(
                f"💾 Updated session {session_id} with {len(history)} messages (TTL: {ttl.total_seconds() / 3600:.1f}h)"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update session with custom TTL: {e}")
            return False

    async def extend_ttl_custom(self, session_id: str, ttl_hours: int) -> bool:
        """
        Extend session TTL to custom duration

        Args:
            session_id: Session UUID
            ttl_hours: New TTL in hours

        Returns:
            bool: True if TTL was extended
        """
        try:
            ttl = timedelta(hours=ttl_hours)
            extended = await self.redis.expire(f"session:{session_id}", ttl)
            if extended:
                logger.info(f"⏰ Extended TTL for session {session_id} to {ttl_hours}h")
            return extended
        except Exception as e:
            logger.error(f"❌ Failed to extend TTL: {e}")
            return False

    async def export_session(self, session_id: str, format: str = "json") -> str | None:
        """
        Export session conversation in specified format

        Args:
            session_id: Session UUID
            format: Export format ("json" or "markdown")

        Returns:
            str: Formatted conversation or None if session not found
        """
        try:
            history = await self.get_history(session_id)
            if not history:
                return None

            if format == "markdown":
                # Format as Markdown
                lines = [f"# Conversation Export - {session_id}\n"]
                lines.append(f"**Messages:** {len(history)}\n")
                lines.append("---\n")

                for i, msg in enumerate(history, 1):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")

                    if role == "user":
                        lines.append(f"## 👤 User (Message {i})\n")
                    else:
                        lines.append(f"## 🤖 Assistant (Message {i})\n")

                    lines.append(f"{content}\n\n")

                return "".join(lines)

            else:  # JSON format (default)
                return json.dumps(
                    {
                        "session_id": session_id,
                        "message_count": len(history),
                        "conversation": history,
                    },
                    indent=2,
                    ensure_ascii=False,
                )

        except Exception as e:
            logger.error(f"❌ Failed to export session: {e}")
            return None

    async def close(self):
        """Close Redis connection"""
        try:
            await self.redis.close()
            logger.info("🔌 SessionService connection closed")
        except Exception as e:
            logger.error(f"❌ Failed to close SessionService: {e}")


# Example usage
async def main():
    """Example usage of SessionService"""
    import logging

    logger = logging.getLogger(__name__)

    # Use settings for Redis URL instead of hardcoding
    from app.core.config import settings

    redis_url = getattr(settings, "redis_url", "redis://localhost:6379")
    service = SessionService(redis_url)

    # Create session
    session_id = await service.create_session()
    logger.info(f"Created session: {session_id}")

    # Update history
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help you?"},
    ]
    await service.update_history(session_id, history)

    # Retrieve history
    retrieved = await service.get_history(session_id)
    logger.info(f"Retrieved: {retrieved}")

    # Get session info
    info = await service.get_session_info(session_id)
    logger.info(f"Session info: {info}")

    # Clean up
    await service.delete_session(session_id)
    await service.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
