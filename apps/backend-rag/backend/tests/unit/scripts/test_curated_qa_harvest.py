"""SPEC v2 D3 (F1b): scripts/curated_qa_harvest.py

Loads normalized JSONL rows from apps/backend-rag/data/curated_qa/*.jsonl and
writes them to two sinks:
- --faq: FAQ cache (Redis, unscoped keys) via NotebookLMCacheService
- --qdrant: curated_qa Qdrant collection (create-if-missing, flat payload,
  embeds the QUESTION with the frozen text-embedding-3-small)

Plus --dry-run and --purge-domain (FAQ: filtered scan+delete since keys are
opaque content hashes; Qdrant: delete-by-filter on the flat `domain` field).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.services.caching.notebooklm_cache_service import NotebookLMCacheService
from scripts import curated_qa_harvest as harvest

# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
        return deleted

    async def scan_iter(self, match: str | None = None):
        prefix = (match or "*").rstrip("*")
        for key in list(self.store.keys()):
            if key.startswith(prefix):
                yield key


class FakeQdrantClient:
    """In-memory stand-in for the subset of QdrantClient used by the harvester."""

    def __init__(self, collection_name: str = "curated_qa", exists: bool = False) -> None:
        self.collection_name = collection_name
        self._exists = exists
        self.points: dict[str, dict[str, Any]] = {}
        self.created_with: dict[str, Any] | None = None

    async def get_stats(self) -> dict:
        if not self._exists:
            return {"collection_name": self.collection_name, "error": "HTTP 404"}
        return {"collection_name": self.collection_name, "total_documents": len(self.points)}

    async def create_collection(self, vector_size: int, distance: str, **_: Any) -> bool:
        self._exists = True
        self.created_with = {"vector_size": vector_size, "distance": distance}
        return True

    async def upsert_documents(
        self,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        ids: list[str] | None = None,
        flatten_payload: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        assert flatten_payload is True, "curated_qa payload must be flat (data invariant)"
        ids = ids or [str(i) for i in range(len(chunks))]
        for i, point_id in enumerate(ids):
            payload = {**metadatas[i], "text": chunks[i]}
            self.points[point_id] = {"payload": payload, "vector": embeddings[i]}
        return {"success": True, "documents_added": len(chunks)}

    async def scroll(
        self,
        limit: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        for point_id, point in self.points.items():
            if metadata_filter:
                if not all(point["payload"].get(k) == v for k, v in metadata_filter.items()):
                    continue
            results.append({"id": point_id, "payload": point["payload"]})
        return results[:limit]

    async def delete(self, ids: list[str]) -> dict[str, Any]:
        deleted = 0
        for point_id in ids:
            if point_id in self.points:
                del self.points[point_id]
                deleted += 1
        return {"success": True, "deleted_count": deleted}


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1] * 1536 for _ in texts]


def _row(**overrides: Any) -> dict:
    """Default row is FAQ-ELIGIBLE (JELAS, non-price, non-client-specific) —
    most tests below exercise the write MECHANICS (domain scoping, collision
    policy, purge, ...), which requires an eligible row by default.
    Eligibility-gate tests (guilt/innocence) override confidence_class,
    client_specific, or answer explicitly."""
    base = {
        "question": "What is the E33 deposit amount?",
        "answer": "The deposit must be held in a state-owned bank account.",
        "domain": "visa",
        "lang": "en",
        "source_ref": "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1",
        "source_date": "2026-07-15",
        "confidence_class": "JELAS",
        "law_refs": ["Permenkumham 22/2023"],
        "source_priority": 80,
        "verbatim_eligible": True,
        "client_specific": False,
    }
    base.update(overrides)
    return base


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def faq_cache() -> NotebookLMCacheService:
    svc = NotebookLMCacheService()
    svc.redis_client = FakeAsyncRedis()
    return svc


# ── load_jsonl_rows + validate_row ──────────────────────────────────────────


def test_load_jsonl_rows_parses_multiple_files(tmp_path: Path) -> None:
    f1 = _write_jsonl(tmp_path / "a.jsonl", [_row(question="Q1"), _row(question="Q2")])
    f2 = _write_jsonl(tmp_path / "b.jsonl", [_row(question="Q3")])

    rows, malformed = harvest.load_jsonl_rows([f1, f2])

    assert malformed == 0
    assert [r["question"] for r in rows] == ["Q1", "Q2", "Q3"]


def test_load_jsonl_rows_skips_malformed_lines_and_counts_them(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(_row(question="good one"))
        + "\n{not json\n"
        + json.dumps(_row(question="also good"))
        + "\n",
        encoding="utf-8",
    )

    rows, malformed = harvest.load_jsonl_rows([path])

    assert malformed == 1
    assert [r["question"] for r in rows] == ["good one", "also good"]


def test_load_jsonl_rows_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "blank.jsonl"
    path.write_text(json.dumps(_row()) + "\n\n\n", encoding="utf-8")

    rows, malformed = harvest.load_jsonl_rows([path])

    assert malformed == 0
    assert len(rows) == 1


@pytest.mark.parametrize(
    "missing_key",
    [
        "question",
        "answer",
        "domain",
        "lang",
        "source_ref",
        "source_date",
        "confidence_class",
        "law_refs",
        "source_priority",
        "verbatim_eligible",
        "client_specific",
    ],
)
def test_validate_row_flags_missing_required_key(missing_key: str) -> None:
    row = _row()
    del row[missing_key]

    error = harvest.validate_row(row)

    assert error is not None
    assert missing_key in error


def test_validate_row_accepts_null_answer_question_only_seed() -> None:
    row = _row(answer=None, confidence_class="UNSCORED")

    assert harvest.validate_row(row) is None


def test_validate_row_accepts_fully_populated_row() -> None:
    assert harvest.validate_row(_row()) is None


# ── harvest_to_faq ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_harvest_to_faq_writes_domain_scoped_entries(
    faq_cache: NotebookLMCacheService,
) -> None:
    """Phase-0 safety rail (FATAL 1): harvest_to_faq() writes DOMAIN-SCOPED
    keys, not unscoped ones — the legacy unscoped get() must NOT find a
    domain-scoped write (proves the cross-domain collision surface is
    closed at the write path)."""
    from backend.services.caching.notebooklm_cache_service import domain_scope_id

    rows = [_row(question="Q1", domain="visa"), _row(question="Q2", domain="visa")]

    stats = await harvest.harvest_to_faq(rows, faq_cache, dry_run=False)

    assert stats.faq_written == 2
    got = await faq_cache.get("Q1", notebook_id=domain_scope_id("visa"))
    assert got is not None
    assert got["answer"] == "The deposit must be held in a state-owned bank account."
    assert got["metadata"]["source_priority"] == 80
    assert await faq_cache.get("Q1") is None  # legacy unscoped lookup: MISS


@pytest.mark.asyncio
async def test_harvest_to_faq_same_question_different_domains_do_not_collide(
    faq_cache: NotebookLMCacheService,
) -> None:
    """GUILT (FATAL 1): byte-identical question text across two domains must
    land at two DIFFERENT keys, never refuse/overwrite each other."""
    from backend.services.caching.notebooklm_cache_service import domain_scope_id

    rows = [
        _row(question="What documents do I need?", domain="visa", answer="Visa answer"),
        _row(question="What documents do I need?", domain="tax", answer="Tax answer"),
    ]

    stats = await harvest.harvest_to_faq(rows, faq_cache, dry_run=False)

    assert stats.faq_written == 2
    assert stats.faq_collision_refused == 0
    visa_got = await faq_cache.get(
        "What documents do I need?",
        notebook_id=domain_scope_id("visa"),
    )
    tax_got = await faq_cache.get(
        "What documents do I need?",
        notebook_id=domain_scope_id("tax"),
    )
    assert visa_got["answer"] == "Visa answer"
    assert tax_got["answer"] == "Tax answer"


@pytest.mark.asyncio
async def test_harvest_to_faq_skips_answerless_rows(faq_cache: NotebookLMCacheService) -> None:
    rows = [_row(question="has answer"), _row(question="no answer", answer=None)]

    stats = await harvest.harvest_to_faq(rows, faq_cache, dry_run=False)

    assert stats.faq_written == 1
    assert stats.faq_answerless_skipped == 1
    assert await faq_cache.get("no answer") is None


@pytest.mark.asyncio
async def test_harvest_to_faq_dry_run_writes_nothing(faq_cache: NotebookLMCacheService) -> None:
    rows = [_row(question="Q1")]

    stats = await harvest.harvest_to_faq(rows, faq_cache, dry_run=True)

    assert stats.faq_written == 1  # counted as "would write"
    assert await faq_cache.get("Q1") is None  # but nothing actually persisted


@pytest.mark.asyncio
async def test_harvest_to_faq_respects_collision_policy(faq_cache: NotebookLMCacheService) -> None:
    from backend.services.caching.notebooklm_cache_service import domain_scope_id

    rows_high_then_low = [
        _row(question="Q1", answer="high prio", source_priority=90),
    ]
    await harvest.harvest_to_faq(rows_high_then_low, faq_cache, dry_run=False)

    rows_low = [_row(question="Q1", answer="low prio", source_priority=10)]
    stats = await harvest.harvest_to_faq(rows_low, faq_cache, dry_run=False)

    assert stats.faq_collision_refused == 1
    got = await faq_cache.get("Q1", notebook_id=domain_scope_id("visa"))
    assert got["answer"] == "high prio"


# ── FAQ-sink eligibility gate (FATAL 3: verbatim_eligible) ──────────────────


def test_derive_verbatim_eligible_true_for_jelas_clean_row() -> None:
    row = _row(confidence_class="JELAS", client_specific=False, answer="No figures here.")
    assert harvest._derive_verbatim_eligible(row) is True


def test_derive_verbatim_eligible_false_for_non_jelas_class() -> None:
    row = _row(confidence_class="BERSYARAT")
    assert harvest._derive_verbatim_eligible(row) is False


def test_derive_verbatim_eligible_false_for_client_specific() -> None:
    row = _row(confidence_class="JELAS", client_specific=True)
    assert harvest._derive_verbatim_eligible(row) is False


def test_derive_verbatim_eligible_false_for_price_bearing_answer() -> None:
    row = _row(confidence_class="JELAS", answer="The deposit is USD 130,000.")
    assert harvest._derive_verbatim_eligible(row) is False


def test_derive_verbatim_eligible_never_trusts_stored_value() -> None:
    """A row that LIES about its own eligibility (stored True but actually
    BERSYARAT) must still derive False — the stored value is never read for
    the decision."""
    row = _row(confidence_class="BERSYARAT", verbatim_eligible=True)
    assert harvest._derive_verbatim_eligible(row) is False

    row2 = _row(confidence_class="JELAS", verbatim_eligible=False)
    assert harvest._derive_verbatim_eligible(row2) is True


@pytest.mark.asyncio
async def test_harvest_to_faq_bersyarat_row_is_ineligible_skipped(
    faq_cache: NotebookLMCacheService,
) -> None:
    """GUILT — a conditional (BERSYARAT) row must never reach the FAQ sink,
    counted as routine ineligibility (not an error)."""
    rows = [_row(question="Conditional Q", confidence_class="BERSYARAT")]

    stats = await harvest.harvest_to_faq(rows, faq_cache, dry_run=False)

    assert stats.faq_written == 0
    assert stats.faq_ineligible_skipped == 1
    assert stats.faq_price_rejected == 0
    assert await faq_cache.get("Conditional Q") is None


@pytest.mark.asyncio
async def test_harvest_to_faq_client_specific_jelas_row_is_ineligible_skipped(
    faq_cache: NotebookLMCacheService,
) -> None:
    """GUILT — a JELAS row marked client_specific must never reach the FAQ
    sink even though its confidence class alone would qualify."""
    rows = [_row(question="Specific Q", confidence_class="JELAS", client_specific=True)]

    stats = await harvest.harvest_to_faq(rows, faq_cache, dry_run=False)

    assert stats.faq_written == 0
    assert stats.faq_ineligible_skipped == 1
    assert await faq_cache.get("Specific Q") is None


@pytest.mark.asyncio
async def test_harvest_to_faq_price_bearing_jelas_row_is_hard_refused(
    faq_cache: NotebookLMCacheService,
) -> None:
    """GUILT — a would-be-eligible JELAS row whose answer states a price
    figure is REFUSED as a distinct hard-error class, not routine
    ineligibility (a price in a JELAS FINAL answer is an authoring defect,
    not expected policy like a BERSYARAT row)."""
    rows = [
        _row(
            question="Price Q",
            confidence_class="JELAS",
            answer="The processing fee is Rp 5.000.000.",
        ),
    ]

    stats = await harvest.harvest_to_faq(rows, faq_cache, dry_run=False)

    assert stats.faq_written == 0
    assert stats.faq_price_rejected == 1
    assert stats.faq_ineligible_skipped == 0
    assert await faq_cache.get("Price Q") is None


@pytest.mark.asyncio
async def test_harvest_to_faq_jelas_clean_row_flows_to_faq_sink(
    faq_cache: NotebookLMCacheService,
) -> None:
    """INNOCENCE — a genuinely eligible JELAS/non-price/non-client-specific
    row DOES reach the FAQ sink (the gate isn't a blanket refusal)."""
    from backend.services.caching.notebooklm_cache_service import domain_scope_id

    rows = [_row(question="Clean Q", confidence_class="JELAS")]

    stats = await harvest.harvest_to_faq(rows, faq_cache, dry_run=False)

    assert stats.faq_written == 1
    got = await faq_cache.get("Clean Q", notebook_id=domain_scope_id("visa"))
    assert got is not None
    assert got["metadata"]["verbatim_eligible"] is True


@pytest.mark.asyncio
async def test_harvest_to_faq_and_qdrant_jelas_clean_row_flows_to_both_sinks() -> None:
    """INNOCENCE (combined) — a JELAS clean row lands in BOTH sinks; Qdrant
    is never gated by eligibility (grounding always gets all answerable
    rows)."""
    faq = NotebookLMCacheService()
    faq.redis_client = FakeAsyncRedis()
    qdrant_client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    rows = [_row(question="Clean Q", confidence_class="JELAS")]

    faq_stats = await harvest.harvest_to_faq(rows, faq, dry_run=False)
    qdrant_stats = await harvest.harvest_to_qdrant(rows, qdrant_client, embedder, dry_run=False)

    assert faq_stats.faq_written == 1
    assert qdrant_stats.qdrant_written == 1


@pytest.mark.asyncio
async def test_harvest_to_qdrant_bersyarat_row_still_written() -> None:
    """INNOCENCE — Qdrant is grounding-only, not eligibility-gated: a
    BERSYARAT row that is FAQ-ineligible still lands in Qdrant."""
    client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    rows = [_row(question="Conditional Q", confidence_class="BERSYARAT")]

    stats = await harvest.harvest_to_qdrant(rows, client, embedder, dry_run=False)

    assert stats.qdrant_written == 1
    (point,) = client.points.values()
    assert point["payload"]["verbatim_eligible"] is False


# ── ensure_qdrant_collection ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_qdrant_collection_creates_when_missing() -> None:
    client = FakeQdrantClient(exists=False)

    created = await harvest.ensure_qdrant_collection(client)

    assert created is True
    assert client.created_with == {"vector_size": 1536, "distance": "Cosine"}


@pytest.mark.asyncio
async def test_ensure_qdrant_collection_noop_when_exists() -> None:
    client = FakeQdrantClient(exists=True)

    created = await harvest.ensure_qdrant_collection(client)

    assert created is False
    assert client.created_with is None


# ── harvest_to_qdrant ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_harvest_to_qdrant_embeds_question_and_writes_flat_payload() -> None:
    client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    rows = [_row(question="What is the E33 deposit amount?")]

    stats = await harvest.harvest_to_qdrant(rows, client, embedder, dry_run=False)

    assert stats.qdrant_written == 1
    assert embedder.calls == [["What is the E33 deposit amount?"]]
    (point,) = client.points.values()
    assert point["payload"]["text"] == "What is the E33 deposit amount?"
    assert point["payload"]["answer"] == "The deposit must be held in a state-owned bank account."
    assert point["payload"]["domain"] == "visa"
    assert "metadata" not in point["payload"]  # flat, not nested


@pytest.mark.asyncio
async def test_harvest_to_qdrant_same_question_different_domains_get_different_point_ids() -> None:
    """GUILT (FATAL 1): byte-identical question text across two domains must
    upsert to two DIFFERENT Qdrant point ids, never silently overwrite each
    other's answer."""
    client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    rows = [
        _row(question="What documents do I need?", domain="visa", answer="Visa answer"),
        _row(question="What documents do I need?", domain="tax", answer="Tax answer"),
    ]

    stats = await harvest.harvest_to_qdrant(rows, client, embedder, dry_run=False)

    assert stats.qdrant_written == 2
    assert len(client.points) == 2  # not a silent overwrite
    answers = {p["payload"]["domain"]: p["payload"]["answer"] for p in client.points.values()}
    assert answers == {"visa": "Visa answer", "tax": "Tax answer"}


@pytest.mark.asyncio
async def test_harvest_to_qdrant_skips_answerless_rows() -> None:
    client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    rows = [_row(question="has answer"), _row(question="no answer", answer=None)]

    stats = await harvest.harvest_to_qdrant(rows, client, embedder, dry_run=False)

    assert stats.qdrant_written == 1
    assert stats.qdrant_answerless_skipped == 1
    assert len(client.points) == 1


@pytest.mark.asyncio
async def test_harvest_to_qdrant_dry_run_does_not_call_embedder_or_write() -> None:
    client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    rows = [_row(question="Q1")]

    stats = await harvest.harvest_to_qdrant(rows, client, embedder, dry_run=True)

    assert stats.qdrant_written == 1
    assert embedder.calls == []
    assert len(client.points) == 0


# ── purge_domain_faq / purge_domain_qdrant ──────────────────────────────────


@pytest.mark.asyncio
async def test_purge_domain_faq_deletes_only_matching_domain(
    faq_cache: NotebookLMCacheService,
) -> None:
    from backend.services.caching.notebooklm_cache_service import domain_scope_id

    await harvest.harvest_to_faq(
        [
            _row(question="visa Q", domain="visa"),
            _row(question="tax Q", domain="tax"),
        ],
        faq_cache,
        dry_run=False,
    )

    deleted = await harvest.purge_domain_faq(faq_cache, "visa", dry_run=False)

    assert deleted == 1
    assert await faq_cache.get("visa Q", notebook_id=domain_scope_id("visa")) is None
    assert (await faq_cache.get("tax Q", notebook_id=domain_scope_id("tax")))["answer"] is not None


@pytest.mark.asyncio
async def test_purge_domain_faq_dry_run_deletes_nothing(
    faq_cache: NotebookLMCacheService,
) -> None:
    from backend.services.caching.notebooklm_cache_service import domain_scope_id

    await harvest.harvest_to_faq([_row(question="visa Q", domain="visa")], faq_cache, dry_run=False)

    deleted = await harvest.purge_domain_faq(faq_cache, "visa", dry_run=True)

    assert deleted == 1  # counted as "would delete"
    assert (
        await faq_cache.get("visa Q", notebook_id=domain_scope_id("visa")) is not None
    )  # untouched


@pytest.mark.asyncio
async def test_purge_domain_qdrant_deletes_only_matching_domain() -> None:
    client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    await harvest.harvest_to_qdrant(
        [
            _row(question="visa Q", domain="visa"),
            _row(question="tax Q", domain="tax"),
        ],
        client,
        embedder,
        dry_run=False,
    )

    deleted = await harvest.purge_domain_qdrant(client, "visa", dry_run=False)

    assert deleted == 1
    remaining = [p["payload"]["domain"] for p in client.points.values()]
    assert remaining == ["tax"]


@pytest.mark.asyncio
async def test_purge_domain_qdrant_dry_run_deletes_nothing() -> None:
    client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    await harvest.harvest_to_qdrant(
        [_row(question="visa Q", domain="visa")],
        client,
        embedder,
        dry_run=False,
    )

    deleted = await harvest.purge_domain_qdrant(client, "visa", dry_run=True)

    assert deleted == 1
    assert len(client.points) == 1


# ── purge_batch_faq / purge_batch_qdrant (MAJOR 9) ──────────────────────────


@pytest.mark.asyncio
async def test_purge_batch_faq_deletes_only_matching_batch(
    faq_cache: NotebookLMCacheService,
) -> None:
    from backend.services.caching.notebooklm_cache_service import domain_scope_id

    await harvest.harvest_to_faq(
        [_row(question="Q1", domain="visa")],
        faq_cache,
        dry_run=False,
        batch_id="visa-aaa",
    )
    await harvest.harvest_to_faq(
        [_row(question="Q2", domain="visa")],
        faq_cache,
        dry_run=False,
        batch_id="visa-bbb",
    )

    deleted = await harvest.purge_batch_faq(faq_cache, "visa-aaa", dry_run=False)

    assert deleted == 1
    assert await faq_cache.get("Q1", notebook_id=domain_scope_id("visa")) is None
    assert (await faq_cache.get("Q2", notebook_id=domain_scope_id("visa")))["answer"] is not None


@pytest.mark.asyncio
async def test_purge_batch_qdrant_deletes_only_matching_batch() -> None:
    client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    await harvest.harvest_to_qdrant(
        [_row(question="Q1", domain="visa")],
        client,
        embedder,
        dry_run=False,
        batch_id="visa-aaa",
    )
    await harvest.harvest_to_qdrant(
        [_row(question="Q2", domain="visa")],
        client,
        embedder,
        dry_run=False,
        batch_id="visa-bbb",
    )

    deleted = await harvest.purge_batch_qdrant(client, "visa-aaa", dry_run=False)

    assert deleted == 1
    remaining = [p["payload"]["batch_id"] for p in client.points.values()]
    assert remaining == ["visa-bbb"]


# ── compute_batch_id / build_batch_manifest / write_batch_manifest ─────────


def test_compute_batch_id_is_deterministic_and_domain_specific() -> None:
    first = harvest.compute_batch_id("visa", "abc123def456")
    second = harvest.compute_batch_id("visa", "abc123def456")
    assert first == second
    assert first == "visa-abc123def456"[: len("visa-") + 12]
    assert harvest.compute_batch_id("tax", "abc123def456") != first


def test_build_batch_manifest_computes_class_histogram_and_gate_flags(tmp_path: Path) -> None:
    path = _write_jsonl(
        tmp_path / "batch.jsonl",
        [
            _row(question="Q1", confidence_class="JELAS"),
            _row(question="Q2", confidence_class="JELAS", client_specific=True),
            _row(question="Q3", confidence_class="BERSYARAT"),
            _row(question="Q4", confidence_class="JELAS", answer="The fee is Rp 5.000.000."),
        ],
    )
    rows, _ = harvest.load_jsonl_rows([path])

    manifest = harvest.build_batch_manifest(path, rows)

    assert manifest["domain"] == "visa"
    assert manifest["row_count"] == 4
    assert manifest["class_histogram"] == {"JELAS": 3, "BERSYARAT": 1}
    assert manifest["gate_flags"] == {
        "price_bearing_rows": 1,
        "client_specific_rows": 1,
        "verbatim_eligible_rows": 1,  # only Q1 clears all three gates
    }
    assert manifest["qdrant_committed"] is False
    assert manifest["faq_committed"] is False


def test_build_batch_manifest_rejects_mixed_domain_file(tmp_path: Path) -> None:
    path = _write_jsonl(
        tmp_path / "mixed.jsonl",
        [_row(question="Q1", domain="visa"), _row(question="Q2", domain="tax")],
    )
    rows, _ = harvest.load_jsonl_rows([path])

    with pytest.raises(ValueError, match="single domain"):
        harvest.build_batch_manifest(path, rows)


def test_write_batch_manifest_writes_to_manifests_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(harvest, "_DEFAULT_DATA_DIR", tmp_path)
    path = _write_jsonl(tmp_path / "batch.jsonl", [_row(question="Q1", confidence_class="JELAS")])

    manifest = harvest.write_batch_manifest(path, dry_run=False)

    manifest_file = tmp_path / "_manifests" / f"{manifest['batch_id']}.json"
    assert manifest_file.exists()
    on_disk = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert on_disk["batch_id"] == manifest["batch_id"]
    assert on_disk["row_count"] == 1


def test_write_batch_manifest_dry_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(harvest, "_DEFAULT_DATA_DIR", tmp_path)
    path = _write_jsonl(tmp_path / "batch.jsonl", [_row(question="Q1", confidence_class="JELAS")])

    manifest = harvest.write_batch_manifest(path, dry_run=True)

    manifest_file = tmp_path / "_manifests" / f"{manifest['batch_id']}.json"
    assert not manifest_file.exists()


# ── _load_and_gate_batches (FATAL 2: fail-closed manifest gate) ────────────


def test_load_and_gate_batches_refuses_file_without_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(harvest, "_DEFAULT_DATA_DIR", tmp_path)
    path = _write_jsonl(tmp_path / "batch.jsonl", [_row(question="Q1", confidence_class="JELAS")])
    stats = harvest.HarvestStats()

    batches = harvest._load_and_gate_batches([path], stats)

    assert batches == []
    assert stats.manifest_missing_rows == 1


def test_load_and_gate_batches_refuses_on_edited_file_as_missing_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """batch_id is DERIVED from the file's content hash, so editing the file
    after approval produces a DIFFERENT batch_id — the old manifest simply
    isn't found at the new expected path (defense in depth: this is the
    manifest_missing_rows path, not manifest_mismatch_rows, for this
    specific tamper vector — see the sibling test below for the hash-
    mismatch path, which requires a directly-tampered manifest)."""
    monkeypatch.setattr(harvest, "_DEFAULT_DATA_DIR", tmp_path)
    path = _write_jsonl(tmp_path / "batch.jsonl", [_row(question="Q1", confidence_class="JELAS")])
    harvest.write_batch_manifest(path, dry_run=False)

    path.write_text(
        json.dumps(_row(question="Q1 EDITED", confidence_class="JELAS")) + "\n",
        encoding="utf-8",
    )
    stats = harvest.HarvestStats()

    batches = harvest._load_and_gate_batches([path], stats)

    assert batches == []
    assert stats.manifest_missing_rows == 1


def test_load_and_gate_batches_refuses_on_hash_mismatch(tmp_path: Path, monkeypatch) -> None:
    """GUILT — a manifest whose recorded source_file_sha256 was directly
    tampered (drifted from the file it claims to describe) must refuse the
    load even though the manifest FILE is found at the expected batch_id
    path."""
    monkeypatch.setattr(harvest, "_DEFAULT_DATA_DIR", tmp_path)
    path = _write_jsonl(tmp_path / "batch.jsonl", [_row(question="Q1", confidence_class="JELAS")])
    manifest = harvest.write_batch_manifest(path, dry_run=False)

    manifest_path = tmp_path / "_manifests" / f"{manifest['batch_id']}.json"
    tampered = dict(manifest)
    tampered["source_file_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(tampered), encoding="utf-8")
    stats = harvest.HarvestStats()

    batches = harvest._load_and_gate_batches([path], stats)

    assert batches == []
    assert stats.manifest_mismatch_rows == 1


def test_load_and_gate_batches_passes_with_valid_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(harvest, "_DEFAULT_DATA_DIR", tmp_path)
    path = _write_jsonl(tmp_path / "batch.jsonl", [_row(question="Q1", confidence_class="JELAS")])
    manifest = harvest.write_batch_manifest(path, dry_run=False)
    stats = harvest.HarvestStats()

    batches = harvest._load_and_gate_batches([path], stats)

    assert len(batches) == 1
    batch_id, manifest_path, loaded_manifest, rows = batches[0]
    assert batch_id == manifest["batch_id"]
    assert len(rows) == 1
    assert stats.manifest_missing_rows == 0
    assert stats.manifest_mismatch_rows == 0


# ── load_batch (two-sink atomicity, MAJOR 10) ───────────────────────────────


@pytest.mark.asyncio
async def test_load_batch_writes_qdrant_first_then_faq_with_commit_markers(
    tmp_path: Path,
    faq_cache: NotebookLMCacheService,
) -> None:
    from backend.services.caching.notebooklm_cache_service import domain_scope_id

    manifest_path = tmp_path / "visa-abc123def456.json"
    manifest = {
        "batch_id": "visa-abc123def456",
        "domain": "visa",
        "qdrant_committed": False,
        "qdrant_committed_at": None,
        "faq_committed": False,
        "faq_committed_at": None,
    }
    rows = [_row(question="Q1", confidence_class="JELAS")]
    qdrant_client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()

    await harvest.load_batch(
        "visa-abc123def456",
        manifest_path,
        manifest,
        rows,
        faq_cache=faq_cache,
        qdrant_client=qdrant_client,
        embedder=embedder,
        do_faq=True,
        do_qdrant=True,
        dry_run=False,
    )

    assert manifest["qdrant_committed"] is True
    assert manifest["faq_committed"] is True
    assert len(qdrant_client.points) == 1
    assert await faq_cache.get("Q1", notebook_id=domain_scope_id("visa")) is not None
    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert on_disk["qdrant_committed"] is True
    assert on_disk["faq_committed"] is True


@pytest.mark.asyncio
async def test_load_batch_interrupted_run_is_idempotently_re_runnable(
    tmp_path: Path,
    faq_cache: NotebookLMCacheService,
) -> None:
    """GUILT — simulates a crash between the Qdrant phase and the FAQ phase
    (manifest says qdrant_committed=True, faq_committed=False on disk). A
    second run must SKIP the already-committed Qdrant phase and complete
    only the FAQ phase — no double Qdrant write, FAQ ends up written."""
    from backend.services.caching.notebooklm_cache_service import domain_scope_id

    manifest_path = tmp_path / "visa-abc123def456.json"
    interrupted_manifest = {
        "batch_id": "visa-abc123def456",
        "domain": "visa",
        "qdrant_committed": True,
        "qdrant_committed_at": "2026-07-19T00:00:00Z",
        "faq_committed": False,
        "faq_committed_at": None,
    }
    manifest_path.write_text(json.dumps(interrupted_manifest), encoding="utf-8")
    rows = [_row(question="Q1", confidence_class="JELAS")]
    qdrant_client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()

    await harvest.load_batch(
        "visa-abc123def456",
        manifest_path,
        dict(interrupted_manifest),
        rows,
        faq_cache=faq_cache,
        qdrant_client=qdrant_client,
        embedder=embedder,
        do_faq=True,
        do_qdrant=True,
        dry_run=False,
    )

    # Qdrant phase was skipped (not re-embedded) — but idempotent upsert
    # means re-running it WOULD have been harmless too; here we assert the
    # skip actually happened (no embedder call).
    assert embedder.calls == []
    assert await faq_cache.get("Q1", notebook_id=domain_scope_id("visa")) is not None
    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert on_disk["faq_committed"] is True


@pytest.mark.asyncio
async def test_load_batch_dry_run_never_persists_commit_markers(tmp_path: Path) -> None:
    manifest_path = tmp_path / "visa-abc123def456.json"
    manifest = {
        "batch_id": "visa-abc123def456",
        "domain": "visa",
        "qdrant_committed": False,
        "qdrant_committed_at": None,
        "faq_committed": False,
        "faq_committed_at": None,
    }
    rows = [_row(question="Q1", confidence_class="JELAS")]
    qdrant_client = FakeQdrantClient(exists=True)
    embedder = FakeEmbedder()
    faq_cache = NotebookLMCacheService()
    faq_cache.redis_client = FakeAsyncRedis()

    await harvest.load_batch(
        "visa-abc123def456",
        manifest_path,
        manifest,
        rows,
        faq_cache=faq_cache,
        qdrant_client=qdrant_client,
        embedder=embedder,
        do_faq=True,
        do_qdrant=True,
        dry_run=True,
    )

    assert manifest["qdrant_committed"] is False
    assert manifest["faq_committed"] is False
    assert not manifest_path.exists()
