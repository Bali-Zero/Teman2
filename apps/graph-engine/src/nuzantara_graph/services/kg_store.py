"""Knowledge Graph store — PostgreSQL KG queries via asyncpg.

Queries the kg_nodes and kg_edges tables (schema inherited from V5).
All endpoints read from Settings (no hardcoded URLs).
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from nuzantara_graph.config import Settings

logger = structlog.get_logger()


class KGStore:
    """PostgreSQL Knowledge Graph query interface.

    Tables (V5 schema, read-only from V6):
      - kg_nodes(entity_id, entity_type, label, description, properties JSONB)
      - kg_edges(source_id, target_id, relationship_type, properties JSONB)

    Usage:
        store = KGStore.from_settings(settings)
        entities = await store.get_entities(entity_ids=["kbli:56101"])
        rels = await store.get_relationships(entity_id="kbli:56101")
    """

    def __init__(self, database_url: str = "") -> None:
        self.database_url = database_url
        self._pool: asyncpg.Pool | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> KGStore:
        return cls(database_url=settings.database_url)

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
        return self._pool

    async def get_entities(
        self,
        entity_ids: list[str] | None = None,
        entity_type: str | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieve KG entities by ID, type, or text search."""
        pool = await self._get_pool()

        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if entity_ids:
            conditions.append(f"entity_id = ANY(${idx}::text[])")
            params.append(entity_ids)
            idx += 1

        if entity_type:
            conditions.append(f"entity_type = ${idx}")
            params.append(entity_type)
            idx += 1

        if query:
            conditions.append(
                f"(label ILIKE ${idx} OR description ILIKE ${idx})"
            )
            params.append(f"%{query}%")
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT entity_id, entity_type, label, description, properties
            FROM kg_nodes
            {where}
            LIMIT ${idx}
        """
        params.append(limit)

        rows = await pool.fetch(sql, *params)
        return [_row_to_dict(row) for row in rows]

    async def get_relationships(
        self,
        entity_id: str,
        relationship_type: str | None = None,
        depth: int = 1,
    ) -> list[dict[str, Any]]:
        """Traverse KG relationships from an entity.

        For depth=1, returns direct relationships.
        For depth>1, uses recursive CTE for multi-hop traversal.
        """
        pool = await self._get_pool()

        if depth <= 1:
            return await self._get_direct_relationships(
                pool, entity_id, relationship_type
            )

        return await self._get_recursive_relationships(
            pool, entity_id, relationship_type, depth
        )

    async def _get_direct_relationships(
        self,
        pool: asyncpg.Pool,
        entity_id: str,
        relationship_type: str | None,
    ) -> list[dict[str, Any]]:
        conditions = ["(source_id = $1 OR target_id = $1)"]
        params: list[Any] = [entity_id]

        if relationship_type:
            conditions.append("relationship_type = $2")
            params.append(relationship_type)

        where = " AND ".join(conditions)

        sql = f"""
            SELECT e.source_id, e.target_id, e.relationship_type, e.properties,
                   n.label as target_label, n.entity_type as target_type
            FROM kg_edges e
            LEFT JOIN kg_nodes n ON (
                CASE WHEN e.source_id = $1 THEN e.target_id ELSE e.source_id END
            ) = n.entity_id
            WHERE {where}
            LIMIT 50
        """

        rows = await pool.fetch(sql, *params)
        return [_row_to_dict(row) for row in rows]

    async def _get_recursive_relationships(
        self,
        pool: asyncpg.Pool,
        entity_id: str,
        relationship_type: str | None,
        max_depth: int,
    ) -> list[dict[str, Any]]:
        type_filter = ""
        params: list[Any] = [entity_id, max_depth]
        if relationship_type:
            type_filter = "AND e.relationship_type = $3"
            params.append(relationship_type)

        sql = f"""
            WITH RECURSIVE traversal AS (
                SELECT e.source_id, e.target_id, e.relationship_type, e.properties,
                       1 as depth
                FROM kg_edges e
                WHERE (e.source_id = $1 OR e.target_id = $1) {type_filter}

                UNION ALL

                SELECT e.source_id, e.target_id, e.relationship_type, e.properties,
                       t.depth + 1
                FROM kg_edges e
                JOIN traversal t ON (
                    e.source_id = t.target_id OR e.target_id = t.source_id
                )
                WHERE t.depth < $2 {type_filter}
            )
            SELECT DISTINCT source_id, target_id, relationship_type, properties, depth
            FROM traversal
            ORDER BY depth
            LIMIT 100
        """

        rows = await pool.fetch(sql, *params)
        return [_row_to_dict(row) for row in rows]

    async def search_entities(
        self,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Full-text search over KG entities using PostgreSQL ILIKE."""
        pool = await self._get_pool()

        conditions = ["(label ILIKE $1 OR description ILIKE $1)"]
        params: list[Any] = [f"%{query}%"]
        idx = 2

        if entity_types:
            conditions.append(f"entity_type = ANY(${idx}::text[])")
            params.append(entity_types)
            idx += 1

        where = " AND ".join(conditions)

        sql = f"""
            SELECT entity_id, entity_type, label, description, properties
            FROM kg_nodes
            WHERE {where}
            ORDER BY
                CASE WHEN label ILIKE $1 THEN 0 ELSE 1 END,
                label
            LIMIT ${idx}
        """
        params.append(limit)

        rows = await pool.fetch(sql, *params)
        return [_row_to_dict(row) for row in rows]

    async def health_check(self) -> dict[str, Any]:
        """Verify PostgreSQL is reachable and KG tables exist."""
        try:
            pool = await self._get_pool()
            row = await pool.fetchrow(
                """
                SELECT
                    (SELECT count(*) FROM information_schema.tables
                     WHERE table_name IN ('kg_nodes', 'kg_edges')) as kg_tables,
                    (SELECT count(*) FROM kg_nodes) as node_count,
                    (SELECT count(*) FROM kg_edges) as edge_count
                """
            )
            return {
                "status": "healthy",
                "kg_tables": row["kg_tables"],
                "node_count": row["node_count"],
                "edge_count": row["edge_count"],
                "ok": row["kg_tables"] == 2,
            }
        except asyncpg.UndefinedTableError:
            return {
                "status": "healthy",
                "kg_tables": 0,
                "node_count": 0,
                "edge_count": 0,
                "note": "KG tables not yet created",
                "ok": True,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "ok": False,
            }

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a plain dict, handling JSONB."""
    result = dict(row)
    # asyncpg returns JSONB as already-parsed Python dicts
    return result
