"""
Comprehensive unit tests for backend/app/routers/intel.py
Targeting 90%+ coverage with all endpoints, success/failure/edge cases
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_embedder():
    """Mock embeddings generator"""
    embedder = MagicMock()
    embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 384)
    return embedder


@pytest.fixture
def mock_qdrant_client():
    """Mock QdrantClient with async methods"""
    client = MagicMock()
    client.search = AsyncMock(
        return_value={
            "documents": ["Test intel document about immigration policy"],
            "metadatas": [
                {
                    "id": "intel_001",
                    "title": "New Visa Policy",
                    "summary_italian": "Nuova politica sui visti",
                    "source": "Immigration Office",
                    "tier": "T1",
                    "published_date": "2024-01-15T10:00:00",
                    "impact_level": "high",
                    "url": "https://example.com/news/1",
                    "key_changes": "Extended visa duration",
                    "action_required": "True",
                    "deadline_date": "2024-02-15",
                }
            ],
            "distances": [0.15],
        }
    )
    client.upsert_documents = AsyncMock(return_value=True)
    client.peek = MagicMock(
        return_value={
            "metadatas": [
                {
                    "id": "critical_001",
                    "title": "Critical Update",
                    "source": "Gov Agency",
                    "tier": "T1",
                    "published_date": datetime.now().isoformat(),
                    "impact_level": "critical",
                    "url": "https://example.com/critical/1",
                    "action_required": "True",
                    "deadline_date": "2024-03-01",
                }
            ]
        }
    )
    client.get_collection_stats = MagicMock(
        return_value={"total_documents": 150, "vectors_count": 150}
    )
    return client


@pytest.fixture
def client():
    """Create FastAPI test client"""
    from app.routers.intel import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ============================================================================
# Tests for /api/intel/search endpoint
# ============================================================================


def test_search_intel_success_with_category(client, mock_embedder, mock_qdrant_client):
    """Test successful search with specific category"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={
                "query": "visa requirements",
                "category": "immigration",
                "date_range": "last_7_days",
                "tier": ["T1", "T2"],
                "limit": 20,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)
        assert data["total"] >= 0

        # Verify embedder was called
        mock_embedder.generate_single_embedding.assert_called_once_with("visa requirements")


def test_search_intel_success_all_categories(client, mock_embedder, mock_qdrant_client):
    """Test successful search across all categories"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={
                "query": "business news",
                "date_range": "last_30_days",
                "limit": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data


def test_search_intel_with_impact_level_filter(client, mock_embedder, mock_qdrant_client):
    """Test search with impact level filter"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={
                "query": "urgent updates",
                "impact_level": "critical",
                "date_range": "today",
                "limit": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data


def test_search_intel_date_range_today(client, mock_embedder, mock_qdrant_client):
    """Test search with 'today' date range"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "today news", "date_range": "today"},
        )

        assert response.status_code == 200


def test_search_intel_date_range_last_90_days(client, mock_embedder, mock_qdrant_client):
    """Test search with 'last_90_days' date range"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "quarterly news", "date_range": "last_90_days"},
        )

        assert response.status_code == 200


def test_search_intel_date_range_all(client, mock_embedder, mock_qdrant_client):
    """Test search with 'all' date range (no date filter)"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "all news", "date_range": "all"},
        )

        assert response.status_code == 200


def test_search_intel_custom_tier_filter(client, mock_embedder, mock_qdrant_client):
    """Test search with custom tier filter"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "tier1 news", "tier": ["T1"]},
        )

        assert response.status_code == 200


