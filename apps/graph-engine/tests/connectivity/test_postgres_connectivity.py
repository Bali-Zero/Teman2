"""PostgreSQL connectivity test — verifies the KGStore can reach PostgreSQL."""

import pytest

from nuzantara_graph.services.kg_store import KGStore
from tests.connectivity.conftest import POSTGRES_AVAILABLE


@pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL not reachable with test credentials at postgresql://postgres:postgres@localhost:5432/nuzantara_v6",
)
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
