"""Wiring tests for STAGE 6.5 — supersession annotation at ingest of an amendment.

The method under test (LegalIngestionService._annotate_superseded_pasals) is
the ingest-side trigger: parse this instrument's own "Pasal X diubah" clauses,
then stamp the base document's chunks. Everything is synthetic; the vector db
is a recording fake.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")


AMENDMENT_TEXT = """
Pasal 1
Beberapa ketentuan dalam Undang-Undang Nomor 6 Tahun 2011 tentang Keimigrasian
diubah sebagai berikut:
1. Ketentuan Pasal 21 diubah sehingga berbunyi sebagai berikut:
   Setiap Orang Asing wajib memiliki Izin Tinggal yang sah.

Pasal 2
Peraturan Pelaksanaan ditetapkan paling lambat 1 (satu) tahun.
"""


def _build_service():
    with (
        patch("backend.services.ingestion.legal_ingestion_service.LegalCleaner") as mc,
        patch("backend.services.ingestion.legal_ingestion_service.LegalMetadataExtractor") as mme,
        patch("backend.services.ingestion.legal_ingestion_service.LegalStructureParser") as msp,
        patch("backend.services.ingestion.legal_ingestion_service.LegalChunker") as mch,
        patch("backend.services.ingestion.legal_ingestion_service.BM25Vectorizer") as mbm,
        patch(
            "backend.services.ingestion.legal_ingestion_service.create_embeddings_generator"
        ) as mce,
        patch(
            "backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
            return_value="legal_unified",
        ),
        patch("backend.services.ingestion.legal_ingestion_service.QdrantClient") as mqd,
        patch("backend.services.ingestion.legal_ingestion_service.TierClassifier") as mtc,
        patch("backend.services.ingestion.legal_ingestion_service.HierarchicalIndexer") as mhi,
    ):
        for m in (mc, mme, msp, mch, mbm, mce, mtc, mhi):
            m.return_value = MagicMock()
        _vector_db = MagicMock()
        _vector_db.scroll_strict = AsyncMock(return_value=[])
        _vector_db.ensure_keyword_payload_index = AsyncMock(return_value={"success": True})
        _vector_db.set_payload = AsyncMock(return_value={"success": True})
        mqd.return_value = _vector_db

        from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

        return LegalIngestionService(collection_name="legal_unified")


class TestAnnotateSupersededPasalsWiring:
    @pytest.mark.asyncio
    async def test_amendment_text_annotates_base_chunks(self) -> None:
        service = _build_service()
        service.vector_db.scroll_strict = AsyncMock(
            return_value=[{"id": "pt-21", "payload": {"document_id": "UU_6_2011", "pasal_number": "21"}}]
        )
        summary = await service._annotate_superseded_pasals(
            service.vector_db,
            cleaned_text=AMENDMENT_TEXT,
            amendment_metadata={"type_abbrev": "UU", "number": "63", "year": "2024"},
            amendment_doc_id="UU_63_2024",
        )
        assert summary["status"] == "annotated"
        assert summary["annotated_points"] == 1
        service.vector_db.set_payload.assert_awaited_once()
        payload = service.vector_db.set_payload.await_args.kwargs["payload"]
        assert payload["superseded_by_document"] == "UU_63_2024"
        assert payload["superseded_by_label"] == "UU 63/2024"

    @pytest.mark.asyncio
    async def test_plain_law_has_no_clauses(self) -> None:
        service = _build_service()
        summary = await service._annotate_superseded_pasals(
            service.vector_db,
            cleaned_text="Pasal 1\nSetiap warga negara mempunyai hak yang sama.",
            amendment_metadata={"type_abbrev": "UU", "number": "8", "year": "2024"},
            amendment_doc_id="UU_8_2024",
        )
        assert summary["status"] == "no_clauses"
        service.vector_db.scroll_strict.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_store_failure_is_reported_not_raised(self) -> None:
        service = _build_service()
        service.vector_db.scroll_strict = AsyncMock(
            return_value=[{"id": "pt-21", "payload": {"document_id": "UU_6_2011", "pasal_number": "21"}}]
        )
        service.vector_db.set_payload = AsyncMock(side_effect=RuntimeError("qdrant down"))
        summary = await service._annotate_superseded_pasals(
            service.vector_db,
            cleaned_text=AMENDMENT_TEXT,
            amendment_metadata={"type_abbrev": "UU", "number": "63", "year": "2024"},
            amendment_doc_id="UU_63_2024",
        )
        assert summary["status"] == "error"
        assert "qdrant down" in summary["error"]
