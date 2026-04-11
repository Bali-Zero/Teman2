"""Eigenvector-reverse detector.

Justification
-------------
Memory cite: ``project_osint_layer27_graph_analytics.md``, Centrality
Algorithms section — "PageRank: Chi è DAVVERO importante" and the
general principle that in legitimate power structures high-eigenvector
nodes sit on top of *other* high-eigenvector nodes.

A node with high eigenvector centrality but whose 1-hop neighbors are
all in the bottom quartile is a **compartmentalized hub** — the
classic cut-out / handler / proxy pattern in which a single actor
mediates flows between otherwise-disconnected peripheries. In OSINT
terms: a facilitator who never lets their contacts meet each other.

False positive mitigation
-------------------------
1. ``min_neighbors``: nodes with fewer than N neighbors are skipped
   (a 2-person handler is not interesting; it's just an acquaintance).
2. ``hub_top_percentile``: the hub must itself be in the top decile so
   we're talking about a *real* hub, not a random disconnected pair.
3. Result ranking uses the ratio of low-centrality neighbors to total
   neighbors, so a "3 low out of 4" case scores lower than "all 10 low".
4. We return only node IDs in the alert — the analyst resolves names
   in a separate step.

GDS API version
---------------
Migrated to GDS 2.13+ ``gds.graph.project`` aggregation function
(Cypher projection). The legacy ``gds.graph.project.cypher`` procedure
is deprecated and will be removed. ``undirectedRelationshipTypes`` is
set so the projection matches what Louvain / articulation points /
eigenvector expect.

Data requirements
-----------------
Any graph. No timestamps needed. Runs on a read-only projection.
"""

from __future__ import annotations

from typing import Any

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector, SessionLike
from osint_nexus.anomaly.thresholds import DEFAULT_THRESHOLDS

# Projection graph name — kept constant per detector so repeated runs
# don't spawn dangling projections. The runbook cleans this up.
_PROJECTION_NAME = "anomaly_eigenvector"


class EigenvectorReverseDetector(Detector):
    name = "eigenvector_reverse"

    @classmethod
    def default_thresholds(cls) -> dict[str, Any]:
        return dict(DEFAULT_THRESHOLDS["eigenvector_reverse"])

    # ------------------------------------------------------------------
    # Cypher queries — kept as class constants for easy test matching
    # ------------------------------------------------------------------

    _DROP_Q = f"""
    CALL gds.graph.drop('{_PROJECTION_NAME}', false)
    YIELD graphName
    RETURN graphName
    """

    _PROJECT_Q = f"""
    MATCH (source)
    OPTIONAL MATCH (source)-[r]-(target)
    WITH source, target WHERE target IS NOT NULL
    WITH gds.graph.project(
      '{_PROJECTION_NAME}',
      source,
      target,
      {{}},
      {{undirectedRelationshipTypes: ['*']}}
    ) AS g
    RETURN g.graphName AS graphName,
           g.nodeCount AS nodeCount,
           g.relationshipCount AS relCount
    """

    # GDS stream returns INTEGER ``nodeId`` — we unwrap via
    # ``gds.util.asNode(nodeId)`` to get the modern elementId so the
    # neighbor fetch below can re-match. Without this the neighbor
    # map would be empty and the detector silently returns zero.
    _EIGENVECTOR_Q = f"""
    CALL gds.eigenvector.stream('{_PROJECTION_NAME}',
      {{maxIterations: 100, tolerance: 0.0001}}
    )
    YIELD nodeId, score
    WITH elementId(gds.util.asNode(nodeId)) AS node_id, score
    WITH collect({{id: node_id, score: score}}) AS nodes
    UNWIND range(0, size(nodes) - 1) AS i
    WITH nodes, i, nodes[i] AS n
    WITH n.id AS node_id, n.score AS score,
         1.0 * i / size(nodes) AS rank_fraction
    RETURN node_id, score,
           1.0 - rank_fraction AS percentile
    ORDER BY score DESC
    """

    _NEIGHBORS_Q = """
    UNWIND $hub_ids AS hid
    MATCH (hub) WHERE toString(elementId(hub)) = hid
    OPTIONAL MATCH (hub)-[]-(neighbor)
    WITH hid AS hub_id,
         [n IN collect(DISTINCT neighbor) WHERE n IS NOT NULL
             | toString(elementId(n))] AS neighbor_ids
    RETURN hub_id, neighbor_ids
    """

    _CLEANUP_Q = f"CALL gds.graph.drop('{_PROJECTION_NAME}', false) YIELD graphName"

    # ------------------------------------------------------------------

    def run(self, session: SessionLike) -> list[Alert]:
        if session is None:
            return []

        th = self._thresholds
        hub_top = float(th.get("hub_top_percentile", 0.90))
        neigh_bottom = float(th.get("neighbor_bottom_percentile", 0.25))
        lone_ratio = float(th.get("lone_hub_min_ratio", 0.75))
        min_neighbors = int(th.get("min_neighbors", 4))
        min_score = float(th.get("min_score", 0.6))

        # Drop stale projection, then build fresh (idempotent).
        try:
            session.run(self._DROP_Q)
        except Exception:  # pragma: no cover
            pass
        try:
            session.run(self._PROJECT_Q)
        except Exception:  # pragma: no cover - exercised against live GDS
            pass

        # Step 2 — pull eigenvector stream with per-node percentiles
        eigen_records = list(session.run(self._EIGENVECTOR_Q))
        if not eigen_records:
            self._safe_drop(session)
            return []

        # Index: id -> percentile, id -> score
        score_by_id: dict[str, float] = {}
        percentile_by_id: dict[str, float] = {}
        for rec in eigen_records:
            nid = str(rec["node_id"])
            score_by_id[nid] = float(rec["score"])
            percentile_by_id[nid] = float(rec["percentile"])

        hub_ids = [
            nid for nid, p in percentile_by_id.items() if p >= hub_top
        ]
        if not hub_ids:
            self._safe_drop(session)
            return []

        # Step 3 — fetch 1-hop neighborhoods for hubs
        neighbor_map: dict[str, list[str]] = {}
        for rec in session.run(self._NEIGHBORS_Q, {"hub_ids": hub_ids}):
            neighbor_map[str(rec["hub_id"])] = [
                str(n) for n in rec.get("neighbor_ids", []) if n
            ]

        alerts: list[Alert] = []
        for hid in hub_ids:
            neighbors = neighbor_map.get(hid, [])
            if len(neighbors) < min_neighbors:
                continue

            low_count = sum(
                1
                for n in neighbors
                if percentile_by_id.get(n, 0.5) <= neigh_bottom
            )
            ratio = low_count / len(neighbors)
            if ratio < lone_ratio:
                continue

            # Score: combine hub percentile and lone-ratio. Both are
            # in [0, 1]; geometric mean punishes either-low cases.
            hub_p = percentile_by_id[hid]
            score = (hub_p * ratio) ** 0.5
            # Confidence reflects data density — more neighbors = more
            # trustworthy ratio signal.
            confidence = min(1.0, len(neighbors) / 10.0)

            if score < min_score:
                continue

            alerts.append(
                self._mk_alert(
                    primary_entity_id=hid,
                    score=score,
                    confidence=confidence,
                    evidence_path=[hid, *neighbors],
                    rationale_id="ER-LONE-HUB",
                )
            )

        self._safe_drop(session)
        return alerts

    @staticmethod
    def _safe_drop(session: SessionLike) -> None:
        try:
            session.run(EigenvectorReverseDetector._CLEANUP_Q)
        except Exception:  # pragma: no cover
            pass
