"""A catalogue that cannot answer must cost the convenience, never the page.

The tombstone cure (2026-09-19) gave `inspect_kbli` its first read of
`kbli_documents`. That added the table's availability to the endpoint's own: before
it, a broken catalogue was invisible here, because the answer came from `kg_nodes`
and Qdrant. After it, an unreadable catalogue raised, reached the router's catch-all
and became a **500 for all 1,559 codes** — a cure worth ten codes costing the other
1,549.

Correctness was never the exposure, and these tests say which half is which. An
exception cannot reach `catalogue_verdict`, so it could never manufacture a false
`ABSENT`; what it could do is take the page down. So the guilt tests below assert
the PRE-TOMBSTONE answer survives a catalogue outage, not that some new answer
appears.

The innocence half is the sharper one: a connection-shaped failure must still reach
the router's 503 with `Retry-After`. Swallowing those too would look like a tidier
`except` and would silently convert a retryable stale-pool outage into a full page
rendered from a degraded read — the client would never learn to retry.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.kbli_notebook as kbli_notebook_module
from backend.app.dependencies import get_optional_database_pool, get_search_service
from backend.services.kbli_catalogue_membership import (
    PHANTOM_LICENSING_STATUS,
    TOMBSTONE_DESCRIPTION,
    TOMBSTONE_TITLE_SUFFIX,
    fetch_catalogue_membership,
)

# `74100` as the graph still holds it: a KBLI-2020 node carrying a full REGULATED
# answer. It is the hardest case for these tests — if the degraded path ever fell
# through to the tombstone branch, THIS is the code that would flip, so asserting it
# comes back REGULATED is asserting the degradation really is inert.
NODE = {
    "entity_id": "kbli:74100",
    "name": "Aktivitas Perancangan Khusus",
    "description": "Aktivitas perancangan khusus.",
    "properties": {
        "uraian": "Aktivitas perancangan khusus.",
        "licensing_status": "REGULATED",
    },
}

REQUIRES_ROWS = [
    {
        "entity_id": "perizinan:izin_usaha_industri",
        "name": "Izin Usaha Industri",
        "target_entity_type": "perizinan",
        "properties": {"skala_usaha": ["Besar"], "kategori_risiko": "Tinggi"},
        "edge_props": None,
    },
]

SIBLINGS = ("kbli:74110", "kbli:74190")


def _pool(*, membership_error=None, sibling_error=None, siblings=SIBLINGS):
    """A connection whose catalogue and/or sibling query fails the way we ask.

    Dispatch is by query TEXT, never by call order — the same discipline the
    tombstone fixture documents, and for the same reason: a fixture keyed on order
    silently re-assigns every later answer the moment a query is added.
    """
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=NODE)

    async def _fetch(query, *args):
        if "catalogue_size" in query:
            if membership_error is not None:
                raise membership_error
            # CANONICAL: the catalogue holds this code. The degraded path must land
            # on the same answer, which is what makes the two indistinguishable to a
            # client and is exactly the property under test.
            return [{"catalogue_size": 1563, "canonical_rows": 1}]
        if "relationship_type = 'REQUIRES'" in query:
            return list(REQUIRES_ROWS)
        if "BELONGS_TO" in query:
            if sibling_error is not None:
                raise sibling_error
            return [{"source_entity_id": s} for s in siblings]
        return []

    conn.fetch = AsyncMock(side_effect=_fetch)
    conn.fetchval = AsyncMock(return_value="sektor:M")

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
# GUILT — a server-side catalogue fault costs the verdict, not the page
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        asyncpg.UndefinedTableError("relation \"kbli_documents\" does not exist"),
        asyncpg.InsufficientPrivilegeError("permission denied for table kbli_documents"),
        asyncpg.QueryCanceledError("canceling statement due to statement timeout"),
    ],
    ids=["undefined_table", "permission_denied", "statement_timeout"],
)
def test_an_unreadable_catalogue_still_serves_the_code(make_client, error):
    """Every shape of "the server refused to answer" degrades to the old answer."""
    client = make_client(membership_error=error)
    response = client.get("/kbli-notebook/inspect/74100")

    assert response.status_code == 200, response.text
    body = response.json()
    # The pre-tombstone answer, unchanged — this is the whole point.
    assert body["licensing_status"] == "REGULATED"
    assert body["licensing_status"] != PHANTOM_LICENSING_STATUS
    assert not body["title"].endswith(TOMBSTONE_TITLE_SUFFIX)
    assert body["description"] != TOMBSTONE_DESCRIPTION


def test_an_unreadable_sibling_query_omits_the_list_and_keeps_the_page(make_client):
    """`_canonical_siblings` promises silence; now it keeps that promise."""
    client = make_client(sibling_error=asyncpg.UndefinedTableError("boom"))
    response = client.get("/kbli-notebook/inspect/74100")

    assert response.status_code == 200, response.text
    assert response.json()["related_codes"] == []


def test_the_related_list_is_still_populated_when_the_query_works(make_client):
    """Innocence for the test above: it must fail for the ERROR, not for the code."""
    client = make_client()
    response = client.get("/kbli-notebook/inspect/74100")

    assert response.status_code == 200, response.text
    assert response.json()["related_codes"] == ["74110", "74190"]


# --------------------------------------------------------------------------
# INNOCENCE — a connection fault is NOT swallowed; the client is told to retry
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        asyncpg.InterfaceError("connection is closed"),
        ConnectionResetError("Connection reset by peer"),
    ],
    ids=["interface_error", "connection_reset"],
)
def test_a_connection_fault_is_not_swallowed_into_a_degraded_page(make_client, error):
    """A stale pool must still earn its 503, not a page built from a degraded read.

    This is the asymmetry the cure turns on. `asyncpg.PostgresError` is the server
    declining to answer and is safely degradable; `InterfaceError`/`ConnectionResetError`
    mean the connection itself is gone, the router expires the pool and answers 503 with
    `Retry-After`, and a client that retries gets a real answer. Catching these here too
    would be one tidier `except` and would cost the client that retry forever.
    """
    client = make_client(membership_error=error)
    response = client.get("/kbli-notebook/inspect/74100")

    assert response.status_code == 503, response.text
    assert response.headers.get("Retry-After") == "5"


# --------------------------------------------------------------------------
# The service in isolation — the router is not the only caller it will ever have
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_none_on_a_server_error_so_the_verdict_is_unknown():
    conn = MagicMock()
    conn.fetch = AsyncMock(side_effect=asyncpg.UndefinedTableError("gone"))

    assert await fetch_catalogue_membership(conn, "74100") is None


@pytest.mark.asyncio
async def test_fetch_lets_a_connection_error_propagate():
    conn = MagicMock()
    conn.fetch = AsyncMock(side_effect=asyncpg.InterfaceError("connection is closed"))

    with pytest.raises(asyncpg.InterfaceError):
        await fetch_catalogue_membership(conn, "74100")


@pytest.mark.asyncio
async def test_fetch_logs_the_fault_rather_than_swallowing_it_silently(caplog):
    """A catalogue that has stopped answering is an operational fact somebody must see.

    Without this, a tombstone cure that quietly stopped tombstoning would be
    indistinguishable from a healthy day — the endpoint would keep answering 200 and
    nothing would ever say the oracle had gone dark.
    """
    conn = MagicMock()
    conn.fetch = AsyncMock(side_effect=asyncpg.UndefinedTableError("relation gone"))

    with caplog.at_level("WARNING"):
        await fetch_catalogue_membership(conn, "74100")

    assert [r for r in caplog.records if r.levelname == "WARNING"], caplog.text
    # The CODE must be in the rendered message — an alert that cannot name which code
    # went dark is an alert nobody can act on.
    assert "74100" in caplog.text
    assert "UndefinedTableError" in caplog.text
