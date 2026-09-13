"""
Channel Overlays — Per-channel configuration for Zantara responses.

Each channel has specific constraints (word limits, markdown support, emoji, etc.)
that get injected into the system prompt at runtime.
"""

from dataclasses import dataclass

from backend.app.core.config import settings


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
        # "Short, direct." was not obeyed, and that is measured, not suspected:
        # across 37 live questions ~10% of answers crossed WhatsApp's 4096-char
        # limit, worst case 13,671 characters for "What is Hak Pakai and how long
        # does it last?" — roughly 2,000 words against a 150-word budget.
        #
        # Two things changed here, both aimed at the reason a soft budget fails.
        # A word count is not a shape the model can check while writing, so the
        # instruction now names the SHAPE it should produce; and the limit is
        # restated as a hard physical fact (the platform refuses the message)
        # rather than a preference, because "max words" reads as style guidance
        # next to a question that deserves a thorough answer.
        #
        # This is a prompt change, so it is a nudge with a measurable outcome and
        # NOT a guarantee. The guarantee is `whatsapp_service.fit_to_whatsapp_limit`,
        # which cuts at a boundary and says so. Do not remove that on the strength
        # of this: the same question measured 1,364 / 13,671 / 2,123 characters on
        # three runs, so any single observation of "it got shorter" is noise.
        extra_instructions=(
            "NO markdown. Plain text only. "
            "HARD LIMIT: WhatsApp REFUSES any message over 4096 characters — "
            "anything past that is physically deleted, so a long answer reaches "
            "the client decapitated. "
            "Answer in AT MOST 5 short paragraphs or 7 bullet points. "
            "Lead with the direct answer in the first sentence, then only what "
            "this person must do next. "
            "Do NOT restate the question, do NOT list every exception, do NOT add "
            "background the client did not ask for. "
            "If the full picture does not fit, give the essentials and offer to go "
            "deeper on one point — that is better than an answer cut mid-word."
        ),
    ),
    "instagram": ChannelConfig(
        name="instagram",
        max_words=150,
        markdown=False,
        emoji=True,
        progressive=False,
        extra_instructions=(
            "NO markdown (no **, ##, *, -, backticks — they render as raw symbols "
            "in Instagram DMs). Plain text only. HARD LIMIT: keep the whole reply "
            "under 800 characters — Instagram truncates at 1000, so going over "
            "loses your closing line and source. Prefer fewer, tighter points over "
            "completeness. Be short, direct, and end with one clear next step."
        ),
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
            f'info@balizero.com or WhatsApp {settings.CLIENT_CONTACT_WHATSAPP}."'
        ),
    ),
}


def build_channel_context(channel: str) -> str:
    """Build the XML channel context block for injection into the system prompt.

    Args:
        channel: Channel name (webapp, telegram, whatsapp, instagram, voice, website).

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


def apply_channel_overlay(system_prompt: str, channel: str | None) -> str:
    """Append the channel context block to an assembled system prompt.

    The append itself is three lines, and until 2026-08-11 those three lines
    lived inline in ``_prepare_react_loop`` — which the STREAMING path calls
    and the non-streaming ``process_query_core`` does not. Measured
    consequence on the live worker, same question, same path, two runs each:

        channel="whatsapp"  ->  611 / 875 chars
        channel="webapp"    -> 1348 / 2163 chars
        channel omitted     -> 1964 / 1900 chars

    The WhatsApp inbox bot sends ``"channel": "whatsapp"`` on every call and
    reaches the backend through the NON-streaming endpoint, so its 150-word
    budget was declared and never applied: production replies measure a median
    of 1586 characters against inbound client messages whose median is 57.

    Owning the rule here — rather than as a copied pair of lines — is the
    point: two call sites that must agree about "what does a channel do to a
    prompt" should not each carry their own answer.

    A falsy or unknown channel leaves the prompt untouched, so a caller that
    declares nothing is unchanged.
    """
    if not channel:
        return system_prompt
    block = build_channel_context(channel)
    if not block:
        return system_prompt
    return f"{system_prompt}\n\n{block}"
