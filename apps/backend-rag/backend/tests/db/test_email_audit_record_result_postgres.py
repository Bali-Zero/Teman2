"""Real-Postgres tests for ``email_audit.record_email_result``.

The UPDATE used ONE parameter for both the ``status`` assignment
(``character varying``) and ``CASE WHEN $2 = 'sent'`` (``text``). Postgres
refuses to PREPARE a parameter whose uses deduce two types, and
``record_email_result`` swallows the error, so every audited email stayed
``'sending'`` — then ``check_stale_sendings`` failed it and the retry worker
mailed a ``[RETRY]`` notice for mail that had been delivered. A fake
connection runs the broken SQL as happily as the fixed one; only a real
PREPARE shows the defect, so these tests use ``db_tx`` (see ``conftest.py``).
``email_send_log`` is migration ``126`` in ``migrations_v2``, so it exists in
the test template.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from backend.services.notifications.email_audit import (
    log_email_attempt,
    record_email_result,
)

pytestmark = pytest.mark.integration


class _SingleConnectionPool:
    """Every ``acquire()`` yields the same ``db_tx`` connection, so rows the
    code under test writes are visible to the assertions and still vanish at
    rollback."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    def acquire(self) -> Any:
        conn = self._conn

        class _Ctx:
            async def __aenter__(self_inner) -> asyncpg.Connection:
                return conn

            async def __aexit__(self_inner, *exc: object) -> bool:
                return False

        return _Ctx()


async def _sending_row(pool: _SingleConnectionPool, email_type: str) -> int:
    row_id = await log_email_attempt(
        pool,  # type: ignore[arg-type]
        email_type=email_type,
        to_email="recipient@example.test",
        subject="subject",
    )
    assert row_id is not None
    return row_id


@pytest.mark.asyncio
async def test_sent_result_leaves_sending_and_stamps_sent_at(db_tx: asyncpg.Connection) -> None:
    pool = _SingleConnectionPool(db_tx)
    row_id = await _sending_row(pool, "welcome")

    await record_email_result(pool, row_id, status="sent", provider="brevo")  # type: ignore[arg-type]

    row = await db_tx.fetchrow(
        "SELECT status, provider, sent_at, retry_after FROM email_send_log WHERE id = $1",
        row_id,
    )
    assert row["status"] == "sent"
    assert row["provider"] == "brevo"
    assert row["sent_at"] is not None
    assert row["retry_after"] is None


@pytest.mark.asyncio
async def test_failed_result_schedules_a_retry_without_sent_at(db_tx: asyncpg.Connection) -> None:
    pool = _SingleConnectionPool(db_tx)
    row_id = await _sending_row(pool, "hr_bonus")

    await record_email_result(  # type: ignore[arg-type]
        pool, row_id, status="failed", provider="brevo", error_message="HTTP 500"
    )

    row = await db_tx.fetchrow(
        "SELECT status, sent_at, retry_after, error_message FROM email_send_log WHERE id = $1",
        row_id,
    )
    assert row["status"] == "failed"
    assert row["sent_at"] is None
    assert row["retry_after"] is not None
    assert row["error_message"] == "HTTP 500"


@pytest.mark.asyncio
async def test_one_parameter_as_varchar_and_text_still_fails_to_prepare(
    db_tx: asyncpg.Connection,
) -> None:
    """GUILT, kept independent of the code under test: the statement shape
    the fix removed is still refused by Postgres, so the two-parameter form
    is load-bearing and must not be 'simplified' back."""
    with pytest.raises(asyncpg.exceptions.AmbiguousParameterError):
        await db_tx.prepare(
            """
            UPDATE email_send_log
               SET status = $2,
                   sent_at = CASE WHEN $2 = 'sent' THEN NOW() ELSE sent_at END
             WHERE id = $1
            """
        )
