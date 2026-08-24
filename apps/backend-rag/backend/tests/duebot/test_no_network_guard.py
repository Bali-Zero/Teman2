"""Proves the autouse ``_no_network`` fixture in ``conftest.py`` actually
blocks real outbound network access — a CHECK, not a promise, per the B6a
mandate: "the mandate states this as a hard rule; make it a check, not a
promise."

Every test in ``backend/tests/duebot/`` runs under that fixture already
(autouse=True); this file's job is narrower and more important: prove the
guard actually fires when something tries to reach the network, by trying
— specifically against ``graph.facebook.com``, the exact host the mandate
names — and asserting the attempt is blocked before any bytes leave the
process. If this file's positive-blocking tests ever go green-by-vacuity
(e.g. because the guard silently stopped being applied), the negative
tests below (that legitimate in-process work still succeeds) would need
no real network either, so a broken guard would show up as EVERY OTHER
test in this package still passing while THESE tests stop failing loudly
— which is why the assertions here are on the exception type, not on
"did not crash".
"""

from __future__ import annotations

import socket

import pytest

from backend.tests.duebot.network_guard import NetworkAccessBlockedError


def test_socket_connect_to_graph_facebook_com_is_blocked() -> None:
    """The literal host named in the mandate's hard rule."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessBlockedError):
            sock.connect(("graph.facebook.com", 443))
    finally:
        sock.close()


def test_socket_connect_ex_to_graph_facebook_com_is_blocked() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessBlockedError):
            sock.connect_ex(("graph.facebook.com", 443))
    finally:
        sock.close()


def test_create_connection_to_graph_facebook_com_is_blocked() -> None:
    with pytest.raises(NetworkAccessBlockedError):
        socket.create_connection(("graph.facebook.com", 443), timeout=1)


def test_connect_to_an_arbitrary_local_looking_address_is_also_blocked() -> None:
    """The guard blocks ALL outbound connect() calls, not an allow-list
    that happens to catch Meta's hostname specifically — a test that only
    exercised ``graph.facebook.com`` could pass by accident if the guard
    were a narrow hostname denylist instead of a real network block.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessBlockedError):
            sock.connect(("127.0.0.1", 65535))
    finally:
        sock.close()


def test_httpx_client_request_is_blocked_by_the_same_guard() -> None:
    """The realistic failure mode: a lane forgets to mock a real HTTP call
    and ``httpx`` tries to actually dial out. httpx's default transport
    goes through stdlib sockets, so the same guard must catch it too —
    this is not guaranteed by the socket-level tests above alone, since
    httpx could in principle use a different connection primitive.
    """
    import httpx

    with pytest.raises(NetworkAccessBlockedError):
        httpx.get("https://graph.facebook.com/v19.0/", timeout=1)


def test_in_process_asgi_test_client_is_unaffected_by_the_guard() -> None:
    """Confirms the guard is scoped to real network egress, not to HTTP
    traffic in general — the webhook replay harness's ``TestClient`` calls
    (used throughout ``test_webhook_replay.py``) must keep working under
    the exact same autouse fixture, since ``TestClient`` talks to the app
    over an in-process ASGI transport that never touches a socket.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    resp = client.get("/ping")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_fake_codex_broker_needs_no_network_exemption() -> None:
    """FakeCodexBroker is pure in-memory state — running its full
    offer/claim/complete/consume cycle under the network guard must not
    even come close to tripping it.
    """
    from backend.tests.duebot.fake_codex_broker import BrokerErrorClass, FakeCodexBroker

    broker = FakeCodexBroker()
    job_id = broker.offer({"prompt": "no network needed"})
    broker.claim()
    broker.complete(job_id, error_class=BrokerErrorClass.INTERNAL)

    assert broker.get(job_id).error_class == BrokerErrorClass.INTERNAL
