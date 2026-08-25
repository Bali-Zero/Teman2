"""No chunk of a document may silently destroy another chunk of the same document.

A chunk's point id is `uuid5(NAMESPACE_LEGAL, chunk_id)` and a chunk_id is
`f"{document_id}_Pasal_{number}"`. An Indonesian law is published together with
its PENJELASAN -- the official article-by-article commentary -- which repeats the
same article numbers. Both therefore produced the same point id, and the second
write silently replaced the first.

Measured on 2026-08-25 by ingesting UU 40/2007 (Perseroan Terbatas): 378 chunks
built, 202 points in Qdrant, 176 articles destroyed by their own commentary. The
text left under Pasal 1, 7, 32, 33 and 109 -- among them the minimum-capital and
paid-up-capital rules a PT PMA is founded on -- was the commentary, in several
cases the literal words "Cukup jelas" ("self-explanatory").

An overwrite is a SUCCESSFUL upsert. Nothing failed and nothing was logged.
"""

import uuid

import pytest

from backend.core.legal.hierarchical_indexer import (
    HierarchicalChunk,
    HierarchicalIndexer,
    LegalIndexIntegrityError,
)

NAMESPACE_LEGAL = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _chunk(chunk_id: str, text: str = "x") -> HierarchicalChunk:
    return HierarchicalChunk(
        chunk_id=chunk_id,
        text=text,
        document_id="UU_40_2007",
        chapter_id=None,
        section_id=None,
        article_id=None,
        hierarchy_path=chunk_id,
        hierarchy_level=3,
        parent_chunk_ids=["UU_40_2007"],
        sibling_chunk_ids=[],
        bab_title=None,
        bab_full_text=None,
        metadata={},
    )


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE_LEGAL, chunk_id))


class _FakeQdrant:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def upsert_documents(self, **kwargs):
        self.calls.append(kwargs)
        return {"success": True, "documents_added": len(kwargs["ids"])}


# ---------------------------------------------------------------------------
# GUILT
# ---------------------------------------------------------------------------


def test_an_article_and_its_commentary_do_not_share_a_point_id():
    body = _chunk("UU_40_2007_Pasal_32", "Modal dasar Perseroan ...")
    penjelasan = _chunk("UU_40_2007_Pasal_32", "Ayat (1) Cukup jelas.")
    renamed = HierarchicalIndexer._disambiguate_chunk_ids([body, penjelasan])
    assert renamed == 1
    assert body.chunk_id != penjelasan.chunk_id
    assert _point_id(body.chunk_id) != _point_id(penjelasan.chunk_id)


def test_the_article_keeps_the_canonical_id_and_the_commentary_moves():
    """Document order decides: the operative article comes first in the PDF, so
    it is the one that keeps `<doc>_Pasal_<n>`. Re-ingesting a corpus that was
    poisoned by this bug therefore CORRECTS the existing point in place rather
    than leaving the commentary sitting on it."""
    body = _chunk("UU_40_2007_Pasal_32", "Modal dasar ...")
    penjelasan = _chunk("UU_40_2007_Pasal_32", "Cukup jelas.")
    HierarchicalIndexer._disambiguate_chunk_ids([body, penjelasan])
    assert body.chunk_id == "UU_40_2007_Pasal_32"
    assert penjelasan.chunk_id == "UU_40_2007_Pasal_32#dup2"


@pytest.mark.asyncio
async def test_the_upsert_path_sends_one_point_per_chunk():
    """The pre-existing completeness guard compared `documents_added` with
    `len(ids)` -- both counted what was SENT, so duplicate ids passed it."""
    indexer = HierarchicalIndexer.__new__(HierarchicalIndexer)
    indexer.qdrant = _FakeQdrant()
    chunks = [_chunk("UU_40_2007_Pasal_32"), _chunk("UU_40_2007_Pasal_32")]
    added = await indexer._upsert_hierarchical_chunks(
        chunks=chunks,
        embeddings=[[0.0], [0.0]],
        sparse_vectors=None,
        qdrant_client=indexer.qdrant,
    )
    sent_ids = indexer.qdrant.calls[0]["ids"]
    assert added == 2
    assert len(set(sent_ids)) == 2, "two chunks collapsed onto one point"


def test_a_third_occurrence_gets_its_own_id():
    chunks = [_chunk("UU_1_2023_Pasal_5") for _ in range(3)]
    assert HierarchicalIndexer._disambiguate_chunk_ids(chunks) == 2
    assert len({c.chunk_id for c in chunks}) == 3


def test_it_refuses_rather_than_overwrites_when_ambiguity_survives():
    """A document that already contains the disambiguation suffix must not be
    quietly re-collided. Fail closed: an overwrite is unrecoverable."""
    chunks = [
        _chunk("UU_1_2023_Pasal_5"),
        _chunk("UU_1_2023_Pasal_5"),
        _chunk("UU_1_2023_Pasal_5#dup2"),
    ]
    with pytest.raises(LegalIndexIntegrityError):
        HierarchicalIndexer._disambiguate_chunk_ids(chunks)


# ---------------------------------------------------------------------------
# INNOCENCE
# ---------------------------------------------------------------------------


def test_unique_chunk_ids_are_left_byte_identical():
    """Re-ingesting an unaffected document must produce the SAME point ids as
    before this change, or the fix would churn the whole corpus."""
    originals = ["UU_40_2007_Pasal_1", "UU_40_2007_Pasal_2", "UU_40_2007_BAB_I"]
    chunks = [_chunk(i) for i in originals]
    assert HierarchicalIndexer._disambiguate_chunk_ids(chunks) == 0
    assert [c.chunk_id for c in chunks] == originals


def test_disambiguation_is_deterministic_across_runs():
    ids = ["A", "A", "B", "A", "B"]
    run_one = [_chunk(i) for i in ids]
    HierarchicalIndexer._disambiguate_chunk_ids(run_one)
    run_two = [_chunk(i) for i in ids]
    HierarchicalIndexer._disambiguate_chunk_ids(run_two)
    assert [c.chunk_id for c in run_one] == [c.chunk_id for c in run_two]


@pytest.mark.asyncio
async def test_the_readable_key_reaches_the_payload():
    """`chunk_id` in the payload is overwritten with the uuid5, which made this
    class of collision undiagnosable from stored data alone."""
    indexer = HierarchicalIndexer.__new__(HierarchicalIndexer)
    indexer.qdrant = _FakeQdrant()
    chunks = [_chunk("UU_40_2007_Pasal_32"), _chunk("UU_40_2007_Pasal_32")]
    await indexer._upsert_hierarchical_chunks(
        chunks=chunks,
        embeddings=[[0.0], [0.0]],
        sparse_vectors=None,
        qdrant_client=indexer.qdrant,
    )
    keys = [m["chunk_key"] for m in indexer.qdrant.calls[0]["metadatas"]]
    assert keys == ["UU_40_2007_Pasal_32", "UU_40_2007_Pasal_32#dup2"]


def test_an_empty_batch_is_not_an_error():
    assert HierarchicalIndexer._disambiguate_chunk_ids([]) == 0
