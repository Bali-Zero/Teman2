"""The rule is correct in `kbli_pp28_provenance`; this proves it REACHES a client.

`inspect_kbli` is what the WhatsApp/MCP model reads. A predicate that returns
the right answer to nobody is the shape this repo keeps re-learning: the field
has to survive the wiring, the `bool(licenses)` gate, and the response cache.

So these tests drive the endpoint itself through a fake pool, and assert on the
JSON a consumer actually receives — including the case an adversarial review
raised, where a cache entry written before the field existed would keep the
endpoint silent for up to 30 days.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.kbli_notebook as kbli_notebook_module
from backend.app.dependencies import get_optional_database_pool, get_search_service

# The endpoint's real query is `SELECT n.*, ... FROM kg_nodes n JOIN kg_edges e`,
# so every key `kg_nodes` has reaches this row — `entity_id` included. Keep this
# fake at the shape the SOURCE emits, not at the subset today's reader happens to
# touch: this fixture was first written against a reader that never looked at
# `entity_id`, and the very next change to the endpoint (the permit-name verdict,
# which classifies on it) turned all four tests into `KeyError: 'entity_id'`. A
# fake trimmed to its current reader is a trap armed for the next one (W114).
LICENSE_ROW = {
    "entity_id": "perizinan:izin_industri_alpalhan",
    "name": "Industri Kelaikan Produksi Alat Peralatan Pertahanan",
    "target_entity_type": "perizinan",
    "properties": {"skala_usaha": ["Besar"], "kategori_risiko": "Tinggi"},
    "edge_props": None,
}


def _pool(node_props: dict, license_rows: list[dict]):
    """A pool whose connection answers the endpoint's four queries."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "name": "VIDEO GAME DEVELOPMENT (AKTIVITAS PENGEMBANGAN VIDEO GAME)",
            "description": "Pengembangan video game.",
            "properties": node_props,
        }
    )

    async def _fetch(query, *args):
        # Dispatch on the query, not on call order: an added query upstream
        # would otherwise silently shift which answer each call receives.
        if "relationship_type = 'REQUIRES'" in query:
            return license_rows
        return []

    conn.fetch = AsyncMock(side_effect=_fetch)
    conn.fetchval = AsyncMock(return_value=None)

    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return pool


@pytest.fixture
def make_client():
    def _make(node_props: dict, license_rows: list[dict], cached=None):
        app = FastAPI()
        app.include_router(kbli_notebook_module.router)
        app.dependency_overrides[get_search_service] = lambda: MagicMock(embedder=MagicMock())
        app.dependency_overrides[get_optional_database_pool] = lambda: _pool(
            node_props, license_rows
        )
        cache = MagicMock()
        cache.get = AsyncMock(return_value=cached)
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
        client = TestClient(app, raise_server_exceptions=False)
        client._patches = stack  # torn down by the test
        client._cache = cache
        return client

    return _make


def _get(client, code="62110"):
    response = client.get(f"/kbli-notebook/inspect/{code}")
    assert response.status_code == 200, response.text
    return response.json()


def _stop(client):
    for p in client._patches:
        p.stop()


# --------------------------------------------------------------------------
# GUILT — the note reaches the consumer
# --------------------------------------------------------------------------


def test_a_carried_code_tells_the_model_whose_licences_these_are(make_client):
    client = make_client(
        {"pp28_sources": ["62011", "62019", "62015", "62013", "62012"]},
        [LICENSE_ROW],
    )
    try:
        body = _get(client)
        assert body["licensing_content_inherited_from"] == [
            "62011",
            "62019",
            "62015",
            "62013",
            "62012",
        ]
        note = body["licensing_note"]
        assert note and "62011" in note and "62012" in note
        # The licences are NOT withheld — this surface can qualify, so it does.
        assert len(body["licenses"]) == 1
    finally:
        _stop(client)


# --------------------------------------------------------------------------
# INNOCENCE — three ways silence is the correct answer
# --------------------------------------------------------------------------


def test_a_self_sourced_code_carries_no_note(make_client):
    client = make_client({"pp28_sources": ["62110"]}, [LICENSE_ROW])
    try:
        body = _get(client)
        assert body["licensing_content_inherited_from"] is None
        assert body["licensing_note"] is None
    finally:
        _stop(client)


def test_an_unsynced_node_carries_no_note(make_client):
    """Every node until `kg_kbli_resync.py --apply` runs. Silence, not a claim."""
    client = make_client({}, [LICENSE_ROW])
    try:
        body = _get(client)
        assert body["licensing_content_inherited_from"] is None
        assert body["licensing_note"] is None
    finally:
        _stop(client)


def test_a_carried_code_with_no_licences_rendered_carries_no_note(make_client):
    """A sentence about "the licences listed" on a response listing none."""
    client = make_client({"pp28_sources": ["62011"]}, [])
    try:
        body = _get(client)
        assert body["licenses"] == []
        assert body["licensing_note"] is None
    finally:
        _stop(client)


# --------------------------------------------------------------------------
# THE CACHE — raised by an adversarial review, and it bites without the bump
# --------------------------------------------------------------------------


def test_the_cache_key_is_versioned_past_the_payload_that_lacked_the_field(
    make_client,
):
    """A v2 entry validates on read (the fields default to None), so a carried
    code would answer WITHOUT the note until its TTL expired — up to 30 days.
    The endpoint must not read entries written before the field existed."""
    client = make_client(
        {"pp28_sources": ["62011", "62019"]},
        [LICENSE_ROW],
    )
    try:
        body = _get(client)
        assert body["licensing_note"] is not None
        requested = client._cache.get.await_args.args[0]
        assert requested == "kbli_inspect_v5_62110", requested
        assert "_v2_" not in requested
    finally:
        _stop(client)


def test_a_current_version_cache_hit_is_still_served_from_cache(make_client):
    """INNOCENCE for the bump: it must invalidate the OLD generation only, not
    disable caching. A current-generation hit short-circuits the DB entirely."""
    cached = {
        "code": "62110",
        "title": "cached title",
        "description": "cached",
        "pma_status": "TERBUKA",
        "licensing_status": "REGULATED",
        "sector": "J",
        "risk_profile": "Tinggi",
        "licenses": [],
        "licensing_content_inherited_from": ["62011"],
        "licensing_note": "cached note",
    }
    client = make_client({"pp28_sources": ["62011"]}, [LICENSE_ROW], cached=cached)
    try:
        body = _get(client)
        assert body["title"] == "cached title"
        assert body["licensing_note"] == "cached note"
    finally:
        _stop(client)
