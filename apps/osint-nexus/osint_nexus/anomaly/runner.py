"""Orchestrator: runs every registered detector, dedupes, ranks."""

from __future__ import annotations

from typing import Any, Iterable

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector, SessionLike
from osint_nexus.utils.logging import get_logger

logger = get_logger("anomaly.runner")


class AnomalyRunner:
    """Runs a sequence of detectors and assembles a ranked alert list.

    Dedupe rule: two alerts with the same ``alert_id`` are collapsed to
    the one with the higher score. This keeps same-day re-runs stable
    and also handles the case where two detectors happen to flag the
    same (pattern, entity, day) triple.
    """

    def __init__(self, detectors: Iterable[Detector]) -> None:
        self._detectors: list[Detector] = list(detectors)

    @property
    def detector_names(self) -> list[str]:
        return [d.name for d in self._detectors]

    def run(self, session: SessionLike | None) -> list[Alert]:
        """Run all detectors, aggregate, dedupe, rank.

        A session of ``None`` is allowed for test paths where detectors
        already carry their results (fake detectors). Real detectors
        will raise if handed None.
        """
        collected: dict[str, Alert] = {}
        for detector in self._detectors:
            try:
                alerts = detector.run(session)  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover - exercised in test
                logger.warning(
                    "detector %s failed: %s", detector.name, type(exc).__name__
                )
                continue

            for alert in alerts:
                existing = collected.get(alert.alert_id)
                if existing is None or alert.score > existing.score:
                    collected[alert.alert_id] = alert

        return self._rank(list(collected.values()))

    @staticmethod
    def _rank(alerts: list[Alert]) -> list[Alert]:
        """Sort by score DESC, tie-break by alert_id ASC (stable)."""
        return sorted(alerts, key=lambda a: (-a.score, a.alert_id))
