"""Property/land rights domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PropertyRight(StrEnum):
    HAK_PAKAI = "hak_pakai"
    HGB = "hgb"
    HAK_MILIK = "hak_milik"
    STRATA_TITLE = "strata_title"
    LEASEHOLD = "leasehold"


class PropertyInfo(BaseModel):
    """Structured property/land rights information."""

    right_type: PropertyRight
    foreigner_eligible: bool = False
    duration_years: int | None = None
    renewable: bool = False
    max_renewals: int | None = None
    requires_pt: bool = False
    min_value_idr: int | None = None
    restrictions: list[str] = Field(default_factory=list)
    zones: list[str] = Field(default_factory=list)
