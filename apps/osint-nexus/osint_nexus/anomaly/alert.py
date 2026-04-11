"""Alert dataclass — the unit of output from every detector.

OPSEC-critical design notes
---------------------------
1. ``primary_entity_id`` MUST be an opaque stable identifier — either a
   Neo4j element_id string or a sha256-derived ID. It MUST NOT be a
   human-readable name. Detectors SHOULD NOT carry ``n.name`` into
   Cypher RETURN clauses.
2. ``evidence_path`` is a list of the same kind of IDs. No names here
   either. Resolution to human-readable data is done in a separate
   offline step that only Zero has access to.
3. ``alert_id`` is a hash of ``pattern + primary_entity_id + day_bucket``
   so re-running the same day yields the same id → dedupe is trivial.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any


def make_alert_id(pattern: str, primary_entity_id: str, day_bucket: str | None = None) -> str:
    """Deterministic 16-char alert id.

    Day bucket ensures two alerts raised on different days are treated
    as distinct events. Same-day re-runs collapse to the same ID.
    """
    if day_bucket is None:
        day_bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = f"{pattern}|{primary_entity_id}|{day_bucket}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


@dataclass(frozen=True)
class Alert:
    """Frozen anomaly alert. Names NEVER appear in any field."""

    alert_id: str
    pattern: str
    primary_entity_id: str
    score: float
    confidence: float
    evidence_path: list[str] = field(default_factory=list)
    rationale_id: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict. evidence_path copied so callers can't mutate."""
        d = asdict(self)
        d["evidence_path"] = list(self.evidence_path)
        return d

    def clamp(self) -> "Alert":
        """Return a copy with score/confidence bounded to [0, 1]."""
        new_score = max(0.0, min(1.0, self.score))
        new_conf = max(0.0, min(1.0, self.confidence))
        if new_score == self.score and new_conf == self.confidence:
            return self
        return replace(self, score=new_score, confidence=new_conf)
