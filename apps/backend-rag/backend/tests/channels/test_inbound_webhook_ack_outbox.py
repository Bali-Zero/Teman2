"""inbound_webhook_repo.persist must ack the outbox wake-up row it publishes.

Regression guard for the loop-repair 2026-06-04 finding: nothing ever acked
the ``inbound_webhook_queued`` channel, so ``events_outbox`` accumulated
unconsumed orphan rows indefinitely (188+ by 2026-06-05). The durable truth is
the ``inbound_webhooks`` row (drained by SELECT FOR UPDATE SKIP LOCKED), so the
wake-up NOTIFY is self-acked in the same transaction inside ``persist``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_pool_with_conn():
    """asyncpg.Pool mock whose acquire() yields a transaction-capable conn."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.fetchrow = AsyncMock(return_value={"id": 4242})

    transaction_ctx = MagicMock()
    transaction_ctx.__aenter__ = AsyncMock(return_value=None)
    transaction_ctx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction_ctx)

    pool = MagicMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    return pool, conn


@pytest.mark.asyncio
async def test_persist_acks_the_outbox_row_it_publishes():
    from backend.services.channels import inbound_webhook_repo

    pool, conn = _mock_pool_with_conn()

    with patch.object(
        inbound_webhook_repo.events_outbox, "publish", new=AsyncMock(return_value=777)
    ) as mock_publish, patch.object(
        inbound_webhook_repo.events_outbox, "acknowledge", new=AsyncMock(return_value=True)
    ) as mock_ack:
        row_id, inserted = await inbound_webhook_repo.persist(
            pool,
            channel="whatsapp",
            dedup_key="wamid.TEST",
            payload={"hello": "world"},
        )

    assert (row_id, inserted) == (4242, True)
    mock_publish.assert_awaited_once()
    # The published wake-up row (id=777) must be acked on the same conn,
    # with a per-channel consumer_id for a readable audit trail.
    mock_ack.assert_awaited_once_with(
        conn, 777, consumer_id="inbound_webhook_persist:whatsapp"
    )


@pytest.mark.asyncio
async def test_persist_does_not_ack_on_dedup_drop():
    """When ON CONFLICT drops the row (duplicate), there is no wake-up to ack."""
    from backend.services.channels import inbound_webhook_repo

    pool, conn = _mock_pool_with_conn()
    conn.fetchrow = AsyncMock(return_value=None)  # duplicate → no insert

    with patch.object(
        inbound_webhook_repo.events_outbox, "publish", new=AsyncMock(return_value=1)
    ) as mock_publish, patch.object(
        inbound_webhook_repo.events_outbox, "acknowledge", new=AsyncMock(return_value=True)
    ) as mock_ack:
        row_id, inserted = await inbound_webhook_repo.persist(
            pool,
            channel="whatsapp",
            dedup_key="wamid.DUP",
            payload={"hello": "world"},
        )

    assert (row_id, inserted) == (None, False)
    mock_publish.assert_not_awaited()
    mock_ack.assert_not_awaited()
