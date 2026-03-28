"""
Conversation Engine - Channel-Agnostic Processing

Handles conversation flow, context management, and orchestrator integration.
This is the bridge between channel adapters and the core RAG pipeline.

Author: Claude Sonnet
Date: 2026-02-10
"""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from backend.channels.base import ChannelMessage, ChannelResponse
from backend.services.rag.agentic.orchestrator import AgenticRAGOrchestrator

logger = logging.getLogger(__name__)


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
        self, message: ChannelMessage, channel_config: dict[str, Any]
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
            f"(user={message.user_id}, session={message.session_id})"
        )

        try:
            # 1. Load conversation context
            context = await self._load_context(message.session_id)

            # 2. Build conversation history
            conversation_history = context.get("history", [])

            # 3. Stream through orchestrator
            async for event in self.orchestrator.stream_query(
                query=message.text,
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
                f"(channel={message.channel}, user={message.user_id})"
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
                text="", metadata={"event_type": "thinking", "data": event.get("data")}
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
                text="", metadata={"event_type": "observation", "data": event.get("data")}
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
        """
        Load conversation context (history, user state).

        Args:
            session_id: Session identifier

        Returns:
            Context dictionary with history and state

        Note:
            In Phase 1, this is a stub. In Phase 4, integrate with:
            - PostgreSQL conversation_history table
            - Redis session cache
            - Memory orchestrator
        """
        # TODO Phase 4: Implement context loading from database
        return {"history": [], "user_state": {}}

    async def _save_context(self, session_id: str, context: dict[str, Any]) -> None:
        """
        Save conversation context.

        Args:
            session_id: Session identifier
            context: Context dictionary to save

        Note:
            In Phase 1, this is a stub. In Phase 4, integrate with:
            - PostgreSQL conversation_history table
            - Redis session cache
        """
        # TODO Phase 4: Implement context saving to database
        pass
