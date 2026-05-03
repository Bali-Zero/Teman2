"""Company/business entity domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class CompanyType(StrEnum):
    PT_PMA = "pt_pma"
    PT_PMDN = "pt_pmdn"
    CV = "cv"
    FIRMA = "firma"
    KOPERASI = "koperasi"
    YAYASAN = "yayasan"


class CompanyInfo(BaseModel):
    """Structured company/business setup information."""

    company_type: CompanyType
    name: str | None = None
    kbli_codes: list[str] = Field(default_factory=list)
    min_capital_idr: int | None = None
    min_investment_usd: int | None = None
    foreign_ownership_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    requirements: list[str] = Field(default_factory=list)
    timeline_days: int | None = None
    is_pma_eligible: bool | None = None
