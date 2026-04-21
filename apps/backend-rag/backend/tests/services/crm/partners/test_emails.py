"""
Email module tests — Task 8.

Three tests:
1. test_send_welcome_idempotent: second call is a no-op (HTTP called once).
2. test_send_welcome_includes_pricing_from_tool: body contains pricing language and commission lang.
3. test_send_commission_earned_sterilizes_client_name: "Mario Rossi" → "Mario R." in body.

_post_email is always mocked so no real HTTP is issued.
PricingService is mocked in test 2 to avoid file-loading dependencies.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.crm.partners.emails import (
    send_commission_earned,
    send_welcome,
)


@pytest.mark.asyncio
async def test_send_welcome_idempotent(db_conn, partner_factory):
    """Calling send_welcome twice only sends one email."""
    p = await partner_factory()

    with patch(
        "backend.services.crm.partners.emails._post_email",
        new=AsyncMock(),
    ) as mock_post, patch(
        "backend.services.crm.partners.emails._build_pricing_services",
        return_value=[{"name": "KITAS E33G", "price_display": "Rp 12.500.000"}],
    ):
        await send_welcome(db_conn, p.id)
        await send_welcome(db_conn, p.id)  # second call: skipped (idempotent)

    assert mock_post.call_count == 1, "Expected exactly one HTTP call; second send_welcome must be skipped"

    row = await db_conn.fetchrow(
        "SELECT welcome_email_sent_at FROM partners WHERE id = $1", p.id
    )
    assert row["welcome_email_sent_at"] is not None, "welcome_email_sent_at must be set after first send"


@pytest.mark.asyncio
async def test_send_welcome_includes_pricing_from_tool(db_conn, partner_factory):
    """Welcome email body must contain pricing reference and commission language."""
    p = await partner_factory(preferred_language="it")

    with patch(
        "backend.services.crm.partners.emails._post_email",
        new=AsyncMock(),
    ) as mock_post, patch(
        "backend.services.crm.partners.emails._build_pricing_services",
        return_value=[
            {"name": "KITAS E33G", "price_display": "Rp 12.500.000"},
            {"name": "PT PMA", "price_display": "Rp 25.000.000"},
        ],
    ):
        await send_welcome(db_conn, p.id)

    assert mock_post.call_count == 1
    body: str = mock_post.call_args.kwargs["body"]

    # Template must reference at least one Bali Zero service price
    assert "Rp" in body or "IDR" in body, f"Expected price reference in body, got:\n{body}"
    # Template must reference commission structure
    assert "commission" in body.lower() or "commissione" in body.lower(), (
        f"Expected commission language in body, got:\n{body}"
    )


@pytest.mark.asyncio
async def test_send_commission_earned_sterilizes_client_name(
    db_conn,
    partner_factory,
    commission_factory,
    client_factory,
):
    """Client full name must be sterilized to 'First L.' before reaching the email body."""
    client = await client_factory(full_name="Mario Rossi")
    p = await partner_factory()
    c = await commission_factory(
        partner_id=p.id,
        process_client_id=int(client.id),
        status="paid",
        net_amount_idr=Decimal("500000"),
    )

    with patch(
        "backend.services.crm.partners.emails._post_email",
        new=AsyncMock(),
    ) as mock_post:
        await send_commission_earned(db_conn, c.id)

    assert mock_post.call_count == 1, "Expected exactly one HTTP call for commission email"
    body: str = mock_post.call_args.kwargs["body"]

    assert "Mario Rossi" not in body, (
        f"UU PDP violation: full client name 'Mario Rossi' found in email body:\n{body}"
    )
    assert "Mario R." in body, (
        f"Expected sterilized name 'Mario R.' in email body, got:\n{body}"
    )


@pytest.mark.asyncio
async def test_build_pricing_services_returns_real_data_or_empty():
    """Integration smoke test: verify traversal produces non-empty list when
    pricing JSON is loaded, or empty when not loaded. Either is acceptable;
    the thing we're guarding against is the previous 0-services-always bug.
    """
    from backend.services.crm.partners.emails import _build_pricing_services, get_pricing_service
    svc = get_pricing_service()
    services = _build_pricing_services()
    if getattr(svc, "loaded", False):
        # If pricing is loaded in test env, we should get non-zero services
        assert len(services) > 0, "PricingService loaded but _build_pricing_services returned 0 — traversal bug"
        sample = services[0]
        assert "name" in sample
        assert "price_display" in sample
        assert isinstance(sample["name"], str)
    else:
        # Gracefully degraded — empty list is fine, but don't crash
        assert services == []