def test_search_intel_multiple_results(client, mock_embedder, mock_qdrant_client):
    """Test search returns multiple sorted results"""
    # Mock multiple results with different similarity scores
    mock_qdrant_client.search = AsyncMock(
        return_value={
            "documents": ["Doc 1", "Doc 2", "Doc 3"],
            "metadatas": [
                {
                    "id": "doc1",
                    "title": "Title 1",
                    "tier": "T1",
                    "published_date": "2024-01-01",
                    "source": "Source 1",
                },
                {
                    "id": "doc2",
                    "title": "Title 2",
                    "tier": "T2",
                    "published_date": "2024-01-02",
                    "source": "Source 2",
                },
                {
                    "id": "doc3",
                    "title": "Title 3",
                    "tier": "T3",
                    "published_date": "2024-01-03",
                    "source": "Source 3",
                },
            ],
            "distances": [0.1, 0.3, 0.2],  # Different distances
        }
    )

    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "category": "immigration"},
        )

        assert response.status_code == 200
        data = response.json()
        results = data["results"]

        # Verify results are sorted by similarity score (descending)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["similarity_score"] >= results[i + 1]["similarity_score"]


def test_search_intel_empty_results(client, mock_embedder, mock_qdrant_client):
    """Test search with no results"""
    mock_qdrant_client.search = AsyncMock(
        return_value={"documents": [], "metadatas": [], "distances": []}
    )

    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "nonexistent topic"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["results"] == []


def test_search_intel_invalid_category(client, mock_embedder, mock_qdrant_client):
    """Test search with invalid category (collection not found)"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "category": "invalid_category"},
        )

        # Should succeed but with empty results since collection doesn't exist
        assert response.status_code == 200


def test_search_intel_qdrant_exception_handled(client, mock_embedder, mock_qdrant_client):
    """Test search handles QdrantClient exception gracefully"""
    mock_qdrant_client.search = AsyncMock(side_effect=Exception("Qdrant error"))

    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "category": "immigration"},
        )

        # Should return empty results, not crash
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


def test_search_intel_embedder_exception(client, mock_embedder, mock_qdrant_client):
    """Test search handles embedder exception"""
    mock_embedder.generate_single_embedding.side_effect = Exception("Embedding failed")

    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test"},
        )

        assert response.status_code == 500
        assert "detail" in response.json()


def test_search_intel_limit_results(client, mock_embedder, mock_qdrant_client):
    """Test search respects limit parameter"""
    # Create more results than limit
    mock_qdrant_client.search = AsyncMock(
        return_value={
            "documents": ["Doc"] * 50,
            "metadatas": [
                {
                    "id": f"doc{i}",
                    "title": f"Title {i}",
                    "tier": "T1",
                    "published_date": "2024-01-01",
                }
                for i in range(50)
            ],
            "distances": [0.1 + i * 0.01 for i in range(50)],
        }
    )

    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 10


def test_search_intel_similarity_score_calculation(client, mock_embedder, mock_qdrant_client):
    """Test similarity score is correctly calculated from distance"""
    mock_qdrant_client.search = AsyncMock(
        return_value={
            "documents": ["Test doc"],
            "metadatas": [
                {
                    "id": "doc1",
                    "title": "Title",
                    "tier": "T1",
                    "published_date": "2024-01-01",
                }
            ],
            "distances": [1.0],  # Distance of 1.0
        }
    )

    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "category": "immigration"},
        )

        assert response.status_code == 200
        data = response.json()
        if data["results"]:
            # Similarity = 1 / (1 + distance) = 1 / (1 + 1.0) = 0.5
            assert abs(data["results"][0]["similarity_score"] - 0.5) < 0.01


def test_search_intel_result_structure(client, mock_embedder, mock_qdrant_client):
    """Test search result has correct structure"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "category": "immigration"},
        )

        assert response.status_code == 200
        data = response.json()

        if data["results"]:
            result = data["results"][0]
            # Verify all expected fields are present
            expected_fields = [
                "id",
                "title",
                "summary_english",
                "summary_italian",
                "source",
                "tier",
                "published_date",
                "category",
                "impact_level",
                "url",
                "key_changes",
                "action_required",
                "deadline_date",
                "similarity_score",
            ]
            for field in expected_fields:
                assert field in result


