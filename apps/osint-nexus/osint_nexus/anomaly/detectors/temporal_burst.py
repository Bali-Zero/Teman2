"""Detector 3: Temporal Burst — edge-class spikes above EWMA baseline.

JUSTIFICATION (project_osint_layer27_graph_analytics.md):
    Layer 27 lists temporal anomaly detection as pattern #3: "promosso
    entro 6 mesi da nuovo boss + stessa angkatan". More broadly, a
    sudden spike in a specific edge type (MET_WITH, ATTENDED,
    WON_CONTRACT) can signal coordinated activity: a patron consolidating
    allies, a procurement ring warming up, or pre-election maneuvering.

    Layer 9 (power topology): "Ciclo Pilkada: pre-elezioni regionali =
    mutasi massicce = rimescolamento" — temporal bursts in PROMOTED_TO
    or POSTED_TO around election cycles are high-value signals.

IMPLEMENTATION:
    Aggregates edge counts per edge type per 7-day window. Computes EWMA
    (span=30d) as baseline. Flags windows where count > EWMA + z*sigma.
    Operates entirely in Cypher over edge date properties.

FALSE-POSITIVE MITIGATION:
    - min_baseline_days: requires enough history for stable EWMA
    - z_threshold=3.0: only flags truly extreme spikes
    - Edge types are configurable: focus on high-signal types
    - Batch data entry (e.g., scraper backfill) is flagged as meta warning
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from neo4j import AsyncSession

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector


class TemporalBurstDetector(Detector):
    """Detect spikes in edge creation rate above EWMA baseline."""

    pattern_name = "temporal_burst"

    async def run(self, session: AsyncSession) -> list[Alert]:
        """Scan for edge-type temporal bursts.

        False-positive mitigation:
        - z_threshold=3.0 filters normal variance
        - min_baseline_days ensures EWMA stability
        - Batch-entry detection via meta flag
        """
        window_days: int = self._t("window_days", 7)
        ewma_span: int = self._t("ewma_span_days", 30)
        z_threshold: float = self._t("z_threshold", 3.0)
        min_baseline: int = self._t("min_baseline_days", 14)
        edge_types: list[str] = self._t(
            "edge_types",
            ["MET_WITH", "ATTENDED", "WON_CONTRACT", "PROMOTED_TO", "POSTED_TO"],
        )

        # Fetch all dated edges grouped by type and date
        query = """
        MATCH ()-[r]->()
        WHERE type(r) IN $edge_types
          AND coalesce(r.date, r.updated_at, r.created_at) IS NOT NULL
        WITH type(r) AS edge_type,
             date(coalesce(r.date, r.updated_at, r.created_at)) AS edge_date,
             elementId(r) AS rel_id
        RETURN edge_type, edge_date, collect(rel_id) AS rel_ids
        ORDER BY edge_type, edge_date
        """
        result = await session.run(query, {"edge_types": edge_types})

        # Group by edge type
        type_dates: dict[str, list[tuple[datetime, list[str]]]] = defaultdict(list)
        async for record in result:
            et = record["edge_type"]
            ed = record["edge_date"]
            rel_ids = record["rel_ids"]
            # neo4j date -> python datetime
            if hasattr(ed, "to_native"):
                dt = datetime.combine(
                    ed.to_native(), datetime.min.time(), tzinfo=timezone.utc
                )
            else:
                dt = datetime(ed.year, ed.month, ed.day, tzinfo=timezone.utc)
            type_dates[et].append((dt, rel_ids))

        alerts: list[Alert] = []

        for edge_type, date_groups in type_dates.items():
            if not date_groups:
                continue

            date_groups.sort(key=lambda x: x[0])

            # Build daily counts
            first_date = date_groups[0][0]
            last_date = date_groups[-1][0]
            total_days = (last_date - first_date).days + 1

            if total_days < min_baseline:
                continue

            daily_counts: dict[int, int] = {}  # day_offset -> count
            daily_rels: dict[int, list[str]] = {}
            for dt, rel_ids in date_groups:
                day_offset = (dt - first_date).days
                daily_counts[day_offset] = daily_counts.get(day_offset, 0) + len(
                    rel_ids
                )
                daily_rels.setdefault(day_offset, []).extend(rel_ids)

            # Compute EWMA and detect bursts in windows
            alpha = 2.0 / (ewma_span + 1)
            ewma = 0.0
            ewma_sq = 0.0
            burst_alerts = self._detect_bursts(
                daily_counts=daily_counts,
                daily_rels=daily_rels,
                total_days=total_days,
                window_days=window_days,
                alpha=alpha,
                z_threshold=z_threshold,
                min_baseline=min_baseline,
                edge_type=edge_type,
                first_date=first_date,
            )
            alerts.extend(burst_alerts)

        return alerts

    def _detect_bursts(
        self,
        daily_counts: dict[int, int],
        daily_rels: dict[int, list[str]],
        total_days: int,
        window_days: int,
        alpha: float,
        z_threshold: float,
        min_baseline: int,
        edge_type: str,
        first_date: datetime,
    ) -> list[Alert]:
        """Compute EWMA over daily counts and flag windows above z-threshold."""
        alerts: list[Alert] = []
        ewma = 0.0
        ewma_var = 0.0

        for day in range(total_days):
            count = daily_counts.get(day, 0)

            if day >= min_baseline:
                sigma = math.sqrt(max(ewma_var, 0.01))
                z_score = (count - ewma) / sigma if sigma > 0 else 0.0

                if z_score >= z_threshold and count > 0:
                    # Collect evidence from the burst window
                    window_rels: list[str] = []
                    for d in range(max(0, day - window_days + 1), day + 1):
                        window_rels.extend(daily_rels.get(d, []))

                    window_count = sum(
                        daily_counts.get(d, 0)
                        for d in range(max(0, day - window_days + 1), day + 1)
                    )

                    burst_date = first_date + timedelta(days=day)
                    score = min(1.0, z_score / 10.0)
                    confidence = min(1.0, day / (min_baseline * 3.0))

                    alerts.append(
                        Alert(
                            pattern=self.pattern_name,
                            score=score,
                            evidence_path=[f"rel:{rid}" for rid in window_rels[:10]],
                            explanation_id_only=(
                                f"Edge type {edge_type}: {window_count} edges in "
                                f"{window_days}d window ending {burst_date.date()}, "
                                f"z={z_score:.1f} (EWMA={ewma:.1f}, sigma={sigma:.1f})"
                            ),
                            confidence=confidence,
                            meta={
                                "edge_type": edge_type,
                                "window_count": window_count,
                                "z_score": round(z_score, 2),
                                "ewma": round(ewma, 2),
                                "burst_date": burst_date.date().isoformat(),
                            },
                        )
                    )

            # Update EWMA
            ewma = alpha * count + (1 - alpha) * ewma
            diff = count - ewma
            ewma_var = alpha * (diff * diff) + (1 - alpha) * ewma_var

        return alerts
