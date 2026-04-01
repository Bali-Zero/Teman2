"""
LKPM (Investment Activity Report) Pydantic Models.

All calculations are deterministic — no AI on numbers.
Models follow flat payload pattern (no nesting in DB schema).
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, computed_field, field_validator


class LKPMStatus(str, Enum):
    """LKPM report lifecycle status."""

    DRAFT = "draft"
    VALIDATED = "validated"
    CLIENT_REVIEW = "client_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    ARCHIVED = "archived"


class ValidationSeverity(str, Enum):
    """Validation alert severity levels."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class DataSource(str, Enum):
    """How the LKPM data was collected."""

    MANUAL = "manual"
    JURNAL = "jurnal"
    MIXED = "mixed"


class InvestmentRealization(BaseModel):
    """Investment realization for a single quarter (6 categories)."""

    equipment_domestic: int = 0
    equipment_import: int = 0
    building_domestic: int = 0
    building_import: int = 0
    vehicle_domestic: int = 0
    vehicle_import: int = 0
    land: int = 0
    working_capital: int = 0
    other: int = 0

    @computed_field
    @property
    def total_domestic(self) -> int:
        return (
            self.equipment_domestic
            + self.building_domestic
            + self.vehicle_domestic
            + self.land
            + self.working_capital
            + self.other
        )

    @computed_field
    @property
    def total_import(self) -> int:
        return self.equipment_import + self.building_import + self.vehicle_import

    @computed_field
    @property
    def grand_total(self) -> int:
        return self.total_domestic + self.total_import

    @field_validator("*", mode="before")
    @classmethod
    def ensure_non_negative(cls, v: Any) -> Any:
        if isinstance(v, int) and v < 0:
            raise ValueError("Investment amounts cannot be negative")
        return v


class EmploymentData(BaseModel):
    """Employment data for LKPM reporting."""

    tki: int = 0  # Tenaga Kerja Indonesia (local workers)
    tka: int = 0  # Tenaga Kerja Asing (foreign workers)

    @computed_field
    @property
    def total(self) -> int:
        return self.tki + self.tka

    @field_validator("tki", "tka", mode="before")
    @classmethod
    def ensure_non_negative(cls, v: Any) -> Any:
        if isinstance(v, int) and v < 0:
            raise ValueError("Employee count cannot be negative")
        return v


class ValidationAlert(BaseModel):
    """A single validation finding."""

    field: str
    severity: ValidationSeverity
    message: str
    details: str | None = None


class LKPMValidationResult(BaseModel):
    """Result of LKPM draft validation."""

    is_valid: bool
    alerts: list[ValidationAlert] = []
    red_count: int = 0
    yellow_count: int = 0
    green_count: int = 0
    validated_at: datetime | None = None


class LKPMDraft(BaseModel):
    """Complete LKPM draft for a single quarter."""

    id: int | None = None
    client_id: int
    quarter: str  # "Q1", "Q2", "Q3", "Q4"
    year: int
    status: LKPMStatus = LKPMStatus.DRAFT

    # Investment realization (this quarter)
    realized: InvestmentRealization = InvestmentRealization()

    # Cumulative realization (all quarters to date)
    cumulative: InvestmentRealization = InvestmentRealization()

    # Employment
    employment: EmploymentData = EmploymentData()

    # Revenue
    quarterly_revenue: int = 0
    annual_revenue: int = 0

    # Narrative (template-based, not AI-generated)
    narrative_obstacles: str | None = None
    narrative_plans: str | None = None

    # Validation
    validation: LKPMValidationResult | None = None

    # Client approval
    client_approved: bool = False
    client_approved_at: datetime | None = None

    # OSS submission
    oss_submitted: bool = False
    oss_submitted_at: datetime | None = None
    oss_receipt_number: str | None = None

    # Data source
    data_source: DataSource = DataSource.MANUAL
    has_ai_categorized_items: bool = False
    ai_categorized_count: int = 0

    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("quarter")
    @classmethod
    def validate_quarter(cls, v: str) -> str:
        if v not in {"Q1", "Q2", "Q3", "Q4"}:
            raise ValueError("quarter must be Q1, Q2, Q3, or Q4")
        return v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if v < 2020 or v > 2100:
            raise ValueError("year must be between 2020 and 2100")
        return v


