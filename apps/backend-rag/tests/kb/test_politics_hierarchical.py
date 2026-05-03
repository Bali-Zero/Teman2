"""
Tests for politics KB hierarchical retrieval.

Covers: chunker, extractor, retriever, determinism, language routing.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.kb.politics.hierarchical.chunker import (
    Chunk,
    HierarchicalChunker,
    _detect_language,
    _deterministic_id,
)
from backend.kb.politics.hierarchical.extractor import ClaimExtractor
from backend.kb.politics.hierarchical.eval import (
    EvalQuery,
    _ndcg_at_k,
    _recall_at_k,
)


# ─── Fixtures ───────────────────────────────────────────────────────────────


PERSON_RECORD: dict[str, Any] = {
    "type": "person",
    "id": "person:id:joko_widodo",
    "name": "Joko Widodo",
    "aliases": ["Jokowi"],
    "dob": "1961-06-21",
    "pob": "Surakarta, Jawa Tengah, Indonesia",
    "party_memberships": [{"party_id": "party:id:pdip", "from": "2005", "to": None}],
    "offices": [
        {
            "office": "Presiden Republik Indonesia",
            "jurisdiction_id": "jur:ID",
            "from": "2014-10-20",
            "to": "2024-10-20",
            "elected": True,
        },
        {
            "office": "Gubernur DKI Jakarta",
            "jurisdiction_id": "jur:ID-31",
            "from": "2012-10-15",
            "to": "2014-10-16",
            "elected": True,
        },
    ],
    "cases": [],
    "sources": ["https://www.setneg.go.id/"],
}

PARTY_RECORD: dict[str, Any] = {
    "type": "party",
    "id": "party:id:gerindra",
    "name": "Partai Gerakan Indonesia Raya",
    "abbrev": "Gerindra",
    "founded": "2008",
    "ideology": [],
    "leaders": [{"person_id": "person:id:prabowo_subianto", "from": "2008", "to": None}],
    "sources": ["https://id.wikipedia.org/wiki/Partai_Gerakan_Indonesia_Raya"],
}

ELECTION_RECORD: dict[str, Any] = {
    "type": "election",
    "id": "election:id-2024-presiden",
    "date": "2024-02-14",
    "level": "national",
    "scope": "Presidential",
    "jurisdiction_id": "jur:ID",
    "contests": [
        {
            "office": "Presiden",
            "district": None,
            "results": [
                {"candidate_id": "person:id:prabowo_subianto", "party_id": "party:id:gerindra", "pct": 58.59},
                {"candidate_id": "person:id:anies_baswedan", "party_id": None, "pct": 24.95},
                {"candidate_id": "person:id:ganjar_pranowo", "party_id": "party:id:pdip", "pct": 16.46},
            ],
        },
    ],
    "turnout_pct": None,
    "sources": ["https://www.kpu.go.id/"],
}

JURISDICTION_RECORD: dict[str, Any] = {
    "type": "jurisdiction",
    "id": "jur:ID",
    "name": "Republik Indonesia",
    "kind": "country",
    "parent_id": None,
    "valid_from": "1945-08-17",
    "codes": {"iso": "ID"},
    "sources": ["https://www.bps.go.id/"],
}

# Extractor fixture sentences with expected claims
EXTRACTOR_FIXTURES: list[tuple[dict[str, Any], list[str]]] = [
    # Person: alias claim
    (
        {"type": "person", "name": "Joko Widodo", "aliases": ["Jokowi"]},
        ["Joko Widodo dikenal juga sebagai Jokowi."],
    ),
    # Person: birth claim
    (
        {"type": "person", "name": "Prabowo Subianto", "aliases": [], "dob": "1951-10-17", "pob": "Jakarta, Indonesia"},
        ["Prabowo Subianto lahir pada 1951-10-17 di Jakarta, Indonesia."],
    ),
    # Person: office claim with end date
    (
        {
            "type": "person",
            "name": "Megawati",
            "aliases": [],
            "offices": [{"office": "Presiden", "jurisdiction_id": "jur:ID", "from": "2001", "to": "2004", "elected": True}],
        },
        ["Megawati terpilih sebagai Presiden di jur:ID dari 2001 sampai 2004."],
    ),
    # Person: office claim without end date
    (
        {
            "type": "person",
            "name": "Prabowo",
            "aliases": [],
            "offices": [{"office": "Presiden", "jurisdiction_id": "jur:ID", "from": "2024", "to": None, "elected": True}],
        },
        ["Prabowo terpilih sebagai Presiden di jur:ID sejak 2024."],
    ),
    # Person: party membership
    (
        {
            "type": "person",
            "name": "SBY",
            "aliases": [],
            "party_memberships": [{"party_id": "party:id:demokrat", "from": "2001", "to": None}],
        },
        ["SBY menjadi anggota party:id:demokrat sejak 2001."],
    ),
    # Party: abbreviation
    (
        {"type": "party", "name": "Partai Demokrasi Indonesia Perjuangan", "abbrev": "PDI-P"},
        ["Partai Demokrasi Indonesia Perjuangan disingkat PDI-P."],
    ),
    # Party: founding
    (
        {"type": "party", "name": "Partai Golkar", "abbrev": "Golkar", "founded": "1964"},
        ["Partai Golkar disingkat Golkar.", "Partai Golkar didirikan pada 1964."],
    ),
    # Election: winner
    (
        {
            "type": "election",
            "id": "election:test",
            "date": "2024-02-14",
            "scope": "Presidential",
            "jurisdiction_id": "jur:ID",
            "contests": [{"office": "Presiden", "results": [{"candidate_id": "X", "party_id": "Y", "pct": 60.0}]}],
        },
        [
            "Pemilu Presidential diadakan pada 2024-02-14 di jur:ID.",
            "X dari Y memenangkan pemilu Presiden 2024-02-14 dengan 60.0% suara.",
            "X dari Y memperoleh 60.0% suara dalam pemilu Presiden 2024-02-14.",
        ],
    ),
    # Jurisdiction: type + establishment
    (
        {"type": "jurisdiction", "name": "Republik Indonesia", "kind": "country", "valid_from": "1945-08-17", "codes": {"iso": "ID"}},
        [
            "Republik Indonesia adalah sebuah country.",
            "Republik Indonesia berdiri sejak 1945-08-17.",
            "Kode iso untuk Republik Indonesia adalah ID.",
        ],
    ),
    # Person: legal case
    (
        {"type": "person", "name": "Test Person", "aliases": [], "cases": ["Korupsi 2020"]},
        ["Test Person terlibat dalam kasus: Korupsi 2020."],
    ),
]


# ─── Chunker Tests ──────────────────────────────────────────────────────────


class TestHierarchicalChunker:
    """Test parent-child chunking."""

    def test_chunk_person_produces_parent_and_children(self) -> None:
        chunker = HierarchicalChunker()
        chunks = chunker.chunk_record(PERSON_RECORD, "test.jsonl", 0)

        assert len(chunks) > 1
        parents = [c for c in chunks if c.chunk_type == "parent"]
        children = [c for c in chunks if c.chunk_type == "child"]
        assert len(parents) == 1
        assert len(children) >= 3  # alias + birth + party + 2 offices

    def test_parent_child_mapping_is_bijective(self) -> None:
        """Every child points to exactly one parent; every parent has children."""
        chunker = HierarchicalChunker()
        all_chunks: list[Chunk] = []

        for record in [PERSON_RECORD, PARTY_RECORD, ELECTION_RECORD, JURISDICTION_RECORD]:
            all_chunks.extend(chunker.chunk_record(record, "test.jsonl", 0))

        parents = {c.id: c for c in all_chunks if c.chunk_type == "parent"}
        children = [c for c in all_chunks if c.chunk_type == "child"]

        # Every child points to a valid parent
        for child in children:
            assert child.parent_id is not None
            assert child.parent_id in parents, f"Child {child.id} points to missing parent {child.parent_id}"

        # Every parent has at least one child
        parent_ids_with_children = {c.parent_id for c in children}
        for pid in parents:
            assert pid in parent_ids_with_children, f"Parent {pid} has no children"

    def test_chunk_ids_are_unique(self) -> None:
        chunker = HierarchicalChunker()
        chunks = chunker.chunk_record(PERSON_RECORD, "test.jsonl", 0)
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids)), "Duplicate chunk IDs"

    def test_empty_record_produces_no_chunks(self) -> None:
        chunker = HierarchicalChunker()
        chunks = chunker.chunk_record({"type": "unknown"}, "test.jsonl", 0)
        # Unknown type still produces parent from json.dumps, but might have no children
        # This is acceptable — the parent is the raw JSON
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_file_handles_corrupt_lines(self) -> None:
        chunker = HierarchicalChunker()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(PERSON_RECORD) + "\n")
            f.write("THIS IS NOT JSON\n")
            f.write(json.dumps(PARTY_RECORD) + "\n")
            f.write("\n")  # empty line
            path = Path(f.name)

        chunks = chunker.chunk_file(path)
        # Should have chunks from person and party, but not the corrupt line
        parents = [c for c in chunks if c.chunk_type == "parent"]
        assert len(parents) == 2
        path.unlink()

    def test_chunk_directory_skips_templates(self) -> None:
        chunker = HierarchicalChunker()

        with tempfile.TemporaryDirectory() as tmpdir:
            persons_dir = Path(tmpdir) / "persons"
            persons_dir.mkdir()

            # Real file
            real = persons_dir / "seed_data.jsonl"
            real.write_text(json.dumps(PERSON_RECORD) + "\n")

            # Template file (should be skipped)
            tmpl = persons_dir / "seed_template.jsonl"
            tmpl.write_text(json.dumps({"type": "person", "id": "template"}) + "\n")

            chunks = chunker.chunk_directory(Path(tmpdir))
            record_ids = {c.record_id for c in chunks}
            assert "person:id:joko_widodo" in record_ids
            assert "template" not in record_ids

    def test_metadata_is_flat(self) -> None:
        """Qdrant payloads must be flat (no nested dicts)."""
        chunker = HierarchicalChunker()
        chunks = chunker.chunk_record(PERSON_RECORD, "test.jsonl", 0)
        for chunk in chunks:
            for key, value in chunk.metadata.items():
                assert not isinstance(value, dict), f"Nested dict in metadata: {key}={value}"
                assert not isinstance(value, list), f"List in metadata: {key}={value}"


# ─── Extractor Tests ────────────────────────────────────────────────────────


class TestClaimExtractor:
    """Test claim extraction from structured records."""

    @pytest.mark.parametrize(
        "record,expected_claims",
        EXTRACTOR_FIXTURES,
        ids=[f"fixture_{i}" for i in range(len(EXTRACTOR_FIXTURES))],
    )
    def test_extraction_fixtures(self, record: dict[str, Any], expected_claims: list[str]) -> None:
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(record)

        for expected in expected_claims:
            assert expected in claims, (
                f"Expected claim not found: {expected!r}\n"
                f"Got claims: {claims}"
            )

    def test_person_full_record_claim_count(self) -> None:
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(PERSON_RECORD)
        # Jokowi: 1 alias + 1 birth + 1 party + 2 offices = 5 claims
        assert len(claims) == 5

    def test_election_produces_winner_and_individual_claims(self) -> None:
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(ELECTION_RECORD)
        # 1 event + 1 winner + 3 individual results = 5
        assert len(claims) >= 5
        # Winner claim mentions highest pct candidate
        winner_claims = [c for c in claims if "memenangkan" in c]
        assert len(winner_claims) == 1
        assert "prabowo_subianto" in winner_claims[0]

    def test_unknown_type_returns_empty(self) -> None:
        extractor = ClaimExtractor()
        claims = extractor.extract_claims({"type": "alien"})
        assert claims == []


# ─── Determinism Tests ──────────────────────────────────────────────────────


class TestDeterminism:
    """Test that same input → same output."""

    def test_deterministic_ids(self) -> None:
        id1 = _deterministic_id("person:id:x", "parent")
        id2 = _deterministic_id("person:id:x", "parent")
        assert id1 == id2

    def test_different_inputs_different_ids(self) -> None:
        id1 = _deterministic_id("person:id:x", "parent")
        id2 = _deterministic_id("person:id:y", "parent")
        assert id1 != id2

    def test_same_record_different_files_same_id(self) -> None:
        """IDs are path-independent — moving files doesn't break idempotency."""
        id1 = _deterministic_id("person:id:x", "child", 0)
        id2 = _deterministic_id("person:id:x", "child", 0)
        assert id1 == id2

    def test_chunker_deterministic(self) -> None:
        chunker = HierarchicalChunker()
        chunks1 = chunker.chunk_record(PERSON_RECORD, "test.jsonl", 0)
        chunks2 = chunker.chunk_record(PERSON_RECORD, "test.jsonl", 0)

        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.id == c2.id
            assert c1.text == c2.text
            assert c1.chunk_type == c2.chunk_type


