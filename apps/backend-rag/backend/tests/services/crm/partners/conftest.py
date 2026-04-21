"""
Local conftest for partners repository tests.

Provides:
- db_conn: a real asyncpg.Connection with all partner tables created for the test,
  then torn down afterward. Connects to nuzantara_dev (or TEST_DATABASE_URL override).
- user_factory, partner_factory, process_factory, referral_factory: helpers
  that insert rows and return UUIDs for use in tests.

IMPORT SHIELDING
-----------------
backend.services.crm.__init__ pulls in the entire CRM stack (langgraph,
google-genai, qdrant-client, etc.). We pre-populate sys.modules with bare
namespace packages BEFORE any backend import fires, so Python skips executing
that heavy __init__ when we import the partners sub-package.
"""
import os
import sys
import types as _types
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Coroutine


class _UUIDWithId(uuid.UUID):
    """UUID subclass that adds an `.id` property for backward-compat with
    both `await factory()` (used as UUID directly) and `(await factory()).id`
    (used in commission_engine tests that expect an object with .id)."""

    @property
    def id(self) -> "_UUIDWithId":
        return self

class _IntWithId(int):
    """int subclass with an `.id` property for factory pattern compat.
    Used for the live clients table which has INTEGER primary key."""

    @property
    def id(self) -> "_IntWithId":
        return self

import asyncpg
import pytest_asyncio


_SHIELDED: list[str] = []  # track what WE injected so we can clean up


def _shield(pkg_name: str, path: list[str] | None = None) -> None:
    """Install a namespace in sys.modules if the real package isn't there yet.

    We set __path__ to the real filesystem path so submodule discovery still
    works, but we don't execute the heavy __init__.py.

    If the module is already in sys.modules (e.g. another CRM test imported it
    first), we skip shielding entirely so the real module stays in place.
    """
    if pkg_name in sys.modules:
        return  # real module already loaded — don't touch it
    mod = _types.ModuleType(pkg_name)
    if path is not None:
        mod.__path__ = path  # type: ignore[assignment]
    else:
        mod.__path__ = []  # type: ignore[assignment]
    sys.modules[pkg_name] = mod
    _SHIELDED.append(pkg_name)


# Resolve the apps/backend-rag/ directory so we can build correct __path__s.
# __file__ = .../apps/backend-rag/backend/tests/services/crm/partners/conftest.py
# We need to go up 6 levels to reach apps/backend-rag/
_BACKEND_RAG_DIR = os.path.dirname(
    os.path.dirname(  # backend/
        os.path.dirname(  # tests/
            os.path.dirname(  # services/
                os.path.dirname(  # crm/
                    os.path.dirname(  # partners/
                        os.path.abspath(__file__)
                    )
                )
            )
        )
    )
)

# Shield the heavy CRM package and its ancestors BEFORE any backend import fires.
# __path__ must point to the actual directory so sub-package discovery works;
# the __init__.py in each directory is NOT executed (we bypass it entirely by
# pre-populating sys.modules before any import statement fires).
_shield("backend",              [os.path.join(_BACKEND_RAG_DIR, "backend")])
_shield("backend.services",     [os.path.join(_BACKEND_RAG_DIR, "backend", "services")])
_shield("backend.services.crm", [os.path.join(_BACKEND_RAG_DIR, "backend", "services", "crm")])


def pytest_unconfigure(config: object) -> None:  # noqa: ARG001
    """Remove shielded stubs after test session so subsequent test runs
    (or long-lived pytest sessions) don't leak hollow modules."""
    for name in _SHIELDED:
        if name in sys.modules and not hasattr(sys.modules[name], "__file__"):
            # only remove if still the hollow stub (real modules have __file__)
            del sys.modules[name]


_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)

# --------------------------------------------------------------------------
# Schema bootstrap DDL
# --------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email   TEXT NOT NULL UNIQUE,
    role    TEXT NOT NULL DEFAULT 'team',
    partner_id UUID
);

-- NOTE: clients table already exists in the dev DB with many dependents.
-- We do NOT create/drop it — we use it as-is. The client_factory
-- inserts rows and cleans them up after each test.

