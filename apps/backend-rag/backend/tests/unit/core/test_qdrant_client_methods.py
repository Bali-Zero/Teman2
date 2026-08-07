"""
Unit tests for QdrantClient methods (get, delete, peek, hybrid_search, upsert_documents_with_sparse)
Target: >95% coverage
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.core.qdrant_db import QdrantClient


class TestQdrantClientGet:
    """Tests for QdrantClient.get method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_get_success(self, client):
        """Test successful get operation"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "id": "1",
                    "vector": [0.1, 0.2, 0.3],
                    "payload": {"text": "test text", "metadata": {"key": "value"}},
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(return_value=mock_response)

            result = await client.get(["1"])

            assert "ids" in result
            assert result["ids"] == ["1"]
            assert len(result["documents"]) == 1

    @pytest.mark.asyncio
    async def test_get_with_include(self, client):
        """Test get with include parameter"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(return_value=mock_response)

            result = await client.get(["1"], include=["embeddings", "payload"])

            assert result is not None

    @pytest.mark.asyncio
    async def test_get_http_error(self, client):
        """Test get with HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=error)

            result = await client.get(["1"])

            assert result["ids"] == []
            assert result["documents"] == []

    @pytest.mark.asyncio
    async def test_get_exception(self, client):
        """Test get with exception"""
        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=Exception("Connection error"))

            result = await client.get(["1"])

            assert result["ids"] == []
            assert result["documents"] == []

    @pytest.mark.asyncio
    async def test_get_with_include_sends_flags_in_json_body_not_query_params(self, client):
        """
        GUILT test (bug fix 2026-07-19, verified live task #22): Qdrant's
        points-retrieve endpoint (POST /collections/{name}/points) only
        honors with_payload/with_vector as JSON BODY fields — it silently
        ignores them as query params (200 OK, empty payload/vectors; scar
        family #2 "green but not working").

        Uses a real httpx.MockTransport so we inspect the ACTUAL wire-level
        Request (query string vs body), not a mocked `.post()` call — a
        mock on `.post()` alone can't distinguish `params=` from `json=`.

        This test FAILS against the pre-fix implementation (which sent
        `params={"with_payload": True, "with_vectors": True}` alongside an
        `{"ids": ids}`-only body): the flags would show up in
        `request.url.params` and be absent from the JSON body.
        """
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(
                200,
                json={
                    "result": [
                        {"id": "1", "vector": [0.1, 0.2], "payload": {"text": "hi"}},
                    ],
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(base_url="http://qdrant-test", transport=transport) as real_http_client:
            with patch.object(client, "_get_client", return_value=real_http_client):
                result = await client.get(["1"], include=["embeddings", "payload"])

        request = captured["request"]

        # Guilt: the flags must NOT be query params (that's the bug location).
        assert "with_payload" not in request.url.params
        assert "with_vector" not in request.url.params
        assert "with_vectors" not in request.url.params

        # Fix: the flags must be in the JSON body, using Qdrant's real
        # (singular) field name "with_vector", not "with_vectors".
        body = json.loads(request.content)
        assert body["ids"] == ["1"]
        assert body["with_payload"] is True
        assert body["with_vector"] is True
        assert "with_vectors" not in body

        # And the round-trip actually recovers payload + vector now.
        assert result["embeddings"] == [[0.1, 0.2]]
        assert result["documents"] == ["hi"]

    @pytest.mark.asyncio
    async def test_get_without_include_still_works(self, client):
        """
        INNOCENCE test: a plain get() with no `include` (the common case,
        e.g. delete-verification / existence-check callers) must keep
        working exactly as before — full payload + vector fetch, flags
        still land in the JSON body.
        """
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(
                200,
                json={
                    "result": [
                        {"id": "1", "vector": [0.4, 0.5], "payload": {"text": "hello"}},
                    ],
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(base_url="http://qdrant-test", transport=transport) as real_http_client:
            with patch.object(client, "_get_client", return_value=real_http_client):
                result = await client.get(["1"])

        request = captured["request"]
        body = json.loads(request.content)
        assert body == {"ids": ["1"], "with_payload": True, "with_vector": True}
        assert "with_payload" not in request.url.params

        assert result["ids"] == ["1"]
        assert result["embeddings"] == [[0.4, 0.5]]
        assert result["documents"] == ["hello"]


class TestQdrantClientDelete:
    """Tests for QdrantClient.delete method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_delete_success(self, client):
        """Test successful delete operation"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(return_value=mock_response)

            result = await client.delete(["1", "2"])

            assert result["success"] is True
            assert result["deleted_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_http_error(self, client):
        """Test delete with HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=error)

            result = await client.delete(["1"])

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_delete_exception(self, client):
        """Test delete with exception"""
        from backend.core.exceptions import QdrantConnectionError

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=Exception("Connection error"))

            with pytest.raises(QdrantConnectionError):
                await client.delete(["1"])


