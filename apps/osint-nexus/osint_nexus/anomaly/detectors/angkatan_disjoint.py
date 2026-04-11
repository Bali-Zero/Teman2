"""Detector 4: Angkatan Disjoint Alliance — cross-angkatan short paths.

JUSTIFICATION (project_osint_layer9_power_topology.md):
    Layer 9 establishes that "stessa angkatan = fratellanza a vita,
    loyalty cross-ufficio". Officials from the same Polimigras Depok
    graduation year form lifelong loyalty bonds. Cross-angkatan alliances
    are therefore structurally unusual and potentially significant.

    When two officials from DIFFERENT angkatan are connected by an
    unexpectedly short path through informal/non-official edges
    (family, patron, social), this may indicate:
    - Active bapakisme patron-client relationship
    - Marriage alliance between factions
    - Hidden coordination channel

    Layer 9 power scoring formula weights Patron Connections at 20%.

IMPLEMENTATION:
    Finds pairs of Officials with different angkatan values connected
    by paths of length <= max_path_length using only non-official edge
    types (family/patron/social edges, not WORKS_AT/POSTED_TO).

FALSE-POSITIVE MITIGATION:
    - min_angkatan_gap: angkatan 2001 and 2002 may overlap in classes;
      require gap >= 1 (configurable, raise to 3+ for stricter signals)
    - Only informal edge types: filters out structural connections
    - Confidence scaled by path shortness: shorter = more suspicious
    - Excludes self-loops and symmetric duplicates (A->B = B->A)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector


class AngkatanDisjointDetector(Detector):
    """Detect cross-angkatan alliances via short informal paths."""

    pattern_name = "angkatan_disjoint_alliance"

    async def run(self, session: AsyncSession) -> list[Alert]:
        """Find Officials from different angkatan connected by short
        paths through non-official edges.

        False-positive mitigation:
        - min_angkatan_gap filters adjacent cohorts
        - Only informal edge types (no WORKS_AT, POSTED_TO)
        - Confidence inversely proportional to path length
        - Symmetric dedup: only report (smaller_id, larger_id) pairs
        """
        max_path: int = self._t("max_path_length", 3)
        non_official_types: list[str] = self._t(
            "non_official_edge_types",
            [
                "MARRIED_TO",
                "PARENT_OF",
                "SIBLING_OF",
                "PATRON_OF",
                "KNOWS",
                "FREQUENTS",
                "MEMBER_OF",
            ],
        )
        min_gap: int = self._t("min_angkatan_gap", 1)

        # Build relationship type filter for variable-length path
        rel_filter = "|".join(non_official_types)

        query = f"""
        MATCH (a:Official), (b:Official)
        WHERE a.angkatan IS NOT NULL
          AND b.angkatan IS NOT NULL
          AND a.angkatan <> b.angkatan
          AND abs(toInteger(a.angkatan) - toInteger(b.angkatan)) >= $min_gap
          AND elementId(a) < elementId(b)
        MATCH p = shortestPath((a)-[:{rel_filter}*..{max_path}]-(b))
        WITH a, b, p, length(p) AS path_length
        RETURN elementId(a) AS node_a_id,
               a.angkatan AS angkatan_a,
               elementId(b) AS node_b_id,
               b.angkatan AS angkatan_b,
               path_length,
               [r IN relationships(p) | type(r)] AS edge_types,
               [n IN nodes(p) | elementId(n)] AS path_node_ids
        ORDER BY path_length ASC
        LIMIT 50
        """

        result = await session.run(query, {"min_gap": min_gap})

        alerts: list[Alert] = []
        async for record in result:
            node_a = record["node_a_id"]
            node_b = record["node_b_id"]
            angk_a = record["angkatan_a"]
            angk_b = record["angkatan_b"]
            path_len = record["path_length"]
            edge_types = record["edge_types"]
            path_nodes = record["path_node_ids"]

            # Score: shorter paths = higher anomaly score
            score = 1.0 / path_len

            # Confidence: shorter path + bigger angkatan gap = more confident
            angkatan_gap = abs(int(angk_a) - int(angk_b))
            confidence = min(1.0, (1.0 / path_len) * (angkatan_gap / 10.0))

            alerts.append(
                Alert(
                    pattern=self.pattern_name,
                    score=score,
                    evidence_path=[f"node:{nid}" for nid in path_nodes],
                    explanation_id_only=(
                        f"Officials {node_a} (angkatan {angk_a}) and "
                        f"{node_b} (angkatan {angk_b}) connected by "
                        f"{path_len}-hop path via {edge_types}"
                    ),
                    confidence=confidence,
                    meta={
                        "angkatan_a": str(angk_a),
                        "angkatan_b": str(angk_b),
                        "angkatan_gap": angkatan_gap,
                        "path_length": path_len,
                        "edge_types": edge_types,
                    },
                )
            )

        return alerts
