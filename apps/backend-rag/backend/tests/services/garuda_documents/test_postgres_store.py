"""`PostgresDocumentStore` against a REAL PostgreSQL cluster: the properties P1-P11 and H1
of SPEC v2 (`evidence/.../SPEC-v2.md`), each with the guilt mutation that turns it red.

This file is a rewrite, not a repair. Its predecessor was suspended after three refuter
rounds reopened one class -- a test that pins a FORM and calls it a PROPERTY: one truncation
cut, then a longer prefix, then every prefix and no suffix; a race whose barrier coordinated
the probes but not the transactions. Every test here states the property it proves in its
docstring, and every declared limit is cited by its id from the brief's `limits:` block (L1..L8)
and stated nowhere else in stronger or weaker words.

Harness, in three parts:

1. A DISPOSABLE DATABASE per test (§4.1): uuid-suffixed database and cluster roles, migration
   304's real forward SQL with `visa_ledger_owner` substituted, dropped in teardown.
   `nuzantara_dev` and `nuzantara_test` are never touched.
2. The SEAM (§4.2): `PostgresDocumentStore(_hooks=_CommitHooks(...))`. `after_lookup` fires
   inside the transaction after `SELECT ... FOR UPDATE`; two racers blocked there have BOTH
   observed the key absent, so neither can have committed and the second INSERT MUST collide
   on the primary key -- the collision is structural, not scheduling luck.
   `after_collision_before_reread` fires after the collision unwound the transaction and
   before the fresh-connection re-read: holding a loser there is how schedules C and D purge
   the winner or re-occupy the key in between.
3. REPORT-LEVEL REDACTION (§5): every connect goes through `_connect`, which takes no DSN
   argument, catches `BaseException`, and raises the redacted outcome `from None` with
   `pytrace=False`. H1 is proved by a SUBPROCESS pytest run with a sentinel password, not by
   inspecting a message.

CI runs this on the PostgreSQL 15 service container via `INTAKE_TEST_DSN`; PG17 is a measured
local run recorded in the brief (limit L3). Under `CI` every degraded case FAILS, never skips.
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.db.migration_base import split_migration_sql
from backend.services.garuda_documents.models import (
    LowConfidenceOutcome,
    PassportReviewFieldName,
    ProcessingOutcome,
    ReadyOutcome,
    ReviewField,
    UncertainReviewField,
    UnreadableOutcome,
)
from backend.services.garuda_documents.ports import (
    DuplicateReviewFieldPath,
    IdempotencyConflictError,
    IdempotencyKeyVanished,
    ReadyOutcomeValueNotPersisted,
)
from backend.services.garuda_documents.postgres_store import (
    _OPERATION_UPLOAD_INTAKE_DOCUMENT,
    PostgresDocumentStore,
    _CommitHooks,
    _HookContext,
    _scoped_key_sha256,
)
from backend.services.garuda_flow.public_api import PersistencePolicyUnavailable
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

pytestmark = pytest.mark.asyncio

_ADMIN_URL = (
    os.environ.get("GARUDA_DOCUMENTS_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)
_ENV = "TEST"
_BACKEND_ROOT = Path(__file__).resolve().parents[4]
_MIGRATION_304 = _BACKEND_ROOT / "backend" / "db" / "migrations_v2" / "304_garuda_documents.sql"
_CANONICAL = tuple(PassportReviewFieldName)

# Real actors are `result_id`s: 32 hex characters. Two of them for the actor-scoping tests;
# NOT a witness pair for the injectivity property -- §3 derives those from the mutation
# model instead of hand-picking them, which is the whole point of that section.
_ACTOR_1 = "0123456789abcdef0123456789abcdef"
_ACTOR_2 = "fedcba9876543210fedcba9876543210"


# ---------------------------------------------------------------------------
# DSN handling -- the redaction is a property of the REPORT (H1, §5)
# ---------------------------------------------------------------------------


def _with_database(dsn: str, database: str) -> str:
    """Replace ONLY the database component, structurally. `rsplit("/", 1)` would rewrite
    the query of a DSN carrying a slash there and leave the shared database in place."""
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _redacted(dsn: str) -> str:
    """TOTAL: never raises. `urlsplit(...).port` raises ValueError on a non-numeric port
    and a malformed IPv6 literal raises on `.hostname`; either, thrown INSIDE `_connect`'s
    handler before the redacted outcome is built, would leave an ordinary traceback whose
    frame arguments carry the DSN (Sol, PR2a-v2 round O1, finding 3). A DSN this cannot
    parse is described by a constant, not echoed."""
    try:
        parts = urlsplit(dsn)
        user = (
            f"{parts.username}:***@"
            if parts.password
            else (f"{parts.username}@" if parts.username else "")
        )
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://{user}{host}{port}{parts.path}"
    except ValueError:
        return "<unparseable dsn: ***>"


_CI_MUST_NOT_SKIP = (
    "under CI this must not be skipped: this file is the only thing exercising the store "
    "against a real database"
)


async def _connect(database: str | None) -> asyncpg.Connection:
    """The ONLY way this module opens a connection (§5). Takes a database NAME, never a
    DSN, so no frame pytest could render carries a secret as an argument. Any failure --
    unreachable server, a DSN asyncpg's parser rejects before opening a socket, anything --
    is re-raised as the redacted pytest outcome with TWO layers: `pytrace=False` makes
    pytest print the message alone (no frame, no locals, under `--tb=long` and under
    `--showlocals` alike), and `from None` severs the chain so the original
    `asyncpg.connect(dsn=...)` frame is not there to render. MEASURED (brief
    `guilt_mutations`, H1 rows): `pytrace=False` alone still passes the subprocess harness;
    `from None` alone passes at `--tb=long` but this function's own `dsn` local renders
    under `--showlocals`. So `pytrace=False` is the load-bearing layer and `from None` is
    defence in depth (brief `spec_errata` against SPEC v2 §5). Under `CI` the outcome is
    a FAILURE; outside CI it is a skip with the same redacted reason."""
    dsn = _ADMIN_URL if database is None else _with_database(_ADMIN_URL, database)
    try:
        return await asyncpg.connect(dsn)
    except BaseException as exc:
        reason = f"no Postgres reachable at {_redacted(dsn)} ({type(exc).__name__})"
        if os.environ.get("CI"):
            raise pytest.fail.Exception(f"{reason} -- {_CI_MUST_NOT_SKIP}", pytrace=False) from None
        raise pytest.skip.Exception(reason, pytrace=False) from None


# ---------------------------------------------------------------------------
# Disposable database (§4.1)
# ---------------------------------------------------------------------------

_RETENTION_POLICIES_DDL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE public.visa_decision_retention_policies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    environment         TEXT NOT NULL
        CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    policy_scope        TEXT NOT NULL
        CHECK (policy_scope IN ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER', 'GARUDA_MAGIC_LINK')),
    policy_version      TEXT NOT NULL
        CHECK (policy_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'),
    retention_interval  INTERVAL NOT NULL
        CHECK (retention_interval > INTERVAL '0 seconds'),
    idempotency_retention_interval INTERVAL NOT NULL,
    legal_hold_review_interval INTERVAL NOT NULL
        CHECK (legal_hold_review_interval > INTERVAL '0 seconds'),
    retention_anchor    TEXT NOT NULL
        CHECK (retention_anchor IN ('EVALUATED_AT', 'CREATED_AT')),
    effective_period    TSTZRANGE NOT NULL,
    approved_by         TEXT NOT NULL
        CHECK (approved_by ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$'),
    approval_reference  TEXT NOT NULL
        CHECK (length(approval_reference) BETWEEN 1 AND 2048),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (NOT isempty(effective_period)),
    CHECK (lower(effective_period) IS NOT NULL),
    CHECK (lower_inc(effective_period)),
    CHECK (upper(effective_period) IS NULL OR NOT upper_inc(effective_period)),
    CHECK (
        idempotency_retention_interval > INTERVAL '0 seconds'
        AND idempotency_retention_interval <= retention_interval
    ),
    UNIQUE (environment, policy_version)
);
"""
# ^ migration 264's shape, including ITS `idempotency_retention_interval <= retention_interval`
#   CHECK (`<=`, not equality; it is 264's, not 304's -- SPEC v2 §7 correction of record).


