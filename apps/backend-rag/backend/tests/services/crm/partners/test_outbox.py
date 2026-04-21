"""
Outbox lifecycle tests — CRIT-2.

Covers:
1. enqueue_welcome inserts a pending row.
2. enqueue_welcome is idempotent (second call → no duplicate row).
3. flush_outbox sends and marks the row sent + stamps idempotency column.
4. flush_outbox records retry on transient failure.
5. flush_outbox moves to failed_dlq after 5 attempts.
6. enqueue_commission_earned inserts a pending row for a paid commission.
7. enqueue_commission_earned is idempotent.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

import backend.services.crm.partners.emails as emails_mod
from backend.services.crm.partners.emails import (
    enqueue_welcome,
    enqueue_commission_earned,
    flush_outbox,
)


@pytest.mark.asyncio
async def test_enqueue_welcome_inserts_outbox_row(db_conn, partner_factory):
    """enqueue_welcome must insert one pending outbox row."""
    pid = await partner_factory()
    with patch(
        "backend.services.crm.partners.emails._build_pricing_services",
        return_value=[],
    ):
        await enqueue_welcome(db_conn, uuid.UUID(int=pid.int))

    row = await db_conn.fetchrow(
        "SELECT email_type, partner_id, status FROM partner_email_outbox "
        "WHERE partner_id = $1",
        uuid.UUID(int=pid.int),
    )
    assert row is not None, "Expected outbox row after enqueue_welcome"
    assert row["email_type"] == "welcome"
    assert row["status"] == "pending"


@pytest.mark.asyncio
async def test_enqueue_welcome_idempotent(db_conn, partner_factory):
    """Calling enqueue_welcome twice must produce exactly one outbox row."""
    pid = await partner_factory()
    with patch(
        "backend.services.crm.partners.emails._build_pricing_services",
        return_value=[],
    ):
        await enqueue_welcome(db_conn, uuid.UUID(int=pid.int))
        await enqueue_welcome(db_conn, uuid.UUID(int=pid.int))

    count = await db_conn.fetchval(
        "SELECT COUNT(*) FROM partner_email_outbox WHERE partner_id = $1",
        uuid.UUID(int=pid.int),
    )
    assert count == 1, f"Expected 1 outbox row, got {count} (idempotency broken)"


@pytest.mark.asyncio
async def test_flush_outbox_sends_and_marks_sent(db_conn, partner_factory, monkeypatch):
    """flush_outbox sends pending row, marks it sent, stamps welcome_email_sent_at."""
    pid = await partner_factory()
    with patch(
        "backend.services.crm.partners.emails._build_pricing_services",
        return_value=[],
    ):
        await enqueue_welcome(db_conn, uuid.UUID(int=pid.int))

    sent_calls: list[dict] = []

    async def fake_post(*, to, cc, subject, body):
        sent_calls.append({"to": to, "subject": subject})

    monkeypatch.setattr(emails_mod, "_post_email", fake_post)

    result = await flush_outbox(db_conn)
    assert result == {"sent": 1, "retried": 0, "dlq": 0}, f"Unexpected result: {result}"
    assert len(sent_calls) == 1

    status = await db_conn.fetchval(
        "SELECT status FROM partner_email_outbox WHERE partner_id = $1",
        uuid.UUID(int=pid.int),
    )
    assert status == "sent"

    # Idempotency column on the source record must be stamped
    sent_at = await db_conn.fetchval(
        "SELECT welcome_email_sent_at FROM partners WHERE id = $1",
        uuid.UUID(int=pid.int),
    )
    assert sent_at is not None, "welcome_email_sent_at must be set after flush"


@pytest.mark.asyncio
async def test_flush_outbox_retries_on_transient_failure(db_conn, partner_factory, monkeypatch):
    """flush_outbox must record the error and schedule a retry on failure."""
    pid = await partner_factory()
    with patch(
        "backend.services.crm.partners.emails._build_pricing_services",
        return_value=[],
    ):
        await enqueue_welcome(db_conn, uuid.UUID(int=pid.int))

    async def fake_post(*, to, cc, subject, body):
        raise RuntimeError("brevo unreachable")

    monkeypatch.setattr(emails_mod, "_post_email", fake_post)

    result = await flush_outbox(db_conn)
    assert result["retried"] == 1
    assert result["sent"] == 0
    assert result["dlq"] == 0

    row = await db_conn.fetchrow(
        "SELECT status, attempts, last_error FROM partner_email_outbox "
        "WHERE partner_id = $1",
        uuid.UUID(int=pid.int),
    )
    assert row["status"] == "pending", "Should remain pending after first failure"
    assert row["attempts"] == 1
    assert "brevo unreachable" in row["last_error"]


@pytest.mark.asyncio
async def test_flush_outbox_dlq_after_5_attempts(db_conn, partner_factory, monkeypatch):
    """After 5 flush failures the row must move to failed_dlq."""
    pid = await partner_factory()
    with patch(
        "backend.services.crm.partners.emails._build_pricing_services",
        return_value=[],
    ):
        await enqueue_welcome(db_conn, uuid.UUID(int=pid.int))

    async def fake_post(*, to, cc, subject, body):
        raise RuntimeError("permanent failure")

    monkeypatch.setattr(emails_mod, "_post_email", fake_post)

    for _ in range(5):
        # Reset next_retry_at so the row is picked up each iteration
        await db_conn.execute(
            "UPDATE partner_email_outbox "
            "SET next_retry_at = now() - interval '1 minute' "
            "WHERE partner_id = $1",
            uuid.UUID(int=pid.int),
        )
        await flush_outbox(db_conn)

    row = await db_conn.fetchrow(
        "SELECT status, attempts FROM partner_email_outbox WHERE partner_id = $1",
        uuid.UUID(int=pid.int),
    )
    assert row["status"] == "failed_dlq", f"Expected failed_dlq, got {row['status']}"
    assert row["attempts"] >= 5


@pytest.mark.asyncio
async def test_enqueue_commission_earned_inserts_outbox_row(
    db_conn, partner_factory, commission_factory
):
    """enqueue_commission_earned must insert one pending outbox row for a paid commission."""
    pid = await partner_factory()
    cid = await commission_factory(
        partner_id=pid,
        status="paid",
        net_amount_idr=Decimal("500000"),
    )
    await enqueue_commission_earned(db_conn, uuid.UUID(int=cid.int))

    row = await db_conn.fetchrow(
        "SELECT email_type, commission_id, status FROM partner_email_outbox "
        "WHERE commission_id = $1",
        uuid.UUID(int=cid.int),
    )
    assert row is not None, "Expected outbox row after enqueue_commission_earned"
    assert row["email_type"] == "commission_earned"
    assert row["status"] == "pending"


@pytest.mark.asyncio
async def test_enqueue_commission_earned_idempotent(
    db_conn, partner_factory, commission_factory
):
    """Calling enqueue_commission_earned twice must produce exactly one outbox row."""
    pid = await partner_factory()
    cid = await commission_factory(
        partner_id=pid,
        status="paid",
        net_amount_idr=Decimal("500000"),
    )
    await enqueue_commission_earned(db_conn, uuid.UUID(int=cid.int))
    await enqueue_commission_earned(db_conn, uuid.UUID(int=cid.int))

    count = await db_conn.fetchval(
        "SELECT COUNT(*) FROM partner_email_outbox WHERE commission_id = $1",
        uuid.UUID(int=cid.int),
    )
    assert count == 1, f"Expected 1 outbox row, got {count} (idempotency broken)"
