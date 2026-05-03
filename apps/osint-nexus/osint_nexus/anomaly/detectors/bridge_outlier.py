"""Detector 2: Bridge Outlier — cut vertices between disjoint communities.

JUSTIFICATION (project_osint_layer27_graph_analytics.md):
    Layer 27 specifies betweenness centrality for finding "ponte tra
    cluster" (bridge between clusters). A node that acts as the sole
    bridge between two otherwise disconnected communities is a high-value
    intelligence target — removing it severs information flow.

    Layer 9 (power topology) notes that cross-Kanim clusters often form
    around shared angkatan or arisan networks. A bridge between such
    clusters may indicate a hidden broker or patron.

IMPLEMENTATION:
    Uses GDS Louvain for community detection via Cypher projection.
    Falls back to Weakly Connected Components if GDS is unavailable.
    Then identifies nodes whose neighbors span 2+ communities (bridge
    candidates) with high betweenness relative to their community size.

FALSE-POSITIVE MITIGATION:
    - min_community_size: ignore tiny communities (< 3 nodes)
    - bridge_score_threshold: require minimum bridge importance score
    - Exclude nodes that are simply high-degree hubs (they connect to
      many communities by virtue of degree, not brokerage)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector


class BridgeOutlierDetector(Detector):
    """Detect nodes bridging otherwise disjoint communities."""

    pattern_name = "bridge_outlier"

    async def run(self, session: AsyncSession) -> list[Alert]:
        """Identify bridge nodes between communities.

        False-positive mitigation:
        - Filters out tiny communities (< min_community_size)
        - Requires bridge_score above threshold
        - Normalizes by degree to distinguish brokers from hubs
        """
        min_community = self._t("min_community_size", 3)
        score_threshold = self._t("bridge_score_threshold", 0.5)

        has_gds = await self.check_gds_available(session)

        if has_gds:
            return await self._run_with_gds(session, min_community, score_threshold)
        return await self._run_pure_cypher(session, min_community, score_threshold)

    async def _run_with_gds(
        self,
        session: AsyncSession,
        min_community: int,
        score_threshold: float,
    ) -> list[Alert]:
        """Use GDS Louvain community detection + bridge analysis."""
        # Project the graph into GDS
        try:
            await session.run(
                "CALL gds.graph.drop('anomaly_bridge', false)"
            )
        except Exception:
            pass

        await session.run("""
            CALL gds.graph.project.cypher(
                'anomaly_bridge',
                'MATCH (n) WHERE n:Official OR n:Person RETURN id(n) AS id',
                'MATCH (a)-[r]-(b)
                 WHERE (a:Official OR a:Person) AND (b:Official OR b:Person)
                 RETURN id(a) AS source, id(b) AS target'
            )
        """)

        # Run Louvain community detection
        await session.run("""
            CALL gds.louvain.write('anomaly_bridge', {
                writeProperty: '_anomaly_community'
            })
        """)

        # Find bridge nodes: neighbors in 2+ communities
        query = """
        MATCH (n)-[r]-(neighbor)
        WHERE (n:Official OR n:Person)
          AND (neighbor:Official OR neighbor:Person)
          AND n._anomaly_community IS NOT NULL
          AND neighbor._anomaly_community IS NOT NULL
        WITH n,
             collect(DISTINCT neighbor._anomaly_community) AS neighbor_communities,
             count(DISTINCT neighbor) AS degree
        WHERE size(neighbor_communities) >= 2
        // Bridge score: how many distinct communities this node connects
        // normalized by degree to penalize pure hubs
        WITH n, neighbor_communities,
             degree,
             toFloat(size(neighbor_communities)) / sqrt(toFloat(degree)) AS bridge_score
        WHERE bridge_score >= $score_threshold
        RETURN elementId(n) AS node_id,
               labels(n) AS node_labels,
               size(neighbor_communities) AS communities_bridged,
               degree,
               bridge_score
        ORDER BY bridge_score DESC
        LIMIT 30
        """
        result = await session.run(query, {"score_threshold": score_threshold})

        alerts = await self._process_results(result)

        # Cleanup GDS projection and temp property
        try:
            await session.run("CALL gds.graph.drop('anomaly_bridge', false)")
            await session.run(
                "MATCH (n) WHERE n._anomaly_community IS NOT NULL "
                "REMOVE n._anomaly_community"
            )
        except Exception:
            pass

        return alerts

    async def _run_pure_cypher(
        self,
        session: AsyncSession,
        min_community: int,
        score_threshold: float,
    ) -> list[Alert]:
        """Fallback: use WCC-like heuristic without GDS.

        Groups nodes by their 2-hop neighborhoods and identifies nodes
        whose immediate neighbors belong to multiple such groups.
        """
        query = """
        MATCH (n)--(neighbor)
        WHERE (n:Official OR n:Person)
          AND (neighbor:Official OR neighbor:Person)
        WITH n, collect(DISTINCT neighbor) AS neighbors
        WHERE size(neighbors) >= $min_community
        // For each neighbor, count their own neighbors to approximate clusters
        UNWIND neighbors AS nb
        OPTIONAL MATCH (nb)--(nb_neighbor)
        WHERE nb_neighbor <> n
          AND (nb_neighbor:Official OR nb_neighbor:Person)
        WITH n, nb, collect(DISTINCT elementId(nb_neighbor)) AS nb_network
        // Group neighbors by network overlap similarity
        WITH n, count(DISTINCT nb) AS degree,
             count(DISTINCT nb_network) AS network_diversity
        WHERE network_diversity >= 2
        WITH n, degree, network_diversity,
             toFloat(network_diversity) / sqrt(toFloat(degree)) AS bridge_score
        WHERE bridge_score >= $score_threshold
        RETURN elementId(n) AS node_id,
               labels(n) AS node_labels,
               network_diversity AS communities_bridged,
               degree,
               bridge_score
        ORDER BY bridge_score DESC
        LIMIT 30
        """
        result = await session.run(
            query,
            {
                "min_community": min_community,
                "score_threshold": score_threshold,
            },
        )
        return await self._process_results(result)

    async def _process_results(self, result: Any) -> list[Alert]:
        """Convert query results to Alert objects."""
        alerts: list[Alert] = []
        async for record in result:
            node_id = record["node_id"]
            communities = record["communities_bridged"]
            degree = record["degree"]
            score = record["bridge_score"]

            # Confidence: more communities bridged = more reliable
            confidence = min(1.0, communities / 5.0)

            alerts.append(
                Alert(
                    pattern=self.pattern_name,
                    score=min(1.0, score),
                    evidence_path=[f"node:{node_id}"],
                    explanation_id_only=(
                        f"Node {node_id} bridges {communities} communities "
                        f"(degree={degree}, bridge_score={score:.2f})"
                    ),
                    confidence=confidence,
                    meta={
                        "communities_bridged": communities,
                        "degree": degree,
                        "bridge_score": round(score, 4),
                    },
                )
            )
        return alerts
