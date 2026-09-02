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
        name="telegram",
        supports_markdown=True,
        supports_buttons=True,
        supports_images=True,
        max_length=4096,
    ),
    "whatsapp": ChannelCapabilities(
        name="whatsapp",
        supports_markdown=True,
        supports_buttons=True,
        supports_images=True,
        max_length=1600,
    ),
    "instagram": ChannelCapabilities(
        name="instagram",
        supports_markdown=False,
        supports_buttons=False,
        supports_images=True,
        max_length=1000,
    ),
    "twitter": ChannelCapabilities(
        name="twitter",
        supports_markdown=False,
        supports_buttons=False,
        supports_images=True,
        max_length=10000,
    ),
    "web": ChannelCapabilities(
        name="web",
        supports_markdown=True,
        supports_buttons=True,
        supports_images=True,
        max_length=100000,
    ),
}


def get_capabilities(channel: str) -> ChannelCapabilities:
    """Get capabilities for a channel, with sensible defaults."""
    return CHANNEL_CAPS.get(channel, ChannelCapabilities(name=channel))


# Bare numeric citation markers the LLM emits inline (e.g. "[5]", "[1, 5]")
# per the CITATION_RULES prompt convention (zantara_core.py). No plain-text
# or WhatsApp channel ever renders an accompanying footnote/source list, so
# these are dangling noise on those surfaces. Digits-only inside the
# brackets is a deliberately narrow match on the bracket CONTENT (entity: a
# numeric citation index), but content alone is not enough: Indonesian
# statutes cite sub-articles the same shape, e.g. "Pasal 19 [2]," or
# "Pasal 6 [1] dan [3] berlaku." — an earlier version of this regex had no
# positional anchor and stripped those mid-sentence, corrupting the legal
# citation ("Pasal 6 dan berlaku." — meaning-changing). The entity this
# guard actually targets is a TRAILING RAG source-index marker, so the
# match is anchored to a trailing position: end-of-text, immediately
# before a newline, or immediately before a single sentence-terminal mark
# (./!/?) that itself sits at end-of-text/end-of-line. A bracket followed
# by more prose (a comma, "dan", any word) is never trailing and survives
# untouched. See .claude/rules/cicatrix-superscar.md family #3
# (guard-over-match) for why that distinction matters.
_BARE_CITATION_RE = re.compile(
    r"\s*\[\d+(?:,\s*\d+)*\]"
    r"(?=[.!?]?\s*(?:\n|\Z))"
)


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
        # WhatsApp: limited markdown — *bold*, _italic_, ```monospace``` are
        # the ONLY formatting WA renders. Headings, **bold**, markdown
        # bullets/links and bare citation markers all render as literal
        # noise to the end client if left untouched.
        #
        # Order matters: structural markers (links/bullets) are normalized
        # BEFORE the inline **bold**/heading conversion, so a line like
        # "*   **Initial Validity:** 1 year [5]" resolves correctly —
        # the leading "*   " bullet becomes "• " first, so it never collides
        # with the "**...**" -> "*...*" bold-delimiter rewrite that follows.
        #
        # Markdown links: [text](url) -> "text (url)" — keep the URL,
        # drop the syntax WA doesn't understand.
        text = re.sub(r"\[(.+?)\]\((\S+?)\)", r"\1 (\2)", text)
        # Bullet markers ("* item" / "- item") -> unicode bullet. WA has no
        # native list syntax, and a bare leading "*" would otherwise be
        # ambiguous with the *bold* delimiter. Anchored to line-start so a
        # "**Bold**: text" line (no space after the first "*") never
        # matches here — only an actual bullet ("* "/"- " + whitespace) does.
        text = re.sub(r"^[ \t]*[*-]\s+", "• ", text, flags=re.MULTILINE)
        # Convert **bold** → *bold* (WA uses single asterisks)
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
        # Convert headers (#{1,6} Header) → *Header*
        # W119c (2026-08-31): same-line separator. With `\s+` a bare `###` on its own
        # line paired with the NEXT paragraph, delivered bold as if it were a heading.
        # A heading and its text are on one line by definition.
        text = re.sub(r"^#{1,6}[^\S\n]+(.+)$", r"*\1*", text, flags=re.MULTILINE)
        # Strip code blocks (WA doesn't render them well)
        text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).strip("`"), text)
        # Strip inline code backticks
        text = re.sub(r"`(.+?)`", r"\1", text)
        # Strip horizontal rules
        text = re.sub(r"^[-*_]{3,}$", "", text, flags=re.MULTILINE)
        # Strip bare numeric citation markers ([5], [1, 5])
        text = _BARE_CITATION_RE.sub("", text)
        # Collapse blank-line buildup left by the strips above
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    if channel in ("instagram", "twitter"):
        # Plain text: strip ALL markdown
        text = _strip_markdown(text)
        return text

    # Unknown channel: strip markdown as safest default
    if not caps.supports_markdown:
        return _strip_markdown(text)
    return text


def format_buttons(
    buttons: list[dict[str, str]],
    channel: str,
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
            wa_buttons.append(
                {
                    "type": "reply",
                    "reply": {
                        "id": btn.get("callback_data", btn["text"][:20]),
                        "title": btn["text"][:20],
                    },
                }
            )
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
    # Remove bare numeric citation markers ([5], [1, 5]) — see
    # _BARE_CITATION_RE docstring for why this is a safe, narrow match.
    text = _BARE_CITATION_RE.sub("", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}$", "", text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
