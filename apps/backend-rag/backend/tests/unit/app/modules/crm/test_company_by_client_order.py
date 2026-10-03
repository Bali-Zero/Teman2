"""Row order of GET /api/crm/companies/by-client/{client_id} against a REAL Postgres.

The kita Company tab shows the link flagged ``is_primary`` as the client's
company and, when no link is primary, the first row returned. Without an
``ORDER BY`` that first row is whatever the heap scan yields, so a mock
connection cannot prove the order: these tests run the production query on a
throwaway database and move rows around the heap (an UPDATE rewrites the tuple
at the end) so an unordered query visibly returns them out of order.

``is_primary`` is nullable (``BOOLEAN DEFAULT FALSE``), and Postgres sorts NULL
first under ``DESC`` — the NULL row is part of the fixture on purpose.

Skipped unless ``TEST_DATABASE_URL`` is set and ``asyncpg`` is installed.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]

import pytest

from backend.app.modules.crm.company_router import get_client_companies_early

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    asyncpg is None or not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set or asyncpg missing",
)

CLIENT_ID = 7

# The columns company_record_to_dict() and the by-client SELECT read; types
# follow scripts/qa/portal_qa_schema.sql where it declares them.
_SCHEMA = """
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    company_type VARCHAR(100),
    brand_name VARCHAR(255),
    kbli_code VARCHAR(100),
    kbli_description TEXT,
    nib VARCHAR(100),
    npwp_company VARCHAR(100),
    akta_pendirian_no VARCHAR(255),
    akta_pendirian_date DATE,
    akta_perubahan_no VARCHAR(255),
    akta_perubahan_date DATE,
    sk_menhumkam_no VARCHAR(255),
    sk_menhumkam_date DATE,
    registered_address TEXT,
    office_address TEXT,
    city VARCHAR(100),
    province VARCHAR(100),
    postal_code VARCHAR(20),
    company_phone VARCHAR(50),
    company_email VARCHAR(255),
    status VARCHAR(50),
    setup_progress INTEGER,
    google_drive_folder_id TEXT,
    custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    created_by TEXT
);

CREATE TABLE client_company_links (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    role VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    ownership_percentage NUMERIC(5, 2),
    shares_count INTEGER,
    share_nominal_value NUMERIC,
    start_date DATE,
    status VARCHAR(50) DEFAULT 'active'
);
"""


@pytest.fixture
async def pool():
    assert asyncpg is not None and TEST_DATABASE_URL is not None
    admin = await asyncpg.connect(TEST_DATABASE_URL)
    db_name = f"company_by_client_test_{uuid.uuid4().hex[:12]}"
    await admin.execute(f'CREATE DATABASE "{db_name}"')
    await admin.close()

    base = TEST_DATABASE_URL.rsplit("/", 1)[0]
    test_pool = None
    try:
        test_pool = await asyncpg.create_pool(f"{base}/{db_name}", min_size=1, max_size=2)
        async with test_pool.acquire() as conn:
            await conn.execute(_SCHEMA)
        yield test_pool
    finally:
        if test_pool is not None:
            await test_pool.close()
        admin = await asyncpg.connect(TEST_DATABASE_URL)
        await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        await admin.close()


async def _link(conn, company_name: str, is_primary: bool | None) -> int:
    company_id = await conn.fetchval(
        "INSERT INTO companies (company_name) VALUES ($1) RETURNING id", company_name
    )
    return await conn.fetchval(
        "INSERT INTO client_company_links (client_id, company_id, is_primary) "
        "VALUES ($1, $2, $3) RETURNING id",
        CLIENT_ID,
        company_id,
        is_primary,
    )


async def _list(pool) -> list[dict]:
    return await get_client_companies_early(
        request=MagicMock(),
        client_id=CLIENT_ID,
        db=pool,
        current_user={"email": "staff@example.invalid", "role": "user"},
    )


async def test_primary_link_comes_first_even_when_inserted_last(pool) -> None:
    async with pool.acquire() as conn:
        null_flag = await _link(conn, "Company A", None)
        not_primary = await _link(conn, "Company B", False)
        primary = await _link(conn, "Company C", True)

    rows = await _list(pool)

    assert [r["link_id"] for r in rows] == [primary, null_flag, not_primary]
    assert rows[0]["is_primary"] is True


async def test_several_primary_links_keep_link_id_order(pool) -> None:
    async with pool.acquire() as conn:
        not_primary = await _link(conn, "Company A", False)
        first_primary = await _link(conn, "Company B", True)
        second_primary = await _link(conn, "Company C", True)
        await conn.execute(
            "UPDATE client_company_links SET role = 'director' WHERE id = $1", first_primary
        )

    rows = await _list(pool)

    assert [r["link_id"] for r in rows] == [first_primary, second_primary, not_primary]


async def test_without_a_primary_links_come_back_in_link_id_order(pool) -> None:
    async with pool.acquire() as conn:
        first = await _link(conn, "Company A", False)
        second = await _link(conn, "Company B", False)
        third = await _link(conn, "Company C", None)
        # Rewrites the oldest link's tuple at the end of the heap.
        await conn.execute("UPDATE client_company_links SET role = 'director' WHERE id = $1", first)

    rows = await _list(pool)

    assert [r["link_id"] for r in rows] == [first, second, third]


async def test_single_link_is_returned_unchanged(pool) -> None:
    async with pool.acquire() as conn:
        only = await _link(conn, "Company A", True)

    rows = await _list(pool)

    assert len(rows) == 1
    assert rows[0]["link_id"] == only
    assert rows[0]["company_name"] == "Company A"
    assert rows[0]["is_primary"] is True
    assert rows[0]["link_status"] == "active"