-- CATA-1 NOTE: practices is a real production table (id=INTEGER in dev DB).
-- We create a TEMPORARY TABLE practices that shadows the real one for this
-- connection session only (pg_temp schema is always first in search_path).
-- The temp table uses UUID id matching the partners module design, with the
-- 4 columns CommissionEngine reads. It is dropped in teardown.
-- This is the same isolation pattern used before CATA-1 with the processes stub.
CREATE TEMP TABLE IF NOT EXISTS practices (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    status             TEXT NOT NULL DEFAULT 'pending',
    payment_status     TEXT NOT NULL DEFAULT 'pending',
    total_invoiced_idr NUMERIC(16,2) NOT NULL DEFAULT 0,
    completed_at       TIMESTAMPTZ,
    client_id          INTEGER,
    service_type       TEXT
);

CREATE TABLE IF NOT EXISTS system_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '0'
);
INSERT INTO system_settings (key, value) VALUES
    ('partner_clawback_auto_writeoff_idr',   '0'),
    ('partner_accrual_cooling_off_days',     '30'),
    ('partner_withholding_rate_pph21',       '2.5'),
    ('partner_withholding_rate_pph23',       '2.0'),
    ('partner_withholding_no_npwp_surcharge','20')
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS partners (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name                 TEXT NOT NULL,
    work_role                 TEXT,
    company_name              TEXT,
    office_address            TEXT,
    email                     TEXT NOT NULL UNIQUE,
    phone                     TEXT,
    preferred_language        TEXT DEFAULT 'id',
    entity_type               TEXT NOT NULL
        CHECK (entity_type IN ('individual','corporate_pt','corporate_cv','foreign')),
    npwp                      TEXT,
    nik                       TEXT,
    tax_withholding_category  TEXT NOT NULL DEFAULT 'tbd'
        CHECK (tax_withholding_category IN ('pph21','pph23','exempt','tbd')),
    fiscal_address            TEXT,
    bank_name                 TEXT,
    bank_account_holder       TEXT,
    bank_account_number       TEXT,
    ewallet_type              TEXT,
    ewallet_number            TEXT,
    payment_currency          TEXT NOT NULL DEFAULT 'IDR',
    iban                      TEXT,
    payment_notes             TEXT,
    default_commission_type   TEXT NOT NULL DEFAULT 'percentage'
        CHECK (default_commission_type IN ('percentage','flat')),
    default_commission_value  NUMERIC(14,4) NOT NULL DEFAULT 10.0,
    onboarding_status         TEXT NOT NULL DEFAULT 'pending_approval'
        CHECK (onboarding_status IN ('pending_approval','active','inactive')),
    assigned_to               UUID REFERENCES users(id) ON DELETE SET NULL,
    pdp_consent_at            TIMESTAMPTZ,
    pdp_consent_version       TEXT,
    terms_accepted_at         TIMESTAMPTZ,
    terms_version             TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by                UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    deactivated_at            TIMESTAMPTZ,
    welcome_email_sent_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS partner_referrals (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id           UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
    -- NOTE: In production, partner_referrals.practice_id FK references practices(id).
    -- In tests, practices.id is INTEGER on the dev DB (type mismatch with UUID).
    -- We omit the FK constraint here so tests run against the partner module logic
    -- without depending on the real practices schema. The FK is enforced in migration 119.
    practice_id          UUID NOT NULL,
    share_percent        NUMERIC(5,2) NOT NULL DEFAULT 100.00
        CHECK (share_percent > 0 AND share_percent <= 100),
    referred_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    referred_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
    notes                TEXT,
    CONSTRAINT partner_referrals_practice_unique_v1 UNIQUE (practice_id)
);

CREATE TABLE IF NOT EXISTS partner_commissions (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id               UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
    referral_id              UUID REFERENCES partner_referrals(id) ON DELETE RESTRICT,
    -- FK omitted for same reason as partner_referrals.practice_id (see above).
    practice_id              UUID,
    entry_type               TEXT NOT NULL
        CHECK (entry_type IN ('accrual','clawback','manual_adjustment')),
    related_commission_id    UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,
    base_amount_idr          NUMERIC(16,2) NOT NULL,
    commission_type_snapshot TEXT NOT NULL
        CHECK (commission_type_snapshot IN ('percentage','flat')),
    commission_value_snapshot NUMERIC(14,4) NOT NULL,
    rule_source              TEXT NOT NULL DEFAULT 'partner_default'
        CHECK (rule_source IN ('partner_default','manual_override')),
    assigned_to_snapshot     UUID REFERENCES users(id) ON DELETE SET NULL,
    gross_amount_idr         NUMERIC(16,2) NOT NULL,
    withholding_category     TEXT NOT NULL DEFAULT 'tbd'
        CHECK (withholding_category IN ('pph21','pph23','exempt','tbd')),
    withholding_rate         NUMERIC(6,4) NOT NULL DEFAULT 0.0,
    withholding_amount_idr   NUMERIC(16,2) NOT NULL DEFAULT 0.0,
    net_amount_idr           NUMERIC(16,2) NOT NULL,
    status                   TEXT NOT NULL DEFAULT 'accrued'
        CHECK (status IN (
            'accrued','approved','paid',
            'clawback_pending','offset_applied',
            'waived','repaid'
        )),
    accrued_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    eligible_for_approval_at TIMESTAMPTZ NOT NULL,
    approved_at              TIMESTAMPTZ,
    approved_by              UUID REFERENCES users(id) ON DELETE SET NULL,
    paid_at                  TIMESTAMPTZ,
    paid_by                  UUID REFERENCES users(id) ON DELETE SET NULL,
    paid_via                 TEXT,
    payment_reference        TEXT,
    payment_proof_url        TEXT,
    receipt_type             TEXT
        CHECK (receipt_type IS NULL OR receipt_type IN ('kwitansi','invoice','none')),
    receipt_file_url         TEXT,
    manual_override_reason   TEXT,
    clawback_reason          TEXT,
    waiver_reason            TEXT,
    idempotency_key          TEXT UNIQUE,
    commission_email_sent_at TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS partner_audit_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id    UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action        TEXT NOT NULL,
    before_json   JSONB,
    after_json    JSONB,
    reason        TEXT,
    at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS partner_email_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_type TEXT NOT NULL CHECK (email_type IN ('welcome','commission_earned')),
    partner_id UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
    commission_id UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,
    to_email TEXT NOT NULL,
    cc_emails TEXT[] DEFAULT '{}',
    subject TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed_dlq')),
    attempts INT NOT NULL DEFAULT 0,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    idempotency_key TEXT UNIQUE
);
"""

_TEARDOWN_SQL = """
DROP TABLE IF EXISTS partner_email_outbox;
DROP TABLE IF EXISTS partner_audit_log;
DROP TABLE IF EXISTS partner_commissions;
DROP TABLE IF EXISTS partner_referrals;
DROP TABLE IF EXISTS partners;
DROP TABLE IF EXISTS system_settings;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS pg_temp.practices;
"""


@pytest_asyncio.fixture(scope="function")
async def db_conn() -> asyncpg.Connection:
    """
    Real asyncpg connection with all partner tables created for the test,
    then torn down afterward. DDL (CREATE TABLE) commits immediately;
    teardown DROPs ensure the next test sees a fresh schema.
    """
    conn = await asyncpg.connect(_DEFAULT_DB_URL)
    # Teardown from any previous failed run first
    await conn.execute(_TEARDOWN_SQL)
    # Create fresh schema
    await conn.execute(_SCHEMA_SQL)
    try:
        yield conn
    finally:
        await conn.execute(_TEARDOWN_SQL)
        await conn.close()


# --------------------------------------------------------------------------
# Factories
# --------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
def user_factory(db_conn: asyncpg.Connection) -> Callable[..., Coroutine[Any, Any, uuid.UUID]]:
    """Returns an async callable that inserts a user row and returns its UUID."""
    async def _create(
        *,
        email: str | None = None,
        role: str = "team",
    ) -> _UUIDWithId:
        uid = _UUIDWithId(int=uuid.uuid4().int)
        _email = email or f"user-{uid}@test.invalid"
        await db_conn.execute(
            "INSERT INTO users (id, email, role) VALUES ($1, $2, $3)",
            uuid.UUID(int=uid.int), _email, role,
        )
        return uid

    return _create


@pytest_asyncio.fixture(scope="function")
def practice_factory(db_conn: asyncpg.Connection) -> Callable[..., Coroutine[Any, Any, _UUIDWithId]]:
    """Returns an async callable that inserts a practice row into the temp practices
    table (session-scoped, shadows the real public.practices for this connection).

    Accepts optional kwargs for columns required by CommissionEngine:
    - total_invoiced_idr: NUMERIC(16,2), default 0
    - status: TEXT, default 'pending'
    - payment_status: TEXT, default 'pending'
    - completed_at: TIMESTAMPTZ, default None (NULL → engine falls back to now())
    """
    async def _create(
        *,
        total_invoiced_idr: Decimal = Decimal("0"),
        status: str = "pending",
        payment_status: str = "pending",
        completed_at: datetime | None = None,
    ) -> _UUIDWithId:
        pid = _UUIDWithId(int=uuid.uuid4().int)
        _completed_at = completed_at or (
            datetime.now(timezone.utc) if status == "completed" else None
        )
        await db_conn.execute(
            """
            INSERT INTO practices
                (id, total_invoiced_idr, status, payment_status, completed_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            uuid.UUID(int=pid.int),
            total_invoiced_idr, status, payment_status, _completed_at,
        )
        return pid

    return _create


@pytest_asyncio.fixture(scope="function")
def partner_factory(db_conn: asyncpg.Connection) -> Callable[..., Coroutine[Any, Any, _UUIDWithId]]:
    """Returns an async callable that inserts a partner and returns its UUID.

    Extended in Task 5 to accept commission/withholding kwargs:
    - default_commission_type: 'percentage'|'flat', default 'percentage'
    - default_commission_value: NUMERIC, default 10.0
    - tax_withholding_category: 'pph21'|'pph23'|'exempt'|'tbd', default 'tbd'
    """
    _counter = [0]

    async def _create(
        *,
        full_name: str | None = None,
        email: str | None = None,
        entity_type: str = "individual",
        assigned_to: uuid.UUID | None = None,
        default_commission_type: str = "percentage",
        default_commission_value: Decimal = Decimal("10.0"),
        tax_withholding_category: str = "tbd",
        preferred_language: str = "en",
    ) -> _UUIDWithId:
        _counter[0] += 1
        _full_name = full_name or f"Test Partner {_counter[0]}"
        _email = email or f"partner-{_counter[0]}-{uuid.uuid4().hex[:6]}@test.invalid"
        row = await db_conn.fetchrow(
            """
            INSERT INTO partners
                (full_name, email, entity_type, assigned_to,
                 default_commission_type, default_commission_value,
                 tax_withholding_category, preferred_language)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            _full_name, _email, entity_type, assigned_to,
            default_commission_type, default_commission_value,
            tax_withholding_category, preferred_language,
        )
        return _UUIDWithId(bytes=row["id"].bytes)

    return _create


@pytest_asyncio.fixture(scope="function")
def referral_factory(
    db_conn: asyncpg.Connection,
    practice_factory: Callable[..., Coroutine[Any, Any, _UUIDWithId]],
) -> Callable[..., Coroutine[Any, Any, _UUIDWithId]]:
    """Returns an async callable that inserts a partner_referral and returns its UUID."""
    async def _create(
        *,
        partner_id: uuid.UUID,
        practice_id: uuid.UUID | None = None,
        share_percent: Decimal = Decimal("100.00"),
    ) -> _UUIDWithId:
        _practice_id = practice_id or await practice_factory()
        row = await db_conn.fetchrow(
            """
            INSERT INTO partner_referrals (partner_id, practice_id, share_percent)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            partner_id, _practice_id, share_percent,
        )
        return _UUIDWithId(bytes=row["id"].bytes)

    return _create


@pytest_asyncio.fixture(scope="function")
async def admin(user_factory: Callable[..., Coroutine[Any, Any, _UUIDWithId]]) -> _UUIDWithId:
    """Inserts an admin user and returns its UUID (with .id attribute)."""
    return await user_factory(role="admin")


@pytest_asyncio.fixture(scope="function")
async def client_factory(db_conn: asyncpg.Connection):
    """Returns an async callable that inserts a clients row (into the existing live table)
    and returns an _IntWithId (int subclass with .id property).
    Cleans up inserted rows after the test.

    The live clients table uses INTEGER primary key (not UUID).
    We never CREATE or DROP this table — only INSERT and DELETE rows by id.
    """
    _counter = [0]
    _inserted_ids: list[int] = []

    async def _create(
        *,
        full_name: str | None = None,
        email: str | None = None,
    ) -> _IntWithId:
        _counter[0] += 1
        _full_name = full_name or f"Test Client {_counter[0]}"
        _email = email or f"client-{_counter[0]}-{uuid.uuid4().hex[:6]}@test.invalid"
        row = await db_conn.fetchrow(
            "INSERT INTO clients (full_name, email) VALUES ($1, $2) RETURNING id",
            _full_name, _email,
        )
        cid = _IntWithId(row["id"])
        _inserted_ids.append(int(cid))
        return cid

    yield _create

    # Cleanup: delete inserted test clients (dependent rows deleted via CASCADE or already gone)
    if _inserted_ids:
        await db_conn.execute(
            "DELETE FROM clients WHERE id = ANY($1::int[])",
            _inserted_ids,
        )


@pytest_asyncio.fixture(scope="function")
def commission_factory(
    db_conn: asyncpg.Connection,
    practice_factory: Callable[..., Coroutine[Any, Any, _UUIDWithId]],
) -> Callable[..., Coroutine[Any, Any, "_UUIDWithId"]]:
    """Returns an async callable that inserts a partner_commissions row and returns its UUID.

    Accepts:
    - partner_id: UUID (required)
    - practice_client_id: UUID | None — if given, creates a practice linked to this client
    - status: CommissionStatus, default 'accrued'
    - net_amount_idr: Decimal, default 500_000
    - gross_amount_idr: Decimal, default same as net_amount_idr
    - withholding_amount_idr: Decimal, default 0
    - withholding_category: str, default 'tbd'
    - paid_via: str | None
    - payment_reference: str | None
    - receipt_file_url: str | None
    """
    async def _create(
        *,
        partner_id: uuid.UUID,
        practice_client_id: int | None = None,
        status: str = "accrued",
        net_amount_idr: Decimal = Decimal("500000"),
        gross_amount_idr: Decimal | None = None,
        withholding_amount_idr: Decimal = Decimal("0"),
        withholding_category: str = "tbd",
        paid_via: str | None = None,
        payment_reference: str | None = None,
        receipt_file_url: str | None = None,
    ) -> _UUIDWithId:
        _gross = gross_amount_idr if gross_amount_idr is not None else net_amount_idr

        # Create a practice stub (optionally linked to a client)
        prac_id = await practice_factory(
            status="completed" if status in ("approved", "paid") else "pending",
            payment_status="paid" if status == "paid" else "pending",
            total_invoiced_idr=_gross,
        )
        # If client provided, update the practice to link it + set a service_type
        if practice_client_id is not None:
            await db_conn.execute(
                "UPDATE practices SET client_id = $1, service_type = 'KITAS E33G' WHERE id = $2",
                int(practice_client_id), uuid.UUID(int=prac_id.int),
            )

        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        paid_at = now if status == "paid" else None

        row = await db_conn.fetchrow(
            """
            INSERT INTO partner_commissions (
                partner_id, practice_id,
                entry_type, base_amount_idr,
                commission_type_snapshot, commission_value_snapshot,
                rule_source,
                gross_amount_idr, withholding_category,
                withholding_rate, withholding_amount_idr, net_amount_idr,
                status, accrued_at, eligible_for_approval_at,
                paid_at, paid_via, payment_reference, receipt_file_url
            ) VALUES (
                $1, $2,
                'accrual', $3,
                'percentage', 10.0,
                'partner_default',
                $4, $5,
                0.0, $6, $7,
                $8, NOW(), NOW(),
                $9, $10, $11, $12
            )
            RETURNING id
            """,
            uuid.UUID(int=partner_id.int),
            uuid.UUID(int=prac_id.int),
            _gross,        # base_amount_idr
            _gross,        # gross_amount_idr
            withholding_category,
            withholding_amount_idr,
            net_amount_idr,
            status,
            paid_at,
            paid_via,
            payment_reference,
            receipt_file_url,
        )
        return _UUIDWithId(bytes=row["id"].bytes)

    return _create
