"""Order aggregate dataclasses — the shape `repository.py` reads/writes.

Kept separate from `state_machine.py` (pure transition logic, no I/O) and
from the OpenAPI-generated wire types (frozen contract, a different
concern): this is the internal row shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_orders.state_machine import OrderState


@dataclass(frozen=True, slots=True)
class Applicant:
    full_name: str
    email: str
    phone: str
    passport_number: str


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    result_id_ref: str
    case_type: CaseType
    applicant: Applicant
    price_idr: int
    price_catalogue_key: str
    state: OrderState
    provider: str
    provider_session_id: str | None
    provider_charge_id: str | None
    checkout_expires_at: datetime | None
    browser_observation: str
    late_case_open: bool
    late_case_resolution: str | None
    created_at: datetime
    updated_at: datetime


__all__ = ["Applicant", "Order"]
