"""Unified Format Contract — channel-aware message formatting.

Transforms rich content (markdown, buttons, images) into channel-specific
formats. Each channel has declared capabilities; the formatter adapts
output automatically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChannelCapabilities:
    """Declared capabilities of a channel."""

    name: str
    supports_markdown: bool = False
    supports_buttons: bool = False
    supports_images: bool = False
    max_length: int = 4096


# Pre-defined capabilities per channel
CHANNEL_CAPS: dict[str, ChannelCapabilities] = {
    "telegram": ChannelCapabilities(
        name="telegram", supports_markdown=True, supports_buttons=True,
        supports_images=True, max_length=4096,
    ),
    "whatsapp": ChannelCapabilities(
        name="whatsapp", supports_markdown=True, supports_buttons=True,
        supports_images=True, max_length=1600,
    ),
    "instagram": ChannelCapabilities(
        name="instagram", supports_markdown=False, supports_buttons=False,
        supports_images=True, max_length=1000,
    ),
    "twitter": ChannelCapabilities(
        name="twitter", supports_markdown=False, supports_buttons=False,
        supports_images=True, max_length=10000,
    ),
    "web": ChannelCapabilities(
        name="web", supports_markdown=True, supports_buttons=True,
        supports_images=True, max_length=100000,
    ),
}


def get_capabilities(channel: str) -> ChannelCapabilities:
    """Get capabilities for a channel, with sensible defaults."""
    return CHANNEL_CAPS.get(channel, ChannelCapabilities(name=channel))


def format_rich_text(text: str, channel: str) -> str:
    """Convert generic markdown to channel-specific format.

    Args:
        text: Markdown-formatted text.
        channel: Target channel name.

    Returns:
        Channel-formatted text.
    """
    caps = get_capabilities(channel)

    if channel == "web":
        # Web: pass through raw markdown (frontend renders it)
        return text

    if channel == "telegram":
        # Telegram: standard Markdown (not MarkdownV2 to avoid escape hell)
        # Already compatible with *bold*, _italic_, `code`, ```pre```
        return text

    if channel == "whatsapp":
        # WhatsApp: limited markdown
        # Convert **bold** → *bold* (WA uses single asterisks)
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
        # Convert headers (## Header) → *Header*
        text = re.sub(r"^#{1,3}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
        # Strip code blocks (WA doesn't render them well)
        text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).strip("`"), text)
        # Strip inline code backticks
        text = re.sub(r"`(.+?)`", r"\1", text)
        return text

    if channel in ("instagram", "twitter"):
        # Plain text: strip ALL markdown
        text = _strip_markdown(text)
        return text

    # Unknown channel: strip markdown as safest default
    if not caps.supports_markdown:
        return _strip_markdown(text)
    return text


def format_buttons(
    buttons: list[dict[str, str]], channel: str,
) -> dict[str, Any] | None:
    """Convert button list to channel-specific format.

    Args:
        buttons: List of ``{"text": "...", "callback_data": "...", "url": "..."}``
        channel: Target channel name.

    Returns:
        Channel-specific button payload, or None if unsupported.
    """
    if not buttons:
        return None

    caps = get_capabilities(channel)
    if not caps.supports_buttons:
        return None

    if channel == "telegram":
        # Telegram inline keyboard
        keyboard = []
        for btn in buttons:
            row: dict[str, str] = {"text": btn["text"]}
            if "url" in btn:
                row["url"] = btn["url"]
            elif "callback_data" in btn:
                row["callback_data"] = btn["callback_data"]
            keyboard.append([row])
        return {"inline_keyboard": keyboard}

    if channel == "whatsapp":
        # WhatsApp interactive buttons (max 3)
        wa_buttons = []
        for btn in buttons[:3]:
            wa_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn.get("callback_data", btn["text"][:20]),
                    "title": btn["text"][:20],
                },
            })
        return {"type": "button", "buttons": wa_buttons}

    if channel == "web":
        # Web: pass through as-is (frontend handles rendering)
        return {"buttons": buttons}

    return None


def _strip_markdown(text: str) -> str:
    """Remove all markdown formatting, leaving plain text."""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).strip("`").strip(), text)
    # Remove inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove bold/italic markers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove links: [text](url) → text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # Remove images: ![alt](url)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}$", "", text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