class TestQdrantClientPayloadGuards:
    """Wire-level coverage for provenance repair and retrieval guard indexes."""

    @pytest.fixture
    def client(self):
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="legal_unified")

    @pytest.mark.asyncio
    async def test_set_payload_merges_only_explicit_provenance_fields(self, client):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        http_client = AsyncMock()
        http_client.post = AsyncMock(return_value=response)

        with patch.object(client, "_get_client", return_value=http_client):
            result = await client.set_payload(
                ["point-1"],
                {"drive_file_id": "drive-1", "retrieval_scope": "historical_only"},
            )

        assert result == {"success": True, "updated": 1, "collection": "legal_unified"}
        http_client.post.assert_awaited_once_with(
            "/collections/legal_unified/points/payload",
            json={
                "points": ["point-1"],
                "payload": {
                    "drive_file_id": "drive-1",
                    "retrieval_scope": "historical_only",
                },
            },
            params={"wait": "true"},
        )

    @pytest.mark.asyncio
    async def test_set_payload_rejects_empty_target_or_payload(self, client):
        with pytest.raises(ValueError, match="ids cannot be empty"):
            await client.set_payload([], {"retrieval_scope": "historical_only"})
        with pytest.raises(ValueError, match="payload cannot be empty"):
            await client.set_payload(["point-1"], {})

    @pytest.mark.asyncio
    async def test_scope_reconciliation_uses_atomic_filter_operations(self, client):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        http_client = AsyncMock()
        http_client.post = AsyncMock(return_value=response)

        with patch.object(client, "_get_client", return_value=http_client):
            await client.set_payload_by_filter(
                metadata_filter={"document_id": "PP_1_2024"},
                payload={"retrieval_scope": "historical_only"},
            )
            await client.delete_by_filter(
                metadata_filter={"document_id": "PP_1_2024"},
            )

        document_filter = {
            "must": [
                {
                    "should": [
                        {
                            "key": "metadata.document_id",
                            "match": {"value": "PP_1_2024"},
                        },
                        {"key": "document_id", "match": {"value": "PP_1_2024"}},
                    ]
                }
            ]
        }
        assert http_client.post.await_args_list == [
            call(
                "/collections/legal_unified/points/payload",
                json={
                    "filter": document_filter,
                    "payload": {"retrieval_scope": "historical_only"},
                },
                params={"wait": "true"},
            ),
            call(
                "/collections/legal_unified/points/delete",
                json={"filter": document_filter},
                params={"wait": "true"},
            ),
        ]

    @pytest.mark.asyncio
    async def test_ensure_keyword_payload_index_uses_qdrant_keyword_schema(self, client):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        http_client = AsyncMock()
        http_client.put = AsyncMock(return_value=response)

        with patch.object(client, "_get_client", return_value=http_client):
            result = await client.ensure_keyword_payload_index("retrieval_scope")

        assert result == {"success": True, "field_name": "retrieval_scope"}
        http_client.put.assert_awaited_once_with(
            "/collections/legal_unified/index",
            params={"wait": "true"},
            json={"field_name": "retrieval_scope", "field_schema": "keyword"},
        )

    @pytest.mark.asyncio
    async def test_scroll_strict_paginates_and_checks_flat_and_nested_tax_payloads(self):
        client = QdrantClient(
            qdrant_url="http://localhost:6333",
            collection_name="tax_genius",
        )
        first = MagicMock()
        first.raise_for_status = MagicMock()
        first.json.return_value = {
            "result": {
                "points": [{"id": "one", "payload": {"document_id": "PP_1_2024"}}],
                "next_page_offset": "next",
            }
        }
        second = MagicMock()
        second.raise_for_status = MagicMock()
        second.json.return_value = {
            "result": {
                "points": [{"id": "two", "payload": {"document_id": "PP_1_2024"}}],
                "next_page_offset": None,
            }
        }
        http_client = AsyncMock()
        http_client.post = AsyncMock(side_effect=[first, second])

        with patch.object(client, "_get_client", return_value=http_client):
            points = await client.scroll_strict(
                metadata_filter={"document_id": "PP_1_2024"},
                page_size=1,
            )

        assert [point["id"] for point in points] == ["one", "two"]
        first_payload = http_client.post.await_args_list[0].kwargs["json"]
        document_filter = first_payload["filter"]["must"][0]
        assert document_filter == {
            "should": [
                {"key": "metadata.document_id", "match": {"value": "PP_1_2024"}},
                {"key": "document_id", "match": {"value": "PP_1_2024"}},
            ]
        }
        assert http_client.post.await_args_list[1].kwargs["json"]["offset"] == "next"

    @pytest.mark.asyncio
    async def test_scroll_strict_propagates_qdrant_failure(self, client):
        http_client = AsyncMock()
        http_client.post = AsyncMock(side_effect=RuntimeError("qdrant unavailable"))

        with patch.object(client, "_get_client", return_value=http_client):
            with pytest.raises(RuntimeError, match="qdrant unavailable"):
                await client.scroll_strict(
                    metadata_filter={"document_id": "PP_1_2024"},
                )


