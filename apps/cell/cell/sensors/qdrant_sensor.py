"""QdrantSensor — monitors Qdrant collection health from /health body.

No additional HTTP call needed — reuses the HealthReading already fetched
by HealthSensor. Reads body.database.collections and body.database.total_documents.

Thresholds:
  collections < 8          → YELLOW  (expected ≥ 8 live collections)
  doc drop > 5% vs baseline → YELLOW
"""
from dataclasses import dataclass, field
from typing import Any

from cell.sensors.health_sensor import HealthReading

_EXPECTED_COLLECTIONS = 8
_DOC_DROP_THRESHOLD = 0.05  # 5% drop triggers YELLOW


@dataclass
class SensorReading:
    status: str  # "green", "yellow", "red"
    metadata: dict[str, Any] = field(default_factory=dict)


class QdrantSensor:
    """Detects Qdrant degradation from /health body without extra HTTP calls."""

    def __init__(self) -> None:
        self._baseline_docs: int | None = None

    def read(self, health: HealthReading) -> SensorReading:
        if health.body is None:
            return SensorReading(status="red", metadata={"reason": "health body absent"})

        db_info = health.body.get("database", {})
        if not isinstance(db_info, dict):
            return SensorReading(status="red", metadata={"reason": "database key not a dict"})

        collections = db_info.get("collections")
        total_docs = db_info.get("total_documents")

        issues: list[str] = []

        # Collections count check
        if collections is not None:
            try:
                coll_count = int(collections)
                if coll_count < _EXPECTED_COLLECTIONS:
                    issues.append(f"collections={coll_count} < expected {_EXPECTED_COLLECTIONS}")
            except (ValueError, TypeError):
                issues.append(f"collections value unreadable: {collections!r}")

        # Document drop check
        if total_docs is not None:
            try:
                docs_now = int(total_docs)
                if self._baseline_docs is None:
                    self._baseline_docs = docs_now
                else:
                    drop_pct = (self._baseline_docs - docs_now) / max(self._baseline_docs, 1)
                    if drop_pct > _DOC_DROP_THRESHOLD:
                        issues.append(
                            f"docs dropped {drop_pct:.1%}: {self._baseline_docs} → {docs_now}"
                        )
                    # Update baseline upwards only (never lower it on a drop)
                    if docs_now > self._baseline_docs:
                        self._baseline_docs = docs_now
            except (ValueError, TypeError):
                issues.append(f"total_documents value unreadable: {total_docs!r}")

        if issues:
            return SensorReading(
                status="yellow",
                metadata={
                    "issues": issues,
                    "collections": collections,
                    "total_documents": total_docs,
                    "baseline_docs": self._baseline_docs,
                },
            )

        return SensorReading(
            status="green",
            metadata={
                "collections": collections,
                "total_documents": total_docs,
                "baseline_docs": self._baseline_docs,
            },
        )
