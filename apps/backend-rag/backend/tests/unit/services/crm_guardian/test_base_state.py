from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.crm_guardian.base import bump_circuit_breaker


@pytest.mark.asyncio
async def test_bump_circuit_breaker_success_clears_active_failure_state() -> None:
    class FakeConn:
        def __init__(self) -> None:
            self.execute = AsyncMock(return_value="UPDATE 1")

    conn = FakeConn()

    await bump_circuit_breaker(conn, "I10_summary_l1", True)

    sql = conn.execute.await_args.args[0]
    assert "consecutive_errors = 0" in sql
    assert "circuit_breaker_tripped = false" in sql
    assert "last_error_message = NULL" in sql
    assert conn.execute.await_args.args[1] == "I10_summary_l1"


@pytest.mark.asyncio
async def test_bump_circuit_breaker_failure_records_error_state() -> None:
    class FakeConn:
        def __init__(self) -> None:
            self.execute = AsyncMock(return_value="UPDATE 1")

    conn = FakeConn()

    await bump_circuit_breaker(conn, "I10_summary_l1", False, "drive unavailable")

    sql = conn.execute.await_args.args[0]
    assert "last_error_at = NOW()" in sql
    assert "last_error_message = $2" in sql
    assert "consecutive_errors = consecutive_errors + 1" in sql
    assert conn.execute.await_args.args[1] == "I10_summary_l1"
    assert conn.execute.await_args.args[2] == "drive unavailable"
