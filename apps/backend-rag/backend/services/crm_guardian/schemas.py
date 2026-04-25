"""L1 semantic summary schemas for CRM-Guardian.

Schema v1.0 — produced by Gemini 3 Pro via Panel Side on drive.google.com,
parsed and validated at worker boundary before writing to clients.ai_summary
(JSONB). Pydantic guarantees downstream consumers (AI Profile Card, alerts,
NB-CRM brief generator) can trust the shape.

Bumping schema_version: any change to field names/types that is NOT
backward-compatible requires a new migration to add the new version to
crm_guardian_summary_queue.schema_version default and a new prompt file
under prompts/crm_guardian/.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "v1.0"


class Identity(BaseModel):
    """Core identity — passport is the authoritative PK across systems."""
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    date_of_birth: date | None = None
    birthplace: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    passport_expires_at: date | None = None
    npwp_personal: str | None = None


class VisaStatus(BaseModel):
    """Current Indonesian immigration status."""
    model_config = ConfigDict(extra="forbid")

    visa_type: str | None = Field(default=None, description="E28A, C1, D12, KITAS, KITAP, …")
    stay_permit_number: str | None = None
    issued_at: date | None = None
    valid_until: date | None = None
    sponsor_company: str | None = None
    multiple_entry: bool | None = None


class Company(BaseModel):
    """Indonesian legal entity (PT PMA, CV, Perseroan)."""
    model_config = ConfigDict(extra="forbid")

    legal_name: str | None = None
    legal_form: Literal["PT_PMA", "PT", "CV", "Perseroan", "Foundation", "Other"] | None = None
    nib: str | None = Field(default=None, description="Nomor Induk Berusaha")
    npwp_corporate: str | None = None
    akta_number: str | None = None
    akta_date: date | None = None
    sk_kemenkumham: str | None = None
    kbli_codes: list[str] = Field(default_factory=list)
    kbli_primary: str | None = None
    paid_up_capital_idr: int | None = None
    authorized_capital_idr: int | None = None
    registered_address: str | None = None


class Shareholder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    percentage: float | None = None
    role: Literal["Director", "Commissioner", "Shareholder", "Founder"] | None = None
    nationality: str | None = None

    @field_validator("percentage")
    @classmethod
    def _pct_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError(f"percentage must be in [0,100], got {v}")
        return v


class PropertyAsset(BaseModel):
    """Real estate / villa / lease — Bali-specific."""
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    address: str | None = None
    tenure: Literal["Hak_Milik", "Hak_Pakai", "HGB", "Lease", "Other"] | None = None
    pbg_status: str | None = None
    lease_expires_at: date | None = None


class DocumentRef(BaseModel):
    """Reference to a source file inside the client's canonical folder."""
    model_config = ConfigDict(extra="forbid")

    file_id: str
    file_name: str
    doc_type: str = Field(description="akta, nib, npwp, passport, visa, evisa, bukti_mutasi, statement, sk, other")
    issued_at: date | None = None
    expires_at: date | None = None
    subject_entity: str | None = None
    key_fields: dict[str, str] = Field(default_factory=dict)


class Timeline(BaseModel):
    """Chronological milestones extracted from documents."""
    model_config = ConfigDict(extra="forbid")

    event_date: date
    event_type: str
    description: str
    source_file_id: str | None = None


class Compliance(BaseModel):
    """Compliance signals (LKPM, SPT, BPJS, expiries)."""
    model_config = ConfigDict(extra="forbid")

    lkpm_last_reported: date | None = None
    lkpm_next_due: date | None = None
    spt_tahunan_last: date | None = None
    bpjs_enrolled: bool | None = None
    passport_days_until_expiry: int | None = None
    visa_days_until_expiry: int | None = None
    red_flags: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    """Top-level tiering and archetype (used for routing + AI Profile Card)."""
    model_config = ConfigDict(extra="forbid")

    archetype: Literal[
        "individual_expat",
        "individual_investor",
        "pt_pma_owner",
        "family_member",
        "property_holder",
        "business_only",
        "other",
    ] = "other"
    tier: Literal["VIP", "standard", "archive", "unknown"] = "unknown"
    primary_service: Literal[
        "visa_immigration",
        "company_setup",
        "tax",
        "property",
        "hr_payroll",
        "mixed",
        "unknown",
    ] = "unknown"
    rationale: str | None = Field(
        default=None,
        description="One-sentence explanation of archetype+tier choice (for audit).",
    )


class L1ClientSummary(BaseModel):
    """Root L1 summary written to clients.ai_summary JSONB.

    Every field is optional at runtime (Gemini may fail to extract) but the
    SHAPE is enforced: downstream code can `.profile.archetype` without
    defensive `.get()` chains.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    client_id: int
    generated_at: str = Field(description="ISO-8601 UTC timestamp from worker.")
    source_folder_id: str
    source_file_count: int
    source_file_fingerprint: str = Field(
        description="SHA256 of sorted (file_id, modifiedTime) — matches ai_summary_file_hash.",
    )
    prompt_version: str = "L1_extraction_v1"

    # Core semantic layers (all optional — nullable Gemini extraction)
    identity: Identity = Field(default_factory=Identity)
    visa: VisaStatus = Field(default_factory=VisaStatus)
    company: Company = Field(default_factory=Company)
    shareholders: list[Shareholder] = Field(default_factory=list)
    properties: list[PropertyAsset] = Field(default_factory=list)
    documents: list[DocumentRef] = Field(default_factory=list)
    timeline: list[Timeline] = Field(default_factory=list)
    compliance: Compliance = Field(default_factory=Compliance)
    profile: Profile = Field(default_factory=Profile)

    # Free-form narrative layer (for NB-CRM brief + AI Profile Card "About")
    narrative_en: str | None = Field(
        default=None, description="1-2 paragraph English narrative for brief/card.",
    )
    narrative_id: str | None = Field(
        default=None, description="1-2 paragraph Bahasa Indonesia narrative (optional).",
    )

    # Extraction quality self-report from Gemini
    extraction_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Gemini self-reported confidence (0-1). Below 0.6 flags manual review.",
    )
    extraction_notes: list[str] = Field(
        default_factory=list,
        description="Things Gemini couldn't determine (e.g. 'shareholder percentages inconsistent').",
    )


__all__ = [
    "SCHEMA_VERSION",
    "L1ClientSummary",
    "Identity",
    "VisaStatus",
    "Company",
    "Shareholder",
    "PropertyAsset",
    "DocumentRef",
    "Timeline",
    "Compliance",
    "Profile",
]