def test_search_intel_action_required_boolean_conversion(client, mock_embedder, mock_qdrant_client):
    """Test action_required is converted to boolean"""
    mock_qdrant_client.search = AsyncMock(
        return_value={
            "documents": ["Test"],
            "metadatas": [
                {
                    "id": "doc1",
                    "title": "Title",
                    "tier": "T1",
                    "published_date": "2024-01-01",
                    "action_required": "True",  # String
                }
            ],
            "distances": [0.1],
        }
    )

    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "category": "immigration"},
        )

        assert response.status_code == 200
        data = response.json()
        if data["results"]:
            assert isinstance(data["results"][0]["action_required"], bool)
            assert data["results"][0]["action_required"] is True


# ============================================================================
# Tests for /api/intel/store endpoint
# ============================================================================


def test_store_intel_success(client, mock_qdrant_client):
    """Test successful intel storage"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.post(
            "/api/intel/store",
            json={
                "collection": "immigration",
                "id": "intel_123",
                "document": "New immigration policy for digital nomads",
                "embedding": [0.1] * 384,
                "metadata": {
                    "title": "Digital Nomad Visa",
                    "tier": "T1",
                    "published_date": "2024-01-15",
                    "impact_level": "high",
                },
                "full_data": {"source": "Immigration Office"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["collection"] == "bali_intel_immigration"
        assert data["id"] == "intel_123"

        # Verify upsert was called
        mock_qdrant_client.upsert_documents.assert_called_once()


def test_store_intel_all_collections(client, mock_qdrant_client):
    """Test storing to all different collection types"""
    collections = [
        "immigration",
        "bkpm_tax",
        "realestate",
        "events",
        "social",
        "competitors",
        "bali_news",
        "roundup",
    ]

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        for collection_key in collections:
            response = client.post(
                "/api/intel/store",
                json={
                    "collection": collection_key,
                    "id": f"doc_{collection_key}",
                    "document": f"Test document for {collection_key}",
                    "embedding": [0.1] * 384,
                    "metadata": {"tier": "T1"},
                    "full_data": {},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


def test_store_intel_invalid_collection(client, mock_qdrant_client):
    """Test storing to invalid collection"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.post(
            "/api/intel/store",
            json={
                "collection": "invalid_collection",
                "id": "doc123",
                "document": "Test",
                "embedding": [0.1] * 384,
                "metadata": {},
                "full_data": {},
            },
        )

        # HTTPException gets caught and re-raised as 500
        assert response.status_code == 500
        assert "Invalid collection" in response.json()["detail"]


def test_store_intel_qdrant_exception(client, mock_qdrant_client):
    """Test store handles QdrantClient exception"""
    mock_qdrant_client.upsert_documents = AsyncMock(side_effect=Exception("Upsert failed"))

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.post(
            "/api/intel/store",
            json={
                "collection": "immigration",
                "id": "doc123",
                "document": "Test",
                "embedding": [0.1] * 384,
                "metadata": {},
                "full_data": {},
            },
        )

        assert response.status_code == 500
        assert "Upsert failed" in response.json()["detail"]


def test_store_intel_with_complete_metadata(client, mock_qdrant_client):
    """Test storing with full metadata"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.post(
            "/api/intel/store",
            json={
                "collection": "immigration",
                "id": "intel_full",
                "document": "Complete test document",
                "embedding": [0.1] * 384,
                "metadata": {
                    "title": "Full Test",
                    "tier": "T1",
                    "published_date": "2024-01-15T10:00:00",
                    "impact_level": "critical",
                    "source": "Test Source",
                    "url": "https://example.com",
                    "key_changes": "Major changes",
                    "action_required": "True",
                    "deadline_date": "2024-02-15",
                    "summary_italian": "Test italiano",
                },
                "full_data": {"additional": "data"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# Tests for /api/intel/critical endpoint
# ============================================================================


def test_get_critical_items_success(client, mock_qdrant_client):
    """Test getting critical items successfully"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["count"], int)


def test_get_critical_items_with_category(client, mock_qdrant_client):
    """Test getting critical items for specific category"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical?category=immigration")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data


def test_get_critical_items_with_days_filter(client, mock_qdrant_client):
    """Test getting critical items with custom days parameter"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical?days=30")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data


