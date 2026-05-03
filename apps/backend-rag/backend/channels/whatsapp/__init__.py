"""
WhatsApp channel adapter package.

Provides WhatsApp Business API integration (Meta Cloud API).
"""

from backend.channels.whatsapp.adapter import WhatsAppChannelAdapter
from backend.channels.whatsapp.config import WhatsAppChannelConfig
from backend.channels.whatsapp.formatter import WhatsAppMessageFormatter

__all__ = [
    "WhatsAppChannelAdapter",
    "WhatsAppChannelConfig",
    "WhatsAppMessageFormatter",
]
