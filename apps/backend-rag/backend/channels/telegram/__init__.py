"""
Telegram channel adapter package.

Provides Telegram Bot API integration for the multi-channel architecture.
"""

from backend.channels.telegram.adapter import TelegramChannelAdapter
from backend.channels.telegram.config import TelegramChannelConfig
from backend.channels.telegram.formatter import TelegramMessageFormatter

__all__ = [
    "TelegramChannelAdapter",
    "TelegramChannelConfig",
    "TelegramMessageFormatter",
]
