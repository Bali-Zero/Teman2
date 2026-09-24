"""B2.2 — tests for the no-send retrieval harness
(`backend/tests/benchmarks/evidence_sufficiency/retrieval_harness.py`).

Ground: `evidence/2026-09/agent-nuzantara-backend-rag-b2-2-harness-5936113c/
brief.yml`, key `harness_contract` HC1-HC10 (adopted by imperator ruling
I54, replacing I48 F4 after Codex r2 BLOCKed the QueryRouter-based design).
This suite proves the harness's hard guarantees:

  1. the artifact FILE'S BYTES are sha256-verified before parsing, no CLI
     flag overrides the pin, and there is no `--collection`/`--limit` of
     any kind (F1/HC6);
  2. per-query collections come from the REAL `QueryPlanner`, deduped in
     priority order; an empty plan is `unbuildable:no_collections`, never
     a failure; a translation-changing query is `embedding_divergent`,
     still fully retrieved (HC1/HC3);
  3. ANY retrieval failure — an absent collection, a collection with zero
     `points_count`, an exception from `get_stats`/`hybrid_search`/
     `search`, or zero hits across EVERY planned collection of a case —
     is a HARD STOP; a single empty collection among several is recorded,
     not fatal (HC2/HC6);
  4. no real network call ever happens, and neither does the embedder, the
     LLM generator, the Codex adapter, the WhatsApp sender, the cache
     writer, the rerankers, or `QueryExpander` — proven by patching each
     REAL production entrypoint to raise, in a FRESH subprocess, BEFORE
     the harness is even imported, then running both a safe and several
     guilty fake-client scenarios in that SAME process (HC7);
  5. `backend.app.core.config` is absent from `sys.modules` until the
     `--execute` plan-file gate has passed (or the query being run has
     confirmed non-empty collections) — proven in a fresh subprocess, and
     proven NOT to leave any residue for a later, unrelated import in the
     same process (HC5);
  6. no chunk text ever appears in a `QueryOutcome`, its JSON projection,
     or a file the harness writes — only opaque, collection-scoped
     references (HC9);
  7. `RetrievalError` carries a fixed message, the causing exception's
     class name, and an int status ONLY when the exception itself carries
     one in 100..599 — NEVER `str(exc)`, and the exception chain is
     severed (`from None`) so a secret-bearing original message cannot
     leak even via an uncaught traceback (HC8);
  8. `--execute` refuses, before importing `CollectionManager`, unless
     `--plan-file`'s bytes hash to `--plan-sha256` AND its parsed plan
     equals the plan recomputed now (F3/HC6).

Every test uses a FAKE vector-store client; none constructs a real
`QdrantClient`, `CollectionManager` or `SearchService`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

import pytest

from backend.tests.benchmarks.evidence_sufficiency import retrieval_harness as rh

pytestmark = pytest.mark.asyncio

_SENTINEL = "SENTINEL-CHUNK-TEXT-MUST-NEVER-BE-EXPORTED-9f3e7c"
_REPO_ROOT = Path(__file__).resolve().parents[5]  # apps/backend-rag


def _raw_results(
    *,
    text: str = "PT PMA registration takes about 2-4 weeks.",
    count: int = 1,
    hybrid: bool = True,
) -> dict[str, Any]:
    """A minimal, `QdrantClient`-shaped raw-results dict."""
    payload: dict[str, Any] = {
        "ids": [str(i) for i in range(count)],
        "documents": [text] * count,
        "metadatas": [{}] * count,
        "distances": [0.2] * count,
        "scores": [0.83] * count,
        "total_found": count,
    }
    if hybrid:
        payload["search_type"] = "hybrid_rrf"
    return payload


def _empty_raw_results() -> dict[str, Any]:
    return {
        "ids": [],
        "documents": [],
        "metadatas": [],
        "distances": [],
        "scores": [],
        "total_found": 0,
    }


class _FakeVectorDb:
    """Duck-typed stand-in for a `CollectionManager.get_collection(...)`
    result: exposes async `get_stats`/`hybrid_search`/`search`, records
    every call, never touches a socket."""

    def __init__(
        self,
        *,
        total_documents: int = 100,
        raw_results: dict[str, Any] | None = None,
        has_hybrid: bool = True,
    ) -> None:
        self.total_documents = total_documents
        self._raw_results = raw_results if raw_results is not None else _raw_results()
        self.calls: list[dict[str, Any]] = []
        if not has_hybrid:
            del self.__class__.hybrid_search  # type: ignore[attr-defined]

    async def get_stats(self) -> dict[str, Any]:
        return {"total_documents": self.total_documents}

    async def hybrid_search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"method": "hybrid_search", **kwargs})
        return self._raw_results

    async def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"method": "search", **kwargs})
        return self._raw_results


class _DenseOnlyVectorDb:
    """A client exposing ONLY `get_stats`/`search` — no `hybrid_search`
    attribute at all, forcing the dense-only branch."""

    def __init__(
        self, *, total_documents: int = 100, raw_results: dict[str, Any] | None = None
    ) -> None:
        self.total_documents = total_documents
        self._raw_results = raw_results if raw_results is not None else _raw_results(hybrid=False)
        self.calls: list[dict[str, Any]] = []

    async def get_stats(self) -> dict[str, Any]:
        return {"total_documents": self.total_documents}

    async def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"method": "search", **kwargs})
        return self._raw_results


class _RaisingVectorDb:
    """A client whose `.hybrid_search()`/`.search()` raise instead of
    returning."""

    def __init__(self, exc: BaseException, *, total_documents: int = 100) -> None:
        self._exc = exc
        self.total_documents = total_documents

    async def get_stats(self) -> dict[str, Any]:
        return {"total_documents": self.total_documents}

    async def hybrid_search(self, **kwargs: Any) -> dict[str, Any]:
        raise self._exc

    async def search(self, **kwargs: Any) -> dict[str, Any]:
        raise self._exc


class _StatsRaisingVectorDb:
    """A client whose `.get_stats()` itself raises."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def get_stats(self) -> dict[str, Any]:
        raise self._exc


def _resolver_map(mapping: dict[str, Any]) -> Any:
    """`resolve_client` that looks a collection up in `mapping`; `None`
    for anything not listed (an "absent collection")."""

    def _resolve(collection_name: str) -> Any:
        return mapping.get(collection_name)

    return _resolve


def _resolver_one(client: Any) -> Any:
    """`resolve_client` returning the SAME client for every collection."""

    def _resolve(_collection_name: str) -> Any:
        return client

    return _resolve