def _migration_304_forward(ledger_role: str) -> str:
    forward_sql, _rollback_sql = split_migration_sql(_MIGRATION_304.read_text(encoding="utf-8"))
    # The migration names `visa_ledger_owner` literally, as it must in production; a
    # cluster role cannot be scoped to one database, so a uuid-suffixed name stands in.
    return forward_sql.replace("visa_ledger_owner", ledger_role)


@dataclass(frozen=True, slots=True)
class _Sandbox:
    database: str
    dsn: str
    ledger: str
    app: str


@asynccontextmanager
async def _sandbox(retention: str) -> AsyncIterator[_Sandbox]:
    """A database + two roles + migration 304 + ONE active GARUDA_DOCUMENT policy whose
    `retention_interval` is `retention` (30 days for ordinary tests; 2 seconds for
    schedules C and D, which need a row to become legally purgeable within the test)."""
    suffix = uuid.uuid4().hex[:12]
    database = f"nuzantara_test_gdoc_{suffix}"
    ledger = f"gdoc_ledger_{suffix}"
    app = f"gdoc_app_{suffix}"

    admin = await _connect(None)
    try:
        if not await admin.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"):
            reason = f"the connecting role for {_redacted(_ADMIN_URL)} is not a superuser"
            if os.environ.get("CI"):
                pytest.fail(f"{reason} -- {_CI_MUST_NOT_SKIP}", pytrace=False)
            pytest.skip(reason)
        await admin.execute(f'CREATE DATABASE "{database}"')
        await admin.execute(f'CREATE ROLE "{ledger}" NOLOGIN')
        await admin.execute(f'CREATE ROLE "{app}" NOLOGIN')
    finally:
        await admin.close()

    try:
        conn = await _connect(database)
        try:
            await conn.execute(_RETENTION_POLICIES_DDL)
            await conn.execute(
                f'ALTER TABLE public.visa_decision_retention_policies OWNER TO "{ledger}"'
            )
            await conn.execute(
                f'GRANT SELECT ON TABLE public.visa_decision_retention_policies TO "{app}"'
            )
            await conn.execute(_migration_304_forward(ledger))
            await conn.execute(f'GRANT SELECT, INSERT ON TABLE public.garuda_documents TO "{app}"')
            await conn.execute(
                f'GRANT SELECT, INSERT ON TABLE public.garuda_document_review_fields TO "{app}"'
            )
            await conn.execute(
                """
                INSERT INTO public.visa_decision_retention_policies (
                    environment, policy_scope, policy_version, retention_interval,
                    idempotency_retention_interval, legal_hold_review_interval,
                    retention_anchor, effective_period, approved_by, approval_reference
                ) VALUES (
                    'TEST', 'GARUDA_DOCUMENT', $1, $2::text::interval,
                    $2::text::interval, INTERVAL '30 days',
                    -- `$2::text::interval`, not `$2::interval`: asyncpg infers the parameter
                    -- type from the cast and would demand a `timedelta` for `interval`,
                    -- rejecting the string ('str' object has no attribute 'days').
                    -- Casting through text keeps the interval literal readable here.
                    'CREATED_AT', tstzrange(clock_timestamp(), NULL, '[)'),
                    'zero-test-approver', 'ZERO-GARUDA-DOCUMENT-RETENTION-TEST-APPROVAL'
                )
                """,
                f"gdoc-test-policy-{suffix}",
                retention,
            )
        finally:
            await conn.close()
        yield _Sandbox(
            database=database, dsn=_with_database(_ADMIN_URL, database), ledger=ledger, app=app
        )
    finally:
        admin = await _connect(None)
        try:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
                database,
            )
            await admin.execute(f'DROP DATABASE IF EXISTS "{database}"')
            for role in (app, ledger):
                await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        finally:
            await admin.close()


@pytest.fixture
async def sandbox() -> AsyncIterator[_Sandbox]:
    async with _sandbox("30 days") as sb:
        yield sb


@pytest.fixture
async def short_sandbox() -> AsyncIterator[_Sandbox]:
    async with _sandbox("2 seconds") as sb:
        yield sb


@pytest.fixture
async def pool(sandbox: _Sandbox) -> AsyncIterator[asyncpg.Pool]:
    p = await create_prod_shaped_pool(dsn=sandbox.dsn, min_size=1, max_size=4)
    yield p
    await p.close()


_RACE_POOL_MIN, _RACE_POOL_MAX = 4, 8


