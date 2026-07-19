"""Passport-name enrichment tests for intake client cards."""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.intake.client_enricher import enrich_client_from_extracted_fields


class FakeConn:
    def __init__(self, current_name: str | None) -> None:
        self.current_name = current_name
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, _query: str, *args: Any) -> list[dict[str, str]]:
        assert args == ()
        return [
            {"column_name": "full_name"},
            {"column_name": "passport_number"},
            {"column_name": "passport_expiry"},
            {"column_name": "date_of_birth"},
            {"column_name": "nationality"},
            {"column_name": "kitas_number"},
            {"column_name": "kitas_expiry_date"},
        ]

    async def fetchrow(self, _query: str, *args: Any) -> dict[str, str | None]:
        assert args == (123,)
        return {"full_name": self.current_name}

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((query, args))
        return "UPDATE 1"

    async def fetchval(self, query: str, *args: Any) -> None:
        # pg_advisory_xact_lock taken before strong-id column writes — record it
        # so tests can assert the lock protocol without a real Postgres.
        self.lock_calls = getattr(self, "lock_calls", [])
        self.lock_calls.append((query, args))
        return None


@pytest.mark.asyncio
async def test_passport_name_replaces_placeholder_client_name() -> None:
    conn = FakeConn("Lead +6281200001111")

    written = await enrich_client_from_extracted_fields(
        conn,
        123,
        "passport",
        {
            "name": {"value": "Maria Rossi"},
            "passport_no": {"value": "YC0000001"},
        },
    )

    assert written["full_name"] == "Maria Rossi"
    assert written["passport_number"] == "YC0000001"
    sql, args = conn.execute_calls[0]
    assert "full_name =" in sql
    assert args[:2] == ("Maria Rossi", "YC0000001")


@pytest.mark.asyncio
async def test_passport_name_does_not_overwrite_real_client_name() -> None:
    conn = FakeConn("Existing Client")

    written = await enrich_client_from_extracted_fields(
        conn,
        123,
        "passport",
        {
            "name": {"value": "Different Passport Name"},
            "passport_no": {"value": "YC0000001"},
        },
    )

    assert "full_name" not in written
    assert written["passport_number"] == "YC0000001"
    sql, args = conn.execute_calls[0]
    assert "full_name =" not in sql
    assert args[0] == "YC0000001"


@pytest.mark.asyncio
async def test_kitas_name_replaces_placeholder_client_name() -> None:
    conn = FakeConn("Lead +6281200001111")

    written = await enrich_client_from_extracted_fields(
        conn,
        123,
        "kitas",
        {
            "name": {"value": "Maria Rossi"},
            "kitas_no": {"value": "2C11AB98765"},
        },
    )

    assert written["full_name"] == "Maria Rossi"
    assert written["kitas_number"] == "2C11AB98765"
    sql, args = conn.execute_calls[0]
    assert "full_name =" in sql
    assert args[:2] == ("Maria Rossi", "2C11AB98765")


@pytest.mark.asyncio
async def test_kitas_name_does_not_overwrite_real_client_name() -> None:
    conn = FakeConn("Existing Client")

    written = await enrich_client_from_extracted_fields(
        conn,
        123,
        "kitas",
        {
            "name": {"value": "Different Kitas Name"},
            "kitas_no": {"value": "2C11AB98765"},
        },
    )

    assert "full_name" not in written
    assert written["kitas_number"] == "2C11AB98765"
    sql, args = conn.execute_calls[0]
    assert "full_name =" not in sql
    assert args[0] == "2C11AB98765"
