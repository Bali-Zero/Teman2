"""Detector 5: Eigenvector Reverse — lone hubs with low-centrality neighbors.

JUSTIFICATION (project_osint_layer27_graph_analytics.md):
    Layer 27 lists eigenvector centrality as a measure of being
    "referenziato da nodi importanti" (referenced by important nodes).
    A node with HIGH eigenvector centrality whose 1-hop neighbors ALL
    have LOW eigenvector scores is structurally anomalous: it is important
    not because of WHO it connects to, but despite connecting only to
    unimportant nodes.

    This signals deliberate compartmentalization — the node is a "lone
    hub" that may be:
    - A handler controlling low-level operatives
    - A cutout designed to limit exposure
    - A patron whose clients are deliberately kept invisible

    Layer 9: "bapakisme" patrons sometimes operate through intermediaries
    who themselves have no visible power (low centrality), making the
    patron appear isolated in the graph while actually controlling
    significant resources.

IMPLEMENTATION:
    Uses GDS eigenvector centrality (Cypher projection). Falls back to
    PageRank if eigenvector is unavailable. Identifies nodes in the top
    percentile whose ALL 1-hop neighbors fall below the low percentile.

FALSE-POSITIVE MITIGATION:
    - min_neighbors: requires at least 2 neighbors (isolates ignored)
    - top_percentile: only examines truly high-eigenvector nodes
    - neighbor_max_percentile: "all neighbors low" is a strict criterion
    - Confidence scaled by neighbor count: more isolated neighbors =
      stronger signal
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector


class EigenvectorReverseDetector(Detector):
    """Detect high-eigenvector nodes surrounded by low-eigenvector neighbors."""

    pattern_name = "eigenvector_reverse"

    async def run(self, session: AsyncSession) -> list[Alert]:
        """Find lone hubs: high eigenvector, all neighbors low.

        False-positive mitigation:
        - min_neighbors filter avoids leaf/isolated nodes
        - Strict "all neighbors below threshold" criterion
        - Confidence scales with how isolated the hub is
        """
        top_pct: float = self._t("top_percentile", 0.10)
        neighbor_max_pct: float = self._t("neighbor_max_percentile", 0.25)
        min_neighbors: int = self._t("min_neighbors", 2)

        has_gds = await self.check_gds_available(session)

        if has_gds:
            return await self._run_with_gds(
                session, top_pct, neighbor_max_pct, min_neighbors
            )
        return await self._run_with_pagerank_proxy(
            session, top_pct, neighbor_max_pct, min_neighbors
        )

    async def _run_with_gds(
        self,
        session: AsyncSession,
        top_pct: float,
        neighbor_max_pct: float,
        min_neighbors: int,
    ) -> list[Alert]:
        """Use GDS eigenvector centrality."""
        # Project and compute
        try:
            await session.run("CALL gds.graph.drop('anomaly_eigen', false)")
        except Exception:
            pass

        await session.run("""
            CALL gds.graph.project.cypher(
                'anomaly_eigen',
                'MATCH (n) WHERE n:Official OR n:Person RETURN id(n) AS id',
                'MATCH (a)-[r]-(b)
                 WHERE (a:Official OR a:Person) AND (b:Official OR b:Person)
                 RETURN id(a) AS source, id(b) AS target'
            )
        """)

        await session.run("""
            CALL gds.eigenvector.write('anomaly_eigen', {
                writeProperty: '_anomaly_eigen',
                maxIterations: 50
            })
        """)

        alerts = await self._analyze_centrality(
            session,
            property_name="_anomaly_eigen",
            top_pct=top_pct,
            neighbor_max_pct=neighbor_max_pct,
            min_neighbors=min_neighbors,
        )

        # Cleanup
        try:
            await session.run("CALL gds.graph.drop('anomaly_eigen', false)")
            await session.run(
                "MATCH (n) WHERE n._anomaly_eigen IS NOT NULL "
                "REMOVE n._anomaly_eigen"
            )
        except Exception:
            pass

        return alerts

    async def _run_with_pagerank_proxy(
        self,
        session: AsyncSession,
        top_pct: float,
        neighbor_max_pct: float,
        min_neighbors: int,
    ) -> list[Alert]:
        """Fallback: approximate with degree-based centrality score.

        Without GDS, we compute a simple centrality proxy:
        score = degree / max_degree. This approximates eigenvector for
        small graphs.
        """
        # Compute degree-based centrality proxy
        await session.run("""
            MATCH (n)
            WHERE n:Official OR n:Person
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) AS deg
            WITH max(deg) AS max_deg
            MATCH (n)
            WHERE n:Official OR n:Person
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) AS deg, max_deg
            SET n._anomaly_eigen = CASE
                WHEN max_deg > 0 THEN toFloat(deg) / max_deg
                ELSE 0.0
            END
        """)

        alerts = await self._analyze_centrality(
            session,
            property_name="_anomaly_eigen",
            top_pct=top_pct,
            neighbor_max_pct=neighbor_max_pct,
            min_neighbors=min_neighbors,
        )

        # Cleanup
        try:
            await session.run(
                "MATCH (n) WHERE n._anomaly_eigen IS NOT NULL "
                "REMOVE n._anomaly_eigen"
            )
        except Exception:
            pass

        return alerts

    async def _analyze_centrality(
        self,
        session: AsyncSession,
        property_name: str,
        top_pct: float,
        neighbor_max_pct: float,
        min_neighbors: int,
    ) -> list[Alert]:
        """Common analysis logic: find high-centrality nodes with all-low neighbors."""
        # Get percentile thresholds
        threshold_query = f"""
        MATCH (n)
        WHERE (n:Official OR n:Person) AND n.{property_name} IS NOT NULL
        WITH n.{property_name} AS score
        ORDER BY score ASC
        WITH collect(score) AS scores
        WITH scores,
             scores[toInteger(size(scores) * (1.0 - $top_pct))] AS high_threshold,
             scores[toInteger(size(scores) * $neighbor_max_pct)] AS low_threshold
        RETURN high_threshold, low_threshold
        """
        thresh_result = await session.run(
            threshold_query,
            {"top_pct": top_pct, "neighbor_max_pct": neighbor_max_pct},
        )
        thresh_record = await thresh_result.single()
        if not thresh_record:
            return []

        high_threshold = thresh_record["high_threshold"]
        low_threshold = thresh_record["low_threshold"]

        if high_threshold is None or low_threshold is None:
            return []

        # Find lone hubs
        query = f"""
        MATCH (n)
        WHERE (n:Official OR n:Person)
          AND n.{property_name} >= $high_threshold
        MATCH (n)--(neighbor)
        WHERE (neighbor:Official OR neighbor:Person)
          AND neighbor.{property_name} IS NOT NULL
        WITH n,
             n.{property_name} AS node_score,
             collect(neighbor.{property_name}) AS neighbor_scores,
             collect(elementId(neighbor)) AS neighbor_ids,
             count(neighbor) AS num_neighbors
        WHERE num_neighbors >= $min_neighbors
          AND all(s IN neighbor_scores WHERE s <= $low_threshold)
        RETURN elementId(n) AS node_id,
               node_score,
               num_neighbors,
               reduce(acc = 0.0, s IN neighbor_scores | acc + s) / num_neighbors
                   AS avg_neighbor_score,
               neighbor_ids
        ORDER BY node_score DESC
        LIMIT 30
        """
        result = await session.run(
            query,
            {
                "high_threshold": high_threshold,
                "low_threshold": low_threshold,
                "min_neighbors": min_neighbors,
            },
        )

        alerts: list[Alert] = []
        async for record in result:
            node_id = record["node_id"]
            node_score = record["node_score"]
            num_neighbors = record["num_neighbors"]
            avg_neighbor = record["avg_neighbor_score"]
            neighbor_ids = record["neighbor_ids"]

            # Score: ratio between node's centrality and neighbor mean
            ratio = node_score / max(avg_neighbor, 0.001)
            score = min(1.0, ratio / 100.0)

            # Confidence: more neighbors all being low = stronger signal
            confidence = min(1.0, num_neighbors / 10.0)

            alerts.append(
                Alert(
                    pattern=self.pattern_name,
                    score=score,
                    evidence_path=[f"node:{node_id}"]
                    + [f"node:{nid}" for nid in neighbor_ids[:5]],
                    explanation_id_only=(
                        f"Node {node_id} has eigenvector {node_score:.4f} but "
                        f"{num_neighbors} neighbors average {avg_neighbor:.4f} "
                        f"(ratio={ratio:.0f}x)"
                    ),
                    confidence=confidence,
                    meta={
                        "node_score": round(node_score, 6),
                        "avg_neighbor_score": round(avg_neighbor, 6),
                        "ratio": round(ratio, 2),
                        "num_neighbors": num_neighbors,
                    },
                )
            )

        return alerts
