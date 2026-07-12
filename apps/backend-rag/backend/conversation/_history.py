"""Pure helpers for conversation-history shaping (no heavy imports).

Kept separate from engine.py so unit tests don't drag in the orchestrator
import chain.
"""

from __future__ import annotations

from typing import Any


def trim_self_echo(history: list[dict[str, Any]], current_text: str) -> list[dict[str, Any]]:
    """Drop the trailing history entry when it IS the current inbound message.

    The ChannelRouter persists the inbound row BEFORE the engine loads context
    (audit-first ordering — a crash mid-processing must not lose the audit
    row). On a Redis cache miss the DB fallback therefore returns the current
    message as the newest history entry, and the LLM would receive it twice:
    once in history, once as the query (Codex review 2026-07-13).

    Only the LAST entry is considered, and only when it is a user turn with
    exactly the current text — a genuinely repeated earlier message deeper in
    the history is never touched.
    """
    if (
        history
        and history[-1].get("role") == "user"
        and history[-1].get("content") == current_text
    ):
        return history[:-1]
    return history
