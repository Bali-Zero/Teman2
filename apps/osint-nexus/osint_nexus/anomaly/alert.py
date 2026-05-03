"""Alert dataclass — the output unit for every detector.

OPSEC: ``explanation_id_only`` must NEVER contain entity names.
It exposes only Neo4j internal IDs or hashed references so that a
separate, access-controlled resolve step can map them to names.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class Alert:
    """A single anomaly alert produced by a detector."""

    # Unique alert ID (auto-generated UUID4)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # Which detector pattern produced this alert
    pattern: str = ""

    # Anomaly score — higher = more anomalous. Scale is detector-dependent
    # but normalized to [0, 1] by the runner before final ranking.
    score: float = 0.0

    # List of Neo4j element IDs forming the evidence path.
    # Format: ["node:<element_id>", "rel:<element_id>", ...]
    evidence_path: list[str] = field(default_factory=list)

    # Human-readable explanation using ONLY IDs, never names.
    # Example: "Node 4:abc has eigenvector 0.92 but 1-hop mean is 0.03"
    explanation_id_only: str = ""

    # Confidence in [0, 1].  1.0 = structural certainty, <0.5 = heuristic.
    confidence: float = 0.5

    # Timestamp when alert was generated
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Optional metadata bucket for detector-specific extras
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        """Deterministic key for deduplication across runs.

        Based on pattern + sorted evidence path so the same structural
        anomaly doesn't produce duplicate alerts on re-runs.
        """
        content = f"{self.pattern}|{'|'.join(sorted(self.evidence_path))}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