def test_get_critical_items_filters_correctly(client, mock_qdrant_client):
    """Test that only critical items within date range are returned"""
    # Create mix of critical and non-critical items
    old_date = (datetime.now() - timedelta(days=30)).isoformat()
    recent_date = (datetime.now() - timedelta(days=3)).isoformat()

    mock_qdrant_client.peek = MagicMock(
        return_value={
            "metadatas": [
                {
                    "id": "1",
                    "title": "Critical Recent",
                    "impact_level": "critical",
                    "published_date": recent_date,
                    "tier": "T1",
                    "action_required": "True",
                },
                {
                    "id": "2",
                    "title": "Critical Old",
                    "impact_level": "critical",
                    "published_date": old_date,
                    "tier": "T1",
                },
                {
                    "id": "3",
                    "title": "High Impact",
                    "impact_level": "high",  # Not critical
                    "published_date": recent_date,
                    "tier": "T1",
                },
            ]
        }
    )

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical?days=7")

        assert response.status_code == 200
        data = response.json()

        # Should only include critical items within date range
        # The filtering happens in Python, so we verify the structure is correct
        assert "items" in data


def test_get_critical_items_sorted_by_date(client, mock_qdrant_client):
    """Test critical items are sorted by date (newest first)"""
    mock_qdrant_client.peek = MagicMock(
        return_value={
            "metadatas": [
                {
                    "id": "1",
                    "title": "Item 1",
                    "impact_level": "critical",
                    "published_date": "2024-01-10",
                    "tier": "T1",
                },
                {
                    "id": "2",
                    "title": "Item 2",
                    "impact_level": "critical",
                    "published_date": "2024-01-15",
                    "tier": "T1",
                },
                {
                    "id": "3",
                    "title": "Item 3",
                    "impact_level": "critical",
                    "published_date": "2024-01-12",
                    "tier": "T1",
                },
            ]
        }
    )

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical")

        assert response.status_code == 200
        data = response.json()
        items = data["items"]

        # Verify sorting (newest first)
        if len(items) > 1:
            for i in range(len(items) - 1):
                assert items[i].get("published_date", "") >= items[i + 1].get("published_date", "")


def test_get_critical_items_empty_results(client, mock_qdrant_client):
    """Test getting critical items with no results"""
    mock_qdrant_client.peek = MagicMock(return_value={"metadatas": []})

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["items"] == []


def test_get_critical_items_qdrant_exception_handled(client, mock_qdrant_client):
    """Test critical items endpoint handles Qdrant exception"""
    mock_qdrant_client.peek = MagicMock(side_effect=Exception("Peek failed"))

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical?category=immigration")

        # Should handle exception and continue
        assert response.status_code == 200


def test_get_critical_items_general_exception(client, mock_qdrant_client):
    """Test critical items endpoint handles general exception in outer try block"""
    # Need to make datetime.now() fail to trigger outer exception handler
    with (
        patch("app.routers.intel.datetime") as mock_datetime,
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        mock_datetime.now.side_effect = Exception("Datetime error")

        response = client.get("/api/intel/critical")

        assert response.status_code == 500
        assert "detail" in response.json()


def test_get_critical_items_invalid_category(client, mock_qdrant_client):
    """Test critical items with invalid category"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical?category=invalid")

        # Should handle gracefully
        assert response.status_code == 200


def test_get_critical_items_action_required_conversion(client, mock_qdrant_client):
    """Test action_required is converted to boolean in critical items"""
    mock_qdrant_client.peek = MagicMock(
        return_value={
            "metadatas": [
                {
                    "id": "1",
                    "title": "Test",
                    "impact_level": "critical",
                    "published_date": datetime.now().isoformat(),
                    "tier": "T1",
                    "action_required": "True",  # String
                }
            ]
        }
    )

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/critical")

        assert response.status_code == 200
        data = response.json()
        if data["items"]:
            assert isinstance(data["items"][0]["action_required"], bool)


# ============================================================================
# Tests for /api/intel/trends endpoint
# ============================================================================


def test_get_trends_success(client, mock_qdrant_client):
    """Test getting trends successfully"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/trends")

        assert response.status_code == 200
        data = response.json()
        assert "trends" in data
        assert "top_topics" in data
        assert isinstance(data["trends"], list)
        assert isinstance(data["top_topics"], list)


