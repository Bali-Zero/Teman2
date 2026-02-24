"""Qdrant connectivity test — verifies the VectorStore can reach Qdrant."""

import socket

import pytest

from nuzantara_graph.services.vector_store import VectorStore


def _port_open(host: str, port: int) -> bool:
    try:
        s = socket.create_connection((host, port), timeout=1)
        s.close()
        return True
    except (OSError, ConnectionRefusedError):
        return False


@pytest.mark.skipif(not _port_open("localhost", 6333), reason="Qdrant not running on :6333")
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