class LKPMClientConfig(BaseModel):
    """Client configuration for LKPM reporting."""

    client_id: int
    company_name: str
    npwp: str | None = None
    nib: str | None = None
    kbli_codes: list[str] = []

    # Investment plan from BKPM approval
    planned: InvestmentRealization = InvestmentRealization()

    # Employment plan
    planned_tki: int = 0
    planned_tka: int = 0

    # Jurnal.id integration
    jurnal_api_key: str | None = None
    jurnal_company_id: str | None = None

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("company_name cannot be empty")
        return v


class LKPMClientSubmission(BaseModel):
    """Data submitted by client via form."""

    client_id: int
    quarter: str
    year: int

    # Investment data (flat, no nesting)
    equipment_domestic: int = 0
    equipment_import: int = 0
    building_domestic: int = 0
    building_import: int = 0
    vehicle_domestic: int = 0
    vehicle_import: int = 0
    land: int = 0
    working_capital: int = 0
    other: int = 0

    # Employment
    tki: int = 0
    tka: int = 0

    # Revenue
    quarterly_revenue: int = 0
    annual_revenue: int = 0

    # Narrative
    narrative_obstacles: str | None = None
    narrative_plans: str | None = None

    @field_validator("quarter")
    @classmethod
    def validate_quarter(cls, v: str) -> str:
        if v not in {"Q1", "Q2", "Q3", "Q4"}:
            raise ValueError("quarter must be Q1, Q2, Q3, or Q4")
        return v


class LKPMReadyPack(BaseModel):
    """OSS-ready output for copy-paste submission."""

    draft_id: int
    client_id: int
    company_name: str
    npwp: str | None = None
    nib: str | None = None
    quarter: str
    year: int

    # KBLI codes registered
    kbli_codes: list[str] = []

    # Investment realization (this quarter) — formatted for OSS
    realized: InvestmentRealization
    realized_total: int = 0

    # Cumulative realization — formatted for OSS
    cumulative: InvestmentRealization
    cumulative_total: int = 0

    # Plan vs realization percentages
    plan: InvestmentRealization
    realization_percentage: float = 0.0

    # Employment
    employment: EmploymentData

    # Revenue
    quarterly_revenue: int = 0
    annual_revenue: int = 0

    # Narrative
    narrative_obstacles: str | None = None
    narrative_plans: str | None = None

    # Validation summary
    validation_summary: LKPMValidationResult | None = None

    # Ready pack metadata
    generated_at: datetime | None = None
    html_content: str | None = None


class LKPMBatchItem(BaseModel):
    """Summary of one LKPM report in a batch listing."""

    id: int
    client_id: int
    company_name: str
    quarter: str
    year: int
    status: LKPMStatus
    validation_status: str = "pending"
    realized_total: int = 0
    red_alerts: int = 0
    yellow_alerts: int = 0
    oss_submitted: bool = False
    oss_receipt_number: str | None = None
    updated_at: datetime | None = None


class LKPMDeadline(BaseModel):
    """LKPM submission deadline info."""

    quarter: str
    year: int
    deadline: datetime
    days_remaining: int
    is_overdue: bool = False


class TransactionCategorization(BaseModel):
    """Result of categorizing a financial transaction into LKPM categories."""

    journal_entry_id: str
    description: str
    amount: int
    category: str  # equipment, building, vehicle, land, working_capital, other
    sub_category: str  # domestic, import (where applicable)
    confidence: str  # "deterministic" or "ai_suggested"
    ai_needs_review: bool = False
    original_account_code: str | None = None
    original_account_name: str | None = None