def _artifact_bytes(*, query_list: list[dict[str, str]], vectors: dict[str, list[float]]) -> bytes:
    """A tiny, self-consistent synthetic artifact."""
    from backend.tests.benchmarks.evidence_sufficiency.build_query_vectors import list_sha256

    payload = {
        "schema_version": 1,
        "synthetic": True,
        "query_list": query_list,
        "list_sha256": list_sha256(query_list),
        "vectors": vectors,
        "model": "text-embedding-3-small",
        "dimension": 3,
        "language_coverage": sorted({e["query_lang"] for e in query_list}),
        "approval_reference": "test fixture — not a real authorization",
        "attempts_made": len(query_list),
        "failures": [],
        "handoff": "test fixture",
        "base_sha": "0" * 40,
        "generated_at_utc": "2026-09-13T00:00:00+00:00",
    }
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def _write_artifact(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / "fixture_vectors.json"
    path.write_bytes(data)
    return path


# A domain-classified, non-divergent query (translator leaves it unchanged),
# routing to 2 collections (general -> legal_unified_hybrid + training_
# conversations_hybrid) — the clean "scored, inferable" fixture.
_GENERAL_QUERY = "xyzabc nonsense zzzqqq"
_GENERAL_ENTRY = {"query": _GENERAL_QUERY, "query_lang": "EN"}

# A domain-classified query that DOES change under translation (visa
# keywords trigger EN/ID keyword expansion) — the "embedding_divergent"
# fixture.
_VISA_QUERY = "Quanto costa il KITAS?"
_VISA_ENTRY = {"query": _VISA_QUERY, "query_lang": "IT"}

# A greeting — the "unbuildable:no_collections" fixture.
_GREETING_ENTRY = {"query": "Hello there!", "query_lang": "EN"}

_ONE_VECTOR = [0.1, 0.2, 0.3]


def _make_outcome(**overrides: Any) -> rh.QueryOutcome:
    """A minimal, valid `QueryOutcome` — override only the fields a given
    test cares about. Shared by `TestBuildReport` and the A55/item-F test
    classes below."""
    base = {
        "query_key": "EN::q",
        "query": "q",
        "query_lang": "EN",
        "case": "scored",
        "query_domain": "tax",
        "translation_changes_query": False,
        "embedding_divergent": False,
        "planned_collections": ("legal_unified_hybrid",),
        "collection_hit_counts": (("legal_unified_hybrid", 1),),
        "score": 0.12,
        "score_kinds": ("dense_formatted",),
        "generation_decision": "abstain",
        "label_decision": "abstain",
        "generation_threshold": 0.15,
        "label_threshold": 0.10,
        "source_count": 1,
        "source_refs": ("legal_unified_hybrid:id:1",),
    }
    base.update(overrides)
    return rh.QueryOutcome(**base)


def _synthetic_artifact(entries: list[dict[str, str]]) -> rh.QueryVectorArtifact:
    """An in-memory `QueryVectorArtifact` covering exactly `entries` — for
    tests exercising `run_all`/`run_query` with the fixture queries above,
    none of which are among the REAL B1.5 artifact's 23 queries."""
    vectors = {f"{e['query_lang']}::{e['query']}": _ONE_VECTOR for e in entries}
    data = {
        "query_list": entries,
        "vectors": vectors,
        "model": "text-embedding-3-small",
        "dimension": 3,
    }
    return rh.QueryVectorArtifact(path=Path("synthetic"), sha256="0" * 64, data=data)


class TestArtifactShaVerification:
    def test_pinned_sha256_matches_the_real_artifact(self) -> None:
        artifact = rh.load_artifact()
        assert artifact.sha256 == rh.EXPECTED_ARTIFACT_SHA256
        assert len(artifact.query_list) == 23

    def test_sha256_mismatch_aborts_before_parsing(self, tmp_path: Path) -> None:
        path = tmp_path / "not_json.json"
        path.write_bytes(b"{not valid json at all")

        with pytest.raises(rh.ArtifactError, match="sha256 mismatch"):
            rh.load_artifact(path, expected_sha256="0" * 64)

    def test_correct_sha256_on_a_synthetic_artifact_loads_fine(self, tmp_path: Path) -> None:
        data = _artifact_bytes(
            query_list=[_GENERAL_ENTRY], vectors={f"EN::{_GENERAL_QUERY}": _ONE_VECTOR}
        )
        path = _write_artifact(tmp_path, data)
        expected = hashlib.sha256(data).hexdigest()

        artifact = rh.load_artifact(path, expected_sha256=expected)
        assert artifact.query_list == [_GENERAL_ENTRY]


class TestNoOverrideFlagsOnTheCli:
    """F1 — the CLI always uses DEFAULT_ARTIFACT + EXPECTED_ARTIFACT_SHA256;
    there is no `--collection`, no `--limit`, and no escape flag of any
    kind for the pin."""

    def test_expected_sha256_flag_is_gone(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            rh.main(["--expected-sha256", "0" * 64])
        assert exc_info.value.code == 2

    def test_artifact_flag_is_gone(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            rh.main(["--artifact", "/tmp/whatever.json"])
        assert exc_info.value.code == 2

    def test_unsafe_flag_is_gone(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            rh.main(["--unsafe"])
        assert exc_info.value.code == 2

    def test_collection_flag_is_gone(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            rh.main(["--collection", "visa_oracle"])
        assert exc_info.value.code == 2

    def test_limit_flag_is_gone(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            rh.main(["--limit", "5"])
        assert exc_info.value.code == 2

    def test_plan_mode_works_without_any_flags(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = rh.main([])
        assert exit_code == 0
        printed = json.loads(capsys.readouterr().out)
        assert printed["query_count"] == 23
        assert "plan_sha256" in printed


class TestMissingVectorAbortsBeforeAnyClientCall:
    def test_resolve_vectors_raises_and_names_the_missing_key(self, tmp_path: Path) -> None:
        data = _artifact_bytes(query_list=[_GENERAL_ENTRY], vectors={})
        path = _write_artifact(tmp_path, data)
        artifact = rh.load_artifact(path, expected_sha256=hashlib.sha256(data).hexdigest())

        with pytest.raises(rh.ArtifactError, match=f"EN::{_GENERAL_QUERY}"):
            rh.resolve_vectors(artifact, [_GENERAL_ENTRY])

    async def test_run_all_never_calls_the_client_when_a_vector_is_missing(
        self, tmp_path: Path
    ) -> None:
        data = _artifact_bytes(query_list=[_GENERAL_ENTRY], vectors={})
        path = _write_artifact(tmp_path, data)
        artifact = rh.load_artifact(path, expected_sha256=hashlib.sha256(data).hexdigest())
        client = _FakeVectorDb()

        with pytest.raises(rh.ArtifactError):
            await rh.run_all(
                artifact=artifact,
                query_entries=[_GENERAL_ENTRY],
                resolve_client=_resolver_one(client),
            )

        assert client.calls == []

    async def test_run_all_partial_miss_still_aborts_the_whole_run(self, tmp_path: Path) -> None:
        two_queries = [_GENERAL_ENTRY, _VISA_ENTRY]
        data = _artifact_bytes(
            query_list=two_queries,
            vectors={f"EN::{_GENERAL_QUERY}": _ONE_VECTOR},
        )
        path = _write_artifact(tmp_path, data)
        artifact = rh.load_artifact(path, expected_sha256=hashlib.sha256(data).hexdigest())
        client = _FakeVectorDb()

        with pytest.raises(rh.ArtifactError, match=f"IT::{_VISA_QUERY}"):
            await rh.run_all(
                artifact=artifact,
                query_entries=two_queries,
                resolve_client=_resolver_one(client),
            )

        assert client.calls == []


class TestPlanForQuery:
    """HC1/HC3 — collections come from the REAL `QueryPlanner`, deduped;
    an empty plan is `unbuildable:no_collections`; a translation-changing
    query is `embedding_divergent`."""

    def test_build_plan_records_planned_collections_and_domain(self) -> None:
        plan = rh.build_plan([_GENERAL_ENTRY])
        case = plan["cases"][0]
        assert case["planned_domain"] == "general"
        assert case["planned_collections"] == [
            "legal_unified_hybrid",
            "training_conversations_hybrid",
        ]
        assert case["case"] == "scored"
        assert case["translation_changes_query"] is False

    def test_greeting_query_is_unbuildable_no_collections(self) -> None:
        plan = rh.build_plan([_GREETING_ENTRY])
        case = plan["cases"][0]
        assert case["planned_collections"] == []
        assert case["case"] == "unbuildable:no_collections"

    def test_visa_query_flags_translation_changes(self) -> None:
        plan = rh.build_plan([_VISA_ENTRY])
        case = plan["cases"][0]
        assert case["translation_changes_query"] is True
        assert case["planned_collections"]

    def test_collections_are_deduped_in_priority_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _DupPlan:
            domain = rh.QueryPlanner().plan("x").domain

            def __init__(self) -> None:
                self.collections = ["a", "b", "a", "c", "b"]

        class _DupPlanner:
            def plan(self, _query: str) -> _DupPlan:
                return _DupPlan()

        monkeypatch.setattr(rh, "QueryPlanner", _DupPlanner)
        _domain, collections, _divergent = rh._plan_for_query("whatever")
        assert collections == ["a", "b", "c"]

    async def test_unbuildable_case_never_calls_the_client(self) -> None:
        resolver = _resolver_one(_FakeVectorDb())
        outcome = await rh.run_query(
            query_entry=_GREETING_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=resolver,
        )
        assert outcome.case == "unbuildable:no_collections"
        assert outcome.score is None
        assert outcome.planned_collections == ()
        assert outcome.source_refs == ()

    async def test_embedding_divergent_case_is_still_fully_scored(self) -> None:
        client = _FakeVectorDb()
        outcome = await rh.run_query(
            query_entry=_VISA_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        assert outcome.case == "scored"
        assert outcome.embedding_divergent is True
        assert outcome.translation_changes_query is True
        assert outcome.score is not None
        assert outcome.source_count > 0

    async def test_build_plan_agrees_with_run_query_planned_collections(self) -> None:
        plan = rh.build_plan([_GENERAL_ENTRY])
        planned = plan["cases"][0]["planned_collections"]

        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(_FakeVectorDb()),
        )
        assert list(outcome.planned_collections) == planned


class TestPerCollectionRetrieval:
    """HC2 — the filter/BM25/hybrid-vs-dense branch mirror
    `_prepare_search_context`/`SearchService.hybrid_search` exactly."""

    async def test_filter_matches_prepare_search_context_recipe(self) -> None:
        client = _FakeVectorDb()
        await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        expected = rh._build_search_filter_for("legal_unified_hybrid")
        assert client.calls[0]["filter"] == expected

    async def test_bm25_sparse_vector_matches_a_real_bm25vectorizer(self) -> None:
        client = _FakeVectorDb()
        bm25 = rh.BM25Vectorizer(vocab_size=30000, k1=1.5, b=0.75)
        await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
            bm25=bm25,
        )
        expected_sparse = bm25.generate_query_sparse_vector(_GENERAL_QUERY)
        assert client.calls[0]["query_sparse"] == expected_sparse

    async def test_hybrid_search_limit_and_prefetch(self) -> None:
        client = _FakeVectorDb()
        await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        call = client.calls[0]
        assert call["limit"] == rh._CHUNKS_PER_COLLECTION_LIMIT
        assert call["prefetch_limit"] == rh._CHUNKS_PER_COLLECTION_LIMIT * 3

    async def test_declared_score_kind_hybrid_when_search_type_present(self) -> None:
        client = _FakeVectorDb(raw_results=_raw_results(hybrid=True))
        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        assert all(k == "hybrid_rrf_formatted" for k in outcome.score_kinds)

    async def test_declared_score_kind_dense_when_search_type_absent(self) -> None:
        client = _FakeVectorDb(raw_results=_raw_results(hybrid=False))
        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        assert all(k == "dense_formatted" for k in outcome.score_kinds)

    async def test_no_hybrid_search_attribute_takes_the_dense_branch(self) -> None:
        client = _DenseOnlyVectorDb()
        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        assert client.calls[0]["method"] == "search"
        assert "vector_name" in client.calls[0]
        assert all(k == "dense_formatted" for k in outcome.score_kinds)

    async def test_all_planned_collections_are_searched(self) -> None:
        clients: dict[str, _FakeVectorDb] = {}

        def resolve_client(collection: str) -> Any:
            # A55_1: called with the CANONICALIZED/resolved name, never the
            # raw planned one (search_service.py:526 calls get_collection on
            # collection_name AFTER _route_search_query's canonicalization).
            clients.setdefault(collection, _FakeVectorDb())
            return clients[collection]

        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=resolve_client,
        )
        resolved_names = {
            resolved for _planned, resolved, _sub, _dup in outcome.collection_resolutions
        }
        assert set(clients) == resolved_names
        assert set(dict(outcome.collection_hit_counts)) == set(outcome.planned_collections)

    async def test_hygiene_caps_applied(self) -> None:
        long_text = "x" * (rh._MAX_CHUNK_CHARS + 500)
        client = _FakeVectorDb(raw_results=_raw_results(text=long_text, count=rh._MAX_CHUNKS + 5))
        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        assert outcome.source_count <= rh._MAX_CHUNKS

    async def test_dlp_redaction_is_called_with_the_builder_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import backend.services.rag.agentic.wa_dlp as wa_dlp_mod

        real_redact = wa_dlp_mod.redact_package_fields  # captured BEFORE patching
        calls: list[dict[str, Any]] = []

        def _spy(history: Any, chunks: Any, search_query: Any) -> Any:
            calls.append(
                {"history": history, "search_query": search_query, "chunk_count": len(chunks)}
            )
            return real_redact(history, chunks, search_query)

        monkeypatch.setattr(wa_dlp_mod, "redact_package_fields", _spy)

        client = _FakeVectorDb()
        await rh.run_query(
            query_entry=_GENERAL_ENTRY, vector=_ONE_VECTOR, resolve_client=_resolver_one(client)
        )

        assert len(calls) == 1
        assert calls[0]["history"] == []
        assert calls[0]["search_query"] is None
        assert calls[0]["chunk_count"] > 0


class TestMultiCollectionHardStops:
    """HC6/A55_1/A55_2 — empty-index/exception/an 'error'-key result is
    ALWAYS a hard stop per RESOLVED collection; zero hits across ALL
    RESOLVED collections of a case is a hard stop; zero hits on ONE of
    several is recorded, not fatal. An unresolvable PLANNED collection is
    substituted to 'legal_unified' (never an immediate hard stop by
    itself) — see `TestA55CollectionResolution` for that behavior."""

    async def test_one_empty_collection_among_several_is_recorded_not_fatal(self) -> None:
        empty_client = _FakeVectorDb(raw_results=_empty_raw_results())
        hit_client = _FakeVectorDb(raw_results=_raw_results())
        # Keyed by the RESOLVED (canonicalized) name: "legal_unified_hybrid"
        # canonicalizes to "legal_unified" before resolve_client ever sees it
        # (A55_1) — "training_conversations_hybrid" canonicalizes to itself.
        mapping = {
            "legal_unified": empty_client,
            "training_conversations_hybrid": hit_client,
        }
        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_map(mapping),
        )
        assert outcome.case == "scored"
        hit_counts = dict(outcome.collection_hit_counts)
        # collection_hit_counts stays keyed by the PLANNED (raw) name.
        assert hit_counts["legal_unified_hybrid"] == 0
        assert hit_counts["training_conversations_hybrid"] == 1

    async def test_zero_hits_on_every_planned_collection_is_a_hard_stop(self) -> None:
        empty_client = _FakeVectorDb(raw_results=_empty_raw_results())
        mapping = {
            "legal_unified": empty_client,
            "training_conversations_hybrid": empty_client,
        }
        with pytest.raises(rh.RetrievalError, match="zero hits across ALL resolved collections"):
            await rh.run_query(
                query_entry=_GENERAL_ENTRY,
                vector=_ONE_VECTOR,
                resolve_client=_resolver_map(mapping),
            )

    async def test_absent_collection_is_a_hard_stop_even_if_others_would_hit(self) -> None:
        """A55_1: an absent PLANNED collection is no longer an immediate hard
        stop by itself — it is resolved and, on failure, substituted to
        'legal_unified' (search_service.py:526-532). This mapping leaves
        BOTH the canonical name ('legal_unified', what 'legal_unified_hybrid'
        resolves to) AND the substitution target absent, so the fallback has
        nothing left to fall back to — still a hard stop, but for the NEW
        reason (see TestA55CollectionResolution for the substitution-success
        case this replaces as HC6's old-behavior test)."""
        mapping = {"training_conversations_hybrid": _FakeVectorDb()}  # legal_unified absent too
        with pytest.raises(rh.RetrievalError, match="legal_unified_hybrid"):
            await rh.run_query(
                query_entry=_GENERAL_ENTRY,
                vector=_ONE_VECTOR,
                resolve_client=_resolver_map(mapping),
            )

    async def test_zero_points_count_is_a_hard_stop(self) -> None:
        client = _FakeVectorDb(total_documents=0)
        with pytest.raises(rh.RetrievalError, match="zero points_count"):
            await rh.run_query(
                query_entry=_GENERAL_ENTRY,
                vector=_ONE_VECTOR,
                resolve_client=_resolver_one(client),
            )

    async def test_get_stats_exception_is_a_hard_stop(self) -> None:
        client = _StatsRaisingVectorDb(ConnectionError("simulated"))
        with pytest.raises(rh.RetrievalError, match="get_stats"):
            await rh.run_query(
                query_entry=_GENERAL_ENTRY,
                vector=_ONE_VECTOR,
                resolve_client=_resolver_one(client),
            )

    async def test_hybrid_search_exception_is_a_hard_stop(self) -> None:
        client = _RaisingVectorDb(ConnectionError("simulated Qdrant connection failure"))
        with pytest.raises(rh.RetrievalError, match="client search raised"):
            await rh.run_query(
                query_entry=_GENERAL_ENTRY,
                vector=_ONE_VECTOR,
                resolve_client=_resolver_one(client),
            )

    async def test_run_and_write_writes_no_file_on_any_hard_stop(self, tmp_path: Path) -> None:
        data = _artifact_bytes(
            query_list=[_GENERAL_ENTRY], vectors={f"EN::{_GENERAL_QUERY}": _ONE_VECTOR}
        )
        artifact_path = _write_artifact(tmp_path, data)
        out_path = tmp_path / "report.json"
        client = _FakeVectorDb(total_documents=0)

        with pytest.raises(rh.RetrievalError):
            await rh.run_and_write(
                artifact_path=artifact_path,
                expected_sha256=hashlib.sha256(data).hexdigest(),
                query_entries=[_GENERAL_ENTRY],
                resolve_client=_resolver_one(client),
                out_path=out_path,
            )

        assert not out_path.exists()

    async def test_a_later_query_is_never_run_after_a_hard_stop(self) -> None:
        artifact = _synthetic_artifact([_GENERAL_ENTRY, _GENERAL_ENTRY])
        entries = [_GENERAL_ENTRY, _GENERAL_ENTRY]
        calls_made = {"n": 0}

        def resolve_client(_collection: str) -> Any:
            calls_made["n"] += 1
            return _FakeVectorDb(total_documents=0)

        with pytest.raises(rh.RetrievalError):
            await rh.run_all(
                artifact=artifact, query_entries=entries, resolve_client=resolve_client
            )

        # Only the FIRST query's first collection lookup ever happened.
        assert calls_made["n"] == 1


def _fixed_planner(collections: list[str]) -> type:
    """A `QueryPlanner` stand-in that always plans exactly `collections`,
    for tests that need a DETERMINISTIC plan rather than depending on
    `QueryPlanner`'s real heuristic classification of query text."""

    class _FixedPlan:
        domain = rh.QueryPlanner().plan("x").domain

        def __init__(self) -> None:
            self.collections = list(collections)

    class _FixedPlanner:
        def plan(self, _query: str) -> _FixedPlan:
            return _FixedPlan()

    return _FixedPlanner


class TestA55CollectionResolution:
    """A55_1 — every planned collection is resolved exactly as
    search_service.py:526-532 resolves it for a collection_override: the
    REAL `canonicalize_collection_name`, then a resolve/substitute-to-
    'legal_unified' fallback replicated verbatim (parity-pinned below). An
    unresolvable planned name is NOT a hard stop any more — it substitutes,
    like production, and the substitution is recorded as a FINDING."""

    async def test_unresolvable_planned_collection_substitutes_to_legal_unified(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """'nuzantara_general_hybrid' — planned FIRST for TAX/PROPERTY/
        PRICING (query_planner.py:255-260) — has zero occurrences in
        collection_registry.py/collection_manager.py. Production silently
        substitutes 'legal_unified' (search_service.py:526-532); so does
        this harness."""
        monkeypatch.setattr(rh, "QueryPlanner", _fixed_planner(["nuzantara_general_hybrid"]))
        legal_client = _FakeVectorDb()
        mapping = {"legal_unified": legal_client}  # nuzantara_general_hybrid absent by design

        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_map(mapping),
        )
        assert outcome.case == "scored"
        assert outcome.collection_resolutions == (
            ("nuzantara_general_hybrid", "legal_unified", True, False),
        )

    async def test_two_planned_collections_resolving_to_the_same_collection_are_both_searched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Production searches a resolved collection TWICE when two
        DIFFERENT planned collections resolve to it — never deduped
        post-resolution. TAX/PROPERTY plan exactly this pair:
        ['nuzantara_general_hybrid', 'legal_unified_hybrid'] — both resolve
        to 'legal_unified' (the first via substitution, the second via
        plain canonicalization)."""
        monkeypatch.setattr(
            rh, "QueryPlanner", _fixed_planner(["nuzantara_general_hybrid", "legal_unified_hybrid"])
        )
        legal_client = _FakeVectorDb()

        def resolve_client(name: str) -> Any:
            return legal_client if name == "legal_unified" else None

        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY, vector=_ONE_VECTOR, resolve_client=resolve_client
        )
        assert outcome.case == "scored"
        resolved_names = [resolved for _p, resolved, _s, _d in outcome.collection_resolutions]
        assert resolved_names == ["legal_unified", "legal_unified"]
        duplicates = [dup for _p, _r, _s, dup in outcome.collection_resolutions]
        assert duplicates == [False, True]
        # Searched TWICE, not deduped after resolution:
        assert len(legal_client.calls) == 2

    async def test_chunks_keep_the_planned_name_and_skip_empty_text_hits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """wa_package_builder.py:280-290 (TP1 r3 findings 1-2): the chunk
        carries the PLANNED collection name — the sort tie-breaker — and a
        hit without text never becomes a chunk."""
        monkeypatch.setattr(rh, "QueryPlanner", _fixed_planner(["nuzantara_general_hybrid"]))
        raw = _raw_results(count=2)
        raw["documents"] = ["", "PT PMA registration takes about 2-4 weeks."]
        mapping = {"legal_unified": _FakeVectorDb(raw_results=raw)}
        captured: list[dict[str, Any]] = []
        real_cap = rh._cap_chunks

        def _spy(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
            captured.extend(chunks)
            return real_cap(chunks)

        monkeypatch.setattr(rh, "_cap_chunks", _spy)
        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY, vector=_ONE_VECTOR, resolve_client=_resolver_map(mapping)
        )
        assert outcome.case == "scored"
        assert captured, "no chunk reached the cap"
        assert all(chunk["text"] for chunk in captured)
        assert {chunk["collection"] for chunk in captured} == {"nuzantara_general_hybrid"}

    async def test_legal_unified_itself_unresolvable_is_still_a_hard_stop(self) -> None:
        """When even the substitution target is absent, production raises
        ValueError (search_service.py:538-539) — the harness's one
        remaining hard stop for collection resolution."""
        with pytest.raises(rh.RetrievalError, match="substitution target"):
            await rh.run_query(
                query_entry=_GENERAL_ENTRY,
                vector=_ONE_VECTOR,
                resolve_client=_resolver_map({}),  # nothing resolves, ever
            )

    def test_search_service_substitution_shape_parity(self) -> None:
        """A55_1 parity pin: search_service.py:532-539 (shifted from 526-532
        by L2104's `collection_substituted` flag, 2026-09-24) must keep this
        literal shape (get_collection -> None -> log + substitute
        'legal_unified' -> get_collection('legal_unified') -> raise
        ValueError if STILL None), or this harness's replica in
        `run_query` has silently drifted from production and must be
        re-verified by hand before this pin is updated."""
        path = _REPO_ROOT / "backend" / "services" / "search" / "search_service.py"
        lines = path.read_text(encoding="utf-8").splitlines()
        window = "\n".join(lines[531:539])  # 532-539, 1-indexed
        assert "get_collection(collection_name)" in window
        assert "if not vector_db" in window
        assert 'get_collection("legal_unified")' in window
        assert 'collection_name = "legal_unified"' in window
        assert "raise ValueError" in window

    def test_substitutions_surface_in_the_run_level_report(self) -> None:
        """The pack needs the substitution as a FINDING (A55_1) — a
        run-level `substitutions` list, not buried per-row only."""
        outcome = _make_outcome(
            query_key="EN::q",
            planned_collections=("nuzantara_general_hybrid",),
            collection_hit_counts=(("nuzantara_general_hybrid", 1),),
            source_refs=("legal_unified:id:1",),
            collection_resolutions=(("nuzantara_general_hybrid", "legal_unified", True, False),),
        )
        report = rh.build_report([outcome])
        assert report["substitutions"] == [
            {
                "query_key": "EN::q",
                "collection_planned": "nuzantara_general_hybrid",
                "collection_resolved": "legal_unified",
            },
        ]


class TestA55ErrorShape:
    """A55_2 — qdrant_db.py's `hybrid_search` does not always raise: a
    returned dict carrying an 'error' key is a HARD STOP (never zero
    evidence, never leaking the error text — HC8); a dense fallback taken
    INSIDE `hybrid_search` (no 'search_type' key) is a score_kind
    divergence, excluded from inference, never a hard stop."""

    async def test_error_key_in_raw_results_is_a_hard_stop_never_zero_evidence(self) -> None:
        secret = "SECRET-SHAPED-qdrant-internal-failure-token-9f3e"

        class _ErrorVectorDb:
            total_documents = 100

            async def get_stats(self) -> dict[str, Any]:
                return {"total_documents": self.total_documents}

            async def hybrid_search(self, **kwargs: Any) -> dict[str, Any]:
                return {
                    "ids": [],
                    "documents": [],
                    "metadatas": [],
                    "distances": [],
                    "scores": [],
                    "total_found": 0,
                    "search_type": "hybrid_rrf",
                    "error": secret,
                }

            async def search(self, **kwargs: Any) -> dict[str, Any]:
                raise AssertionError("must not fall back to plain search")

        client = _ErrorVectorDb()
        with pytest.raises(rh.RetrievalError) as excinfo:
            await rh.run_query(
                query_entry=_GENERAL_ENTRY,
                vector=_ONE_VECTOR,
                resolve_client=_resolver_one(client),
            )
        assert secret not in str(excinfo.value)
        assert "error" in str(excinfo.value).lower()

    async def test_dense_fallback_inside_hybrid_search_is_score_kind_divergent(self) -> None:
        # has_hybrid=True (default): the HYBRID branch is taken, but its OWN
        # raw_results lack "search_type" — the internal fallback qdrant_db.py
        # takes on some 400s, not this harness's own dense branch.
        client = _FakeVectorDb(raw_results=_raw_results(hybrid=False))
        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        assert outcome.case == "scored"
        assert outcome.score_kind_divergent is True
        assert outcome.score is not None  # still fully scored and reported

    def test_score_kind_divergent_excluded_from_inference_and_relief_band(self) -> None:
        outcome = _make_outcome(
            query_key="k1", query_domain="tax", score=0.12, score_kind_divergent=True
        )
        report = rh.build_report([outcome])
        assert report["relief_band_cases"] == []
        assert report["inferable_count"] == 0
        assert report["inferable_case_count"] == 0


class TestA55Filter:
    """A55_3 — the per-collection filter goes through the REAL
    `_requires_current_law_guard` path (canonicalize, then membership in
    {legal_unified, tax_genius}); a hand-built filter would drop it
    silently."""

    def test_legal_unified_and_tax_genius_carry_the_current_law_guard(self) -> None:
        for name in ("legal_unified", "tax_genius"):
            filt = rh._build_search_filter_for(name)
            assert filt is not None
            assert filt["retrieval_scope"] == {"$ne": "historical_only"}

    def test_visa_oracle_does_not_carry_the_current_law_guard(self) -> None:
        filt = rh._build_search_filter_for("visa_oracle")
        assert filt is not None
        assert "retrieval_scope" not in filt

    def test_parity_with_the_real_search_service_guard(self) -> None:
        """Calls the REAL `SearchService._requires_current_law_guard` — a
        staticmethod, called via the CLASS, never instantiated (HC5 binds
        only the harness module itself, never this test file)."""
        from backend.services.search.search_service import SearchService

        for name in (
            "legal_unified",
            "tax_genius",
            "visa_oracle",
            "kbli_2025_final",
            "legal_unified_hybrid",
            "nuzantara_general_hybrid",
            "balizero_news",
        ):
            assert rh._requires_current_law_guard(
                name
            ) == SearchService._requires_current_law_guard(name)


class TestA55Bm25Determinant:
    """A55_4 — vocab_size is the QUERY-side sparse determinant; k1/b are
    document-side, still passed to the constructor as production does but
    never reported as determinants."""

    async def test_run_and_write_reports_vocab_size_as_the_determinant_not_k1_b(
        self, tmp_path: Path
    ) -> None:
        client = _FakeVectorDb()
        data = _artifact_bytes(
            query_list=[_GENERAL_ENTRY], vectors={f"EN::{_GENERAL_QUERY}": _ONE_VECTOR}
        )
        artifact_path = _write_artifact(tmp_path, data)
        bm25 = rh.BM25Vectorizer(vocab_size=12345, k1=1.5, b=0.75)

        payload = await rh.run_and_write(
            artifact_path=artifact_path,
            expected_sha256=hashlib.sha256(data).hexdigest(),
            query_entries=[_GENERAL_ENTRY],
            resolve_client=_resolver_one(client),
            bm25=bm25,
        )
        run = payload["run"]
        assert run["bm25_sparse_determinant"] == {"vocab_size": 12345}
        assert run["bm25_document_side_constructor_params"] == {"k1": 1.5, "b": 0.75}
        assert "bm25_k1" not in run
        assert "bm25_vocab_size" not in run
        assert "bm25_b" not in run


class TestRunAndWriteBuildsReport:
    """D3 (gate-6429, folded into the B2 ledger close, row `main --execute
    never calls build_report`) — `run_and_write` now builds the HC9/HC10
    report itself (`build_report(outcomes, manifest_cases=...)`) instead of
    leaving every B2.x evidence pack to be rebuilt OFFLINE by the standalone
    `build_sample_report.py` script."""

    async def test_manifest_cases_given_adds_a_report_key(self, tmp_path: Path) -> None:
        client = _FakeVectorDb()
        data = _artifact_bytes(
            query_list=[_GENERAL_ENTRY], vectors={f"EN::{_GENERAL_QUERY}": _ONE_VECTOR}
        )
        artifact_path = _write_artifact(tmp_path, data)

        payload = await rh.run_and_write(
            artifact_path=artifact_path,
            expected_sha256=hashlib.sha256(data).hexdigest(),
            query_entries=[_GENERAL_ENTRY],
            resolve_client=_resolver_one(client),
            bm25=rh.BM25Vectorizer(vocab_size=30000, k1=1.5, b=0.75),
            manifest_cases=[],
        )

        assert "report" in payload
        assert payload["report"]["rows"]
        assert len(payload["report"]["rows"]) == len(payload["cases"])
        assert payload["report"]["support_none_sentence"]
        assert payload["report"]["canary"]

    async def test_manifest_cases_omitted_has_no_report_key(self, tmp_path: Path) -> None:
        """Backward compatibility: every pre-existing caller that never
        passes `manifest_cases` keeps getting exactly the payload it always
        got — no `"report"` key, no behavior change."""
        client = _FakeVectorDb()
        data = _artifact_bytes(
            query_list=[_GENERAL_ENTRY], vectors={f"EN::{_GENERAL_QUERY}": _ONE_VECTOR}
        )
        artifact_path = _write_artifact(tmp_path, data)

        payload = await rh.run_and_write(
            artifact_path=artifact_path,
            expected_sha256=hashlib.sha256(data).hexdigest(),
            query_entries=[_GENERAL_ENTRY],
            resolve_client=_resolver_one(client),
            bm25=rh.BM25Vectorizer(vocab_size=30000, k1=1.5, b=0.75),
        )

        assert "report" not in payload


class TestInferableCaseCount:
    """Item F — a run-level `inferable_case_count` excluding
    embedding_divergent, score_kind_divergent, AND unbuildable cases."""

    def test_excludes_all_three_categories(self) -> None:
        scored = _make_outcome(query_key="k1")
        embedding_divergent = _make_outcome(query_key="k2", embedding_divergent=True)
        score_kind_divergent = _make_outcome(query_key="k3", score_kind_divergent=True)
        unbuildable = _make_outcome(
            query_key="k4",
            case="unbuildable:no_collections",
            query_domain=None,
            score=None,
            planned_collections=(),
            collection_hit_counts=(),
            score_kinds=(),
            source_count=0,
            source_refs=(),
        )
        report = rh.build_report([scored, embedding_divergent, score_kind_divergent, unbuildable])
        assert report["inferable_case_count"] == 1
        assert report["inferable_count"] == 1


class TestSafeExceptionSummaryNeverLeaksSecrets:
    """HC8 — a fixed message, the exception's class name, and an int
    status ONLY when it is in 100..599 — NEVER `str(exc)` — and the chain
    is severed (`from None`) so an uncaught traceback cannot leak it."""

    def test_status_code_included_only_when_valid_int_in_range(self) -> None:
        class _WithStatus(Exception):
            status_code = 404

        class _WithBadStatus(Exception):
            status_code = "sk-FAKE-TEST-0000"

        class _WithOutOfRangeStatus(Exception):
            status_code = 9001

        class _Plain(Exception):
            pass

        assert rh._safe_exception_summary(_WithStatus()) == {
            "exception_type": "_WithStatus",
            "status_code": 404,
        }
        assert rh._safe_exception_summary(_WithBadStatus()) == {"exception_type": "_WithBadStatus"}
        assert rh._safe_exception_summary(_WithOutOfRangeStatus()) == {
            "exception_type": "_WithOutOfRangeStatus"
        }
        assert rh._safe_exception_summary(_Plain()) == {"exception_type": "_Plain"}

    async def test_secret_shaped_exception_message_never_leaks(self, tmp_path: Path) -> None:
        secret = "sk-FAKE-TEST-0000-do-not-leak"
        fake_url = "https://fake-internal.example/leak?token=" + secret

        class _Secrety(Exception):
            status_code = 500

        client = _RaisingVectorDb(_Secrety(f"upstream said: {fake_url}"))

        with pytest.raises(rh.RetrievalError) as exc_info:
            await rh.run_query(
                query_entry=_GENERAL_ENTRY,
                vector=_ONE_VECTOR,
                resolve_client=_resolver_one(client),
            )

        message = str(exc_info.value)
        assert secret not in message
        assert fake_url not in message
        assert "_Secrety" in message

        # The chain is severed: Python's own traceback formatter would
        # therefore never print the original (secret-bearing) exception
        # even if this propagated fully uncaught.
        assert exc_info.value.__cause__ is None
        formatted = "".join(
            traceback.format_exception(
                type(exc_info.value), exc_info.value, exc_info.value.__traceback__
            ),
        )
        assert secret not in formatted
        assert fake_url not in formatted

        data = _artifact_bytes(
            query_list=[_GENERAL_ENTRY], vectors={f"EN::{_GENERAL_QUERY}": _ONE_VECTOR}
        )
        artifact_path = _write_artifact(tmp_path, data)
        out_path = tmp_path / "report.json"
        with pytest.raises(rh.RetrievalError):
            await rh.run_and_write(
                artifact_path=artifact_path,
                expected_sha256=hashlib.sha256(data).hexdigest(),
                query_entries=[_GENERAL_ENTRY],
                resolve_client=_resolver_one(client),
                out_path=out_path,
            )
        assert not out_path.exists()


class TestNoNetworkCall:
    async def test_full_run_never_touches_a_socket(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _blocked(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("the B2.2 retrieval harness must never touch a real socket")

        async def _blocked_async(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(
                "the B2.2 retrieval harness must never touch a real socket (asyncio)"
            )

        monkeypatch.setattr(socket.socket, "connect", _blocked)
        monkeypatch.setattr(socket, "create_connection", _blocked)
        monkeypatch.setattr(asyncio.base_events.BaseEventLoop, "sock_connect", _blocked_async)
        monkeypatch.setattr(asyncio.base_events.BaseEventLoop, "create_connection", _blocked_async)
        monkeypatch.setattr(asyncio, "open_connection", _blocked_async)

        artifact = _synthetic_artifact([_GENERAL_ENTRY, _VISA_ENTRY, _GREETING_ENTRY])
        entries = [_GENERAL_ENTRY, _VISA_ENTRY, _GREETING_ENTRY]
        client = _FakeVectorDb()

        outcomes = await rh.run_all(
            artifact=artifact,
            query_entries=entries,
            resolve_client=_resolver_one(client),
        )

        assert len(outcomes) == 3
        assert outcomes[2].case == "unbuildable:no_collections"


class TestHC5ImportBoundary:
    """HC5 — `backend.app.core.config` absent from `sys.modules` until the
    `--execute` plan-file gate has passed (or a query's collections are
    confirmed non-empty), proven in a FRESH subprocess."""

    def test_config_absent_until_plan_check_and_bad_plan_file_stays_that_way(self) -> None:
        script = """
import sys

def _blocked(*_a, **_k):
    raise AssertionError("network touched")

import socket
socket.socket.connect = _blocked
socket.create_connection = _blocked

from backend.tests.benchmarks.evidence_sufficiency import retrieval_harness as rh

assert "backend.app.core.config" not in sys.modules, "config loaded merely by importing the harness"

plan = rh.build_plan(rh.load_artifact().query_list)
assert "backend.app.core.config" not in sys.modules, "config loaded by build_plan()"

exit_code = rh.main(["--execute", "--plan-sha256", "0" * 64])
assert exit_code == 1
assert "backend.app.core.config" not in sys.modules, "config loaded on a refused --execute"
assert "backend.services.ingestion.collection_manager" not in sys.modules

print("B2_2_HC5_MARKER_OK")
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = "."
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
        assert "B2_2_HC5_MARKER_OK" in result.stdout


class TestHC5StubBypassLeavesNoTrace:
    """`_import_pure_leaf`'s bypass must leave zero residue: after `rh`
    has already been imported (module scope of this test file), the REAL
    packages must still import normally with their real attributes."""

    def test_real_packages_still_import_correctly_after_the_bypass(self) -> None:
        import backend.services.rag.agentic as agentic_pkg
        import backend.services.search as search_pkg

        assert hasattr(agentic_pkg, "AgenticRAGOrchestrator")
        assert hasattr(search_pkg, "SearchService")
        # The bypass drops its module from sys.modules after binding the
        # class, so a later normal import re-executes the SAME file into a
        # distinct class object: same file, same plan, never class identity.
        from backend.services.rag.agentic import query_planner as real_module

        assert real_module.__file__ == rh.QueryPlanner.plan.__code__.co_filename
        query = "What visa do I need?"
        assert (
            real_module.QueryPlanner().plan(query).collections
            == rh.QueryPlanner().plan(query).collections
        )


class TestGuardsHC7:
    """HC7 — guards installed BEFORE importing the harness, in a FRESH
    subprocess; a safe fake-Qdrant `--execute` run goes green, and each
    guilty scenario (the fake client itself reaching a guarded real
    entrypoint) goes red with no report file, in that SAME subprocess."""

    def test_safe_case_green_and_each_guarded_entrypoint_reached_goes_red(self) -> None:
        script = r"""
import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock

import backend.core.embeddings as embeddings_mod
import backend.llm.codex_exec_client as codex_mod
import backend.services.integrations.whatsapp_service as wa_mod
import backend.core.cache as cache_mod
import backend.core.reranker as reranker_mod
import backend.services.rag.reranker as reranker2_mod
import backend.services.search.query_expander as expander_mod
import backend.services.ingestion.collection_manager as cm_mod

raisers = {}

def _install(obj, attr, msg):
    mock = AsyncMock(side_effect=RuntimeError(msg))
    setattr(obj, attr, mock)
    raisers[msg] = mock

_install(embeddings_mod.EmbeddingsGenerator, "generate_query_embedding", "embedder must never be called")
_install(embeddings_mod, "create_embeddings_generator", "embedder factory must never be called")
_install(codex_mod.CodexExecClient, "generate", "Codex adapter must never be called")
_install(wa_mod.WhatsAppService, "send_message", "WA sender must never be called")
_install(cache_mod.CacheService, "set", "cache writer must never be called")
_install(reranker_mod.ReRanker, "rerank", "Ze-Rank reranker must never be called")
_install(reranker2_mod.CrossEncoderReranker, "rerank", "cross-encoder reranker must never be called")
_install(expander_mod.QueryExpander, "expand", "query expander must never be called")

from backend.tests.benchmarks.evidence_sufficiency import retrieval_harness as rh


class _FakeVectorDb:
    def __init__(self, bad_call=None):
        self._bad_call = bad_call

    async def get_stats(self):
        return {"total_documents": 5}

    async def hybrid_search(self, **kwargs):
        if self._bad_call is not None:
            await self._bad_call()
        return {
            "ids": ["1"], "documents": ["doc"], "metadatas": [{}],
            "distances": [0.1], "scores": [0.9], "total_found": 1,
            "search_type": "hybrid_rrf",
        }


def _make_cm(bad_call):
    class _FakeCM:
        def __init__(self, **kwargs):
            pass

        def get_collection(self, name):
            return _FakeVectorDb(bad_call)

    return _FakeCM


tmp = tempfile.mkdtemp()
artifact = rh.load_artifact()
plan = rh.build_plan(artifact.query_list)
plan_bytes = rh._canonical_plan_bytes(plan)
plan_sha = rh._plan_sha256(plan)
plan_path = os.path.join(tmp, "plan.json")
with open(plan_path, "wb") as fh:
    fh.write(plan_bytes)

# --- SAFE CASE ---
cm_mod.CollectionManager = _make_cm(None)
out_path = os.path.join(tmp, "report.json")

build_report_calls = []
_real_build_report = rh.build_report
def _traced_build_report(outcomes, **kwargs):
    build_report_calls.append(kwargs.get("manifest_cases"))
    return _real_build_report(outcomes, **kwargs)
rh.build_report = _traced_build_report

exit_code = rh.main(["--execute", "--plan-file", plan_path, "--plan-sha256", plan_sha, "--out", out_path])
assert exit_code == 0, f"safe case did not go green: {exit_code}"
assert os.path.exists(out_path), "safe case should write a report"
for msg, mock in raisers.items():
    assert not mock.called, f"a guard fired on the SAFE case: {msg}"

# D3 (gate-6429): main --execute's OWN code path must call build_report
# directly — traced here, not inferred from the output shape alone.
assert len(build_report_calls) == 1, "main --execute must call build_report exactly once"
assert build_report_calls[0], "build_report must be called with the frozen mandatory manifest's cases"
with open(out_path, encoding="utf-8") as fh:
    written = json.load(fh)
assert "report" in written, "the written --execute payload must carry build_report's report"
assert written["report"]["rows"], "the report must have one row per case"
print("SAFE_CASE_OK")

# --- GUILTY CASES ---
scenarios = {
    "embed": lambda: embeddings_mod.EmbeddingsGenerator.generate_query_embedding(None, "probe"),
    "embed_factory": lambda: embeddings_mod.create_embeddings_generator(),
    "codex": lambda: codex_mod.CodexExecClient.generate(None, "probe"),
    "send": lambda: wa_mod.WhatsAppService.send_message(None, phone="1", text="x"),
    "cache_set": lambda: cache_mod.CacheService.set(None, "k", "v"),
    "rerank": lambda: reranker_mod.ReRanker.rerank(None, "q", [], top_k=1),
    "cross_rerank": lambda: reranker2_mod.CrossEncoderReranker.rerank(None, "q", [], top_k=1),
    "expand": lambda: expander_mod.QueryExpander.expand(None, "q"),
}

for name, bad_call in scenarios.items():
    for mock in raisers.values():
        mock.reset_mock()
    cm_mod.CollectionManager = _make_cm(bad_call)
    guilty_out = os.path.join(tmp, f"report_{name}.json")
    raised = False
    try:
        rh.main(["--execute", "--plan-file", plan_path, "--plan-sha256", plan_sha, "--out", guilty_out])
    except rh.RetrievalError:
        raised = True
    assert raised, f"{name} should have gone red (RetrievalError)"
    assert not os.path.exists(guilty_out), f"{name} should not write a report"
    print(f"GUILTY_{name}_OK")

print("ALL_HC7_OK")
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = "."
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
        assert "SAFE_CASE_OK" in result.stdout
        assert "ALL_HC7_OK" in result.stdout
        for name in (
            "embed",
            "embed_factory",
            "codex",
            "send",
            "cache_set",
            "rerank",
            "cross_rerank",
            "expand",
        ):
            assert f"GUILTY_{name}_OK" in result.stdout


class TestExecuteRequiresInspectedPlanFile:
    """F3/HC6 — `--execute` refuses (before constructing `CollectionManager`)
    unless the named `--plan-file`'s bytes hash to `--plan-sha256` AND its
    parsed plan equals the plan recomputed now."""

    def _write_real_plan(self, tmp_path: Path) -> tuple[Path, str]:
        artifact = rh.load_artifact()
        plan = rh.build_plan(artifact.query_list)
        plan_bytes = rh._canonical_plan_bytes(plan)
        plan_path = tmp_path / "plan.json"
        plan_path.write_bytes(plan_bytes)
        return plan_path, rh._plan_sha256(plan)

    def test_plan_mode_out_writes_bytes_that_hash_to_the_printed_plan_sha256(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out_path = tmp_path / "plan.json"
        exit_code = rh.main(["--out", str(out_path)])
        assert exit_code == 0

        printed = json.loads(capsys.readouterr().out)
        written_bytes = out_path.read_bytes()
        assert hashlib.sha256(written_bytes).hexdigest() == printed["plan_sha256"]
        recomputed = rh.build_plan(rh.load_artifact().query_list)
        assert json.loads(written_bytes) == recomputed

    def test_missing_plan_file_flag_refuses_before_collection_manager(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _boom(self: object, *args: object, **kwargs: object) -> None:
            raise AssertionError("CollectionManager must never be constructed on a refusal")

        monkeypatch.setattr(
            "backend.services.ingestion.collection_manager.CollectionManager.__init__",
            _boom,
        )
        exit_code = rh.main(["--execute", "--plan-sha256", "0" * 64])
        assert exit_code == 1

    def test_missing_plan_sha256_flag_refuses_before_collection_manager(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plan_path, _sha = self._write_real_plan(tmp_path)

        def _boom(self: object, *args: object, **kwargs: object) -> None:
            raise AssertionError("CollectionManager must never be constructed on a refusal")

        monkeypatch.setattr(
            "backend.services.ingestion.collection_manager.CollectionManager.__init__",
            _boom,
        )
        exit_code = rh.main(["--execute", "--plan-file", str(plan_path)])
        assert exit_code == 1

    def test_wrong_plan_sha256_refuses_before_collection_manager(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plan_path, _sha = self._write_real_plan(tmp_path)

        def _boom(self: object, *args: object, **kwargs: object) -> None:
            raise AssertionError("CollectionManager must never be constructed on a refusal")

        monkeypatch.setattr(
            "backend.services.ingestion.collection_manager.CollectionManager.__init__",
            _boom,
        )
        exit_code = rh.main(["--execute", "--plan-file", str(plan_path), "--plan-sha256", "0" * 64])
        assert exit_code == 1

    def test_nonexistent_plan_file_refuses_before_collection_manager(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _boom(self: object, *args: object, **kwargs: object) -> None:
            raise AssertionError("CollectionManager must never be constructed on a refusal")

        monkeypatch.setattr(
            "backend.services.ingestion.collection_manager.CollectionManager.__init__",
            _boom,
        )
        exit_code = rh.main(
            [
                "--execute",
                "--plan-file",
                str(tmp_path / "does_not_exist.json"),
                "--plan-sha256",
                "0" * 64,
            ],
        )
        assert exit_code == 1

    def test_tampered_plan_file_content_refuses_even_with_a_matching_hash_of_itself(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plan_path, _sha = self._write_real_plan(tmp_path)
        tampered = plan_path.read_bytes().replace(
            b'"case":"scored"', b'"case":"unbuildable:no_collections"'
        )
        if tampered == plan_path.read_bytes():
            # No literal match (canonical JSON has no spaces) — fall back to
            # a guaranteed-different, still-valid-JSON single-byte tweak.
            tampered = plan_path.read_bytes()[:-1] + b" "
        tampered_path = tmp_path / "tampered.json"
        tampered_path.write_bytes(tampered)
        tampered_sha = hashlib.sha256(tampered).hexdigest()

        def _boom(self: object, *args: object, **kwargs: object) -> None:
            raise AssertionError("CollectionManager must never be constructed on a refusal")

        monkeypatch.setattr(
            "backend.services.ingestion.collection_manager.CollectionManager.__init__",
            _boom,
        )
        exit_code = rh.main(
            ["--execute", "--plan-file", str(tampered_path), "--plan-sha256", tampered_sha],
        )
        assert exit_code == 1

    def test_matching_plan_file_and_sha256_pass_the_gate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plan_path, correct_sha = self._write_real_plan(tmp_path)
        reached = {"called": False}

        def _mark_reached(self: object, *args: object, **kwargs: object) -> None:
            reached["called"] = True
            raise RuntimeError("stop right after construction — this test only checks the gate")

        monkeypatch.setattr(
            "backend.services.ingestion.collection_manager.CollectionManager.__init__",
            _mark_reached,
        )
        with pytest.raises(RuntimeError, match="stop right after construction"):
            rh.main(["--execute", "--plan-file", str(plan_path), "--plan-sha256", correct_sha])

        assert reached["called"] is True


class TestPlanSha256:
    def test_plan_sha256_excludes_itself_and_is_canonical(self) -> None:
        plan = rh.build_plan([_GENERAL_ENTRY])
        assert "plan_sha256" not in plan
        expected = hashlib.sha256(
            json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            ),
        ).hexdigest()
        assert rh._plan_sha256(plan) == expected

    def test_plan_sha256_changes_when_the_plan_changes(self) -> None:
        plan_a = rh.build_plan([_GENERAL_ENTRY])
        plan_b = rh.build_plan([_VISA_ENTRY])
        assert rh._plan_sha256(plan_a) != rh._plan_sha256(plan_b)


class TestDryRunPlan:
    def test_plan_lists_every_disabled_operation(self) -> None:
        plan = rh.build_plan([_GENERAL_ENTRY])
        disabled_ops = {d["operation"] for d in plan["disabled_by_construction"]}
        assert disabled_ops == {
            "embedding",
            "query_expansion",
            "reranking",
            "cache_read_or_write",
            "health_monitor_write",
            "surface_router",
            "network_fallback",
            "generation",
            "send",
        }
        assert plan["fixed_constants"] == {
            "search_user_level": rh._SEARCH_USER_LEVEL,
            "chunks_per_collection_limit": rh._CHUNKS_PER_COLLECTION_LIMIT,
            "max_chunks": rh._MAX_CHUNKS,
            "max_chunk_chars": rh._MAX_CHUNK_CHARS,
        }
        assert any("a pass does not prove support" in item for item in plan["limitations"])
        assert any("UNVERIFIABLE" in item for item in plan["limitations"])

    def test_plan_is_pure_and_touches_no_client(self) -> None:
        entries = [{"query": f"query {i}", "query_lang": "EN"} for i in range(23)]
        plan = rh.build_plan(entries)
        assert plan["query_count"] == 23
        assert len(plan["cases"]) == 23


class TestBm25EnvPresence:
    def test_reports_presence_never_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BM25_VOCAB_SIZE", "99999")
        monkeypatch.delenv("BM25_K1", raising=False)
        presence = rh.bm25_env_presence()
        assert presence["BM25_VOCAB_SIZE"] is True
        assert presence["BM25_K1"] is False
        assert "99999" not in json.dumps(presence)


class TestNoChunkTextExport:
    async def test_outcome_never_carries_the_sentinel(self) -> None:
        client = _FakeVectorDb(raw_results=_raw_results(text=_SENTINEL))
        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        serialized = json.dumps(rh.outcome_to_dict(outcome))
        assert _SENTINEL not in serialized
        assert outcome.source_refs and all(_SENTINEL not in ref for ref in outcome.source_refs)

    async def test_written_file_never_carries_the_sentinel(self, tmp_path: Path) -> None:
        client = _FakeVectorDb(raw_results=_raw_results(text=_SENTINEL))
        data = _artifact_bytes(
            query_list=[_GENERAL_ENTRY], vectors={f"EN::{_GENERAL_QUERY}": _ONE_VECTOR}
        )
        artifact_path = _write_artifact(tmp_path, data)
        out_path = tmp_path / "report.json"

        # Pin bm25 explicitly (item E, order-dependent failure): this test
        # must not depend on `backend.app.core.config.settings`, because
        # `backend/tests/unit/services/rag/agentic/conftest.py:39-55`
        # replaces `sys.modules["backend.app.core.config"]` at IMPORT time
        # (no fixture, no teardown) with a fake module whose `settings` is a
        # bare `MagicMock()` — its `bm25_vocab_size`/`bm25_k1`/`bm25_b` are
        # then auto-generated child MagicMocks for the REST OF THE PROCESS.
        # In a full `backend/tests/unit/services/rag` run (which recurses
        # into `agentic/`), that conftest is collected before this test
        # runs, so the harness's own lazy `bm25=None` fallback would read
        # those MagicMocks and `json.dump` would fail deep in stdlib. This
        # test's own inputs are pinned instead — it never reads that global.
        pinned_bm25 = rh.BM25Vectorizer(vocab_size=30000, k1=1.5, b=0.75)

        payload = await rh.run_and_write(
            artifact_path=artifact_path,
            expected_sha256=hashlib.sha256(data).hexdigest(),
            query_entries=[_GENERAL_ENTRY],
            resolve_client=_resolver_one(client),
            bm25=pinned_bm25,
            out_path=out_path,
        )

        assert payload["cases"]
        written = out_path.read_text(encoding="utf-8")
        assert _SENTINEL not in written
        assert _SENTINEL not in json.dumps(payload)

    async def test_source_ref_uses_id_when_present(self) -> None:
        client = _FakeVectorDb(raw_results=_raw_results())
        outcome = await rh.run_query(
            query_entry=_GENERAL_ENTRY,
            vector=_ONE_VECTOR,
            resolve_client=_resolver_one(client),
        )
        assert outcome.source_refs
        assert any(":id:" in ref for ref in outcome.source_refs)

    def test_source_ref_falls_back_to_hash_without_id(self) -> None:
        ref = rh._opaque_source_ref(
            {"score_kind": "dense_formatted", "score": 0.5}, collection="visa_oracle"
        )
        assert ref.startswith("visa_oracle:hash:")


class TestBuildReport:
    """HC9/HC10 — the support=None sentence, the canary line, the
    orchestrator-exclusion reason, and the relief band."""

    def _outcome(self, **overrides: Any) -> rh.QueryOutcome:
        return _make_outcome(**overrides)

    def test_header_fields_present_verbatim(self) -> None:
        report = rh.build_report([self._outcome()])
        assert report["support_none_sentence"] == rh._SUPPORT_NONE_SENTENCE
        assert "a pass does not prove support" in report["support_none_sentence"]
        assert report["canary"] == "canary overlap: UNVERIFIABLE (baseline absent on this host)"
        assert "0" != report["canary"]
        assert "QueryPlanner" in report["orchestrator_exclusion_reason"]

    def test_relief_band_tax_and_visa(self) -> None:
        tax_in_band = self._outcome(query_key="k1", query_domain="tax", score=0.12)
        tax_out_of_band = self._outcome(query_key="k2", query_domain="tax", score=0.20)
        visa_in_band = self._outcome(query_key="k3", query_domain="visa", score=0.13)
        report = rh.build_report([tax_in_band, tax_out_of_band, visa_in_band])
        assert set(report["relief_band_cases"]) == {"k1", "k3"}

    def test_divergent_and_unbuildable_excluded_from_relief_band(self) -> None:
        divergent = self._outcome(
            query_key="k1", query_domain="tax", score=0.12, embedding_divergent=True
        )
        unbuildable = self._outcome(
            query_key="k2",
            case="unbuildable:no_collections",
            query_domain=None,
            score=None,
        )
        report = rh.build_report([divergent, unbuildable])
        assert report["relief_band_cases"] == []
        assert report["divergent_count"] == 1
        assert report["inferable_count"] == 0

    def test_manifest_join_shows_both_no_verdict_on_score_kind_disagreement(self) -> None:
        outcome = self._outcome(query_key="EN::same query", score_kinds=("dense_formatted",))
        manifest_case = {
            "query": "same query",
            "query_lang": "EN",
            "expected_generation_gate": "abstain",
            "expected_label_gate": "abstain",
            "provenance_fixture": {"sources": [{"score_kind": "hybrid_rrf_formatted"}]},
        }
        report = rh.build_report([outcome], manifest_cases=[manifest_case])
        row = report["rows"][0]
        assert row["manifest_expected_generation_gate"] == "abstain"
        assert row["score_kind_disagreement"] == {
            "manifest": "hybrid_rrf_formatted",
            "harness": ["dense_formatted"],
            "verdict": None,
        }

    def test_no_manifest_match_has_no_manifest_fields(self) -> None:
        report = rh.build_report([self._outcome(query_key="EN::no such query")])
        row = report["rows"][0]
        assert "manifest_expected_generation_gate" not in row
