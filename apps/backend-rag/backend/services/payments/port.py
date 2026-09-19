"""Provider-agnostic payment port — owner decision 1 (Xendit, tier (a) only).

`garuda_orders/repository.py` depends on this Protocol, never on a concrete
provider. Tier (a) is the ONLY shape this port needs to express: a small
ticket (<= ~Rp 3jt), card in checkout, the provider fee ABSORBED into the
one all-inclusive `price_idr` — the fee is never a second line, never
returned to the caller, and never persisted as a separate figure (SM-G04 /
`test_the_price_is_one_field_and_never_a_computation`). Tiers (b)/(c) from
DECISIONS.md (VA, deposit+wire) are explicitly out of scope for this port
and MUST NOT be added here — see `products/garuda-voa/DECISIONS.md`
owner decision 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.services.payments.terminal_taxonomy import MappedFailure


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    provider_session_id: str
    checkout_url: str
    expires_at: object  # datetime, kept loosely typed to avoid an import cycle in the Protocol


@dataclass(frozen=True, slots=True)
class NormalizedPaidEvent:
    provider_event_id: str
    provider_charge_id: str
    provider_session_id: str
    amount_idr: int
    currency: str


@dataclass(frozen=True, slots=True)
class NormalizedFailureEvent:
    provider_event_id: str
    provider_session_id: str
    failure: MappedFailure


@dataclass(frozen=True, slots=True)
class NormalizedRefundEvent:
    provider_event_id: str
    provider_refund_id: str
    provider_charge_id: str
    provider_session_id: str


@dataclass(frozen=True, slots=True)
class ChargeConfirmation:
    """What OP-04 reconciliation learned from the PROVIDER about one session.

    `confirmed_unpaid` is deliberately not the negation of "paid": it is true
    only when the provider names a status this adapter positively recognises
    as carrying no accepted charge. A status the adapter does not recognise
    yields `False` — OP-04 then declines to expire the order, because an
    unknown status is not evidence of absence and expiring a paid order is
    the one outcome that costs the customer money.

    `provider_charge_id` matters for the same reason it does on the OP-F05
    webhook path: `resolveLateOrder` has nothing to refund without it, so a
    late case opened from reconciliation must carry it too.
    """

    confirmed_unpaid: bool
    provider_charge_id: str | None = None
    provider_status: str | None = None


class WebhookSignatureInvalid(Exception):
    """Raised by `verify_signature` — maps to OP-F02 (reject before inbox)."""


class WebhookUnparseable(Exception):
    """Raised by `parse_event` for a signed body this adapter cannot read.

    Distinct from `WebhookSignatureInvalid`: the signature is valid (so the
    event IS ours), but the body shape is not one this adapter's contract
    version understands. Maps to a 422, never a silent drop.
    """


class RefundFailed(Exception):
    """Raised by `refund` when the provider could not place the refund.

    The caller (resolveLateOrder) MUST propagate this as a failure and MUST
    NOT record a resolution — per DECISIONS.md/contract: "a refund that
    cannot be placed must fail loudly rather than record a resolution that
    did not happen".
    """


class PaymentProvider(Protocol):
    """Sandbox-only for this build (ASSEMBLY-LINE G5 gauntlet, MANDATE §6).

    No method here ever accepts or returns a live secret key, a raw card
    number, or a fee as a customer-facing figure. `fee_config_is_a_parameter`
    (DECISIONS.md owner decision 1) lives entirely inside the concrete
    adapter's construction — this Protocol never sees it, because the fee
    never crosses the port boundary as data.
    """

    async def create_checkout_session(
        self,
        *,
        order_id: str,
        price_idr: int,
        idempotency_key: str,
    ) -> CheckoutSession:
        """OP-01. `price_idr` is the ONE all-inclusive figure; the fee the
        provider charges Bali Zero is absorbed and never appears here."""
        ...

    def verify_signature(self, *, raw_body: bytes, headers: dict[str, str]) -> None:
        """Raises `WebhookSignatureInvalid` on any failure. Never returns a
        bool — a Protocol that could be misread as "verified=False, continue
        anyway" is exactly the OP-F02 mistake this signature forbids by
        construction."""
        ...

    def parse_event(
        self, *, raw_body: bytes, headers: dict[str, str]
    ) -> NormalizedPaidEvent | NormalizedFailureEvent | NormalizedRefundEvent:
        """Only called after `verify_signature` succeeds. Raises
        `WebhookUnparseable` for a signed body this adapter cannot map."""
        ...

    async def confirm_no_successful_charge(self, *, provider_session_id: str) -> ChargeConfirmation:
        """OP-04 reconciliation: `confirmed_unpaid` is true only when the
        provider itself confirms no accepted charge exists for this session.
        Never inferred from our own clock alone — STATE-MACHINE.md OP-04
        requires "reconciliation confirms no accepted payment", not just
        "time passed".

        An implementation MUST answer from a positive allow-list of statuses
        it recognises as unpaid, never from `status != "PAID"`: the provider
        owns that vocabulary and can extend it, and the failure mode of the
        negated form is to expire an order the customer really paid.
        """
        ...

    async def refund(self, *, provider_charge_id: str, idempotency_key: str) -> str:
        """Places a full refund. Returns the provider's refund id. Raises
        `RefundFailed` rather than returning a falsy value — a refund that
        cannot be placed must fail loudly (resolveLateOrder contract)."""
        ...


__all__ = [
    "ChargeConfirmation",
    "CheckoutSession",
    "NormalizedFailureEvent",
    "NormalizedPaidEvent",
    "NormalizedRefundEvent",
    "PaymentProvider",
    "RefundFailed",
    "WebhookSignatureInvalid",
    "WebhookUnparseable",
]