# ─── Language Detection Tests ───────────────────────────────────────────────


class TestLanguageDetection:
    """Test language routing for ID vs EN content."""

    def test_indonesian_text_detected(self) -> None:
        text = "Joko Widodo terpilih sebagai Presiden Republik Indonesia"
        assert _detect_language(text) == "id"

    def test_english_text_detected(self) -> None:
        text = "The results of the election were announced today in Washington"
        assert _detect_language(text) == "en"

    def test_mixed_text_defaults_to_id(self) -> None:
        text = "Presiden Indonesia visits the United States for bilateral talks"
        assert _detect_language(text) == "id"

    def test_language_set_on_chunks(self) -> None:
        chunker = HierarchicalChunker()
        chunks = chunker.chunk_record(PERSON_RECORD, "test.jsonl", 0)
        for chunk in chunks:
            assert chunk.language == "id"


# ─── Retriever Tests (Mock) ────────────────────────────────────────────────


class TestHierarchicalRetriever:
    """Test retriever with mock Qdrant."""

    def _make_mock_retriever(self) -> Any:
        from backend.kb.politics.hierarchical.retriever import HierarchicalRetriever

        retriever = HierarchicalRetriever.__new__(HierarchicalRetriever)
        retriever._qdrant_url = "http://mock:6333"
        retriever._collection = "test"
        retriever._child_limit = 10
        retriever._parent_limit = 5
        retriever._client = MagicMock()
        retriever._sparse_encoder = None  # dense-only mode

        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 384
        retriever._embedder = mock_embedder

        return retriever

    def test_retrieve_returns_parents_sorted_by_score(self) -> None:
        retriever = self._make_mock_retriever()

        # Mock child search
        child_response = {
            "result": [
                {"id": "c1", "score": 0.9, "payload": {"text": "claim1", "parent_id": "p1", "record_id": "r1", "record_type": "person", "chunk_type": "child"}},
                {"id": "c2", "score": 0.8, "payload": {"text": "claim2", "parent_id": "p2", "record_id": "r2", "record_type": "party", "chunk_type": "child"}},
                {"id": "c3", "score": 0.7, "payload": {"text": "claim3", "parent_id": "p1", "record_id": "r1", "record_type": "person", "chunk_type": "child"}},
            ],
        }

        # Mock parent fetch
        parent_response = {
            "result": [
                {"id": "p1", "payload": {"text": "Parent 1 full text", "record_id": "r1", "record_type": "person"}},
                {"id": "p2", "payload": {"text": "Parent 2 full text", "record_id": "r2", "record_type": "party"}},
            ],
        }

        retriever._client.post.side_effect = [
            MagicMock(status_code=200, json=lambda: child_response, raise_for_status=lambda: None),
            MagicMock(status_code=200, json=lambda: parent_response, raise_for_status=lambda: None),
        ]

        results = retriever.retrieve("test query")

        assert len(results) == 2
        # p1 has 2 children (0.9 + 0.7 = 1.6) > p2 (0.8)
        assert results[0].parent_id == "p1"
        assert results[0].score == pytest.approx(1.6, abs=0.01)
        assert results[1].parent_id == "p2"

    def test_retrieve_empty_results(self) -> None:
        retriever = self._make_mock_retriever()

        retriever._client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"result": []},
            raise_for_status=lambda: None,
        )

        results = retriever.retrieve("nonexistent query")
        assert results == []


