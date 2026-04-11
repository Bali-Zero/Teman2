"""Orchestrator: runs every registered detector, dedupes, ranks.

Precheck flow
-------------
For each detector the runner first calls ``detector.precheck(session)``.
If the precheck returns ``ok=False`` the detector is SKIPPED — no
``run`` call — and the runner synthesizes a single informational
Alert:

* ``pattern``       = detector name
* ``primary_entity_id`` = ``"precondition:<name>"``
* ``score``         = 0.0
* ``confidence``    = 0.0
* ``rationale_id``  = ``"PRECHECK-BLOCKED:<reason>"``
* ``evidence_path`` = flattened ``key=value`` strings from ``stat``
* ``informational`` = True

Informational alerts pass through the same dedupe as real alerts but
are ranked LAST so they never bury real signal in operator dashboards.
"""

from __future__ import annotations

from typing import Any, Iterable

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector, PreconditionResult, SessionLike
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
            # Step 1 — precheck. A failing precheck produces a single
            # informational alert and the detector.run() is skipped.
            pre: PreconditionResult
            if session is not None:
                try:
                    pre = detector.precheck(session)  # type: ignore[arg-type]
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning(
                        "detector %s precheck failed: %s",
                        detector.name,
                        type(exc).__name__,
                    )
                    pre = PreconditionResult.success()
            else:
                pre = PreconditionResult.success()

            if not pre.ok:
                logger.info("detector %s blocked: %s", detector.name, pre.reason)
                info_alert = self._make_informational(detector, pre)
                collected[info_alert.alert_id] = info_alert
                continue

            # Step 2 — real run
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
    def _make_informational(detector: Detector, pre: PreconditionResult) -> Alert:
        """Build a single precondition-blocked alert for ``detector``."""
        primary = f"precondition:{detector.name}"
        evidence = [f"{k}={v}" for k, v in sorted(pre.stat.items())]
        return detector._mk_alert(
            primary_entity_id=primary,
            score=0.0,
            confidence=0.0,
            evidence_path=evidence,
            rationale_id=f"PRECHECK-BLOCKED:{pre.reason}",
            informational=True,
        )

    @staticmethod
    def _rank(alerts: list[Alert]) -> list[Alert]:
        """Sort by informational-last, then score DESC, then alert_id.

        ``informational`` alerts always come AFTER real alerts. Within
        each group we sort by score DESC and tie-break on alert_id
        ASC (stable determinism).
        """
        return sorted(
            alerts,
            key=lambda a: (a.informational, -a.score, a.alert_id),
        )
