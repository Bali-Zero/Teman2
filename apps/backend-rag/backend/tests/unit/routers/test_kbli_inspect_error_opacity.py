"""A 500 tells the client that we failed, never how the database failed.

`inspect_kbli`'s catch-all ends `detail=f"Internal processing error: {err_msg}"`
where `err_msg = str(e)` for ANY exception that is neither an `HTTPException` nor
connection-shaped. Whatever the driver put in that string — a table name, a column,
a host, a DSN fragment, a server-side message the operator never chose to publish —
is handed to whoever made the request, on a route that needs no authentication.

The cure is opacity in the RESPONSE and nothing else. The log keeps the whole
string, `exc_info` included: a cure that made the operator blind to trade for a
client who cannot see would be the same mistake facing the other way, so the second
guilt test asserts the detail is still written down where the operator reads it.

The innocence half fences what the catch-all must keep doing: a connection-shaped
failure still earns its 503 with `Retry-After`, an `HTTPException` raised deeper in
the route — a 404 for a code the graph does not hold — still reaches the client with
its own status and its own detail, and a healthy request is still a 200.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.kbli_notebook as kbli_notebook_module
from backend.app.dependencies import get_optional_database_pool, get_search_service

NODE = {
    "entity_id": "kbli:56101",
    "name": "Restoran",
    "description": "Restoran.",
    "properties": {"uraian": "Restoran.", "licensing_status": "REGULATED"},
}

# The three things a driver string leaks that a client has no business reading: the
# server's own words, our schema, and our topology. Each is asserted separately so a
# partial cure — scrubbing the host but echoing the table — cannot pass.
SERVER_WORDS = "syntax error at or near SELEKT"
SCHEMA_NAME = "kbli_documents_internal_v3"
TOPOLOGY = "db-internal-7.flycast:5432"
LEAKY_MESSAGE = f"{SERVER_WORDS} — table {SCHEMA_NAME} on {TOPOLOGY}"


def _pool(*, node_error=None):
    conn = MagicMock()

    async def _fetchrow(query, *args):
        if node_error is not None:
            raise node_error
        # Dispatch on the CODE, never on call order: the 404 innocence test needs a
        # code the graph does not hold, and a fixture that answers NODE to anything
        # would hand it a 200 and silently stop testing the re-raise.
        return NODE if any("56101" in str(a) for a in args) else None

    conn.fetchrow = AsyncMock(side_effect=_fetchrow)

    async def _fetch(query, *args):
        if "catalogue_size" in query:
            return [{"catalogue_size": 1563, "canonical_rows": 1}]
        return []

    conn.fetch = AsyncMock(side_effect=_fetch)
    conn.fetchval = AsyncMock(return_value="sektor:I")

    pool = MagicMock()
    pool.expire_connections = AsyncMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return pool


@pytest.fixture
def make_client():
    started = []

    def _make(**pool_kwargs):
        app = FastAPI()
        app.include_router(kbli_notebook_module.router)
        app.dependency_overrides[get_search_service] = lambda: MagicMock(embedder=MagicMock())
        app.dependency_overrides[get_optional_database_pool] = lambda: _pool(**pool_kwargs)
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        stack = [
            patch.object(
                kbli_notebook_module,
                "_get_kbli_payload_from_qdrant",
                AsyncMock(return_value=None),
            ),
            patch("backend.core.cache.get_cache_service", return_value=cache),
        ]
        for p in stack:
            p.start()
        started.extend(stack)
        return TestClient(app, raise_server_exceptions=False)

    yield _make
    for p in started:
        p.stop()


# --------------------------------------------------------------------------
# GUILT — the driver's words must not reach the response body
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        asyncpg.PostgresSyntaxError(LEAKY_MESSAGE),
        asyncpg.UndefinedColumnError(LEAKY_MESSAGE),
        RuntimeError(LEAKY_MESSAGE),
        ValueError(LEAKY_MESSAGE),
    ],
    ids=["syntax_error", "undefined_column", "runtime_error", "value_error"],
)
@pytest.mark.parametrize(
    "leak", [SERVER_WORDS, SCHEMA_NAME, TOPOLOGY], ids=["server_words", "schema", "topology"]
)
def test_the_five_hundred_body_carries_none_of_the_drivers_words(make_client, error, leak):
    client = make_client(node_error=error)
    response = client.get("/kbli-notebook/inspect/56101")

    assert response.status_code == 500, response.text
    assert leak not in response.text


def test_the_operator_still_reads_the_whole_string_in_the_log(make_client, caplog):
    """Opacity is not amnesia: the cure moves the detail, it does not delete it."""
    client = make_client(node_error=RuntimeError(LEAKY_MESSAGE))
    with caplog.at_level(logging.ERROR):
        response = client.get("/kbli-notebook/inspect/56101")

    assert response.status_code == 500
    assert LEAKY_MESSAGE in caplog.text


# --------------------------------------------------------------------------
# INNOCENCE — what the catch-all must keep doing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        asyncpg.InterfaceError("connection is closed"),
        ConnectionResetError("Connection reset by peer"),
    ],
    ids=["interface_error", "connection_reset"],
)
def test_a_connection_fault_still_earns_its_503_and_retry_after(make_client, error):
    client = make_client(node_error=error)
    response = client.get("/kbli-notebook/inspect/56101")

    assert response.status_code == 503, response.text
    assert response.headers["Retry-After"] == "5"
    assert "retry" in response.json()["detail"].lower()


def test_a_404_raised_deeper_in_the_route_is_not_rewritten_as_a_500(make_client):
    """`except HTTPException: raise` is load-bearing; the cure must not absorb it."""
    client = make_client()
    with patch.object(
        kbli_notebook_module, "_get_kbli_payload_from_qdrant", AsyncMock(return_value=None)
    ):
        response = client.get("/kbli-notebook/inspect/99999")

    assert response.status_code == 404, response.text
    assert "99999" in response.json()["detail"]


def test_a_healthy_request_is_still_a_200(make_client):
    """Innocence for every test above: they must fail for the ERROR, not the route."""
    client = make_client()
    response = client.get("/kbli-notebook/inspect/56101")

    assert response.status_code == 200, response.text
    assert response.json()["code"] == "56101"
