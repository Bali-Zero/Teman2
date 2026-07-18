"""intake-v2 PR-1 — identity capture at the entry door: gate + idempotency tests.

Per W96 (test-writes-prod), this suite NEVER touches a real database — a
``FakeConn`` stands in for ``asyncpg.Connection`` and dispatches on query text,
same convention as ``test_intake_routing_phone.py``. The concurrency test
models the ON CONFLICT DO NOTHING + re-select race explicitly (a second
``resolve_or_create_contact`` call observing the first call's committed row)
rather than touching Postgres — the real SQL (partial unique index arbiter +
the ``phone``/``phone_normalized`` trigger interaction) was verified manually
against nuzantara_dev in a rolled-back transaction while building this module;
this suite locks in the CALLER-VISIBLE contract.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.intake import contact_autocreate as ca


class FakeConn:
    """Minimal asyncpg.Connection stand-in: dispatches on query text.

    ``existing_matches``: rows returned for the phone-lookup SELECT.
    ``insert_returns_id``: id returned by the INSERT ... RETURNING id (None
        means the INSERT lost the ON CONFLICT race, mirroring a concurrent
        winner already occupying the partial-unique slot).
    ``winner_id``: id returned by the post-conflict re-select SELECT.
    """

    def __init__(
        self,
        *,
        existing_matches: list[dict[str, Any]] | None = None,
        insert_returns_id: int | None = None,
        winner_id: int | None = None,
    ) -> None:
        self.existing_matches = existing_matches or []
        self.insert_returns_id = insert_returns_id
        self.winner_id = winner_id
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((query, args))
        if "phone_normalized IN" in query:
            return self.existing_matches
        return []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((query, args))
        if "INSERT INTO clients" in query:
            if self.insert_returns_id is not None:
                return {"id": self.insert_returns_id}
            return None
        if "SELECT id FROM clients" in query and "origin = $1" in query:
            return {"id": self.winner_id} if self.winner_id is not None else None
        return None


def _never_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ca, "_is_internal_sender_phone", lambda _phone: False)


def _always_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ca, "_is_internal_sender_phone", lambda _phone: True)


# --------------------------------------------------------------------------- #
# (a) roster / internal phone -> NEVER a contact
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_roster_phone_never_creates_a_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    _always_internal(monkeypatch)
    monkeypatch.setenv(ca.AUTOCREATE_ENABLED_ENV, "1")
    conn = FakeConn(insert_returns_id=999)  # would "succeed" if ever attempted

    out = await ca.resolve_or_create_contact(conn, sender_phone="0811234567")

    assert out.kind == ca.KIND_INTERNAL_FORWARD
    assert out.client_id is None
    assert not conn.fetchrow_calls, "internal/roster phone must never reach the INSERT"
    assert not conn.fetch_calls, "internal/roster phone must never even probe existing clients"


# --------------------------------------------------------------------------- #
# (b) known phone -> existing id, no create attempted
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_known_phone_returns_existing_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _never_internal(monkeypatch)
    monkeypatch.setenv(ca.AUTOCREATE_ENABLED_ENV, "1")
    conn = FakeConn(existing_matches=[{"id": 123}])

    out = await ca.resolve_or_create_contact(conn, sender_phone="081234567890")

    assert out.kind == ca.KIND_EXISTING
    assert out.client_id == 123
    assert not conn.fetchrow_calls, "an existing match must never trigger an INSERT"


@pytest.mark.asyncio
async def test_shared_phone_multiple_matches_is_ambiguous_not_a_guess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _never_internal(monkeypatch)
    monkeypatch.setenv(ca.AUTOCREATE_ENABLED_ENV, "1")
    conn = FakeConn(existing_matches=[{"id": 1}, {"id": 2}])

    out = await ca.resolve_or_create_contact(conn, sender_phone="081234567890")

    assert out.kind == ca.KIND_AMBIGUOUS
    assert out.client_id is None
    assert not conn.fetchrow_calls


# --------------------------------------------------------------------------- #
# (c) unknown phone -> auto-create, gated by the killswitch
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_unknown_phone_creates_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    _never_internal(monkeypatch)
    monkeypatch.setenv(ca.AUTOCREATE_ENABLED_ENV, "1")
    conn = FakeConn(existing_matches=[], insert_returns_id=555)

    out = await ca.resolve_or_create_contact(conn, sender_phone="081234567890")

    assert out.kind == ca.KIND_CREATED
    assert out.client_id == 555
    # The SQL binds the SAME $2 placeholder to both `phone` and
    # `phone_normalized` columns (the DB-side trigger overwrites
    # phone_normalized FROM phone otherwise) — asyncpg sees one bound param.
    insert_query, insert_args = conn.fetchrow_calls[0]
    assert "INSERT INTO clients" in insert_query
    assert "VALUES ($1, $2, $2, $3, $4, $5" in insert_query
    assert insert_args[1] == out.phone_normalized


@pytest.mark.asyncio
async def test_unknown_phone_flag_off_is_noop_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _never_internal(monkeypatch)
    monkeypatch.delenv(ca.AUTOCREATE_ENABLED_ENV, raising=False)
    conn = FakeConn(existing_matches=[])

    out = await ca.resolve_or_create_contact(conn, sender_phone="081234567890")

    assert out.kind == ca.KIND_DISABLED
    assert out.client_id is None
    assert not conn.fetchrow_calls, "killswitch off must never reach the INSERT"


@pytest.mark.asyncio
async def test_no_phone_abstains(monkeypatch: pytest.MonkeyPatch) -> None:
    _never_internal(monkeypatch)
    monkeypatch.setenv(ca.AUTOCREATE_ENABLED_ENV, "1")
    conn = FakeConn(insert_returns_id=999)

    out = await ca.resolve_or_create_contact(conn, sender_phone=None)

    assert out.kind == ca.KIND_NO_PHONE
    assert out.client_id is None
    assert not conn.fetch_calls
    assert not conn.fetchrow_calls


# --------------------------------------------------------------------------- #
# Concurrent double-call -> created exactly once (idempotent under the race)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_concurrent_double_call_creates_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _never_internal(monkeypatch)
    monkeypatch.setenv(ca.AUTOCREATE_ENABLED_ENV, "1")

    # Caller A: nobody exists yet, wins the INSERT race.
    conn_a = FakeConn(existing_matches=[], insert_returns_id=777)
    out_a = await ca.resolve_or_create_contact(conn_a, sender_phone="081234567890")
    assert out_a.kind == ca.KIND_CREATED
    assert out_a.client_id == 777

    # Caller B: races in at the SAME moment (still sees 0 existing matches —
    # A's row hasn't committed from B's snapshot yet), loses the ON CONFLICT
    # (insert_returns_id=None) and re-selects A's committed winner.
    conn_b = FakeConn(existing_matches=[], insert_returns_id=None, winner_id=777)
    out_b = await ca.resolve_or_create_contact(conn_b, sender_phone="081234567890")

    assert out_b.kind == ca.KIND_EXISTING
    assert out_b.client_id == 777
    assert out_a.client_id == out_b.client_id, "both callers must converge on ONE client id"


@pytest.mark.asyncio
async def test_conflict_with_no_reselect_hit_abstains_never_guesses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pathological race outcome (should not happen) — must abstain, not fabricate an id."""
    _never_internal(monkeypatch)
    monkeypatch.setenv(ca.AUTOCREATE_ENABLED_ENV, "1")
    conn = FakeConn(existing_matches=[], insert_returns_id=None, winner_id=None)

    out = await ca.resolve_or_create_contact(conn, sender_phone="081234567890")

    assert out.kind == ca.KIND_AMBIGUOUS
    assert out.client_id is None
