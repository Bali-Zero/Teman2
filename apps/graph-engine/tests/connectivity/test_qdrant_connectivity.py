"""Qdrant connectivity test — verifies the VectorStore can reach Qdrant."""

import pytest

from nuzantara_graph.services.vector_store import VectorStore
from tests.connectivity.conftest import QDRANT_AVAILABLE


@pytest.mark.skipif(
    not QDRANT_AVAILABLE,
    reason="Qdrant not reachable at http://localhost:6333",
)
class TestQdrantConnectivity:

    @pytest.mark.asyncio
    async def test_health_check(self, local_settings):
        store = VectorStore.from_settings(local_settings)
        try:
            result = await store.health_check()
            assert result["ok"] is True
            assert result["status"] == "healthy"
            assert isinstance(result["collections"], list)
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_list_collections(self, local_settings):
        store = VectorStore.from_settings(local_settings)
        try:
            client = await store._get_client()
            collections = await client.get_collections()
            names = [c.name for c in collections.collections]
            assert isinstance(names, list)
        finally:
            await store.close()