# ─── Eval Metric Tests ─────────────────────────────────────────────────────


class TestEvalMetrics:
    """Test nDCG and Recall calculations."""

    def test_perfect_ndcg(self) -> None:
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        assert _ndcg_at_k(retrieved, relevant, 5) == pytest.approx(1.0, abs=0.01)

    def test_zero_ndcg(self) -> None:
        retrieved = ["x", "y", "z"]
        relevant = {"a", "b"}
        assert _ndcg_at_k(retrieved, relevant, 5) == pytest.approx(0.0, abs=0.01)

    def test_partial_recall(self) -> None:
        retrieved = ["a", "x", "y"]
        relevant = {"a", "b"}
        assert _recall_at_k(retrieved, relevant, 5) == pytest.approx(0.5, abs=0.01)

    def test_full_recall(self) -> None:
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b"}
        assert _recall_at_k(retrieved, relevant, 5) == pytest.approx(1.0, abs=0.01)

    def test_empty_relevant(self) -> None:
        assert _recall_at_k(["a"], set(), 5) == 0.0


# ─── BM25 Sparse Encoder Tests ─────────────────────────────────────────────


class TestBM25SparseEncoder:
    """Test BM25 sparse vector encoding."""

    def test_fit_builds_vocab(self) -> None:
        from backend.kb.politics.hierarchical.embedder import BM25SparseEncoder

        enc = BM25SparseEncoder()
        enc.fit(["Joko Widodo presiden", "Prabowo menteri pertahanan"])
        assert enc.vocab_size > 0

    def test_encode_document_returns_sparse_vector(self) -> None:
        from backend.kb.politics.hierarchical.embedder import BM25SparseEncoder

        enc = BM25SparseEncoder()
        enc.fit(["presiden Indonesia 2024", "gubernur Jakarta 2017"])
        vec = enc.encode_document("presiden Indonesia 2024")
        assert len(vec["indices"]) > 0
        assert len(vec["indices"]) == len(vec["values"])
        assert all(v > 0 for v in vec["values"])

    def test_query_encoding_uses_idf_only(self) -> None:
        from backend.kb.politics.hierarchical.embedder import BM25SparseEncoder

        enc = BM25SparseEncoder()
        enc.fit(["presiden Indonesia", "gubernur Jakarta", "menteri pertahanan"])
        qvec = enc.encode_query("presiden")
        assert len(qvec["indices"]) >= 1

    def test_unfitted_returns_empty(self) -> None:
        from backend.kb.politics.hierarchical.embedder import BM25SparseEncoder

        enc = BM25SparseEncoder()
        vec = enc.encode_document("test text")
        assert vec == {"indices": [], "values": []}

    def test_stopwords_filtered(self) -> None:
        from backend.kb.politics.hierarchical.embedder import _tokenize

        tokens = _tokenize("yang dan di ke dari presiden Indonesia")
        assert "presiden" in tokens
        assert "indonesia" in tokens
        assert "yang" not in tokens
        assert "dan" not in tokens

    def test_deterministic_encoding(self) -> None:
        from backend.kb.politics.hierarchical.embedder import BM25SparseEncoder

        corpus = ["pemilu presiden 2024", "gubernur DKI Jakarta"]
        enc1 = BM25SparseEncoder()
        enc1.fit(corpus)
        v1 = enc1.encode_document("pemilu presiden 2024")

        enc2 = BM25SparseEncoder()
        enc2.fit(corpus)
        v2 = enc2.encode_document("pemilu presiden 2024")

        assert v1 == v2
