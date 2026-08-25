"""Xendit sandbox adapter — owner decision 1 (ratified 2026-08-25), tier (a) only.

Tier (a): small tickets (<= ~Rp 3jt), card in checkout, provider fee ABSORBED
into the one all-inclusive `price_idr` (GARUDA VOA: 790.000 / 850.000 IDR).
Never builds tier (b) (deposit+wire) or tier (c) (Virtual Account) — those
are out of scope for this product (DECISIONS.md owner decision 1).

Uses the Xendit Invoices API (sandbox secret key only — never a live key in
this build; ASSEMBLY-LINE G5 gauntlet runs on sandbox exclusively). Webhook
authenticity is Xendit's actual mechanism: a static `x-callback-token`
header compared to our stored verification token, constant-time — NOT an
HMAC signature (Xendit Invoices callbacks carry no body signature). The
`card_fee` handed to `__init__` is configuration (Zero's note: "the card
fee is negotiable at volume") and never crosses the `PaymentProvider` port
as data — see `port.py` module docstring.
"""

from __future__ import annotations

import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

from backend.services.payments.port import (
    CheckoutSession,
    NormalizedFailureEvent,
    NormalizedPaidEvent,
    NormalizedRefundEvent,
    RefundFailed,
    WebhookSignatureInvalid,
    WebhookUnparseable,
)
from backend.services.payments.terminal_taxonomy import (
    FailureOutcome,
    classify,
    map_provider_failure_code,
)

logger = logging.getLogger(__name__)

_SANDBOX_BASE_URL = "https://api.xendit.co"
_CHECKOUT_TTL_MINUTES = 60

# Xendit Invoices `failure_code` -> our closed vocabulary. Deliberately
# NOT exhaustive of Xendit's real catalog: any code not listed here (and
# any code Xendit adds later) falls through `map_provider_failure_code` to
# `UNRECOGNISED_RETRYABLE`, which pages rather than silently terminal-izing
# an unknown code (DECISIONS.md Q8's first required property).
_FAILURE_CODE_MAP: dict[str, FailureOutcome] = {
    "DECLINED_BY_ISSUER": FailureOutcome.DECLINED_BY_ISSUER,
    "INSUFFICIENT_BALANCE": FailureOutcome.INSUFFICIENT_FUNDS,
    "INSUFFICIENT_FUNDS": FailureOutcome.INSUFFICIENT_FUNDS,
    "AUTHENTICATION_FAILED": FailureOutcome.AUTHENTICATION_FAILED,
    "PROCESSOR_ERROR": FailureOutcome.PROVIDER_UNAVAILABLE,
    "SERVER_ERROR": FailureOutcome.PROVIDER_UNAVAILABLE,
    "EXPIRED_INVOICE": FailureOutcome.EXPIRED,
    "INVOICE_EXPIRED": FailureOutcome.EXPIRED,
}


@dataclass(frozen=True, slots=True)
class XenditFeeConfig:
    """Configuration, never a constant baked into logic (owner decision 1).

    The fee is Bali Zero's cost of accepting the card, already absorbed
    into `price_idr` upstream (GARUDA VOA pricing) — this dataclass exists
    so operations can change the negotiated rate without touching code, and
    it is deliberately never read by anything that builds a customer-facing
    response (SM-G04 forbids a fee/PNBP component on the wire).
    """

    percentage_bps: int  # e.g. 350 == 3.5%
    fixed_idr: int  # e.g. 6000 == Rp 6.000


