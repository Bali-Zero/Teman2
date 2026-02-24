"""Conversation memory service — Redis-backed multi-turn session store.

Stores conversation history per session_id with TTL.
The `understand` node reads history to provide follow-up context.
The route in `routes.py` loads/saves history around each graph invocation.

Key format: v6:session:{session_id}
TTL: 24 hours (configurable)

Data format (JSON list):
  [
    {"role": "user", "content": "How do I set up a PT PMA?"},
    {"role": "assistant", "content": "A PT PMA requires..."},
    ...
  ]

Max turns kept in memory: 10 (5 exchanges) — older turns are dropped
to avoid token overflow in LLM context windows.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()

SESSION_PREFIX = "v6:session:"
SESSION_TTL_SECONDS = 86_400  # 24 hours
MAX_HISTORY_TURNS = 10  # 5 user + 5 assistant messages


class ConversationMemory:
    """Redis-backed multi-turn conversation memory.

    Usage:
        memory = ConversationMemory(redis_url=settings.redis_url)

        # Load history before graph invocation
        history = await memory.load(session_id)

        # Save new turns after graph completes
        await memory.append(session_id, role="user", content=query)
        await memory.append(session_id, role="assistant", content=answer)
    """

    def __init__(self, redis_url: str = "", ttl_seconds: int = SESSION_TTL_SECONDS) -> None:
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self._client: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
        return self._client

    async def load(self, session_id: str) -> list[dict[str, Any]]:
        """Load conversation history for a session.

        Returns empty list if session not found or Redis unavailable.
        """
        if not session_id:
            return []

        try:
            client = await self._get_client()
            key = self._make_key(session_id)
            raw = await client.get(key)
            if raw is None:
                return []

            history: list[dict[str, Any]] = json.loads(raw)
            logger.debug(
                "session_loaded",
                session_id=session_id,
                turns=len(history),
            )
            return history

        except Exception as e:
            logger.warning("session_load_error", session_id=session_id, error=str(e))
            return []

    async def append(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Append a single turn to the session history.

        Trims to MAX_HISTORY_TURNS (keeping most recent).
        Resets TTL on every write.
        """
        if not session_id or not content:
            return

        try:
            client = await self._get_client()
            key = self._make_key(session_id)

            # Load existing history
            raw = await client.get(key)
            history: list[dict[str, Any]] = json.loads(raw) if raw else []

            # Append new turn
            history.append({"role": role, "content": content})

            # Trim to max turns (drop oldest first)
            if len(history) > MAX_HISTORY_TURNS:
                history = history[-MAX_HISTORY_TURNS:]

            await client.setex(key, self.ttl_seconds, json.dumps(history))
            logger.debug(
                "session_appended",
                session_id=session_id,
                role=role,
                total_turns=len(history),
            )

        except Exception as e:
            logger.warning("session_append_error", session_id=session_id, error=str(e))

    async def save(
        self,
        session_id: str,
        history: list[dict[str, Any]],
    ) -> None:
        """Replace the full session history (used for bulk updates)."""
        if not session_id:
            return

        try:
            client = await self._get_client()
            key = self._make_key(session_id)
            trimmed = history[-MAX_HISTORY_TURNS:]
            await client.setex(key, self.ttl_seconds, json.dumps(trimmed))
        except Exception as e:
            logger.warning("session_save_error", session_id=session_id, error=str(e))

    async def clear(self, session_id: str) -> None:
        """Delete all history for a session (new chat)."""
        if not session_id:
            return

        try:
            client = await self._get_client()
            key = self._make_key(session_id)
            await client.delete(key)
            logger.debug("session_cleared", session_id=session_id)
        except Exception as e:
            logger.warning("session_clear_error", session_id=session_id, error=str(e))

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _make_key(session_id: str) -> str:
        return f"{SESSION_PREFIX}{session_id}"
