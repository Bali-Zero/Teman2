"""Detector Abstract Base Class.

Every detector follows the same shape:
1. accept a thresholds dict
2. expose ``.name`` — a stable detector identifier
3. expose ``.run(session)`` — run Cypher through a neo4j session-like
   object and return a list[Alert]
4. expose ``.precheck(session)`` — verify the live graph carries the
   preconditions the detector needs (e.g. temporal spread, angkatan
   variance). The runner calls ``precheck`` before ``run``; if it
   returns ``ok=False`` the detector is skipped and an informational
   alert is emitted in its place. This lets us distinguish
   "no anomalies today" from "detector semantically blocked because
   the graph does not yet have the data this detector needs".

The session parameter is duck-typed: we don't import the neo4j driver
from this module. Any object with ``.run(query, params) -> records``
works. That keeps tests hermetic (no neo4j required).

Detectors MUST NOT log names. They must RETURN only IDs in Alert
objects. If a detector needs to fetch a name, it does so in a separate
method the runner never calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol

from osint_nexus.anomaly.alert import Alert


class SessionLike(Protocol):
    """Neo4j session duck type — we only need .run()."""

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> Any: ...


@dataclass(frozen=True)
class PreconditionResult:
    """Result of a detector's ``precheck(session)`` call.

    ``ok``
        True if the detector can run meaningfully against the current
        graph. False if the graph lacks data the detector semantically
        needs (temporal spread, angkatan variance, etc.).

    ``reason``
        Short human-ish explanation of *why* the check failed. The
        runner surfaces this in the informational alert so the analyst
        can fix the upstream data problem.

    ``stat``
        Raw numbers the precheck observed, carried through to the
        informational alert's ``evidence_path`` for debugging. Values
        must be simple (int/float/str) — no Neo4j objects.
    """

    ok: bool
    reason: str = ""
    stat: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls) -> "PreconditionResult":
        return cls(ok=True)


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

    def precheck(self, session: SessionLike) -> PreconditionResult:
        """Confirm the live graph meets this detector's preconditions.

        Default implementation is permissive (``ok=True``) — detectors
        whose output is always meaningful on any non-empty graph can
        leave this alone. Detectors that semantically require a
        specific graph shape (temporal spread, variance in categorical
        fields, etc.) override this method.

        The runner calls ``precheck`` BEFORE ``run``; on a failing
        precheck the runner synthesizes a single informational alert
        and skips ``run``, so a broken precondition never masquerades
        as "no anomalies found".
        """
        return PreconditionResult.success()

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
        informational: bool = False,
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
            informational=informational,
        ).clamp()
