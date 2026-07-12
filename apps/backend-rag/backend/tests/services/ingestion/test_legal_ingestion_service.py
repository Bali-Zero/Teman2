from __future__ import annotations

import pytest

from backend.services.ingestion import legal_ingestion_service as legal_module
from backend.services.ingestion.legal_ingestion_service import (
    LEGAL_ENV_OVERRIDE_FLAG,
    LegalIngestIntegrityError,
    LegalIngestPreflight,
    build_legal_ingest_preflight,
    validate_legal_ingest_preflight,
    validate_legal_ingest_result,
)


def test_build_legal_ingest_preflight_reads_env_file_and_override_flag(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('QDRANT_URL="http://env-file:6333"\n', encoding="utf-8")

    preflight = build_legal_ingest_preflight(
        configured_qdrant_url="http://configured:6333/",
        requested_collection="legal_unified",
        resolved_collection="legal_unified",
        env_file_path=env_file,
        environ={
            "QDRANT_URL": "http://process:6333",
            LEGAL_ENV_OVERRIDE_FLAG: "yes",
            "ENVIRONMENT": "staging",
        },
    )

    assert preflight.configured_qdrant_url == "http://configured:6333/"
    assert preflight.process_qdrant_url == "http://process:6333"
    assert preflight.env_file_qdrant_url == "http://env-file:6333"
    assert preflight.allow_process_env_override is True
    assert preflight.environment == "staging"


def test_validate_legal_ingest_preflight_rejects_conflicting_env_without_override() -> None:
    preflight = LegalIngestPreflight(
        configured_qdrant_url="http://configured:6333",
        process_qdrant_url="http://process:6333",
        env_file_qdrant_url="http://env-file:6333",
        requested_collection="legal_unified",
        resolved_collection="legal_unified",
        allow_process_env_override=False,
        environment="development",
    )

    with pytest.raises(LegalIngestIntegrityError, match="QDRANT_URL source conflict"):
        validate_legal_ingest_preflight(preflight)


def test_validate_legal_ingest_preflight_rejects_unsafe_collection() -> None:
    preflight = LegalIngestPreflight(
        configured_qdrant_url="http://configured:6333",
        process_qdrant_url=None,
        env_file_qdrant_url=None,
        requested_collection="kbli",
        resolved_collection="kbli",
        allow_process_env_override=False,
        environment="production",
    )

    with pytest.raises(LegalIngestIntegrityError, match="target collection"):
        validate_legal_ingest_preflight(preflight)


def test_validate_legal_ingest_result_requires_success_chunks_and_upserts() -> None:
    validate_legal_ingest_result(
        {"success": True, "chunks_created": "2", "chunks_upserted": "2"}
    )

    with pytest.raises(LegalIngestIntegrityError, match="failed"):
        validate_legal_ingest_result({"success": False, "error": "boom"})

    with pytest.raises(LegalIngestIntegrityError, match="zero chunks"):
        validate_legal_ingest_result({"success": True, "chunks_created": 0})

    with pytest.raises(LegalIngestIntegrityError, match="zero upserts"):
        validate_legal_ingest_result(
            {"success": True, "chunks_created": 1, "chunks_upserted": 0}
        )


def test_detect_legal_document_delegates_to_metadata_extractor() -> None:
    class FakeMetadataExtractor:
        def __init__(self) -> None:
            self.seen: list[str] = []

        def is_legal_document(self, text: str) -> bool:
            self.seen.append(text)
            return "Peraturan" in text

    service = legal_module.LegalIngestionService.__new__(legal_module.LegalIngestionService)
    service.metadata_extractor = FakeMetadataExtractor()

    assert service.detect_legal_document("Peraturan Pemerintah 2024") is True
    assert service.detect_legal_document("plain note") is False
    assert service.metadata_extractor.seen == ["Peraturan Pemerintah 2024", "plain note"]
