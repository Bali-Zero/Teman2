"""
Graph Service - Persistent Knowledge Graph using PostgreSQL
===========================================================

Provides CRUD operations and traversal logic for the Knowledge Graph
stored in 'kg_nodes' and 'kg_edges' tables.

Updated Dec 2025 to use unified KG schema (kg_nodes/kg_edges).
"""

import json
import logging
from typing import Any

import asyncpg
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GraphEntity(BaseModel):
    id: str
    type: str
    name: str
    description: str | None = None
    properties: dict[str, Any] = {}


class GraphRelation(BaseModel):
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = {}
    strength: float = 1.0


class GraphService:
    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def add_entity(self, entity: GraphEntity) -> str:
        """Upsert an entity into the graph (kg_nodes table)."""
        # Merge description into properties if provided
        props = entity.properties.copy()
        if entity.description:
            props["description"] = entity.description

        query = """
            INSERT INTO kg_nodes (entity_id, entity_type, name, properties, confidence, source_chunk_ids, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 1.0, ARRAY[]::TEXT[], NOW(), NOW())
            ON CONFLICT (entity_id) DO UPDATE SET
                name = EXCLUDED.name,
                properties = kg_nodes.properties || EXCLUDED.properties,
                updated_at = NOW()
            RETURNING entity_id
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                query,
                entity.id,
                entity.type,
                entity.name,
                json.dumps(props),
            )

    async def add_relation(self, relation: GraphRelation) -> str:
        """Upsert a relationship edge (kg_edges table)."""
        # Store strength in properties for compatibility
        props = relation.properties.copy()
        props["strength"] = relation.strength

        # Generate relationship_id (TEXT PK) from source, type, target
        relationship_id = f"{relation.source_id}__{relation.type.lower().replace(' ', '_')}__{relation.target_id}"

        query = """
            INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id, relationship_type, properties, source_chunk_ids, created_at)
            VALUES ($1, $2, $3, $4, $5, ARRAY[]::TEXT[], NOW())
            ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO UPDATE SET
                properties = kg_edges.properties || EXCLUDED.properties
            RETURNING relationship_id
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                query,
                relationship_id,
                relation.source_id,
                relation.target_id,
                relation.type,
                json.dumps(props),
            )

    async def get_neighbors(
        self, entity_id: str, relation_type: str | None = None
    ) -> list[dict]:
        """Get outgoing edges and target entities for a node (kg_edges + kg_nodes)."""
        query = """
            SELECT
                r.relationship_type,
                COALESCE((r.properties->>'strength')::float, 1.0) as strength,
                e.entity_id as target_id,
                e.name as target_name,
                e.entity_type as target_type,
                e.properties->>'description' as description
            FROM kg_edges r
            JOIN kg_nodes e ON r.target_entity_id = e.entity_id
            WHERE r.source_entity_id = $1
        """
        params = [entity_id]
        if relation_type:
            query += " AND r.relationship_type = $2"
            params.append(relation_type)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def find_entity_by_name(self, name_query: str, limit: int = 5) -> list[GraphEntity]:
        """Fuzzy search for entities by name (kg_nodes table)."""
        query = """
            SELECT entity_id, entity_type, name, properties
            FROM kg_nodes
            WHERE name ILIKE $1
            LIMIT $2
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, f"%{name_query}%", limit)
            return [
                GraphEntity(
                    id=row["entity_id"],
                    type=row["entity_type"],
                    name=row["name"],
                    description=row["properties"].get("description") if row["properties"] else None,
                    properties=row["properties"] if row["properties"] else {},
                )
                for row in rows
            ]

    async def traverse(self, start_id: str, max_depth: int = 2) -> dict[str, Any]:
        """
        BFS Traversal from a starting node (kg_nodes + kg_edges).
        Returns a subgraph (nodes and edges).
        """
        nodes = {}
        edges = []
        queue = [(start_id, 0)]
        visited = set()

        async with self.pool.acquire() as conn:
            # Get start node from kg_nodes
            start_node = await conn.fetchrow(
                """SELECT entity_id as id, entity_type as type, name, properties
                   FROM kg_nodes WHERE entity_id = $1""",
                start_id,
            )
            if start_node:
                node_dict = dict(start_node)
                # Extract description from properties for compatibility
                if node_dict.get("properties"):
                    node_dict["description"] = node_dict["properties"].get("description")
                nodes[start_id] = node_dict
                visited.add(start_id)

            while queue:
                current_id, depth = queue.pop(0)
                if depth >= max_depth:
                    continue

                # Fetch outgoing edges from kg_edges joined with kg_nodes
                rows = await conn.fetch(
                    """
                    SELECT r.*, e.entity_type as target_type, e.name as target_name,
                           e.properties->>'description' as target_desc
                    FROM kg_edges r
                    JOIN kg_nodes e ON r.target_entity_id = e.entity_id
                    WHERE r.source_entity_id = $1
                """,
                    current_id,
                )

                for row in rows:
                    target_id = row["target_entity_id"]

                    edge = {
                        "source": current_id,
                        "target": target_id,
                        "type": row["relationship_type"],
                        "strength": row["properties"].get("strength", 1.0) if row["properties"] else 1.0,
                    }
                    edges.append(edge)

                    if target_id not in visited:
                        visited.add(target_id)
                        nodes[target_id] = {
                            "id": target_id,
                            "type": row["target_type"],
                            "name": row["target_name"],
                            "description": row["target_desc"],
                        }
                        queue.append((target_id, depth + 1))

        return {"nodes": list(nodes.values()), "edges": edges}
