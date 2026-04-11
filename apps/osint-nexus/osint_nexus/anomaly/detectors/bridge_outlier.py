"""Bridge-outlier detector — cut vertices between communities.

Justification
-------------
Memory cite: ``project_osint_layer27_graph_analytics.md``, Community
Detection section — "Louvain: Fazioni naturali (spesso NON
corrispondono a struktur formal). Sorpresa tipica: cluster cross-Kanim
= stessa angkatan o stessa arisan istri."

A cut vertex (articulation point) whose removal disconnects two
substantial Louvain communities is a **single point of failure** for
information flow between those factions. In an OSINT context this
translates to a broker who controls — probably deliberately — the only
channel between otherwise-isolated power groups. Such brokers are
uniquely valuable and uniquely vulnerable.

False positive mitigation
-------------------------
1. ``min_community_size`` — we require both sides of the cut to have
   at least N members. Stops alerts on a single node hanging off a
   community by one edge (accident / data noise).
2. ``min_communities`` — the cut must span at least 2 distinct
   Louvain community labels. Intra-community cut vertices are not
   interesting (local topological noise).
3. Score uses ``min(size_left, size_right) / max(size_left, size_right)``
   so a lopsided cut (1000 vs 3) scores lower than a balanced one
   (100 vs 80) — balanced is where real brokerage lives.
4. Evidence path contains only the cut vertex plus up to 10 neighbors
   — no community-wide dumps, to keep the alert compact.

Cypher strategy
---------------
1. Project the undirected graph via cypher projection.
2. Run ``gds.louvain.stream`` to label each node with a community id.
3. Run ``gds.articulationPoints.stream`` for cut vertices.
4. For each cut, compute neighbor community diversity via a plain
   Cypher match.
5. Emit one alert per cut vertex that meets size + diversity thresholds.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector, SessionLike
from osint_nexus.anomaly.thresholds import DEFAULT_THRESHOLDS

_PROJECTION_NAME = "anomaly_bridge"


class BridgeOutlierDetector(Detector):
    name = "bridge_outlier"

    @classmethod
    def default_thresholds(cls) -> dict[str, Any]:
        return dict(DEFAULT_THRESHOLDS["bridge_outlier"])

    # ------------------------------------------------------------------
    _PROJECT_Q = f"""
    CALL gds.graph.project.cypher(
      '{_PROJECTION_NAME}',
      'MATCH (n) RETURN id(n) AS id',
      'MATCH (a)-[r]-(b) RETURN id(a) AS source, id(b) AS target'
    )
    YIELD graphName
    RETURN graphName
    """

    _LOUVAIN_Q = f"""
    CALL gds.louvain.stream('{_PROJECTION_NAME}')
    YIELD nodeId, communityId
    RETURN toString(nodeId) AS node_id, communityId AS community_id
    """

    _ARTICULATION_Q = f"""
    CALL gds.articulationPoints.stream('{_PROJECTION_NAME}')
    YIELD nodeId
    RETURN toString(nodeId) AS node_id
    """

    _NEIGHBORS_Q = """
    UNWIND $cut_ids AS cid
    MATCH (cut) WHERE toString(elementId(cut)) = cid OR toString(id(cut)) = cid
    OPTIONAL MATCH (cut)-[]-(nbr)
    WITH cid AS cut_id, collect(DISTINCT nbr) AS neighbors
    RETURN cut_id,
           [n IN neighbors | coalesce(toString(elementId(n)), toString(id(n)))] AS neighbor_ids,
           [n IN neighbors | n.community_id] AS neighbor_communities
    """

    _CLEANUP_Q = f"CALL gds.graph.drop('{_PROJECTION_NAME}', false) YIELD graphName"
    # ------------------------------------------------------------------

    def run(self, session: SessionLike) -> list[Alert]:
        if session is None:
            return []

        th = self._thresholds
        min_communities = int(th.get("min_communities", 2))
        min_community_size = int(th.get("min_community_size", 3))
        min_score = float(th.get("min_score", 0.6))

        try:
            session.run(self._PROJECT_Q)
        except Exception:  # pragma: no cover
            pass

        louvain_records = list(session.run(self._LOUVAIN_Q))
        if not louvain_records:
            self._safe_drop(session)
            return []

        community_of: dict[str, int] = {}
        community_sizes: Counter[int] = Counter()
        for rec in louvain_records:
            nid = str(rec["node_id"])
            cid = int(rec["community_id"])
            community_of[nid] = cid
            community_sizes[cid] += 1

        articulation_records = list(session.run(self._ARTICULATION_Q))
        if not articulation_records:
            self._safe_drop(session)
            return []

        cut_ids = [str(r["node_id"]) for r in articulation_records]
        neighbor_map: dict[str, dict[str, Any]] = {}
        for rec in session.run(self._NEIGHBORS_Q, {"cut_ids": cut_ids}):
            neighbor_map[str(rec["cut_id"])] = {
                "neighbor_ids": [str(n) for n in rec.get("neighbor_ids", []) if n],
                "neighbor_communities": [
                    int(c) for c in rec.get("neighbor_communities", []) if c is not None
                ],
            }

        alerts: list[Alert] = []
        for cid_node in cut_ids:
            info = neighbor_map.get(cid_node)
            if not info:
                continue
            neigh_ids = info["neighbor_ids"]
            neigh_comms_raw = info["neighbor_communities"]

            # If Louvain did not decorate neighbor nodes with community_id
            # inline, fall back to the global community_of map.
            if not neigh_comms_raw:
                neigh_comms = [community_of[n] for n in neigh_ids if n in community_of]
            else:
                neigh_comms = neigh_comms_raw

            distinct_comms = set(neigh_comms)
            if len(distinct_comms) < min_communities:
                continue

            # Keep only communities at least min_community_size large
            big_comms = {c for c in distinct_comms if community_sizes.get(c, 0) >= min_community_size}
            if len(big_comms) < min_communities:
                continue

            sizes = sorted(
                (community_sizes[c] for c in big_comms), reverse=True
            )
            if len(sizes) < 2:
                continue
            balance = sizes[-1] / sizes[0] if sizes[0] else 0.0

            # Score: (balance * min(1, distinct/5)) clamped. A balanced
            # cut between 2 large communities gets ~1.0; lopsided or
            # single-community cuts get closer to 0.
            distinct_factor = min(1.0, len(big_comms) / 3.0 + 0.5)
            score = balance * distinct_factor
            if score < min_score:
                continue

            confidence = min(1.0, min(sizes) / 10.0)

            evidence = [cid_node] + neigh_ids[:10]
            alerts.append(
                self._mk_alert(
                    primary_entity_id=cid_node,
                    score=score,
                    confidence=confidence,
                    evidence_path=evidence,
                    rationale_id="BO-CUT-BETWEEN-COMMUNITIES",
                )
            )

        self._safe_drop(session)
        return alerts

    @staticmethod
    def _safe_drop(session: SessionLike) -> None:
        try:
            session.run(BridgeOutlierDetector._CLEANUP_Q)
        except Exception:  # pragma: no cover
            pass
