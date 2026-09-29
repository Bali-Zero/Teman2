"""Public, stateless tax-calendar projection over the compliance catalog."""

from datetime import date, datetime
from functools import lru_cache
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.services.compliance.obligations_register import (
    ClientProfile,
    ObligationRule,
    applies,
    due_dates,
    load_catalog,
)
from backend.services.compliance.tax_calendar_public_review import (
    PublicReview,
    is_publicly_cleared,
    load_public_reviews,
)

router = APIRouter(prefix="/api/public/tax-calendar", tags=["tax-calendar"])
WITA = ZoneInfo("Asia/Makassar")


def get_tax_calendar_today() -> date:
    """Civil date used for public deadlines; override this dependency in tests."""
    return datetime.now(WITA).date()


class TaxCalendarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxpayer_type: Literal["individual", "company"]
    company_type: (
        Literal["PT_PMA", "PT_PMDN", "CV", "KP3A", "KPPA", "FOREIGN_PLATFORM", "OTHER"] | None
    ) = None
    has_employees: bool = False
    employee_count: int = Field(0, ge=0)
    has_foreign_employees: bool = False
    pkp: bool = False
    serves_indonesian_users_online: bool = False
    pse_registered: bool = False
    pmse_vat_appointed: bool = False
    investment_stage: Literal["construction", "commercial"] | None = None
    fiscal_year_end: str = Field("12-31", pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
    horizon_days: int = Field(365, ge=1, le=400)

    @field_validator("fiscal_year_end")
    @classmethod
    def _fiscal_year_end_is_a_calendar_day(cls, value: str) -> str:
        month, day = (int(part) for part in value.split("-"))
        try:
            date(2024, month, day)  # leap year: 02-29 is a real fiscal year end
        except ValueError as exc:
            raise ValueError("fiscal_year_end must be a real calendar day (MM-DD)") from exc
        return value


class UpcomingDueDate(BaseModel):
    due_date: date
    period_key: str


class TaxCalendarObligation(BaseModel):
    id: str
    name: str
    authority: str
    legal_source: str
    frequency: str
    reviewed_on: date
    upcoming_due_dates: list[UpcomingDueDate]


class TaxCalendarResponse(BaseModel):
    obligations: list[TaxCalendarObligation]
    withheld_count: int


@lru_cache(maxsize=1)
def _catalog() -> tuple[ObligationRule, ...]:
    return tuple(load_catalog())


@lru_cache(maxsize=1)
def _public_reviews() -> dict[str, PublicReview]:
    return load_public_reviews()


def get_public_reviews() -> dict[str, PublicReview]:
    """Reviewer clearances; override this dependency in tests."""
    return _public_reviews()


def _profile(body: TaxCalendarRequest) -> ClientProfile:
    if body.taxpayer_type == "individual":
        # The register has no INDIVIDUAL company_type. OTHER is a valid inert
        # carrier; _applicable below excludes company-scoped predicates.
        return ClientProfile(company_type="OTHER", fiscal_year_end=body.fiscal_year_end)
    return ClientProfile(
        company_type=body.company_type or "OTHER",
        has_employees=body.has_employees,
        employee_count=body.employee_count,
        has_foreign_employees=body.has_foreign_employees,
        pkp=body.pkp,
        investment_stage=body.investment_stage,
        fiscal_year_end=body.fiscal_year_end,
        serves_indonesian_users_online=body.serves_indonesian_users_online,
        pse_registered=body.pse_registered,
        pmse_vat_appointed=body.pmse_vat_appointed,
    )


def _applicable(rule: ObligationRule, profile: ClientProfile, taxpayer_type: str) -> bool:
    """Keep individual profiles out of rules explicitly scoped to a company type."""
    return applies(rule, profile) and (
        taxpayer_type == "company" or not any(p.attr == "company_type" for p in rule.applies_if)
    )


@router.post(
    "/obligations", response_model=TaxCalendarResponse, operation_id="publicTaxCalendarObligations"
)
async def public_tax_calendar_obligations(
    body: TaxCalendarRequest,
    today: Annotated[date, Depends(get_tax_calendar_today)],
    reviews: Annotated[dict[str, PublicReview], Depends(get_public_reviews)],
) -> TaxCalendarResponse:
    profile = _profile(body)
    obligations: list[TaxCalendarObligation] = []
    withheld = 0
    for rule in _catalog():
        if not _applicable(rule, profile, body.taxpayer_type):
            continue
        if not is_publicly_cleared(rule, reviews):
            withheld += 1
            continue
        upcoming = [
            UpcomingDueDate(period_key=key, due_date=due)
            for key, due in due_dates(rule, profile, today, body.horizon_days)
        ]
        obligations.append(
            TaxCalendarObligation(
                id=rule.id,
                name=rule.name,
                authority=rule.authority,
                legal_source=rule.legal_source,
                frequency=rule.due.frequency,
                reviewed_on=reviews[rule.id].reviewed_on,
                upcoming_due_dates=upcoming,
            )
        )
    return TaxCalendarResponse(obligations=obligations, withheld_count=withheld)
