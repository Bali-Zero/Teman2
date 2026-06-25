"""
Regression tests for the Instagram channel overlay (design + latency fix, 2026-06-21).

Two halves of the same fix are pinned here:

1. CHANNEL_CONFIGS has an "instagram" entry → build_channel_context("instagram")
   returns a non-empty, plain-text, no-markdown block with a length cap. Without
   it the IG bot inherited the webapp default (markdown, 800 words) and its DMs
   showed raw ** / ### symbols and got truncated mid-sentence at 1000 chars.

2. ConversationEngine.process_message MUST forward message.channel to
   orchestrator.stream_query(channel=...). The whole overlay chain
   (stream_query → stream_query_core → prepare_react_execution →
   build_channel_context) was already wired; the single severed link was the
   engine dropping the channel, so the overlay was inert (superscar #2:
   exists-but-not-armed). Structural assert via inspect so a future refactor
   that silently drops the kwarg fails CI instead of going live mute-on-design.
"""

import inspect

from backend.prompts.channel_overlays import (
    CHANNEL_CONFIGS,
    build_channel_context,
)


def test_instagram_entry_exists_and_is_plain_short() -> None:
    config = CHANNEL_CONFIGS.get("instagram")
    assert config is not None, "instagram missing from CHANNEL_CONFIGS"
    assert config.markdown is False, "instagram must be plain-text (no markdown)"
    # IG DM hard limit is 1000 chars; cap the model well under it so the reply
    # is never truncated mid-sentence.
    assert config.max_words <= 150


def test_build_channel_context_instagram_is_plain_no_markdown() -> None:
    block = build_channel_context("instagram")
    assert block, "instagram overlay must not be empty (else IG gets webapp markdown)"
    assert "Markdown: no" in block
    # The extra-instructions must explicitly forbid markdown and bound length.
    lowered = block.lower()
    assert "no markdown" in lowered
    assert "800" in block, "must cap reply length so IG never truncates mid-sentence"


def test_unknown_channel_still_returns_empty() -> None:
    # Innocence: the new entry must not change the fallback contract for
    # genuinely-unknown channels.
    assert build_channel_context("unknown") == ""
    assert build_channel_context("definitely-not-a-channel") == ""


def test_engine_forwards_channel_to_stream_query() -> None:
    """The overlay is inert unless the engine passes message.channel through."""
    from backend.conversation.engine import ConversationEngine

    src = inspect.getsource(ConversationEngine.process_message)
    assert "channel=message.channel" in src, (
        "ConversationEngine.process_message must forward channel=message.channel "
        "to stream_query — otherwise the per-channel overlay never reaches the "
        "orchestrator and IG/WA bots get webapp-style markdown answers."
    )
