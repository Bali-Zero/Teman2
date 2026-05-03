"""
Channel Overlays — Per-channel configuration for Zantara responses.

Each channel has specific constraints (word limits, markdown support, emoji, etc.)
that get injected into the system prompt at runtime.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelConfig:
    """Immutable configuration for a single delivery channel."""

    name: str
    max_words: int
    markdown: bool
    emoji: bool
    progressive: bool
    extra_instructions: str = ""


CHANNEL_CONFIGS: dict[str, ChannelConfig] = {
    "webapp": ChannelConfig(
        name="webapp",
        max_words=800,
        markdown=True,
        emoji=True,
        progressive=True,
    ),
    "telegram": ChannelConfig(
        name="telegram",
        max_words=300,
        markdown=True,
        emoji=True,
        progressive=True,
    ),
    "whatsapp": ChannelConfig(
        name="whatsapp",
        max_words=150,
        markdown=False,
        emoji=True,
        progressive=False,
        extra_instructions="NO markdown. Plain text only. Short, direct.",
    ),
    "voice": ChannelConfig(
        name="voice",
        max_words=100,
        markdown=False,
        emoji=False,
        progressive=False,
        extra_instructions="2-3 sentences max. Spoken, brief.",
    ),
    "website": ChannelConfig(
        name="website",
        max_words=400,
        markdown=True,
        emoji=True,
        progressive=True,
        extra_instructions=(
            "You are embedded as a widget on balizero.com. "
            "Keep answers concise and helpful — this is a lead generation context. "
            "After the user's 3rd question, naturally suggest a personal consultation: "
            '"For a personalized consultation, reach us at '
            'info@balizero.com or WhatsApp +62 821 3107 363."'
        ),
    ),
}


def build_channel_context(channel: str) -> str:
    """Build the XML channel context block for injection into the system prompt.

    Args:
        channel: Channel name (webapp, telegram, whatsapp, voice, website).

    Returns:
        XML string to inject, or empty string if channel is unknown.
    """
    config = CHANNEL_CONFIGS.get(channel)
    if config is None:
        return ""

    lines = [
        "<channel_context>",
        f"Channel: {config.name}",
        f"Max words: {config.max_words}",
        f"Markdown: {'yes' if config.markdown else 'no'}",
        f"Emoji: {'yes' if config.emoji else 'no'}",
    ]
    if config.extra_instructions:
        lines.append(f"Extra: {config.extra_instructions}")
    lines.append("</channel_context>")
    return "\n".join(lines)
