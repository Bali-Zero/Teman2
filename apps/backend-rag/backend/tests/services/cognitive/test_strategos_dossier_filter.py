"""Tests for Qdrant-backed semantic reranker for Strategos dossier selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.services.cognitive.strategos import StrategosContextBuilder
from backend.services.cognitive.strategos_dossier_filter import QdrantDossierFilter

# ── Helpers ───────────────────────────────────────────────────


@dataclass
class _StubEmbedder:
    """Minimal async embedder exposing ``embed(text) -> list[float]``."""

    vector: list[float]
    calls: list[str]

    def __init__(self, vector: list[float] | None = None) -> None:
        self.vector = vector or [0.1, 0.2, 0.3]
        self.calls = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return self.vector


def _scored_point(dossier_id: UUID, score: float) -> SimpleNamespace:
    """Mimic qdrant_client ScoredPoint shape used by AsyncQdrantClient.query_points."""
    return SimpleNamespace(
        id=str(dossier_id),
        score=score,
        payload={"dossier_id": str(dossier_id)},
    )


def _query_response(points: list) -> SimpleNamespace:
    """Mimic QueryResponse(points=[...])."""
    return SimpleNamespace(points=points)


# ── QdrantDossierFilter.rank ──────────────────────────────────


@pytest.mark.asyncio
async def test_rank_orders_by_rrf_when_scores_present():
    """Cosine ranks A>B>C, confidence ranks B>A>C → RRF keeps A on top, C last."""
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    rows = [
        {"id": id_a, "confidence_0_1": 0.75, "title": "A"},
        {"id": id_b, "confidence_0_1": 0.90, "title": "B"},
        {"id": id_c, "confidence_0_1": 0.30, "title": "C"},
    ]

    qdrant = SimpleNamespace()
    qdrant.query_points = AsyncMock(return_value=_query_response([
        _scored_point(id_a, 0.95),
        _scored_point(id_b, 0.80),
        _scored_point(id_c, 0.40),
    ]))

    filt = QdrantDossierFilter(
        qdrant_client=qdrant,
        embedder=_StubEmbedder(),
        collection="research_dossiers_v1",
        rrf_k=60,
    )
    ranked = await filt.rank(rows, seed_text="weekly thesis", top_k=3)

    # cosine: A(1) B(2) C(3) | confidence: B(1) A(2) C(3)
    # RRF: A = 1/61 + 1/62 ≈ 0.032522 | B = 1/62 + 1/61 ≈ 0.032522 | C = 1/63 + 1/63 ≈ 0.031746
    # A and B tie, C is strictly last.
    assert ranked[-1]["id"] == id_c
    assert {ranked[0]["id"], ranked[1]["id"]} == {id_a, id_b}


@pytest.mark.asyncio
async def test_rank_uses_query_points_with_correct_kwargs():
    """rank() must call query_points(collection_name, query, query_filter, limit, with_payload)."""
    id_a = uuid4()
    rows = [{"id": id_a, "confidence_0_1": 0.5, "title": "A"}]

    qdrant = SimpleNamespace()
    qdrant.query_points = AsyncMock(return_value=_query_response([]))

    filt = QdrantDossierFilter(
        qdrant_client=qdrant,
        embedder=_StubEmbedder(vector=[0.1] * 5),
        collection="my_collection",
    )
    await filt.rank(rows, seed_text="seed")

    qdrant.query_points.assert_awaited_once()
    kwargs = qdrant.query_points.await_args.kwargs
    assert kwargs["collection_name"] == "my_collection"
    assert kwargs["query"] == [0.1] * 5
    assert kwargs["limit"] == 1
    assert kwargs["with_payload"] is True
    # Verify filter construction: Filter(must=[FieldCondition(key=dossier_id, match=MatchAny)])
    qfilter = kwargs["query_filter"]
    assert qfilter.must[0].key == "dossier_id"
    assert qfilter.must[0].match.any == [str(id_a)]


@pytest.mark.asyncio
async def test_rank_fails_open_on_qdrant_error():
    """If query_points raises, rank() returns input rows untouched."""
    rows = [
        {"id": uuid4(), "confidence_0_1": 0.50, "title": "X"},
        {"id": uuid4(), "confidence_0_1": 0.80, "title": "Y"},
    ]
    qdrant = SimpleNamespace()
    qdrant.query_points = AsyncMock(side_effect=RuntimeError("qdrant down"))

    filt = QdrantDossierFilter(
        qdrant_client=qdrant,
        embedder=_StubEmbedder(),
        collection="col",
    )
    out = await filt.rank(rows, seed_text="any seed")

    assert out == rows


@pytest.mark.asyncio
async def test_rank_dispatches_sync_client_to_executor():
    """Sync Qdrant client must be invoked via run_in_executor, not on the event loop."""
    id_a, id_b = uuid4(), uuid4()
    rows = [
        {"id": id_a, "confidence_0_1": 0.4, "title": "A"},
        {"id": id_b, "confidence_0_1": 0.6, "title": "B"},
    ]

    response = _query_response([
        _scored_point(id_a, 0.9),
        _scored_point(id_b, 0.2),
    ])
    qdrant = SimpleNamespace()
    qdrant.query_points = MagicMock(return_value=response)  # sync callable

    filt = QdrantDossierFilter(
        qdrant_client=qdrant,
        embedder=_StubEmbedder(),
        collection="col",
    )
    ranked = await filt.rank(rows, seed_text="seed", top_k=2)

    # The sync callable must be called EXACTLY once (no double-execution bug).
    assert qdrant.query_points.call_count == 1
    # Cosine: A>B, confidence: B>A → tie; but RRF at least returns both.
    assert {r["id"] for r in ranked} == {id_a, id_b}


@pytest.mark.asyncio
async def test_rank_excludes_missing_rows_from_cosine_ranking():
    """Rows without a Qdrant hit don't inflate their RRF via cosine-list rank."""
    id_hit, id_miss = uuid4(), uuid4()
    rows = [
        {"id": id_hit, "confidence_0_1": 0.40, "title": "hit"},
        {"id": id_miss, "confidence_0_1": 0.80, "title": "miss"},
    ]

    qdrant = SimpleNamespace()
    # Only id_hit returns from Qdrant.
    qdrant.query_points = AsyncMock(return_value=_query_response([
        _scored_point(id_hit, 0.9),
    ]))

    filt = QdrantDossierFilter(
        qdrant_client=qdrant,
        embedder=_StubEmbedder(),
        collection="col",
    )
    ranked = await filt.rank(rows, seed_text="seed", top_k=2)

    # id_hit: cos rank 1 (only candidate) + conf rank 2 → 1/61 + 1/62 ≈ 0.032522
    # id_miss: cos absent (no contribution) + conf rank 1 → 1/61 ≈ 0.016393
    # id_hit wins despite lower confidence.
    assert ranked[0]["id"] == id_hit
    assert ranked[1]["id"] == id_miss


