"""OP-F08 slice — `confirm_no_successful_charge` returns a `ChargeConfirmation`
built from a positive allow-list of Xendit invoice statuses, never from
`status != "PAID"`. See `_INVOICE_STATUSES_WITH_NO_ACCEPTED_CHARGE` in
`xendit.py` for the vocabulary this file exercises.
"""

from __future__ import annotations

import httpx
import pytest

from backend.services.payments.port import ChargeConfirmation
from backend.services.payments.xendit import XenditFeeConfig, XenditPaymentProvider


def _provider(handler) -> XenditPaymentProvider:
    return XenditPaymentProvider(
        secret_key="xnd_development_fake_key_for_tests",
        callback_verification_token="fake-token",
        public_base_url="https://example.com",
        fee_config=XenditFeeConfig(percentage_bps=350, fixed_idr=6000),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _handler_for(body: dict) -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    return handler


@pytest.mark.parametrize("status", ["PENDING", "EXPIRED", "FAILED"])
@pytest.mark.asyncio
async def test_statuses_with_no_accepted_charge_yield_confirmed_unpaid_true(
    status: str,
) -> None:
    provider = _provider(_handler_for({"id": "inv-1", "status": status}))
    confirmation = await provider.confirm_no_successful_charge(provider_session_id="sess-1")
    assert confirmation.confirmed_unpaid is True


@pytest.mark.asyncio
async def test_paid_status_yields_confirmed_unpaid_false() -> None:
    provider = _provider(_handler_for({"id": "inv-2", "status": "PAID"}))
    confirmation = await provider.confirm_no_successful_charge(provider_session_id="sess-2")
    assert confirmation.confirmed_unpaid is False


@pytest.mark.asyncio
async def test_settled_status_yields_confirmed_unpaid_false() -> None:
    """The guilt test for the whole OP-F08 change: under the old
    `status != "PAID"` test, a `SETTLED` invoice (a real Xendit paid status)
    would have yielded `confirmed_unpaid=True` and OP-04 would have expired
    an order the customer had actually paid for."""

    provider = _provider(_handler_for({"id": "inv-3", "status": "SETTLED"}))
    confirmation = await provider.confirm_no_successful_charge(provider_session_id="sess-3")
    assert confirmation.confirmed_unpaid is False


@pytest.mark.asyncio
async def test_unknown_status_yields_confirmed_unpaid_false() -> None:
    """An unknown/novel status is never evidence of absence: it must not be
    read as unpaid just because it fails an equality check against `PAID`."""

    provider = _provider(_handler_for({"id": "inv-4", "status": "SOME_FUTURE_STATUS"}))
    confirmation = await provider.confirm_no_successful_charge(provider_session_id="sess-4")
    assert confirmation.confirmed_unpaid is False


@pytest.mark.asyncio
async def test_provider_charge_id_is_the_invoice_id_even_when_a_payment_id_is_present() -> None:
    """GUILT, money path. The first draft preferred `payment_id`, and two
    cross-family reviewers caught the same consequence: this adapter's own
    `refund()` posts whatever it is handed as `{"invoice_id": ...}`, so a
    `payment_id` parked in `late_case_charge_id` makes the late case
    UNREFUNDABLE — the refund 404s into `RefundFailed`, i.e. the one remedy
    this whole path exists to enable. A PAID/SETTLED invoice is exactly the
    body that carries both ids, so this is the reachable case, not a corner.
    """
    provider = _provider(_handler_for({"id": "inv-5", "payment_id": "pay-5", "status": "PAID"}))
    confirmation = await provider.confirm_no_successful_charge(provider_session_id="sess-5")
    assert confirmation.provider_charge_id == "inv-5"


@pytest.mark.asyncio
async def test_provider_charge_id_is_the_invoice_id_when_there_is_no_payment_id() -> None:
    provider = _provider(_handler_for({"id": "inv-6", "status": "PENDING"}))
    confirmation = await provider.confirm_no_successful_charge(provider_session_id="sess-6")
    assert confirmation.provider_charge_id == "inv-6"


@pytest.mark.asyncio
async def test_provider_charge_id_is_none_when_neither_payment_id_nor_id_present() -> None:
    provider = _provider(_handler_for({"status": "PENDING"}))
    confirmation = await provider.confirm_no_successful_charge(provider_session_id="sess-7")
    assert confirmation.provider_charge_id is None


@pytest.mark.asyncio
async def test_provider_status_is_carried_verbatim() -> None:
    provider = _provider(_handler_for({"id": "inv-8", "status": "EXPIRED"}))
    confirmation = await provider.confirm_no_successful_charge(provider_session_id="sess-8")
    assert confirmation.provider_status == "EXPIRED"
    assert isinstance(confirmation, ChargeConfirmation)