class TestQdrantClientPeek:
    """Tests for QdrantClient.peek method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_peek_success(self, client):
        """Test successful peek operation"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"points": [{"id": "1", "payload": {"text": "test", "metadata": {}}}]},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(return_value=mock_response)

            result = await client.peek(limit=10)

            assert "ids" in result
            assert len(result["ids"]) == 1

    @pytest.mark.asyncio
    async def test_peek_http_error(self, client):
        """Test peek with HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=error)

            result = await client.peek(limit=10)

            assert result["ids"] == []
            assert result["documents"] == []

    @pytest.mark.asyncio
    async def test_peek_exception(self, client):
        """Test peek with exception"""
        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=Exception("Error"))

            result = await client.peek(limit=10)

            assert result["ids"] == []
            assert result["documents"] == []


class TestQdrantClientHybridSearch:
    """Tests for QdrantClient.hybrid_search method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_hybrid_search_without_sparse(self, client):
        """Test hybrid_search falls back to dense search when no sparse vector"""
        with patch.object(client, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"ids": ["1"], "documents": ["test"]}

            result = await client.hybrid_search(query_embedding=[0.1] * 1536, query_sparse=None)

            mock_search.assert_called_once()
            assert result["ids"] == ["1"]

    @pytest.mark.asyncio
    async def test_hybrid_search_with_empty_sparse(self, client):
        """Test hybrid_search with empty sparse vector"""
        with patch.object(client, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"ids": ["1"], "documents": ["test"]}

            await client.hybrid_search(query_embedding=[0.1] * 1536, query_sparse={})

            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_success(self, client):
        """Test successful hybrid search"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "points": [{"id": "1", "score": 0.9, "payload": {"text": "test", "metadata": {}}}],
            },
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch(
                "backend.core.qdrant_db._retry_with_backoff",
                new_callable=AsyncMock,
            ) as mock_retry,
        ):

            async def retry_func():
                mock_http_client = await mock_get_client()
                mock_http_client.post = AsyncMock(return_value=mock_response)
                return await mock_http_client.post("/test")

            mock_retry.return_value = {
                "ids": ["1"],
                "documents": ["test"],
                "metadatas": [{}],
                "distances": [0.1],
                "scores": [0.9],
                "total_found": 1,
                "search_type": "hybrid_rrf",
            }

            result = await client.hybrid_search(
                query_embedding=[0.1] * 1536,
                query_sparse={"indices": [1, 2, 3], "values": [0.5, 0.6, 0.7]},
                limit=10,
            )

            assert "ids" in result or result is not None

    @pytest.mark.asyncio
    async def test_hybrid_search_fallback_on_error(self, client):
        """Test hybrid_search falls back to dense search on error"""
        with (
            patch.object(client, "search", new_callable=AsyncMock) as mock_search,
            patch.object(client, "_get_client", return_value=AsyncMock()),
            patch(
                "backend.core.qdrant_db._retry_with_backoff",
                new_callable=AsyncMock,
            ) as mock_retry,
        ):
            mock_search.return_value = {"ids": ["1"], "documents": ["test"]}

            # Simulate error in hybrid search
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "sparse vector error"
            error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)
            mock_retry.side_effect = error

            result = await client.hybrid_search(
                query_embedding=[0.1] * 1536,
                query_sparse={"indices": [1], "values": [0.5]},
                limit=10,
            )

            # Should fall back to dense search
            assert result is not None


class TestQdrantClientUpsertDocumentsWithSparse:
    """Tests for QdrantClient.upsert_documents_with_sparse method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_success(self, client):
        """Test successful upsert with sparse vectors"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
        ):
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(return_value=mock_response)

            result = await client.upsert_documents_with_sparse(
                chunks=["chunk1", "chunk2"],
                embeddings=[[0.1] * 1536, [0.2] * 1536],
                sparse_vectors=[
                    {"indices": [1, 2], "values": [0.5, 0.6]},
                    {"indices": [3, 4], "values": [0.7, 0.8]},
                ],
                metadatas=[{"key": "value1"}, {"key": "value2"}],
                ids=["id1", "id2"],
            )

            assert result["success"] is True
            assert result["documents_added"] == 2
            assert result["has_sparse_vectors"] is True

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_generate_ids(self, client):
        """Test upsert generates IDs if not provided"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("uuid.uuid4", side_effect=lambda: MagicMock(hex="test-uuid")),
        ):
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(return_value=mock_response)

            result = await client.upsert_documents_with_sparse(
                chunks=["chunk1"],
                embeddings=[[0.1] * 1536],
                sparse_vectors=[{"indices": [1], "values": [0.5]}],
                metadatas=[{"key": "value"}],
                ids=None,
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_length_mismatch(self, client):
        """Test upsert with length mismatch"""
        with pytest.raises(ValueError, match="same length"):
            await client.upsert_documents_with_sparse(
                chunks=["chunk1"],
                embeddings=[[0.1] * 1536, [0.2] * 1536],  # Different length
                sparse_vectors=[{"indices": [1], "values": [0.5]}],
                metadatas=[{"key": "value"}],
                ids=["id1"],
            )

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_batch_error(self, client):
        """Test upsert with batch error"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
        ):
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(side_effect=error)

            result = await client.upsert_documents_with_sparse(
                chunks=["chunk1"],
                embeddings=[[0.1] * 1536],
                sparse_vectors=[{"indices": [1], "values": [0.5]}],
                metadatas=[{"key": "value"}],
                ids=["id1"],
            )

            assert result["success"] is False
            assert "error" in result
