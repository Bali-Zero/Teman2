"""ConversationContextLoader — bounded, sanitized history loading (see its
own module docstring for why the safe-empty default is deliberate).

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import pytest

from backend.channels.profiles import CLIENT_WA_V1
from backend.services.client_bot.context import ConversationContextLoader
from backend.services.client_bot.contracts import HistoryRole
from backend.tests.duebot.goldens.builders import det_uuid, make_history_turn


class _FixedStore:
    def __init__(self, turns) -> None:
        self._turns = turns
        self.last_limit: int | None = None

    async def recent_turns(self, conversation_id, limit):
        self.last_limit = limit
        return self._turns


@pytest.mark.asyncio
async def test_no_store_wired_returns_empty_tuple() -> None:
    loader = ConversationContextLoader()
    turns = await loader.load(det_uuid("ctx", "conversation"), CLIENT_WA_V1)
    assert turns == ()


@pytest.mark.asyncio
async def test_store_result_within_bound_is_returned_as_is() -> None:
    turns = tuple(make_history_turn(HistoryRole.USER, f"turn {i}") for i in range(3))
    store = _FixedStore(turns)
    loader = ConversationContextLoader(store)
    result = await loader.load(det_uuid("ctx", "conversation"), CLIENT_WA_V1)
    assert result == turns
    assert store.last_limit == CLIENT_WA_V1.history_turns


@pytest.mark.asyncio
async def test_store_over_returning_is_truncated_to_the_most_recent() -> None:
    over_limit = CLIENT_WA_V1.history_turns + 5
    turns = tuple(make_history_turn(HistoryRole.USER, f"turn {i}") for i in range(over_limit))
    store = _FixedStore(turns)
    loader = ConversationContextLoader(store)
    result = await loader.load(det_uuid("ctx", "conversation"), CLIENT_WA_V1)
    assert len(result) == CLIENT_WA_V1.history_turns
    assert result == turns[-CLIENT_WA_V1.history_turns :]
