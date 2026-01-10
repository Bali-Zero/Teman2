"""
Unit tests for agents/services/kg_schema.py
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.agents.services.kg_schema import KnowledgeGraphSchema


class TestKnowledgeGraphSchema:
    """Tests for KnowledgeGraphSchema"""

    @pytest.fixture
    def mock_pool(self):
        """Create mock database pool"""
        pool = MagicMock()
        return pool

    @pytest.fixture
    def kg_schema(self, mock_pool):
        """Create KnowledgeGraphSchema instance"""
        return KnowledgeGraphSchema(mock_pool)

    def test_init(self, mock_pool):
        """Test initialization"""
        schema = KnowledgeGraphSchema(mock_pool)
        assert schema.db_pool == mock_pool

    @pytest.mark.asyncio
    async def test_init_schema_both_tables_exist(self, kg_schema, mock_pool):
        """Test init_schema when both tables exist"""
        mock_conn = AsyncMock()
        # First call: kg_nodes exists, Second call: kg_edges exists
        # Third call: nodes count, Fourth call: edges count
        mock_conn.fetchval = AsyncMock(side_effect=[True, True, 1000, 2000])

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        await kg_schema.init_schema()

        assert mock_conn.fetchval.call_count == 4

    @pytest.mark.asyncio
    async def test_init_schema_kg_nodes_missing(self, kg_schema, mock_pool):
        """Test init_schema when kg_nodes table is missing"""
        mock_conn = AsyncMock()
        # kg_nodes doesn't exist, kg_edges exists
        mock_conn.fetchval = AsyncMock(side_effect=[False, True])

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        await kg_schema.init_schema()

        assert mock_conn.fetchval.call_count == 2

    @pytest.mark.asyncio
    async def test_init_schema_kg_edges_missing(self, kg_schema, mock_pool):
        """Test init_schema when kg_edges table is missing"""
        mock_conn = AsyncMock()
        # kg_nodes exists, kg_edges doesn't exist
        mock_conn.fetchval = AsyncMock(side_effect=[True, False])

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        await kg_schema.init_schema()

        assert mock_conn.fetchval.call_count == 2

    @pytest.mark.asyncio
    async def test_init_schema_both_tables_missing(self, kg_schema, mock_pool):
        """Test init_schema when both tables are missing"""
        mock_conn = AsyncMock()
        # Neither table exists
        mock_conn.fetchval = AsyncMock(side_effect=[False, False])

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        await kg_schema.init_schema()

        assert mock_conn.fetchval.call_count == 2

    @pytest.mark.asyncio
    async def test_init_schema_postgres_error(self, kg_schema, mock_pool):
        """Test init_schema with PostgresError"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=asyncpg.PostgresError("Connection failed"))

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(asyncpg.PostgresError):
            await kg_schema.init_schema()

    @pytest.mark.asyncio
    async def test_init_schema_unexpected_error(self, kg_schema, mock_pool):
        """Test init_schema with unexpected error"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=Exception("Unexpected error"))

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(Exception, match="Unexpected error"):
            await kg_schema.init_schema()

    @pytest.mark.asyncio
    async def test_init_schema_logs_counts(self, kg_schema, mock_pool):
        """Test init_schema logs correct counts"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[True, True, 5000, 10000])

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.agents.services.kg_schema.logger") as mock_logger:
            await kg_schema.init_schema()

            # Verify info was logged with counts
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "5,000 nodes" in call_args
            assert "10,000 edges" in call_args
