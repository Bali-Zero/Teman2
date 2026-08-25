"""Real-database integration tests for `PostgresMagicLinkStore`
(products/garuda-voa/L4-CONTINUATION.md part 2 of 3, "Acceptance" section).

DSN resolution mirrors `garuda_orders/test_repository_integration.py`
(`INTAKE_TEST_DSN`, the variable this repo's CI already sets, with
`GARUDA_L4_TEST_DSN` as an optional local override) and the same
CI-fails-loud-not-skip posture: this file's tests are the money-adjacent
auth path (a red here means a real double-authorization or a leaked
secret), not something a missing local Postgres should quietly hide in CI.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import secrets
import uuid

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_portal.magic_link import (
    ExchangeOutcome,
    PersistencePolicyUnavailable,
    RateLimited,
)
from backend.services.garuda_portal.magic_link_store import (
    _MAX_ISSUES_PER_EMAIL_PER_WINDOW,
    PostgresMagicLinkStore,
)

_DSN = (
    os.environ.get("GARUDA_L4_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)

_RESULT_ID = "result-l4-store-0000000"
_EMAIL = "visitor@example.com"


class _CapturingSender:
    """Fake `send_email` — captures the raw token instead of calling Brevo.

    This IS the seam the real adapter's email dispatch never lets a caller
    (or a test) see the raw token any other way: `IssueOutcome` structurally
    carries no token field (magic_link.py docstring), so the only place a
    test can observe the value the store minted is this injection point —
    exactly mirroring how the real email body is the one place it lives.
    """

    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()

    async def __call__(self, *, email: str, result_id: str, raw_token: str) -> None:
        await self.queue.put(raw_token)


async def _ensure_garuda_magic_link_test_policy(conn: asyncpg.Connection) -> str:
    """Install this suite's own Zero-approved GARUDA_MAGIC_LINK retention
    policy fixture — same self-heal-first + unbackdated-lower-bound
    discipline as `garuda_orders/test_repository_integration.py`'s
    `_ensure_garuda_order_test_policy` (that function's docstring is the
    full rationale; not re-derived here to avoid the two drifting apart).
    """
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_MAGIC_LINK'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"l4-test-fixture-{uuid.uuid4().hex[:16]}"
    await conn.execute(
        """
        INSERT INTO public.visa_decision_retention_policies (
            environment, policy_scope, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor, effective_period, approved_by, approval_reference
        ) VALUES (
            'TEST', 'GARUDA_MAGIC_LINK', $1, INTERVAL '14 days',
            INTERVAL '1 hour', INTERVAL '30 days',
            'CREATED_AT', tstzrange(clock_timestamp(), NULL, '[)'),
            'zero-test-approver', 'ZERO-GARUDA-MAGIC-LINK-RETENTION-TEST-APPROVAL'
        )
        ON CONFLICT DO NOTHING
        """,
        policy_version,
    )
    return policy_version


async def _close_garuda_magic_link_test_policy(conn: asyncpg.Connection, policy_version: str) -> None:
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE policy_scope = 'GARUDA_MAGIC_LINK'
           AND policy_version = $1
           AND upper(effective_period) IS NULL
        """,
        policy_version,
    )


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(dsn=_DSN, min_size=1, max_size=4)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable Postgres for INTAKE_TEST_DSN "
                f"(or GARUDA_L4_TEST_DSN override) -- {_DSN!r} unreachable: {exc}. "
                f"This file gates the magic-link auth path; it must never "
                f"silently pass by skipping."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_account_sessions, garuda_magic_link_idempotency, garuda_magic_link_tokens"
        )
        policy_version = await _ensure_garuda_magic_link_test_policy(conn)
    yield p
    async with p.acquire() as conn:
        await _close_garuda_magic_link_test_policy(conn, policy_version)
    await p.close()


@pytest.fixture
def store(pool):
    return PostgresMagicLinkStore(pool, environment="TEST", send_email=_CapturingSender())


async def _issue_and_capture_token(store: PostgresMagicLinkStore, *, idempotency_key: str) -> str:
    outcome = await store.issue(
        idempotency_key=idempotency_key,
        result_id=_RESULT_ID,
        email=_EMAIL,
        result_session_secret="result-session-cookie-secret",
    )
    assert outcome.idempotency_replayed is False
    sender = store._send_email  # the _CapturingSender injected by the `store` fixture
    return await asyncio.wait_for(sender.queue.get(), timeout=2)


