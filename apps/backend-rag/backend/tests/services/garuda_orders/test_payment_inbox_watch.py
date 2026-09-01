"""Real-database tests for `count_quarantined` — the reader `garuda_payment_inbox`
never had.

DSN resolution follows `test_repository_integration.py` exactly, including its
correction: in CI a connection failure FAILS rather than skips, because a skip
in a gate is a fail-open and this file guards a money path.

Deliberately self-contained: it inserts into `garuda_payment_inbox` (and, where
the projection needs one, `garuda_orders`) directly rather than driving the
repository, so a failure here points at the READER and nothing else. The write
side — that the real `handle_paid_event` records `amount_mismatch` — is pinned
where that path already lives, in `test_repository_integration.py`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_orders.payment_inbox_watch import (
    UNRECORDED,
    count_quarantined,
)

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)

_NOW = datetime(2026, 8, 29, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
async def conn():
    try:
        c = await asyncpg.connect(_DSN)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable Postgres for INTAKE_TEST_DSN "
                f"(or GARUDA_L3_TEST_DSN override) -- {_DSN!r} unreachable: {exc}. "
                f"This file guards a money path; it must never pass by skipping."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
        raise AssertionError("unreachable: pytest.skip always raises") from exc
    await c.execute("TRUNCATE garuda_payment_inbox, garuda_orders CASCADE")
    try:
        yield c
    finally:
        await c.execute("TRUNCATE garuda_payment_inbox, garuda_orders CASCADE")
        await c.close()


async def _insert_order(conn, *, order_id: str, result_id: str) -> None:
    """The minimum a `garuda_payment_inbox.order_id` FK needs. No real person:
    the applicant columns are NOT NULL, so they carry obvious placeholders."""

    await conn.execute(
        """
        INSERT INTO garuda_orders
            (order_id, result_id_ref, case_type, applicant_full_name, applicant_email,
             applicant_phone, applicant_passport_number, price_idr, price_catalogue_key,
             state)
        VALUES ($1, $2, 'issuance', 'PLACEHOLDER', 'placeholder', 'placeholder',
                'placeholder', 1000000, 'test.key', 'paid')
        """,
        order_id,
        result_id,
    )


async def _insert_inbox(
    conn,
    *,
    event_id: str,
    outcome: str = "quarantined",
    reason: str | None = "unmatched_session",
    order_id: str | None = None,
    processed_at: datetime | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO garuda_payment_inbox
            (provider, provider_event_id, canonical_payload_sha256, order_id,
             outcome, quarantine_reason, processed_at)
        VALUES ('xendit', $1, $2, $3, $4, $5, $6)
        """,
        event_id,
        b"\x00" * 32,
        order_id,
        outcome,
        reason,
        processed_at if processed_at is not None else _NOW - timedelta(minutes=5),
    )


# --------------------------------------------------------------------------
# GUILT
# --------------------------------------------------------------------------


async def test_a_quarantined_row_is_seen(conn):
    """RED IF: the reader stops seeing quarantined rows — i.e. the state goes
    back to being write-only, which was the entire measured defect."""

    await _insert_order(conn, order_id="ord_watch_0000001", result_id="res_watch_0000001")
    await _insert_inbox(
        conn, event_id="evt_seen_1", reason="amount_mismatch", order_id="ord_watch_0000001"
    )

    snapshot = await count_quarantined(conn, now=_NOW)

    assert snapshot.recent == 1
    assert snapshot.lifetime == 1
    assert snapshot.reasons == frozenset({"amount_mismatch"})
    assert snapshot.clean is False
    assert snapshot.sample[0].provider_event_id == "evt_seen_1"
    assert snapshot.sample[0].order_id == "ord_watch_0000001"
    assert snapshot.sample[0].reason == "amount_mismatch"


async def test_the_reason_set_covers_the_whole_window_not_just_the_sample(conn):
    """RED IF: `reasons` is derived from the truncated sample.

    A burst of `unmatched_session` rows must not hide the one `amount_mismatch`
    that fell past `sample_limit` — the same "reading only the latest pass
    loses a type" trap the outbox scheduler documents for `unroutable_types`.
    The mismatch is inserted OLDEST so the newest-first sample excludes it.
    """

    await _insert_inbox(
        conn,
        event_id="evt_old_mismatch",
        reason="amount_mismatch",
        processed_at=_NOW - timedelta(hours=3),
    )
    for i in range(6):
        await _insert_inbox(
            conn,
            event_id=f"evt_burst_{i}",
            reason="unmatched_session",
            processed_at=_NOW - timedelta(minutes=i + 1),
        )

    snapshot = await count_quarantined(conn, sample_limit=2, now=_NOW)

    assert snapshot.recent == 7
    assert len(snapshot.sample) == 2
    assert all(e.reason == "unmatched_session" for e in snapshot.sample)
    assert "amount_mismatch" in snapshot.reasons


