"""
Shared fixtures for router integration tests.

Provides:
  db_pool  — asyncpg.Pool against local test DB
  db_tx    — per-test transaction, rolled back at teardown

Tests skip cleanly when the test DB is unreachable or lacks the schema
they need (e.g. CI's empty postgres:15 service container).
"""

from __future__ import annotations

import os

import asyncpg
import pytest
import pytest_asyncio

_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)

# Tables every router-integration test in this directory expects to exist.
# If any one is missing the suite skips, since the test setup that adds rows
# (via raw INSERTs, not migrations) would otherwise crash with UndefinedTable.
_REQUIRED_TABLES = ("clients", "compliance_alerts")


@pytest_asyncio.fixture(scope="function")
async def db_pool() -> asyncpg.Pool:
    try:
        pool = await asyncpg.create_pool(_DEFAULT_DB_URL, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"router integration tests: DB unreachable ({exc})")
        return  # help static analyzers see pool is unbound on this path

    skip_reason: str | None = None
    try:
        async with pool.acquire() as conn:
            for table in _REQUIRED_TABLES:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=$1)",
                    table,
                )
                if not exists:
                    skip_reason = (
                        f"router integration tests: required table '{table}' "
                        "missing (run migrations against the test DB to enable)"
                    )
                    break
        if skip_reason is None:
            yield pool
    finally:
        await pool.close()
    if skip_reason:
        pytest.skip(skip_reason)


@pytest_asyncio.fixture
async def db_tx(db_pool: asyncpg.Pool) -> asyncpg.Connection:
    async with db_pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
        finally:
            await tx.rollback()


# ── GARUDA VOA truth-freshness isolation ────────────────────────────────────
# G-FRESHNESS-FAIL-CLOSED (DECISIONS.md Q9) makes `intake.build_verdict` DECLINE
# and `pricing.price_for_case` refuse to quote whenever a real stamp is past its
# window. The real price catalogue is stamped 2026-05-06 against a 90-day window,
# so it is stale TODAY — which is correct, and is owner decision 7.
#
# Left alone, that turns four router tests red for a reason none of them is about:
# they assert 201/409 round-trips and privacy headers, and they were reading the
# real catalogue against the real clock. A test that fails because a data file
# aged is a clock, not a test — and it teaches the next person that red means
# "edit the test". The freshness path gets its own test below and in
# `services/garuda_flow/`; everywhere else it is pinned fresh.
#
# Narrow by construction: this patches only `garuda_flow.freshness`, so no other
# router's tests can notice it.
@pytest.fixture(autouse=True)
def _garuda_truth_sheets_assumed_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.garuda_flow import freshness

    def _fresh(source: str) -> freshness.FreshnessReport:
        return freshness.FreshnessReport(
            source=source,
            verdict=freshness.FreshnessVerdict.FRESH,
            stamp="2026-01-01",
            age_days=0,
            max_age_days=freshness.MAX_AGE_DAYS[source],
            detail="router conftest: pinned fresh for a test unrelated to freshness",
        )

    # Keyword-only `today`, matching the real signatures — a stub that swallows
    # everything would also hide a caller that stopped passing the civil day.
    #
    # `price_catalogue_freshness` lives in `pricing`, not in `freshness`, because it
    # reads the catalogue file the pricing service owns. The first version of this
    # fixture guarded every patch with `hasattr(freshness, name)` and therefore
    # skipped that one in silence, leaving the four tests exactly as red as before —
    # a defensive skip hiding the case it existed to handle. No guard now: a renamed
    # function must break this loudly, not quietly stop being pinned.
    from backend.services.garuda_flow import pricing

    for module, name, source in (
        (freshness, "nationality_eligibility_freshness", "nationality_eligibility"),
        (freshness, "rule_constants_freshness", "rule_constants"),
        (pricing, "price_catalogue_freshness", "price_catalogue"),
    ):
        assert hasattr(module, name), (
            f"{module.__name__}.{name} is gone — this fixture is pinning nothing and "
            "the freshness gate is silently live in tests that are not about it"
        )
        # `**_` absorbs the extra keyword-only params the real functions carry
        # (pricing's takes an optional `service`), while `today` stays REQUIRED so a
        # caller that stops passing the civil day still fails here.
        monkeypatch.setattr(
            module, name, lambda *, today, _s=source, **_: _fresh(_s)
        )
