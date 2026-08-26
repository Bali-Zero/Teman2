"""Tests for portal process timeline endpoint."""

import logging
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.app.routers.portal_process_timeline import _build_timeline


@pytest.mark.asyncio
async def test_timeline_returns_steps_for_valid_practice() -> None:
    """Timeline endpoint returns ordered steps for a practice belonging to the client."""
    mock_conn = AsyncMock()

    mock_conn.fetchrow.return_value = {
        "id": 10,
        "client_id": 1,
        "status": "in_progress",
        "start_date": "2026-01-15",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "KITAS B211A",
        "practice_category": "visa",
        "assigned_to": "asya@balizero.com",
    }

    mock_conn.fetch.return_value = [
        {
            "old_status": None,
            "new_status": "inquiry",
            "changed_at": "2026-01-15T10:00:00+00:00",
            "changed_by": "system",
        },
        {
            "old_status": "inquiry",
            "new_status": "quotation_sent",
            "changed_at": "2026-01-15T14:00:00+00:00",
            "changed_by": "asya@balizero.com",
        },
        {
            "old_status": "quotation_sent",
            "new_status": "payment_pending",
            "changed_at": "2026-01-16T09:00:00+00:00",
            "changed_by": "asya@balizero.com",
        },
        {
            "old_status": "payment_pending",
            "new_status": "in_progress",
            "changed_at": "2026-01-17T11:00:00+00:00",
            "changed_by": "system",
        },
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=10, client_id=1)

    assert result is not None
    assert result["practice_id"] == 10
    assert result["practice_name"] == "KITAS B211A"
    assert result["current_status"] == "in_progress"
    assert len(result["steps"]) == 4
    assert result["steps"][0]["status"] == "inquiry"
    assert result["steps"][0]["completed"] is True
    assert result["steps"][-1]["status"] == "in_progress"
    assert result["steps"][-1]["is_current"] is True


@pytest.mark.asyncio
async def test_timeline_returns_none_for_wrong_client() -> None:
    """Timeline endpoint returns None if practice does not belong to the client."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=999, client_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_timeline_fallback_when_no_status_log() -> None:
    """Timeline returns single step when practice_status_log table doesn't exist."""
    mock_conn = AsyncMock()

    mock_conn.fetchrow.return_value = {
        "id": 5,
        "client_id": 1,
        "status": "waiting_documents",
        "start_date": "2026-02-01",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "PT PMA Setup",
        "practice_category": "company",
        "assigned_to": "damar@balizero.com",
    }

    # Simulate table not existing
    mock_conn.fetch.side_effect = asyncpg.UndefinedTableError(
        "relation practice_status_log does not exist"
    )

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=5, client_id=1)

    assert result is not None
    assert result["practice_name"] == "PT PMA Setup"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["status"] == "waiting_documents"
    assert result["steps"][0]["is_current"] is True


@pytest.mark.asyncio
async def test_timeline_response_never_carries_staff_identity() -> None:
    """Client-facing timeline must not leak staff actor identity.

    `changed_by` (practice_status_log actor) and `assigned_to` (case
    officer) are staff email addresses — internal identity, never
    client-facing. Even if a row/mock still carries them (e.g. a stale
    caller or a DB column that outlives this query), the response dict
    built for the client must not surface either key, at any nesting
    level (outer dict + every step dict, both the history-rows path and
    the single-step fallback path).
    """
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 20,
        "client_id": 1,
        "status": "in_progress",
        "start_date": "2026-01-15",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "KITAS B211A",
        "practice_category": "visa",
        # Extra keys a looser mock/caller might still attach — must never
        # be read into the response even if present on the row.
        "assigned_to": "staff@example.com",
    }
    mock_conn.fetch.return_value = [
        {
            "old_status": None,
            "new_status": "inquiry",
            "changed_at": "2026-01-15T10:00:00+00:00",
            "changed_by": "staff@example.com",
        },
        {
            "old_status": "inquiry",
            "new_status": "in_progress",
            "changed_at": "2026-01-16T09:00:00+00:00",
            "changed_by": "other-staff@example.com",
        },
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=20, client_id=1)

    assert result is not None
    assert "assigned_to" not in result
    assert len(result["steps"]) == 2
    for step in result["steps"]:
        assert "changed_by" not in step


