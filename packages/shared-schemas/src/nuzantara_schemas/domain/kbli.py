"""KBLI (Indonesian Business Classification) domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KBLIEntry(BaseModel):
    """A KBLI business classification entry."""

    kode_kbli: str
    judul: str
    content: str = ""
    sektor_id: str | None = None
    pma_status: str | None = None  # open | restricted | closed
    foreign_ownership_max_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    requirements: list[str] = Field(default_factory=list)
    risk_level: str | None = None  # low | medium | high
