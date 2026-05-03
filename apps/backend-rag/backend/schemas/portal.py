"""Portal API schemas - Pydantic models for request/response validation."""

from datetime import date, datetime

from pydantic import BaseModel


class TaxObligation(BaseModel):
    """Tax obligation record."""

    id: int
    uuid: str
    client_id: int
    tax_type: str  # pph_21, pph_23, pph_4_2, ppn, spt_annual, npwp
    name: str
    frequency: str  # monthly, quarterly, annual, one_time
    period_start: date
    period_end: date
    due_date: date
    status: str  # upcoming, pending, filed, paid, overdue
    amount_due: float | None = None
    amount_paid: float | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class TaxSummary(BaseModel):
    """Tax summary for dashboard card."""

    total_due: float = 0
    next_deadline: date | None = None
    days_until_deadline: int | None = None
    pending_count: int = 0
    overdue_count: int = 0
    status: str = "ok"  # ok, attention, critical


class VisaRecord(BaseModel):
    """Visa record."""

    id: int
    uuid: str
    client_id: int
    visa_type: str  # tourist, business, social, kitas_work, kitas_investor, etc.
    status: str  # none, applied, processing, active, expiring_soon, expired, cancelled
    issue_date: date | None = None
    expiry_date: date | None = None
    visa_number: str | None = None
    sponsor_name: str | None = None
    sponsor_type: str | None = None  # company, individual
    created_at: datetime

    class Config:
        from_attributes = True


class VisaSummary(BaseModel):
    """Visa summary for dashboard card."""

    has_active_visa: bool = False
    visa_type: str | None = None
    expiry_date: date | None = None
    days_until_expiry: int | None = None
    status: str = "none"  # none, active, expiring_soon, expired


class TimelineEvent(BaseModel):
    """Timeline event for Portal dashboard."""

    id: int
    event_type: str  # deadline, milestone, document_request, status_change, reminder, etc.
    title: str
    description: str | None = None
    event_date: datetime
    icon: str | None = None
    color: str = "info"  # info, warning, success, error
    action_url: str | None = None
    action_label: str | None = None

    class Config:
        from_attributes = True
