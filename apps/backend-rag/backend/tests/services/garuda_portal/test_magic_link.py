"""Tests for the GARUDA VOA magic-link seam (L4).

Each guard here is proven to bite: broken then restored, with the literal
red/green recorded (modus VERIFY discipline) — see the companion router test
file for the router-level journey proofs from
`products/garuda-voa/journeys/magic-link-security.feature`.
"""

from __future__ import annotations

import pytest

from backend.services.garuda_portal.magic_link import (
    PersistencePolicyUnavailable,
    UnconfiguredMagicLinkStore,
)


class TestUnconfiguredMagicLinkStoreFailsClosed:
    """No retention-policy row exists for magic-link tokens yet (LANES.md
    prerequisite chain) — every call must raise, never silently succeed."""

    async def test_issue_raises_persistence_policy_unavailable(self):
        store = UnconfiguredMagicLinkStore()
        with pytest.raises(PersistencePolicyUnavailable):
            await store.issue(
                idempotency_key="k" * 16,
                result_id="r" * 22,
                email="visitor@example.com",
                result_session_secret="s" * 43,
            )

    async def test_exchange_raises_persistence_policy_unavailable(self):
        store = UnconfiguredMagicLinkStore()
        with pytest.raises(PersistencePolicyUnavailable):
            await store.exchange(idempotency_key="k" * 16, token="t" * 43)
