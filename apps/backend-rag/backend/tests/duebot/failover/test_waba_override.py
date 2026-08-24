"""Proves ``WABAOverrideClient`` against ``FakeGraphAPI`` — the POST +
GET-readback contract F9 step 5-6 names, and every typed failure class
the closed wire-error vocabulary declares. No test in this module opens
a real socket (``network_guard.py`` enforces that at collection time for
the whole ``backend/tests/duebot/`` package; ``FakeGraphAPI`` uses
``httpx.MockTransport`` so there is nothing for the guard to even need
to catch here).
"""

from __future__ import annotations

import pytest

from backend.services.team_bot_ingress.waba_override import (
    WABAOverrideClient,
    WABAOverrideError,
    WABAOverrideErrorClass,
)
from backend.tests.duebot.failover.fake_graph_api import FakeGraphAPI


async def test_override_callback_succeeds_and_verifies_readback() -> None:
    fake = FakeGraphAPI()
    async with fake.client() as httpx_client:
        override_client = WABAOverrideClient(httpx_client, access_token="fake-token")
        result = await override_client.override_callback(
            waba_id="waba-123",
            callback_uri="https://nuzantara.example.ts.net/webhooks/team-wa",
            verify_token="fake-verify-token",
        )
    assert result.verified is True
    assert result.callback_uri == "https://nuzantara.example.ts.net/webhooks/team-wa"
    assert len(fake.post_calls) == 1
    assert fake.post_calls[0]["waba_id"] == "waba-123"
    assert len(fake.get_calls) == 1


async def test_override_callback_raises_readback_mismatch_even_on_200_post() -> None:
    """The RED case F9 step 6 exists for: Meta's POST looks fine but the
    GET readback does not confirm it — must raise, never return success.
    """
    fake = FakeGraphAPI(force_readback_mismatch=True)
    async with fake.client() as httpx_client:
        override_client = WABAOverrideClient(httpx_client, access_token="fake-token")
        with pytest.raises(WABAOverrideError) as exc_info:
            await override_client.override_callback(
                waba_id="waba-123",
                callback_uri="https://nuzantara.example.ts.net/webhooks/team-wa",
                verify_token="fake-verify-token",
            )
    assert exc_info.value.error_class is WABAOverrideErrorClass.READBACK_MISMATCH


@pytest.mark.parametrize(
    "status,expected_class",
    [
        (401, WABAOverrideErrorClass.AUTH_DEAD),
        (403, WABAOverrideErrorClass.AUTH_DEAD),
        (429, WABAOverrideErrorClass.RATE_LIMITED),
        (500, WABAOverrideErrorClass.SERVER_ERROR),
        (503, WABAOverrideErrorClass.SERVER_ERROR),
    ],
)
async def test_override_callback_classifies_graph_api_error_statuses(
    status: int, expected_class: WABAOverrideErrorClass
) -> None:
    fake = FakeGraphAPI(force_status=status)
    async with fake.client() as httpx_client:
        override_client = WABAOverrideClient(httpx_client, access_token="fake-token")
        with pytest.raises(WABAOverrideError) as exc_info:
            await override_client.override_callback(
                waba_id="waba-123",
                callback_uri="https://nuzantara.example.ts.net/webhooks/team-wa",
                verify_token="fake-verify-token",
            )
    assert exc_info.value.error_class is expected_class


async def test_auth_dead_and_rate_limited_are_distinct_classes() -> None:
    """F3 names this discipline for the codex broker leg explicitly
    ("auth and quota MUST be distinct — today they collapse, split
    before arming"); the WABA client applies the same discipline from
    the start rather than repeating that defect in a new place.
    """
    auth_dead = FakeGraphAPI(force_status=401)
    rate_limited = FakeGraphAPI(force_status=429)
    async with auth_dead.client() as c1, rate_limited.client() as c2:
        client1 = WABAOverrideClient(c1, access_token="t")
        client2 = WABAOverrideClient(c2, access_token="t")
        with pytest.raises(WABAOverrideError) as e1:
            await client1.override_callback(
                waba_id="w", callback_uri="https://x.ts.net/w", verify_token="v"
            )
        with pytest.raises(WABAOverrideError) as e2:
            await client2.override_callback(
                waba_id="w", callback_uri="https://x.ts.net/w", verify_token="v"
            )
    assert e1.value.error_class is not e2.value.error_class
    assert {e1.value.error_class, e2.value.error_class} == {
        WABAOverrideErrorClass.AUTH_DEAD,
        WABAOverrideErrorClass.RATE_LIMITED,
    }
