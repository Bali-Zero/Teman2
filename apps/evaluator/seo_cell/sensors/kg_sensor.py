"""KG Sensor — snapshot of Knowledge Graph coverage.

The v2.1 memo framed this sensor as per-query coverage. That's the
right contract for the *thinker*, not a *sensor*: sensors are
parallel and stateless, so a KG sensor cannot depend on GSC query
output from the same pulse. We therefore make KGSensor emit a
**global KG snapshot**:

  value.node_count            — total kg_nodes
  value.edge_count            — total kg_edges
  value.nodes_by_type         — {entity_type: count} top 20
  value.edges_by_type         — {relationship_type: count} top 20
  value.last_updated_at       — max(updated_at) across nodes

The thinker in Sprint 3+ then:
  1. reads GSC query strings from the GSC reading
  2. does entity-pattern matching on each query (reusing the regex
     battery from services/knowledge_graph/entity_linker.py)
  3. looks up each candidate in kg_nodes and counts its outgoing
     edges — that's the per-query coverage score

This sensor simply answers: "how big and how fresh is the KG
overall?" — the prerequisite question for any coverage reasoning.

Failure policy (consistent with other sensors):
- DATABASE_URL missing           → yellow, error_code=db_url_missing
- asyncpg ImportError            → red,    error_code=import_error
- connect/query exception        → red,    error_code=db_error
- any other exception            → red,    error_code=unexpected
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from cell_core.types import SensorReading

logger = logging.getLogger("seo_cell.sensors.kg")

_TOP_N_TYPES = 20


class KGSensor:
    name = "kg"

    def __init__(self, db_url: str | None = None) -> None:
        self._db_url_override = db_url

    def _resolve_db_url(self) -> str | None:
        return self._db_url_override or os.environ.get("DATABASE_URL")

    async def read(self, **context) -> SensorReading:
        db_url = self._resolve_db_url()
        if not db_url:
            return self._yellow(
                "db_url_missing",
                "DATABASE_URL not set (and no override)",
            )

        try:
            snapshot = await self._fetch_snapshot(db_url)
        except _KGError as e:
            return self._red(e.code, str(e))
        except Exception as e:  # noqa: BLE001 — sensor must not raise
            logger.exception("[kg] unexpected failure")
            return self._red("unexpected", repr(e))

        node_count = snapshot["node_count"]
        status = "green" if node_count > 0 else "yellow"
        return SensorReading(
            sensor_name=self.name,
            status=status,
            value=snapshot,
            metadata={
                "tables": "kg_nodes, kg_edges",
                "top_n_types": _TOP_N_TYPES,
            },
        )

    # ── internal ──────────────────────────────────────────────────────────

    async def _fetch_snapshot(self, db_url: str) -> dict[str, Any]:
        try:
            import asyncpg
        except ImportError as e:
            raise _KGError("import_error", f"missing dep: {e}") from e

        try:
            conn = await asyncpg.connect(db_url, timeout=10)
        except Exception as e:
            raise _KGError("db_error", f"connect failed: {e!r}") from e

        try:
            node_count = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
            edge_count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")

            nodes_by_type_rows = await conn.fetch(
                """
                SELECT entity_type, COUNT(*) AS n
                FROM kg_nodes
                GROUP BY entity_type
                ORDER BY n DESC
                LIMIT $1
                """,
                _TOP_N_TYPES,
            )
            edges_by_type_rows = await conn.fetch(
                """
                SELECT relationship_type, COUNT(*) AS n
                FROM kg_edges
                GROUP BY relationship_type
                ORDER BY n DESC
                LIMIT $1
                """,
                _TOP_N_TYPES,
            )
            last_updated: datetime | None = await conn.fetchval(
                "SELECT MAX(updated_at) FROM kg_nodes"
            )
        except Exception as e:
            raise _KGError("db_error", f"query failed: {e!r}") from e
        finally:
            await conn.close()

        return {
            "node_count": int(node_count or 0),
            "edge_count": int(edge_count or 0),
            "nodes_by_type": {r["entity_type"]: int(r["n"]) for r in nodes_by_type_rows},
            "edges_by_type": {r["relationship_type"]: int(r["n"]) for r in edges_by_type_rows},
            "last_updated_at": last_updated.isoformat() if last_updated else None,
        }

    def _yellow(self, code: str, msg: str) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={
                "node_count": 0,
                "edge_count": 0,
                "nodes_by_type": {},
                "edges_by_type": {},
                "last_updated_at": None,
            },
            metadata={"error_code": code, "error": msg},
        )

    def _red(self, code: str, msg: str) -> SensorReading:
        logger.warning("[kg] red: %s — %s", code, msg)
        return SensorReading(
            sensor_name=self.name,
            status="red",
            value={
                "node_count": 0,
                "edge_count": 0,
                "nodes_by_type": {},
                "edges_by_type": {},
                "last_updated_at": None,
            },
            metadata={"error_code": code, "error": msg},
        )


class _KGError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
