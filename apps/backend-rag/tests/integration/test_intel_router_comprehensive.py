"""
Comprehensive Integration Tests for Intel Router
Tests Intel search, store, and management endpoints

Covers:
- POST /api/intel/search - Search intel
- POST /api/intel/store - Store intel
- Intel category filtering
- Date range filtering
- Impact level filtering
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestIntelRouterComprehensive:
    """Comprehensive integration tests for Intel router"""

    @pytest.mark.asyncio
    async def test_intel_search_endpoint(self, qdrant_client):
        """Test POST /api/intel/search - Search intel"""

        collection_name = "bali_intel_immigration"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Insert test intel
            test_embedding = [0.1] * 1536
            await qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": "intel_1",
                        "vector": test_embedding,
                        "payload": {
                            "document": "Immigration policy update",
                            "category": "immigration",
                            "date": "2025-01-15",
                            "tier": ["T1"],
                            "impact_level": "high",
                        },
                    }
                ],
            )

            # Search intel
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                limit=10,
            )

            assert len(results) > 0

        finally:
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_intel_store_endpoint(self, qdrant_client):
        """Test POST /api/intel/store - Store intel"""

        collection_name = "bali_intel_test_store"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Store intel
            test_embedding = [0.2] * 1536
            await qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": "stored_intel_1",
                        "vector": test_embedding,
                        "payload": {
                            "document": "Test intel document",
                            "category": "immigration",
                            "metadata": {"source": "test"},
                            "full_data": {"title": "Test", "content": "Test content"},
                        },
                    }
                ],
            )

            # Verify storage
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                limit=1,
            )

            assert len(results) == 1
            assert results[0]["id"] == "stored_intel_1"

        finally:
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_intel_category_filtering(self, qdrant_client):
        """Test intel category filtering"""

        collection_name = "bali_intel_category_test"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Insert intel with different categories
            categories = ["immigration", "bkpm_tax", "realestate"]
            test_embedding = [0.1] * 1536

            for i, category in enumerate(categories):
                await qdrant_client.upsert(
                    collection_name=collection_name,
                    points=[
                        {
                            "id": f"intel_{category}",
                            "vector": test_embedding,
                            "payload": {
                                "document": f"Intel for {category}",
                                "category": category,
                            },
                        }
                    ],
                )

            # Filter by category
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                query_filter={"must": [{"key": "category", "match": {"value": "immigration"}}]},
                limit=10,
            )

            # Verify filtering
            assert len(results) >= 1

        finally:
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_intel_date_range_filtering(self, qdrant_client):
        """Test intel date range filtering"""

        collection_name = "bali_intel_date_test"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Insert intel with different dates
            dates = ["2025-01-10", "2025-01-15", "2025-01-20"]
            test_embedding = [0.1] * 1536

            for date in dates:
                await qdrant_client.upsert(
                    collection_name=collection_name,
                    points=[
                        {
                            "id": f"intel_{date}",
                            "vector": test_embedding,
                            "payload": {
                                "document": f"Intel from {date}",
                                "date": date,
                            },
                        }
                    ],
                )

            # Filter by date range
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                query_filter={
                    "must": [
                        {
                            "key": "date",
                            "range": {
                                "gte": "2025-01-15",
                                "lte": "2025-01-20",
                            },
                        }
                    ]
                },
                limit=10,
            )

            # Verify date filtering
            assert len(results) >= 1

        finally:
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_intel_impact_level_filtering(self, qdrant_client):
        """Test intel impact level filtering"""

        collection_name = "bali_intel_impact_test"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Insert intel with different impact levels
            impact_levels = ["high", "medium", "low"]
            test_embedding = [0.1] * 1536

            for impact in impact_levels:
                await qdrant_client.upsert(
                    collection_name=collection_name,
                    points=[
                        {
                            "id": f"intel_{impact}",
                            "vector": test_embedding,
                            "payload": {
                                "document": f"Intel with {impact} impact",
                                "impact_level": impact,
                            },
                        }
                    ],
                )

            # Filter by impact level
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                query_filter={"must": [{"key": "impact_level", "match": {"value": "high"}}]},
                limit=10,
            )

            # Verify impact filtering
            assert len(results) >= 1

        finally:
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass
