"""Temporal-burst detector.

Justification
-------------
Memory cite: ``project_osint_layer27_graph_analytics.md`` — the
detection of sudden spikes in meeting / attendance edges is a
canonical signal of "something is happening": a pre-mutasi political
realignment, a sponsorship blitz, a crisis-response coalition forming.
See also ``project_osint_layer9_power_topology.md``, section "Ciclo
Pilkada": mutasi massicce correlate with social-event bursts.

We implement a z-score burst test over weekly EWMA baselines,
following Kleinberg (2002) "Bursty and hierarchical structure in
streams". The exact formula:

```
ewma_t = alpha * x_t + (1 - alpha) * ewma_{t-1}
var_t  = alpha * (x_t - ewma_{t-1})^2 + (1 - alpha) * var_{t-1}
z_t    = (x_t - ewma_{t-1}) / sqrt(var_{t-1})
```

The detector raises one alert per (rel_type, bucket) where z_t >
threshold AND x_t >= min_edges_in_window AND the edges in that bucket
are not predominantly from an excluded source.

Important caveat (documented limitation)
----------------------------------------
The OSINT graph does NOT carry a genuine *event date* on edges like
``MET_WITH`` or ``ATTENDED``. The only available timestamp is
``r.updated_at`` — which reflects when the loader wrote the edge, not
when the real-world event happened.

In the current live graph (Apr 2026) ``r.created_at`` is always NULL,
so the legacy ``coalesce(r.updated_at, r.created_at)`` pattern was
pointless overhead. We just use ``r.updated_at`` directly and skip
edges where it is null.

Data precondition
-----------------
Burst detection requires **at least ``min_history_days`` of temporal
spread** (the span between the oldest and newest ``r.updated_at``).
Below that threshold the EWMA baseline has no memory, every bucket is
"bursty" and the detector produces 100% false positives. The runner
calls ``precheck()`` first and emits a single informational alert on
blocked runs instead of running the detector.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector, PreconditionResult, SessionLike
from osint_nexus.anomaly.thresholds import DEFAULT_THRESHOLDS


class TemporalBurstDetector(Detector):
    name = "temporal_burst"

    @classmethod
    def default_thresholds(cls) -> dict[str, Any]:
        return dict(DEFAULT_THRESHOLDS["temporal_burst"])

    _PRECHECK_Q = """
    // temporal_burst_precheck — observed history span
    MATCH ()-[r]->()
    WHERE r.updated_at IS NOT NULL
    WITH datetime(r.updated_at) AS ts
    RETURN min(ts) AS min_ts, max(ts) AS max_ts, count(*) AS total,
           duration.inDays(min(ts), max(ts)).days AS spread_days
    """

    _SERIES_Q = """
    // temporal_burst_series — weekly bucket counts for configured rel types
    UNWIND $rel_types AS rt
    CALL (rt) {
      MATCH ()-[r]->()
      WHERE type(r) = rt
        AND r.updated_at IS NOT NULL
      WITH r,
           date.truncate('week', datetime(r.updated_at)) AS bucket
      WITH bucket, count(r) AS edge_count,
           collect(DISTINCT coalesce(r.source, '')) AS sources
      RETURN toString(bucket) AS bucket, edge_count, sources
    }
    RETURN rt AS rel_type, bucket, edge_count, sources
    ORDER BY rel_type, bucket
    """

    _BURST_EDGES_Q = """
    // burst_edges — fetch source/target ids for the spike bucket
    UNWIND $buckets AS b
    MATCH (src)-[r]->(tgt)
    WHERE type(r) = b.rel_type
      AND r.updated_at IS NOT NULL
      AND date.truncate('week', datetime(r.updated_at)) = date(b.bucket)
    WITH b.rel_type AS rel_type, b.bucket AS bucket,
         collect(DISTINCT toString(elementId(src))) AS source_ids,
         collect(DISTINCT toString(elementId(tgt))) AS target_ids
    RETURN rel_type, bucket, source_ids[..10] AS source_ids, target_ids[..10] AS target_ids
    """

    def precheck(self, session: SessionLike) -> PreconditionResult:
        """Verify the graph has enough temporal spread for EWMA to mean anything."""
        if session is None:  # pragma: no cover - runner never passes None here
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
        z_threshold = float(th.get("z_threshold", 3.0))
        alpha = float(th.get("ewma_alpha", 0.3))
        min_edges = int(th.get("min_edges_in_window", 5))
        min_score = float(th.get("min_score", 0.6))
        rel_types = list(th.get("rel_types", []))
        source_exclude = {s.lower() for s in th.get("source_exclude", [])}

        records = list(session.run(self._SERIES_Q, {"rel_types": rel_types}))
        if not records:
            return []

        series: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rec in records:
            series[str(rec["rel_type"])].append({
                "bucket": str(rec["bucket"]),
                "edge_count": int(rec["edge_count"]),
                "sources": [str(s).lower() for s in rec.get("sources", [])],
            })

        bursts: list[dict[str, Any]] = []
        for rel_type, buckets in series.items():
            if len(buckets) < 3:
                continue
            buckets_sorted = sorted(buckets, key=lambda b: b["bucket"])
            ewma: float = float(buckets_sorted[0]["edge_count"])
            var: float = 1.0  # start with non-zero variance to avoid div/0
            for item in buckets_sorted[1:]:
                x = float(item["edge_count"])
                diff = x - ewma
                z = diff / (var ** 0.5) if var > 0 else 0.0
                # If sources are all excluded, skip (don't even update ewma
                # — these aren't real-world bursts).
                if item["sources"] and all(s in source_exclude for s in item["sources"] if s):
                    continue
                if z >= z_threshold and x >= min_edges:
                    bursts.append({
                        "rel_type": rel_type,
                        "bucket": item["bucket"],
                        "z": z,
                        "count": int(x),
                    })
                # Update EWMA + variance
                ewma = alpha * x + (1 - alpha) * ewma
                var = alpha * diff * diff + (1 - alpha) * var

        if not bursts:
            return []

        # Enrich with edge ids (for evidence path)
        edges_by_key: dict[tuple[str, str], dict[str, list[str]]] = {}
        for rec in session.run(
            self._BURST_EDGES_Q,
            {"buckets": [{"rel_type": b["rel_type"], "bucket": b["bucket"]} for b in bursts]},
        ):
            key = (str(rec["rel_type"]), str(rec["bucket"]))
            edges_by_key[key] = {
                "source_ids": [str(x) for x in rec.get("source_ids", [])],
                "target_ids": [str(x) for x in rec.get("target_ids", [])],
            }

        alerts: list[Alert] = []
        for b in bursts:
            key = (b["rel_type"], b["bucket"])
            evidence = edges_by_key.get(key, {"source_ids": [], "target_ids": []})
            primary_id = f"{b['rel_type']}:{b['bucket']}"
            # Score: squash z to [0, 1] with z_threshold → 0.6
            z = float(b["z"])
            score = 0.6 + min(0.4, (z - z_threshold) / 10.0)
            if score < min_score:
                continue
            confidence = min(1.0, b["count"] / 20.0)
            evidence_path = [primary_id] + evidence["source_ids"] + evidence["target_ids"]
            alerts.append(
                self._mk_alert(
                    primary_entity_id=primary_id,
                    score=score,
                    confidence=confidence,
                    evidence_path=evidence_path,
                    rationale_id=f"TB-{b['rel_type']}-Z{z:.1f}",
                )
            )
        return alerts
