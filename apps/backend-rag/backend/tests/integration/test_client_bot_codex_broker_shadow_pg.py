"""B1c — client-bot goldens through the REAL codex-broker TRANSPORT leg,
against REAL PostgreSQL with migration 290 applied (I DUE BOT rung 1b).

Rung 1b, as the mandate names it, is "shadow against recorded fixtures":
run every B6b golden through the codex-broker leg for real and report what
the gates did. This file does the OFFER + WAIT half of that for real, and
is explicit about the half it deliberately does NOT do.

WHAT THIS FILE PROVES, MEASURED, NOT MOCKED:

- ``CodexBrokerClientBrainProvider`` / ``wa_broker.offer_client_job`` /
  ``wa_broker.wait_for_job`` run against a REAL Postgres schema built from
  the REAL migration 270-274 + 290 DDL (the exact throwaway-schema pattern
  ``test_wa_broker_pg.py`` already established for the WA-outbox leg) —
  every CHECK constraint migration 290 added
  (``broker_jobs_kind_identifiers_check`` etc.) is enforced by Postgres
  itself, not asserted against a scripted double. This is NEW coverage:
  ``offer_client_job`` is otherwise exercised only via ``ScriptedConn``
  (``backend/tests/unit/services/test_wa_broker.py``, 7 cases) and a
  ``_FakePool`` (``backend/tests/services/client_bot/test_codex_broker.py``)
  — neither touches real SQL, so migration 290's actual shape against a
  real database had never been measured before this file.
- ``ClientBrainProviderRouter.run_shadow()`` swallowing a REAL
  ``ProviderFailure`` (not a scripted one) and returning ``None`` —
  ``test_provider_router.py`` exercises that contract only against
  ``_FakeProvider``.
- The circuit breaker (``wa_broker_gauge.consecutive_failures``) folding a
  client-bot (``mode='serve'``) DEADLINE exactly like a WA-leg one — a real,
  measured consequence of F1's "do not create a second jobs table": the
  breaker cannot tell "offered, nobody ever claims it" apart from "claimed,
  then failed." Left here as a documented finding, not "fixed" — this file
  owns no doctrine.

WHAT THIS FILE DELIBERATELY DOES NOT PROVE — the ChatGPT/codex-exec leg:

Every golden below times out (``ProviderFailureKind.TIMEOUT``) because
nothing in this test process ever claims the ``broker_jobs`` row it offers.
That is not a bug this file works around; it is the honest, correct
classification of the two reasons a live claimant is unreachable from here:

1. INFRA. The only thing that claims a real ``client_answer_v1`` job is
   ``wa_codex_daemon.py``, running on Pro as the login-less ``zantara-codex``
   user, polling ``WA_BROKER_BASE_URL`` (an HTTP endpoint, not this schema)
   with credentials that live ONLY in a root-owned
   ``/Users/zantara-codex/.wa-codex-broker.env`` on Pro — invisible to this
   worktree, this machine (Mini), or this lane. Migration 290 itself is not
   applied to whatever Postgres that daemon's HTTP endpoint actually reads
   (verified: it exists only in ``feature/due-bot``'s ``migrations_v2/``,
   unmerged to ``main``, undeployed). Even with DB write credentials to that
   live Postgres, a fixture-driven offer would still need the migration
   applied there first — out of scope for a shadow-fixtures lane.
2. GOVERNANCE. ``backend/llm/codex_exec_client.py``'s own module docstring
   (2026-08-15 Legge-5 ruling) authorizes exactly ONE live consumer:
   "this module may be used only by the human-run offline evidence
   harness," widened by the 2026-08-25 correction to cover
   ``wa_codex_daemon.py``'s specific, reviewed production wiring — and
   nothing else: "Any FURTHER live use beyond what wa_codex_daemon.py
   already does still requires a separate runtime design, security/privacy
   review, context-parity evidence, and explicit activation authorization;
   none is supplied by this file or ruling." Standing up a second consumer
   here (importing ``WaCodexDaemon``/``CodexExecClient`` to drive a REAL
   ``codex exec`` from a Mini-side pytest process) would be exactly that
   unauthorized further live use — and the B1c mandate itself reserves
   "doctrine alignment [for codex_exec_client.py]" as a separate unit. This
   file therefore imports neither module, directly or transitively.

Net: rung 1b's MODEL leg is NOT reachable from a test/harness context on
this machine today, for the two reasons above — reported precisely, per
the mandate, rather than substituted with ``fake_codex_broker.py`` (which
would prove the adapter's plumbing and nothing about the ChatGPT leg) to
manufacture a green number.

PII (SYMBIOSIS Law 2 / CLAUDE.md #14): every golden fixture is synthetic
(``backend/tests/duebot/goldens/builders.py`` — deterministic, fabricated
Indonesian-regulation text, no real client data). Nothing here logs a
prompt/answer body; only ids, job_kind/state/outcome, and the closed
``ProviderFailureKind`` vocabulary ever reach an assertion or a log line.

Connects to ``TEST_DATABASE_URL`` (same convention as ``test_wa_broker_pg.py``
— CI provides the postgres:15 service); fail-hard-if-absent (scar family
#2: a suite that quietly skips when the DB is unreachable is exactly the
"green theater" this mandate exists to refuse).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.services.client_bot.contracts import BrainRequest
from backend.services.client_bot.policy.types import GateVerdict
from backend.services.client_bot.provider_router import ClientBrainProviderRouter
from backend.services.client_bot.providers.base import ProviderFailure, ProviderFailureKind
from backend.services.client_bot.providers.codex_broker import CodexBrokerClientBrainProvider
from backend.tests.duebot.goldens.builders import make_brain_request
from backend.tests.duebot.goldens.fixtures import CLIENT_GOLDENS, ClientGoldenFixture

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"

# Every migration that has ever touched broker_jobs/wa_broker_gauge, in
# order (same discipline as test_wa_broker_pg.py's own _BROKER_MIGRATIONS —
# verified 2026-08-26 that nothing between 274 and 290 touches either
# table: `grep -l broker_jobs backend/db/migrations_v2/27[5-9]*.sql
# backend/db/migrations_v2/28*.sql` matches nothing).
_BROKER_MIGRATIONS = (
    _MIGRATIONS_DIR / "270_wa_broker_jobs.sql",
    _MIGRATIONS_DIR / "271_wa_broker_gauge_half_open_at.sql",
    _MIGRATIONS_DIR / "272_wa_broker_package_text.sql",
    _MIGRATIONS_DIR / "273_wa_broker_completion_digest.sql",
    _MIGRATIONS_DIR / "274_wa_broker_completed_at_check.sql",
    _MIGRATIONS_DIR / "290_broker_jobs_client_bot.sql",
)

_SCHEMA = "client_bot_codex_broker_shadow_it"

# Minimal stand-ins for the two parent tables migration 270's FKs reference
# — identical to test_wa_broker_pg.py's. A client-bot row never populates
# outbox_id/thread_id (migration 290's CHECK forbids it), but the DDL still
# needs the referenced tables to exist to apply at all.
_PARENT_STUBS = """
CREATE TABLE wa_outbox (
    id BIGSERIAL PRIMARY KEY,
    claim_token UUID,
    status TEXT NOT NULL DEFAULT 'generating'
);
CREATE TABLE meta_inbox_threads (
    thread_id BIGSERIAL PRIMARY KEY
);
"""

# Short enough to keep 17 sequential real-Postgres round trips fast; long
# enough (10x wa_broker.WAIT_POLL_SECONDS=0.2s) to exercise the real poll
# loop across several iterations rather than resolving on the first one.
_SHADOW_DEADLINE_S = 2

# The two client.* defect classes whose expected_decision is DROP before
# generation is ever attempted (grounding=None by construction — see
# fixtures.py's own comments at each site) — structurally impossible to
# offer to a provider, not an oversight. Asserted, not just asserted-away.
_NO_GROUNDING_CASE_IDS = frozenset(
    {
        "client-human-takeover-thread-epoch-race-001",
        "client-duplicate-meta-delivery-001",
    }
)


def _runnable_goldens() -> list[ClientGoldenFixture]:
    return [fx for fx in CLIENT_GOLDENS if fx.grounding is not None]


def _skipped_goldens() -> list[ClientGoldenFixture]:
    return [fx for fx in CLIENT_GOLDENS if fx.grounding is None]


def _request_for(fx: ClientGoldenFixture) -> BrainRequest:
    return make_brain_request(
        fx.case_id,
        message=fx.message,
        profile=fx.profile,
        grounding=fx.grounding,
        # 3x the provider's own configured deadline_s so _effective_deadline_s
        # (codex_broker.py) is bounded by the provider's budget, not by this
        # request field — the thing under test is the BROKER's own deadline.
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=_SHADOW_DEADLINE_S * 3),
    )


@pytest_asyncio.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    """Fresh schema per test — same isolation shape as test_wa_broker_pg.py.
    Function-scoped deliberately: each golden gets its OWN wa_broker_gauge,
    so a run of 17 goldens never trips BREAKER_TRIP_AFTER=3 against itself
    and masks TIMEOUT as BREAKER_OPEN for the later goldens in the list.
    """
    c = await asyncpg.connect(_DB_URL)
    try:
        await c.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
        await c.execute(f"CREATE SCHEMA {_SCHEMA}")
        await c.execute(f"SET search_path TO {_SCHEMA}")
        await c.execute(_PARENT_STUBS)
        for migration in _BROKER_MIGRATIONS:
            forward, _rollback = split_migration_sql(migration.read_text(encoding="utf-8"))
            await c.execute(forward)
        yield c
    finally:
        await c.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
        await c.close()


@pytest_asyncio.fixture
async def pool(conn: asyncpg.Connection) -> AsyncIterator[asyncpg.Pool]:
    """Pool bound to the same throwaway schema — CodexBrokerClientBrainProvider
    is constructed with a Pool, never a bare Connection."""
    p = await asyncpg.create_pool(
        _DB_URL,
        min_size=1,
        max_size=3,
        server_settings={"search_path": _SCHEMA},
    )
    try:
        yield p
    finally:
        await p.close()


async def _seed_alive_gauge(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        INSERT INTO wa_broker_gauge (id, broker_last_seen_at, updated_at)
        VALUES (1, now(), now())
        ON CONFLICT (id) DO UPDATE
        SET broker_last_seen_at = now(), updated_at = now()
        """
    )


