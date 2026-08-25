"""Integration tests for the ``garuda_voa_check_results`` purge wrapper.

Dissent from PR #4920 review (team-lead, family #2 esiste != armato):
migration 286 defines ``purge_garuda_voa_check_results`` but shipped with
zero Python callers, while the sibling archive table's purge primitive
(``purge_garuda_voa_checks``, mirrored here as
``purge_expired_garuda_voa_check_results``) has one in
``garuda_flow.retention``. This proves the new wrapper actually reaches the
real function end-to-end, the same way ``test_retention.py`` proves the
archive one does.

Uses the same live-Postgres convention as
``test_check_to_order_journey.py`` (persistent ``nuzantara_test`` database
with the full migration chain already applied through 286) rather than the
from-scratch ephemeral sandbox in
``test_garuda_voa_retention.py``/``test_retention.py`` -- that sandbox's
``GARUDA_MIGRATION_NUMBERS`` tuple is a self-contained subset frozen at 281
and does not know about 284/285/286, and widening someone else's frozen
subset for this one dissent-fix is out of scope.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import date

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_flow.check_store import purge_expired_garuda_voa_check_results

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)


async def _seed_policy(conn: asyncpg.Connection, *, retention_interval: str) -> str:
    """Mirrors test_check_to_order_journey.py's ``_seed_policy`` -- self-heals
    a dangling open GARUDA_CHECK row, then opens a fresh one with a
    caller-controlled retention interval (short, so purge has something
    expired to find)."""

    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_CHECK'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"check-results-purge-test-{uuid.uuid4().hex[:16]}"
    await conn.execute(
        f"""
        INSERT INTO public.visa_decision_retention_policies (
            environment, policy_scope, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor, effective_period, approved_by, approval_reference
        ) VALUES (
            'TEST', 'GARUDA_CHECK', $1, {retention_interval},
            INTERVAL '1 second', INTERVAL '30 days',
            'CREATED_AT', tstzrange(clock_timestamp(), NULL, '[)'),
            'zero-test-approver', 'ZERO-CHECK-RESULTS-PURGE-TEST-APPROVAL'
        )
        """,
        policy_version,
    )
    return policy_version


async def _close_policy(conn: asyncpg.Connection, *, policy_version: str) -> None:
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE policy_scope = 'GARUDA_CHECK' AND policy_version = $1
           AND upper(effective_period) IS NULL
        """,
        policy_version,
    )


async def _insert_check_result(connection: asyncpg.Connection, *, result_id: str) -> None:
    secret_hash = hashlib.sha256(b"irrelevant-for-this-test").hexdigest()
    await connection.execute(
        """
        INSERT INTO public.garuda_voa_check_results (
            result_id, session_secret_hash, environment, case_type, nationality,
            entry_date, passport_expiry_date, purpose, travellers, self_pay,
            decision, reason_codes, published_filing_deadline, price_idr, price_source,
            retention_notice_acknowledged_at
        ) VALUES (
            $1, $2, 'TEST', 'issuance', 'USA',
            $3, $4, 'tourism', 1, TRUE,
            'ACCEPT', $5, $6, $7, $8,
            clock_timestamp()
        )
        """,
        result_id,
        secret_hash,
        date(2026, 8, 1),
        date(2027, 8, 1),
        json.dumps([]),
        date(2026, 8, 31),
        500_000,
        "test-fixture",
    )


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(dsn=_DSN, min_size=1, max_size=4)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable Postgres for INTAKE_TEST_DSN "
                f"(or GARUDA_L3_TEST_DSN override) -- {_DSN!r} unreachable: {exc}."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")

    async with p.acquire() as conn:
        await conn.execute("TRUNCATE garuda_voa_check_idempotency, garuda_voa_check_results CASCADE")

    yield p
    await p.close()


async def test_purge_rejects_out_of_range_limit(pool) -> None:
    with pytest.raises(ValueError, match="limit must be"):
        await purge_expired_garuda_voa_check_results(pool, limit=0, requested_by="zero")
    with pytest.raises(ValueError, match="requested_by"):
        await purge_expired_garuda_voa_check_results(pool, limit=10, requested_by="")


async def test_purge_deletes_via_the_bounded_primitive(pool) -> None:
    async with pool.acquire() as conn:
        policy_version = await _seed_policy(conn, retention_interval="INTERVAL '1 second'")
        try:
            result_id = "purge-test-" + uuid.uuid4().hex[:20]
            await _insert_check_result(conn, result_id=result_id)

            await asyncio.sleep(1.2)

            deleted = await purge_expired_garuda_voa_check_results(
                pool, limit=100, requested_by="svc-op"
            )
            assert deleted == 1

            row = await conn.fetchrow(
                "SELECT 1 FROM garuda_voa_check_results WHERE result_id = $1", result_id
            )
            assert row is None
        finally:
            await _close_policy(conn, policy_version=policy_version)


async def test_purge_is_inert_with_no_signed_policy(pool) -> None:
    """The GARUDA_CHECK scope is shared -- with no policy row bound, the
    fail-closed insert trigger means nothing can ever land in the table to
    be purged. Zero rows expired is the correct, safe answer here, not a
    silent no-op masking a broken wrapper."""

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE public.visa_decision_retention_policies
               SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
             WHERE environment = 'TEST' AND policy_scope = 'GARUDA_CHECK'
               AND upper(effective_period) IS NULL
            """
        )

    deleted = await purge_expired_garuda_voa_check_results(pool, limit=100, requested_by="svc-op")
    assert deleted == 0
