"""A code KBLI 2025 does not contain must not be answered like one that exists.

`inspect_kbli` resolves against `kg_nodes`, and the graph carries ten KBLI-2020
numbers the 2025 revision dropped. Until 2026-09-19 each was served as an ordinary
200: `74100` came back `licensing_status: REGULATED` with a licence list, `26120`
with a full semiconductor description. Nothing in the payload said the number
cannot be registered.

These tests drive the endpoint, not the predicate — the verdict has its own unit
tests in `tests/unit/services/test_kbli_catalogue_membership.py`. What is proven
here is that the verdict SURVIVES the wiring: the response contract, the PMA
validator, the cache key, and the `related_codes` query that used to hand a
phantom to 38 real codes.

The fixture is built so every assertion DISCRIMINATES. The phantom and the
canonical node are fed the SAME graph rows — the same licence, the same cost, the
same located ownership tuple — because a fake that answers `[]` to everything
would let a disabled tombstone branch pass the tombstone's own tests. The two
codes differ in one thing only: whether the catalogue contains them.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.kbli_notebook as kbli_notebook_module
from backend.app.dependencies import get_optional_database_pool, get_search_service
from backend.services.kbli_catalogue_membership import (
    PHANTOM_LICENSING_STATUS,
    TOMBSTONE_DESCRIPTION,
    TOMBSTONE_RISK_PROFILE,
    TOMBSTONE_TITLE_SUFFIX,
)

# A located PMA tuple: `disclose_pma` publishes an ownership verdict only for a
# complete one, so this is what it takes to make the endpoint SAY something about
# foreign ownership. On a phantom code that claim is about an activity nobody can
# register today — which is why the tombstone must not inherit it.
LOCATED_PMA = {
    "pma_status": "TERBUKA",
    "pma_max_asing": 100,
    "pma_verification_status": "located",
    "pma_official_basis": "Perpres 10/2021 Lampiran III",
    "pma_source_vintage": "2021",
    # The cap is published only with this marker (`_public_pma_cap`): a bare
    # number is not self-authenticating.
    "pma_cap_verified": True,
}

# `74100` on prod: a KBLI-2020 node the 2025 catalogue does not carry. Keep the row
# at the shape `SELECT *` emits, not at the subset today's reader touches (W114).
PHANTOM_NODE = {
    "entity_id": "kbli:74100",
    "name": "Aktivitas Perancangan Khusus",
    "description": "Aktivitas perancangan khusus.",
    "properties": {
        "uraian": "Aktivitas perancangan khusus.",
        "licensing_status": "REGULATED",
        **LOCATED_PMA,
    },
}

CANONICAL_NODE = {
    "entity_id": "kbli:74120",
    "name": "Aktivitas Desain Interior",
    "description": "Desain interior.",
    "properties": {
        "uraian": "Desain interior.",
        "licensing_status": "REGULATED",
        **LOCATED_PMA,
    },
}

# What the graph hangs off both codes — and what the endpoint rendered for the
# phantom before this cure.
REQUIRES_ROWS = [
    {
        "entity_id": "perizinan:izin_usaha_industri",
        "name": "Izin Usaha Industri",
        "target_entity_type": "perizinan",
        "properties": {"skala_usaha": ["Besar"], "kategori_risiko": "Tinggi"},
        "edge_props": None,
    },
    {
        "entity_id": "biaya:pnbp_74100",
        "name": "Rp 5.000.000",
        "target_entity_type": "biaya",
        "properties": None,
        "edge_props": None,
    },
]

FULL_CATALOGUE = 1563


def _membership(size=FULL_CATALOGUE, canonical=0):
    return [{"catalogue_size": size, "canonical_rows": canonical}]


def _pool(
    *,
    membership,
    node=PHANTOM_NODE,
    requires=REQUIRES_ROWS,
    siblings=(),
    sector="sektor:M",
    calls=None,
):
    """A connection that answers the endpoint's queries, dispatching on the SQL.

    Dispatch by query text, never by call order: the tombstone ADDED a query, and a
    fixture keyed on order would have silently re-assigned every later answer.
    """
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=node)

    async def _fetch(query, *args):
        if calls is not None:
            calls.append((query, args))
        if "catalogue_size" in query:
            return membership
        if "relationship_type = 'REQUIRES'" in query:
            return list(requires)
        if "BELONGS_TO" in query:
            return [{"source_entity_id": s} for s in siblings]
        return []

    conn.fetch = AsyncMock(side_effect=_fetch)
    conn.fetchval = AsyncMock(return_value=sector)

    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return pool


@pytest.fixture
def make_client():
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
        client = TestClient(app, raise_server_exceptions=False)
        client._patches = stack
        client._cache = cache
        return client

    return _make


def _get(client, code="74100"):
    response = client.get(f"/kbli-notebook/inspect/{code}")
    assert response.status_code == 200, response.text
    return response.json()


def _stop(client):
    for p in client._patches:
        p.stop()


# --------------------------------------------------------------------------
# GUILT — the phantom is buried, and the client is told so
# --------------------------------------------------------------------------


def test_a_phantom_code_is_answered_with_a_tombstone(make_client):
    client = make_client(membership=_membership())
    try:
        body = _get(client)
    finally:
        _stop(client)

    assert body["title"].endswith(TOMBSTONE_TITLE_SUFFIX)
    assert body["description"] == TOMBSTONE_DESCRIPTION
    assert body["licensing_status"] == PHANTOM_LICENSING_STATUS
    assert body["risk_profile"] == TOMBSTONE_RISK_PROFILE
    assert body["sector"] == "N/A"


def test_the_tombstone_asserts_no_licence_and_no_requirement(make_client):
    """The old answer's real harm: a licence to obtain for an unregistrable code.

    The graph still holds `Izin Usaha Industri` for `74100`; it describes an
    activity under the OLD numbering, and rendering it here would be the same
    error one layer down.
    """
    client = make_client(membership=_membership())
    try:
        body = _get(client)
    finally:
        _stop(client)

    assert body["licenses"] == []
    assert body["related_requirements"] == {}
    assert body["expert_legal"] is None


def test_the_tombstone_withholds_every_ownership_claim(make_client):
    """The node carries a LOCATED tuple; the tombstone must still say nothing.

    A published `TERBUKA / 100%` about a code that cannot be registered is a
    foreign-ownership claim with no subject.
    """
    client = make_client(membership=_membership())
    try:
        body = _get(client)
    finally:
        _stop(client)

    assert body["pma_status"] == "NOT_VERIFIED"
    assert body["pma_verification_status"] == "declared_gap"
    assert body["pma_max_asing"] is None
    assert body["pma_cap_verified"] is False


def test_the_tombstone_keeps_the_original_name_visible(make_client):
    """The client typed a number for a reason; the suffix is added, not a rewrite."""
    client = make_client(membership=_membership())
    try:
        body = _get(client)
    finally:
        _stop(client)

    assert body["title"] == f"{PHANTOM_NODE['name']}{TOMBSTONE_TITLE_SUFFIX}"


def test_the_tombstone_still_points_at_real_neighbours(make_client):
    """The one thing worth keeping: where to go next."""
    client = make_client(membership=_membership(), siblings=["kbli:74120", "kbli:74901"])
    try:
        body = _get(client)
    finally:
        _stop(client)

    assert body["related_codes"] == ["74120", "74901"]


def test_the_tombstone_is_cached_under_the_bumped_key(make_client):
    """v7, not v6: the old entries are WRONG about existence and must be evicted."""
    client = make_client(membership=_membership())
    try:
        _get(client)
        cache = client._cache
    finally:
        _stop(client)

    key = cache.set.call_args.args[0]
    assert key == "kbli_inspect_v7_74100", key


# --------------------------------------------------------------------------
# INNOCENCE — a code the catalogue DOES contain keeps every answer it had
# --------------------------------------------------------------------------


def test_a_canonical_code_still_gets_its_licence_cost_and_ownership_verdict(
    make_client,
):
    """Same node shape, same graph rows, opposite verdict.

    This is the pair that makes the tests above mean something: if the membership
    test convicted everything, this one would go silent.
    """
    client = make_client(membership=_membership(canonical=1), node=CANONICAL_NODE)
    try:
        body = _get(client, "74120")
    finally:
        _stop(client)

    assert body["title"] == CANONICAL_NODE["name"]
    assert TOMBSTONE_TITLE_SUFFIX not in body["title"]
    assert body["licensing_status"] == "REGULATED"
    assert body["sector"] == "M"
    assert [lic["type"] for lic in body["licenses"]] == ["Izin Usaha Industri"]
    assert body["related_requirements"] == {"costs": ["Rp 5.000.000"]}
    assert body["pma_status"] == "TERBUKA"
    assert body["pma_max_asing"] == 100


@pytest.mark.parametrize("size", [0, 3, 999])
def test_a_catalogue_below_the_floor_never_buries_a_code(make_client, size):
    """The failure that would cost 1,559 codes instead of curing ten.

    A truncated or unreadable `kbli_documents` must leave the endpoint exactly as
    it was — the phantom keeps being served, which is the cheaper of the two
    errors and the direction this guard fails in on purpose.
    """
    client = make_client(membership=_membership(size=size))
    try:
        body = _get(client)
    finally:
        _stop(client)

    assert body["licensing_status"] == "REGULATED"
    assert TOMBSTONE_TITLE_SUFFIX not in body["title"]


def test_a_connection_that_cannot_answer_the_membership_query_changes_nothing(
    make_client,
):
    """Every pre-existing endpoint fixture answers `[]` to an unknown query.

    That must mean UNKNOWN — silence is not a finding of absence — which is also
    why the tests in `test_kbli_inherited_licensing_reaches_the_model.py` needed
    no edit.
    """
    client = make_client(membership=[])
    try:
        body = _get(client)
    finally:
        _stop(client)

    assert body["licensing_status"] == "REGULATED"
    assert TOMBSTONE_TITLE_SUFFIX not in body["title"]


def test_a_code_with_no_node_at_all_is_still_a_404(make_client):
    """The tombstone answers `in the graph, absent from the catalogue`.

    A number that is in neither keeps the 404 it always had.
    """
    client = make_client(membership=_membership(), node=None)
    try:
        response = client.get("/kbli-notebook/inspect/99999")
    finally:
        _stop(client)

    assert response.status_code == 404, response.text
    assert TOMBSTONE_TITLE_SUFFIX not in response.text


# --------------------------------------------------------------------------
# The sibling query — the second face of the same defect
# --------------------------------------------------------------------------


def test_the_phantom_exclusion_is_applied_inside_the_sql(make_client):
    """Measured: 38 real codes were offering a phantom under `related_codes`.

    Filtering them out in Python after the fetch would be a different fix — the
    `LIMIT 6` is spent by Postgres, so a dropped row silently COSTS A SLOT instead
    of being replaced by a real sibling.
    """
    calls: list = []
    client = make_client(membership=_membership(canonical=1), node=CANONICAL_NODE, calls=calls)
    try:
        _get(client, "74120")
    finally:
        _stop(client)

    issued = [(q, a) for q, a in calls if "BELONGS_TO" in q]
    assert issued, "the endpoint issued no sibling query at all"
    query, args = issued[0]
    assert "EXISTS" in query, query
    assert query.index("EXISTS") < query.index("LIMIT"), query
    assert PHANTOM_LICENSING_STATUS in args, args


async def test_canonical_siblings_asks_for_the_same_sector_and_prefix():
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value="sektor:M")
    conn.fetch = AsyncMock(return_value=[{"source_entity_id": "kbli:74120"}])

    result = await kbli_notebook_module._canonical_siblings(conn, "74100")

    assert result == ["74120"]
    args = conn.fetch.call_args.args
    assert args[1] == "sektor:M"
    assert args[2] == "kbli:74%"
    assert args[3] == "kbli:74100"
    assert args[4] == PHANTOM_LICENSING_STATUS


async def test_canonical_siblings_without_a_sector_asks_nothing():
    """INNOCENCE — no sector edge means no neighbours, not an unfiltered query."""
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])

    assert await kbli_notebook_module._canonical_siblings(conn, "74100") == []
    conn.fetch.assert_not_called()
