"""Tests for the GARUDA VOA magic-link seam (L4).

Each guard here is proven to bite: broken then restored, with the literal
red/green recorded (modus VERIFY discipline) — see the companion router test
file for the router-level journey proofs from
`products/garuda-voa/journeys/magic-link-security.feature`.
"""

from __future__ import annotations

import pytest

from backend.services.garuda_portal.magic_link import (
    ExchangeOutcome,
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


class TestExchangeOutcomeRepr:
    """`account_session_secret` must never appear in `repr(ExchangeOutcome(...))`
    (2026-08-25, CodeQL #8755 review, round 4). A dataclass instance in frame
    locals renders as ONE repr() string under its variable name as key — a
    shape neither sentry_sdk's own built-in EventScrubber nor this repo's
    `_scrub` can catch, both being key-based. `field(repr=False)` closes it
    at the source instead: every capture path (traceback, debugger, f-string,
    a logger call written next month) inherits the omission, rather than each
    one needing its own guard. This is the unit-level pin; the delivery-path
    proof (a real `sentry_sdk.init()` + `capture_exception`, envelope
    inspected) is the actual evidence and lives outside this test file — this
    test exists so a regression is caught at the cheapest possible layer too.
    """

    def test_account_session_secret_absent_from_repr(self):
        secret = "sess-9xQ2mK7vL4pR8tY1wZ3nC6hJ0aB"
        outcome = ExchangeOutcome(
            authorized=True,
            security_counter="magic_link_authorized",
            account_session_secret=secret,
        )
        rendered = repr(outcome)
        assert secret not in rendered, f"secret leaked into repr(): {rendered!r}"
        assert "account_session_secret" not in rendered, (
            f"field name should not even appear (field(repr=False) omits it "
            f"entirely, not just its value): {rendered!r}"
        )

    def test_equality_is_unaffected_by_repr_false(self):
        """`field(repr=False)` changes only `__repr__` — `frozen=True`'s
        generated `__eq__` still compares every field's VALUE. Pinned so
        nobody mistakes repr-suppression for the field being dropped."""
        a = ExchangeOutcome(
            authorized=True,
            security_counter="magic_link_authorized",
            account_session_secret="sess-same",
        )
        b = ExchangeOutcome(
            authorized=True,
            security_counter="magic_link_authorized",
            account_session_secret="sess-same",
        )
        c = ExchangeOutcome(
            authorized=True,
            security_counter="magic_link_authorized",
            account_session_secret="sess-different",
        )
        assert a == b
        assert a != c
        assert a.account_session_secret == "sess-same"