class XenditPaymentProvider:
    """Implements `payments.port.PaymentProvider` against Xendit sandbox."""

    def __init__(
        self,
        *,
        secret_key: str,
        callback_verification_token: str,
        public_base_url: str,
        fee_config: XenditFeeConfig,
        client: httpx.AsyncClient,
        base_url: str = _SANDBOX_BASE_URL,
    ) -> None:
        if not secret_key.startswith("xnd_development_"):
            # Fail closed rather than risk a live key reaching this sandbox
            # adapter — ASSEMBLY-LINE G5 forbids a real charge in this build.
            raise ValueError(
                "XenditPaymentProvider requires a sandbox (xnd_development_) secret key"
            )
        self._secret_key = secret_key
        self._callback_verification_token = callback_verification_token
        # `public_base_url` is the ONE thing this adapter needs to reach the
        # frontend -- NOT two static success/failure URLs (Dissent #3,
        # 2026-08-25 review of PR #4920). A static URL cannot carry the
        # per-order `orderId` the return route requires, and the product's
        # own contract forbids a success/failure split anyway: the browser
        # return is an OBSERVATION, never a truth
        # (`apps/mouth/.../orders/[orderId]/return/page.tsx` docstring), so
        # there is deliberately ONE return route regardless of outcome. The
        # per-invoice URL (order id + a freshly minted, opaque nonce) is
        # built in `create_checkout_session` below, where `order_id` is
        # actually known.
        self._public_base_url = public_base_url.rstrip("/")
        self._fee_config = (
            fee_config  # kept for operator visibility only; never read by mapping code
        )
        self._client = client
        self._base_url = base_url

    async def create_checkout_session(
        self,
        *,
        order_id: str,
        price_idr: int,
        idempotency_key: str,
    ) -> CheckoutSession:
        if price_idr <= 0:
            raise ValueError("price_idr must be a positive all-inclusive integer")
        expires_at = datetime.now(UTC) + timedelta(minutes=_CHECKOUT_TTL_MINUTES)
        # One nonce, one route, regardless of outcome (see __init__ docstring
        # note above). Minting it here does not create a second source of
        # truth: `record_browser_return_observation` (repository.py OP-07)
        # accepts and stores whatever nonce the browser echoes back on its
        # FIRST write for this order_id -- there is no earlier value it must
        # match. `secrets.token_urlsafe` is opaque and carries no PII.
        return_nonce = secrets.token_urlsafe(32)
        return_url = (
            f"{self._public_base_url}/visa/voa/orders/{quote(order_id, safe='')}"
            f"/return?return_nonce={quote(return_nonce, safe='')}"
        )
        response = await self._client.post(
            f"{self._base_url}/v2/invoices",
            auth=(self._secret_key, ""),
            headers={"Idempotency-Key": idempotency_key},
            json={
                "external_id": order_id,
                "amount": price_idr,
                "currency": "IDR",
                "invoice_duration": _CHECKOUT_TTL_MINUTES * 60,
                "success_redirect_url": return_url,
                "failure_redirect_url": return_url,
                "payment_methods": ["CREDIT_CARD"],
            },
        )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        return CheckoutSession(
            provider_session_id=str(body["id"]),
            checkout_url=str(body["invoice_url"]),
            expires_at=expires_at,
        )

    def verify_signature(self, *, raw_body: bytes, headers: dict[str, str]) -> None:
        # Xendit Invoices callbacks are authenticated by a static verification
        # token in `x-callback-token`, not a body HMAC. Header lookup is
        # case-insensitive per HTTP; callers pass a dict already normalized
        # by the web framework, but we defend here too.
        received = None
        for key, value in headers.items():
            if key.lower() == "x-callback-token":
                received = value
                break
        if not received or not hmac.compare_digest(received, self._callback_verification_token):
            raise WebhookSignatureInvalid("x-callback-token missing or mismatched")

    def parse_event(
        self, *, raw_body: bytes, headers: dict[str, str]
    ) -> NormalizedPaidEvent | NormalizedFailureEvent | NormalizedRefundEvent:
        import json

        try:
            body: dict[str, Any] = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise WebhookUnparseable("callback body is not valid JSON") from exc

        event_id = body.get("id")
        session_id = body.get("id")  # Xendit Invoices reuse the invoice id as external correlation
        status = body.get("status")
        if not isinstance(event_id, str) or not event_id:
            raise WebhookUnparseable("callback body missing invoice id")

        if status == "PAID":
            charge_id = body.get("payment_id") or body.get("id")
            amount = body.get("paid_amount") or body.get("amount")
            currency = body.get("currency", "IDR")
            if not isinstance(amount, int | float):
                raise WebhookUnparseable("PAID callback missing a numeric amount")
            return NormalizedPaidEvent(
                provider_event_id=str(event_id),
                provider_charge_id=str(charge_id),
                provider_session_id=str(session_id),
                amount_idr=int(amount),
                currency=str(currency),
            )
        if status in ("EXPIRED", "FAILED"):
            raw_code = body.get("failure_code")
            # CORRECTED (refuter finding, minor): a real Xendit EXPIRED
            # callback typically carries no `failure_code` at all -- routing
            # it through map_provider_failure_code(None, ...) landed on
            # UNRECOGNISED_RETRYABLE and paged staff for a routine checkout
            # expiry. `status == "EXPIRED"` already tells us the outcome
            # unambiguously (unless Xendit explicitly names a different
            # failure_code, e.g. one of the two EXPIRED aliases in the
            # table); map it directly instead of through the "code missing"
            # branch of the generic lookup.
            if status == "EXPIRED" and not raw_code:
                mapped = classify(FailureOutcome.EXPIRED)
            else:
                mapped = map_provider_failure_code("xendit", raw_code, _FAILURE_CODE_MAP)
            return NormalizedFailureEvent(
                provider_event_id=str(event_id),
                provider_session_id=str(session_id),
                failure=mapped,
            )
        if status == "REFUNDED" or "refund" in body:
            refund_id = body.get("refund_id") or f"{event_id}-refund"
            charge_id = body.get("payment_id") or body.get("id")
            return NormalizedRefundEvent(
                provider_event_id=str(event_id),
                provider_refund_id=str(refund_id),
                provider_charge_id=str(charge_id),
                provider_session_id=str(session_id),
            )
        raise WebhookUnparseable(f"unrecognised Xendit invoice status: {status!r}")

    async def confirm_no_successful_charge(self, *, provider_session_id: str) -> bool:
        response = await self._client.get(
            f"{self._base_url}/v2/invoices/{provider_session_id}",
            auth=(self._secret_key, ""),
        )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        return body.get("status") != "PAID"

    async def refund(self, *, provider_charge_id: str, idempotency_key: str) -> str:
        try:
            response = await self._client.post(
                f"{self._base_url}/refunds",
                auth=(self._secret_key, ""),
                headers={"Idempotency-Key": idempotency_key},
                json={"invoice_id": provider_charge_id, "reason": "OTHERS"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RefundFailed(f"Xendit refund failed for charge {provider_charge_id}") from exc
        body: dict[str, Any] = response.json()
        refund_id = body.get("id")
        if not isinstance(refund_id, str) or not refund_id:
            raise RefundFailed("Xendit refund response missing an id")
        return refund_id


__all__ = ["XenditFeeConfig", "XenditPaymentProvider"]
