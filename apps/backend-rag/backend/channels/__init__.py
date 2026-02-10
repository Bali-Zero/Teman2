"""
Multi-Channel Architecture

Unified interface for handling multiple communication channels
(Telegram, WhatsApp, Instagram, X/Twitter, Web App) with a single
business logic core.

Architecture:
    Channel Layer (adapters) → ChannelRouter → ConversationEngine → Orchestrator

Author: Claude Sonnet (Multi-Channel Architecture Implementation)
Date: 2026-02-10
"""

from .base import BaseChannel, ChannelMessage, ChannelResponse
from .router import ChannelRouter

__all__ = ["BaseChannel", "ChannelMessage", "ChannelResponse", "ChannelRouter"]
