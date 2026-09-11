"""B1.1 — the score contract crossing tests.

Each case follows the EXACT numeric `score` and its `score_kind` across one
hop of the pipeline: producer -> formatter/reranker -> source projection ->
package construction -> DLP/capping -> canonical serialization -> scorer
input. Numbers are taken from the MEASURED table
(evidence/2026-09/agent-nuzantara-backend-rag-b1-score-contract-107e45b6/measured-fusion-table.md),
never re-derived locally, per the build spec's own instruction.

Case numbering follows `B1-1-build-spec.md`'s "Crossing tests" list
(1-11). The last case is an addition, not in that list: an R2
backward-compat condition the staff room attached when it accepted R1/R2
(ack 2026-09-10T20:54:08Z) — `package_hash` is persisted and re-verified
across the deploy boundary, so a package sealed BEFORE this PR existed
must still verify after it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core import score_provenance
from backend.services.misc.result_formatter import format_search_results
from backend.services.rag.agentic import wa_package_builder as wpb_module
from backend.services.rag.agentic.wa_package_builder import ContextPackage
from backend.services.rag.reranker import CrossEncoderReranker
from backend.services.search.search_service import SearchService
from backend.tests.unit.services.rag.agentic.test_wa_package_builder import (
    VISA_QUERY,
    FakeRetriever,
    _visa_retriever,
)

# ============================================================================
# Fixtures for the search_service cases (8, 9) — mirrors
# test_search_service_comprehensive.py's fixture shape so a cache-hit /
# hybrid_search() call can run without touching a real Qdrant/embedder.
# ============================================================================


@pytest.fixture
def mock_qdrant_client() -> MagicMock:
    client = MagicMock()

    async def mock_search(*args, **kwargs):
        return {
            "ids": ["1"],
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
            "scores": [0.9],
            "total_found": 1,
        }

    client.search = mock_search
    return client


@pytest.fixture
def mock_embedder() -> MagicMock:
    embedder = MagicMock()
    embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
    embedder.provider = "openai"
    embedder.dimensions = 1536
    return embedder


@pytest.fixture
def search_service(mock_qdrant_client: MagicMock, mock_embedder: MagicMock) -> SearchService:
    with (
        patch("backend.core.embeddings.create_embeddings_generator", return_value=mock_embedder),
        patch("backend.core.qdrant_db.QdrantClient", return_value=mock_qdrant_client),
        patch("backend.services.search.search_service.CollectionManager") as mock_cm,
        patch("backend.services.search.search_service.ConflictResolver"),
        patch("backend.services.search.search_service.CulturalInsightsService"),
        patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
        patch("backend.services.ingestion.collection_health_service.CollectionHealthService"),
        patch("backend.services.search.search_service.CollectionWarmupService"),
    ):
        mock_cm_instance = MagicMock()
        mock_cm_instance.get_collection.return_value = mock_qdrant_client
        mock_cm.return_value = mock_cm_instance

        service = SearchService()
        service.embedder = mock_embedder
        service.collection_manager = mock_cm_instance
        return service


# ============================================================================
# Cases 1-3: hybrid RRF formatted (result_formatter.py:89 via the hybrid
# branch). Fusion values are the MEASURED formula (1/(2+rank0)), never
# re-derived — case 3 reuses the measured table's row 7 arithmetic directly
# (single-list rank0=4 -> 0.166667 -> formatted 0.545455).
# ============================================================================


def test_01_rank1_hybrid_single_list_formatted_and_kind() -> None:
    raw_results = {
        "ids": ["a"],
        "documents": ["doc a"],
        "metadatas": [{}],
        "distances": [0.5],
        "scores": [0.5],
        "search_type": "hybrid_rrf",
    }
    results = format_search_results(
        raw_results,
        collection_name="visa_oracle",
        score_kind=score_provenance.HYBRID_RRF_FORMATTED,
    )
    assert results[0]["score"] == 0.6667
    assert results[0]["score_kind"] == score_provenance.HYBRID_RRF_FORMATTED
    assert results[0]["score_raw"] == 0.5


def test_02_rank1_hybrid_both_lists_formatted_and_kind() -> None:
    raw_results = {
        "ids": ["a"],
        "documents": ["doc a"],
        "metadatas": [{}],
        "distances": [0.0],
        "scores": [1.0],
        "search_type": "hybrid_rrf",
    }
    results = format_search_results(
        raw_results,
        collection_name="visa_oracle",
        score_kind=score_provenance.HYBRID_RRF_FORMATTED,
    )
    assert results[0]["score"] == 1.0
    assert results[0]["score_kind"] == score_provenance.HYBRID_RRF_FORMATTED
    assert results[0]["score_raw"] == 1.0


def test_03_rank5_hybrid_one_list_formatted_and_kind() -> None:
    fusion = 0.166667  # MEASURED table row 7: single-list rank0=4, 1/(2+4)
    raw_results = {
        "ids": ["a"],
        "documents": ["doc a"],
        "metadatas": [{}],
        "distances": [1.0 - fusion],
        "scores": [fusion],
        "search_type": "hybrid_rrf",
    }
    results = format_search_results(
        raw_results,
        collection_name="visa_oracle",
        score_kind=score_provenance.HYBRID_RRF_FORMATTED,
    )
    assert results[0]["score"] == 0.5455
    assert results[0]["score_kind"] == score_provenance.HYBRID_RRF_FORMATTED
    assert results[0]["score_raw"] == fusion


# ============================================================================
# Case 4: dense fallback (result_formatter.py:89 via the dense branch /
# core/qdrant_db.py:1362's internal fallback).
# ============================================================================


@pytest.mark.parametrize(
    ("cosine", "expected_formatted"),
    [(0.0, 0.5), (0.5, 0.6667), (0.9, 0.9091)],
)
def test_04_dense_fallback_formatted_and_kind(cosine: float, expected_formatted: float) -> None:
    raw_results = {
        "ids": ["a"],
        "documents": ["doc a"],
        "metadatas": [{}],
        "distances": [1.0 - cosine],
        "scores": [cosine],
    }
    results = format_search_results(
        raw_results,
        collection_name="visa_oracle",
        score_kind=score_provenance.DENSE_FORMATTED,
    )
    assert results[0]["score"] == expected_formatted
    assert results[0]["score_kind"] == score_provenance.DENSE_FORMATTED
    assert results[0]["score_raw"] == cosine


# ============================================================================
# Case 5: reranked source. score_raw == the pre-rerank value == vector_score.
# ============================================================================


@pytest.mark.asyncio
async def test_05_reranked_kind_and_raw_equals_prior_score_and_vector_score() -> None:
    reranker = CrossEncoderReranker(enabled=True)
    reranker.compute_scores_async = AsyncMock(return_value=[0.95])

    docs = [{"text": "doc a", "score": 0.6667}]
    reranked = await reranker.rerank("query", docs, top_k=1)

    assert reranked[0]["score"] == 0.95
    assert reranked[0]["vector_score"] == 0.6667
    assert reranked[0]["score_kind"] == score_provenance.RERANKED
    assert reranked[0]["score_raw"] == 0.6667


# ============================================================================
# Case 6: curated synthetic. score_raw absent — nothing was consumed.
# ============================================================================


@pytest.mark.asyncio
async def test_06_curated_synthetic_chunk_kind_and_absent_raw() -> None:
    package = await wpb_module.build_context_package(
        query=VISA_QUERY,
        history=[],
        thread_epoch=0,
        retriever=_visa_retriever(),
        curated_qa_block="Curated answer text.",
    )
    curated = next(c for c in package.chunks if c["collection"] == "curated_qa")
    assert curated["score"] == 1.0
    assert curated["score_kind"] == score_provenance.CURATED_SYNTHETIC
    assert score_provenance.SCORE_RAW_KEY not in curated


# ============================================================================
# Case 7: a collection boost applied — the boosted NUMBER is unchanged from
# today (recomputed structurally from SearchConstants, not from a hardcoded
# literal) AND the kind survives the boost.
# ============================================================================


def test_07_collection_boost_preserves_number_and_kind() -> None:
    from backend.app.core.constants import SearchConstants

    raw_results = {
        "ids": ["a"],
        "documents": ["doc a"],
        "metadatas": [{}],
        "distances": [0.5],
        "scores": [0.5],
        "search_type": "hybrid_rrf",
    }
    boosted = format_search_results(
        raw_results,
        collection_name="bali_zero_pricing_hybrid",
        score_kind=score_provenance.HYBRID_RRF_FORMATTED,
    )
    base_score = 1 / (1 + 0.5)
    expected = round(
        min(SearchConstants.MAX_SCORE, base_score + SearchConstants.PRICING_SCORE_BOOST), 4
    )
    assert boosted[0]["score"] == expected
    assert boosted[0]["score_kind"] == score_provenance.HYBRID_RRF_FORMATTED
    assert boosted[0]["score_raw"] == 0.5


# ============================================================================
# Case 8: an `unknown` cache hit — a cached entry with no score_kind reads
# back as unknown, and no number moves.
# ============================================================================


@pytest.mark.asyncio
async def test_08_unknown_cache_hit_stamps_legacy_entries(search_service: SearchService) -> None:
    legacy_cached = {
        "query": "test",
        "collection": "visa_oracle",
        "total_results": 1,
        "search_type": "hybrid_rrf",
        "bm25_enabled": True,
        "results": [{"id": "a", "text": "doc", "metadata": {}, "score": 0.9}],
    }
    with patch("backend.core.cache.get_cache_service") as mock_cache_svc:
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=legacy_cached)
        mock_cache.set = AsyncMock()
        mock_cache._generate_key = MagicMock(return_value="test_key_08")
        mock_cache_svc.return_value = mock_cache

        result = await search_service.hybrid_search(query="test", user_level=1, limit=5)

    assert result["cache_hit"] is True
    assert result["results"][0]["score_kind"] == score_provenance.UNKNOWN
    assert result["results"][0]["score"] == 0.9


# ============================================================================
# Case 9 — NEGATIVE, must fail on origin/main: a dense fallback whose
# raw_results carries no `search_type` is labelled dense_formatted even
# though search_service.py:1142 still calls it "hybrid_rrf". The two
# disagree ON PURPOSE (R1) — score_kind comes from the caller's own branch
# (checked via the key's PRESENCE, never its value), the search_type lie is
# B2's to fix. On origin/main `score_kind` does not exist on a result dict
# at all, so this assertion cannot even be expressed there.
# ============================================================================


@pytest.mark.asyncio
async def test_09_dense_fallback_without_search_type_key_labelled_dense_formatted(
    search_service: SearchService,
) -> None:
    async def fake_hybrid_search(*, query_embedding, query_sparse, filter, limit, prefetch_limit):
        # Simulates core/qdrant_db.py:1362's internal fallback: a
        # dense-shaped dict that never sets "search_type" at all.
        return {
            "ids": ["1"],
            "documents": ["doc"],
            "metadatas": [{}],
            "distances": [0.1],
            "scores": [0.9],
            "total_found": 1,
        }

    mock_client = MagicMock()
    mock_client.hybrid_search = fake_hybrid_search
    search_service.collection_manager.get_collection.return_value = mock_client

    mock_bm25 = MagicMock()
    mock_bm25.generate_query_sparse_vector.return_value = {"indices": [1], "values": [0.5]}
    search_service._bm25_vectorizer = mock_bm25
    search_service._bm25_enabled = True

    with patch("backend.core.cache.get_cache_service") as mock_cache_svc:
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_cache._generate_key = MagicMock(return_value="test_key_09")
        mock_cache_svc.return_value = mock_cache

        result = await search_service.hybrid_search(query="test", user_level=1, limit=5)

    # The lie stays exactly as it was — B1 does NOT fix search_type (R1).
    assert result["search_type"] == "hybrid_rrf"
    # But score_kind tells the truth: this was a dense-shaped result.
    assert result["results"][0]["score_kind"] == score_provenance.DENSE_FORMATTED


def _formatter_backed_retriever() -> FakeRetriever:
    """A retriever whose hits are minted by the REAL formatter.

    Case 10 is a CROSSING test, so its inputs may not be hand-written dicts
    carrying a hand-written `score_kind`: that would assert the test's own
    imagination rather than the chain. These hits are produced by calling
    `format_search_results` exactly as `SearchService.hybrid_search` calls it
    on the hybrid branch — the same function, the same declared kind — so what
    the package builder receives here has the shape production hands it.

    The first draft of case 10 used the shared `_visa_retriever()` fake, whose
    hits declare no kind at all. It passed on key-presence alone while every
    source reached the scorer as UNKNOWN, which is the precise failure the
    strengthened assertion below exists to catch.
    """
    raw = {
        "ids": ["1", "2"],
        "documents": [
            "KITAS requires a sponsor letter and passport copy.",
            "Immigration law UU 6/2011 governs stay permits.",
        ],
        "metadatas": [{}, {}],
        # 1/(2+0) and 1/(2+1): first and second of ONE contributing list,
        # from the measured server-side RRF table.
        "distances": [1.0 - 0.5, 1.0 - (1.0 / 3.0)],
        "scores": [0.5, 1.0 / 3.0],
        "total_found": 2,
    }
    formatted = format_search_results(
        raw,
        "visa_oracle",
        primary_collection=None,
        query=VISA_QUERY,
        score_kind=score_provenance.HYBRID_RRF_FORMATTED,
    )
    return FakeRetriever({"visa_oracle": formatted})


# ============================================================================
# Case 10 — PROJECTION test (staff-room requirement 2): the list handed to
# calculate_evidence_score at wa_package_builder.py:594-598 carries
# score_kind on EVERY element. Fails if the projection is ever re-narrowed
# to {"score": ...} only.
# ============================================================================


@pytest.mark.asyncio
async def test_10_scorer_projection_carries_score_kind_on_every_element(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, list] = {}

    def fake_calculate_evidence_score(*, sources, context_gathered, query):
        captured["sources"] = sources
        return 0.5

    monkeypatch.setattr(wpb_module, "calculate_evidence_score", fake_calculate_evidence_score)

    await wpb_module.build_context_package(
        query=VISA_QUERY,
        history=[],
        thread_epoch=0,
        retriever=_formatter_backed_retriever(),
    )

    assert captured.get("sources"), "expected at least one source handed to the scorer"
    for source in captured["sources"]:
        assert score_provenance.SCORE_KIND_KEY in source
    # Presence alone is not enough: stamping every element UNKNOWN would also
    # satisfy the loop above while destroying the contract's whole point. At
    # least one element must carry a kind that a WRITER actually declared.
    declared = {
        source[score_provenance.SCORE_KIND_KEY] for source in captured["sources"]
    } - {score_provenance.UNKNOWN}
    assert declared, (
        "every source reached the scorer as UNKNOWN — the projection kept the key "
        "but the chain lost the provenance somewhere upstream"
    )
    # The kind is half the promise; `score_raw` is the other half, and it used
    # to die at this exact hop — the projection carried {score, score_kind}
    # only (Codex round 1, finding 10). Asserted by EXACT value, not presence:
    # these are the two fusion outputs `_formatter_backed_retriever` fed in,
    # so a projection that re-derived the number instead of carrying the
    # writer's own would not match.
    for source in captured["sources"]:
        assert score_provenance.SCORE_RAW_KEY in source
    assert {source[score_provenance.SCORE_RAW_KEY] for source in captured["sources"]} == {
        0.5,
        1.0 / 3.0,
    }


# ============================================================================
# Case 11: a printed real package from the fixture path shows every source
# with its kind (PR body illustration).
# ============================================================================


@pytest.mark.asyncio
async def test_11_real_package_prints_every_source_with_its_kind() -> None:
    package = await wpb_module.build_context_package(
        query=VISA_QUERY,
        history=[],
        thread_epoch=0,
        retriever=_visa_retriever(),
        curated_qa_block="Curated pricing note.",
    )
    lines = [
        f"  chunk[{i}] collection={chunk['collection']!r} score={chunk['score']} "
        f"score_kind={chunk['score_kind']} score_raw={chunk.get('score_raw')}"
        for i, chunk in enumerate(package.chunks)
    ]
    print("\n".join(["Real package sources (B1.1 crossing test #11):", *lines]))
    assert package.chunks
    for chunk in package.chunks:
        assert chunk["score_kind"] in score_provenance.SCORE_KINDS


# ============================================================================
# Case 12 (addition, R2 backward-compat condition — staff-room ack
# 2026-09-10T20:54:08Z, reiterated by the Dux): `package_hash` is
# persisted and RE-VERIFIED ACROSS THE DEPLOY BOUNDARY
# (services/integrations/wa_broker.py:468/691/885,
# app/routers/wa_broker.py:279, app/routers/wa_package.py:161,
# services/integrations/wa_codex_daemon.py:342) — so the question is not
# "does the new hash differ" but "does a package sealed BEFORE this PR
# still verify after it". `_canonical_wire`/`_package_hash` have no
# per-field allowlist (spec R2): they are content-agnostic
# `json.dumps(sort_keys=True)` over whatever they are given, so a stored
# dict lacking score_kind/score_raw must re-hash to its own original value,
# unchanged.
# ============================================================================


# Frozen 2026-09-11 by RUNNING the base sha 1d726045c9's own
# `_canonical_wire`/`_package_hash` in a throwaway checkout, on the inputs
# below, and pasting the results here as literals. They are the pre-PR
# oracle. Computing them with the CURRENT code instead would make the test
# tautological: a coherent change to BOTH the serializer and the digest
# would break every stored package while keeping the assertion green
# (Codex round 1, finding 8 — that is exactly what the first version did).
_BASE_SEALED_WIRE = (
    '{"chunks":[{"collection":"visa_oracle","score":0.7,'
    '"text":"legacy chunk, no score_kind"}],'
    '"evidence_inputs":{"abstain":false,"context_length":1,"dlp":false,'
    '"domain":"visa","evidence_score":0.5,"label_threshold":0.12},'
    '"history":[{"content":"hi","role":"user"}],"persona_digest":"pd",'
    '"pricing_block":null,"thread_epoch":1}'
)
_BASE_SEALED_DIGEST = "466643afc3c393d49fcaddd4a92f5f8be63d64e88dc351c6c90921edc84a4454"

_BASE_SEALED_HISTORY = [{"role": "user", "content": "hi"}]
_BASE_SEALED_CHUNKS = [
    {"collection": "visa_oracle", "text": "legacy chunk, no score_kind", "score": 0.7}
]
_BASE_SEALED_EVIDENCE_INPUTS = {
    "evidence_score": 0.5,
    "context_length": 1,
    "domain": "visa",
    "label_threshold": 0.12,
    "abstain": False,
    "dlp": False,
}


def test_a_package_sealed_before_score_kind_existed_still_verifies() -> None:
    """A package sealed by the BASE code — chunks with no score_kind/score_raw
    key at all — must still verify, and emit the same bytes, under this PR.

    `ContextPackage.__post_init__` (wa_package_builder.py :153-172) recomputes
    the wire and raises ValueError unless the digest matches, so constructing
    against the FROZEN base digest without raising is the verification the
    deploy boundary performs when it reloads a stored package.
    """
    assert score_provenance.SCORE_KIND_KEY not in _BASE_SEALED_CHUNKS[0]
    assert score_provenance.SCORE_RAW_KEY not in _BASE_SEALED_CHUNKS[0]

    package = ContextPackage(
        history=_BASE_SEALED_HISTORY,
        chunks=_BASE_SEALED_CHUNKS,
        pricing_block=None,
        persona_digest="pd",
        evidence_inputs=_BASE_SEALED_EVIDENCE_INPUTS,
        thread_epoch=1,
        package_hash=_BASE_SEALED_DIGEST,
    )
    assert package.package_hash == _BASE_SEALED_DIGEST
    # Not just "it verifies": the bytes this PR puts on the wire for a
    # pre-PR package are byte-identical to the ones the base emitted.
    assert package.wire_text() == _BASE_SEALED_WIRE


def test_the_frozen_base_digest_rejects_altered_bytes() -> None:
    """The companion to the test above, and the reason it means anything: the
    frozen digest must FAIL on content it does not cover. Without this, a
    __post_init__ that verified nothing would pass the compatibility test.
    """
    altered_chunks = [dict(_BASE_SEALED_CHUNKS[0], score=0.71)]
    with pytest.raises(ValueError, match="package_hash does not cover"):
        ContextPackage(
            history=_BASE_SEALED_HISTORY,
            chunks=altered_chunks,
            pricing_block=None,
            persona_digest="pd",
            evidence_inputs=_BASE_SEALED_EVIDENCE_INPUTS,
            thread_epoch=1,
            package_hash=_BASE_SEALED_DIGEST,
        )


# ============================================================================
# Case 13 (Codex round 1, finding 9 — BLOCKER): the ORDINARY search paths.
# `format_search_results` has five call sites in search_service.py and for
# the first version of this PR only ONE of them declared a kind, so
# `search()` and `_single_query_search()` — the reranker-skipped routes that
# reach the scorer through VectorSearchTool — shipped results of KNOWN dense
# origin stamped UNKNOWN. Case 13c is the counterweight: `search()`'s single
# formatter call is fed by THREE branches, and the fix must not sweep the
# hybrid one into "dense" while curing the two that are.
# ============================================================================


def _dense_raw() -> dict:
    return {
        "ids": ["1"],
        "documents": ["doc"],
        "metadatas": [{}],
        "distances": [0.1],
        "scores": [0.9],
        "total_found": 1,
    }


@pytest.mark.asyncio
async def test_13a_ordinary_search_dense_branch_declares_dense_formatted(
    search_service: SearchService,
) -> None:
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=_dense_raw())
    search_service.collection_manager.get_collection.return_value = mock_client
    search_service._bm25_enabled = False  # the plain dense-only branch
    search_service._bm25_vectorizer = None

    result = await search_service.search(
        query="test", user_level=1, limit=5, collection_override="visa_oracle"
    )

    assert result["results"][0]["score_kind"] == score_provenance.DENSE_FORMATTED
    assert result["results"][0]["score_raw"] == 0.9


@pytest.mark.asyncio
async def test_13b_single_query_search_declares_dense_formatted(
    search_service: SearchService,
) -> None:
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=_dense_raw())
    search_service.collection_manager.get_collection.return_value = mock_client

    result = await search_service._single_query_search(
        query="test", user_level=1, limit=5, tier_filter=None, apply_filters=None
    )

    assert result["results"][0]["score_kind"] == score_provenance.DENSE_FORMATTED
    assert result["results"][0]["score_raw"] == 0.9


@pytest.mark.asyncio
async def test_13c_ordinary_search_hybrid_branch_is_not_mislabelled_dense(
    search_service: SearchService,
) -> None:
    """The regression guard for the cure itself.

    `search()`'s ONE formatter call serves the hybrid success branch as well
    as the two dense ones. Declaring DENSE_FORMATTED at the call site would
    have cured finding 9 by introducing a fresh lie — a genuinely hybrid
    result served as dense. The kind must be decided per BRANCH, and on the
    hybrid branch by the PRESENCE of the "search_type" key (ruling R1).
    """
    hybrid_raw = dict(_dense_raw(), search_type="hybrid_rrf")
    mock_client = MagicMock()
    mock_client.hybrid_search = AsyncMock(return_value=hybrid_raw)
    mock_client.search = AsyncMock(return_value=_dense_raw())
    search_service.collection_manager.get_collection.return_value = mock_client

    mock_bm25 = MagicMock()
    mock_bm25.generate_query_sparse_vector.return_value = {"indices": [1], "values": [0.5]}
    search_service._bm25_vectorizer = mock_bm25
    search_service._bm25_enabled = True

    result = await search_service.search(
        query="test", user_level=1, limit=5, collection_override="visa_oracle"
    )

    assert result["results"][0]["score_kind"] == score_provenance.HYBRID_RRF_FORMATTED
