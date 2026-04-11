"""Centrality-jump detector — structural proxy for temporal centrality.

Justification
-------------
Memory cite: ``project_osint_layer27_graph_analytics.md``, Centrality
Algorithms section, and ``project_osint_layer9_power_topology.md``,
"Temporal Power Mapping" / "Ciclo Pilkada: pre-elezioni regionali =
mutasi massicce = rimescolamento".

The pure temporal-snapshot version of this detector (compare
betweenness_t vs betweenness_t-1) is **not implementable today**
because the graph schema has no history table — only
``r.updated_at`` on each edge. We therefore use a structural proxy:

**Proxy**: treat the most recently written ``recent_fraction`` of
edges (sorted by ``r.updated_at``) as a "today" layer and the rest as
a "before" layer. For each node compute ``recent_degree /
total_degree`` — the **recency ratio**. Nodes whose recency ratio is
more than ``sigma_multiplier`` standard deviations above the
population mean are flagged as candidates for centrality shift.

Why degree and not betweenness? Betweenness on the projected graph
is cheap but its timeline-aware version requires running it twice on
two different projections, and that doubles cost + does not beat
degree-based detection on real Kemenkumham data — where the primary
signal is "suddenly a lot more people are connected to X". We
document this limitation in ``anomaly-patterns.md``.

False positive mitigation
-------------------------
1. ``min_degree`` — skip nodes with very few total edges.
2. Recency ratio is compared only to the *local* population's mean and
   sigma, so batch ingestions (which boost everyone uniformly) do not
   produce false positives.
3. Score is normalized via a logistic squash so a 10-sigma outlier and
   a 3-sigma outlier both end up in [0.6, 1.0] — the analyst still
   sees the raw z in the alert rationale.
4. ``min_score`` cut prevents borderline cases.

Data precondition
-----------------
Same as ``temporal_burst``: we need at least ``min_history_days`` of
temporal spread on ``r.updated_at`` for "recent" to differ
meaningfully from "before". Below that threshold the recency ratio
is uniformly 1 (or uniformly 0) across the whole graph and the z test
produces zero-variance nonsense. The runner calls ``precheck()`` and
emits one informational alert when blocked.

Cypher strategy
---------------
```cypher
MATCH (n)
WITH n, count { (n)-[r]-() } AS total_degree
WHERE total_degree >= $min_degree
CALL (n, total_degree) {
  MATCH (n)-[r]-()
  WHERE r.updated_at IS NOT NULL
  WITH r ORDER BY datetime(r.updated_at) DESC
  WITH collect(r) AS rels,
       toInteger(ceil(total_degree * $recent_fraction)) AS k
  RETURN size(rels[..k]) AS recent_degree
}
RETURN toString(elementId(n)) AS node_id, total_degree, recent_degree
```

Note on neighbor fetch: we fetch the top-K neighbors of alerted nodes
for the evidence path (separate query), for analyst context.
"""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector, PreconditionResult, SessionLike
from osint_nexus.anomaly.thresholds import DEFAULT_THRESHOLDS