# ---------------------------------------------------------------------------
# Acceptance #1/#2 — single-use is atomic under real concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_concurrent_exchanges_of_the_same_token_exactly_one_wins(pool, store):
    """Two DIFFERENT Idempotency-Keys (never a replay of each other) racing
    the SAME token: the atomic `UPDATE ... WHERE used_at IS NULL` predicate
    is what this test proves. Manually verified red/green (modus VERIFY,
    2026-08-25): with the `AND used_at IS NULL` clause removed from
    `PostgresMagicLinkStore.exchange`'s UPDATE, this test went RED --
    `asyncpg.exceptions.RaiseError: garuda_magic_link_tokens.used_at is
    immutable once consumed`, thrown by the migration 285 DB-level guard
    trigger (`guard_garuda_magic_link_token_mutation`) when the second
    concurrent UPDATE tried to overwrite an already-consumed row. This is
    the correct red shape, not a softer one: it shows the atomic app-layer
    predicate and the DB-level immutability guard are two INDEPENDENT
    barriers against the same double-authorization, not one guard wearing
    two hats -- removing either one alone still fails closed via the
    other. Restoring the clause returned this test to green (exactly one
    winner, one loser, no unhandled exception).
    """
    raw_token = await _issue_and_capture_token(store, idempotency_key="issue-key-concurrency-1")

    results = await asyncio.gather(
        store.exchange(idempotency_key="exchange-key-A", token=raw_token),
        store.exchange(idempotency_key="exchange-key-B", token=raw_token),
    )

    authorized = [r for r in results if r.authorized]
    denied = [r for r in results if not r.authorized]
    assert len(authorized) == 1, f"expected exactly one winner, got {results!r}"
    assert len(denied) == 1, f"expected exactly one loser, got {results!r}"
    assert authorized[0].account_session_secret is not None
    assert denied[0].account_session_secret is None
    assert denied[0].security_counter == "magic_link_invalid"

    async with pool.acquire() as conn:
        sessions = await conn.fetchval("SELECT count(*) FROM garuda_account_sessions")
    assert sessions == 1, "exactly one session row may exist for a single-use token"


