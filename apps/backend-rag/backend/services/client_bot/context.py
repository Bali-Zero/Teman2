"""ConversationContextLoader — the bounded, sanitized ``HistoryTurn`` tuple
every ``GroundingBundle`` carries (research capture Sol §1.1 runtime flow).

No conversation-history table/migration exists in this lane's scope (F1's
own module layout names ``context.py`` as an engine internal, not a new
persistence layer to design). This is an injectable ``ConversationStore``
protocol with a safe empty default — a client-bot turn with no history
loaded is a WORSE answer (less context) but never an UNSAFE one; the
absence of history cannot itself produce a false ALLOW anywhere downstream
(``FinalPolicyGate`` never reads ``GroundingBundle.history`` as a source of
truth for any check — it is prompt/generation-time context only).

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.channels.profiles import SurfaceProfile
from backend.services.client_bot.contracts import HistoryTurn

__all__ = ["ConversationContextLoader", "ConversationStore"]


class ConversationStore(Protocol):
    """A future lane's real persistence (Postgres conversation log, or a
    thin wrapper over whatever already logs WA/IG/portal turns today).
    Returns turns OLDEST-FIRST, already sanitized (``HistoryTurn``'s own
    ``extra="forbid"``/``max_length`` bounds are the last line of defense,
    not the only one — a store implementation must not hand this loader
    raw, unbounded, or PII-bearing text expecting the loader to clean it).
    """

    async def recent_turns(self, conversation_id: UUID, limit: int) -> tuple[HistoryTurn, ...]: ...


class ConversationContextLoader:
    def __init__(self, store: ConversationStore | None = None) -> None:
        self._store = store

    async def load(self, conversation_id: UUID, profile: SurfaceProfile) -> tuple[HistoryTurn, ...]:
        """Bounded to ``profile.history_turns`` (F2's per-surface history
        depth) regardless of what the store returns — a store that ignores
        ``limit`` or over-returns must not silently blow the profile's own
        budget.
        """
        if self._store is None:
            return ()
        turns = await self._store.recent_turns(conversation_id, profile.history_turns)
        if len(turns) > profile.history_turns:
            return turns[-profile.history_turns :]
        return turns