async def _race_pool(dsn: str) -> asyncpg.Pool:
    """§4.7. Both racers' transactions have UNWOUND by the time the loser reaches
    `after_collision_before_reread` (the `async with` exited on the exception), so the
    re-read does not compete with them for a connection; what does compete is the
    superuser purge (outside the pool) and, in schedule D, the third caller INSIDE the
    pool while the loser is held. `min_size=4, max_size=8` is asserted FROM THE POOL by
    `_assert_spare_capacity`, not trusted as a literal."""
    return await create_prod_shaped_pool(dsn=dsn, min_size=_RACE_POOL_MIN, max_size=_RACE_POOL_MAX)


@pytest.fixture
async def race_pool(sandbox: _Sandbox) -> AsyncIterator[asyncpg.Pool]:
    p = await _race_pool(sandbox.dsn)
    yield p
    await p.close()


@pytest.fixture
async def short_race_pool(short_sandbox: _Sandbox) -> AsyncIterator[asyncpg.Pool]:
    p = await _race_pool(short_sandbox.dsn)
    yield p
    await p.close()


@pytest.fixture
def store(pool: asyncpg.Pool) -> PostgresDocumentStore:
    return PostgresDocumentStore(pool, environment=_ENV)


def _doc_id(label: str) -> str:
    """A valid `document_id` (304's CHECK: 32 lowercase hex) derived from a readable label."""
    return hashlib.sha256(label.encode()).hexdigest()[:32]


def _low_confidence(
    document_id: str, fields: tuple[PassportReviewFieldName, ...] = ()
) -> LowConfidenceOutcome:
    chosen = fields or (PassportReviewFieldName.FULL_NAME, PassportReviewFieldName.PASSPORT_NUMBER)
    return LowConfidenceOutcome(
        document_id=document_id,
        uncertain_fields=tuple(
            UncertainReviewField(field_path=f, confirmation_required=True) for f in chosen
        ),
    )


def _ready(document_id: str, fields: tuple[PassportReviewFieldName, ...] = ()) -> ReadyOutcome:
    """Flags ALTERNATE by position in the received order (True, False, True, ...), so a
    store that forces every flag to True, or drops one named field, is red (Sol, PR2a-v2
    O1, finding 2: a matrix of all-True flags over three of four fields proved neither)."""
    chosen = fields or (PassportReviewFieldName.FULL_NAME,)
    return ReadyOutcome(
        document_id=document_id,
        review_fields=tuple(
            ReviewField(
                field_path=f, value=f"SYNTHETIC {f.value}", confirmation_required=(i % 2 == 0)
            )
            for i, f in enumerate(chosen)
        ),
    )


@dataclass
class _Counters:
    lookups: int = 0
    collisions: int = 0


async def _row_count(pool: asyncpg.Pool, table: str = "garuda_documents") -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(f"SELECT count(*) FROM public.{table}")