# ── innocence: the 2 excluded goldens are excluded for a structural reason,
#    not silently dropped ────────────────────────────────────────────────


def test_two_goldens_have_no_grounding_and_are_structurally_unreachable() -> None:
    skipped = _skipped_goldens()
    assert {fx.case_id for fx in skipped} == _NO_GROUNDING_CASE_IDS
    for fx in skipped:
        assert fx.expected_decision.verdict is GateVerdict.DROP, (
            f"{fx.case_id}: excluded from this shadow run because it carries no "
            "GroundingBundle at all (BrainRequest.grounding is non-Optional, so no "
            "BrainRequest — and therefore no provider call — can even be constructed for "
            "it). Verified reason: FinalPolicyGate DROPs this class before generation is "
            "ever attempted. If this class ever stops being a DROP-before-generation case "
            "it needs a real grounding bundle and a seat back in the runnable set — not a "
            "silent skip."
        )
    assert len(_runnable_goldens()) == 17


# ── the pass matrix: every runnable golden, offered for real ──────────────


@pytest.mark.parametrize("fx", _runnable_goldens(), ids=lambda fx: fx.case_id)
async def test_golden_offered_to_real_broker_times_out_with_no_live_claimant(
    fx: ClientGoldenFixture, conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    """Offers this golden's real wire envelope onto a real broker_jobs row
    (migration 290's CHECK constraints enforced by Postgres), then records
    what the real wait_for_job poll loop does with nobody claiming it — see
    module docstring for why TIMEOUT is the correct, not-a-bug outcome
    here, and what it does/does not prove.
    """
    await _seed_alive_gauge(conn)
    provider = CodexBrokerClientBrainProvider(pool, deadline_s=_SHADOW_DEADLINE_S)
    request = _request_for(fx)

    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.provider_name == "codex_broker"
    assert exc_info.value.kind is ProviderFailureKind.TIMEOUT
    assert exc_info.value.detail == "deadline"

    # Real SQL proof, not a mocked call-count: the offer really inserted a
    # client_answer_v1 row, and wait_for_job really CASed it to expired.
    row = await conn.fetchrow(
        "SELECT job_kind, surface, request_id, state, outcome, output_schema_version, "
        "outbox_id, thread_id "
        "FROM broker_jobs WHERE request_id = $1",
        request.request_id,
    )
    assert row is not None, f"{fx.case_id}: offer_client_job never inserted a real row"
    assert row["job_kind"] == "client_answer_v1"
    assert row["surface"] == fx.message.surface.value
    assert row["output_schema_version"] == "1.0"
    assert row["outbox_id"] is None and row["thread_id"] is None  # migration 290's own CHECK
    assert row["state"] == "expired"
    assert row["outcome"] == "expired_deadline"

    # The breaker finding: a client-bot (mode='serve') DEADLINE folds into
    # the SAME consecutive_failures counter as a WA-leg one (wait_for_job's
    # `if expired["mode"] == "serve"` branch does not distinguish job_kind).
    # Documented here as a measured fact, not fixed — not this lane's call.
    gauge = await conn.fetchrow(
        "SELECT breaker_state, consecutive_failures FROM wa_broker_gauge WHERE id = 1"
    )
    assert gauge["consecutive_failures"] == 1
    assert gauge["breaker_state"] == "closed"  # 1 < BREAKER_TRIP_AFTER (3)


# ── guilt: proves the TIMEOUT classification above is not vacuous — a
#    DIFFERENT real DB state produces a DIFFERENT typed failure ───────────


async def test_golden_offered_with_no_gauge_row_is_broker_absent_not_timeout(
    conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    """Innocence check for every assertion above: TIMEOUT is not just
    "whatever this harness always says" — deliberately skip
    _seed_alive_gauge (no wa_broker_gauge row at all) and the SAME real
    offer_client_job/wait_for_job path must classify this differently:
    BROKER_ABSENT at the admission check, never reaching wait_for_job's
    poll loop at all. If this test ever started reporting TIMEOUT too, the
    pass matrix above would be discriminating nothing.
    """
    fx = _runnable_goldens()[0]
    provider = CodexBrokerClientBrainProvider(pool, deadline_s=_SHADOW_DEADLINE_S)
    request = _request_for(fx)

    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.kind is ProviderFailureKind.HOST_OFFLINE
    assert exc_info.value.detail == "offer:broker_absent"
    # No row was ever inserted — admission failed before the INSERT.
    assert await conn.fetchval(
        "SELECT count(*) FROM broker_jobs WHERE request_id = $1", request.request_id
    ) == 0


# ── the router-level wiring the mandate asked for, explicitly ─────────────


async def test_router_run_shadow_swallows_a_real_timeout_and_returns_none(
    conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    """The minimal router wiring rung 1b calls for: a
    ClientBrainProviderRouter whose mapping contains ONLY the codex_broker
    provider. gemini.py is deliberately NOT built here — routing rule 6
    (provider_router.py's own docstring) is that run_shadow() never touches
    route(), so the primary provider need not resolve for this call.

    Proves routing rule 6's safety contract against a REAL ProviderFailure
    for the first time — test_provider_router.py's own
    test_run_shadow_swallows_failure_and_returns_none exercises the same
    contract, but only against a scripted _FakeProvider.
    """
    await _seed_alive_gauge(conn)
    fx = _runnable_goldens()[0]
    provider = CodexBrokerClientBrainProvider(pool, deadline_s=_SHADOW_DEADLINE_S)
    router = ClientBrainProviderRouter(
        {"codex_broker": provider},
        primary_provider="gemini",  # never resolved — routing rule 6
        fallback_provider=None,
        shadow_provider="codex_broker",
        codex_broker_enabled=True,
        future_metered_enabled=False,
    )

    result = await router.run_shadow(_request_for(fx))

    assert result is None