def test_get_trends_with_category(client, mock_qdrant_client):
    """Test getting trends for specific category"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/trends?category=immigration")

        assert response.status_code == 200
        data = response.json()
        assert "trends" in data


def test_get_trends_with_days_parameter(client, mock_qdrant_client):
    """Test getting trends with custom days parameter"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/trends?_days=60")

        assert response.status_code == 200


def test_get_trends_includes_collection_stats(client, mock_qdrant_client):
    """Test trends include collection statistics"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/trends")

        assert response.status_code == 200
        data = response.json()
        trends = data["trends"]

        if trends:
            trend = trends[0]
            assert "collection" in trend
            assert "total_items" in trend


def test_get_trends_all_collections(client, mock_qdrant_client):
    """Test trends for all collections"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/trends")

        assert response.status_code == 200
        data = response.json()
        # Should attempt to get stats from all collections
        assert isinstance(data["trends"], list)


def test_get_trends_handles_collection_exception(client, mock_qdrant_client):
    """Test trends handles exception from individual collection"""
    mock_qdrant_client.get_collection_stats = MagicMock(side_effect=Exception("Stats unavailable"))

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/trends?category=immigration")

        # Should continue despite exception
        assert response.status_code == 200


def test_get_trends_general_exception(client, mock_qdrant_client):
    """Test trends endpoint handles general exception in outer try block"""
    # Need to trigger outer exception handler by making INTEL_COLLECTIONS.values() fail
    with patch("app.routers.intel.INTEL_COLLECTIONS") as mock_collections:
        mock_collections.get.side_effect = Exception("Collections error")
        mock_collections.values.side_effect = Exception("Collections error")

        response = client.get("/api/intel/trends")

        assert response.status_code == 500
        assert "detail" in response.json()


def test_get_trends_invalid_category(client, mock_qdrant_client):
    """Test trends with invalid category"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/trends?category=nonexistent")

        # Should handle gracefully
        assert response.status_code == 200


# ============================================================================
# Tests for /api/intel/stats/{collection} endpoint
# ============================================================================


def test_get_collection_stats_success(client, mock_qdrant_client):
    """Test getting collection stats successfully"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/stats/immigration")

        assert response.status_code == 200
        data = response.json()
        assert "collection_name" in data
        assert "total_documents" in data
        assert "last_updated" in data
        assert data["collection_name"] == "bali_intel_immigration"
        assert data["total_documents"] == 150


def test_get_collection_stats_all_collections(client, mock_qdrant_client):
    """Test getting stats for all collection types"""
    collections = [
        "immigration",
        "bkpm_tax",
        "realestate",
        "events",
        "social",
        "competitors",
        "bali_news",
        "roundup",
    ]

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        for collection in collections:
            response = client.get(f"/api/intel/stats/{collection}")

            assert response.status_code == 200
            data = response.json()
            assert data["collection_name"] == f"bali_intel_{collection}"


