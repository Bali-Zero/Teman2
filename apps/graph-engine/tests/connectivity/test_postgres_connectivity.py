"""PostgreSQL connectivity test — verifies the KGStore can reach PostgreSQL."""

import socket

import pytest

from nuzantara_graph.services.kg_store import KGStore


def _port_open(host: str, port: int) -> bool:
    try:
        s = socket.create_connection((host, port), timeout=1)
        s.close()
        return True
    except (OSError, ConnectionRefusedError):
        return False


@pytest.mark.skipif(not _port_open("localhost", 5432), reason="PostgreSQL not running on :5432")
class TestPostgresConnectivity:

    @pytest.mark.asyncio
    async def test_health_check(self, local_settings):
        store = KGStore.from_settings(local_settings)
        try:
            result = await store.health_check()
            assert result["status"] in ("healthy", "unhealthy")
            assert result.get("ok") is True or "not yet created" in result.get("note", "")
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_raw_query(self, local_settings):
        store = KGStore.from_settings(local_settings)
        try:
            pool = await store._get_pool()
            row = await pool.fetchrow("SELECT version() as pg_version")
            assert "PostgreSQL" in row["pg_version"]
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_public_tables(self, local_settings):
        """Verify we can list public tables."""
        store = KGStore.from_settings(local_settings)
        try:
            pool = await store._get_pool()
            tables = await pool.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
            table_names = [r["table_name"] for r in tables]
            assert isinstance(table_names, list)
        finally:
            await store.close()