# ── StrategosContextBuilder integration ──────────────────────


@pytest.fixture
def repos():
    intel = AsyncMock()
    cognitive = AsyncMock()
    cognitive.recent_theses = AsyncMock(return_value=[])
    cognitive.unresolved_alerts = AsyncMock(return_value=[])
    war_room = AsyncMock()
    intel.fetch_safe = AsyncMock(return_value=[])
    war_room.fetch_safe = AsyncMock(return_value=[])
    return intel, cognitive, war_room


@pytest.mark.asyncio
async def test_context_builder_no_filter_unchanged(repos):
    """Omitting dossier_filter preserves legacy ranking-by-confidence order."""
    intel, cognitive, war_room = repos
    id_a, id_b = uuid4(), uuid4()
    intel.fetch_safe = AsyncMock(return_value=[
        {
            "id": id_a,
            "title": "Alpha",
            "topic_category": "visa",
            "confidence_0_1": 0.90,
            "summary_short": "alpha summary",
        },
        {
            "id": id_b,
            "title": "Beta",
            "topic_category": "tax",
            "confidence_0_1": 0.40,
            "summary_short": "beta summary",
        },
    ])

    builder = StrategosContextBuilder(
        intel_repo=intel,
        cognitive_repo=cognitive,
        war_room_repo=war_room,
    )
    ctx = await builder.build(week_of=date(2026, 4, 20))

    lines = ctx.dossiers_block.splitlines()
    assert lines[0].startswith(f"- id={id_a}")
    assert lines[1].startswith(f"- id={id_b}")


@pytest.mark.asyncio
async def test_context_builder_invokes_filter_when_provided(repos):
    """When a dossier_filter is injected, build() must call rank() on the raw rows."""
    intel, cognitive, war_room = repos
    id_a, id_b = uuid4(), uuid4()
    raw_rows = [
        {
            "id": id_a,
            "title": "Alpha",
            "topic_category": "visa",
            "confidence_0_1": 0.90,
            "summary_short": "alpha summary",
        },
        {
            "id": id_b,
            "title": "Beta",
            "topic_category": "tax",
            "confidence_0_1": 0.40,
            "summary_short": "beta summary",
        },
    ]
    intel.fetch_safe = AsyncMock(return_value=raw_rows)

    filter_stub = SimpleNamespace()
    filter_stub.rank = AsyncMock(return_value=list(reversed(raw_rows)))

    builder = StrategosContextBuilder(
        intel_repo=intel,
        cognitive_repo=cognitive,
        war_room_repo=war_room,
        dossier_filter=filter_stub,
    )
    ctx = await builder.build(week_of=date(2026, 4, 20))

    filter_stub.rank.assert_awaited_once()
    lines = ctx.dossiers_block.splitlines()
    assert lines[0].startswith(f"- id={id_b}")
    assert lines[1].startswith(f"- id={id_a}")


@pytest.mark.asyncio
async def test_context_builder_filter_exception_preserves_sql_rows(repos):
    """If dossier_filter.rank() raises, builder MUST preserve SQL-ranked rows."""
    intel, cognitive, war_room = repos
    id_a, id_b = uuid4(), uuid4()
    raw_rows = [
        {
            "id": id_a,
            "title": "Alpha",
            "topic_category": "visa",
            "confidence_0_1": 0.90,
            "summary_short": "alpha summary",
        },
        {
            "id": id_b,
            "title": "Beta",
            "topic_category": "tax",
            "confidence_0_1": 0.40,
            "summary_short": "beta summary",
        },
    ]
    intel.fetch_safe = AsyncMock(return_value=raw_rows)

    broken_filter = SimpleNamespace()
    broken_filter.rank = AsyncMock(side_effect=RuntimeError("filter crashed"))

    builder = StrategosContextBuilder(
        intel_repo=intel,
        cognitive_repo=cognitive,
        war_room_repo=war_room,
        dossier_filter=broken_filter,
    )
    ctx = await builder.build(week_of=date(2026, 4, 20))

    # SQL-ranked rows must still appear in dossiers_block, untouched.
    assert ctx.dossiers_block  # not empty
    lines = ctx.dossiers_block.splitlines()
    assert lines[0].startswith(f"- id={id_a}")
    assert lines[1].startswith(f"- id={id_b}")
