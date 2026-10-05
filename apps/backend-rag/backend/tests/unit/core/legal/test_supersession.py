"""Tests for pasal-level supersession metadata (PENDING-ARMS 2026-08-25, minimal arm).

Covers the WRITER half: clause parsing from an amendment's own text, identity
triple -> document_id mapping, and the annotator's store writes against a fake
vector db (never a real Qdrant). The RETRIEVAL half is tested in
backend/tests/unit/services/search/test_supersession_guard.py, including the
guilt/innocence proof target.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.core.legal.supersession import (
    PasalSupersession,
    annotate_superseded_pasals,
    build_supersession_payload,
    identity_triple_to_document_id,
    parse_amendment_clauses,
)

# A synthetic but shape-faithful excerpt of an omnibus amendment in the
# UU 63/2024 mold: one article citing the base law, numbered sub-clauses
# rewriting its pasals, then the amendment's own operational articles.
UU_63_2024_STYLE = """
Pasal 1
Beberapa ketentuan dalam Undang-Undang Nomor 6 Tahun 2011 tentang Keimigrasian
diubah sebagai berikut:
1. Ketentuan Pasal 1 angka 1 diubah sehingga berbunyi sebagai berikut:
   Keimigrasian adalah segala sesuatu yang berkaitan dengan ...
2. Ketentuan Pasal 21 diubah sehingga berbunyi sebagai berikut:
   Setiap Orang Asing wajib memiliki Izin Tinggal ...
3. Ketentuan Pasal 83 ayat (1) huruf a diubah sehingga berbunyi sebagai berikut:
   ...

Pasal 2
Ketentuan Pasal 128 Undang-Undang Nomor 6 Tahun 2011 tentang Keimigrasian
dicabut.

Pasal 3
Peraturan Pelaksanaan undang-undang ini harus ditetapkan paling lambat ...
"""

PERMENKUMHAM_11_2024_STYLE = """
Pasal 1
Beberapa ketentuan dalam Peraturan Menteri Nomor 22 Tahun 2023 tentang
Keimigrasian diubah sebagai berikut:
1. Ketentuan Pasal 4 ayat (2) diubah sehingga berbunyi sebagai berikut:
   ...
2. Ketentuan Pasal 17 dicabut.

