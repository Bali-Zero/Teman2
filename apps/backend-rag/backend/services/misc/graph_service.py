"""
Graph Service - Persistent Knowledge Graph using PostgreSQL
===========================================================

Provides CRUD operations and traversal logic for the Knowledge Graph
stored in 'kg_nodes' and 'kg_edges' tables.

Updated Dec 2025 to use unified KG schema (kg_nodes/kg_edges).
"""

import json
import logging
from collections import deque
from collections.abc import Mapping
from typing import Any

import asyncpg
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GraphEntity(BaseModel):
    id: str
    type: str
    name: str
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphRelation(BaseModel):
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    strength: float = 1.0


class GraphService:
    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.pool: asyncpg.Pool = db_pool

    @staticmethod
    def _merge_description(
        properties: Mapping[str, Any], description: str | None,
    ) -> dict[str, Any]:
        merged = dict(properties)
        if description:
            merged["description"] = description
        return merged

    @staticmethod
    def _extract_description(properties: Mapping[str, Any] | None) -> str | None:
        if not properties:
            return None
        return properties.get("description")

    @staticmethod
    def _build_relationship_id(source_id: str, relation_type: str, target_id: str) -> str:
        normalized_type = relation_type.lower().replace(" ", "_")
        return f"{source_id}__{normalized_type}__{target_id}"

    async def add_entity(self, entity: GraphEntity) -> str:
        """Upsert an entity into the graph (kg_nodes table)."""
        # Merge description into properties if provided
        props = self._merge_description(entity.properties, entity.description)

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
        relationship_id = self._build_relationship_id(
            relation.source_id, relation.type, relation.target_id,
        )

        query = """
            INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id, relationship_type, properties, source_chunk_ids, created_at)
            VALUES ($1, $2, $3, $4, $5, ARRAY[]::TEXT[], NOW())
            ON CONFLICT (relationship_id) DO UPDATE SET
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
        self, entity_id: str, relation_type: str | None = None, limit: int | None = None,
    ) -> list[dict[str, Any]]:
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
        params: list[Any] = [entity_id]
        if relation_type:
            params.append(relation_type)
            query += f" AND r.relationship_type = ${len(params)}"
        if limit is not None:
            params.append(limit)
            query += f" LIMIT ${len(params)}"

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
                    description=self._extract_description(row["properties"]),
                    properties=row["properties"] if row["properties"] else {},
                )
                for row in rows
            ]

    async def traverse(
        self, start_id: str, max_depth: int = 2, max_edges_per_node: int | None = None,
    ) -> dict[str, Any]:
        """
        BFS Traversal from a starting node (kg_nodes + kg_edges).
        Returns a subgraph (nodes and edges).
        """
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])
        visited: set[str] = set()

        async with self.pool.acquire() as conn:
            # Get start node from kg_nodes
            start_node = await conn.fetchrow(
                """
                SELECT entity_id as id, entity_type as type, name,
                       properties->>'description' as description
                FROM kg_nodes
                WHERE entity_id = $1
                """,
                start_id,
            )
            if start_node:
                nodes[start_id] = dict(start_node)
                visited.add(start_id)

            while queue:
                current_id, depth = queue.popleft()
                if depth >= max_depth:
                    continue

                # Fetch outgoing edges from kg_edges joined with kg_nodes
                query = """
                    SELECT
                        r.relationship_type,
                        r.target_entity_id,
                        COALESCE((r.properties->>'strength')::float, 1.0) as strength,
                        e.entity_type as target_type,
                        e.name as target_name,
                        e.properties->>'description' as target_desc
                    FROM kg_edges r
                    JOIN kg_nodes e ON r.target_entity_id = e.entity_id
                    WHERE r.source_entity_id = $1
                """
                params: list[Any] = [current_id]
                if max_edges_per_node is not None:
                    params.append(max_edges_per_node)
                    query += f" LIMIT ${len(params)}"

                rows = await conn.fetch(query, *params)

                for row in rows:
                    target_id = row["target_entity_id"]

                    edge = {
                        "source": current_id,
                        "target": target_id,
                        "type": row["relationship_type"],
                        "strength": row["strength"],
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
