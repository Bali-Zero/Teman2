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
from decimal import Decimal
from typing import Any, Callable, Coroutine

import asyncpg
import pytest_asyncio


def _shield(pkg_name: str, path: list[str] | None = None) -> None:
    """Install a namespace in sys.modules if the real package isn't there yet.

    We set __path__ to the real filesystem path so submodule discovery still
    works, but we don't execute the heavy __init__.py.
    """
    if pkg_name not in sys.modules:
        mod = _types.ModuleType(pkg_name)
        if path is not None:
            mod.__path__ = path  # type: ignore[assignment]
        else:
            mod.__path__ = []  # type: ignore[assignment]
        sys.modules[pkg_name] = mod


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

CREATE TABLE IF NOT EXISTS processes (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
    process_id           UUID NOT NULL REFERENCES processes(id) ON DELETE RESTRICT,
    share_percent        NUMERIC(5,2) NOT NULL DEFAULT 100.00
        CHECK (share_percent > 0 AND share_percent <= 100),
    referred_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    referred_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
    notes                TEXT,
    CONSTRAINT partner_referrals_process_unique_v1 UNIQUE (process_id)
);

CREATE TABLE IF NOT EXISTS partner_commissions (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id               UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
    referral_id              UUID REFERENCES partner_referrals(id) ON DELETE RESTRICT,
    process_id               UUID REFERENCES processes(id) ON DELETE RESTRICT,
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
"""

_TEARDOWN_SQL = """
DROP TABLE IF EXISTS partner_audit_log;
DROP TABLE IF EXISTS partner_commissions;
DROP TABLE IF EXISTS partner_referrals;
DROP TABLE IF EXISTS partners;
DROP TABLE IF EXISTS processes;
DROP TABLE IF EXISTS users;
"""


@pytest_asyncio.fixture
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

@pytest_asyncio.fixture
def user_factory(db_conn: asyncpg.Connection) -> Callable[..., Coroutine[Any, Any, uuid.UUID]]:
    """Returns an async callable that inserts a user row and returns its UUID."""
    async def _create(
        *,
        email: str | None = None,
        role: str = "team",
    ) -> uuid.UUID:
        uid = uuid.uuid4()
        _email = email or f"user-{uid}@test.invalid"
        await db_conn.execute(
            "INSERT INTO users (id, email, role) VALUES ($1, $2, $3)",
            uid, _email, role,
        )
        return uid

    return _create


@pytest_asyncio.fixture
def process_factory(db_conn: asyncpg.Connection) -> Callable[..., Coroutine[Any, Any, uuid.UUID]]:
    """Returns an async callable that inserts a process row and returns its UUID."""
    async def _create() -> uuid.UUID:
        pid = uuid.uuid4()
        await db_conn.execute(
            "INSERT INTO processes (id) VALUES ($1)",
            pid,
        )
        return pid

    return _create


@pytest_asyncio.fixture
def partner_factory(db_conn: asyncpg.Connection) -> Callable[..., Coroutine[Any, Any, uuid.UUID]]:
    """Returns an async callable that inserts a partner and returns its UUID."""
    _counter = [0]

    async def _create(
        *,
        full_name: str | None = None,
        email: str | None = None,
        entity_type: str = "individual",
        assigned_to: uuid.UUID | None = None,
    ) -> uuid.UUID:
        _counter[0] += 1
        _full_name = full_name or f"Test Partner {_counter[0]}"
        _email = email or f"partner-{_counter[0]}-{uuid.uuid4().hex[:6]}@test.invalid"
        row = await db_conn.fetchrow(
            """
            INSERT INTO partners (full_name, email, entity_type, assigned_to)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            _full_name, _email, entity_type, assigned_to,
        )
        return row["id"]

    return _create


@pytest_asyncio.fixture
def referral_factory(
    db_conn: asyncpg.Connection,
    process_factory: Callable[..., Coroutine[Any, Any, uuid.UUID]],
) -> Callable[..., Coroutine[Any, Any, uuid.UUID]]:
    """Returns an async callable that inserts a partner_referral and returns its UUID."""
    async def _create(
        *,
        partner_id: uuid.UUID,
        process_id: uuid.UUID | None = None,
        share_percent: Decimal = Decimal("100.00"),
    ) -> uuid.UUID:
        _process_id = process_id or await process_factory()
        row = await db_conn.fetchrow(
            """
            INSERT INTO partner_referrals (partner_id, process_id, share_percent)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            partner_id, _process_id, share_percent,
        )
        return row["id"]

    return _create
