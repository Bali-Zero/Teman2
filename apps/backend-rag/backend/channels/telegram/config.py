"""
Telegram Channel Configuration.

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

from dataclasses import dataclass


@dataclass
class TelegramChannelConfig:
    """
    Configuration for Telegram channel adapter.

    Attributes:
        bot_token: Telegram Bot API token (from BotFather)
        max_message_length: Maximum length for Telegram messages (4096 chars)
        update_interval: Seconds between progressive message updates
        supports_markdown: Whether to use Markdown formatting
        supports_media: Whether to support media attachments
        webhook_path: Path for webhook endpoint (e.g., "/webhook/telegram")
        parse_mode: Telegram parse mode ("Markdown", "MarkdownV2", "HTML", or None)
    """

    bot_token: str
    max_message_length: int = 4096
    update_interval: float = 1.5  # Telegram allows ~1 edit per second per chat
    supports_markdown: bool = True
    supports_media: bool = True
    webhook_path: str = "/webhook/telegram"
    parse_mode: str = "Markdown"

    # Advanced settings
    disable_web_page_preview: bool = True  # Don't show link previews
    disable_notification: bool = False  # Send silent notifications

    # Rate limiting (Telegram Bot API limits)
    max_edits_per_second: int = 1
    max_messages_per_second: int = 30
    max_messages_per_minute: int = 20  # To same chat

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.bot_token:
            raise ValueError("bot_token is required")

        if self.max_message_length > 4096:
            raise ValueError("Telegram max_message_length cannot exceed 4096")

        if self.update_interval < 1.0:
            raise ValueError("update_interval must be >= 1.0 seconds (Telegram rate limit)")