Pasal 2
Peraturan Menteri ini mulai berlaku pada tanggal diundangkan.
"""


class TestParseAmendmentClauses:
    def test_uu_style_parses_target_and_directives(self) -> None:
        supersessions = parse_amendment_clauses(UU_63_2024_STYLE)
        by_pasal = {(s.base_type_abbrev, s.base_number, s.base_year, s.pasal_number): s.action
                    for s in supersessions}
        assert ("UU", "6", "2011", "1") in by_pasal
        assert ("UU", "6", "2011", "21") in by_pasal
        assert ("UU", "6", "2011", "83") in by_pasal
        assert ("UU", "6", "2011", "128") in by_pasal
        assert by_pasal[("UU", "6", "2011", "21")] == "diubah"
        assert by_pasal[("UU", "6", "2011", "128")] == "dicabut"

    def test_permen_style_uses_permen_abbrev(self) -> None:
        supersessions = parse_amendment_clauses(PERMENKUMHAM_11_2024_STYLE)
        assert {(s.base_type_abbrev, s.base_number, s.base_year) for s in supersessions} == {
            ("Permen", "22", "2023"),
        }
        actions = {s.pasal_number: s.action for s in supersessions}
        assert actions == {"4": "diubah", "17": "dicabut"}

    def test_directive_without_target_in_window_is_skipped(self) -> None:
        # "Pasal 9 dicabut" with NO instrument citation anywhere: there is no
        # honest base to bind it to, so the parser must NOT guess.
        text = "Pasal 9 dicabut dan tidak berlaku lagi sejak diundangkan."
        assert parse_amendment_clauses(text) == []

    def test_non_amending_verbs_do_not_match(self) -> None:
        text = (
            "Beberapa ketentuan dalam Undang-Undang Nomor 6 Tahun 2011 "
            "dinyatakan tetap. Pasal 3 diberlakukan sejak tanggal diundangkan. "
            "Lihat Pasal 7 mengenai kewenangan."
        )
        assert parse_amendment_clauses(text) == []

    def test_empty_text(self) -> None:
        assert parse_amendment_clauses("") == []

    def test_duplicate_directives_deduped(self) -> None:
        text = (
            "Dalam Undang-Undang Nomor 6 Tahun 2011: Pasal 21 diubah. "
            "Kembali disebutkan bahwa Pasal 21 diubah."
        )
        assert len(parse_amendment_clauses(text)) == 1


class TestIdentityTripleToDocumentId:
    def test_complete_triple(self) -> None:
        assert identity_triple_to_document_id("UU", "6", "2011") == "UU_6_2011"

    def test_incomplete_triple_returns_none(self) -> None:
        assert identity_triple_to_document_id("UU", "UNKNOWN", "2011") is None
        assert identity_triple_to_document_id(None, "6", "2011") is None


class TestBuildSupersessionPayload:
    def test_flat_keys(self) -> None:
        sup = PasalSupersession("UU", "6", "2011", "21", "diubah")
        payload = build_supersession_payload(
            sup, amendment_doc_id="UU_63_2024", amendment_label="UU 63/2024"
        )
        assert payload == {
            "superseded_by_document": "UU_63_2024",
            "superseded_pasal_number": "21",
            "superseded_action": "diubah",
            "superseded_by_label": "UU 63/2024",
        }


class _FakeVectorDB:
    """Records the writes the annotator would make against a real store."""

    def __init__(self, points: list[dict[str, Any]]) -> None:
        self._points = points
        self.set_payload_calls: list[dict[str, Any]] = []

    async def scroll_strict(self, *, metadata_filter: dict[str, Any]) -> list[dict[str, Any]]:
        doc_id = metadata_filter.get("document_id")
        return [p for p in self._points if (p.get("payload") or {}).get("document_id") == doc_id]

    async def set_payload(self, *, ids: list[str], payload: dict[str, Any]) -> dict[str, Any]:
        self.set_payload_calls.append({"ids": ids, "payload": payload})
        return {"success": True}


def _base_point(point_id: str, doc_id: str, pasal: str) -> dict[str, Any]:
    return {"id": point_id, "payload": {"document_id": doc_id, "pasal_number": pasal}}


class TestAnnotateSupersededPasals:
    @pytest.mark.asyncio
    async def test_writes_payload_by_point_id(self) -> None:
        fake = _FakeVectorDB(
            [
                _base_point("p21", "UU_6_2011", "21"),
                _base_point("p22", "UU_6_2011", "22"),
            ]
        )
        sup = PasalSupersession("UU", "6", "2011", "21", "diubah")
        summary = await annotate_superseded_pasals(
            fake,
            [sup],
            amendment_doc_id="UU_63_2024",
            amendment_label="UU 63/2024",
        )
        assert summary["annotated_points"] == 1
        assert summary["unresolved"] == []
        assert len(fake.set_payload_calls) == 1
        call = fake.set_payload_calls[0]
        # Only the pasal-21 point is written — pasal 22 of the same document
        # must NOT be touched.
        assert call["ids"] == ["p21"]
        assert call["payload"]["superseded_by_document"] == "UU_63_2024"

    @pytest.mark.asyncio
    async def test_missing_base_chunk_is_unresolved_not_fatal(self) -> None:
        fake = _FakeVectorDB([_base_point("p22", "UU_6_2011", "22")])
        sup = PasalSupersession("UU", "6", "2011", "21", "diubah")
        summary = await annotate_superseded_pasals(
            fake, [sup], amendment_doc_id="UU_63_2024", amendment_label="UU 63/2024"
        )
        assert summary["annotated_points"] == 0
        assert any("UU_6_2011" in u and "Pasal 21" in u for u in summary["unresolved"])
        assert fake.set_payload_calls == []

    @pytest.mark.asyncio
    async def test_dry_run_makes_no_writes(self) -> None:
        fake = _FakeVectorDB([_base_point("p21", "UU_6_2011", "21")])
        sup = PasalSupersession("UU", "6", "2011", "21", "diubah")
        summary = await annotate_superseded_pasals(
            fake,
            [sup],
            amendment_doc_id="UU_63_2024",
            amendment_label="UU 63/2024",
            dry_run=True,
        )
        assert summary["dry_run"] is True
        assert summary["annotated_points"] == 1
        assert fake.set_payload_calls == []
