"""Provider acceptance and idempotency contract for portal email jobs."""

import importlib
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

router = importlib.import_module("backend.app.modules.notifications.router")
adapter = importlib.import_module("backend.app.services.internal_email")


@pytest.mark.asyncio
async def test_keyed_send_has_no_cross_provider_fallback(monkeypatch):
    brevo, resend, zoho = AsyncMock(return_value=False), AsyncMock(), AsyncMock()
    monkeypatch.setattr(router, "_send_via_brevo", brevo)
    monkeypatch.setattr(router, "_send_via_resend", resend)
    monkeypatch.setattr(router, "_send_via_zoho_smtp", zoho)
    key = uuid4()
    result = await router.send_direct_email(
        router.SendEmailRequest(
            to="client@example.com", subject="Notice", body="Generic notice", idempotency_key=key
        )
    )
    assert result.success is False
    assert brevo.call_args.kwargs["idempotency_key"] == str(key)
    resend.assert_not_awaited()
    zoho.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(
            400, json={"code": "duplicate_parameter", "message": "Key already processed"}
        ),
        httpx.Response(400, json={"code": "duplicate_parameter", "message": "Duplicate recipient"}),
        httpx.Response(503),
    ],
)
async def test_ambiguous_provider_result_is_never_reported_as_accepted(monkeypatch, response):
    monkeypatch.setenv("SENDGRID_API_KEY", "xkeysib-synthetic-test-key")
    client = AsyncMock()
    client.post.return_value = response
    monkeypatch.setattr(router, "get_email_client", AsyncMock(return_value=client))
    with pytest.raises(router.EmailDeliveryUncertain):
        await router._send_via_brevo(
            "client@example.com", "Notice", "Generic", None, idempotency_key="synthetic-key"
        )
    assert client.post.call_args.kwargs["json"]["headers"] == {"idempotencyKey": "synthetic-key"}
    result = await router.send_direct_email(
        router.SendEmailRequest(
            to="client@example.com", subject="Notice", body="Generic", idempotency_key=uuid4()
        )
    )
    assert result.success is False and result.delivery_uncertain is True


@pytest.mark.asyncio
async def test_non_brevo_key_is_not_used_for_keyed_delivery(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "synthetic-sendgrid-key")
    client = AsyncMock()
    monkeypatch.setattr(router, "get_email_client", AsyncMock(return_value=client))
    assert not await router._send_via_brevo(
        "client@example.com", "Notice", "Generic", None, idempotency_key="synthetic-key"
    )
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_http_200_provider_failure_does_not_mark_delivery_success(monkeypatch):
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        200, json={"success": False}, request=httpx.Request("POST", "https://example.invalid/email")
    )
    monkeypatch.setattr(adapter, "_EMAIL_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(adapter, "get_email_client", AsyncMock(return_value=client))
    with pytest.raises(RuntimeError, match="email_provider_rejected"):
        await adapter.send_internal_email(
            to="client@example.com",
            subject="Notice",
            body="Generic notice",
            idempotency_key=str(uuid4()),
            raise_on_failure=True,
        )


@pytest.mark.asyncio
async def test_adapter_preserves_uncertain_acceptance(monkeypatch):
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        200,
        json={"success": False, "delivery_uncertain": True},
        request=httpx.Request("POST", "https://example.invalid/email"),
    )
    monkeypatch.setattr(adapter, "_EMAIL_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(adapter, "get_email_client", AsyncMock(return_value=client))
    with pytest.raises(adapter.EmailDeliveryUncertain):
        await adapter.send_internal_email(
            to="client@example.com",
            subject="Notice",
            body="Generic",
            idempotency_key=str(uuid4()),
            raise_on_failure=True,
        )