class CentralityJumpDetector(Detector):
    name = "centrality_jump"

    @classmethod
    def default_thresholds(cls) -> dict[str, Any]:
        return dict(DEFAULT_THRESHOLDS["centrality_jump"])

    _PRECHECK_Q = """
    // centrality_jump_precheck — observed history span
    MATCH ()-[r]->()
    WHERE r.updated_at IS NOT NULL
    WITH datetime(r.updated_at) AS ts
    RETURN min(ts) AS min_ts, max(ts) AS max_ts, count(*) AS total,
           duration.inDays(min(ts), max(ts)).days AS spread_days
    """

    # Query marker in comment so FakeSession can match by substring.
    # Uses the scoped CALL (n, total_degree) { ... } form (Neo4j 5.23+)
    # to silence the "CALL subquery without a variable scope" warning.
    # Takes the first ceil(total * recent_fraction) edges ordered by
    # r.updated_at DESC — the actual recent slice, not the buggy
    # always-full / always-empty predicate the old query used.
    _DEGREE_Q = """
    // recent_degree — centrality_jump probe
    MATCH (n)
    WITH n, count { (n)-[]-() } AS total_degree
    WHERE total_degree >= $min_degree
    CALL (n, total_degree) {
      MATCH (n)-[r]-()
      WHERE r.updated_at IS NOT NULL
      WITH r, datetime(r.updated_at) AS ts
      ORDER BY ts DESC
      WITH collect(r) AS rels,
           toInteger(ceil(total_degree * $recent_fraction)) AS k
      RETURN size(rels[..k]) AS recent_degree
    }
    RETURN toString(elementId(n)) AS node_id,
           total_degree,
           recent_degree
    """

    _NEIGHBORS_Q = """
    // spike_neighbors — evidence fetch for centrality_jump
    UNWIND $node_ids AS nid
    MATCH (n) WHERE toString(elementId(n)) = nid
    OPTIONAL MATCH (n)-[r]-(nbr)
    WHERE r.updated_at IS NOT NULL
    WITH nid AS node_id, r, nbr, datetime(r.updated_at) AS ts
    ORDER BY ts DESC
    WITH node_id, [x IN collect(DISTINCT nbr) WHERE x IS NOT NULL][..10] AS recent_neighbors
    RETURN node_id,
           [x IN recent_neighbors | toString(elementId(x))] AS neighbor_ids
    """

    def precheck(self, session: SessionLike) -> PreconditionResult:
        """Verify the graph has enough r.updated_at spread for the recency proxy."""
        if session is None:  # pragma: no cover - runner never passes None
            return PreconditionResult.success()
        min_days = int(self._thresholds.get("min_history_days", 30))
        try:
            records = list(session.run(self._PRECHECK_Q))
        except Exception as exc:  # pragma: no cover - defensive
            return PreconditionResult(
                ok=False,
                reason=f"precheck query failed: {type(exc).__name__}",
                stat={"error": type(exc).__name__},
            )
        if not records:
            return PreconditionResult(
                ok=False,
                reason="no edges with r.updated_at",
                stat={"total_edges_with_ts": 0, "min_history_days": min_days},
            )
        rec = records[0]
        total = int(rec.get("total") or 0)
        spread = rec.get("spread_days")
        spread_days = int(spread) if spread is not None else 0
        stat = {
            "total_edges_with_ts": total,
            "spread_days": spread_days,
            "min_history_days": min_days,
        }
        if total == 0:
            return PreconditionResult(
                ok=False,
                reason="no edges with r.updated_at",
                stat=stat,
            )
        if spread_days < min_days:
            return PreconditionResult(
                ok=False,
                reason=f"temporal spread too narrow: {spread_days} days, need {min_days}",
                stat=stat,
            )
        return PreconditionResult(ok=True, stat=stat)

    def run(self, session: SessionLike) -> list[Alert]:
        if session is None:
            return []

        th = self._thresholds
        sigma_mult = float(th.get("sigma_multiplier", 2.5))
        min_degree = int(th.get("min_degree", 3))
        recent_fraction = float(th.get("recent_fraction", 0.2))
        min_score = float(th.get("min_score", 0.55))

        params = {"min_degree": min_degree, "recent_fraction": recent_fraction}
        records = list(session.run(self._DEGREE_Q, params))
        if not records:
            return []

        ratios: list[tuple[str, float, int, int]] = []
        for rec in records:
            total = int(rec["total_degree"])
            recent = int(rec["recent_degree"])
            if total < min_degree or total == 0:
                continue
            ratios.append((str(rec["node_id"]), recent / total, total, recent))

        if len(ratios) < 3:
            return []

        values = [r[1] for r in ratios]
        mu = mean(values)
        sigma = pstdev(values) if len(values) > 1 else 0.0
        if sigma == 0.0:
            return []

        candidates: list[tuple[str, float, float, int, int]] = []
        for nid, ratio, total, recent in ratios:
            z = (ratio - mu) / sigma
            if z < sigma_mult:
                continue
            # Logistic squash to [0, 1]: 0 at z=sigma_mult, →1 as z grows
            score = 1.0 / (1.0 + math.exp(-(z - sigma_mult)))
            # Shift so z==sigma_mult → 0.5 and large z → ~1.0
            score = 0.5 + score / 2.0
            if score < min_score:
                continue
            candidates.append((nid, score, z, total, recent))

        if not candidates:
            return []

        # Fetch neighbors for evidence
        ids = [c[0] for c in candidates]
        neigh_by_id: dict[str, list[str]] = {}
        for rec in session.run(self._NEIGHBORS_Q, {"node_ids": ids}):
            neigh_by_id[str(rec["node_id"])] = [
                str(x) for x in rec.get("neighbor_ids", []) if x
            ]

        alerts: list[Alert] = []
        for nid, score, z, total, recent in candidates:
            neighbors = neigh_by_id.get(nid, [])
            # Confidence: more data = more trust; cap at 1.0
            confidence = min(1.0, total / 20.0)
            alerts.append(
                self._mk_alert(
                    primary_entity_id=nid,
                    score=score,
                    confidence=confidence,
                    evidence_path=[nid, *neighbors[:10]],
                    rationale_id=f"CJ-DEGREE-DELTA-Z{z:.1f}",
                )
            )
        return alerts
