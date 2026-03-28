"""
Telegram Channel Adapter.

Implements BaseChannel for Telegram Bot API integration.

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.channels.base import BaseChannel, ChannelMessage, ChannelResponse
from backend.channels.telegram.config import TelegramChannelConfig
from backend.channels.telegram.formatter import TelegramMessageFormatter
from backend.services.integrations.telegram_bot_service import TelegramBotService

logger = logging.getLogger(__name__)


class TelegramChannelAdapter(BaseChannel):
    """
    Telegram Bot API adapter for multi-channel architecture.

    Features:
    - Webhook-based message reception
    - Progressive message updates (typing → partial → complete)
    - Markdown formatting support
    - Rate limiting compliance (Telegram API limits)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize Telegram adapter.

        Args:
            config: Configuration dictionary (must include 'bot_token')
        """
        super().__init__(config)

        # Parse Telegram-specific config
        self.telegram_config = TelegramChannelConfig(
            bot_token=config.get("bot_token", ""),
            max_message_length=config.get("max_message_length", 4096),
            update_interval=config.get("update_interval", 1.5),
            parse_mode=config.get("parse_mode", "Markdown"),
        )

        # Initialize Telegram Bot Service
        self.bot_service = TelegramBotService()
        self.formatter = TelegramMessageFormatter()

        # Track last message sent (for progressive updates)
        self._last_message_id: int | None = None
        self._last_chat_id: str | int | None = None

    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """
        Parse Telegram Update JSON into ChannelMessage.

        Telegram Update structure:
        {
            "update_id": 12345,
            "message": {
                "message_id": 789,
                "from": {"id": 123, "first_name": "John", "username": "john_doe"},
                "chat": {"id": 123, "type": "private"},
                "date": 1234567890,
                "text": "Hello bot!"
            }
        }

        Args:
            raw_event: Telegram Update dict from webhook

        Returns:
            Normalized ChannelMessage
        """
        try:
            # Extract message object
            message = raw_event.get("message", {})

            if not message:
                logger.warning("Received Telegram update without 'message' field")
                # Handle callback queries, edited messages, etc.
                # For now, return empty message
                return ChannelMessage(
                    user_id="unknown",
                    session_id="unknown",
                    text="",
                    channel="telegram",
                    metadata={"raw_event": raw_event},
                )

            # Extract user info
            from_user = message.get("from", {})
            user_id = str(from_user.get("id", "unknown"))
            username = from_user.get("username", "")
            first_name = from_user.get("first_name", "")

            # Extract chat info
            chat = message.get("chat", {})
            chat_id = str(chat.get("id", "unknown"))

            # Session ID = Telegram chat_id (each chat is a session)
            session_id = f"tg_session_{chat_id}"

            # Extract message content
            text = message.get("text", "")

            # Extract media (photos, documents, etc.)
            media = []
            if "photo" in message:
                # Photo is array of sizes, take largest
                photo = message["photo"][-1] if message["photo"] else {}
                file_id = photo.get("file_id")
                if file_id:
                    media.append(f"telegram://photo/{file_id}")

            if "document" in message:
                doc = message["document"]
                file_id = doc.get("file_id")
                if file_id:
                    media.append(f"telegram://document/{file_id}")

            # Build metadata
            metadata = {
                "chat_id": chat_id,
                "message_id": message.get("message_id"),
                "username": username,
                "first_name": first_name,
                "chat_type": chat.get("type", "private"),
                "date": message.get("date"),
            }

            logger.info(
                f"📨 Telegram message received: chat_id={chat_id}, "
                f"user={first_name} (@{username}), text={text[:50]}..."
            )

            return ChannelMessage(
                user_id=f"telegram_{user_id}",
                session_id=session_id,
                text=text,
                media=media if media else None,
                metadata=metadata,
                channel="telegram",
            )

        except Exception as e:
            logger.error(f"Failed to parse Telegram update: {e}", exc_info=True)
            raise

    async def send_response(self, channel_id: str, response: ChannelResponse) -> None:
        """
        Send a complete response to Telegram chat.

        Args:
            channel_id: Telegram chat_id
            response: Response to send
        """
        try:
            # Format response text
            formatted_text = self.formatter.format_response(response)

            # Truncate if too long
            if len(formatted_text) > self.telegram_config.max_message_length:
                formatted_text = self.truncate_message(
                    formatted_text, self.telegram_config.max_message_length
                )

            # Send message
            result = await self.bot_service.send_message(
                chat_id=channel_id,
                text=formatted_text,
                parse_mode=self.telegram_config.parse_mode,
                disable_web_page_preview=self.telegram_config.disable_web_page_preview,
            )

            # Track message for potential edits
            if result and result.get("ok"):
                message = result.get("result", {})
                self._last_message_id = message.get("message_id")
                self._last_chat_id = channel_id

                logger.info(f"✅ Sent Telegram message to chat {channel_id}")
            else:
                logger.error(f"Failed to send Telegram message: {result}")

        except Exception as e:
            logger.error(f"Error sending Telegram response: {e}", exc_info=True)

    async def send_status_update(self, channel_id: str, status: str) -> None:
        """
        Send typing indicator to Telegram chat.

        Args:
            channel_id: Telegram chat_id
            status: Status type ("processing", "thinking", etc.)
        """
        try:
            # Map status to Telegram chat action
            action_map = {
                "processing": "typing",
                "thinking": "typing",
                "searching": "typing",
                "analyzing": "typing",
                "uploading": "upload_document",
            }

            action = action_map.get(status, "typing")

            # Send chat action (typing indicator)
            await self.bot_service.send_chat_action(chat_id=channel_id, action=action)

            logger.debug(f"📍 Sent Telegram status '{status}' to chat {channel_id}")

        except Exception as e:
            # Non-critical error, just log
            logger.warning(f"Failed to send Telegram status update: {e}")

    async def stream_response(
        self, channel_id: str, response_stream: AsyncIterator[ChannelResponse]
    ) -> None:
        """
        Stream response to Telegram using progressive message edits.

        Strategy:
        1. Send initial message with status
        2. Accumulate tokens
        3. Edit message every `update_interval` seconds
        4. Send final complete message

        Args:
            channel_id: Telegram chat_id
            response_stream: AsyncIterator of ChannelResponse events
        """
        accumulated_text = ""
        accumulated_sources = []
        accumulated_workflow = None

        message_id = None
        last_update_time = 0.0
        update_interval = self.telegram_config.update_interval

        try:
            # Send initial "thinking" message
            initial_result = await self.bot_service.send_message(
                chat_id=channel_id,
                text="💭 _Sto pensando..._",
                parse_mode=self.telegram_config.parse_mode,
            )

            if initial_result and initial_result.get("ok"):
                message = initial_result.get("result", {})
                message_id = message.get("message_id")
                logger.info(
                    f"📝 Created initial Telegram message {message_id} in chat {channel_id}"
                )

            # Process stream events
            async for response in response_stream:
                import time

                current_time = time.time()

                # Accumulate content
                if response.text:
                    accumulated_text += response.text

                if response.sources:
                    accumulated_sources.extend(response.sources)

                if response.workflow:
                    accumulated_workflow = response.workflow

                # Check if we should update (rate limiting)
                should_update = (current_time - last_update_time) >= update_interval

                # Update message if interval passed and we have content
                if should_update and accumulated_text and message_id:
                    # Build current response
                    current_response = ChannelResponse(
                        text=accumulated_text,
                        sources=accumulated_sources if accumulated_sources else None,
                        workflow=accumulated_workflow,
                        metadata=response.metadata,
                    )

                    # Format and truncate
                    formatted_text = self.formatter.format_response(current_response)
                    if len(formatted_text) > self.telegram_config.max_message_length:
                        formatted_text = self.truncate_message(
                            formatted_text, self.telegram_config.max_message_length
                        )

                    # Edit message
                    try:
                        await self.bot_service.edit_message_text(
                            chat_id=channel_id,
                            message_id=message_id,
                            text=formatted_text,
                            parse_mode=self.telegram_config.parse_mode,
                        )

                        last_update_time = current_time
                        logger.debug(
                            f"📝 Updated Telegram message {message_id}: {len(formatted_text)} chars"
                        )

                    except Exception as e:
                        # Edit failed (maybe message unchanged) - continue
                        logger.debug(f"Edit message failed (non-fatal): {e}")

            # Send final complete message
            if accumulated_text and message_id:
                final_response = ChannelResponse(
                    text=accumulated_text,
                    sources=accumulated_sources if accumulated_sources else None,
                    workflow=accumulated_workflow,
                    metadata={"final": True},
                )

                formatted_text = self.formatter.format_response(final_response)
                if len(formatted_text) > self.telegram_config.max_message_length:
                    formatted_text = self.truncate_message(
                        formatted_text, self.telegram_config.max_message_length
                    )

                # Final edit
                await self.bot_service.edit_message_text(
                    chat_id=channel_id,
                    message_id=message_id,
                    text=formatted_text,
                    parse_mode=self.telegram_config.parse_mode,
                )

                logger.info(
                    f"✅ Completed Telegram message stream: {message_id} ({len(accumulated_text)} chars)"
                )

        except Exception as e:
            logger.error(f"Error streaming to Telegram: {e}", exc_info=True)

            # Send error message
            if message_id:
                error_text = self.formatter.format_error(
                    "Si è verificato un errore durante l'elaborazione. Riprova."
                )
                await self.bot_service.edit_message_text(
                    chat_id=channel_id,
                    message_id=message_id,
                    text=error_text,
                    parse_mode=self.telegram_config.parse_mode,
                )

    # BaseChannel abstract properties

    @property
    def channel_name(self) -> str:
        """Channel identifier."""
        return "telegram"

    @property
    def supports_markdown(self) -> bool:
        """Telegram supports Markdown."""
        return self.telegram_config.supports_markdown

    @property
    def supports_media(self) -> bool:
        """Telegram supports media attachments."""
        return self.telegram_config.supports_media

    @property
    def max_message_length(self) -> int:
        """Telegram max message length: 4096 characters."""
        return self.telegram_config.max_message_length