@pytest.mark.asyncio
async def test_timeline_fallback_response_never_carries_staff_identity() -> None:
    """Same guarantee on the single-step fallback path (no status_log rows)."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 21,
        "client_id": 1,
        "status": "waiting_documents",
        "start_date": "2026-02-01",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "PT PMA Setup",
        "practice_category": "company",
        "assigned_to": "staff@example.com",
    }
    mock_conn.fetch.side_effect = asyncpg.UndefinedTableError(
        "relation practice_status_log does not exist"
    )

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=21, client_id=1)

    assert result is not None
    assert "assigned_to" not in result
    assert len(result["steps"]) == 1
    assert "changed_by" not in result["steps"][0]


def _practice_row(status: str = "waiting_documents") -> dict:
    return {
        "id": 5,
        "client_id": 1,
        "status": status,
        "start_date": "2026-02-01",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "PT PMA Setup",
        "practice_category": "company",
        "assigned_to": "damar@balizero.com",
    }


def _pool_for(mock_conn) -> MagicMock:
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


class TestHistoryFailuresAreNotSpelledAsEmptyHistory:
    """A missing table and a broken query must not look the same.

    Until migration 289 the history query was wrapped in a bare
    `except Exception: pass`, so BOTH cases produced a one-step timeline and a
    200 — and an empty history is indistinguishable from a practice that never
    moved. Prod was measured in that state on 2026-08-27: the table did not
    exist at all, so every tracker request took the silent path.
    """

    @pytest.mark.asyncio
    async def test_absent_table_degrades_but_says_so(self, caplog) -> None:
        """The pre-289 database still serves a timeline, and logs a warning."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row()
        mock_conn.fetch.side_effect = asyncpg.UndefinedTableError(
            "relation practice_status_log does not exist"
        )

        with caplog.at_level(logging.WARNING, logger="backend.app.routers.portal_process_timeline"):
            result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        assert result is not None
        assert len(result["steps"]) == 1
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "practice_status_log is absent" in joined
        assert "289" in joined, "the log line must name the migration that fixes it"

    @pytest.mark.asyncio
    async def test_a_real_db_error_still_degrades_but_is_no_longer_SILENT(self, caplog) -> None:
        """A fault still yields a one-step timeline — it is no longer unlogged.

        The name matters and an earlier one overclaimed: this test was called
        "..._is_logged_not_swallowed" while asserting `len(steps) == 1`, i.e.
        asserting the swallowing. An adversarial review caught the mismatch.

        The DEGRADATION is deliberate and unchanged: a client asking about their
        own practice should not get a 500 because history is unavailable. What
        changed is only that the fault is now on the record at ERROR with a
        traceback, instead of vanishing into `except Exception: pass`. Note the
        scope this leaves: `asyncpg.PostgresError` also covers a query timeout
        and a schema drift (`QueryCanceledError`, `UndefinedColumnError`), and
        each of those likewise renders as a one-step timeline. Logged, not
        surfaced. Turning any of them into a client-visible failure is a
        product decision, not a bug fix, and is not made here.
        """
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row()
        mock_conn.fetch.side_effect = asyncpg.InsufficientPrivilegeError(
            "permission denied for table practice_status_log"
        )

        with caplog.at_level(logging.ERROR, logger="backend.app.routers.portal_process_timeline"):
            result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        # Still serves the current status — a client asking about their own
        # practice should not get a 500 because history is unavailable.
        assert result is not None
        assert len(result["steps"]) == 1
        # …but the fault is on the record, at ERROR, with a traceback.
        assert any(r.levelno >= logging.ERROR for r in caplog.records)
        assert any(r.exc_info for r in caplog.records), "must log the traceback"
        assert "practice_status_log query failed" in " ".join(
            r.getMessage() for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_a_non_database_error_still_propagates(self) -> None:
        """The narrowed except must not become a new catch-all.

        A bug in this function (a TypeError, an attribute error on a row) is
        not a degraded-history condition and must reach the caller instead of
        being rendered as a practice that never moved.
        """
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row()
        mock_conn.fetch.side_effect = TypeError("not a postgres problem")

        with pytest.raises(TypeError):
            await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)


class TestTheTimelineSurvivesAStatusProductionActuallyAllows:
    """`practices.status` is NULLABLE in prod, and the reader assumed a string.

    Measured 2026-08-27 against the code as it stood: BOTH paths raised
    `AttributeError: 'NoneType' object has no attribute 'replace'` — including
    the fallback path, which is the one production takes today. This was a LIVE
    500 on the client tracker for any practice with a NULL status, not a defect
    migration 289 introduced; 289 only makes a second path reach it.

    The cause is subtle enough to be worth naming: the call was
    `STATUS_LABELS.get(status, status.replace(...))`, and Python evaluates a
    `dict.get` DEFAULT eagerly — so it raised before the lookup that would have
    succeeded.
    """

    @pytest.mark.asyncio
    async def test_a_null_status_does_not_crash_the_fallback_path(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row(status=None)
        mock_conn.fetch.side_effect = asyncpg.UndefinedTableError("no table")

        result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        assert result is not None
        assert result["steps"][0]["status"] is None
        assert result["steps"][0]["label"] == "Unknown"

    @pytest.mark.asyncio
    async def test_a_null_status_does_not_crash_the_history_path(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row(status=None)
        mock_conn.fetch.return_value = [
            {"old_status": "on_process", "new_status": None, "changed_at": "2026-01-01"}
        ]

        result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        assert result is not None
        assert result["steps"][-1]["label"] == "Unknown"


class TestATerminalStatusIsNeverRenderedAsInProgress:
    """The two paths used to disagree about a finished practice.

    The history path marked the last row current whenever it matched the
    practice's status, so a completed practice came back as
    `{"status": "completed", "completed": False, "is_current": True}` and the
    client rendered a spinning loader on finished work — while the fallback
    path, ten lines below, got the same practice right. Caught by an adversarial
    review, and reachable only because 289 makes the history path run at all.
    """

    @pytest.mark.asyncio
    async def test_completed_is_completed_not_current_on_the_history_path(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row(status="completed")
        mock_conn.fetch.return_value = [
            {"old_status": None, "new_status": "on_process", "changed_at": "2026-01-01"},
            {
                "old_status": "on_process",
                "new_status": "completed",
                "changed_at": "2026-01-02",
            },
        ]

        result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        last = result["steps"][-1]
        assert last["status"] == "completed"
        assert last["is_current"] is False, "a finished practice is not in progress"
        assert last["completed"] is True

    @pytest.mark.asyncio
    async def test_a_non_terminal_last_step_IS_current(self) -> None:
        """Innocence: the fix must not mark everything finished."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row(status="on_process")
        mock_conn.fetch.return_value = [
            {"old_status": "inquiry", "new_status": "on_process", "changed_at": "2026-01-02"}
        ]

        result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        last = result["steps"][-1]
        assert last["is_current"] is True
        assert last["completed"] is False
