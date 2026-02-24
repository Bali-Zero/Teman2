"""Tax domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TaxType(StrEnum):
    PPH_21 = "pph_21"
    PPH_23 = "pph_23"
    PPH_25 = "pph_25"
    PPH_FINAL = "pph_final"
    PPN = "ppn"
    BPHTB = "bphtb"
    PBB = "pbb"


class TaxBracket(BaseModel):
    """A single tax bracket."""

    min_idr: int
    max_idr: int | None = None
    rate_pct: float = Field(ge=0.0, le=100.0)


class TaxInfo(BaseModel):
    """Structured tax information."""

    tax_type: TaxType
    rate_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    brackets: list[TaxBracket] = Field(default_factory=list)
    applicable_to_foreigners: bool = True
    filing_frequency: str | None = None  # monthly | quarterly | annual
    exemptions: list[str] = Field(default_factory=list)
    penalties: list[str] = Field(default_factory=list)
