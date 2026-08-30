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


class TestEmailedMagicLinkUrl:
    """The URL this product mails out had NEVER been asserted anywhere, which
    is how it came to point at a page that reads neither of its two query
    parameters: `/visa/voa` is the funnel's FIRST page, and the token rode
    along in the URL unread. Corrected 2026-08-28 to `/visa/voa/auth`, the
    only surface that redeems it (`apps/mouth/src/app/visa/voa/auth/`).

    NOTE this is asserted in TWO places on purpose — the code default here and
    the value `.github/workflows/garuda-arm.yml` writes to Fly. Fixing only
    one is a no-op: the arming workflow would set the env var back to the
    placeholder and win over the default.
    """

    @staticmethod
    async def _capture_link(monkeypatch) -> str:
        import httpx

        from backend.services.garuda_portal import magic_link_store

        sent: dict[str, str] = {}

        class _Resp:
            def raise_for_status(self) -> None:
                return None

        class _Client:
            def __init__(self, *a, **kw) -> None:
                pass

            async def __aenter__(self) -> _Client:
                return self

            async def __aexit__(self, *a) -> None:
                return None

            async def post(self, url, *, headers=None, json=None) -> _Resp:
                sent["body"] = json["body"]
                return _Resp()

        monkeypatch.setattr(httpx, "AsyncClient", _Client)
        await magic_link_store._default_send_magic_link_email(
            email="visitor@example.com",
            result_id="R" * 24,
            raw_token="T" * 43,
        )
        return sent["body"]

    async def test_default_link_targets_the_page_that_redeems_the_token(self, monkeypatch):
        monkeypatch.delenv("GARUDA_MAGIC_LINK_BASE_URL", raising=False)
        body = await self._capture_link(monkeypatch)
        assert 'href="https://balizero.com/visa/voa/auth?' in body, body

    async def test_default_link_is_not_the_funnel_first_page(self, monkeypatch):
        """Guilt test for the regression this replaced: `/visa/voa?...` renders
        the eligibility form, which ignores `result_id` and `magic_token`."""
        monkeypatch.delenv("GARUDA_MAGIC_LINK_BASE_URL", raising=False)
        body = await self._capture_link(monkeypatch)
        assert 'href="https://balizero.com/visa/voa?' not in body, body

    async def test_link_carries_both_parameters_the_landing_page_reads(self, monkeypatch):
        monkeypatch.delenv("GARUDA_MAGIC_LINK_BASE_URL", raising=False)
        body = await self._capture_link(monkeypatch)
        assert f"result_id={'R' * 24}" in body
        assert f"magic_token={'T' * 43}" in body

    async def test_env_var_overrides_the_default(self, monkeypatch):
        monkeypatch.setenv("GARUDA_MAGIC_LINK_BASE_URL", "https://staging.example/visa/voa/auth/")
        body = await self._capture_link(monkeypatch)
        # Trailing slash stripped by `.rstrip("/")`.
        assert 'href="https://staging.example/visa/voa/auth?' in body, body
