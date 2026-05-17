"""Qdrant payload shape tests for legal/regulatory ingestion."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_upsert_documents_can_write_flat_payload_without_nested_metadata() -> None:
    from backend.core.qdrant_db import QdrantClient

    http_client = AsyncMock()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    http_client.put = AsyncMock(return_value=response)

    client = QdrantClient(qdrant_url="http://localhost:6333", collection_name="legal_unified")

    with patch.object(client, "_get_client", new=AsyncMock(return_value=http_client)):
        result = await client.upsert_documents(
            chunks=["Pasal 1 text"],
            embeddings=[[0.1] * 1536],
            metadatas=[{"document_id": "PP_123_2024", "legal_type": "PP"}],
            ids=["00000000-0000-0000-0000-000000000001"],
            flatten_payload=True,
        )

    assert result["success"] is True
    payload = http_client.put.call_args.kwargs["json"]["points"][0]["payload"]
    assert payload["text"] == "Pasal 1 text"
    assert payload["document_id"] == "PP_123_2024"
    assert payload["legal_type"] == "PP"
    assert "metadata" not in payload


def test_extract_point_metadata_supports_nested_and_flat_payloads() -> None:
    from backend.core.qdrant_db import _extract_point_metadata

    assert _extract_point_metadata(
        {"text": "nested text", "metadata": {"document_id": "nested-doc"}}
    ) == {"document_id": "nested-doc"}
    assert _extract_point_metadata(
        {"text": "flat text", "document_id": "flat-doc", "legal_type": "PP"}
    ) == {"document_id": "flat-doc", "legal_type": "PP"}