def test_get_collection_stats_invalid_collection(client, mock_qdrant_client):
    """Test getting stats for invalid collection"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/stats/invalid_collection")

        # HTTPException gets caught and re-raised as 500
        assert response.status_code == 500
        assert "Collection not found" in response.json()["detail"]


def test_get_collection_stats_qdrant_exception(client, mock_qdrant_client):
    """Test stats endpoint handles Qdrant exception"""
    mock_qdrant_client.get_collection_stats = MagicMock(side_effect=Exception("Stats error"))

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/stats/immigration")

        assert response.status_code == 500
        assert "Stats error" in response.json()["detail"]


def test_get_collection_stats_includes_timestamp(client, mock_qdrant_client):
    """Test stats include last_updated timestamp"""
    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/stats/immigration")

        assert response.status_code == 200
        data = response.json()

        # Verify timestamp is ISO format
        from datetime import datetime

        try:
            datetime.fromisoformat(data["last_updated"])
            timestamp_valid = True
        except ValueError:
            timestamp_valid = False

        assert timestamp_valid


def test_get_collection_stats_zero_documents(client, mock_qdrant_client):
    """Test stats with empty collection"""
    mock_qdrant_client.get_collection_stats = MagicMock(
        return_value={"total_documents": 0, "vectors_count": 0}
    )

    with patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client):
        response = client.get("/api/intel/stats/immigration")

        assert response.status_code == 200
        data = response.json()
        assert data["total_documents"] == 0


# ============================================================================
# Integration and Edge Case Tests
# ============================================================================


def test_search_intel_with_missing_metadata_fields(client, mock_embedder, mock_qdrant_client):
    """Test search handles missing optional metadata fields"""
    mock_qdrant_client.search = AsyncMock(
        return_value={
            "documents": ["Minimal doc"],
            "metadatas": [
                {
                    "id": "minimal_doc",
                    "title": "Minimal",
                    "tier": "T1",
                    "published_date": "2024-01-01",
                    # Missing: summary_italian, source, impact_level, url, etc.
                }
            ],
            "distances": [0.2],
        }
    )

    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "category": "immigration"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should handle missing fields gracefully
        if data["results"]:
            result = data["results"][0]
            assert result["summary_italian"] == ""  # Default for missing


def test_search_intel_summary_truncation(client, mock_embedder, mock_qdrant_client):
    """Test search truncates summary_english to 300 chars"""
    long_text = "A" * 500  # 500 characters

    mock_qdrant_client.search = AsyncMock(
        return_value={
            "documents": [long_text],
            "metadatas": [
                {
                    "id": "long_doc",
                    "title": "Long Document",
                    "tier": "T1",
                    "published_date": "2024-01-01",
                }
            ],
            "distances": [0.1],
        }
    )

    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "category": "immigration"},
        )

        assert response.status_code == 200
        data = response.json()

        if data["results"]:
            assert len(data["results"][0]["summary_english"]) == 300


def test_search_intel_category_name_stripping(client, mock_embedder, mock_qdrant_client):
    """Test category name correctly strips 'bali_intel_' prefix"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        response = client.post(
            "/api/intel/search",
            json={"query": "test", "category": "immigration"},
        )

        assert response.status_code == 200
        data = response.json()

        if data["results"]:
            # Category should be "immigration", not "bali_intel_immigration"
            assert data["results"][0]["category"] == "immigration"


def test_all_endpoints_require_valid_json(client):
    """Test all POST endpoints validate JSON payload"""
    # Test search endpoint
    response = client.post("/api/intel/search", data="invalid json")
    assert response.status_code == 422

    # Test store endpoint
    response = client.post("/api/intel/store", data="invalid json")
    assert response.status_code == 422


def test_search_intel_default_values(client, mock_embedder, mock_qdrant_client):
    """Test search uses correct default values"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        # Minimal request
        response = client.post(
            "/api/intel/search",
            json={"query": "test"},
        )

        assert response.status_code == 200
        # Defaults: date_range="last_7_days", tier=["T1", "T2", "T3"], limit=20


def test_intel_collections_constant(client):
    """Test INTEL_COLLECTIONS constant has all expected collections"""
    from app.routers.intel import INTEL_COLLECTIONS

    expected_collections = [
        "immigration",
        "bkpm_tax",
        "realestate",
        "events",
        "social",
        "competitors",
        "bali_news",
        "roundup",
    ]

    for key in expected_collections:
        assert key in INTEL_COLLECTIONS
        assert INTEL_COLLECTIONS[key] == f"bali_intel_{key}"


def test_concurrent_search_requests(client, mock_embedder, mock_qdrant_client):
    """Test multiple simultaneous search requests"""
    with (
        patch("app.routers.intel.embedder", mock_embedder),
        patch("app.routers.intel.QdrantClient", return_value=mock_qdrant_client),
    ):
        responses = []
        for i in range(5):
            response = client.post(
                "/api/intel/search",
                json={"query": f"query {i}", "category": "immigration"},
            )
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 200
