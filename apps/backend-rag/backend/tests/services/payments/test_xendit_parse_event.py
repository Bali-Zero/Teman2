"""Refuter finding (minor, Kimi K3 review of commit e1a0f708a): a real
Xendit EXPIRED invoice callback typically carries no `failure_code` at
all. Routing that through map_provider_failure_code(None, ...) landed on
UNRECOGNISED_RETRYABLE and paged staff for a routine checkout expiry
instead of classifying it as the closed, non-retryable EXPIRED outcome.
"""

from __future__ import annotations

import json

import httpx
import pytest

from backend.services.payments.port import (
    NormalizedFailureEvent,
    NormalizedPaidEvent,
    NormalizedRefundEvent,
    RefundFailed,
)
from backend.services.payments.terminal_taxonomy import CustomerAction, FailureOutcome
from backend.services.payments.xendit import XenditFeeConfig, XenditPaymentProvider


@pytest.fixture
def provider() -> XenditPaymentProvider:
    return XenditPaymentProvider(
        secret_key="xnd_development_fake_key_for_tests",
        callback_verification_token="fake-token",
        public_base_url="https://example.com",
        fee_config=XenditFeeConfig(percentage_bps=350, fixed_idr=6000),
        client=httpx.AsyncClient(),
    )


def test_bare_expired_status_with_no_failure_code_is_classified_expired_not_retryable(
    provider: XenditPaymentProvider,
) -> None:
    body = {
        "id": "inv-bare-expired-1",
        "status": "EXPIRED",
        # deliberately NO "failure_code" key -- this is the real-world shape
    }
    event = provider.parse_event(raw_body=json.dumps(body).encode(), headers={})
    assert isinstance(event, NormalizedFailureEvent)
    assert event.failure.outcome is FailureOutcome.EXPIRED
    assert event.failure.retryable is False
    assert event.failure.should_page is False
    assert event.failure.customer_action is CustomerAction.NONE_ORDER_CLOSED


def test_expired_status_with_an_explicit_failure_code_still_uses_the_table(
    provider: XenditPaymentProvider,
) -> None:
    body = {
        "id": "inv-explicit-expired-1",
        "status": "EXPIRED",
        "failure_code": "EXPIRED_INVOICE",
    }
    event = provider.parse_event(raw_body=json.dumps(body).encode(), headers={})
    assert isinstance(event, NormalizedFailureEvent)
    assert event.failure.outcome is FailureOutcome.EXPIRED


def test_paid_status_is_unaffected_by_the_expired_fix(provider: XenditPaymentProvider) -> None:
    body = {"id": "inv-paid-1", "status": "PAID", "paid_amount": 790_000, "currency": "IDR"}
    event = provider.parse_event(raw_body=json.dumps(body).encode(), headers={})
    assert isinstance(event, NormalizedPaidEvent)
    assert event.amount_idr == 790_000


# --- the id a callback yields must be the id `refund()` can spend ---------------
#
# `provider_charge_id` is not a free-form label: it is stored on the order, an
# OP-F04/F05 late case carries it into `late_case_charge_id`, and
# `resolve_late_order` hands it to `refund()`, which posts it as
# `{"invoice_id": ...}`. Both webhook branches used to prefer `payment_id`, so a
# real staff refund on that path was issued with a payment id in the invoice-id
# field: 404 -> RefundFailed -> PaymentProviderUnavailable, money kept, case
# stuck open. Found by Codex `gpt-5.6-sol` and Kimi `k3` on the OP-F08 diff.


def test_a_paid_callback_carrying_both_ids_yields_the_invoice_id(
    provider: XenditPaymentProvider,
) -> None:
    body = {
        "id": "inv-both-ids-1",
        "status": "PAID",
        # the shape that made the two indistinguishable: BOTH keys present
        "payment_id": "pay-both-ids-1",
        "paid_amount": 790000,
        "currency": "IDR",
    }
    event = provider.parse_event(raw_body=json.dumps(body).encode(), headers={})
    assert isinstance(event, NormalizedPaidEvent)
    assert event.provider_charge_id == "inv-both-ids-1"
    assert event.provider_charge_id != "pay-both-ids-1"


def test_a_refunded_callback_carrying_both_ids_yields_the_invoice_id(
    provider: XenditPaymentProvider,
) -> None:
    body = {
        "id": "inv-both-ids-2",
        "status": "REFUNDED",
        "payment_id": "pay-both-ids-2",
        "refund_id": "rfd-both-ids-2",
    }
    event = provider.parse_event(raw_body=json.dumps(body).encode(), headers={})
    assert isinstance(event, NormalizedRefundEvent)
    assert event.provider_charge_id == "inv-both-ids-2"
    assert event.provider_refund_id == "rfd-both-ids-2"


@pytest.mark.asyncio
async def test_the_refund_the_paid_callback_makes_possible_is_spendable() -> None:
    """The end the two tests above exist for: parse a PAID callback carrying
    both ids, then spend the id it yielded through `refund()` and read what
    actually goes on the wire. `invoice_id` must be the INVOICE id — Xendit
    404s on anything else, and `RefundFailed` is raised after the staff action
    has already been taken."""

    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "rfd-spent-1"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = XenditPaymentProvider(
        secret_key="xnd_development_fake_key_for_tests",
        callback_verification_token="fake-token",
        public_base_url="https://example.com",
        fee_config=XenditFeeConfig(percentage_bps=350, fixed_idr=6000),
        client=client,
    )
    try:
        body = {
            "id": "inv-spendable-1",
            "status": "PAID",
            "payment_id": "pay-spendable-1",
            "paid_amount": 790000,
            "currency": "IDR",
        }
        event = provider.parse_event(raw_body=json.dumps(body).encode(), headers={})
        assert isinstance(event, NormalizedPaidEvent)
        refund_id = await provider.refund(
            provider_charge_id=event.provider_charge_id,
            idempotency_key="idem-spendable-1",
        )
    finally:
        await client.aclose()

    assert refund_id == "rfd-spent-1"
    assert sent == [{"invoice_id": "inv-spendable-1", "reason": "OTHERS"}], (
        "the refund was issued against something other than the invoice id — "
        "Xendit answers 404 and the money never goes back"
    )


# --- a refund with no charge id must not reach the network ---------------------
#
# `resolve_late_order` passes `row["late_case_charge_id"]`, and an OP-08 case
# writes that column as NULL on purpose (`_open_late_case(charge_id=None)`).
# Before the guard, "nothing gets refunded" held only because Xendit rejects a
# null `invoice_id` — a safety property owned by someone else's validator, and
# one the OP-08 staff page states as settled fact.


@pytest.mark.asyncio
async def test_a_refund_without_a_charge_id_never_reaches_the_provider() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"id": "rfd-should-not-happen"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = XenditPaymentProvider(
        secret_key="xnd_development_fake_key_for_tests",
        callback_verification_token="fake-token",
        public_base_url="https://example.com",
        fee_config=XenditFeeConfig(percentage_bps=350, fixed_idr=6000),
        client=client,
    )
    try:
        with pytest.raises(RefundFailed) as raised:
            await provider.refund(provider_charge_id=None, idempotency_key="idem-null-1")
        with pytest.raises(RefundFailed):
            await provider.refund(provider_charge_id="", idempotency_key="idem-empty-1")
    finally:
        await client.aclose()

    assert "no charge id" in str(raised.value)
    assert calls == [], "a refund with no charge id was sent to the provider anyway"
