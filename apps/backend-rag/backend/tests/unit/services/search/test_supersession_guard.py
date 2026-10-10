"""Retrieval-side supersession guard tests, including the guilt/innocence proof.

PROOF TARGET (PENDING-ARMS 2026-08-25): a result set that mixes the
pre-amendment wording (UU 6/2011) with the amendment (UU 63/2024) must surface
the amendment as the top answer and carry the 2011 chunk either demoted with a
superseded marker — while chunks with no supersession metadata (the rest of
the corpus, pre-backfill) pass through untouched. Everything here is
synthetic; no production store is involved.
"""

from __future__ import annotations

from typing import Any

from backend.services.search.supersession_guard import apply_supersession_guard


def _result(
    result_id: str,
    document_id: str,
    score: float,
    *,
    pasal: str | None = None,
    superseded_by_document: str | None = None,
    superseded_action: str = "diubah",
    superseded_by_label: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"document_id": document_id}
    if pasal is not None:
        metadata["pasal_number"] = pasal
    if superseded_by_document is not None:
        metadata["superseded_by_document"] = superseded_by_document
        metadata["superseded_action"] = superseded_action
        metadata["superseded_by_label"] = superseded_by_label or superseded_by_document
    return {"id": result_id, "text": f"text of {result_id}", "metadata": metadata, "score": score}


class TestSupersessionGuard:
    def test_guilt_innocence_proof(self) -> None:
        # The 2011 wording of Pasal 21 out-scores everything, the 2024
        # amendment is second, and an untouched 2011 pasal is third.
        results = [
            _result(
                "a",
                "UU_6_2011",
                0.95,
                pasal="21",
                superseded_by_document="UU_63_2024",
                superseded_by_label="UU 63/2024",
            ),
            _result("b", "UU_63_2024", 0.80, pasal="1"),
            _result("c", "UU_6_2011", 0.70, pasal="99"),
        ]
        guarded = apply_supersession_guard(results)
        assert [r["id"] for r in guarded] == ["b", "c", "a"]
        # The amendment is now the top answer ...
        assert guarded[0]["metadata"]["document_id"] == "UU_63_2024"
        # ... the superseded 2011 chunk is demoted and carries a marker ...
        stale = guarded[-1]
        assert stale["metadata"]["is_superseded"] is True
        assert "UU 63/2024" in stale["metadata"]["superseded_marker"]
        # ... and the innocent 2011 pasal is untouched and ahead of the stale chunk.
        innocent = guarded[1]
        assert innocent["metadata"]["document_id"] == "UU_6_2011"
        assert "is_superseded" not in innocent["metadata"]
        assert "superseded_marker" not in innocent["metadata"]

    def test_noop_when_no_metadata_present(self) -> None:
        results = [
            _result("a", "UU_6_2011", 0.9, pasal="21"),
            _result("b", "UU_63_2024", 0.8, pasal="1"),
        ]
        guarded = apply_supersession_guard(results)
        assert [r["id"] for r in guarded] == ["a", "b"]
        assert all("is_superseded" not in r["metadata"] for r in guarded)

    def test_noop_when_replacement_not_in_result_set(self) -> None:
        # The superseding document did not surface: demoting here would trade a
        # stale answer for NO answer, so the chunk keeps its rank unmarked.
        results = [
            _result(
                "a",
                "UU_6_2011",
                0.9,
                pasal="21",
                superseded_by_document="UU_63_2024",
                superseded_by_label="UU 63/2024",
            ),
            _result("c", "PP_31_2013", 0.7, pasal="5"),
        ]
        guarded = apply_supersession_guard(results)
        assert [r["id"] for r in guarded] == ["a", "c"]
        assert "is_superseded" not in guarded[0]["metadata"]

    def test_stable_order_within_groups(self) -> None:
        results = [
            _result("a", "UU_6_2011", 0.95, pasal="21", superseded_by_document="UU_63_2024"),
            _result("b", "UU_6_2011", 0.90, pasal="22", superseded_by_document="UU_63_2024"),
            _result("c", "UU_63_2024", 0.80, pasal="1"),
            _result("d", "UU_63_2024", 0.75, pasal="2"),
        ]
        guarded = apply_supersession_guard(results)
        assert [r["id"] for r in guarded] == ["c", "d", "a", "b"]

    def test_empty_and_missing_metadata(self) -> None:
        assert apply_supersession_guard([]) == []
        no_metadata = [{"id": "x", "text": "t", "score": 0.5}]
        assert apply_supersession_guard(no_metadata) == no_metadata