async def test_a_row_from_before_migration_298_renders_unrecorded(conn):
    """RED IF: a NULL reason crashes the reader or is silently given a
    fabricated cause. Rows quarantined before the column existed have no
    recorded reason and must still page."""

    await _insert_inbox(conn, event_id="evt_null_reason", reason=None)

    snapshot = await count_quarantined(conn, now=_NOW)

    assert snapshot.recent == 1
    assert snapshot.reasons == frozenset({UNRECORDED})
    assert snapshot.sample[0].reason == UNRECORDED


# --------------------------------------------------------------------------
# INNOCENCE — the positive control
# --------------------------------------------------------------------------


async def test_an_empty_inbox_is_clean(conn):
    snapshot = await count_quarantined(conn, now=_NOW)
    assert snapshot.recent == 0
    assert snapshot.lifetime == 0
    assert snapshot.reasons == frozenset()
    assert snapshot.sample == ()
    assert snapshot.clean is True


async def test_committed_and_received_rows_are_not_a_condition(conn):
    """RED IF: the query stops filtering on `outcome`. Every ordinary paid
    callback lands as `committed`; counting those would page constantly and the
    alarm would be muted within a day."""

    await _insert_inbox(conn, event_id="evt_ok_1", outcome="committed", reason=None)
    await _insert_inbox(conn, event_id="evt_ok_2", outcome="received", reason=None)
    await _insert_inbox(conn, event_id="evt_ok_3", outcome="rejected", reason=None)

    snapshot = await count_quarantined(conn, now=_NOW)

    assert snapshot.recent == 0
    assert snapshot.clean is True


async def test_a_row_outside_the_window_leaves_the_page_but_not_the_record(conn):
    """RED IF: the window stops applying (the alarm would page forever), or
    `lifetime` starts being windowed too (history would vanish, and "none in
    the window" would read as "none at all")."""

    await _insert_inbox(
        conn, event_id="evt_ancient", processed_at=_NOW - timedelta(days=9)
    )

    snapshot = await count_quarantined(conn, now=_NOW)

    assert snapshot.recent == 0
    assert snapshot.lifetime == 1
    assert snapshot.sample == ()


# --------------------------------------------------------------------------
# the reader is READ-ONLY, and the vocabulary is closed
# --------------------------------------------------------------------------


async def test_the_reader_mutates_nothing(conn):
    """RED IF: someone later makes this mark rows as seen. It reports; it does
    not act. An acknowledgement column would be a schema change with its own
    review, not a side effect smuggled into a reader."""

    await _insert_inbox(conn, event_id="evt_readonly", reason="session_not_bound")
    before = await conn.fetch(
        "SELECT provider_event_id, outcome, quarantine_reason, processed_at, order_id "
        "FROM garuda_payment_inbox ORDER BY id"
    )

    await count_quarantined(conn, now=_NOW)

    after = await conn.fetch(
        "SELECT provider_event_id, outcome, quarantine_reason, processed_at, order_id "
        "FROM garuda_payment_inbox ORDER BY id"
    )
    assert [dict(r) for r in before] == [dict(r) for r in after]


async def test_an_unknown_reason_is_refused_by_the_database(conn):
    """RED IF: migration 298's CHECK is dropped or widened by accident. The
    vocabulary is closed on purpose — an open one would let an unbounded string
    (and with it, one day, PII) into a column the alarm prints verbatim."""

    with pytest.raises(asyncpg.PostgresError):
        await _insert_inbox(conn, event_id="evt_bad_reason", reason="whatever_i_want")


@pytest.mark.parametrize("reason", ["unmatched_session", "amount_mismatch", "session_not_bound", "unexpected_state"])
async def test_every_reason_the_repository_writes_is_accepted(conn, reason):
    """RED IF: `repository.py` and migration 298 drift apart — a reason the code
    writes but the CHECK refuses would raise inside the webhook transaction and
    roll back a legitimate quarantine."""

    await _insert_inbox(conn, event_id=f"evt_{reason}", reason=reason)
    snapshot = await count_quarantined(conn, now=_NOW)
    assert snapshot.reasons == frozenset({reason})


# --------------------------------------------------------------------------
# argument validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [0, -1])
async def test_a_non_positive_sample_limit_is_refused(conn, bad):
    with pytest.raises(ValueError):
        await count_quarantined(conn, sample_limit=bad, now=_NOW)


async def test_a_non_positive_window_is_refused(conn):
    with pytest.raises(ValueError):
        await count_quarantined(conn, window=timedelta(0), now=_NOW)
