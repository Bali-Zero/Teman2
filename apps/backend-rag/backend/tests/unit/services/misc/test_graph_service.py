"""
Unit tests for GraphService
Target: 100% coverage
Composer: 4
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.graph_service import GraphService, GraphEntity, GraphRelation


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    return pool


@pytest.fixture
def graph_service(mock_db_pool):
    """Create graph service instance"""
    return GraphService(db_pool=mock_db_pool)


class TestGraphService:
    """Tests for GraphService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = GraphService(db_pool=mock_db_pool)
        assert service.pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_add_entity(self, graph_service):
        """Test adding entity"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="entity_123")
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        entity = GraphEntity(
            id="entity_123",
            type="Organization",
            name="PT PMA"
        )
        
        result = await graph_service.add_entity(entity)
        assert result == "entity_123"

    @pytest.mark.asyncio
    async def test_add_relation(self, graph_service):
        """Test adding relation"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="rel_123")
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        relation = GraphRelation(
            source_id="entity1",
            target_id="entity2",
            type="REQUIRES",
            strength=0.9
        )
        
        result = await graph_service.add_relation(relation)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_neighbors(self, graph_service):
        """Test getting neighbors"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"target_id": "entity2", "relationship_type": "REQUIRES", "strength": 0.9}
        ])
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        neighbors = await graph_service.get_neighbors("entity1")
        assert len(neighbors) > 0

    @pytest.mark.asyncio
    async def test_get_neighbors_with_type_filter(self, graph_service):
        """Test getting neighbors with type filter"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        neighbors = await graph_service.get_neighbors("entity1", relation_type="REQUIRES")
        assert isinstance(neighbors, list)


class TestGraphEntity:
    """Tests for GraphEntity model"""

    def test_entity_creation(self):
        """Test entity creation"""
        entity = GraphEntity(
            id="test",
            type="Organization",
            name="Test Company"
        )
        assert entity.id == "test"
        assert entity.type == "Organization"

    def test_entity_with_description(self):
        """Test entity with description"""
        entity = GraphEntity(
            id="test",
            type="Organization",
            name="Test",
            description="Test description"
        )
        assert entity.description == "Test description"


class TestGraphRelation:
    """Tests for GraphRelation model"""

    def test_relation_creation(self):
        """Test relation creation"""
        relation = GraphRelation(
            source_id="entity1",
            target_id="entity2",
            type="REQUIRES"
        )
        assert relation.source_id == "entity1"
        assert relation.target_id == "entity2"
        assert relation.strength == 1.0

    @pytest.mark.asyncio
    async def test_find_entity_by_name(self, graph_service):
        """Test finding entity by name"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "entity_id": "entity_123",
                "entity_type": "Organization",
                "name": "PT PMA",
                "properties": {"description": "Test description"}
            }
        ])
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        entities = await graph_service.find_entity_by_name("PT PMA", limit=5)
        assert len(entities) > 0
        assert entities[0].name == "PT PMA"

    @pytest.mark.asyncio
    async def test_traverse(self, graph_service):
        """Test graph traversal"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        # Mock start node
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "entity1",
            "type": "Organization",
            "name": "PT PMA",
            "properties": {"description": "Test"}
        })
        # Mock neighbors
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "source_entity_id": "entity1",
                "target_entity_id": "entity2",
                "relationship_type": "REQUIRES",
                "properties": {"strength": 0.9},
                "target_type": "IZIN_USAHA",
                "target_name": "Investment",
                "target_desc": "Investment requirement"
            }
        ])
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        subgraph = await graph_service.traverse("entity1", max_depth=2)
        assert "nodes" in subgraph
        assert "edges" in subgraph
        assert len(subgraph["nodes"]) > 0

    @pytest.mark.asyncio
    async def test_traverse_no_start_node(self, graph_service):
        """Test traversal when start node doesn't exist"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)  # Node doesn't exist
        mock_conn.fetch = AsyncMock(return_value=[])
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        subgraph = await graph_service.traverse("nonexistent", max_depth=2)
        assert "nodes" in subgraph
        assert "edges" in subgraph
        assert len(subgraph["nodes"]) == 0

    @pytest.mark.asyncio
    async def test_traverse_max_depth(self, graph_service):
        """Test traversal respects max depth"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "entity1",
            "type": "Organization",
            "name": "PT PMA",
            "properties": {}
        })
        mock_conn.fetch = AsyncMock(return_value=[
            {
                "source_entity_id": "entity1",
                "target_entity_id": "entity2",
                "relationship_type": "REQUIRES",
                "properties": {},
                "target_type": "IZIN_USAHA",
                "target_name": "Investment",
                "target_desc": None
            }
        ])
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        subgraph = await graph_service.traverse("entity1", max_depth=1)
        # Should only include nodes at depth 0 and 1
        assert len(subgraph["nodes"]) <= 2  # Start node + one neighbor

    @pytest.mark.asyncio
    async def test_add_entity_with_description(self, graph_service):
        """Test adding entity with description"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="entity_123")
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        entity = GraphEntity(
            id="entity_123",
            type="Organization",
            name="PT PMA",
            description="Test description"
        )
        
        result = await graph_service.add_entity(entity)
        assert result == "entity_123"

    @pytest.mark.asyncio
    async def test_add_relation_with_properties(self, graph_service):
        """Test adding relation with custom properties"""
        from contextlib import asynccontextmanager
        
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="rel_123")
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        graph_service.pool.acquire = acquire
        
        relation = GraphRelation(
            source_id="entity1",
            target_id="entity2",
            type="REQUIRES",
            strength=0.8,
            properties={"evidence": "document X"}
        )
        
        result = await graph_service.add_relation(relation)
        assert result is not None

