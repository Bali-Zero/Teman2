"""
Conversation Engine - Channel-Agnostic Processing

Handles conversation flow, context management, and orchestrator integration.
This is the bridge between channel adapters and the core RAG pipeline.

Author: Claude Sonnet
Date: 2026-02-10
"""

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from backend.channels.base import ChannelMessage, ChannelResponse
from backend.services.rag.agentic.orchestrator import AgenticRAGOrchestrator

logger = logging.getLogger(__name__)

# Session context TTL: 1 hour in Redis
_SESSION_CONTEXT_TTL = 3600
# Max conversation history entries to load
_MAX_HISTORY_ENTRIES = 20


class ConversationEngine:
    """
    Channel-agnostic conversation processing engine.

    Responsibilities:
    - Load conversation context (history, user state)
    - Process messages through RAG orchestrator
    - Convert orchestrator events → ChannelResponse
    - Save conversation state

    This is the central component that allows the same business logic
    to work across all channels (Telegram, WhatsApp, Web, etc.).
    """

    def __init__(self, orchestrator: AgenticRAGOrchestrator) -> None:
        """
        Initialize conversation engine.

        Args:
            orchestrator: Initialized AgenticRAGOrchestrator
        """
        self.orchestrator = orchestrator
        logger.info("✅ ConversationEngine initialized")

    async def process_message(
        self, message: ChannelMessage, channel_config: dict[str, Any],
    ) -> AsyncIterator[ChannelResponse]:
        """
        Process a message through the RAG pipeline.

        This is the main entry point for all conversations, regardless of channel.

        Args:
            message: Normalized message from any channel
            channel_config: Channel-specific configuration (timeout, features, etc.)

        Yields:
            ChannelResponse objects containing text, sources, metadata

        Example:
            async for response in engine.process_message(msg, config):
                # response contains normalized data
                # Channel adapter will format it for the platform
                await channel_adapter.send_response(chat_id, response)
        """
        start_time = time.time()
        logger.info(
            f"🔄 Processing message from {message.channel} "
            f"(user={message.user_id}, session={message.session_id})",
        )

        try:
            # 1. Load conversation context
            context = await self._load_context(message.session_id)

            # 2. Build conversation history
            conversation_history = context.get("history", [])

            # 2.3. Cross-channel memory: inject thread history from other channels
            thread_id = message.metadata.get("thread_id")
            if thread_id:
                cross_channel_context = await self._load_cross_channel_context(thread_id)
                if cross_channel_context:
                    conversation_history = cross_channel_context + conversation_history

            # 2.5. Agent Mesh: inject team member context into conversation
            query_text = message.text
            agent_ctx = message.metadata.get("agent_mesh")
            if agent_ctx:
                agent_name = message.metadata.get("agent_name", "Team Member")
                agent_role = message.metadata.get("agent_role_display", "")
                agent_system = message.metadata.get("agent_system_context", "")
                agent_scope = message.metadata.get("agent_client_scope", "all")
                agent_email = message.metadata.get("agent_email", "")

                # Prepend agent context so the LLM knows who it's talking to
                scope_instruction = ""
                if agent_scope == "assigned":
                    scope_instruction = (
                        f" When querying client data, filter by assigned_to='{agent_email}'. "
                        f"Only show clients assigned to {agent_name}."
                    )

                context_prefix = (
                    f"[AGENT CONTEXT] Speaking with {agent_name} ({agent_role}). "
                    f"{agent_system}{scope_instruction}\n\n"
                )
                query_text = context_prefix + message.text

                logger.info(
                    f"🤖 Agent Mesh context injected for {agent_name} ({agent_role})",
                )

            # 3. Stream through orchestrator
            async for event in self.orchestrator.stream_query(
                query=query_text,
                user_id=message.user_id,
                session_id=message.session_id,
                conversation_history=conversation_history,
                images=message.media,
            ):
                # Convert orchestrator events → ChannelResponse
                response = self._convert_event_to_response(event)
                if response:
                    yield response

            # 4. Save updated context
            duration = time.time() - start_time
            await self._save_context(message.session_id, context)

            logger.info(
                f"✅ Message processed in {duration:.2f}s "
                f"(channel={message.channel}, user={message.user_id})",
            )

        except Exception as e:
            logger.error(f"❌ Error processing message from {message.channel}: {e}", exc_info=True)
            # Yield error response
            yield ChannelResponse(
                text="Mi dispiace, si è verificato un errore. Riprova tra poco.",
                metadata={"event_type": "error", "error": str(e)},
            )

    def _convert_event_to_response(self, event: dict) -> ChannelResponse | None:
        """
        Convert orchestrator event → ChannelResponse.

        Orchestrator emits various event types (token, thinking, tool_call, sources, etc.).
        We normalize them into ChannelResponse objects.

        Args:
            event: Event from orchestrator.stream_query()

        Returns:
            ChannelResponse or None if event should be skipped
        """
        event_type = event.get("type")

        # Token event: streaming text
        if event_type == "token":
            return ChannelResponse(text=event.get("data", ""), metadata={"event_type": "token"})

        # Thinking event: LLM reasoning step
        elif event_type == "thinking":
            return ChannelResponse(
                text="", metadata={"event_type": "thinking", "data": event.get("data")},
            )

        # Tool call event: agent executing a tool
        elif event_type == "tool_call":
            return ChannelResponse(
                text="",
                metadata={
                    "event_type": "tool_call",
                    "tool_name": event.get("data", {}).get("tool_name"),
                    "arguments": event.get("data", {}).get("arguments"),
                },
            )

        # Observation event: tool execution result
        elif event_type == "observation":
            return ChannelResponse(
                text="", metadata={"event_type": "observation", "data": event.get("data")},
            )

        # Sources event: citations/references
        elif event_type == "sources":
            return ChannelResponse(
                text="",
                sources=event.get("data", []),
                metadata={"event_type": "sources"},
            )

        # Workflow event: suggested workflow from LangGraph KG
        elif event_type == "workflow":
            return ChannelResponse(
                text="",
                workflow=event.get("data"),
                metadata={"event_type": "workflow"},
            )

        # Final answer event: complete response
        elif event_type == "answer":
            return ChannelResponse(
                text=event.get("data", {}).get("text", ""),
                sources=event.get("data", {}).get("sources"),
                workflow=event.get("data", {}).get("workflow"),
                metadata={"event_type": "answer"},
            )

        # Unknown event type - skip
        else:
            logger.debug(f"Skipping unknown event type: {event_type}")
            return None

    async def _load_context(self, session_id: str) -> dict[str, Any]:
        """Load conversation context from Redis cache, falling back to PostgreSQL.

        Lookup order:
        1. Redis session cache (fast, TTL=1h)
        2. PostgreSQL conversation_messages table (persistent)
        3. Empty context (new session)

        Args:
            session_id: Session identifier.

        Returns:
            Context dict with 'history' (list of role/content dicts) and 'user_state'.
        """
        empty_context: dict[str, Any] = {"history": [], "user_state": {}}

        if not session_id:
            return empty_context

        cache_key = f"zantara:session_ctx:{session_id}"

        # Strategy 1: Redis cache (sub-ms)
        try:
            from backend.core.cache import get_cache_service

            cache = get_cache_service()
            cached = await cache.get(cache_key)
            if cached and isinstance(cached, dict):
                logger.debug(f"Session context cache hit for {session_id}")
                return cached
        except Exception as e:
            logger.debug(f"Redis context load skipped: {e}")

        # Strategy 2: PostgreSQL conversation_messages table
        db_pool = getattr(self, "_db_pool", None)
        if db_pool:
            try:
                rows = await db_pool.fetch(
                    """
                    SELECT direction, content
                    FROM conversation_messages
                    WHERE metadata->>'session_id' = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    session_id,
                    _MAX_HISTORY_ENTRIES,
                )
                if rows:
                    history = []
                    for row in reversed(rows):  # Chronological order
                        role = "user" if row["direction"] == "inbound" else "assistant"
                        history.append({"role": role, "content": row["content"]})

                    context = {"history": history, "user_state": {}}

                    # Warm the cache for next time
                    try:
                        cache = get_cache_service()
                        await cache.set(cache_key, context, ttl=_SESSION_CONTEXT_TTL)
                    except Exception:
                        pass

                    logger.debug(
                        f"Loaded {len(history)} messages from DB for session {session_id}",
                    )
                    return context
            except Exception as e:
                logger.debug(f"DB context load failed (non-fatal): {e}")

        return empty_context

    async def _load_cross_channel_context(self, thread_id: str) -> list[dict[str, str]]:
        """Load recent messages from the same thread across all channels.

        Converts cross-channel messages into conversation history format
        so the LLM can see what the client said on other channels.

        Args:
            thread_id: UUID of the conversation thread.

        Returns:
            List of ``{"role": "...", "content": "..."}`` dicts, or empty.
        """
        try:
            from uuid import UUID

            from backend.services.communication.thread_manager import ThreadManager

            # Get db_pool from app state (set during lifespan)
            db_pool = getattr(self, "_db_pool", None)
            if not db_pool:
                return []

            tm = ThreadManager(db_pool)
            summary = await tm.get_thread_summary(UUID(thread_id), max_messages=8)
            if not summary:
                return []

            return [{
                "role": "system",
                "content": (
                    f"[Cross-Channel History] This client has an ongoing conversation "
                    f"across multiple channels. Recent messages:\n{summary}"
                ),
            }]
        except Exception as e:
            logger.debug(f"Cross-channel context load failed (non-fatal): {e}")
            return []

    async def _save_context(self, session_id: str, context: dict[str, Any]) -> None:
        """Save conversation context to Redis cache (with 1h TTL).

        PostgreSQL persistence of individual messages is handled by
        ChannelRouter._persist_message() at the channel layer.
        This method only caches the assembled context for fast reload.

        Args:
            session_id: Session identifier.
            context: Context dictionary with history and user_state.
        """
        if not session_id or not context:
            return

        cache_key = f"zantara:session_ctx:{session_id}"

        try:
            from backend.core.cache import get_cache_service

            cache = get_cache_service()
            await cache.set(cache_key, context, ttl=_SESSION_CONTEXT_TTL)
            logger.debug(f"Saved session context to cache for {session_id}")
        except Exception as e:
            logger.debug(f"Failed to cache session context (non-fatal): {e}")
