"""Detector 1: Centrality Jump — nodes with sudden edge-mass increase.

JUSTIFICATION (project_osint_layer27_graph_analytics.md):
    Layer 27 specifies betweenness and PageRank as primary centrality
    measures for detecting "broker di potere nascosto" (hidden power
    brokers). A sudden jump in centrality indicates a node that has
    rapidly acquired new connections — potentially a newly appointed
    patron consolidating power (Layer 9: bapakisme pattern).

PROXY DECISION:
    No temporal graph snapshots exist. Instead, we use edge creation
    timestamps (created_at / updated_at) as a structural proxy.
    A node where a disproportionate fraction of edges were created
    in the last N days (default: 30) signals a centrality jump.
    This captures the same underlying signal: rapid importance growth.

FALSE-POSITIVE MITIGATION:
    - min_degree filter: ignores low-degree nodes (noise from data entry)
    - min_recent_edges: requires at least 3 recent edges (not just 1 of 2)
    - Confidence scaled by total degree: higher-degree nodes get higher
      confidence because the signal is more statistically significant
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector


class CentralityJumpDetector(Detector):
    """Detect nodes with disproportionately many recently-created edges."""

    pattern_name = "centrality_jump"

    async def run(self, session: AsyncSession) -> list[Alert]:
        """Scan for nodes whose recent edge fraction exceeds threshold.

        False-positive mitigation:
        - min_degree filter prevents noise from sparse nodes
        - min_recent_edges requires absolute minimum of new connections
        - Confidence is scaled by degree (more edges = more reliable signal)
        """
        window_days: int = self._t("window_days", 30)
        fraction_threshold: float = self._t("recent_edge_fraction_threshold", 0.40)
        min_degree: int = self._t("min_degree", 5)
        min_recent_edges: int = self._t("min_recent_edges", 3)

        # Count total edges and recent edges per node.
        # Uses relationship property `updated_at` or `created_at` or `date`
        # as the temporal marker.
        query = """
        MATCH (n)-[r]-()
        WHERE n:Official OR n:Person
        WITH n,
             count(r) AS total_degree,
             sum(CASE
                 WHEN coalesce(r.updated_at, r.created_at, r.date, '') <> ''
                  AND date(coalesce(r.updated_at, r.created_at, r.date))
                      >= date() - duration({days: $window_days})
                 THEN 1 ELSE 0
             END) AS recent_edges
        WHERE total_degree >= $min_degree
          AND recent_edges >= $min_recent_edges
        WITH n, total_degree, recent_edges,
             toFloat(recent_edges) / total_degree AS recent_fraction
        WHERE recent_fraction >= $fraction_threshold
        RETURN elementId(n) AS node_id,
               labels(n) AS node_labels,
               total_degree,
               recent_edges,
               recent_fraction
        ORDER BY recent_fraction DESC
        LIMIT 50
        """
        result = await session.run(
            query,
            {
                "window_days": window_days,
                "min_degree": min_degree,
                "min_recent_edges": min_recent_edges,
                "fraction_threshold": fraction_threshold,
            },
        )

        alerts: list[Alert] = []
        async for record in result:
            node_id = record["node_id"]
            total = record["total_degree"]
            recent = record["recent_edges"]
            fraction = record["recent_fraction"]

            # Confidence: higher degree = more reliable signal
            confidence = min(1.0, total / 20.0)

            alerts.append(
                Alert(
                    pattern=self.pattern_name,
                    score=fraction,
                    evidence_path=[f"node:{node_id}"],
                    explanation_id_only=(
                        f"Node {node_id} has {recent}/{total} edges "
                        f"({fraction:.0%}) created in last {window_days}d"
                    ),
                    confidence=confidence,
                    meta={
                        "total_degree": total,
                        "recent_edges": recent,
                        "recent_fraction": round(fraction, 4),
                        "window_days": window_days,
                    },
                )
            )

        return alerts
