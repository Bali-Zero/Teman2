"""
Channel Router - Unified Message Routing

Central routing logic that dispatches messages to appropriate channel adapters.
This is the entry point for all incoming messages, regardless of source.

Author: Claude Sonnet
Date: 2026-02-10
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.channels.base import ChannelMessage
    from backend.conversation.engine import ConversationEngine
    from backend.services.communication.thread_manager import ThreadManager

from backend.channels.base import BaseChannel
from backend.channels.optimizations import message_deduplicator

logger = logging.getLogger(__name__)


class ChannelRouter:
    """
    Routes messages to appropriate channel adapter.

    This is the central hub that:
    1. Registers channel adapters (Telegram, WhatsApp, Web, etc.)
    2. Routes incoming messages to the correct adapter
    3. Normalizes messages → processes through ConversationEngine
    4. Returns responses via the adapter

    Usage:
        router = ChannelRouter(conversation_engine)
        await router.route_message("telegram", telegram_webhook_event)
        await router.route_message("whatsapp", whatsapp_webhook_event)
        await router.route_message("web", web_api_request)
    """

    def __init__(self, conversation_engine: ConversationEngine) -> None:
        """
        Initialize channel router.

        Args:
            conversation_engine: Initialized ConversationEngine
        """
        self.conversation_engine = conversation_engine
        self.adapters: dict[str, BaseChannel] = {}
        self._thread_manager: ThreadManager | None = None
        self._identity_resolver: Any = None
        logger.info("✅ ChannelRouter initialized")

    def register_adapter(self, channel_name: str, adapter: BaseChannel) -> None:
        """
        Register a channel adapter.

        Args:
            channel_name: Channel identifier (e.g., "telegram", "whatsapp")
            adapter: Initialized channel adapter

        Example:
            telegram_adapter = TelegramChannelAdapter(config)
            router.register_adapter("telegram", telegram_adapter)
        """
        self.adapters[channel_name] = adapter
        logger.info(f"✅ Registered channel adapter: {channel_name}")

    async def route_message(self, channel: str, raw_event: dict) -> None:
        """
        Main routing logic.

        Steps:
        1. Get channel adapter
        2. Normalize message (platform-specific → ChannelMessage)
        3. Send status update (typing indicator)
        4. Process through ConversationEngine
        5. Stream response via adapter

        Args:
            channel: Channel name (e.g., "telegram", "whatsapp", "web")
            raw_event: Raw event from platform webhook/API

        Raises:
            ValueError: If channel is not registered

        Example:
            # Telegram webhook
            await router.route_message("telegram", telegram_update)

            # WhatsApp webhook
            await router.route_message("whatsapp", whatsapp_event)

            # Web API request
            await router.route_message("web", web_request_dict)
        """
        # 1. Get channel adapter
        adapter = self.adapters.get(channel)
        if not adapter:
            raise ValueError(
                f"Channel '{channel}' not registered. "
                f"Available channels: {list(self.adapters.keys())}",
            )

        logger.info(f"🔀 Routing message from {channel}")

        try:
            # 2. Normalize incoming message
            message = await adapter.receive_message(raw_event)
            if message is None:
                logger.debug(f"Adapter returned None (echo/skip) for {channel}")
                return

            logger.info(
                f"📨 Received message from {message.channel} "
                f"(user={message.user_id}, text_length={len(message.text)})",
            )

            # 2.5 Deduplication check BEFORE persist (prevents duplicate DB rows)
            if message_deduplicator and await message_deduplicator.is_duplicate(
                channel, message.user_id, message.text,
            ):
                logger.warning(
                    f"🔁 Duplicate message dropped: channel={channel}, user={message.user_id}",
                )
                return

            # 3. Persist inbound message to conversation history (UU PDP: audit trail)
            await self._persist_message(
                channel=channel,
                direction="inbound",
                sender_id=message.user_id,
                content=message.text,
                metadata=message.metadata,
            )

            # 3.5 Omnichannel: resolve identity, classify, thread
            await self._enrich_with_routing(message, channel)

            # 4. Extract channel-specific ID (chat_id, phone_number, etc.)
            channel_id = self._extract_channel_id(message.metadata)

            # 5. Send immediate status update (typing indicator)
            await adapter.send_status_update(channel_id, "processing")

            # 6. Build channel config
            channel_config = {
                "timeout": adapter.timeout,
                "update_interval": adapter.update_interval,
                "supports_markdown": adapter.supports_markdown,
                "supports_media": adapter.supports_media,
                "max_message_length": adapter.max_message_length,
            }

            # 7. Process through conversation engine
            response_stream = self.conversation_engine.process_message(
                message=message, channel_config=channel_config,
            )

            # 8. Stream response via adapter
            await adapter.stream_response(channel_id, response_stream)

            logger.info(f"✅ Successfully routed and processed message from {channel}")

        except Exception as e:
            logger.error(f"❌ Error routing message from {channel}: {e}", exc_info=True)
            raise

    def _extract_channel_id(self, metadata: dict[str, Any]) -> str:
        """
        Extract channel-specific identifier from metadata.

        Different channels use different identifiers:
        - Telegram: chat_id
        - WhatsApp: phone_number
        - Instagram: thread_id
        - X/Twitter: conversation_id
        - Web: not used (SSE connection)

        Args:
            metadata: Message metadata

        Returns:
            Channel-specific identifier string
        """
        # Telegram
        if "chat_id" in metadata:
            return str(metadata["chat_id"])

        # WhatsApp (adapter sets "phone", some legacy paths use "phone_number")
        if "phone" in metadata:
            return metadata["phone"]
        if "phone_number" in metadata:
            return metadata["phone_number"]

        # Instagram
        if "thread_id" in metadata:
            return metadata["thread_id"]

        # X/Twitter
        if "conversation_id" in metadata:
            return metadata["conversation_id"]

        # Web (not used for routing)
        return ""

    def get_available_channels(self) -> list[str]:
        """
        Get list of registered channel names.

        Returns:
            List of channel names (e.g., ["telegram", "whatsapp", "web"])
        """
        return list(self.adapters.keys())

    async def _persist_message(
        self,
        channel: str,
        direction: str,
        sender_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Persist message to conversation_messages table for cross-channel history.

        Non-blocking: failures are logged but don't break the message flow.
        """
        try:
            db_pool = getattr(self, "_db_pool", None)
            if db_pool is None:
                return  # DB not available, skip silently

            # Resolve client_id from sender metadata if available
            client_id = (metadata or {}).get("client_id")

            await db_pool.execute(
                """
                INSERT INTO conversation_messages (client_id, channel, direction, sender_id, content, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                client_id,
                channel,
                direction,
                sender_id,
                content[:10000],  # Limit content size
                json.dumps(metadata or {}),
            )
        except Exception as e:
            logger.debug(f"[PERSIST] Could not save message: {e}")

    async def _enrich_with_routing(self, message: ChannelMessage, channel: str) -> None:
        """Resolve client identity, classify intent, and create/join thread.

        Enriches ``message.metadata`` with ``client_id``, ``thread_id``,
        ``intent``, ``priority``, and ``is_vip`` for downstream consumption.
        Failures are non-blocking — the message still routes to the engine.
        """
        db_pool = getattr(self, "_db_pool", None)
        if db_pool is None:
            return

        try:
            # 1. Resolve client identity
            client_id: int | None = message.metadata.get("client_id")
            if not client_id:
                client_id = await self._resolve_client_id(message, db_pool)
                if client_id:
                    message.metadata["client_id"] = client_id

            # 2. Classify intent and score priority
            from backend.services.communication import routing_engine

            decision = await routing_engine.route_message(
                text=message.text,
                client_id=client_id,
                db_pool=db_pool,
                channel=channel,
            )
            message.metadata["intent"] = decision.intent.value
            message.metadata["priority"] = decision.priority.value
            message.metadata["is_vip"] = decision.is_vip

            # 3. Thread management
            if self._thread_manager is None:
                from backend.services.communication.thread_manager import ThreadManager
                self._thread_manager = ThreadManager(db_pool)

            thread_id = await self._thread_manager.get_or_create_thread(
                client_id=client_id,
                channel=channel,
                sender_id=message.user_id,
                subject=message.text[:100] if message.text else None,
            )
            message.metadata["thread_id"] = str(thread_id)

            # Update thread with intent/priority
            from backend.services.communication.models import Priority
            await self._thread_manager.update_thread(
                thread_id,
                priority=Priority(decision.priority.value),
            )
            if decision.intent:
                await db_pool.execute(
                    "UPDATE conversation_threads SET intent = $1 WHERE id = $2 AND intent IS NULL",
                    decision.intent.value, thread_id,
                )

        except Exception as e:
            logger.debug(f"Routing enrichment failed (non-fatal): {e}")

    async def _resolve_client_id(self, message: ChannelMessage, db_pool: Any) -> int | None:
        """Resolve CRM client_id from channel-specific identifiers."""
        try:
            if self._identity_resolver is None:
                from backend.services.crm.assignment import ClientIdentityResolver
                self._identity_resolver = ClientIdentityResolver(db_pool)

            channel = message.channel
            if channel == "telegram":
                chat_id = message.metadata.get("chat_id")
                if chat_id:
                    return await self._identity_resolver.find_client_by_telegram(str(chat_id))

            elif channel == "whatsapp":
                phone = message.metadata.get("phone")
                if phone:
                    return await self._identity_resolver.find_client_by_whatsapp(phone)

            elif channel == "web":
                user_id = message.user_id
                if user_id and "@" in user_id:
                    return await self._identity_resolver.find_client_by_email(user_id)

        except Exception as e:
            logger.debug(f"Client identity resolution failed: {e}")
        return None

    def is_channel_registered(self, channel: str) -> bool:
        """
        Check if a channel is registered.

        Args:
            channel: Channel name

        Returns:
            True if channel is registered, False otherwise
        """
        return channel in self.adapters