# ---------------------------------------------------------------------------
# Acceptance #3 — unknown / expired / consumed are byte-identical
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_expired_and_consumed_tokens_are_byte_identical(pool, store):
    # Unknown: never issued.
    unknown = await store.exchange(
        idempotency_key="exchange-key-unknown", token=secrets.token_urlsafe(32)
    )

    # Expired: inserted directly (bypassing store.issue, which always mints
    # a fresh 15-minute TTL) with a TTL short enough to have elapsed by the
    # time we exchange it -- the CHECK (expires_at > created_at) constraint
    # forbids constructing an already-past expiry directly, and the
    # immutability guard forbids backdating expires_at after the fact, so a
    # short real TTL is the only way to reach this state honestly.
    expired_raw_token = secrets.token_urlsafe(32)
    expired_hash = hashlib.sha256(expired_raw_token.encode()).hexdigest()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO garuda_magic_link_tokens (token_hash, result_id, email, environment, expires_at)
            VALUES ($1, $2, $3, 'TEST', statement_timestamp() + INTERVAL '50 milliseconds')
            """,
            expired_hash,
            _RESULT_ID,
            _EMAIL,
        )
    await asyncio.sleep(0.25)
    expired = await store.exchange(idempotency_key="exchange-key-expired", token=expired_raw_token)

    # Consumed: issue + exchange for real, then exchange AGAIN under a
    # different (non-replay) Idempotency-Key.
    consumed_raw_token = await _issue_and_capture_token(store, idempotency_key="issue-key-consumed")
    first = await store.exchange(idempotency_key="exchange-key-consumed-first", token=consumed_raw_token)
    assert first.authorized is True
    consumed = await store.exchange(
        idempotency_key="exchange-key-consumed-second", token=consumed_raw_token
    )

    expected = ExchangeOutcome(authorized=False, security_counter="magic_link_invalid")
    assert unknown == expected
    assert expired == expected
    assert consumed == expected
    assert unknown == expired == consumed


# ---------------------------------------------------------------------------
# Acceptance #4 — the raw token / raw session secret / result-session
# secret never reach a DB column or a log line.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raw_secrets_never_reach_db_columns_or_logs(pool, store, caplog):
    caplog.set_level(logging.DEBUG, logger="backend.services.garuda_portal.magic_link_store")
    presented_result_session_secret = "cookie-value-" + secrets.token_urlsafe(16)

    outcome = await store.issue(
        idempotency_key="issue-key-secrecy",
        result_id=_RESULT_ID,
        email=_EMAIL,
        result_session_secret=presented_result_session_secret,
    )
    assert outcome.idempotency_replayed is False
    raw_token = await asyncio.wait_for(store._send_email.queue.get(), timeout=2)

    exchange_outcome = await store.exchange(idempotency_key="exchange-key-secrecy", token=raw_token)
    assert exchange_outcome.authorized is True
    assert exchange_outcome.account_session_secret

    async with pool.acquire() as conn:
        all_rows = []
        for table in (
            "garuda_magic_link_tokens",
            "garuda_account_sessions",
            "garuda_magic_link_idempotency",
        ):
            all_rows.extend(await conn.fetch(f"SELECT * FROM {table}"))
        dumped_rows = "".join(repr(row) for row in all_rows)

    for secret_value, label in (
        (raw_token, "raw magic-link token"),
        (exchange_outcome.account_session_secret, "raw account-session secret"),
        (presented_result_session_secret, "presented result-session secret"),
    ):
        assert secret_value not in dumped_rows, f"{label} leaked into a DB column"
        assert secret_value not in caplog.text, f"{label} leaked into a log line"


# ---------------------------------------------------------------------------
# Fail-closed pre-check (mirrors GarudaOrderRepository's
# `_active_order_policy_available` gate, L3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_fails_closed_with_no_active_policy_for_the_environment(pool):
    # 'STAGING' has no policy row installed by this suite's fixture (only
    # 'TEST' does) -- issue() must refuse before writing anything.
    staging_store = PostgresMagicLinkStore(pool, environment="STAGING", send_email=_CapturingSender())
    with pytest.raises(PersistencePolicyUnavailable):
        await staging_store.issue(
            idempotency_key="issue-key-no-policy",
            result_id=_RESULT_ID,
            email=_EMAIL,
            result_session_secret="whatever",
        )
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM garuda_magic_link_tokens WHERE environment = 'STAGING'"
        )
    assert count == 0, "a fail-closed issue() must not write a token row"


# ---------------------------------------------------------------------------
# Idempotency replay — issue and exchange
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_replay_is_a_noop_second_call(pool, store):
    first = await store.issue(
        idempotency_key="issue-key-replay",
        result_id=_RESULT_ID,
        email=_EMAIL,
        result_session_secret="secret-1",
    )
    assert first.idempotency_replayed is False
    second = await store.issue(
        idempotency_key="issue-key-replay",
        result_id=_RESULT_ID,
        email=_EMAIL,
        result_session_secret="secret-1",
    )
    assert second.idempotency_replayed is True

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM garuda_magic_link_tokens")
    assert count == 1, "a replayed issue must not mint a second token"


@pytest.mark.asyncio
async def test_exchange_replay_returns_same_outcome_without_a_second_session(pool, store):
    raw_token = await _issue_and_capture_token(store, idempotency_key="issue-key-exchange-replay")

    first = await store.exchange(idempotency_key="exchange-key-replay", token=raw_token)
    assert first.authorized is True
    assert first.idempotency_replayed is False
    assert first.account_session_secret is not None

    second = await store.exchange(idempotency_key="exchange-key-replay", token=raw_token)
    assert second.authorized is True
    assert second.idempotency_replayed is True
    assert second.result_id == first.result_id
    # DECISIONS.md / router contract: a replay never re-emits the secret
    # (the router only Set-Cookies on a fresh, non-replayed exchange).
    assert second.account_session_secret is None

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM garuda_account_sessions")
    assert count == 1, "a replayed exchange must not mint a second session"


# ---------------------------------------------------------------------------
# Rate limiting on issue (team-lead review, 2026-08-25 — RATE_LIMITED was
# declared in the contract but unreachable on every code path before this).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_raises_rate_limited_after_the_per_email_window_is_exhausted(pool, store):
    email = f"flood-target-{uuid.uuid4().hex[:8]}@example.com"

    for i in range(_MAX_ISSUES_PER_EMAIL_PER_WINDOW):
        outcome = await store.issue(
            idempotency_key=f"issue-key-flood-{i}",
            result_id=_RESULT_ID,
            email=email,
            result_session_secret="whatever",
        )
        assert outcome.idempotency_replayed is False

    with pytest.raises(RateLimited):
        await store.issue(
            idempotency_key="issue-key-flood-over-limit",
            result_id=_RESULT_ID,
            email=email,
            result_session_secret="whatever",
        )

    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM garuda_magic_link_tokens WHERE email = $1", email
        )
    assert count == _MAX_ISSUES_PER_EMAIL_PER_WINDOW, (
        "the rate-limited attempt must not have minted a token — the transaction "
        "raising RateLimited must roll back its own idempotency reservation too"
    )


@pytest.mark.asyncio
async def test_issue_rate_limit_does_not_double_count_an_exact_replay(pool, store):
    """A replay of an already-issued request must not consume another slot
    in the window — otherwise a client's own retry-after-timeout starves
    out its own legitimate follow-up request."""
    email = f"replay-safe-{uuid.uuid4().hex[:8]}@example.com"

    for i in range(_MAX_ISSUES_PER_EMAIL_PER_WINDOW):
        await store.issue(
            idempotency_key=f"issue-key-replaysafe-{i}",
            result_id=_RESULT_ID,
            email=email,
            result_session_secret="whatever",
        )

    # Replay the FIRST request under its original key — must succeed as a
    # replay, not count as a 6th fresh issue, and must not itself raise.
    replay = await store.issue(
        idempotency_key="issue-key-replaysafe-0",
        result_id=_RESULT_ID,
        email=email,
        result_session_secret="whatever",
    )
    assert replay.idempotency_replayed is True

    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM garuda_magic_link_tokens WHERE email = $1", email
        )
    assert count == _MAX_ISSUES_PER_EMAIL_PER_WINDOW


# ---------------------------------------------------------------------------
# Timing equivalence across the three deny paths (team-lead review,
# 2026-08-25 — byte-identical RESPONSES are necessary but not sufficient;
# the adapter must not do measurably different WORK per deny reason).
# ---------------------------------------------------------------------------


def _make_counting_connection_class(counts: list[int]) -> type:
    """A `connection_class` for `asyncpg.create_pool` that counts every
    `fetchrow`/`fetchval`/`execute` round-trip. `counts` is a shared
    single-element list (closed over, not a class attribute) so every
    connection the pool hands out reports into the SAME counter — the
    thing under test is the total number of statements one `exchange()`
    call issues, not which specific connection issued them.
    """

    class _CountingConnection(asyncpg.Connection):
        async def fetchrow(self, *args, **kwargs):
            counts[0] += 1
            return await super().fetchrow(*args, **kwargs)

        async def fetchval(self, *args, **kwargs):
            counts[0] += 1
            return await super().fetchval(*args, **kwargs)

        async def execute(self, *args, **kwargs):
            counts[0] += 1
            return await super().execute(*args, **kwargs)

    return _CountingConnection


@pytest.fixture
async def counting_pool():
    """A SEPARATE pool (own connection class) so this file's other tests'
    connections are never instrumented — only exchange() calls made
    through `counting_store` below are counted."""
    counts = [0]
    p = await asyncpg.create_pool(
        dsn=_DSN, min_size=1, max_size=2, connection_class=_make_counting_connection_class(counts)
    )
    yield p, counts
    await p.close()


@pytest.mark.asyncio
async def test_deny_paths_execute_the_same_query_shape(pool, store, counting_pool):
    """Structural invariant: unknown / expired / consumed must each cause
    `exchange()` to issue the SAME NUMBER of statements. This is the
    mechanism-level property that makes engine-level timing constancy at
    least possible — a naive implementation that does "return immediately
    on no row" for one case and "look up, then compare, then return" for
    another would fail this test long before any clock ever ran, which is
    exactly why it is the primary, CI-stable gate (see
    `test_deny_path_timing_does_not_separate_under_repetition` below for
    the secondary, advisory empirical signal).
    """
    counting_conn_pool, counts = counting_pool
    counting_store = PostgresMagicLinkStore(
        counting_conn_pool, environment="TEST", send_email=_CapturingSender()
    )

    # Unknown.
    counts[0] = 0
    await counting_store.exchange(
        idempotency_key="exchange-key-shape-unknown", token=secrets.token_urlsafe(32)
    )
    unknown_count = counts[0]

    # Expired (same construction as the byte-identical-outcome test above).
    expired_raw_token = secrets.token_urlsafe(32)
    expired_hash = hashlib.sha256(expired_raw_token.encode()).hexdigest()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO garuda_magic_link_tokens (token_hash, result_id, email, environment, expires_at)
            VALUES ($1, $2, $3, 'TEST', statement_timestamp() + INTERVAL '50 milliseconds')
            """,
            expired_hash,
            _RESULT_ID,
            _EMAIL,
        )
    await asyncio.sleep(0.25)
    counts[0] = 0
    await counting_store.exchange(idempotency_key="exchange-key-shape-expired", token=expired_raw_token)
    expired_count = counts[0]

    # Consumed.
    consumed_raw_token = await _issue_and_capture_token(store, idempotency_key="issue-key-shape-consumed")
    await store.exchange(idempotency_key="exchange-key-shape-consumed-first", token=consumed_raw_token)
    counts[0] = 0
    await counting_store.exchange(
        idempotency_key="exchange-key-shape-consumed-second", token=consumed_raw_token
    )
    consumed_count = counts[0]

    assert unknown_count == expired_count == consumed_count, (
        f"deny paths issued different numbers of statements: "
        f"unknown={unknown_count} expired={expired_count} consumed={consumed_count}"
    )


