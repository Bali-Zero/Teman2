"""Wire-independent shapes for a GARUDA VOA delivered artifact.

Mirrors `garuda_practice_artifacts` (migration 313) exactly -- one dataclass
per row, never a customer- or staff-facing JSON shape (that translation
lives in the routers, same discipline as `PracticeView` /
`_staff_practice_view` in the neighbouring modules).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """One row of `garuda_practice_artifacts`, as written or read.

    `superseded_at is None` means live -- the one row the partial unique
    index (`ux_garuda_practice_artifacts_live`) allows per `practice_id`.
    `superseded_by` is the artifact_id of the row that replaced this one --
    always set together with `superseded_at` (decision #13-revision, DB
    CHECK + guard trigger in migration 313 enforce the pair).
    """

    artifact_id: str
    practice_id: str
    storage_key: str
    artifact_digest: str
    byte_length: int
    content_type: str
    produced_by: str
    environment: str
    created_at: datetime
    retention_until: datetime
    superseded_at: datetime | None = None
    superseded_by: str | None = None

    @property
    def is_live(self) -> bool:
        return self.superseded_at is None
