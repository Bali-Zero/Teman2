"""Visa/immigration domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class VisaType(StrEnum):
    KITAS = "kitas"
    KITAP = "kitap"
    B211A = "b211a"
    E_VISA = "e_visa"
    VOA = "voa"
    SECOND_HOME = "second_home"


class VisaInfo(BaseModel):
    """Structured visa/immigration information."""

    visa_type: VisaType
    sponsor_required: bool = False
    duration_months: int | None = None
    extendable: bool = False
    max_extensions: int | None = None
    requirements: list[str] = Field(default_factory=list)
    costs_usd: dict[str, float] = Field(default_factory=dict)
    processing_days: int | None = None
    work_permit_included: bool = False