def _key(idempotency_key: str, actor_id: str = _ACTOR_1) -> bytes:
    return _scoped_key_sha256(
        actor_id=actor_id,
        operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT,
        environment=_ENV,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# P1 -- actor scoping is injective, not decorative
# ---------------------------------------------------------------------------


async def test_p1_two_actors_same_literal_key_hold_two_bindings(
    store: PostgresDocumentStore, pool: asyncpg.Pool
):
    """P1. Both commits win; two rows; each actor replays its own outcome and the other
    actor's lookup is None -- not a conflict, not a replay. Guilt: `actor_id` replaced by
    `""` in `_scoped_key_sha256` (the store that accepts the argument and ignores it)."""
    outcome_1 = _low_confidence(_doc_id("p1-actor-1"))
    outcome_2 = _low_confidence(_doc_id("p1-actor-2"))

    assert await store.commit("shared-literal-key", "aa" * 32, outcome_1, actor_id=_ACTOR_1) is True
    assert await store.commit("shared-literal-key", "bb" * 32, outcome_2, actor_id=_ACTOR_2) is True

    assert await _row_count(pool) == 2
    assert await store.get_existing("shared-literal-key", "aa" * 32, actor_id=_ACTOR_1) == outcome_1
    assert await store.get_existing("shared-literal-key", "bb" * 32, actor_id=_ACTOR_2) == outcome_2
    assert await store.get_existing("shared-literal-key", "cc" * 32, actor_id="0" * 32) is None


# ---------------------------------------------------------------------------
# P2 / §3 -- injectivity of the scoped key, DERIVED from a mutation model
# ---------------------------------------------------------------------------

_SEPARATORS = ("|", "\x00", ":", "-", "/", ",", "\n")
_BASE_ACTOR = "0123456789abcdef0123456789abcdef"  # L = 32
_BASE_KEY = "idem-key-0123456789"  # L = 19


def _flip(s: str, i: int) -> str:
    """One character changed at index i, staying inside the same alphabet."""
    c = "z" if s[i] != "z" else "y"
    return s[:i] + c + s[i + 1 :]


@dataclass(frozen=True, slots=True)
class _Encoder:
    """One member of the mutation model E (§3): a LOSSY string encoder and a constructor
    for a pair it collapses. The pair is COMPUTED from the encoder, never hand-picked."""

    name: str
    encode: Callable[[str], str]
    witness: Callable[[str], tuple[str, str]]


def _string_model(L: int) -> list[_Encoder]:
    model: list[_Encoder] = []
    for n in range(1, L):
        model.append(_Encoder(f"prefix_{n}", lambda s, n=n: s[:n], lambda s, n=n: (s, _flip(s, n))))
        model.append(
            _Encoder(f"suffix_{n}", lambda s, n=n: s[n:], lambda s, n=n: (s, _flip(s, n - 1)))
        )
    for k in range(2, 5):
        for o in range(k):
            # s[o::k] keeps indices congruent to o mod k; flip one that is not.
            j = (o + 1) % k
            model.append(
                _Encoder(
                    f"stride_{k}_{o}", lambda s, k=k, o=o: s[o::k], lambda s, j=j: (s, _flip(s, j))
                )
            )
    for i in range(L):
        if i < L - 1:
            model.append(
                _Encoder(
                    f"drop_{i}",
                    lambda s, i=i: s[:i] + s[i + 1 :],
                    lambda s, i=i: (s[:i] + "ab" + s[i + 2 :], s[:i] + "bb" + s[i + 2 :]),
                )
            )
        else:
            model.append(
                _Encoder(
                    f"drop_{i}", lambda s, i=i: s[:i], lambda s, i=i: (s[:i] + "a", s[:i] + "b")
                )
            )
    # `swapcase` is a bijection on ASCII letters and has NO collision pair, so it cannot be
    # a member of a LOSSY model; the case-insensitive encoder that IS lossy is casefold.
    model.append(
        _Encoder("casefold", lambda s: s.casefold(), lambda s: (s[:-2] + "ab", s[:-2] + "AB"))
    )
    for sep in _SEPARATORS:
        model.append(
            _Encoder(
                f"strip_sep_{sep!r}",
                lambda s, sep=sep: s.replace(sep, ""),
                lambda s, sep=sep: (s[:4] + sep + s[4:], s),
            )
        )
        # Trailing/leading strips are NOT covered by an inner strip: `rstrip("-")` collapses
        # `k` and `k-` and leaves every inner-separator witness intact (Sol, PR2a-v2 O1,
        # finding 1). Each gets its own witness at the edge it erases.
        model.append(
            _Encoder(
                f"rstrip_sep_{sep!r}",
                lambda s, sep=sep: s.rstrip(sep),
                lambda s, sep=sep: (s + sep, s),
            )
        )
        model.append(
            _Encoder(
                f"lstrip_sep_{sep!r}",
                lambda s, sep=sep: s.lstrip(sep),
                lambda s, sep=sep: (sep + s, s),
            )
        )
    return model


def _expected_model_size(L: int) -> int:
    """The size of E for a component of length L, derived from the model's own shape:
    (L-1) prefixes + (L-1) suffixes + 9 strides (k=2..4, o<k) + L drops + 1 casefold
    + 3 per separator (strip, rstrip, lstrip). Asserted EXACTLY, so removing one member
    is red (limit L6: injectivity is proved over this enumerated model)."""
    return 2 * (L - 1) + 9 + L + 1 + 3 * len(_SEPARATORS)


def _tuple_model() -> list[
    tuple[str, Callable[[tuple[str, ...]], str], tuple[tuple[str, ...], tuple[str, ...]]]
]:
    """Encoders over the whole 4-tuple: separator-joins, and a byte moved across a component
    boundary (actor/operation and operation/environment)."""
    cases = []
    for sep in _SEPARATORS:
        cases.append(
            (
                f"join_sep_{sep!r}",
                lambda t, sep=sep: sep.join(t),
                ((f"a{sep}b", "c", _ENV, _BASE_KEY), ("a", f"b{sep}c", _ENV, _BASE_KEY)),
            )
        )
    cases.append(
        (
            "swap_actor_operation",
            "".join,
            (("actorab", "c", _ENV, _BASE_KEY), ("actora", "bc", _ENV, _BASE_KEY)),
        )
    )
    cases.append(
        (
            "swap_operation_environment",
            "".join,
            (("a", "opTE", "ST", _BASE_KEY), ("a", "op", "TEST", _BASE_KEY)),
        )
    )
    return cases


_STRING_CASES = [
    (comp, enc)
    for comp, base in (("actor", _BASE_ACTOR), ("key", _BASE_KEY))
    for enc in _string_model(len(base))
]
_TUPLE_CASES = _tuple_model()


def test_p2_the_mutation_model_is_exactly_the_enumerated_model():
    """§3 and limit L6: injectivity is proved OVER the model E enumerated in this file, not
    universally -- a lossy encoder outside E is outside the proof, and the honest guard is
    that E is exactly what it claims to be. The case count is asserted EXACTLY per
    component from the model's own shape, so dropping a single member is red; every
    family must be present; the tuple model is exactly the separators plus the two
    boundary shifts."""
    families = (
        "prefix_",
        "suffix_",
        "stride_",
        "drop_",
        "casefold",
        "strip_sep_",
        "rstrip_sep_",
        "lstrip_sep_",
    )
    for component, base in (("actor", _BASE_ACTOR), ("key", _BASE_KEY)):
        names = [enc.name for comp, enc in _STRING_CASES if comp == component]
        # actor L=32 -> 62 + 9 + 32 + 1 + 21 = 125; key L=19 -> 36 + 9 + 19 + 1 + 21 = 86;
        # 211 string cases in total, which is what `_STRING_CASES` parametrizes.
        assert len(names) == _expected_model_size(len(base)), (
            f"{component}: model has {len(names)} members, expected {_expected_model_size(len(base))}"
        )
        assert len(set(names)) == len(names), f"{component}: duplicate encoder names"
        for family in families:
            assert any(n.startswith(family) for n in names), (
                f"{component}: family {family!r} missing from the model"
            )
    assert len(_TUPLE_CASES) == len(_SEPARATORS) + 2


@pytest.mark.parametrize(
    ("component", "encoder"), _STRING_CASES, ids=lambda x: x if isinstance(x, str) else x.name
)
def test_p2_scoped_key_distinguishes_every_pair_a_lossy_encoder_collapses(
    component: str, encoder: _Encoder
):
    """P2, stated as INJECTIVITY over the 4-tuple, proved per encoder of the model E --
    and ONLY over E (limit L6): the proof is exactly as wide as the enumerated model.

    For this encoder the test COMPUTES a pair (t1, t2) with t1 != t2 and e(t1) == e(t2),
    checks that premise (a witness the model cannot construct is an ERROR, not a skip),
    then asserts the real scoped key separates them. Parametrization is over the model,
    not over a range of one integer: prefix cuts, suffix cuts, strides, single drops,
    case folding and separator stripping, applied to the actor and to the idempotency
    key. Guilt: substituting any encoder into `_scoped_key_sha256` turns its own case red.
    """
    base = _BASE_ACTOR if component == "actor" else _BASE_KEY
    s1, s2 = encoder.witness(base)
    assert s1 != s2, f"{encoder.name}: witness pair must differ"
    assert encoder.encode(s1) == encoder.encode(s2), (
        f"{encoder.name}: encoder does not collapse its own witness"
    )

    def tup(s: str) -> dict[str, str]:
        return {
            "actor_id": s if component == "actor" else _BASE_ACTOR,
            "operation": _OPERATION_UPLOAD_INTAKE_DOCUMENT,
            "environment": _ENV,
            "idempotency_key": s if component == "key" else _BASE_KEY,
        }

    assert _scoped_key_sha256(**tup(s1)) != _scoped_key_sha256(**tup(s2)), (
        f"{encoder.name} on {component}: the scoped key collapsed a pair a lossy encoder collapses -- "
        "the encoding is not injective"
    )


@pytest.mark.parametrize(("name", "encode", "pair"), _TUPLE_CASES, ids=[c[0] for c in _TUPLE_CASES])
def test_p2_scoped_key_distinguishes_tuples_a_separator_join_or_boundary_shift_collapses(
    name, encode, pair
):
    """P2 across component boundaries: two tuples that render identically under a
    separator-join (a component CONTAINING the separator) or under a byte moved across a
    boundary must hash differently. Guilt: `sep.join(...)` in place of length-prefixing."""
    t1, t2 = pair
    assert t1 != t2 and encode(t1) == encode(t2), f"{name}: witness premise failed"
    h1 = _scoped_key_sha256(
        actor_id=t1[0], operation=t1[1], environment=t1[2], idempotency_key=t1[3]
    )
    h2 = _scoped_key_sha256(
        actor_id=t2[0], operation=t2[1], environment=t2[2], idempotency_key=t2[3]
    )
    assert h1 != h2, f"{name}: the scoped key is separator-joined, not length-prefixed"


def test_p2_golden_vector_backward_compatibility_pin_not_a_property():
    """A FORM pin, labelled as such (§3). `key_sha256` is a persisted PRIMARY KEY: changing
    the encoding orphans every production row, so ONE fixed tuple and its digest are pinned.
    This proves compatibility with the shipped encoding and nothing else; the property is
    the parametrized test above."""
    digest = _scoped_key_sha256(
        actor_id="0123456789abcdef0123456789abcdef",
        operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT,
        environment="PRODUCTION",
        idempotency_key="golden-vector-0001",
    )
    assert digest.hex() == "3b54819ba48dd396baa9e7798d95b13997f1c422c559053b7defe15fd925dda9"


# ---------------------------------------------------------------------------
# P3 / P4 -- replay and conflict on both entry points
# ---------------------------------------------------------------------------


async def test_p3_exact_replay_returns_the_committed_outcome_and_creates_nothing(
    pool: asyncpg.Pool,
):
    """P3. A sequential replay is answered by the LOOKUP, never by a primary-key collision:
    the outcome comes back equal, the second commit returns False, no row is added, and the
    collision seam never fires. That last assertion is what makes the guilt bite -- with the
    `SELECT ... FOR UPDATE` branch removed the store still answers False and adds no row,
    but only by INSERTing into the primary key and recovering (measured: the mutation
    survived the first three assertions alone, 240 passed). Guilt: that branch removed."""
    collisions = _Counters()

    async def unexpected_collision(_ctx: _HookContext) -> None:
        collisions.collisions += 1

    store = PostgresDocumentStore(
        pool,
        environment=_ENV,
        _hooks=_CommitHooks(after_collision_before_reread=unexpected_collision),
    )
    outcome = _low_confidence(_doc_id("p3-replay"))
    assert await store.commit("key-p3", "aa" * 32, outcome, actor_id=_ACTOR_1) is True
    rows, fields = await _row_count(pool), await _row_count(pool, "garuda_document_review_fields")

    assert await store.get_existing("key-p3", "aa" * 32, actor_id=_ACTOR_1) == outcome
    assert await store.commit("key-p3", "aa" * 32, outcome, actor_id=_ACTOR_1) is False
    assert (await _row_count(pool), await _row_count(pool, "garuda_document_review_fields")) == (
        rows,
        fields,
    )
    assert collisions.collisions == 0, (
        "a sequential replay must be answered by the lookup, not by a PK collision"
    )


async def test_p3_processing_and_unreadable_replay_faithfully(store: PostgresDocumentStore):
    processing = ProcessingOutcome(document_id=_doc_id("p3-processing"))
    unreadable = UnreadableOutcome(document_id=_doc_id("p3-unreadable"))
    await store.commit("key-p3-processing", "dd" * 32, processing, actor_id=_ACTOR_1)
    await store.commit("key-p3-unreadable", "ee" * 32, unreadable, actor_id=_ACTOR_1)
    assert await store.get_existing("key-p3-processing", "dd" * 32, actor_id=_ACTOR_1) == processing
    assert await store.get_existing("key-p3-unreadable", "ee" * 32, actor_id=_ACTOR_1) == unreadable


async def test_p4_different_payload_same_key_is_a_conflict_on_both_entry_points(
    store: PostgresDocumentStore, pool: asyncpg.Pool
):
    """P4. `service.py` calls `get_existing` and `commit` on different paths; they must not
    disagree. Guilt: either hash comparison replaced by `True`."""
    await store.commit("key-p4", "11" * 32, _low_confidence(_doc_id("p4-first")), actor_id=_ACTOR_1)
    with pytest.raises(IdempotencyConflictError):
        await store.get_existing("key-p4", "22" * 32, actor_id=_ACTOR_1)
    with pytest.raises(IdempotencyConflictError):
        await store.commit(
            "key-p4", "22" * 32, _low_confidence(_doc_id("p4-second")), actor_id=_ACTOR_1
        )
    assert await _row_count(pool) == 1


# ---------------------------------------------------------------------------
# P5 / P6 / P7 -- the forced schedules (§4.3, §4.4)
# ---------------------------------------------------------------------------


def _racing_hooks(
    barrier: asyncio.Barrier,
    counters: _Counters,
    hold_loser: Callable[[], Awaitable[None]] | None = None,
) -> _CommitHooks:
    async def after_lookup(_ctx: _HookContext) -> None:
        counters.lookups += 1
        await barrier.wait()

    async def after_collision(_ctx: _HookContext) -> None:
        counters.collisions += 1
        if hold_loser is not None:
            await hold_loser()

    return _CommitHooks(after_lookup=after_lookup, after_collision_before_reread=after_collision)


async def _assert_spare_capacity(pool: asyncpg.Pool, needed: int = 3) -> None:
    assert pool.get_min_size() >= _RACE_POOL_MIN and pool.get_max_size() >= _RACE_POOL_MAX, (
        f"setup: race pool must be sized >= {_RACE_POOL_MIN}/{_RACE_POOL_MAX}, "
        f"got {pool.get_min_size()}/{pool.get_max_size()} (§4.7)"
    )
    free = pool.get_max_size() - pool.get_size() + pool.get_idle_size()
    assert free >= needed, f"setup: race needs {needed} spare connections, pool has {free} (§4.7)"


async def _schedule_a(
    pool: asyncpg.Pool, key: str, payload_a: str, payload_b: str, hold_loser=None
):
    """Two stores on one pool, both blocked in `after_lookup` behind a Barrier(2). After
    the barrier neither can have committed -- both were still inside their lookup when it
    closed -- so the replay branch is unreachable and the second INSERT MUST collide on
    `garuda_documents_pkey`. Returns (results, counters)."""
    await _assert_spare_capacity(pool)
    barrier, counters = asyncio.Barrier(2), _Counters()
    store_a = PostgresDocumentStore(
        pool, environment=_ENV, _hooks=_racing_hooks(barrier, counters, hold_loser)
    )
    store_b = PostgresDocumentStore(
        pool, environment=_ENV, _hooks=_racing_hooks(barrier, counters, hold_loser)
    )
    results = await asyncio.gather(
        store_a.commit(key, payload_a, _low_confidence(_doc_id(f"{key}-a")), actor_id=_ACTOR_1),
        store_b.commit(key, payload_b, _low_confidence(_doc_id(f"{key}-b")), actor_id=_ACTOR_1),
        return_exceptions=True,
    )
    assert counters.lookups == 2, (
        f"setup: both racers must pass after_lookup, saw {counters.lookups}"
    )
    assert counters.collisions == 1, (
        f"setup: exactly one racer must collide on the PK, saw {counters.collisions}"
    )
    return results, counters


async def test_p5_p6_schedule_a_exactly_one_winner_and_the_loser_traversed_the_pk_branch(
    race_pool: asyncpg.Pool,
):
    """P5 (at most one True per key) and P6 (`commit` is total) under schedule A. The
    collision counter == 1 IS the branch assertion the previous suite could not make: the
    loser went through the `UniqueViolationError` handler, under ANY scheduler. Guilt: the
    handler deleted -> `UniqueViolationError` escapes -> red on PG15 and PG17, no caveat."""
    results, _ = await _schedule_a(race_pool, "key-schedule-a", "55" * 32, "55" * 32)
    assert sorted(results, key=str) == [False, True], (
        f"exactly one winner and one loser: {results!r}"
    )
    assert await _row_count(race_pool) == 1


async def test_p7_schedule_b_loser_with_a_different_payload_gets_conflict_not_false(
    race_pool: asyncpg.Pool,
):
    """P7. On the INSERT-collision path no payload was compared (there was no row when we
    looked), so the loser is re-read against the winner: a different hash is
    IDEMPOTENCY_CONFLICT, never "you merely lost". Guilt: `payload_checked=True` on that path."""
    results, _ = await _schedule_a(race_pool, "key-schedule-b", "aa" * 32, "bb" * 32)
    winners = [r for r in results if r is True]
    conflicts = [r for r in results if isinstance(r, IdempotencyConflictError)]
    assert len(winners) == 1 and len(conflicts) == 1, f"one winner, one conflict: {results!r}"
    assert await _row_count(race_pool) == 1
    async with race_pool.acquire() as conn:
        persisted = await conn.fetchval(
            "SELECT canonical_payload_sha256 FROM public.garuda_documents"
        )
    assert bytes(persisted) in (bytes.fromhex("aa" * 32), bytes.fromhex("bb" * 32))


async def test_p5_sequential_second_commit_returns_false(store: PostgresDocumentStore):
    outcome = _low_confidence(_doc_id("p5-sequential"))
    assert await store.commit("key-p5-seq", "66" * 32, outcome, actor_id=_ACTOR_1) is True
    assert await store.commit("key-p5-seq", "66" * 32, outcome, actor_id=_ACTOR_1) is False


# ---------------------------------------------------------------------------
# §2 outcomes 3 and 4 -- schedules C and D
# ---------------------------------------------------------------------------


async def _purge_winner_once_expired(database: str, key_hash: bytes) -> None:
    """From a SUPERUSER connection outside the store's pool: wait until the winner's row is
    legally purgeable (`clock_timestamp() >= retention_until`, 304's DELETE guard), delete
    it, and assert exactly one row went -- so a timing flake is a loud failure, never a
    silent pass."""
    conn = await _connect(database)
    try:
        for _ in range(60):
            if await conn.fetchval(
                "SELECT clock_timestamp() >= retention_until FROM public.garuda_documents WHERE key_sha256 = $1",
                key_hash,
            ):
                break
            await asyncio.sleep(0.1)
        deleted = await conn.fetchval(
            "WITH gone AS (DELETE FROM public.garuda_documents WHERE key_sha256 = $1 RETURNING 1) SELECT count(*) FROM gone",
            key_hash,
        )
        assert deleted == 1, f"setup: expected to purge exactly the winner's row, deleted {deleted}"
    finally:
        await conn.close()


async def test_schedule_c_key_vanished_after_the_collision_is_typed(
    short_sandbox: _Sandbox, short_race_pool: asyncpg.Pool
):
    """§2 outcome 3. The loser is held in `after_collision_before_reread`; the winner's row
    expires (2-second policy) and is purged, legally, by a superuser outside the pool; the
    loser's re-read finds the key bound to nothing -> `IdempotencyKeyVanished`, typed, no
    retry. Guilt: the typed error reverted to `RuntimeError`."""
    key_hash = _key("key-schedule-c")

    async def hold() -> None:
        await _purge_winner_once_expired(short_sandbox.database, key_hash)

    results, _ = await _schedule_a(
        short_race_pool, "key-schedule-c", "77" * 32, "77" * 32, hold_loser=hold
    )
    assert [r for r in results if r is True] == [True]
    assert [type(r) for r in results if isinstance(r, Exception)] == [IdempotencyKeyVanished]
    assert await _row_count(short_race_pool) == 0


@pytest.mark.parametrize(
    "reoccupier_payload_matches_loser", [True, False], ids=["same-payload", "different-payload"]
)
async def test_schedule_d_reoccupation_collapses_into_outcome_1_or_2(
    short_sandbox: _Sandbox, short_race_pool: asyncpg.Pool, reoccupier_payload_matches_loser: bool
):
    """§2 outcome 4 -- and the ruling that provenance is NOT observable. After the purge a
    THIRD caller takes the free key; the held loser's re-read then sees THAT row. Same
    payload as the loser -> False; different -> IdempotencyConflictError. Never
    `IdempotencyKeyVanished`, and never the reverse: the port promises a function of the
    row holding the key at re-read time, not of the row that beat us."""
    key_hash = _key("key-schedule-d")
    loser_payload = "88" * 32
    third_payload = loser_payload if reoccupier_payload_matches_loser else "99" * 32
    third = PostgresDocumentStore(short_race_pool, environment=_ENV)

    async def hold() -> None:
        await _purge_winner_once_expired(short_sandbox.database, key_hash)
        assert await third.commit(
            "key-schedule-d", third_payload, _low_confidence(_doc_id("d-third")), actor_id=_ACTOR_1
        )

    results, _ = await _schedule_a(
        short_race_pool, "key-schedule-d", loser_payload, loser_payload, hold_loser=hold
    )
    assert [r for r in results if r is True] == [True]
    loser_result = [r for r in results if r is not True]
    if reoccupier_payload_matches_loser:
        assert loser_result == [False]
    else:
        assert [type(r) for r in loser_result] == [IdempotencyConflictError]
    assert await _row_count(short_race_pool) == 1


# ---------------------------------------------------------------------------
# P8 / P9 / P10 / P11
# ---------------------------------------------------------------------------


async def test_p8_duplicate_document_id_under_a_fresh_key_propagates_not_a_lost_race(
    store: PostgresDocumentStore, pool: asyncpg.Pool
):
    """P8. `garuda_documents_document_id_key` means the minted id exists under ANOTHER key --
    nobody won THIS key, and `False` would send `service.py` to its assert. Guilt: the
    `constraint_name != _PK_KEY_SHA256` discrimination removed."""
    shared = _doc_id("p8-shared-document")
    assert await store.commit("key-p8-first", "aa" * 32, _low_confidence(shared), actor_id=_ACTOR_1)
    with pytest.raises(asyncpg.UniqueViolationError) as excinfo:
        await store.commit("key-p8-second", "bb" * 32, _low_confidence(shared), actor_id=_ACTOR_1)
    assert excinfo.value.constraint_name == "garuda_documents_document_id_key"
    assert await store.get_existing("key-p8-second", "bb" * 32, actor_id=_ACTOR_1) is None
    assert await _row_count(pool) == 1


async def test_p6_a_duplicate_field_path_is_refused_typed_before_any_sql(
    store: PostgresDocumentStore, pool: asyncpg.Pool
):
    """P6. The model does not forbid naming a field twice; the child table's PRIMARY KEY
    (document_id, field_path) does, and would answer with a raw UniqueViolationError from
    outside the handler. The store refuses it first, typed, and writes nothing. Guilt:
    `_unique_fields` returning its input unchecked."""
    twice = LowConfidenceOutcome(
        document_id=_doc_id("p6-dup"),
        uncertain_fields=(
            UncertainReviewField(field_path=PassportReviewFieldName.FULL_NAME),
            UncertainReviewField(field_path=PassportReviewFieldName.FULL_NAME),
        ),
    )
    with pytest.raises(DuplicateReviewFieldPath) as excinfo:
        await store.commit("key-p6-dup", "ee" * 32, twice, actor_id=_ACTOR_1)
    assert excinfo.value.field_path == "full_name"
    assert (
        await _row_count(pool) == 0 and await _row_count(pool, "garuda_document_review_fields") == 0
    )
    assert await store.get_existing("key-p6-dup", "ee" * 32, actor_id=_ACTOR_1) is None


async def test_p9_no_active_policy_fails_closed_with_the_documented_type(pool: asyncpg.Pool):
    """P9. STAGING has no policy in the sandbox. The assertion is on the TYPE: with the
    Python guard deleted the refusal still happens, but as migration 304's untranslated
    `asyncpg.RaiseError` -- differently red, and this test tells the two apart. Guilt: the
    `active_garuda_document_policy_available` check deleted."""
    staging = PostgresDocumentStore(pool, environment="STAGING")
    with pytest.raises(PersistencePolicyUnavailable):
        await staging.commit("key-p9", "77" * 32, _low_confidence(_doc_id("p9")), actor_id=_ACTOR_1)
    assert await _row_count(pool) == 0


@pytest.mark.parametrize(
    "order",
    list(itertools.permutations(_CANONICAL)),
    ids=lambda o: "-".join(f.value[:4] for f in o),
)
async def test_p10_ready_replay_announces_the_gap_with_the_persisted_structure_in_canonical_order(
    store: PostgresDocumentStore, order: tuple[PassportReviewFieldName, ...]
):
    """P10. No field VALUE is persisted; a replayed ReadyOutcome raises
    `ReadyOutcomeValueNotPersisted` carrying the document_id and the FULL persisted
    STRUCTURE -- every one of the four names, each with the flag it was committed with --
    in canonical order, for EVERY received order (24 permutations; flags alternate by
    received position, so the committed flag set differs per permutation). The TYPE alone
    is not the property. Guilt: `_rehydrate` fabricating a valueless ReadyOutcome;
    `persisted_fields` replaced by `()`; one named field dropped in `_decompose`; every
    flag forced to True."""
    document_id = _doc_id("p10-" + "".join(f.value for f in order))
    key = "key-p10-" + "-".join(f.value[:3] for f in order)
    committed = _ready(document_id, order)
    assert await store.commit(key, "cc" * 32, committed, actor_id=_ACTOR_1)

    with pytest.raises(ReadyOutcomeValueNotPersisted) as excinfo:
        await store.get_existing(key, "cc" * 32, actor_id=_ACTOR_1)

    committed_flags = {rf.field_path: rf.confirmation_required for rf in committed.review_fields}
    expected = tuple((f, committed_flags[f]) for f in _CANONICAL)
    assert excinfo.value.document_id == document_id
    assert excinfo.value.persisted_fields == expected


@pytest.mark.parametrize(
    "order",
    list(itertools.permutations(_CANONICAL)),
    ids=lambda o: "-".join(f.value[:4] for f in o),
)
async def test_p11_low_confidence_replay_is_canonical_for_every_received_order(
    store: PostgresDocumentStore, order: tuple[PassportReviewFieldName, ...]
):
    """P11, and limit L1 cited exactly: for ANY received order the replay returns
    `PassportReviewFieldName`'s declaration order. The RECEIVED order is not preserved and
    cannot be without an ordinal column, i.e. a migration (L1). Guilt: `_in_canonical_order`
    dropped, SQL (alphabetical) order kept -- red on every permutation that is not already
    alphabetical."""
    key = "key-p11-" + "-".join(f.value[:3] for f in order)
    committed = _low_confidence(_doc_id("p11-" + key), order)
    assert await store.commit(key, "ab" * 32, committed, actor_id=_ACTOR_1)

    replayed = await store.get_existing(key, "ab" * 32, actor_id=_ACTOR_1)

    assert isinstance(replayed, LowConfidenceOutcome)
    assert tuple(f.field_path for f in replayed.uncertain_fields) == _CANONICAL
    assert replayed == _low_confidence(committed.document_id, _CANONICAL)


# ---------------------------------------------------------------------------
# The seam is a test seam (§4.2)
# ---------------------------------------------------------------------------


def test_the_default_constructor_has_no_hooks():
    """A store built the way a production factory builds one carries no hooks. PR3, which
    writes the factory, asserts the same at the factory (limit L4)."""
    store = PostgresDocumentStore(object(), environment="PRODUCTION")  # type: ignore[arg-type]
    assert store._hooks is None


# ---------------------------------------------------------------------------
# H1 -- report-level redaction, proved in a SUBPROCESS (§5)
# ---------------------------------------------------------------------------

_PROBE_MODULE = """
from backend.tests.services.garuda_documents.test_postgres_store import _connect


async def test_probe():
    conn = await _connect(None)
    await conn.close()
"""


def _run_probe_subprocess(tmp_path: Path, dsn: str) -> tuple[subprocess.CompletedProcess[str], str]:
    probe = tmp_path / "test_h1_probe.py"
    probe.write_text(_PROBE_MODULE)
    junit = tmp_path / "h1.xml"
    env = {**os.environ, "CI": "1", "GARUDA_DOCUMENTS_TEST_DSN": dsn, "PYTHONPATH": "."}
    env.pop("INTAKE_TEST_DSN", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(probe),
            "--tb=long",
            "--showlocals",
            f"--junit-xml={junit}",
            f"--rootdir={_BACKEND_ROOT}",
            "-c",
            str(_BACKEND_ROOT / "pytest.ini"),
            "-p",
            "no:cacheprovider",
        ],
        cwd=_BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return completed, junit.read_text() if junit.exists() else ""


def _sentinel_dsn(host_port: str, query: str = "") -> tuple[str, str]:
    secret = f"SENTINEL_PW_{uuid.uuid4().hex}"
    return secret, f"postgresql://sentinel_user:{secret}@{host_port}/nope{query}"


@pytest.mark.parametrize(
    ("host_port", "query", "case"),
    [
        ("127.0.0.1:1", "", "unreachable-server"),
        ("127.0.0.1:1", "?sslmode=bogus", "dsn-rejected-by-parser"),
        ("127.0.0.1:notaport", "", "dsn-the-redactor-itself-cannot-parse"),
    ],
    ids=["unreachable-server", "dsn-rejected-by-parser", "dsn-the-redactor-itself-cannot-parse"],
)
def test_h1_no_dsn_secret_reaches_the_report_at_tb_long_or_the_junit_xml(
    tmp_path: Path, host_port: str, query: str, case: str
):
    """H1. A pytest SUBPROCESS with `--tb=long --showlocals` and JUnit output, `CI=1`, and
    a sentinel password in the DSN. The sentinel must be absent from stdout, stderr and the
    XML under the most verbose renderer pytest has (`--showlocals` prints every frame's
    locals, which is where a `dsn` variable would leak). The sentinel is a random uuid minted
    by THIS test, not a credential: the harness's own frames hold it (`secret`, `dsn`), so a
    failure of the harness itself would render a throwaway string, never a real password. The
    run must FAIL (exit != 0) with the must-not-skip text; and the `***` redaction marker
    must be present -- the last two so a subprocess that merely failed to collect cannot
    pass vacuously. Three degraded cases: an unreachable server (OSError); a DSN asyncpg's
    parser rejects before any socket (`ClientConfigurationError`, an InterfaceError that
    the old suite's `except (OSError, PostgresError)` let through); and a DSN `_redacted`
    itself cannot parse (a non-numeric port), which is red the moment the redactor stops
    being total. Guilt (brief `guilt_mutations`, H1 rows): `_redacted` passing the DSN
    through -> 4 failed; `pytrace=True` -> 3 failed (`_connect`'s `dsn` local renders under
    `--showlocals`); `from None` dropped alone -> survives, because `pytrace=False` renders
    the message alone -- declared in the brief's `spec_errata`, not hidden."""
    secret, dsn = _sentinel_dsn(host_port, query)
    completed, xml = _run_probe_subprocess(tmp_path, dsn)
    report = completed.stdout + completed.stderr

    assert completed.returncode != 0, f"{case}: the probe must FAIL under CI\n{report[-2000:]}"
    assert secret not in report and secret not in xml, f"{case}: sentinel leaked into the report"
    assert "***" in report, (
        f"{case}: the redaction marker is missing, so nothing was redacted\n{report[-2000:]}"
    )
    assert "must not be skipped" in report, f"{case}: CI must FAIL, not skip\n{report[-2000:]}"


async def test_h1_non_superuser_role_fails_under_ci_without_leaking_its_password(
    sandbox: _Sandbox, tmp_path: Path
):
    """§8.2's third degraded case, behaviourally: a LOGIN role that is NOT a superuser, with
    a sentinel password, pointed at the sandbox. Under CI the fixture must FAIL (not skip)
    and the sentinel must not reach the report. Closes the "untestable" declaration the
    previous brief carried for this branch."""
    secret = f"SENTINEL_PW_{uuid.uuid4().hex}"
    role = f"gdoc_probe_{uuid.uuid4().hex[:12]}"
    admin = await _connect(None)
    try:
        await admin.execute(f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{secret}'")
    finally:
        await admin.close()
    parts = urlsplit(_ADMIN_URL)
    host = parts.hostname or "localhost"
    port = parts.port or 5432
    dsn = f"postgresql://{role}:{secret}@{host}:{port}/{sandbox.database}"
    probe = _PROBE_MODULE + (
        "\n\nasync def test_superuser_gate():\n"
        "    from backend.tests.services.garuda_documents.test_postgres_store import _sandbox\n"
        "    async with _sandbox('30 days'):\n"
        "        pass\n"
    )
    try:
        (tmp_path / "test_h1_probe.py").write_text(probe)
        junit = tmp_path / "h1.xml"
        env = {**os.environ, "CI": "1", "GARUDA_DOCUMENTS_TEST_DSN": dsn, "PYTHONPATH": "."}
        env.pop("INTAKE_TEST_DSN", None)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(tmp_path / "test_h1_probe.py"),
                "--tb=long",
                "--showlocals",
                f"--junit-xml={junit}",
                f"--rootdir={_BACKEND_ROOT}",
                "-c",
                str(_BACKEND_ROOT / "pytest.ini"),
                "-p",
                "no:cacheprovider",
            ],
            cwd=_BACKEND_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        report = completed.stdout + completed.stderr
        xml = junit.read_text() if junit.exists() else ""
    finally:
        admin = await _connect(None)
        try:
            await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        finally:
            await admin.close()

    assert completed.returncode != 0, f"a non-superuser role must FAIL under CI\n{report[-2000:]}"
    assert secret not in report and secret not in xml, "sentinel leaked into the report"
    assert "not a superuser" in report and "must not be skipped" in report, report[-2000:]
