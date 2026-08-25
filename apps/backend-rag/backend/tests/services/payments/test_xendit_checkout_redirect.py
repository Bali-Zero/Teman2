"""Dissent #3 (team-lead review of PR #4920, 2026-08-25): the redirect URL
sent to Xendit must be able to carry the order back to the frontend. A
static `success_redirect_url`/`failure_redirect_url` pair configured at
construction time cannot -- `orderId` is a dynamic Next.js route segment
read via `useParams()` at
`apps/mouth/src/app/visa/voa/orders/[orderId]/return/page.tsx`, so no fixed
string reaches that route for any order. This is the regression test that
would go RED the moment the redirect URL stops containing the order id --
"the whole defect is that a static string looks fine in review" (team-lead,
Dissent #3).

Also pins the product's return-route contract: there is deliberately ONE
route regardless of outcome (the return page's own docstring: "the browser
return is an OBSERVATION, not a truth" -- it must never render a
success/paid state on the strength of the redirect alone), so
`success_redirect_url` and `failure_redirect_url` sent to Xendit must be
byte-identical.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from backend.services.payments.xendit import XenditFeeConfig, XenditPaymentProvider


def _provider(captured: dict, *, base_url: str = "https://www.balizero.com") -> XenditPaymentProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request

        import json as _json

        payload = _json.loads(request.content)
        captured["payload"] = payload
        return httpx.Response(
            200,
            json={
                "id": "inv-fake-1",
                "invoice_url": "https://checkout.xendit.co/web/inv-fake-1",
            },
        )

    return XenditPaymentProvider(
        secret_key="xnd_development_fake_key_for_tests",
        callback_verification_token="fake-token",
        public_base_url=base_url,
        fee_config=XenditFeeConfig(percentage_bps=0, fixed_idr=0),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_the_redirect_url_carries_the_order_id() -> None:
    """The whole defect Dissent #3 caught: a static URL cannot carry a
    per-order id. If this ever regresses to a fixed string again, this
    assertion is the one that goes red."""
    captured: dict = {}
    provider = _provider(captured)

    await provider.create_checkout_session(
        order_id="order-abc-123",
        price_idr=790_000,
        idempotency_key="idem-key-1",
    )

    success_url = captured["payload"]["success_redirect_url"]
    assert "/visa/voa/orders/order-abc-123/return" in success_url, (
        f"redirect URL does not carry the order id -- got {success_url!r}. "
        "A static success/failure URL cannot reach the dynamic "
        "[orderId]/return route; this is exactly the defect Dissent #3 caught."
    )


@pytest.mark.asyncio
async def test_success_and_failure_redirect_to_the_same_single_route() -> None:
    """Product contract: the browser return is an OBSERVATION, never a
    truth -- there is deliberately ONE return route regardless of outcome,
    so Xendit must never be given two different destinations."""
    captured: dict = {}
    provider = _provider(captured)

    await provider.create_checkout_session(
        order_id="order-abc-123",
        price_idr=790_000,
        idempotency_key="idem-key-2",
    )

    payload = captured["payload"]
    assert payload["success_redirect_url"] == payload["failure_redirect_url"], (
        "success_redirect_url and failure_redirect_url diverged -- the return "
        "route's contract requires exactly one destination for both outcomes "
        "(it observes and forwards, it never declares a result itself)."
    )


@pytest.mark.asyncio
async def test_the_redirect_url_carries_a_return_nonce_query_param() -> None:
    """The return page reads `return_nonce` from the query string
    (`page.tsx`'s `useSearchParams().get("return_nonce")`) -- without it,
    `observePaymentBrowserReturn` never fires and OP-07 never records an
    observation for this order."""
    captured: dict = {}
    provider = _provider(captured)

    await provider.create_checkout_session(
        order_id="order-abc-123",
        price_idr=790_000,
        idempotency_key="idem-key-3",
    )

    parsed = urlsplit(captured["payload"]["success_redirect_url"])
    query = parse_qs(parsed.query)
    assert "return_nonce" in query, (
        f"redirect URL has no return_nonce query param -- got "
        f"{captured['payload']['success_redirect_url']!r}"
    )
    assert len(query["return_nonce"][0]) >= 16


@pytest.mark.asyncio
async def test_two_checkout_sessions_mint_different_nonces() -> None:
    """A reused nonce across orders would let one customer's browser return
    be replayed against another order's URL shape -- each invoice gets its
    own opaque token."""
    captured_a: dict = {}
    captured_b: dict = {}
    provider = _provider(captured_a)

    await provider.create_checkout_session(
        order_id="order-abc-123", price_idr=790_000, idempotency_key="idem-key-4"
    )
    provider_b = _provider(captured_b)
    await provider_b.create_checkout_session(
        order_id="order-abc-123", price_idr=790_000, idempotency_key="idem-key-5"
    )

    nonce_a = parse_qs(urlsplit(captured_a["payload"]["success_redirect_url"]).query)[
        "return_nonce"
    ][0]
    nonce_b = parse_qs(urlsplit(captured_b["payload"]["success_redirect_url"]).query)[
        "return_nonce"
    ][0]
    assert nonce_a != nonce_b


@pytest.mark.asyncio
async def test_the_redirect_url_uses_the_configured_public_base() -> None:
    """The base is a business/deploy config, not a hardcoded constant --
    verify the adapter actually reads it rather than a baked-in default."""
    captured: dict = {}
    provider = _provider(captured, base_url="https://staging.example.org")

    await provider.create_checkout_session(
        order_id="order-abc-123", price_idr=790_000, idempotency_key="idem-key-6"
    )

    success_url = captured["payload"]["success_redirect_url"]
    assert success_url.startswith("https://staging.example.org/visa/voa/orders/")