@pytest.mark.asyncio
async def test_deny_path_timing_does_not_separate_under_repetition(pool, store):
    """Secondary, ADVISORY signal only — not the primary gate (see the
    structural test above for that). CI runners are shared vCPUs with no
    isolation guarantee; a single sample's wall-clock time is dominated by
    scheduler jitter, not by this adapter's own logic, and asserting a
    tight bound here would be exactly the kind of noisy, non-reproducible
    check this repo's verification discipline warns against. What IS
    reliably true, and what this test actually checks: averaged over many
    repetitions, no deny path's MEAN latency should separate from the
    others by an order of magnitude — a real "return immediately on no
    row" shortcut would show up as a large, not a marginal, gap even
    through CI noise. The tolerance below (5x) is deliberately generous;
    it exists to catch a gross regression, not to certify constant-time
    behaviour (the class docstring explains why true constant-time against
    the underlying Postgres index is not attempted here at all).
    """
    import time

    trials = 30

    async def _time_unknown() -> float:
        start = time.perf_counter()
        await store.exchange(idempotency_key=f"timing-unknown-{uuid.uuid4().hex}", token=secrets.token_urlsafe(32))
        return time.perf_counter() - start

    async def _time_consumed(raw_token: str) -> float:
        start = time.perf_counter()
        await store.exchange(idempotency_key=f"timing-consumed-{uuid.uuid4().hex}", token=raw_token)
        return time.perf_counter() - start

    # One consumed token, exchanged repeatedly under fresh keys — each
    # exchange after the first is a deny (already used_at), never a replay
    # (fresh Idempotency-Key every time).
    consumed_raw_token = await _issue_and_capture_token(store, idempotency_key="issue-key-timing-consumed")
    await store.exchange(idempotency_key="exchange-key-timing-consumed-prime", token=consumed_raw_token)

    unknown_samples = [await _time_unknown() for _ in range(trials)]
    consumed_samples = [await _time_consumed(consumed_raw_token) for _ in range(trials)]

    unknown_mean = sum(unknown_samples) / len(unknown_samples)
    consumed_mean = sum(consumed_samples) / len(consumed_samples)
    ratio = max(unknown_mean, consumed_mean) / max(min(unknown_mean, consumed_mean), 1e-9)

    assert ratio < 5.0, (
        f"unknown-vs-consumed deny latency separated by {ratio:.1f}x "
        f"(unknown mean={unknown_mean * 1000:.3f}ms, consumed mean={consumed_mean * 1000:.3f}ms) "
        f"— investigate for a short-circuit branch, not just CI noise"
    )
