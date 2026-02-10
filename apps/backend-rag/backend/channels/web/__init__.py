"""
Web channel adapter package.

Provides SSE (Server-Sent Events) streaming for web applications.
"""

from backend.channels.web.adapter import WebChannelAdapter
from backend.channels.web.config import WebChannelConfig
from backend.channels.web.formatter import WebMessageFormatter

__all__ = [
    "WebChannelAdapter",
    "WebChannelConfig",
    "WebMessageFormatter",
]
