"""Anomaly runner — orchestrates all detectors, deduplicates, and ranks alerts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector
from osint_nexus.anomaly.thresholds import load_thresholds
from osint_nexus.utils.logging import get_logger

if TYPE_CHECKING:
    from neo4j import AsyncSession

logger = get_logger("anomaly.runner")


class AnomalyRunner:
    """Runs all registered detectors, deduplicates results, ranks by score."""

    def __init__(
        self,
        detectors: list[Detector] | None = None,
        config_path: Path | None = None,
    ) -> None:
        self._thresholds = load_thresholds(config_path)
        self._detectors: list[Detector] = detectors or self._default_detectors()

    def _default_detectors(self) -> list[Detector]:
        """Instantiate all 5 detectors with loaded thresholds."""
        from osint_nexus.anomaly.detectors.angkatan_disjoint import (
            AngkatanDisjointDetector,
        )
        from osint_nexus.anomaly.detectors.bridge_outlier import BridgeOutlierDetector
        from osint_nexus.anomaly.detectors.centrality_jump import (
            CentralityJumpDetector,
        )
        from osint_nexus.anomaly.detectors.eigenvector_reverse import (
            EigenvectorReverseDetector,
        )
        from osint_nexus.anomaly.detectors.temporal_burst import TemporalBurstDetector

        return [
            CentralityJumpDetector(self._thresholds.get("centrality_jump", {})),
            BridgeOutlierDetector(self._thresholds.get("bridge_outlier", {})),
            TemporalBurstDetector(self._thresholds.get("temporal_burst", {})),
            AngkatanDisjointDetector(
                self._thresholds.get("angkatan_disjoint_alliance", {})
            ),
            EigenvectorReverseDetector(
                self._thresholds.get("eigenvector_reverse", {})
            ),
        ]

    async def run_all(self, session: AsyncSession) -> list[Alert]:
        """Run all detectors sequentially and return deduplicated, ranked alerts.

        Sequential execution avoids Neo4j session contention. Each detector
        gets the same session so GDS projections can be shared if needed.
        """
        all_alerts: list[Alert] = []

        for detector in self._detectors:
            detector_name = detector.pattern_name or detector.__class__.__name__
            logger.info("Running detector: %s", detector_name)
            try:
                alerts = await detector.run(session)
                logger.info(
                    "Detector %s produced %d alerts", detector_name, len(alerts)
                )
                all_alerts.extend(alerts)
            except Exception:
                logger.exception("Detector %s failed", detector_name)

        deduped = self._deduplicate(all_alerts)
        ranked = self._rank(deduped)

        logger.info(
            "Scan complete: %d raw → %d deduped → ranked",
            len(all_alerts),
            len(ranked),
        )
        return ranked

    @staticmethod
    def _deduplicate(alerts: list[Alert]) -> list[Alert]:
        """Remove duplicate alerts based on dedup_key.

        When duplicates exist, keep the one with the highest score.
        """
        seen: dict[str, Alert] = {}
        for alert in alerts:
            key = alert.dedup_key
            if key not in seen or alert.score > seen[key].score:
                seen[key] = alert
        return list(seen.values())

    @staticmethod
    def _rank(alerts: list[Alert]) -> list[Alert]:
        """Rank alerts by (score * confidence) descending.

        This produces a stable ordering: alerts with both high score
        and high confidence float to the top.
        """
        return sorted(
            alerts,
            key=lambda a: (a.score * a.confidence, a.score),
            reverse=True,
        )

    def to_dict(self, alerts: list[Alert]) -> list[dict[str, Any]]:
        """Serialize alerts to plain dicts for JSON output."""
        return [
            {
                "id": a.id,
                "pattern": a.pattern,
                "score": round(a.score, 4),
                "confidence": round(a.confidence, 4),
                "evidence_path": a.evidence_path,
                "explanation": a.explanation_id_only,
                "detected_at": a.detected_at,
                "meta": a.meta,
            }
            for a in alerts
        ]
