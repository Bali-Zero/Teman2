"""Detector abstract base class.

Every anomaly detector inherits from ``Detector`` and implements
``run(session)`` which returns a list of ``Alert`` objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from osint_nexus.anomaly.alert import Alert

if TYPE_CHECKING:
    from neo4j import AsyncSession


class Detector(ABC):
    """Base class for all graph anomaly detectors.

    Subclasses MUST:
    - Set ``pattern_name`` (used in Alert.pattern)
    - Implement ``run()``
    - Include a justification comment block at module level
    - Include a false-positive mitigation docstring in ``run()``
    """

    pattern_name: str = ""

    def __init__(self, thresholds: dict[str, Any] | None = None) -> None:
        self._thresholds = thresholds or {}

    def _t(self, key: str, default: Any) -> Any:
        """Get a threshold value, falling back to default."""
        return self._thresholds.get(key, default)

    @abstractmethod
    async def run(self, session: AsyncSession) -> list[Alert]:
        """Execute the detector against a Neo4j session.

        Args:
            session: An open Neo4j AsyncSession.

        Returns:
            List of Alert objects. May be empty if no anomalies found.
        """
        ...

    async def check_gds_available(self, session: AsyncSession) -> bool:
        """Check if Neo4j GDS plugin is installed."""
        try:
            result = await session.run("RETURN gds.version() AS v")
            record = await result.single()
            return record is not None
        except Exception:
            return False
