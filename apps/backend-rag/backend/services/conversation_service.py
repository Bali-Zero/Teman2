from datetime import datetime
from typing import Any

import asyncpg

from app.utils.logging_utils import get_logger, log_success
from services.memory_fallback import get_memory_cache

logger = get_logger(__name__)


class ConversationService:
    """
    Service for managing conversation persistence and retrieval.
    Handles saving to PostgreSQL, Memory Cache fallback, and triggering Auto-CRM.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self._auto_crm_service = None

    def _get_auto_crm(self):
        """Lazy load Auto-CRM service"""
        if self._auto_crm_service is None:
            try:
                from services.auto_crm_service import get_auto_crm_service

                self._auto_crm_service = get_auto_crm_service()
            except ImportError:
                self._auto_crm_service = False
            except Exception as e:
                logger.warning(f"Auto-CRM service not available: {e}")
                self._auto_crm_service = False
        return self._auto_crm_service if self._auto_crm_service else None

    async def save_conversation(
        self,
        user_email: str,
        messages: list[dict[str, Any]],
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Save conversation messages to PostgreSQL and Memory Cache.
        Triggers Auto-CRM if successful.
        """
        if not session_id:
            session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        metadata = metadata or {}

        try:
            mem_cache = get_memory_cache()
            for msg in messages:
                mem_cache.add_message(
                    session_id, msg.get("role", "unknown"), msg.get("content", "")
                )
            logger.info(
                f"✅ Saved {len(messages)} messages to memory cache for session {session_id}"
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to save to memory cache: {e}")

        conversation_id = 0
        db_success = False

        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO conversations (user_id, session_id, messages, metadata, created_at)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING id
                        """,
                        user_email,
                        session_id,
                        messages,
                        metadata,
                        datetime.now(),
                    )

                    if row:
                        conversation_id = row["id"]
                        db_success = True
                        log_success(
                            logger,
                            "Saved conversation to DB",
                            conversation_id=conversation_id,
                            user_email=user_email,
                            messages_count=len(messages),
                        )
            else:
                logger.warning("⚠️ DB Pool unavailable, skipping DB save")

        except Exception as e:
            logger.error(f"❌ DB Save failed: {e}")
            if not db_success:
                logger.info("⚠️ Continuing with memory-only persistence")

        crm_result = {}
        if db_success:
            auto_crm = self._get_auto_crm()
            if auto_crm and len(messages) > 0:
                try:
                    crm_result = await auto_crm.process_conversation(
                        conversation_id=conversation_id,
                        messages=messages,
                        user_email=user_email,
                        team_member=metadata.get("team_member", "system"),
                        db_pool=self.db_pool,
                    )
                except Exception as crm_error:
                    logger.error(f"Auto-CRM processing error: {crm_error}")
                    crm_result = {"processed": False, "error": str(crm_error)}
            else:
                crm_result = {"processed": False, "reason": "auto-crm not available"}

        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages_saved": len(messages),
            "user_email": user_email,
            "crm": crm_result,
            "persistence_mode": "db" if db_success else "memory_fallback",
            "session_id": session_id,
        }

    async def get_history(
        self, user_email: str, limit: int = 20, session_id: str | None = None
    ) -> dict[str, Any]:
        """
        Retrieve conversation history from DB or Memory Cache.
        """
        messages = []
        source = "db"

        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    if session_id:
                        row = await conn.fetchrow(
                            """
                            SELECT messages FROM conversations
                            WHERE user_id = $1 AND session_id = $2
                            ORDER BY created_at DESC LIMIT 1
                            """,
                            user_email,
                            session_id,
                        )
                    else:
                        row = await conn.fetchrow(
                            """
                            SELECT messages FROM conversations
                            WHERE user_id = $1
                            ORDER BY created_at DESC LIMIT 1
                            """,
                            user_email,
                        )

                    if row and row["messages"]:
                        messages = row["messages"]
                        if isinstance(messages, str):
                            import json

                            messages = json.loads(messages)
            except Exception as e:
                logger.error(f"Failed to fetch history from DB: {e}")
                source = "fallback_failed"

        if not messages:
            try:
                mem_cache = get_memory_cache()
                if session_id:
                    cached = mem_cache.get_conversation(session_id)
                    if cached:
                        messages = cached
                        source = "memory_cache"
            except Exception as e:
                logger.warning(f"Failed to fetch history from memory cache: {e}")

        return {
            "messages": messages[-limit:] if limit else messages,
            "source": source,
            "total": len(messages),
        }
