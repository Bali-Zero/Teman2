"""Detector Abstract Base Class.

Every detector follows the same shape:
1. accept a thresholds dict
2. expose ``.name`` — a stable detector identifier
3. expose ``.run(session)`` — run Cypher through a neo4j session-like
   object and return a list[Alert]

The session parameter is duck-typed: we don't import the neo4j driver
from this module. Any object with ``.run(query, params) -> records``
works. That keeps tests hermetic (no neo4j required).

Detectors MUST NOT log names. They must RETURN only IDs in Alert
objects. If a detector needs to fetch a name, it does so in a separate
method the runner never calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from osint_nexus.anomaly.alert import Alert


class SessionLike(Protocol):
    """Neo4j session duck type — we only need .run()."""

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> Any: ...


class Detector(ABC):
    """Base class for all anomaly detectors."""

    #: Stable string key used in YAML config and Alert.pattern
    name: str = "base"

    def __init__(self, thresholds: dict[str, Any] | None = None) -> None:
        self._thresholds = dict(self.default_thresholds())
        if thresholds:
            self._thresholds.update(thresholds)

    @classmethod
    def default_thresholds(cls) -> dict[str, Any]:
        """Per-class default thresholds. Override in subclasses."""
        return {}

    @property
    def thresholds(self) -> dict[str, Any]:
        return dict(self._thresholds)

    @abstractmethod
    def run(self, session: SessionLike) -> list[Alert]:
        """Execute the detector against a neo4j session.

        Must return a list of Alert objects (possibly empty).
        Must not raise on empty graphs.
        Must not log or return names — only opaque IDs.
        """

    def _mk_alert(
        self,
        *,
        primary_entity_id: str,
        score: float,
        confidence: float,
        evidence_path: list[str],
        rationale_id: str,
    ) -> Alert:
        """Helper: build a standard Alert with correct pattern + ID."""
        from osint_nexus.anomaly.alert import make_alert_id
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        day_bucket = now.strftime("%Y-%m-%d")
        return Alert(
            alert_id=make_alert_id(self.name, primary_entity_id, day_bucket=day_bucket),
            pattern=self.name,
            primary_entity_id=primary_entity_id,
            score=score,
            confidence=confidence,
            evidence_path=list(evidence_path),
            rationale_id=rationale_id,
            created_at=now.isoformat(),
        ).clamp()
