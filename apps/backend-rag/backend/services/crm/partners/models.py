from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

EntityType = Literal["individual", "corporate_pt", "corporate_cv", "foreign"]
WithholdingCategory = Literal["pph21", "pph23", "exempt", "tbd"]
CommissionType = Literal["percentage", "flat"]
OnboardingStatus = Literal["pending_approval", "active", "inactive"]
CommissionStatus = Literal[
    "accrued", "approved", "paid",
    "clawback_pending", "offset_applied",
    "waived", "repaid",
]
CommissionEntryType = Literal["accrual", "clawback", "manual_adjustment"]
RuleSource = Literal["partner_default", "manual_override"]


@dataclass
class Partner:
    id: UUID
    full_name: str
    email: str
    entity_type: EntityType
    tax_withholding_category: WithholdingCategory
    default_commission_type: CommissionType
    default_commission_value: Decimal
    onboarding_status: OnboardingStatus
    payment_currency: str
    preferred_language: str
    created_at: datetime
    updated_at: datetime

    # optional fields
    work_role: str | None = None
    company_name: str | None = None
    office_address: str | None = None
    phone: str | None = None
    npwp: str | None = None
    nik: str | None = None
    fiscal_address: str | None = None
    bank_name: str | None = None
    bank_account_holder: str | None = None
    bank_account_number: str | None = None
    ewallet_type: str | None = None
    ewallet_number: str | None = None
    iban: str | None = None
    payment_notes: str | None = None
    assigned_to: UUID | None = None
    pdp_consent_at: datetime | None = None
    pdp_consent_version: str | None = None
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None
    created_by: UUID | None = None
    deactivated_at: datetime | None = None
    welcome_email_sent_at: datetime | None = None


@dataclass
class PartnerReferral:
    id: UUID
    partner_id: UUID
    practice_id: UUID
    share_percent: Decimal
    referred_at: datetime
    referred_by_user_id: UUID | None = None
    notes: str | None = None


@dataclass
class PartnerCommission:
    id: UUID
    partner_id: UUID
    entry_type: CommissionEntryType
    base_amount_idr: Decimal
    commission_type_snapshot: CommissionType
    commission_value_snapshot: Decimal
    rule_source: RuleSource
    gross_amount_idr: Decimal
    withholding_category: WithholdingCategory
    withholding_rate: Decimal
    withholding_amount_idr: Decimal
    net_amount_idr: Decimal
    status: CommissionStatus
    accrued_at: datetime
    eligible_for_approval_at: datetime
    created_at: datetime

    referral_id: UUID | None = None
    practice_id: UUID | None = None
    related_commission_id: UUID | None = None
    assigned_to_snapshot: UUID | None = None
    approved_at: datetime | None = None
    approved_by: UUID | None = None
    paid_at: datetime | None = None
    paid_by: UUID | None = None
    paid_via: str | None = None
    payment_reference: str | None = None
    payment_proof_url: str | None = None
    receipt_type: Literal["kwitansi", "invoice", "none"] | None = None
    receipt_file_url: str | None = None
    manual_override_reason: str | None = None
    clawback_reason: str | None = None
    waiver_reason: str | None = None
    idempotency_key: str | None = None
    commission_email_sent_at: datetime | None = None


@dataclass
class PartnerAuditLogEntry:
    id: UUID
    partner_id: UUID
    action: str
    at: datetime
    actor_user_id: UUID | None = None
    before_json: dict | None = None
    after_json: dict | None = None
    reason: str | None = None
