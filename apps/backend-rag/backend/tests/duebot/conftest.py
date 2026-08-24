"""Shared fixtures for the B6a test harness (webhook replay + broker).

The autouse ``_no_network`` fixture below disables real outbound socket
connections for every test collected under ``backend/tests/duebot/`` — see
``test_no_network_guard.py`` for the proof it actually fires, not just a
promise that it does. FastAPI's ``TestClient`` (used by the ``duebot``
fixture below) talks to the app over an in-process ASGI transport and
never opens a socket on its own, so this guard is pure defense-in-depth
against anything that DOES try — a stray real HTTP call, an unmocked
background task reaching an LLM/CRM/WhatsApp API, etc. ``FakeCodexBroker``
is likewise pure in-memory state and needs no exemption.
"""

from __future__ import annotations

import itertools
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.tests.duebot.network_guard import (
    NetworkAccessBlockedError as NetworkAccessBlockedError,  # re-exported, see below
)
from backend.tests.duebot.network_guard import (
    blocked_connect,
    blocked_connect_ex,
    blocked_create_connection,
)

# Re-exported so existing `from backend.tests.duebot.conftest import
# NetworkAccessBlockedError` call sites keep working, but the CLASS ITSELF
# is defined in network_guard.py and imported here by the same dotted
# path a test file would use — see network_guard.py's module docstring
# for why that indirection is load-bearing, not decorative.


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test under this package runs with real outbound sockets
    disabled.

    Covers the call shapes stdlib/``httpx``/``asyncpg``/etc. use to open an
    outbound connection: raw ``socket.socket().connect()``, ``connect_ex``
    (the non-blocking-connect path), and the ``socket.create_connection``
    convenience wrapper most HTTP clients call under the hood. It does NOT
    patch ``socket.socket`` construction, or ``bind``/``listen``/``accept``
    — this guards OUTBOUND egress (the mandate's concern: "nothing touches
    graph.facebook.com"), not the ability to run a local test server or
    construct a socket object.
    """
    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked_connect_ex)
    monkeypatch.setattr(socket, "create_connection", blocked_create_connection)


FakePersist = Callable[..., Awaitable[tuple[int | None, bool]]]


@pytest.fixture
def fake_inbound_store() -> tuple[FakePersist, set[tuple[str, str]]]:
    """Stand-in for the ``inbound_webhooks`` ``UNIQUE(channel, dedup_key)``
    constraint: an in-memory ``(channel, dedup_key)`` set.

    First insert of a key returns ``(row_id, True)``; every subsequent
    insert of the SAME key returns ``(None, False)`` — the exact
    ``persist()`` return contract documented in
    ``backend.services.channels.inbound_webhook_repo``. This is what makes
    the duplicate-``wamid``-replay tests meaningful without a real
    Postgres pool.
    """
    seen: set[tuple[str, str]] = set()
    counter = itertools.count(1)

    async def fake_persist(
        pool: Any,
        *,
        channel: str,
        dedup_key: str,
        payload: dict[str, Any],
        recovery_after_seconds: int = 0,
    ) -> tuple[int | None, bool]:
        key = (channel, dedup_key)
        if key in seen:
            return (None, False)
        seen.add(key)
        return (next(counter), True)

    return fake_persist, seen


@dataclass
class DuebotHarness:
    """Everything a webhook-replay test needs: the mounted app, a
    ``TestClient`` against it, and handles onto every mock so a test can
    assert on call counts/args — not just on the HTTP response.
    """

    app: FastAPI
    client: TestClient
    process_whatsapp_mock: AsyncMock
    channel_router_mock: AsyncMock
    seen_dedup_keys: set[tuple[str, str]]


@pytest.fixture
def duebot(
    monkeypatch: pytest.MonkeyPatch,
    fake_inbound_store: tuple[FakePersist, set[tuple[str, str]]],
) -> DuebotHarness:
    """A FastAPI app mounting the REAL WhatsApp + Instagram webhook
    routers, unmodified, with only the heavy/unrelated side effects
    replaced:

    - ``inbound_webhook_repo.persist`` → the in-memory dedup fake above,
      patched at the module attribute (both routers do
      ``from backend.services.channels import inbound_webhook_repo`` and
      then call ``inbound_webhook_repo.persist(...)`` — a module-attribute
      lookup at call time, so patching the attribute here is visible to
      them regardless of when they import the module).
    - ``whatsapp_chat.process_whatsapp_message_and_mark_processed`` (the
      WhatsApp background task that hands off to the orchestrator/LLM/CRM
      chain) → ``AsyncMock``. That chain is out of scope for a
      TRANSPORT-level harness and needs real network/DB to run for real.
    - ``app.state.channel_router`` (Instagram's synchronous routing call,
      read directly off ``request.app.state`` — NOT resolved through
      FastAPI's ``Depends()`` machinery, so a ``dependency_overrides``
      entry alone would silently do nothing here; verified by reading
      ``backend.app.deps.services.get_channel_router``) → ``AsyncMock``
      with an explicit ``AsyncMock`` ``route_message`` attribute.

    NOT mocked: ``_verify_whatsapp_signature``. The real production HMAC
    verifier runs completely unmodified — that is the entire point of this
    harness (B6a mandate: "your signer must produce signatures that this
    verifier accepts").
    """
    from backend.app.routers import instagram_chat, whatsapp_chat

    fake_persist, seen = fake_inbound_store
    monkeypatch.setattr(
        "backend.services.channels.inbound_webhook_repo.persist",
        AsyncMock(side_effect=fake_persist),
    )
    process_whatsapp_mock = AsyncMock()
    monkeypatch.setattr(
        whatsapp_chat,
        "process_whatsapp_message_and_mark_processed",
        process_whatsapp_mock,
    )

    app = FastAPI()
    app.include_router(whatsapp_chat.router)
    app.include_router(instagram_chat.webhook_router)
    # Both routers read these off request.app.state directly (see
    # backend/app/deps/database.py::get_database_pool and
    # backend/app/deps/services.py::get_channel_router) — a MagicMock
    # satisfies the `hasattr(db_pool, "acquire")` check without a real pool
    # because persist() itself is fully replaced above.
    app.state.db_pool = MagicMock()
    channel_router_mock = AsyncMock()
    channel_router_mock.route_message = AsyncMock()
    app.state.channel_router = channel_router_mock

    client = TestClient(app, raise_server_exceptions=False)
    return DuebotHarness(
        app=app,
        client=client,
        process_whatsapp_mock=process_whatsapp_mock,
        channel_router_mock=channel_router_mock,
        seen_dedup_keys=seen,
    )
