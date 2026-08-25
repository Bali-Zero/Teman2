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

from backend.services.payments.port import NormalizedFailureEvent, NormalizedPaidEvent
from backend.services.payments.terminal_taxonomy import CustomerAction, FailureOutcome
from backend.services.payments.xendit import XenditFeeConfig, XenditPaymentProvider


@pytest.fixture
def provider() -> XenditPaymentProvider:
    return XenditPaymentProvider(
        secret_key="xnd_development_fake_key_for_tests",
        callback_verification_token="fake-token",
        success_redirect_url="https://example.com/success",
        failure_redirect_url="https://example.com/failure",
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
