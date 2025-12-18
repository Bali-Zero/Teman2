"""
Graph Service - Persistent Knowledge Graph using PostgreSQL
===========================================================

Provides CRUD operations and traversal logic for the Knowledge Graph
stored in 'kg_entities' and 'kg_relationships' tables.

Replaces the in-memory storage of KnowledgeGraphBuilder.
"""

import json
import logging
from typing import Any, List, Optional, Dict

import asyncpg
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class GraphEntity(BaseModel):
    id: str
    type: str
    name: str
    description: Optional[str] = None
    properties: Dict[str, Any] = {}

class GraphRelation(BaseModel):
    source_id: str
    target_id: str
    type: str
    properties: Dict[str, Any] = {}
    strength: float = 1.0

class GraphService:
    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def add_entity(self, entity: GraphEntity) -> str:
        """Upsert an entity into the graph."""
        query = """
            INSERT INTO kg_entities (id, type, name, description, properties, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = COALESCE(EXCLUDED.description, kg_entities.description),
                properties = kg_entities.properties || EXCLUDED.properties,
                updated_at = NOW()
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                query, 
                entity.id, 
                entity.type, 
                entity.name, 
                entity.description, 
                json.dumps(entity.properties)
            )

    async def add_relation(self, relation: GraphRelation) -> int:
        """Upsert a relationship edge."""
        query = """
            INSERT INTO kg_relationships (source_entity_id, target_entity_id, relationship_type, strength, properties, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO UPDATE SET
                strength = EXCLUDED.strength,
                properties = kg_relationships.properties || EXCLUDED.properties
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                query,
                relation.source_id,
                relation.target_id,
                relation.type,
                relation.strength,
                json.dumps(relation.properties)
            )

    async def get_neighbors(self, entity_id: str, relation_type: Optional[str] = None) -> List[Dict]:
        """Get outgoing edges and target entities for a node."""
        query = """
            SELECT 
                r.relationship_type, 
                r.strength,
                e.id as target_id,
                e.name as target_name,
                e.type as target_type,
                e.description
            FROM kg_relationships r
            JOIN kg_entities e ON r.target_entity_id = e.id
            WHERE r.source_entity_id = $1
        """
        params = [entity_id]
        if relation_type:
            query += " AND r.relationship_type = $2"
            params.append(relation_type)
            
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def find_entity_by_name(self, name_query: str, limit: int = 5) -> List[GraphEntity]:
        """Fuzzy search for entities by name."""
        query = """
            SELECT id, type, name, description, properties
            FROM kg_entities
            WHERE name ILIKE $1
            LIMIT $2
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, f"%{name_query}%", limit)
            return [
                GraphEntity(
                    id=row['id'], 
                    type=row['type'], 
                    name=row['name'], 
                    description=row['description'],
                    properties=json.loads(row['properties']) if isinstance(row['properties'], str) else row['properties']
                ) for row in rows
            ]

    async def traverse(self, start_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """
        BFS Traversal from a starting node.
        Returns a subgraph (nodes and edges).
        """
        nodes = {}
        edges = []
        queue = [(start_id, 0)]
        visited = set()

        async with self.pool.acquire() as conn:
            # Get start node
            start_node = await conn.fetchrow("SELECT * FROM kg_entities WHERE id = $1", start_id)
            if start_node:
                nodes[start_id] = dict(start_node)
                visited.add(start_id)

            while queue:
                current_id, depth = queue.pop(0)
                if depth >= max_depth:
                    continue

                # Fetch outgoing edges
                rows = await conn.fetch("""
                    SELECT r.*, e.type as target_type, e.name as target_name, e.description as target_desc
                    FROM kg_relationships r
                    JOIN kg_entities e ON r.target_entity_id = e.id
                    WHERE r.source_entity_id = $1
                """, current_id)

                for row in rows:
                    target_id = row['target_entity_id']
                    
                    edge = {
                        "source": current_id,
                        "target": target_id,
                        "type": row['relationship_type'],
                        "strength": row['strength']
                    }
                    edges.append(edge)

                    if target_id not in visited:
                        visited.add(target_id)
                        nodes[target_id] = {
                            "id": target_id,
                            "type": row['target_type'],
                            "name": row['target_name'],
                            "description": row['target_desc']
                        }
                        queue.append((target_id, depth + 1))

        return {"nodes": list(nodes.values()), "edges": edges}
