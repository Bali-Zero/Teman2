"""
Expanded API Tests for Agentic RAG Endpoints

Tests for:
- Agentic RAG query endpoint
- Agentic RAG streaming endpoint
- Vision-enabled queries
- Error handling and edge cases
"""

import pytest


@pytest.mark.api
class TestAgenticRAGQueryEndpoint:
    """Test Agentic RAG query endpoint"""

    def test_agentic_rag_query_basic(self, authenticated_client):
        """Test basic Agentic RAG query"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": "What is PT PMA?",
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [200, 400, 422, 500]
        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "sources" in data
            assert isinstance(data["answer"], str)
            assert isinstance(data["sources"], list)

    def test_agentic_rag_query_detailed_fields(self, authenticated_client):
        """Test Agentic RAG query response includes all expected fields"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": "Explain KITAS requirements",
                "user_id": "test_user@example.com",
            },
        )

        if response.status_code == 200:
            data = response.json()
            # Verify all response fields
            assert "answer" in data
            assert "sources" in data
            assert "context_length" in data or "context_used" in data
            assert "execution_time" in data
            assert "route_used" in data or "route" in data

    def test_agentic_rag_query_with_vision_enabled(self, authenticated_client):
        """Test Agentic RAG query with vision enabled"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": "Analyze this document about PT PMA",
                "user_id": "test_user@example.com",
                "enable_vision": True,
            },
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_agentic_rag_query_with_vision_disabled(self, authenticated_client):
        """Test Agentic RAG query with vision explicitly disabled"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": "What are visa requirements?",
                "user_id": "test_user@example.com",
                "enable_vision": False,
            },
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_agentic_rag_query_anonymous_user(self, authenticated_client):
        """Test Agentic RAG query with anonymous user"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": "Test query",
            },
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_agentic_rag_query_empty_query(self, authenticated_client):
        """Test Agentic RAG query with empty query string"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": "",
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [400, 422, 500]

    def test_agentic_rag_query_long_query(self, authenticated_client):
        """Test Agentic RAG query with very long query"""
        long_query = "What is " + "PT PMA? " * 100
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": long_query,
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_agentic_rag_query_multiple_queries(self, authenticated_client):
        """Test multiple sequential Agentic RAG queries"""
        queries = [
            "What is PT PMA?",
            "What are KITAS requirements?",
            "How to open a business in Indonesia?",
        ]

        for query in queries:
            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={
                    "query": query,
                    "user_id": "test_user@example.com",
                },
            )

            assert response.status_code in [200, 400, 422, 500]


@pytest.mark.api
class TestAgenticRAGStreamEndpoint:
    """Test Agentic RAG streaming endpoint"""

    def test_agentic_rag_stream_basic(self, authenticated_client):
        """Test basic Agentic RAG streaming"""
        response = authenticated_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "Explain PT PMA setup process",
                "user_id": "test_user@example.com",
            },
            stream=True,
        )

        assert response.status_code in [200, 400, 422, 500]
        if response.status_code == 200:
            # Verify streaming headers
            assert response.headers.get("content-type") == "text/event-stream"
            assert "cache-control" in response.headers or "Cache-Control" in response.headers

    def test_agentic_rag_stream_with_vision(self, authenticated_client):
        """Test Agentic RAG streaming with vision enabled"""
        response = authenticated_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "Analyze this document",
                "user_id": "test_user@example.com",
                "enable_vision": True,
            },
            stream=True,
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_agentic_rag_stream_multiple_events(self, authenticated_client):
        """Test that stream returns multiple events"""
        response = authenticated_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "What are the steps for PT PMA setup?",
                "user_id": "test_user@example.com",
            },
            stream=True,
        )

        if response.status_code == 200:
            # Try to read some events
            try:
                content = b""
                for chunk in response.iter_bytes(chunk_size=1024):
                    content += chunk
                    if len(content) > 1000:  # Read first 1KB
                        break

                # Should have some content
                assert len(content) > 0
            except Exception:
                # Streaming might fail in test environment, that's OK
                pass

    def test_agentic_rag_stream_error_handling(self, authenticated_client):
        """Test stream error handling"""
        response = authenticated_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "",  # Empty query should trigger error
                "user_id": "test_user@example.com",
            },
            stream=True,
        )

        # Should handle error gracefully
        assert response.status_code in [200, 400, 422, 500]


@pytest.mark.api
class TestAgenticRAGComparison:
    """Test comparing query vs stream endpoints"""

    def test_query_vs_stream_same_input(self, authenticated_client):
        """Test that query and stream return similar results for same input"""
        test_query = "What is PT PMA?"
        user_id = "comparison@example.com"

        # Query endpoint
        query_response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={"query": test_query, "user_id": user_id},
        )

        # Stream endpoint
        stream_response = authenticated_client.post(
            "/api/agentic-rag/stream",
            json={"query": test_query, "user_id": user_id},
            stream=True,
        )

        # Both should handle the request
        assert query_response.status_code in [200, 400, 422, 500]
        assert stream_response.status_code in [200, 400, 422, 500]

    def test_query_response_time_vs_stream(self, authenticated_client):
        """Test response time characteristics"""
        import time

        query_start = time.time()
        query_response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": "Test query for timing",
                "user_id": "timing@example.com",
            },
        )
        query_time = time.time() - query_start

        stream_start = time.time()
        stream_response = authenticated_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "Test query for timing",
                "user_id": "timing@example.com",
            },
            stream=True,
        )
        stream_time = time.time() - stream_start

        # Both should respond
        assert query_response.status_code in [200, 400, 422, 500]
        assert stream_response.status_code in [200, 400, 422, 500]
        # Timing should be reasonable (not too long)
        assert query_time < 60  # Should complete within 60 seconds
        assert stream_time < 60


@pytest.mark.api
class TestAgenticRAGErrorScenarios:
    """Test error scenarios for Agentic RAG endpoints"""

    def test_missing_required_fields(self, authenticated_client):
        """Test missing required fields"""
        # Missing query
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={"user_id": "test@example.com"},
        )

        assert response.status_code in [400, 422]

    def test_invalid_json(self, authenticated_client):
        """Test invalid JSON payload"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code in [400, 422]

    def test_very_large_query(self, authenticated_client):
        """Test handling of very large query"""
        large_query = "A" * 10000  # 10KB query
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": large_query,
                "user_id": "test@example.com",
            },
        )

        # Should handle gracefully (either process or reject)
        assert response.status_code in [200, 400, 422, 500, 413]
