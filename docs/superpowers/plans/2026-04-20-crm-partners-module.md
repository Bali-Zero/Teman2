# CRM Partners Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build v1 of the Partners module: anagrafica + commission ledger + role-gated portal + Brevo emails, formalizing Bali Zero's third-party referral network end-to-end in the CRM.

**Architecture:** Four new Postgres tables (migration 119) with an append-only commission ledger. EventBus subscriber on `practice.status_changed` drives accrual; 30-day cooling-off gates approval; admin/finance perms gate payment. Two Next.js route namespaces (`/portal/partners/*` team, `/portal/partner/*` self) share middleware role-gating. Welcome + commission emails via Brevo from `zantara@balizero.com`.

**Tech Stack:** Python 3.11 + FastAPI + asyncpg, Postgres, Next.js 16 (App Router) + Tailwind, jinja2 email templates, Brevo HTTP API, existing in-process+PG EventBus.

**Spec:** `docs/superpowers/specs/2026-04-20-crm-partners-module.md`
**Council:** `docs/superpowers/specs/2026-04-20-partners-brainstorm/99-synthesis.md`
**Branch:** `feat/crm-partners-module` (isolated worktree).

---

## File Structure

### Backend (`apps/backend-rag/backend/`)

- `migrations/migration_119_partners.py` — schema (4 tables + 2 system_settings rows)
- `services/crm/partners/__init__.py` — package exports
- `services/crm/partners/models.py` — `@dataclass` Partner, PartnerReferral, PartnerCommission
- `services/crm/partners/repository.py` — asyncpg CRUD, append-only guards, email-collision check
- `services/crm/partners/service.py` — business logic, audit-log writes, RBAC helpers
- `services/crm/partners/commission_engine.py` — accrual math, cooling-off, clawback+offset, idempotency
- `services/crm/partners/events.py` — EventBus subscriber + `partner_commission_changed` publisher
- `services/crm/partners/emails.py` — Brevo payload builder + jinja2 render
- `services/crm/partners/templates/welcome.md.j2` — welcome email template
- `services/crm/partners/templates/commission.md.j2` — commission-earned email template
- `app/routers/partners.py` — 20 FastAPI endpoints
- `app/setup/router_manifest.py` — add `RouterEntry` for partners

### Backend tests

- `tests/services/crm/partners/test_repository.py`
- `tests/services/crm/partners/test_service.py`
- `tests/services/crm/partners/test_commission_engine.py`
- `tests/services/crm/partners/test_events.py`
- `tests/services/crm/partners/test_emails.py`
- `tests/routers/test_partners.py`
- `tests/integration/test_partners_e2e.py`
- `tests/migrations/test_migration_119.py`

### Frontend (`apps/mouth/`)

- `src/app/portal/(authenticated)/partners/page.tsx` — team list view
- `src/app/portal/(authenticated)/partners/new/page.tsx` — create form
- `src/app/portal/(authenticated)/partners/[id]/page.tsx` — detail tabs
- `src/app/portal/(authenticated)/partners/[id]/edit/page.tsx` — edit form
- `src/app/portal/(authenticated)/partners/orphaned/page.tsx` — admin bulk reassign
- `src/app/portal/(authenticated)/partners/finance/page.tsx` — approve + pay queue + CSV
- `src/app/portal/(authenticated)/partner/dashboard/page.tsx` — partner summary
- `src/app/portal/(authenticated)/partner/referrals/page.tsx` — partner referrals list (sterilized)
- `src/app/portal/(authenticated)/partner/commissions/page.tsx` — partner ledger
- `src/app/portal/(authenticated)/partner/profile/page.tsx` — partner own profile (read-only)
- `src/lib/api/partners.ts` — typed fetch client
- `src/components/portal/ReferrerDropdown.tsx` — shared dropdown for process forms
- `src/middleware.ts` — **modify** to role-gate `/portal/partner/*`

### Frontend tests

- `tests/app/portal/partners.spec.tsx` — team list + create flow
- `tests/app/portal/partner-dashboard.spec.tsx` — partner view sterilization
- `tests/middleware.spec.ts` — role-gate logic

### Responsibility boundaries

- `repository.py` = SQL only. No business logic, no audit writes, no event fires.
- `service.py` = orchestrates repository + audit log + emits events. No SQL.
- `commission_engine.py` = pure calculation + status transitions. Calls `repository`.
- `events.py` = subscribe/unsubscribe + payload shape. Wraps `commission_engine`.
- `emails.py` = render + POST to Brevo endpoint. Idempotency check + `notification_log` write.
- `routers/partners.py` = HTTP → service mapping. Uses `verify_partner_access`.
- Frontend pages = data fetching + layout. `api/partners.ts` is the only fetch surface.

---

## Execution Order

Tasks are ordered to keep each commit shippable:

1. **Migration 119** — schema lives before code touches it.
2. **Models + repository** — data access with append-only enforcement.
3. **Service + RBAC + audit** — business layer.
4. **Commission engine** — the single most complex unit; tested in isolation.
5. **EventBus wiring** — glues engine to `practice.status_changed`.
6. **API router** — thin HTTP layer over service.
7. **Emails** — Brevo templates + idempotency.
8. **Team frontend** — list, detail, edit, finance queue.
9. **Partner frontend + middleware** — role-gated portal.
10. **E2E integration test** — end-to-end proof: process flips → ledger + email.

One commit per task group. Run `pytest backend/tests/services/crm/partners/ -q` plus targeted tests before each commit. No force push. Never `--no-verify`.

---

## Task 1: Migration 119 — schema

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_119_partners.py`
- Test: `apps/backend-rag/backend/tests/migrations/test_migration_119.py`

- [ ] **Step 1.1: Write the failing migration test**

```python
# tests/migrations/test_migration_119.py
import pytest
from backend.migrations.migration_119_partners import apply, rollback


@pytest.mark.asyncio
async def test_migration_119_creates_partners(db_conn):
    await apply(db_conn)
    rows = await db_conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'partners'"
    )
    col_names = {r["column_name"] for r in rows}
    assert "default_commission_value" in col_names
    assert "tax_withholding_category" in col_names
    assert "welcome_email_sent_at" in col_names
    assert "pdp_consent_version" in col_names
    await rollback(db_conn)


@pytest.mark.asyncio
async def test_migration_119_creates_4_tables(db_conn):
    await apply(db_conn)
    expected = {"partners", "partner_referrals", "partner_commissions", "partner_audit_log"}
    rows = await db_conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
        "AND tablename = ANY($1)",
        list(expected),
    )
    assert {r["tablename"] for r in rows} == expected
    await rollback(db_conn)


@pytest.mark.asyncio
async def test_migration_119_seeds_system_settings(db_conn):
    await apply(db_conn)
    rows = await db_conn.fetch(
        "SELECT key FROM system_settings WHERE key LIKE 'partner_%'"
    )
    keys = {r["key"] for r in rows}
    assert "partner_clawback_auto_writeoff_idr" in keys
    assert "partner_accrual_cooling_off_days" in keys
    await rollback(db_conn)


@pytest.mark.asyncio
async def test_migration_119_idempotent(db_conn):
    await apply(db_conn)
    # Second apply must not raise — idempotent DO blocks + IF NOT EXISTS
    await apply(db_conn)
    await rollback(db_conn)


@pytest.mark.asyncio
async def test_migration_119_rollback(db_conn):
    await apply(db_conn)
    await rollback(db_conn)
    rows = await db_conn.fetch(
        "SELECT tablename FROM pg_tables WHERE tablename LIKE 'partner%'"
    )
    assert rows == []
```

- [ ] **Step 1.2: Run test to verify it fails (module missing)**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/migrations/test_migration_119.py -v
```

Expected: FAIL with `ImportError: cannot import name 'apply' from 'backend.migrations.migration_119_partners'`.

- [ ] **Step 1.3: Write the migration**

Copy the SQL bodies verbatim from spec §3.1, §3.2, §3.3, §3.4, §3.5. Wrap each `CREATE TABLE` in a `DO $$ ... END $$;` block guarded by `IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = '<name>')`. Indexes use `CREATE INDEX IF NOT EXISTS`. System settings uses `ON CONFLICT (key) DO NOTHING`.

Shape the file after `migration_118_clients_referrer_url.py`:

```python
# apps/backend-rag/backend/migrations/migration_119_partners.py
"""Migration 119: Partners module — 4 tables + 2 system settings.

Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3
Council: docs/superpowers/specs/2026-04-20-partners-brainstorm/99-synthesis.md
Author: Claude Opus 4.7
Date: 2026-04-20
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    # --- partners ---
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partners'
            ) THEN
                CREATE TABLE partners (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    full_name TEXT NOT NULL,
                    work_role TEXT,
                    company_name TEXT,
                    office_address TEXT,
                    email TEXT NOT NULL UNIQUE,
                    phone TEXT,
                    preferred_language TEXT DEFAULT 'id',
                    entity_type TEXT NOT NULL
                        CHECK (entity_type IN ('individual','corporate_pt','corporate_cv','foreign')),
                    npwp TEXT,
                    nik TEXT,
                    tax_withholding_category TEXT NOT NULL DEFAULT 'tbd'
                        CHECK (tax_withholding_category IN ('pph21','pph23','exempt','tbd')),
                    fiscal_address TEXT,
                    bank_name TEXT,
                    bank_account_holder TEXT,
                    bank_account_number TEXT,
                    ewallet_type TEXT,
                    ewallet_number TEXT,
                    payment_currency TEXT NOT NULL DEFAULT 'IDR',
                    iban TEXT,
                    payment_notes TEXT,
                    default_commission_type TEXT NOT NULL DEFAULT 'percentage'
                        CHECK (default_commission_type IN ('percentage','flat')),
                    default_commission_value NUMERIC(14,4) NOT NULL DEFAULT 10.0,
                    onboarding_status TEXT NOT NULL DEFAULT 'pending_approval'
                        CHECK (onboarding_status IN ('pending_approval','active','inactive')),
                    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
                    pdp_consent_at TIMESTAMPTZ,
                    pdp_consent_version TEXT,
                    terms_accepted_at TIMESTAMPTZ,
                    terms_version TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    deactivated_at TIMESTAMPTZ,
                    welcome_email_sent_at TIMESTAMPTZ
                );
            END IF;
        END $$;
    """)

    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_email ON partners (email);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_partners_assigned_to ON partners (assigned_to) WHERE assigned_to IS NOT NULL;")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_partners_onboarding_status ON partners (onboarding_status);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_partners_entity_type ON partners (entity_type);")

    # --- partner_referrals ---
    # (copy SQL verbatim from spec §3.2 into another DO $$ block + IF NOT EXISTS)
    # --- partner_commissions ---
    # (copy SQL verbatim from spec §3.3)
    # --- partner_audit_log ---
    # (copy SQL verbatim from spec §3.4)

    # --- system_settings rows ---
    await conn.execute("""
        INSERT INTO system_settings (key, value, description) VALUES
          ('partner_clawback_auto_writeoff_idr', '0',
           'If > 0, clawback rows below this IDR amount auto-waive on creation. Default 0 = disabled.'),
          ('partner_accrual_cooling_off_days', '30',
           'Days between accrual and eligibility for approval. Default 30.')
        ON CONFLICT (key) DO NOTHING;
    """)

    logger.info("✅ Migration 119: 4 tables + 2 system_settings rows")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS partner_audit_log;")
    await conn.execute("DROP TABLE IF EXISTS partner_commissions;")
    await conn.execute("DROP TABLE IF EXISTS partner_referrals;")
    await conn.execute("DROP TABLE IF EXISTS partners;")
    await conn.execute(
        "DELETE FROM system_settings WHERE key IN "
        "('partner_clawback_auto_writeoff_idr','partner_accrual_cooling_off_days');"
    )
    logger.info("Migration 119 rollback: 4 tables dropped, 2 settings removed")
```

Complete the three omitted `DO $$` blocks (`partner_referrals`, `partner_commissions`, `partner_audit_log`) by copying the SQL from spec §3.2–§3.4 verbatim. Every index from those sections must have its own `CREATE INDEX IF NOT EXISTS` call after the `DO $$` block.

- [ ] **Step 1.4: Run test until all 5 pass**

```bash
PYTHONPATH=. pytest backend/tests/migrations/test_migration_119.py -v
```

Expected: 5 passed.

- [ ] **Step 1.5: Run full backend test suite smoke**

```bash
PYTHONPATH=. pytest backend/tests/migrations/ -q
```

Expected: all green (no regressions to existing migration tests).

- [ ] **Step 1.6: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_119_partners.py \
        apps/backend-rag/backend/tests/migrations/test_migration_119.py
git commit -m "feat(partners): migration 119 — partners, referrals, commissions ledger, audit log

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Models (dataclasses)

**Files:**

- Create: `apps/backend-rag/backend/services/crm/partners/__init__.py`
- Create: `apps/backend-rag/backend/services/crm/partners/models.py`

- [ ] **Step 2.1: Create package init**

```python
# apps/backend-rag/backend/services/crm/partners/__init__.py
"""Partners module — third-party referral + commission management.

Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md
"""
```

- [ ] **Step 2.2: Write models**

```python
# apps/backend-rag/backend/services/crm/partners/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

EntityType = Literal["individual", "corporate_pt", "corporate_cv", "foreign"]
WithholdingCategory = Literal["pph21", "pph23", "exempt", "tbd"]
CommissionType = Literal["percentage", "flat"]
OnboardingStatus = Literal["pending_approval", "active", "inactive"]
CommissionStatus = Literal[
    "accrued", "approved", "paid",
    "clawback_pending", "offset_applied",
    "waived", "repaid",
]
CommissionEntryType = Literal["accrual", "clawback", "manual_adjustment"]
RuleSource = Literal["partner_default", "manual_override"]


@dataclass
class Partner:
    id: UUID
    full_name: str
    email: str
    entity_type: EntityType
    tax_withholding_category: WithholdingCategory
    default_commission_type: CommissionType
    default_commission_value: Decimal
    onboarding_status: OnboardingStatus
    payment_currency: str
    preferred_language: str
    created_at: datetime
    updated_at: datetime

    # optional fields
    work_role: str | None = None
    company_name: str | None = None
    office_address: str | None = None
    phone: str | None = None
    npwp: str | None = None
    nik: str | None = None
    fiscal_address: str | None = None
    bank_name: str | None = None
    bank_account_holder: str | None = None
    bank_account_number: str | None = None
    ewallet_type: str | None = None
    ewallet_number: str | None = None
    iban: str | None = None
    payment_notes: str | None = None
    assigned_to: UUID | None = None
    pdp_consent_at: datetime | None = None
    pdp_consent_version: str | None = None
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None
    created_by: UUID | None = None
    deactivated_at: datetime | None = None
    welcome_email_sent_at: datetime | None = None


@dataclass
class PartnerReferral:
    id: UUID
    partner_id: UUID
    process_id: UUID
    share_percent: Decimal
    referred_at: datetime
    referred_by_user_id: UUID | None = None
    notes: str | None = None


@dataclass
class PartnerCommission:
    id: UUID
    partner_id: UUID
    entry_type: CommissionEntryType
    base_amount_idr: Decimal
    commission_type_snapshot: CommissionType
    commission_value_snapshot: Decimal
    rule_source: RuleSource
    gross_amount_idr: Decimal
    withholding_category: WithholdingCategory
    withholding_rate: Decimal
    withholding_amount_idr: Decimal
    net_amount_idr: Decimal
    status: CommissionStatus
    accrued_at: datetime
    eligible_for_approval_at: datetime
    created_at: datetime

    referral_id: UUID | None = None
    process_id: UUID | None = None
    related_commission_id: UUID | None = None
    assigned_to_snapshot: UUID | None = None
    approved_at: datetime | None = None
    approved_by: UUID | None = None
    paid_at: datetime | None = None
    paid_by: UUID | None = None
    paid_via: str | None = None
    payment_reference: str | None = None
    payment_proof_url: str | None = None
    receipt_type: Literal["kwitansi", "invoice", "none"] | None = None
    receipt_file_url: str | None = None
    manual_override_reason: str | None = None
    clawback_reason: str | None = None
    waiver_reason: str | None = None
    idempotency_key: str | None = None
    commission_email_sent_at: datetime | None = None


@dataclass
class PartnerAuditLogEntry:
    id: UUID
    partner_id: UUID
    action: str
    at: datetime
    actor_user_id: UUID | None = None
    before_json: dict | None = None
    after_json: dict | None = None
    reason: str | None = None
```

- [ ] **Step 2.3: Verify import**

```bash
PYTHONPATH=. python -c "from backend.services.crm.partners.models import Partner, PartnerCommission; print('OK')"
```

Expected: `OK`.

- [ ] **Step 2.4: Commit**

```bash
git add apps/backend-rag/backend/services/crm/partners/__init__.py \
        apps/backend-rag/backend/services/crm/partners/models.py
git commit -m "feat(partners): dataclass models for Partner, Referral, Commission, AuditLog

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Repository (asyncpg, append-only guards)

**Files:**

- Create: `apps/backend-rag/backend/services/crm/partners/repository.py`
- Test: `apps/backend-rag/backend/tests/services/crm/partners/__init__.py` (empty)
- Test: `apps/backend-rag/backend/tests/services/crm/partners/test_repository.py`

- [ ] **Step 3.1: Write failing repository tests**

```python
# tests/services/crm/partners/test_repository.py
from decimal import Decimal

import asyncpg
import pytest

from backend.services.crm.partners.repository import PartnersRepository


@pytest.fixture
async def repo(db_conn):
    return PartnersRepository(db_conn)


@pytest.mark.asyncio
async def test_insert_partner_returns_id_and_defaults(repo):
    pid = await repo.insert_partner(
        full_name="Hotel Kama",
        email="referrals@hotelkama.id",
        entity_type="corporate_pt",
    )
    p = await repo.get_partner(pid)
    assert p.full_name == "Hotel Kama"
    assert p.onboarding_status == "pending_approval"
    assert p.default_commission_value == Decimal("10.0")
    assert p.default_commission_type == "percentage"
    assert p.tax_withholding_category == "tbd"
    assert p.payment_currency == "IDR"


@pytest.mark.asyncio
async def test_email_unique_violation(repo):
    await repo.insert_partner(
        full_name="A", email="dupe@x.io", entity_type="individual"
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await repo.insert_partner(
            full_name="B", email="dupe@x.io", entity_type="individual"
        )


@pytest.mark.asyncio
async def test_email_collision_with_internal_user_is_rejected(repo, db_conn):
    await db_conn.execute(
        "INSERT INTO users (id, email, role) VALUES (gen_random_uuid(), $1, 'team')",
        "zero@balizero.com",
    )
    with pytest.raises(ValueError, match="email is already a team/admin user"):
        await repo.insert_partner(
            full_name="Zero Partner",
            email="zero@balizero.com",
            entity_type="individual",
        )


@pytest.mark.asyncio
async def test_list_partners_filters_by_assigned_to(repo, user_factory):
    u1 = await user_factory(role="team")
    u2 = await user_factory(role="team")
    p1 = await repo.insert_partner(full_name="P1", email="p1@x.io",
                                   entity_type="individual", assigned_to=u1)
    _ = await repo.insert_partner(full_name="P2", email="p2@x.io",
                                  entity_type="individual", assigned_to=u2)
    results = await repo.list_partners(assigned_to=u1)
    assert len(results) == 1
    assert results[0].id == p1


@pytest.mark.asyncio
async def test_commission_insert_and_append_only_delete_blocked(repo):
    pid = await repo.insert_partner(
        full_name="Hotel", email="a@b.io", entity_type="individual"
    )
    cid = await repo.insert_commission(
        partner_id=pid,
        entry_type="accrual",
        base_amount_idr=Decimal("10000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("1000000"),
        net_amount_idr=Decimal("1000000"),
        idempotency_key="accrual:proc-1:2026-04-20T00:00:00",
    )
    # Repository must refuse DELETE (append-only contract)
    with pytest.raises(RuntimeError, match="append-only"):
        await repo.delete_commission(cid)


@pytest.mark.asyncio
async def test_commission_idempotency_key_unique(repo):
    pid = await repo.insert_partner(
        full_name="H", email="h@b.io", entity_type="individual"
    )
    await repo.insert_commission(
        partner_id=pid, entry_type="accrual",
        base_amount_idr=Decimal("1000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("100"),
        net_amount_idr=Decimal("100"),
        idempotency_key="same-key",
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await repo.insert_commission(
            partner_id=pid, entry_type="accrual",
            base_amount_idr=Decimal("1000"),
            commission_type_snapshot="percentage",
            commission_value_snapshot=Decimal("10.0"),
            gross_amount_idr=Decimal("100"),
            net_amount_idr=Decimal("100"),
            idempotency_key="same-key",
        )
```

Additional tests to write in same file (same shape as above — cover branches):

- `test_update_partner_whitelist_rejects_status_column` — `update_partner` must reject updates to `onboarding_status` (lifecycle is separate method).
- `test_activate_partner_transitions_status` — `activate_partner(pid)` flips `pending_approval → active`; idempotent.
- `test_deactivate_partner_sets_status_and_timestamp` — `deactivate_partner(pid)` flips to `inactive`, sets `deactivated_at`.
- `test_reassign_partner_changes_assigned_to` — `reassign_partner(pid, new_user_id)` writes and returns nothing.
- `test_orphan_partners_of_user` — `orphan_partners_of_user(user_id)` sets `assigned_to = NULL` for all partners of a given user, returns count.
- `test_referral_unique_process_id_violation` — inserting 2 referrals on same process raises `UniqueViolationError`.
- `test_update_commission_status_allows_accrued_to_approved` — `update_commission_status(cid, "approved", approved_by=uid)` succeeds.
- `test_update_commission_status_rejects_invalid_transition` — `accrued → paid` skipping `approved` raises `ValueError`.
- `test_audit_log_insert_and_list` — `insert_audit(partner_id, action, actor, before, after, reason)`; `list_audit_for_partner(pid)` returns newest-first.

- [ ] **Step 3.2: Run tests — they fail with ImportError**

```bash
PYTHONPATH=. pytest backend/tests/services/crm/partners/test_repository.py -v
```

- [ ] **Step 3.3: Write `PartnersRepository`**

```python
# backend/services/crm/partners/repository.py
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from backend.services.crm.partners.models import (
    Partner, PartnerReferral, PartnerCommission, PartnerAuditLogEntry,
    EntityType, CommissionType, CommissionStatus, CommissionEntryType,
    WithholdingCategory, RuleSource,
)

logger = logging.getLogger(__name__)

_ALLOWED_TRANSITIONS: dict[CommissionStatus, set[CommissionStatus]] = {
    "accrued": {"approved"},
    "approved": {"paid"},
    "paid": set(),
    "clawback_pending": {"offset_applied", "waived", "repaid"},
    "offset_applied": set(),
    "waived": set(),
    "repaid": set(),
}

_PARTNER_UPDATABLE_COLS = {
    "full_name", "work_role", "company_name", "office_address",
    "email", "phone", "preferred_language",
    "entity_type", "npwp", "nik", "tax_withholding_category", "fiscal_address",
    "bank_name", "bank_account_holder", "bank_account_number",
    "ewallet_type", "ewallet_number", "payment_currency", "iban", "payment_notes",
    "default_commission_type", "default_commission_value",
    "pdp_consent_at", "pdp_consent_version", "terms_accepted_at", "terms_version",
}
# NB: onboarding_status, assigned_to, welcome_email_sent_at are ONLY settable
# via their dedicated methods (activate_partner, reassign_partner, mark_welcome_sent).


class PartnersRepository:
    """SQL layer. No business logic, no audit writes, no event emission."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    # ── Partner CRUD ────────────────────────────────────────────────────

    async def insert_partner(
        self,
        *,
        full_name: str,
        email: str,
        entity_type: EntityType,
        assigned_to: UUID | None = None,
        created_by: UUID | None = None,
        **optional: Any,
    ) -> UUID:
        await self._assert_email_is_not_internal(email)
        cols = ["full_name", "email", "entity_type", "assigned_to", "created_by"]
        vals: list[Any] = [full_name, email, entity_type, assigned_to, created_by]
        for k, v in optional.items():
            if k not in _PARTNER_UPDATABLE_COLS:
                raise ValueError(f"Field {k!r} is not insertable via insert_partner")
            cols.append(k); vals.append(v)
        placeholders = ", ".join(f"${i+1}" for i in range(len(vals)))
        sql = f"INSERT INTO partners ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"
        row = await self.conn.fetchrow(sql, *vals)
        return row["id"]

    async def _assert_email_is_not_internal(self, email: str) -> None:
        row = await self.conn.fetchrow(
            "SELECT 1 FROM users WHERE email = $1 AND role IN ('team','admin')",
            email,
        )
        if row is not None:
            raise ValueError(f"email is already a team/admin user: {email!r}")

    async def get_partner(self, partner_id: UUID) -> Partner | None:
        row = await self.conn.fetchrow("SELECT * FROM partners WHERE id = $1", partner_id)
        return self._row_to_partner(row) if row else None

    async def list_partners(
        self,
        *,
        assigned_to: UUID | None = None,
        onboarding_status: str | None = None,
        orphaned: bool = False,
        search: str | None = None,
        limit: int = 200,
    ) -> list[Partner]:
        where, args = ["TRUE"], []
        if assigned_to is not None:
            args.append(assigned_to); where.append(f"assigned_to = ${len(args)}")
        if onboarding_status is not None:
            args.append(onboarding_status); where.append(f"onboarding_status = ${len(args)}")
        if orphaned:
            where.append("assigned_to IS NULL")
        if search:
            args.append(f"%{search}%")
            where.append(f"(full_name ILIKE ${len(args)} OR email ILIKE ${len(args)} OR company_name ILIKE ${len(args)})")
        args.append(limit)
        sql = f"SELECT * FROM partners WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ${len(args)}"
        rows = await self.conn.fetch(sql, *args)
        return [self._row_to_partner(r) for r in rows]

    async def update_partner(self, partner_id: UUID, **fields: Any) -> None:
        bad = set(fields) - _PARTNER_UPDATABLE_COLS
        if bad:
            raise ValueError(f"Non-updatable fields: {bad}")
        if "email" in fields:
            await self._assert_email_is_not_internal(fields["email"])
        sets = [f"{k} = ${i+2}" for i, k in enumerate(fields)]
        sets.append(f"updated_at = now()")
        sql = f"UPDATE partners SET {', '.join(sets)} WHERE id = $1"
        await self.conn.execute(sql, partner_id, *fields.values())

    async def activate_partner(self, partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partners SET onboarding_status = 'active', updated_at = now() "
            "WHERE id = $1 AND onboarding_status = 'pending_approval'",
            partner_id,
        )

    async def deactivate_partner(self, partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partners SET onboarding_status = 'inactive', deactivated_at = now(), "
            "updated_at = now() WHERE id = $1",
            partner_id,
        )

    async def reassign_partner(self, partner_id: UUID, new_user_id: UUID | None) -> None:
        await self.conn.execute(
            "UPDATE partners SET assigned_to = $2, updated_at = now() WHERE id = $1",
            partner_id, new_user_id,
        )

    async def orphan_partners_of_user(self, user_id: UUID) -> int:
        result = await self.conn.execute(
            "UPDATE partners SET assigned_to = NULL, updated_at = now() WHERE assigned_to = $1",
            user_id,
        )
        # asyncpg returns "UPDATE <n>"
        return int(result.split()[-1])

    async def mark_welcome_sent(self, partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partners SET welcome_email_sent_at = now() "
            "WHERE id = $1 AND welcome_email_sent_at IS NULL",
            partner_id,
        )

    # ── Referrals ───────────────────────────────────────────────────────

    async def insert_referral(
        self, *, partner_id: UUID, process_id: UUID,
        referred_by_user_id: UUID | None = None,
        share_percent: Decimal = Decimal("100.00"),
        notes: str | None = None,
    ) -> UUID:
        row = await self.conn.fetchrow(
            """
            INSERT INTO partner_referrals
                (partner_id, process_id, share_percent, referred_by_user_id, notes)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            partner_id, process_id, share_percent, referred_by_user_id, notes,
        )
        return row["id"]

    async def get_referral_by_process(self, process_id: UUID) -> PartnerReferral | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM partner_referrals WHERE process_id = $1", process_id
        )
        return self._row_to_referral(row) if row else None

    async def list_referrals_for_partner(self, partner_id: UUID) -> list[PartnerReferral]:
        rows = await self.conn.fetch(
            "SELECT * FROM partner_referrals WHERE partner_id = $1 ORDER BY referred_at DESC",
            partner_id,
        )
        return [self._row_to_referral(r) for r in rows]

    async def update_referral_partner(self, referral_id: UUID, new_partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partner_referrals SET partner_id = $2 WHERE id = $1",
            referral_id, new_partner_id,
        )

    async def delete_referral(self, referral_id: UUID) -> None:
        # Referrals are deletable ONLY before any commission is accrued against them.
        row = await self.conn.fetchrow(
            "SELECT 1 FROM partner_commissions WHERE referral_id = $1 LIMIT 1",
            referral_id,
        )
        if row is not None:
            raise RuntimeError("Cannot delete referral with commissions recorded")
        await self.conn.execute("DELETE FROM partner_referrals WHERE id = $1", referral_id)

    # ── Commissions (append-only) ───────────────────────────────────────

    async def insert_commission(
        self,
        *,
        partner_id: UUID,
        entry_type: CommissionEntryType,
        base_amount_idr: Decimal,
        commission_type_snapshot: CommissionType,
        commission_value_snapshot: Decimal,
        gross_amount_idr: Decimal,
        net_amount_idr: Decimal,
        idempotency_key: str,
        referral_id: UUID | None = None,
        process_id: UUID | None = None,
        related_commission_id: UUID | None = None,
        rule_source: RuleSource = "partner_default",
        assigned_to_snapshot: UUID | None = None,
        withholding_category: WithholdingCategory = "tbd",
        withholding_rate: Decimal = Decimal("0.0"),
        withholding_amount_idr: Decimal = Decimal("0.0"),
        status: CommissionStatus = "accrued",
        eligible_for_approval_at: Any = None,
        manual_override_reason: str | None = None,
        clawback_reason: str | None = None,
    ) -> UUID:
        row = await self.conn.fetchrow(
            """
            INSERT INTO partner_commissions (
                partner_id, entry_type, referral_id, process_id, related_commission_id,
                base_amount_idr, commission_type_snapshot, commission_value_snapshot,
                rule_source, assigned_to_snapshot,
                gross_amount_idr, withholding_category, withholding_rate,
                withholding_amount_idr, net_amount_idr,
                status, eligible_for_approval_at,
                manual_override_reason, clawback_reason, idempotency_key
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,
                    COALESCE($17, now()),$18,$19,$20)
            RETURNING id
            """,
            partner_id, entry_type, referral_id, process_id, related_commission_id,
            base_amount_idr, commission_type_snapshot, commission_value_snapshot,
            rule_source, assigned_to_snapshot,
            gross_amount_idr, withholding_category, withholding_rate,
            withholding_amount_idr, net_amount_idr,
            status, eligible_for_approval_at,
            manual_override_reason, clawback_reason, idempotency_key,
        )
        return row["id"]

    async def get_commission(self, commission_id: UUID) -> PartnerCommission | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM partner_commissions WHERE id = $1", commission_id
        )
        return self._row_to_commission(row) if row else None

    async def list_commissions_for_partner(
        self, partner_id: UUID, *, status: CommissionStatus | None = None,
    ) -> list[PartnerCommission]:
        args: list[Any] = [partner_id]
        where = "partner_id = $1"
        if status is not None:
            args.append(status); where += f" AND status = $2"
        sql = f"SELECT * FROM partner_commissions WHERE {where} ORDER BY created_at DESC"
        rows = await self.conn.fetch(sql, *args)
        return [self._row_to_commission(r) for r in rows]

    async def list_pending_clawbacks(self, partner_id: UUID) -> list[PartnerCommission]:
        rows = await self.conn.fetch(
            "SELECT * FROM partner_commissions WHERE partner_id = $1 AND status = 'clawback_pending' "
            "ORDER BY accrued_at ASC",
            partner_id,
        )
        return [self._row_to_commission(r) for r in rows]

    async def update_commission_status(
        self,
        commission_id: UUID,
        new_status: CommissionStatus,
        *,
        approved_by: UUID | None = None,
        paid_by: UUID | None = None,
        paid_via: str | None = None,
        payment_reference: str | None = None,
        payment_proof_url: str | None = None,
        receipt_type: str | None = None,
        receipt_file_url: str | None = None,
        waiver_reason: str | None = None,
    ) -> None:
        current = await self.get_commission(commission_id)
        if current is None:
            raise ValueError(f"Commission {commission_id} not found")
        if new_status not in _ALLOWED_TRANSITIONS.get(current.status, set()):
            raise ValueError(
                f"Disallowed transition: {current.status!r} -> {new_status!r}"
            )
        fragments, args = ["status = $2"], [commission_id, new_status]
        if new_status == "approved":
            fragments += ["approved_at = now()", f"approved_by = ${len(args)+1}"]; args.append(approved_by)
        if new_status == "paid":
            fragments += [
                "paid_at = now()",
                f"paid_by = ${len(args)+1}", f"paid_via = ${len(args)+2}",
                f"payment_reference = ${len(args)+3}", f"payment_proof_url = ${len(args)+4}",
                f"receipt_type = ${len(args)+5}", f"receipt_file_url = ${len(args)+6}",
            ]
            args += [paid_by, paid_via, payment_reference, payment_proof_url,
                     receipt_type, receipt_file_url]
        if new_status == "waived":
            fragments += [f"waiver_reason = ${len(args)+1}"]; args.append(waiver_reason)
        sql = f"UPDATE partner_commissions SET {', '.join(fragments)} WHERE id = $1"
        await self.conn.execute(sql, *args)

    async def mark_commission_email_sent(self, commission_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partner_commissions SET commission_email_sent_at = now() "
            "WHERE id = $1 AND commission_email_sent_at IS NULL",
            commission_id,
        )

    async def delete_commission(self, commission_id: UUID) -> None:
        raise RuntimeError("partner_commissions is append-only; delete is forbidden")

    # ── Audit log ───────────────────────────────────────────────────────

    async def insert_audit(
        self,
        *,
        partner_id: UUID,
        action: str,
        actor_user_id: UUID | None = None,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO partner_audit_log
                (partner_id, actor_user_id, action, before_json, after_json, reason)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            partner_id, actor_user_id, action,
            json.dumps(before) if before else None,
            json.dumps(after) if after else None,
            reason,
        )

    async def list_audit_for_partner(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
        rows = await self.conn.fetch(
            "SELECT * FROM partner_audit_log WHERE partner_id = $1 ORDER BY at DESC",
            partner_id,
        )
        return [
            PartnerAuditLogEntry(
                id=r["id"], partner_id=r["partner_id"],
                actor_user_id=r["actor_user_id"], action=r["action"],
                before_json=json.loads(r["before_json"]) if r["before_json"] else None,
                after_json=json.loads(r["after_json"]) if r["after_json"] else None,
                reason=r["reason"], at=r["at"],
            )
            for r in rows
        ]

    # ── Row mappers ─────────────────────────────────────────────────────

    @staticmethod
    def _row_to_partner(row: asyncpg.Record) -> Partner:
        return Partner(**dict(row))

    @staticmethod
    def _row_to_referral(row: asyncpg.Record) -> PartnerReferral:
        return PartnerReferral(**dict(row))

    @staticmethod
    def _row_to_commission(row: asyncpg.Record) -> PartnerCommission:
        return PartnerCommission(**dict(row))
```

- [ ] **Step 3.4: Run repository tests**

```bash
PYTHONPATH=. pytest backend/tests/services/crm/partners/test_repository.py -v
```

Expected: all pass.

- [ ] **Step 3.5: Commit**

```bash
git add apps/backend-rag/backend/services/crm/partners/repository.py \
        apps/backend-rag/backend/tests/services/crm/partners/
git commit -m "feat(partners): asyncpg repository with append-only commissions + email collision guard

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Service + RBAC helper + audit wrapper

**Files:**

- Create: `apps/backend-rag/backend/services/crm/partners/service.py`
- Test: `apps/backend-rag/backend/tests/services/crm/partners/test_service.py`

The service orchestrates repository calls with audit-log writes. It is the ONLY caller that mints audit entries — the repository never writes audit rows on its own. The RBAC helper `verify_partner_access(user, partner)` is co-located here.

- [ ] **Step 4.1: Write failing service tests**

```python
# tests/services/crm/partners/test_service.py
import pytest
from decimal import Decimal
from fastapi import HTTPException

from backend.services.crm.partners.service import (
    PartnersService, verify_partner_access,
)


@pytest.fixture
async def svc(db_conn):
    return PartnersService(db_conn)


@pytest.mark.asyncio
async def test_create_partner_writes_audit_log(svc, user_factory):
    team = await user_factory(role="team")
    pid = await svc.create_partner(
        full_name="H", email="h@x.io", entity_type="individual",
        assigned_to=team, created_by=team,
    )
    audit = await svc.list_audit(pid)
    assert len(audit) == 1
    assert audit[0].action == "created"
    assert audit[0].actor_user_id == team


@pytest.mark.asyncio
async def test_activate_partner_requires_admin_and_audits(svc, user_factory):
    team = await user_factory(role="team")
    admin = await user_factory(role="admin")
    pid = await svc.create_partner(
        full_name="H", email="h2@x.io", entity_type="individual", created_by=team,
    )
    with pytest.raises(HTTPException) as exc:
        await svc.activate_partner(pid, actor_user=team)
    assert exc.value.status_code == 403

    await svc.activate_partner(pid, actor_user=admin)
    p = await svc.get_partner(pid, actor_user=admin)
    assert p.onboarding_status == "active"
    audit = await svc.list_audit(pid)
    assert any(a.action == "activated" for a in audit)


@pytest.mark.asyncio
async def test_verify_partner_access_admin_always_allowed(svc, user_factory, partner_factory):
    admin = await user_factory(role="admin")
    p = await partner_factory(assigned_to=None)
    assert await verify_partner_access(svc, admin, p.id) == p


@pytest.mark.asyncio
async def test_verify_partner_access_team_must_own(svc, user_factory, partner_factory):
    u1 = await user_factory(role="team")
    u2 = await user_factory(role="team")
    p = await partner_factory(assigned_to=u1)
    await verify_partner_access(svc, u1, p.id)
    with pytest.raises(HTTPException) as exc:
        await verify_partner_access(svc, u2, p.id)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_reassign_requires_reason_and_records_audit(svc, user_factory):
    admin = await user_factory(role="admin")
    u1 = await user_factory(role="team")
    u2 = await user_factory(role="team")
    pid = await svc.create_partner(
        full_name="H", email="h3@x.io", entity_type="individual",
        assigned_to=u1, created_by=admin,
    )
    with pytest.raises(ValueError, match="reason"):
        await svc.reassign_partner(pid, new_user_id=u2, actor_user=admin, reason=None)
    await svc.reassign_partner(
        pid, new_user_id=u2, actor_user=admin, reason="u1 left bali zero 2026-04"
    )
    audit = await svc.list_audit(pid)
    reassign = next(a for a in audit if a.action == "reassigned")
    assert reassign.reason == "u1 left bali zero 2026-04"


@pytest.mark.asyncio
async def test_orphan_partners_on_team_user_deactivation(svc, user_factory):
    admin = await user_factory(role="admin")
    u = await user_factory(role="team")
    p1 = await svc.create_partner(full_name="A", email="a@z.io",
                                  entity_type="individual",
                                  assigned_to=u, created_by=admin)
    p2 = await svc.create_partner(full_name="B", email="b@z.io",
                                  entity_type="individual",
                                  assigned_to=u, created_by=admin)
    n = await svc.orphan_partners_of_user(u, actor_user=admin)
    assert n == 2
    for pid in (p1, p2):
        p = await svc.get_partner(pid, actor_user=admin)
        assert p.assigned_to is None
        audit = await svc.list_audit(pid)
        assert any(a.action == "orphaned" for a in audit)
```

Additional tests:

- `test_update_partner_clears_welcome_sent_false` — `update_partner` must not touch `welcome_email_sent_at`.
- `test_deactivate_partner_soft_delete_preserves_history` — deactivation keeps all referrals and commissions readable.
- `test_create_rejects_partner_with_internal_email` — inserting a partner whose email matches a `team`/`admin` user raises 409 `ConflictError` from service layer.

- [ ] **Step 4.2: Write `PartnersService`**

```python
# backend/services/crm/partners/service.py
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from backend.services.crm.partners.models import Partner, PartnerAuditLogEntry
from backend.services.crm.partners.repository import PartnersRepository

logger = logging.getLogger(__name__)


class ConflictError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=409, detail=detail)


class PartnersService:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self.repo = PartnersRepository(conn)

    async def create_partner(
        self, *, full_name: str, email: str, entity_type: str,
        assigned_to: UUID | None = None,
        created_by: UUID | None = None,
        **optional: Any,
    ) -> UUID:
        try:
            pid = await self.repo.insert_partner(
                full_name=full_name, email=email, entity_type=entity_type,
                assigned_to=assigned_to, created_by=created_by, **optional,
            )
        except ValueError as e:
            raise ConflictError(str(e))
        except asyncpg.UniqueViolationError:
            raise ConflictError(f"email already in use: {email!r}")
        after = {"full_name": full_name, "email": email, "assigned_to": str(assigned_to) if assigned_to else None}
        await self.repo.insert_audit(
            partner_id=pid, action="created",
            actor_user_id=created_by, after=after,
        )
        return pid

    async def get_partner(self, partner_id: UUID, *, actor_user: UUID) -> Partner:
        return await verify_partner_access(self, actor_user, partner_id)

    async def list_partners(
        self, *, actor_user: UUID, actor_role: str,
        assigned_to: UUID | None = None,
        onboarding_status: str | None = None,
        orphaned: bool = False,
        search: str | None = None,
    ) -> list[Partner]:
        if actor_role == "team":
            assigned_to = actor_user  # force scope to own
        return await self.repo.list_partners(
            assigned_to=assigned_to, onboarding_status=onboarding_status,
            orphaned=orphaned, search=search,
        )

    async def update_partner(
        self, partner_id: UUID, *, actor_user: UUID, actor_role: str,
        **fields: Any,
    ) -> None:
        current = await verify_partner_access_with_role(
            self, actor_user, actor_role, partner_id,
        )
        before = {k: getattr(current, k) for k in fields if hasattr(current, k)}
        try:
            await self.repo.update_partner(partner_id, **fields)
        except ValueError as e:
            raise ConflictError(str(e))
        await self.repo.insert_audit(
            partner_id=partner_id, action="updated",
            actor_user_id=actor_user, before=before, after=fields,
        )

    async def activate_partner(self, partner_id: UUID, *, actor_user: UUID) -> None:
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        await self.repo.activate_partner(partner_id)
        await self.repo.insert_audit(
            partner_id=partner_id, action="activated", actor_user_id=actor_user,
        )

    async def deactivate_partner(self, partner_id: UUID, *, actor_user: UUID) -> None:
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        await self.repo.deactivate_partner(partner_id)
        await self.repo.insert_audit(
            partner_id=partner_id, action="deactivated", actor_user_id=actor_user,
        )

    async def reassign_partner(
        self, partner_id: UUID, *, new_user_id: UUID | None,
        actor_user: UUID, reason: str | None,
    ) -> None:
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        if not reason:
            raise ValueError("reason is required for reassignment")
        current = await self.repo.get_partner(partner_id)
        before = {"assigned_to": str(current.assigned_to) if current.assigned_to else None}
        after = {"assigned_to": str(new_user_id) if new_user_id else None}
        await self.repo.reassign_partner(partner_id, new_user_id)
        await self.repo.insert_audit(
            partner_id=partner_id, action="reassigned", actor_user_id=actor_user,
            before=before, after=after, reason=reason,
        )

    async def orphan_partners_of_user(self, user_id: UUID, *, actor_user: UUID) -> int:
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        affected = await self.repo.list_partners(assigned_to=user_id)
        n = await self.repo.orphan_partners_of_user(user_id)
        for p in affected:
            await self.repo.insert_audit(
                partner_id=p.id, action="orphaned", actor_user_id=actor_user,
                before={"assigned_to": str(user_id)},
                after={"assigned_to": None},
                reason=f"auto-orphan on deactivation of user {user_id}",
            )
        return n

    async def list_audit(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
        return await self.repo.list_audit_for_partner(partner_id)

    async def mark_welcome_sent(self, partner_id: UUID) -> None:
        await self.repo.mark_welcome_sent(partner_id)


async def _is_admin(conn: asyncpg.Connection, user_id: UUID) -> bool:
    row = await conn.fetchrow("SELECT role FROM users WHERE id = $1", user_id)
    return bool(row) and row["role"] == "admin"


async def _get_role(conn: asyncpg.Connection, user_id: UUID) -> str | None:
    row = await conn.fetchrow("SELECT role FROM users WHERE id = $1", user_id)
    return row["role"] if row else None


async def verify_partner_access(
    svc: PartnersService, actor_user: UUID, partner_id: UUID,
) -> Partner:
    role = await _get_role(svc.conn, actor_user)
    return await verify_partner_access_with_role(svc, actor_user, role, partner_id)


async def verify_partner_access_with_role(
    svc: PartnersService, actor_user: UUID, actor_role: str | None, partner_id: UUID,
) -> Partner:
    partner = await svc.repo.get_partner(partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="partner not found")
    if actor_role == "admin":
        return partner
    if actor_role == "team" and partner.assigned_to == actor_user:
        return partner
    if actor_role == "partner":
        # Check via users table: user.partner_id matches partner.id
        row = await svc.conn.fetchrow(
            "SELECT partner_id FROM users WHERE id = $1", actor_user
        )
        if row and row["partner_id"] == partner_id:
            return partner
    raise HTTPException(status_code=403, detail="forbidden")
```

Note on `users.partner_id`: the `users` table must have a `partner_id UUID NULL` column for partner role members. If it doesn't, add a column migration in Task 4 (append to migration 119 before commit).

- [ ] **Step 4.3: Check users.partner_id column exists; add to migration 119 if not**

```bash
PYTHONPATH=. python -c "
import asyncio
from backend.app.db import get_pool
async def go():
    pool = await get_pool()
    async with pool.acquire() as c:
        r = await c.fetchrow(\"SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='partner_id'\")
        print('exists' if r else 'MISSING')
asyncio.run(go())
"
```

If output is `MISSING`, open `migration_119_partners.py` and insert this block AFTER the `partners` table creation but BEFORE `partner_referrals`:

```python
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'partner_id'
            ) THEN
                ALTER TABLE users ADD COLUMN partner_id UUID REFERENCES partners(id) ON DELETE SET NULL;
                CREATE INDEX idx_users_partner_id ON users (partner_id) WHERE partner_id IS NOT NULL;
            END IF;
        END $$;
    """)
```

Then update `rollback` to drop the column (before dropping `partners`):

```python
    await conn.execute("DROP INDEX IF EXISTS idx_users_partner_id;")
    await conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS partner_id;")
```

Re-run migration tests:

```bash
PYTHONPATH=. pytest backend/tests/migrations/test_migration_119.py -v
```

- [ ] **Step 4.4: Run service tests**

```bash
PYTHONPATH=. pytest backend/tests/services/crm/partners/test_service.py -v
```

- [ ] **Step 4.5: Commit**

```bash
git add apps/backend-rag/backend/services/crm/partners/service.py \
        apps/backend-rag/backend/services/crm/partners/models.py \
        apps/backend-rag/backend/tests/services/crm/partners/test_service.py \
        apps/backend-rag/backend/migrations/migration_119_partners.py
git commit -m "feat(partners): service layer with RBAC + audit log + optional users.partner_id

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Commission engine — accrual + cooling-off + clawback + offset

This is the most logic-dense unit. Isolate it from EventBus so it can be tested with direct calls.

**Files:**

- Create: `apps/backend-rag/backend/services/crm/partners/commission_engine.py`
- Test: `apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py`

### Business rules (from spec §4.4)

1. Accrual is fired by `practice.status_changed` event where `status='completed' AND payment_status='paid'`.
2. `idempotency_key = f"accrual:{process_id}:{completed_at.isoformat()}"`.
3. `base_amount_idr` is read from `processes.total_invoiced_idr` (check actual column name via `psql \d processes` — fall back to `processes.total_amount` if naming differs, document the choice in a code comment).
4. Withholding rates (v1 placeholders, Asya to confirm):
   - `pph21` → `2.5%`
   - `pph23` → `2.0%`
   - `exempt` → `0`
   - `tbd` → `0` (and row blocked from approval)
5. Cooling-off from `system_settings.partner_accrual_cooling_off_days` (default 30).
6. Transition gates:
   - `approved`: `status='accrued'` AND `now() >= eligible_for_approval_at` AND `withholding_category != 'tbd'`.
   - `paid`: `status='approved'`.
   - `clawback`: original in `{approved, paid}`.
7. Offset: when approving commission `C` for partner `P`, if pending clawbacks exist for `P`, oldest is paired — clawback flips to `offset_applied`, `C.net_amount_idr` is reduced by the clawback's absolute net. No DB trigger; logic in `approve()`.
8. Auto-writeoff: if `abs(clawback.net) < system_setting(auto_writeoff_idr)`, insert with `status='waived'` immediately.

- [ ] **Step 5.1: Write failing tests**

```python
# tests/services/crm/partners/test_commission_engine.py
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.services.crm.partners.commission_engine import CommissionEngine


@pytest.fixture
async def engine(db_conn):
    return CommissionEngine(db_conn)


@pytest.mark.asyncio
async def test_accrue_creates_accrued_row_with_cooling_off(engine, partner_factory, process_factory):
    p = await partner_factory(default_commission_value=Decimal("10.0"),
                              tax_withholding_category="pph23")
    proc = await process_factory(total_invoiced_idr=Decimal("10000000"),
                                 status="completed", payment_status="paid")
    await engine.accrue_from_process(proc.id, p.id)
    commissions = await engine.repo.list_commissions_for_partner(p.id)
    assert len(commissions) == 1
    c = commissions[0]
    assert c.status == "accrued"
    assert c.base_amount_idr == Decimal("10000000")
    assert c.gross_amount_idr == Decimal("1000000")
    assert c.withholding_category == "pph23"
    assert c.withholding_rate == Decimal("2.0")
    assert c.withholding_amount_idr == Decimal("20000")
    assert c.net_amount_idr == Decimal("980000")
    assert c.eligible_for_approval_at > c.accrued_at


@pytest.mark.asyncio
async def test_accrue_is_idempotent_via_key(engine, partner_factory, process_factory):
    p = await partner_factory()
    proc = await process_factory(status="completed", payment_status="paid")
    await engine.accrue_from_process(proc.id, p.id)
    await engine.accrue_from_process(proc.id, p.id)  # second call: no-op
    commissions = await engine.repo.list_commissions_for_partner(p.id)
    assert len(commissions) == 1


@pytest.mark.asyncio
async def test_approve_blocked_before_cooling_off(engine, partner_factory, process_factory, admin):
    p = await partner_factory()
    proc = await process_factory(status="completed", payment_status="paid")
    await engine.accrue_from_process(proc.id, p.id)
    c = (await engine.repo.list_commissions_for_partner(p.id))[0]
    with pytest.raises(ValueError, match="cooling-off"):
        await engine.approve(c.id, actor=admin)


@pytest.mark.asyncio
async def test_approve_blocked_when_withholding_tbd(engine, partner_factory, process_factory, admin, db_conn):
    p = await partner_factory(tax_withholding_category="tbd")
    proc = await process_factory(status="completed", payment_status="paid")
    await engine.accrue_from_process(proc.id, p.id)
    c = (await engine.repo.list_commissions_for_partner(p.id))[0]
    # Simulate cooling-off elapsed
    await db_conn.execute(
        "UPDATE partner_commissions SET eligible_for_approval_at = now() - interval '1 day' "
        "WHERE id = $1",
        c.id,
    )
    with pytest.raises(ValueError, match="withholding.*tbd"):
        await engine.approve(c.id, actor=admin)


@pytest.mark.asyncio
async def test_flat_commission_type(engine, partner_factory, process_factory):
    p = await partner_factory(default_commission_type="flat",
                              default_commission_value=Decimal("500000"),
                              tax_withholding_category="exempt")
    proc = await process_factory(total_invoiced_idr=Decimal("10000000"),
                                 status="completed", payment_status="paid")
    await engine.accrue_from_process(proc.id, p.id)
    c = (await engine.repo.list_commissions_for_partner(p.id))[0]
    assert c.gross_amount_idr == Decimal("500000")
    assert c.withholding_amount_idr == Decimal("0")
    assert c.net_amount_idr == Decimal("500000")


@pytest.mark.asyncio
async def test_clawback_inserts_negative_row_with_fk(engine, partner_factory, admin):
    p = await partner_factory(tax_withholding_category="pph23")
    orig = await engine.repo.insert_commission(
        partner_id=p.id, entry_type="accrual",
        base_amount_idr=Decimal("10000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("1000000"),
        net_amount_idr=Decimal("980000"),
        status="paid", idempotency_key="manual-1",
    )
    cb = await engine.clawback(orig, actor=admin, reason="client refunded 2026-05-01")
    cb_row = await engine.repo.get_commission(cb)
    assert cb_row.entry_type == "clawback"
    assert cb_row.net_amount_idr == Decimal("-980000")
    assert cb_row.related_commission_id == orig
    assert cb_row.status == "clawback_pending"


@pytest.mark.asyncio
async def test_clawback_auto_writeoff_threshold(engine, partner_factory, admin, db_conn):
    # Set threshold to 1M IDR
    await db_conn.execute(
        "UPDATE system_settings SET value = '1000000' WHERE key = 'partner_clawback_auto_writeoff_idr'"
    )
    p = await partner_factory()
    orig = await engine.repo.insert_commission(
        partner_id=p.id, entry_type="accrual",
        base_amount_idr=Decimal("5000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("500000"),
        net_amount_idr=Decimal("500000"),
        status="paid", idempotency_key="manual-wo",
    )
    cb = await engine.clawback(orig, actor=admin, reason="tiny")
    row = await engine.repo.get_commission(cb)
    assert row.status == "waived"  # auto-writeoff


@pytest.mark.asyncio
async def test_approve_offsets_oldest_pending_clawback(engine, partner_factory, admin, db_conn):
    p = await partner_factory(tax_withholding_category="exempt")
    # 1) Existing pending clawback: -300k
    cb = await engine.repo.insert_commission(
        partner_id=p.id, entry_type="clawback",
        base_amount_idr=Decimal("3000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("-300000"),
        net_amount_idr=Decimal("-300000"),
        status="clawback_pending", idempotency_key="cb-1",
    )
    # 2) New accrual: 500k eligible now
    new = await engine.repo.insert_commission(
        partner_id=p.id, entry_type="accrual",
        base_amount_idr=Decimal("5000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("500000"),
        net_amount_idr=Decimal("500000"),
        status="accrued", idempotency_key="new-1",
    )
    await db_conn.execute(
        "UPDATE partner_commissions SET eligible_for_approval_at = now() - interval '1 day' "
        "WHERE id = $1", new,
    )
    await engine.approve(new, actor=admin)
    cb_row = await engine.repo.get_commission(cb)
    new_row = await engine.repo.get_commission(new)
    assert cb_row.status == "offset_applied"
    assert new_row.status == "approved"
    assert new_row.net_amount_idr == Decimal("200000")  # 500k - 300k
```

- [ ] **Step 5.2: Write the engine**

```python
# backend/services/crm/partners/commission_engine.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from backend.services.crm.partners.repository import PartnersRepository

logger = logging.getLogger(__name__)

_WITHHOLDING_RATES: dict[str, Decimal] = {
    "pph21": Decimal("2.5"),
    "pph23": Decimal("2.0"),
    "exempt": Decimal("0"),
    "tbd": Decimal("0"),
}


class CommissionEngine:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self.repo = PartnersRepository(conn)

    # ── Accrual ─────────────────────────────────────────────────────────

    async def accrue_from_process(self, process_id: UUID, partner_id: UUID | None = None) -> UUID | None:
        proc = await self.conn.fetchrow(
            # NB: verify column names against live schema. v1 uses
            # (status, payment_status, total_invoiced_idr). If your
            # schema uses different names, aliasing happens here only.
            """
            SELECT id, status, payment_status, total_invoiced_idr, completed_at
            FROM processes WHERE id = $1
            """,
            process_id,
        )
        if proc is None:
            return None
        if proc["status"] != "completed" or proc["payment_status"] != "paid":
            return None

        referral = await self.repo.get_referral_by_process(process_id)
        if referral is None:
            return None
        if partner_id is not None and referral.partner_id != partner_id:
            # Caller-specified partner_id is a sanity check only
            return None
        partner = await self.repo.get_partner(referral.partner_id)
        if partner is None:
            return None

        base = Decimal(proc["total_invoiced_idr"])
        if partner.default_commission_type == "percentage":
            gross = (base * partner.default_commission_value / Decimal("100"))
        else:
            gross = partner.default_commission_value
        rate = _WITHHOLDING_RATES.get(partner.tax_withholding_category, Decimal("0"))
        withholding = (gross * rate / Decimal("100")).quantize(Decimal("1"))
        net = gross - withholding

        cooling_days = int(await self._system_setting_int("partner_accrual_cooling_off_days", 30))
        completed_at = proc["completed_at"] or datetime.now(timezone.utc)
        eligible = completed_at + timedelta(days=cooling_days)
        key = f"accrual:{process_id}:{completed_at.isoformat()}"

        try:
            cid = await self.repo.insert_commission(
                partner_id=partner.id,
                entry_type="accrual",
                referral_id=referral.id,
                process_id=process_id,
                base_amount_idr=base,
                commission_type_snapshot=partner.default_commission_type,
                commission_value_snapshot=partner.default_commission_value,
                rule_source="partner_default",
                assigned_to_snapshot=partner.assigned_to,
                gross_amount_idr=gross,
                withholding_category=partner.tax_withholding_category,
                withholding_rate=rate,
                withholding_amount_idr=withholding,
                net_amount_idr=net,
                status="accrued",
                eligible_for_approval_at=eligible,
                idempotency_key=key,
            )
        except asyncpg.UniqueViolationError:
            logger.info("Accrual idempotency hit for key=%s — no-op", key)
            return None
        logger.info("Accrued commission %s for partner %s (net=%s IDR)", cid, partner.id, net)
        return cid

    # ── Approve / Mark-paid / Clawback ──────────────────────────────────

    async def approve(self, commission_id: UUID, *, actor: UUID) -> None:
        c = await self.repo.get_commission(commission_id)
        if c is None:
            raise ValueError(f"commission not found: {commission_id}")
        if c.status != "accrued":
            raise ValueError(f"cannot approve status {c.status!r}")
        if c.eligible_for_approval_at > datetime.now(timezone.utc):
            raise ValueError("commission is still within cooling-off window")
        if c.withholding_category == "tbd":
            raise ValueError("withholding category is tbd — set pph21|pph23|exempt first")

        # Offset against oldest clawback_pending, if any
        pending = await self.repo.list_pending_clawbacks(c.partner_id)
        offset_applied_id: UUID | None = None
        if pending:
            oldest = pending[0]
            offset_amount = -oldest.net_amount_idr  # positive magnitude
            new_net = c.net_amount_idr - offset_amount
            # We mutate the ledger row's net in a narrow, documented exception
            # to append-only: this is the ONE legal net-amount edit. If new_net
            # would be negative, the clawback is larger than the accrual — defer
            # (partial offsets require full policy, out of v1 scope).
            if new_net <= 0:
                logger.info("Clawback %s exceeds new accrual %s — no offset this round",
                            oldest.id, c.id)
            else:
                await self.conn.execute(
                    "UPDATE partner_commissions SET net_amount_idr = $2 WHERE id = $1",
                    c.id, new_net,
                )
                await self.repo.update_commission_status(oldest.id, "offset_applied")
                offset_applied_id = oldest.id

        await self.repo.update_commission_status(commission_id, "approved", approved_by=actor)
        if offset_applied_id:
            logger.info("Offset clawback %s against approval %s", offset_applied_id, commission_id)

    async def mark_paid(
        self, commission_id: UUID, *, actor: UUID,
        paid_via: str, payment_reference: str,
        payment_proof_url: str | None = None,
        receipt_type: str | None = None,
        receipt_file_url: str | None = None,
    ) -> None:
        await self.repo.update_commission_status(
            commission_id, "paid",
            paid_by=actor, paid_via=paid_via,
            payment_reference=payment_reference,
            payment_proof_url=payment_proof_url,
            receipt_type=receipt_type, receipt_file_url=receipt_file_url,
        )

    async def clawback(
        self, original_commission_id: UUID, *, actor: UUID, reason: str,
        amount_idr: Decimal | None = None,
    ) -> UUID:
        orig = await self.repo.get_commission(original_commission_id)
        if orig is None:
            raise ValueError(f"commission not found: {original_commission_id}")
        if orig.status not in ("approved", "paid"):
            raise ValueError(
                f"clawback only valid for approved|paid, got {orig.status!r}"
            )
        magnitude = amount_idr if amount_idr is not None else orig.net_amount_idr
        gross_neg = -magnitude
        net_neg = -magnitude

        threshold = await self._system_setting_int(
            "partner_clawback_auto_writeoff_idr", 0
        )
        auto_waive = threshold > 0 and abs(int(magnitude)) < threshold

        status = "waived" if auto_waive else "clawback_pending"
        key = f"clawback:{original_commission_id}:{datetime.now(timezone.utc).isoformat()}"
        cid = await self.repo.insert_commission(
            partner_id=orig.partner_id, entry_type="clawback",
            referral_id=orig.referral_id, process_id=orig.process_id,
            related_commission_id=orig.id,
            base_amount_idr=orig.base_amount_idr,
            commission_type_snapshot=orig.commission_type_snapshot,
            commission_value_snapshot=orig.commission_value_snapshot,
            assigned_to_snapshot=orig.assigned_to_snapshot,
            gross_amount_idr=gross_neg,
            withholding_category=orig.withholding_category,
            withholding_rate=orig.withholding_rate,
            withholding_amount_idr=Decimal("0"),
            net_amount_idr=net_neg,
            status=status, idempotency_key=key,
            clawback_reason=reason,
        )
        return cid

    async def waive_clawback(self, clawback_id: UUID, *, actor: UUID, reason: str) -> None:
        await self.repo.update_commission_status(
            clawback_id, "waived", waiver_reason=reason
        )

    # ── Helpers ─────────────────────────────────────────────────────────

    async def _system_setting_int(self, key: str, default: int) -> int:
        row = await self.conn.fetchrow(
            "SELECT value FROM system_settings WHERE key = $1", key
        )
        try:
            return int(row["value"]) if row else default
        except (ValueError, TypeError):
            return default
```

- [ ] **Step 5.3: Run engine tests**

```bash
PYTHONPATH=. pytest backend/tests/services/crm/partners/test_commission_engine.py -v
```

Expected: 7 passing. Fix any offset-math discrepancies before committing.

- [ ] **Step 5.4: Commit**

```bash
git add apps/backend-rag/backend/services/crm/partners/commission_engine.py \
        apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py
git commit -m "feat(partners): commission engine — accrual, cooling-off, clawback, offset

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: EventBus subscriber + `partner_commission_changed` publisher

**Files:**

- Create: `apps/backend-rag/backend/services/crm/partners/events.py`
- Modify: `apps/backend-rag/backend/services/events/handlers.py` (register handler)
- Test: `apps/backend-rag/backend/tests/services/crm/partners/test_events.py`

The handler subscribes to `practice.status_changed`. Payload shape from existing
code (see `services/events/event_bus.py:47` — `"practice_changed"` is aliased to
`"practice.status_changed"`). Payload fields include at minimum `process_id`,
`new_status`, optionally `payment_status`. The handler must:

1. Filter: proceed only if `new_status='completed'`. It may not have `payment_status` in the payload — re-read process from DB if needed.
2. Acquire a connection from the pool.
3. Call `CommissionEngine.accrue_from_process(process_id)`.
4. If accrual inserts a row, publish `partner_commission_changed` with
   `{"partner_id": ..., "commission_id": ..., "type": "accrued"}`.

- [ ] **Step 6.1: Write failing test**

```python
# tests/services/crm/partners/test_events.py
import pytest
from uuid import uuid4

from backend.services.crm.partners.events import (
    register_partner_handlers, handle_practice_status_changed,
)


@pytest.mark.asyncio
async def test_handle_practice_status_changed_noop_if_not_completed(
    db_conn, partner_factory, process_factory, monkeypatch,
):
    proc = await process_factory(status="in_progress", payment_status="pending")
    payload = {"process_id": str(proc.id), "new_status": "in_progress"}
    # Should not raise; should not insert any commission
    await handle_practice_status_changed(payload)
    rows = await db_conn.fetch("SELECT COUNT(*) AS n FROM partner_commissions")
    assert rows[0]["n"] == 0


@pytest.mark.asyncio
async def test_handle_practice_status_changed_creates_accrual(
    db_conn, partner_factory, process_factory, referral_factory,
):
    p = await partner_factory(tax_withholding_category="exempt")
    proc = await process_factory(
        total_invoiced_idr=Decimal("5000000"),
        status="completed", payment_status="paid",
    )
    await referral_factory(partner_id=p.id, process_id=proc.id)
    payload = {"process_id": str(proc.id), "new_status": "completed"}
    await handle_practice_status_changed(payload)
    rows = await db_conn.fetch(
        "SELECT COUNT(*) AS n FROM partner_commissions WHERE partner_id = $1", p.id
    )
    assert rows[0]["n"] == 1


@pytest.mark.asyncio
async def test_register_partner_handlers_subscribes_to_bus():
    from backend.services.events import EventBus
    bus = EventBus()
    register_partner_handlers(bus)
    assert "practice.status_changed" in bus._subscribers
```

- [ ] **Step 6.2: Write `events.py`**

```python
# backend/services/crm/partners/events.py
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from backend.app.db import get_pool
from backend.services.crm.partners.commission_engine import CommissionEngine
from backend.services.events import EventBus

logger = logging.getLogger(__name__)

PARTNER_COMMISSION_CHANGED = "partner.commission_changed"


async def handle_practice_status_changed(payload: dict[str, Any]) -> None:
    new_status = payload.get("new_status")
    process_id = payload.get("process_id")
    if new_status != "completed" or not process_id:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        engine = CommissionEngine(conn)
        cid = await engine.accrue_from_process(UUID(process_id))
        if cid is None:
            return
        row = await conn.fetchrow(
            "SELECT partner_id FROM partner_commissions WHERE id = $1", cid
        )
        partner_id = row["partner_id"]
    await _publish_changed(partner_id, cid, kind="accrued")


async def _publish_changed(partner_id: UUID, commission_id: UUID, *, kind: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        payload = f'{{"partner_id":"{partner_id}","commission_id":"{commission_id}","type":"{kind}"}}'
        await conn.execute(f"NOTIFY partner_commission_changed, '{payload}'")
    logger.info("Published partner_commission_changed: %s (%s)", commission_id, kind)


def register_partner_handlers(bus: EventBus) -> None:
    bus.subscribe("practice.status_changed", handle_practice_status_changed)
    logger.info("📡 Partner handlers registered on practice.status_changed")
```

- [ ] **Step 6.3: Register handler at startup**

Open `apps/backend-rag/backend/services/events/handlers.py`. In `register_handlers()` (around line 320), add after the compliance-handler try/except block:

```python
    # ── Partner handlers (2026-04-20) ──────────────────────────────────
    try:
        from backend.services.crm.partners.events import register_partner_handlers
        register_partner_handlers(bus)
    except ImportError as exc:
        logger.warning("partner handlers not loaded: %s", exc)
```

- [ ] **Step 6.4: Run event tests**

```bash
PYTHONPATH=. pytest backend/tests/services/crm/partners/test_events.py -v
```

- [ ] **Step 6.5: Commit**

```bash
git add apps/backend-rag/backend/services/crm/partners/events.py \
        apps/backend-rag/backend/services/events/handlers.py \
        apps/backend-rag/backend/tests/services/crm/partners/test_events.py
git commit -m "feat(partners): EventBus subscriber — practice.status_changed → accrual

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: FastAPI router — 20 endpoints

**Files:**

- Create: `apps/backend-rag/backend/app/routers/partners.py`
- Modify: `apps/backend-rag/backend/app/setup/router_manifest.py`
- Test: `apps/backend-rag/backend/tests/routers/test_partners.py`

Follow SCAR 2026-03-26 pattern: every mutation handler does
`except HTTPException: raise` BEFORE the generic `except Exception`.

### Pydantic request/response shapes

Define these in the same router file (short, local, no need to split):

```python
class PartnerCreate(BaseModel):
    full_name: str
    email: EmailStr
    entity_type: Literal["individual", "corporate_pt", "corporate_cv", "foreign"]
    work_role: str | None = None
    company_name: str | None = None
    office_address: str | None = None
    phone: str | None = None
    preferred_language: str = "id"
    npwp: str | None = None
    nik: str | None = None
    tax_withholding_category: Literal["pph21","pph23","exempt","tbd"] = "tbd"
    fiscal_address: str | None = None
    bank_name: str | None = None
    bank_account_holder: str | None = None
    bank_account_number: str | None = None
    ewallet_type: str | None = None
    ewallet_number: str | None = None
    payment_currency: str = "IDR"
    iban: str | None = None
    payment_notes: str | None = None
    default_commission_type: Literal["percentage","flat"] = "percentage"
    default_commission_value: Decimal = Decimal("10.0")
    assigned_to: UUID | None = None
    pdp_consent_version: str | None = None
    terms_version: str | None = None

class PartnerUpdate(BaseModel):
    # All PartnerCreate fields become Optional here
    ...  # mirror PartnerCreate but every field is Optional

class ReassignRequest(BaseModel):
    new_user_id: UUID | None
    reason: str

class BulkReassignRequest(BaseModel):
    partner_ids: list[UUID]
    new_user_id: UUID
    reason: str

class ReferralCreate(BaseModel):
    process_id: UUID
    notes: str | None = None

class CommissionApproveRequest(BaseModel):
    pass  # server-side only

class CommissionMarkPaidRequest(BaseModel):
    paid_via: str
    payment_reference: str
    payment_proof_url: str | None = None
    receipt_type: Literal["kwitansi","invoice","none"] | None = None
    receipt_file_url: str | None = None

class ClawbackRequest(BaseModel):
    reason: str
    amount_idr: Decimal | None = None

class WaiveRequest(BaseModel):
    reason: str
```

Response models: use `PartnerRead`, `ReferralRead`, `CommissionRead` derived
from dataclass models (use `pydantic.BaseModel.from_attributes = True`).

- [ ] **Step 7.1: Write failing router tests**

```python
# tests/routers/test_partners.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_partner_as_team_auto_assigns_self(client: AsyncClient, team_user):
    resp = await client.post(
        "/api/partners",
        json={"full_name": "Hotel Kama", "email": "h@k.io",
              "entity_type": "corporate_pt"},
        headers=team_user.auth_header,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["assigned_to"] == str(team_user.id)
    assert data["onboarding_status"] == "pending_approval"


@pytest.mark.asyncio
async def test_create_partner_duplicate_email_409(client, admin_user):
    await client.post("/api/partners",
        json={"full_name":"A","email":"dupe@k.io","entity_type":"individual"},
        headers=admin_user.auth_header)
    resp = await client.post("/api/partners",
        json={"full_name":"B","email":"dupe@k.io","entity_type":"individual"},
        headers=admin_user.auth_header)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_partners_team_sees_only_own(client, team_user, admin_user, db_conn):
    await client.post("/api/partners",
        json={"full_name":"Mine","email":"mine@k.io","entity_type":"individual",
              "assigned_to": str(team_user.id)},
        headers=admin_user.auth_header)
    await client.post("/api/partners",
        json={"full_name":"Other","email":"other@k.io","entity_type":"individual"},
        headers=admin_user.auth_header)
    resp = await client.get("/api/partners", headers=team_user.auth_header)
    assert resp.status_code == 200
    emails = [p["email"] for p in resp.json()]
    assert "mine@k.io" in emails
    assert "other@k.io" not in emails


@pytest.mark.asyncio
async def test_activate_requires_admin(client, team_user, admin_user):
    resp = await client.post("/api/partners",
        json={"full_name":"X","email":"x@k.io","entity_type":"individual"},
        headers=admin_user.auth_header)
    pid = resp.json()["id"]
    forbidden = await client.post(f"/api/partners/{pid}/activate",
                                  headers=team_user.auth_header)
    assert forbidden.status_code == 403
    ok = await client.post(f"/api/partners/{pid}/activate",
                           headers=admin_user.auth_header)
    assert ok.status_code == 204


@pytest.mark.asyncio
async def test_partner_self_view_sterilizes_client_data(client, partner_user, db_conn):
    # Arrange: partner_user has a referral on a process with client "Mario Rossi"
    ...
    resp = await client.get("/api/partners/me/referrals",
                            headers=partner_user.auth_header)
    data = resp.json()
    for ref in data:
        assert "passport_number" not in ref
        assert ref["client_display"] == "Mario R."  # sterilized


@pytest.mark.asyncio
async def test_finance_actions_require_finance_permission(
    client, admin_user_without_finance_perm, admin_user,
):
    # Setup a commission in 'approved' state
    ...
    forbidden = await client.post(
        f"/api/partners/commissions/{cid}/mark-paid",
        json={"paid_via": "BCA", "payment_reference": "TX123"},
        headers=admin_user_without_finance_perm.auth_header,
    )
    assert forbidden.status_code == 403

    ok = await client.post(
        f"/api/partners/commissions/{cid}/mark-paid",
        json={"paid_via": "BCA", "payment_reference": "TX123"},
        headers=admin_user.auth_header,
    )
    assert ok.status_code == 204
```

Add tests for: reassign (admin-only, reason required → 400 when missing);
bulk-reassign; referral create / swap / delete (delete rejected when
commissions exist → 409); clawback (admin-only, returns new commission id);
waive; finance CSV export (content-type + required cols).

- [ ] **Step 7.2: Write the router**

Start with the skeleton. Use `Depends(get_current_user)` and
`Depends(get_db_conn)` as existing routers do (see `routers/clients.py` for
the pattern).

```python
# backend/app/routers/partners.py
from __future__ import annotations

import csv
import io
import logging
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr

from backend.app.dependencies import get_current_user, get_db_conn
from backend.services.crm.partners.commission_engine import CommissionEngine
from backend.services.crm.partners.service import (
    PartnersService, ConflictError,
    verify_partner_access_with_role,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/partners", tags=["partners"])


# ── Pydantic models (see Step 7.1 for full definitions) ────────────────
# [paste the PartnerCreate, PartnerUpdate, ReassignRequest, etc. from 7.1]


def _require_finance(user) -> None:
    perms = getattr(user, "permissions", set())
    if "finance.mark_paid" not in perms and user.role != "admin":
        raise HTTPException(403, "finance permission required")


def _sterilize_client_for_partner(client_display: str) -> str:
    # "Mario Rossi" -> "Mario R."
    parts = client_display.strip().split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


# ── Endpoints ──────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_partner(
    body: "PartnerCreate",
    user=Depends(get_current_user),
    conn=Depends(get_db_conn),
):
    try:
        svc = PartnersService(conn)
        data = body.model_dump(exclude_none=True)
        assigned_to = data.pop("assigned_to", None)
        # Team auto-scopes to self; admin may set explicitly
        if user.role == "team" and assigned_to is None:
            assigned_to = user.id
        pid = await svc.create_partner(
            **{k: v for k, v in data.items() if k != "assigned_to"},
            assigned_to=assigned_to, created_by=user.id,
        )
        partner = await svc.repo.get_partner(pid)
        return partner
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_partner failed")
        raise HTTPException(500, "internal error")


@router.get("")
async def list_partners(
    assigned_to: UUID | None = None,
    onboarding_status: str | None = None,
    orphaned: bool = False,
    search: str | None = None,
    user=Depends(get_current_user),
    conn=Depends(get_db_conn),
):
    svc = PartnersService(conn)
    return await svc.list_partners(
        actor_user=user.id, actor_role=user.role,
        assigned_to=assigned_to, onboarding_status=onboarding_status,
        orphaned=orphaned, search=search,
    )


@router.get("/{partner_id}")
async def get_partner(partner_id: UUID,
                      user=Depends(get_current_user),
                      conn=Depends(get_db_conn)):
    svc = PartnersService(conn)
    return await verify_partner_access_with_role(svc, user.id, user.role, partner_id)


@router.patch("/{partner_id}")
async def update_partner(partner_id: UUID, body: "PartnerUpdate",
                         user=Depends(get_current_user),
                         conn=Depends(get_db_conn)):
    try:
        svc = PartnersService(conn)
        fields = body.model_dump(exclude_none=True, exclude_unset=True)
        await svc.update_partner(
            partner_id, actor_user=user.id, actor_role=user.role, **fields,
        )
        return await svc.repo.get_partner(partner_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("update_partner failed")
        raise HTTPException(500, "internal error")


@router.post("/{partner_id}/activate", status_code=204)
async def activate_partner(partner_id: UUID,
                           user=Depends(get_current_user),
                           conn=Depends(get_db_conn)):
    try:
        svc = PartnersService(conn)
        await svc.activate_partner(partner_id, actor_user=user.id)
        # Trigger welcome email (Task 8 adds the emails module).
        from backend.services.crm.partners.emails import send_welcome
        await send_welcome(conn, partner_id)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception:
        logger.exception("activate_partner failed")
        raise HTTPException(500, "internal error")


@router.post("/{partner_id}/deactivate", status_code=204)
async def deactivate_partner(partner_id: UUID,
                             user=Depends(get_current_user),
                             conn=Depends(get_db_conn)):
    try:
        svc = PartnersService(conn)
        await svc.deactivate_partner(partner_id, actor_user=user.id)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception:
        logger.exception("deactivate_partner failed")
        raise HTTPException(500, "internal error")


@router.post("/{partner_id}/reassign", status_code=204)
async def reassign_partner(partner_id: UUID, body: "ReassignRequest",
                           user=Depends(get_current_user),
                           conn=Depends(get_db_conn)):
    try:
        svc = PartnersService(conn)
        await svc.reassign_partner(
            partner_id, new_user_id=body.new_user_id,
            actor_user=user.id, reason=body.reason,
        )
        return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/bulk-reassign", status_code=204)
async def bulk_reassign(body: "BulkReassignRequest",
                        user=Depends(get_current_user),
                        conn=Depends(get_db_conn)):
    try:
        svc = PartnersService(conn)
        for pid in body.partner_ids:
            await svc.reassign_partner(
                pid, new_user_id=body.new_user_id,
                actor_user=user.id, reason=body.reason,
            )
        return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Referrals ──────────────────────────────────────────────────────────

@router.get("/{partner_id}/referrals")
async def list_referrals(partner_id: UUID,
                         user=Depends(get_current_user),
                         conn=Depends(get_db_conn)):
    svc = PartnersService(conn)
    await verify_partner_access_with_role(svc, user.id, user.role, partner_id)
    return await svc.repo.list_referrals_for_partner(partner_id)


@router.post("/{partner_id}/referrals", status_code=201)
async def create_referral(partner_id: UUID, body: "ReferralCreate",
                          user=Depends(get_current_user),
                          conn=Depends(get_db_conn)):
    try:
        svc = PartnersService(conn)
        await verify_partner_access_with_role(svc, user.id, user.role, partner_id)
        rid = await svc.repo.insert_referral(
            partner_id=partner_id, process_id=body.process_id,
            referred_by_user_id=user.id, notes=body.notes,
        )
        return {"id": rid, "partner_id": partner_id, "process_id": body.process_id}
    except HTTPException:
        raise
    except Exception as e:
        # UniqueViolationError on process_id → 409
        if "unique" in str(e).lower():
            raise HTTPException(409, "process already has a referral")
        logger.exception("create_referral failed"); raise HTTPException(500, "internal error")


@router.patch("/referrals/{referral_id}", status_code=204)
async def swap_referral(referral_id: UUID, new_partner_id: UUID,
                        user=Depends(get_current_user),
                        conn=Depends(get_db_conn)):
    if user.role != "admin":
        raise HTTPException(403, "admin only")
    try:
        svc = PartnersService(conn)
        await svc.repo.update_referral_partner(referral_id, new_partner_id)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception:
        logger.exception("swap_referral failed"); raise HTTPException(500, "internal error")


@router.delete("/referrals/{referral_id}", status_code=204)
async def delete_referral(referral_id: UUID,
                          user=Depends(get_current_user),
                          conn=Depends(get_db_conn)):
    if user.role != "admin":
        raise HTTPException(403, "admin only")
    try:
        svc = PartnersService(conn)
        await svc.repo.delete_referral(referral_id)
        return Response(status_code=204)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(409, str(e))


# ── Commissions ────────────────────────────────────────────────────────

@router.get("/{partner_id}/commissions")
async def list_commissions(partner_id: UUID,
                           user=Depends(get_current_user),
                           conn=Depends(get_db_conn)):
    svc = PartnersService(conn)
    await verify_partner_access_with_role(svc, user.id, user.role, partner_id)
    return await svc.repo.list_commissions_for_partner(partner_id)


@router.post("/commissions/{commission_id}/approve", status_code=204)
async def approve_commission(commission_id: UUID,
                             user=Depends(get_current_user),
                             conn=Depends(get_db_conn)):
    if user.role != "admin":
        raise HTTPException(403, "admin only")
    _require_finance(user)
    try:
        engine = CommissionEngine(conn)
        await engine.approve(commission_id, actor=user.id)
        return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/commissions/{commission_id}/mark-paid", status_code=204)
async def mark_paid_commission(commission_id: UUID, body: "CommissionMarkPaidRequest",
                               user=Depends(get_current_user),
                               conn=Depends(get_db_conn)):
    if user.role != "admin":
        raise HTTPException(403, "admin only")
    _require_finance(user)
    try:
        engine = CommissionEngine(conn)
        await engine.mark_paid(
            commission_id, actor=user.id,
            paid_via=body.paid_via, payment_reference=body.payment_reference,
            payment_proof_url=body.payment_proof_url,
            receipt_type=body.receipt_type, receipt_file_url=body.receipt_file_url,
        )
        from backend.services.crm.partners.emails import send_commission_earned
        await send_commission_earned(conn, commission_id)
        return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/commissions/{commission_id}/clawback", status_code=201)
async def clawback_commission(commission_id: UUID, body: "ClawbackRequest",
                              user=Depends(get_current_user),
                              conn=Depends(get_db_conn)):
    if user.role != "admin":
        raise HTTPException(403, "admin only")
    _require_finance(user)
    try:
        engine = CommissionEngine(conn)
        cid = await engine.clawback(
            commission_id, actor=user.id, reason=body.reason, amount_idr=body.amount_idr,
        )
        return {"id": cid}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/commissions/{commission_id}/waive", status_code=204)
async def waive_commission(commission_id: UUID, body: "WaiveRequest",
                           user=Depends(get_current_user),
                           conn=Depends(get_db_conn)):
    if user.role != "admin":
        raise HTTPException(403, "admin only")
    _require_finance(user)
    try:
        engine = CommissionEngine(conn)
        await engine.waive_clawback(commission_id, actor=user.id, reason=body.reason)
        return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── /me endpoints (role=partner) ───────────────────────────────────────

@router.get("/me")
async def me(user=Depends(get_current_user), conn=Depends(get_db_conn)):
    if user.role != "partner" or not user.partner_id:
        raise HTTPException(403, "partner only")
    svc = PartnersService(conn)
    return await svc.repo.get_partner(user.partner_id)


@router.get("/me/referrals")
async def me_referrals(user=Depends(get_current_user), conn=Depends(get_db_conn)):
    if user.role != "partner" or not user.partner_id:
        raise HTTPException(403, "partner only")
    svc = PartnersService(conn)
    refs = await svc.repo.list_referrals_for_partner(user.partner_id)
    # Sterilize client data
    out = []
    for r in refs:
        proc = await conn.fetchrow(
            "SELECT p.id, p.status, p.service_type, c.full_name "
            "FROM processes p LEFT JOIN clients c ON c.id = p.client_id WHERE p.id = $1",
            r.process_id,
        )
        if proc is None:
            continue
        out.append({
            "id": r.id,
            "process_id": r.process_id,
            "service_type": proc["service_type"],
            "process_status": proc["status"],
            "client_display": _sterilize_client_for_partner(proc["full_name"] or ""),
            "referred_at": r.referred_at,
        })
    return out


@router.get("/me/commissions")
async def me_commissions(user=Depends(get_current_user), conn=Depends(get_db_conn)):
    if user.role != "partner" or not user.partner_id:
        raise HTTPException(403, "partner only")
    svc = PartnersService(conn)
    return await svc.repo.list_commissions_for_partner(user.partner_id)


# ── Finance CSV export ─────────────────────────────────────────────────

@router.get("/finance/export")
async def finance_export(from_: str = Query(..., alias="from"),
                         to: str = Query(...),
                         user=Depends(get_current_user),
                         conn=Depends(get_db_conn)):
    if user.role != "admin":
        raise HTTPException(403, "admin only")
    _require_finance(user)
    rows = await conn.fetch(
        """
        SELECT pc.id, p.full_name, p.npwp, p.entity_type,
               pc.entry_type, pc.gross_amount_idr, pc.withholding_category,
               pc.withholding_amount_idr, pc.net_amount_idr, pc.status,
               pc.paid_at, pc.paid_via, pc.payment_reference
        FROM partner_commissions pc
        JOIN partners p ON p.id = pc.partner_id
        WHERE pc.created_at >= $1::timestamptz AND pc.created_at < $2::timestamptz
        ORDER BY pc.created_at ASC
        """,
        from_, to,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "commission_id","partner","npwp","entity_type","entry_type","gross_idr",
        "withholding_category","withholding_idr","net_idr","status",
        "paid_at","paid_via","payment_reference",
    ])
    for r in rows:
        writer.writerow([r[k] for k in r.keys()])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="partners-{from_}-to-{to}.csv"'},
    )
```

- [ ] **Step 7.3: Register in `router_manifest.py`**

Open `apps/backend-rag/backend/app/setup/router_manifest.py` and add an entry following the existing `RouterEntry` pattern. Locate the `ROUTERS: list[RouterEntry] = [...]` list; append:

```python
    RouterEntry(
        module="backend.app.routers.partners",
        router_attr="router",
        process_groups=["_BOTH"],
        description="CRM Partners module (v1)",
    ),
```

Run: `PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py -q` — must stay green.

- [ ] **Step 7.4: Run router tests**

```bash
PYTHONPATH=. pytest backend/tests/routers/test_partners.py -v
```

- [ ] **Step 7.5: Commit**

```bash
git add apps/backend-rag/backend/app/routers/partners.py \
        apps/backend-rag/backend/app/setup/router_manifest.py \
        apps/backend-rag/backend/tests/routers/test_partners.py
git commit -m "feat(partners): 20-endpoint FastAPI router with RBAC + finance gates + CSV export

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Email templates + Brevo send with idempotency

**Files:**

- Create: `apps/backend-rag/backend/services/crm/partners/emails.py`
- Create: `apps/backend-rag/backend/services/crm/partners/templates/welcome.md.j2`
- Create: `apps/backend-rag/backend/services/crm/partners/templates/commission.md.j2`
- Test: `apps/backend-rag/backend/tests/services/crm/partners/test_emails.py`

Emails go via the existing `POST /api/notifications/send-email` endpoint with `X-API-Key: REDACTED-ROTATED-KEY`. Sender `zantara@balizero.com`. Look at `apps/backend-rag/backend/services/crm/welcome/welcome_email_service.py` for the reference call pattern — reuse the same helper function rather than re-implementing HTTP.

- [ ] **Step 8.1: Write failing tests**

```python
# tests/services/crm/partners/test_emails.py
import pytest
from unittest.mock import AsyncMock, patch

from backend.services.crm.partners.emails import (
    send_welcome, send_commission_earned,
)


@pytest.mark.asyncio
async def test_send_welcome_idempotent(db_conn, partner_factory):
    p = await partner_factory()
    with patch("backend.services.crm.partners.emails._post_email",
               new=AsyncMock()) as mock_post:
        await send_welcome(db_conn, p.id)
        await send_welcome(db_conn, p.id)  # second call: skipped
    assert mock_post.call_count == 1
    row = await db_conn.fetchrow(
        "SELECT welcome_email_sent_at FROM partners WHERE id = $1", p.id
    )
    assert row["welcome_email_sent_at"] is not None


@pytest.mark.asyncio
async def test_send_welcome_includes_pricing_from_tool(db_conn, partner_factory):
    p = await partner_factory(preferred_language="it")
    with patch("backend.services.crm.partners.emails._post_email",
               new=AsyncMock()) as mock_post:
        await send_welcome(db_conn, p.id)
    body = mock_post.call_args.kwargs["body"]
    # Welcome template must reference at least one Bali Zero service price
    assert "Rp" in body or "IDR" in body
    assert "commission" in body.lower() or "commissione" in body.lower()


@pytest.mark.asyncio
async def test_send_commission_earned_sterilizes_client_name(
    db_conn, partner_factory, commission_factory, client_factory,
):
    client = await client_factory(full_name="Mario Rossi")
    p = await partner_factory()
    c = await commission_factory(
        partner_id=p.id, process_client_id=client.id,
        status="paid", net_amount_idr=Decimal("500000"),
    )
    with patch("backend.services.crm.partners.emails._post_email",
               new=AsyncMock()) as mock_post:
        await send_commission_earned(db_conn, c.id)
    body = mock_post.call_args.kwargs["body"]
    assert "Mario Rossi" not in body
    assert "Mario R." in body
```

- [ ] **Step 8.2: Write `welcome.md.j2` template**

```jinja
# Welcome to Bali Zero Partners

Hi {{ partner.full_name }},

Welcome aboard! You're now part of the Bali Zero partner network.

## Commission structure

Your default commission is **{{ commission_rate }}**
({{ commission_type }}). Commission accrues on each completed + paid process
that lists you as the referrer.

Payment flow:
1. Process marked **completed + paid** → commission accrues.
2. 30-day cooling-off period (eligible date shown in your dashboard).
3. Asya reviews and approves for payout.
4. Paid via bank transfer (or e-wallet) in IDR. Payment proof uploaded.

## Our services

{% for service in pricing_services %}
- **{{ service.name }}** — from {{ service.price_display }}
{% endfor %}

Full pricing on your partner dashboard.

## Terms

- Commission is paid **only** when the linked process is **completed + paid**.
- Refunds within 30 days trigger a clawback deducted from your next accrual.
- Your personal data is stored for referral tracking and commission payment
  only (UU PDP 27/2022). You may request deletion by replying to this email.

## Your portal

Access your referrals and commissions at
https://kita.balizero.com/portal/partner/dashboard

Questions? Reply to this email.

— Zantara, Bali Zero
```

Same template text in Italian + Indonesian variants in future; v1 ships English only and lets Brevo preview handle fallback.

- [ ] **Step 8.3: Write `commission.md.j2` template**

```jinja
# Commission earned — {{ client_display }}

Hi {{ partner.full_name }},

Good news: a commission has been paid for your referral on the
**{{ service_type }}** service for **{{ client_display }}**.

| Field | Amount (IDR) |
|---|---|
| Gross | {{ gross_idr }} |
| Withholding ({{ withholding_category }}) | {{ withholding_idr }} |
| **Net paid** | **{{ net_idr }}** |

**Paid via:** {{ paid_via }} · **Reference:** {{ payment_reference }} ·
**Paid at:** {{ paid_at }}

{% if receipt_file_url %}
Receipt: {{ receipt_file_url }}
{% endif %}

Reminder: if the client refunds or cancels after payment, a clawback is
deducted from your next commission automatically.

— Zantara, Bali Zero
```

- [ ] **Step 8.4: Write `emails.py`**

```python
# backend/services/crm/partners/emails.py
from __future__ import annotations

import logging
import os
from pathlib import Path
from uuid import UUID

import httpx
import jinja2

from backend.services.crm.partners.repository import PartnersRepository
from backend.services.pricing.pricing_tool import PricingTool  # use existing

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_TEMPLATES_DIR),
    autoescape=False,
    keep_trailing_newline=True,
)

SENDER_EMAIL = "zantara@balizero.com"
SENDER_NAME = "Zantara"
NOTIFICATIONS_ENDPOINT = os.environ.get(
    "NOTIFICATIONS_ENDPOINT",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
X_API_KEY = os.environ.get("NOTIFICATIONS_X_API_KEY", "REDACTED-ROTATED-KEY")


async def _post_email(*, to: str, cc: list[str] | None, subject: str, body: str) -> None:
    payload = {
        "from_email": SENDER_EMAIL,
        "from_name": SENDER_NAME,
        "to": to,
        "cc": cc or [],
        "subject": subject,
        "body_markdown": body,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            NOTIFICATIONS_ENDPOINT,
            json=payload,
            headers={"X-API-Key": X_API_KEY},
        )
        r.raise_for_status()


def _sterilize(name: str) -> str:
    parts = name.strip().split()
    if not parts: return ""
    if len(parts) == 1: return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


async def send_welcome(conn, partner_id: UUID) -> None:
    repo = PartnersRepository(conn)
    p = await repo.get_partner(partner_id)
    if p is None:
        logger.warning("send_welcome: partner %s not found", partner_id)
        return
    if p.welcome_email_sent_at is not None:
        logger.info("send_welcome: already sent for %s — skip", partner_id)
        return

    pricing = PricingTool()
    services = await pricing.list_services_with_prices()  # returns [{name, price_display}, ...]

    tpl = _env.get_template("welcome.md.j2")
    body = tpl.render(
        partner=p,
        commission_rate=(f"{p.default_commission_value}%" if p.default_commission_type == "percentage"
                         else f"IDR {p.default_commission_value}"),
        commission_type=p.default_commission_type,
        pricing_services=services,
    )
    await _post_email(to=p.email, cc=None,
                      subject="Welcome to Bali Zero Partners", body=body)
    await repo.mark_welcome_sent(partner_id)


async def send_commission_earned(conn, commission_id: UUID) -> None:
    repo = PartnersRepository(conn)
    c = await repo.get_commission(commission_id)
    if c is None or c.status != "paid":
        return
    if c.commission_email_sent_at is not None:
        return

    p = await repo.get_partner(c.partner_id)
    proc = await conn.fetchrow(
        "SELECT p.service_type, c.full_name AS client_name "
        "FROM processes p LEFT JOIN clients c ON c.id = p.client_id WHERE p.id = $1",
        c.process_id,
    )
    assigned_to_email = None
    if c.assigned_to_snapshot:
        r = await conn.fetchrow("SELECT email FROM users WHERE id = $1", c.assigned_to_snapshot)
        if r: assigned_to_email = r["email"]

    tpl = _env.get_template("commission.md.j2")
    body = tpl.render(
        partner=p,
        client_display=_sterilize(proc["client_name"] or ""),
        service_type=proc["service_type"],
        gross_idr=f"{c.gross_amount_idr:,.0f}",
        withholding_idr=f"{c.withholding_amount_idr:,.0f}",
        withholding_category=c.withholding_category,
        net_idr=f"{c.net_amount_idr:,.0f}",
        paid_via=c.paid_via or "",
        payment_reference=c.payment_reference or "",
        paid_at=c.paid_at.isoformat() if c.paid_at else "",
        receipt_file_url=c.receipt_file_url,
    )
    subject = f"Commissione maturata — {_sterilize(proc['client_name'] or '')}"
    await _post_email(
        to=p.email,
        cc=[assigned_to_email] if assigned_to_email else [],
        subject=subject, body=body,
    )
    await repo.mark_commission_email_sent(commission_id)
```

- [ ] **Step 8.5: Run email tests**

```bash
PYTHONPATH=. pytest backend/tests/services/crm/partners/test_emails.py -v
```

- [ ] **Step 8.6: Commit**

```bash
git add apps/backend-rag/backend/services/crm/partners/emails.py \
        apps/backend-rag/backend/services/crm/partners/templates/ \
        apps/backend-rag/backend/tests/services/crm/partners/test_emails.py
git commit -m "feat(partners): welcome + commission emails via Brevo with idempotency

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Team portal frontend (`/portal/partners/*`)

**Files:**

- Create: `apps/mouth/src/lib/api/partners.ts` — typed fetch client
- Create: `apps/mouth/src/app/portal/(authenticated)/partners/page.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/partners/new/page.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/partners/[id]/page.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/partners/[id]/edit/page.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/partners/orphaned/page.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/partners/finance/page.tsx`
- Create: `apps/mouth/src/components/portal/ReferrerDropdown.tsx`
- Modify: sidebar navigation component (identify which file holds the portal sidebar and add `Partners` item between `Processi` and `HR`)
- Test: `apps/mouth/tests/app/portal/partners.spec.tsx`

This task is best broken into sub-commits (one per page). Keep the plan high-level here; the subagent doing implementation follows the frontend patterns found in `/portal/clients/*`.

- [ ] **Step 9.1: `src/lib/api/partners.ts`**

Mirror the existing `src/lib/api/clients.ts` pattern (same worktree; verify it exists). Export async functions: `listPartners(filters)`, `createPartner(body)`, `getPartner(id)`, `updatePartner(id, body)`, `activatePartner(id)`, `deactivatePartner(id)`, `reassignPartner(id, body)`, `bulkReassign(body)`, `listReferrals(partnerId)`, `createReferral(partnerId, body)`, `listCommissions(partnerId)`, `approveCommission(id)`, `markPaid(id, body)`, `clawback(id, body)`, `waive(id, body)`, `exportFinanceCsv(from, to)`. All typed via TypeScript interfaces mirroring the Pydantic models in Task 7.1.

- [ ] **Step 9.2: Sidebar add entry between `/process` and `/hr`**

Locate the sidebar config file (likely `apps/mouth/src/config/navigation.ts` or inside a `Sidebar.tsx` component — verify). Insert the `Partners` item referencing `/portal/partners`. Icon: `Handshake` from lucide-react.

- [ ] **Step 9.3: List page `/portal/partners`**

Table with columns: Name, Company, Email, Owner, Status, Created. Filters row: status (all/pending/active/inactive), orphaned toggle (admin only), search input. "New partner" button top-right. Warm-depth styling via `bz-tokens.css` — reuse the existing `ClientsListTable` visual structure.

- [ ] **Step 9.4: New-partner page `/portal/partners/new`**

Form with sections: Anagrafica (required: full_name, email, entity_type), Role (work_role, company_name, office_address, phone, preferred_language), Fiscal (npwp, nik, tax_withholding_category — default `tbd`; fiscal_address), Payment (bank fields + e-wallet + iban + currency + notes), Commission (default_commission_type radio, default_commission_value numeric — default 10), PDP consent (checkbox required before submit; writes `pdp_consent_at=now`, `pdp_consent_version='2026-04-20-v1'`).

Soft warning banner (yellow) when `work_role` input matches `/sponsor|garante|penjamin/i`:

> Reminder: only PT PMA Bali Zero can be the formal sponsor/garante on a visa.

On submit: POST → `/partners`. On success, route to `/portal/partners/{id}`.

- [ ] **Step 9.5: Detail page `/portal/partners/[id]`**

Tabs: **Profile** (read display of anagrafica), **Fiscal**, **Payment**, **Commission Policy**, **Referrals** (list from `listReferrals`), **Commissions** (list from `listCommissions` with status filter), **Audit**. Admin-only action buttons: Activate / Deactivate / Reassign / Bulk finance actions (on commission rows).

- [ ] **Step 9.6: Edit page `/portal/partners/[id]/edit`**

Same form as New but pre-populated via `getPartner`. Excludes `onboarding_status`, `assigned_to`, `welcome_email_sent_at` (those use dedicated endpoints).

- [ ] **Step 9.7: Orphaned page `/portal/partners/orphaned` (admin only)**

Uses `listPartners({ orphaned: true })`. Multi-select table + toolbar with "Reassign selected to…" user picker + required reason textarea → `bulkReassign`.

- [ ] **Step 9.8: Finance queue `/portal/partners/finance` (admin + finance perm)**

Three sections:

1. **Pending approval**: commissions where `status='accrued' AND eligible_for_approval_at <= now()` AND `withholding_category != 'tbd'`. Per-row "Approve" button.
2. **Approved (ready to pay)**: `status='approved'`. Per-row "Mark paid" modal (paid_via, reference, proof URL, receipt_type, receipt file). Asya-gate warning banner for first 3 payouts (track via `localStorage.partners_first_payouts_reviewed` counter; increment on first 3 sends; after 3, banner dismisses automatically).
3. **Pending clawbacks**: `status='clawback_pending'`. Per-row "Waive" button with reason prompt.

CSV export button at top: date-range picker → `exportFinanceCsv`.

- [ ] **Step 9.9: `ReferrerDropdown.tsx` component**

Props: `{value?: UUID, onChange: (partnerId: UUID | null) => void, ownerOnly?: boolean}`. Fetches `listPartners({ onboarding_status: 'active', assigned_to: ownerOnly ? currentUserId : undefined })`. Renders as a shadcn/ui `Select`. Include a "None" option to clear.

Integration: insert into the existing process create/edit form. Locate the file and add the component in the metadata section. On save, when a referrer is selected, POST to `/api/partners/{id}/referrals` with the new process_id after the process itself has been saved.

- [ ] **Step 9.10: Run frontend tests**

```bash
cd apps/mouth && npm test -- tests/app/portal/partners.spec.tsx
```

- [ ] **Step 9.11: Commit (may split into smaller commits per page if each compiles green)**

```bash
git add apps/mouth/src/lib/api/partners.ts \
        apps/mouth/src/app/portal/\(authenticated\)/partners/ \
        apps/mouth/src/components/portal/ReferrerDropdown.tsx \
        apps/mouth/src/config/navigation.ts \
        apps/mouth/tests/app/portal/partners.spec.tsx
git commit -m "feat(partners): team portal /portal/partners/* — list, new, detail, edit, finance

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Partner portal + middleware role-gate + E2E test

**Files:**

- Modify: `apps/mouth/src/middleware.ts`
- Create: `apps/mouth/src/app/portal/(authenticated)/partner/dashboard/page.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/partner/referrals/page.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/partner/commissions/page.tsx`
- Create: `apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx`
- Test: `apps/mouth/tests/middleware.spec.ts`
- Test: `apps/backend-rag/backend/tests/integration/test_partners_e2e.py`

- [ ] **Step 10.1: Middleware role-gate**

Open `apps/mouth/src/middleware.ts`. Add handling for `role=partner`:

```ts
// Inside the main middleware handler, after authentication resolves:
if (user.role === "partner") {
  const path = req.nextUrl.pathname;
  const allowedPrefixes = [
    "/portal/partner/",
    "/api/partners/me",
    "/login",
    "/logout",
  ];
  const allowed =
    allowedPrefixes.some((p) => path.startsWith(p)) ||
    path === "/portal/partner";
  if (!allowed) {
    return NextResponse.redirect(new URL("/portal/partner/dashboard", req.url));
  }
}
```

Tests:

```ts
// tests/middleware.spec.ts
import { NextRequest } from "next/server";
import { middleware } from "../src/middleware";

test("partner accessing /portal/clients is redirected to /portal/partner/dashboard", async () => {
  const req = new NextRequest(new URL("http://local/portal/clients"), {
    headers: { cookie: partnerCookie },
  });
  const res = await middleware(req);
  expect(res.status).toBe(307);
  expect(res.headers.get("location")).toContain("/portal/partner/dashboard");
});

test("partner accessing /portal/partner/referrals is allowed", async () => {
  const req = new NextRequest(
    new URL("http://local/portal/partner/referrals"),
    {
      headers: { cookie: partnerCookie },
    },
  );
  const res = await middleware(req);
  expect(res.status).toBe(200);
});

test("team user accessing /portal/partner/* is 403 (or redirect to /portal)", async () => {
  const req = new NextRequest(
    new URL("http://local/portal/partner/dashboard"),
    {
      headers: { cookie: teamCookie },
    },
  );
  const res = await middleware(req);
  expect([403, 307]).toContain(res.status);
});
```

- [ ] **Step 10.2: Partner dashboard page**

Fetches `/api/partners/me` and `/api/partners/me/commissions`. Shows:

- Greeting banner with partner name.
- 3 metric cards: Total earned (sum of paid), Pending (sum of accrued + approved), Total referrals.
- Recent referrals (last 5) from `/api/partners/me/referrals`.
- Recent commissions (last 5).

- [ ] **Step 10.3: Partner referrals page**

Full list from `/api/partners/me/referrals`. Columns: Process (sterilized client display), Service, Status, Referred at. No passport, no phone, no email of clients.

- [ ] **Step 10.4: Partner commissions page**

Full ledger from `/api/partners/me/commissions`. Columns: Date, Process (sterilized), Gross, Withholding, Net, Status, Paid at. Status filter chips.

- [ ] **Step 10.5: Partner profile page**

Read-only display. Note at the bottom: "To update your profile, reply to zantara@balizero.com. Direct editing will be available in a future release."

- [ ] **Step 10.6: Write E2E integration test**

```python
# tests/integration/test_partners_e2e.py
import pytest
from decimal import Decimal

from backend.services.crm.partners.events import handle_practice_status_changed


@pytest.mark.asyncio
async def test_full_flow_process_to_paid_email(
    db_conn, admin_user, team_user, process_factory, client_factory,
    brevo_mock,  # patches backend.services.crm.partners.emails._post_email
):
    # 1. Admin creates partner, activates
    svc = PartnersService(db_conn)
    pid = await svc.create_partner(
        full_name="Hotel Kama", email="ref@k.io",
        entity_type="corporate_pt", tax_withholding_category="pph23",
        assigned_to=team_user.id, created_by=admin_user.id,
    )
    await svc.activate_partner(pid, actor_user=admin_user.id)
    assert brevo_mock.welcome_called  # welcome email fired

    # 2. Team creates a process for a client, attaches the partner
    client = await client_factory(full_name="Mario Rossi")
    proc = await process_factory(
        client_id=client.id, service_type="KITAS E33G",
        total_invoiced_idr=Decimal("15000000"),
    )
    await svc.repo.insert_referral(
        partner_id=pid, process_id=proc.id,
        referred_by_user_id=team_user.id,
    )

    # 3. Process flips to completed+paid → EventBus fires handler
    await db_conn.execute(
        "UPDATE processes SET status='completed', payment_status='paid', "
        "completed_at = now() WHERE id = $1", proc.id,
    )
    await handle_practice_status_changed(
        {"process_id": str(proc.id), "new_status": "completed"}
    )

    # 4. Commission row now exists
    commissions = await svc.repo.list_commissions_for_partner(pid)
    assert len(commissions) == 1
    c = commissions[0]
    assert c.gross_amount_idr == Decimal("1500000")   # 10% of 15M
    assert c.withholding_amount_idr == Decimal("30000")  # 2% of 1.5M
    assert c.net_amount_idr == Decimal("1470000")

    # 5. Admin fast-forwards cooling-off → approves → marks paid
    await db_conn.execute(
        "UPDATE partner_commissions SET eligible_for_approval_at = now() - interval '1 day' "
        "WHERE id = $1", c.id,
    )
    engine = CommissionEngine(db_conn)
    await engine.approve(c.id, actor=admin_user.id)
    await engine.mark_paid(
        c.id, actor=admin_user.id,
        paid_via="BCA transfer", payment_reference="TX-20260520-001",
    )

    # 6. Email sent, client data sterilized
    sent_body = brevo_mock.commission_call_args["body"]
    assert "Mario R." in sent_body
    assert "Mario Rossi" not in sent_body
    assert "1,470,000" in sent_body  # net with thousands separator

    # 7. Partner's /me endpoints show the row
    partner_view = await svc.repo.list_commissions_for_partner(pid)
    assert partner_view[0].status == "paid"
```

- [ ] **Step 10.7: Run E2E**

```bash
PYTHONPATH=. pytest backend/tests/integration/test_partners_e2e.py -v
```

Expected: passes.

- [ ] **Step 10.8: Full backend suite**

```bash
PYTHONPATH=. pytest backend/tests/services/crm/partners/ \
                   backend/tests/routers/test_partners.py \
                   backend/tests/integration/test_partners_e2e.py \
                   backend/tests/migrations/test_migration_119.py -v
```

Expected: all pass. Fix any regressions before committing.

- [ ] **Step 10.9: Commit**

```bash
git add apps/mouth/src/middleware.ts \
        apps/mouth/src/app/portal/\(authenticated\)/partner/ \
        apps/mouth/tests/middleware.spec.ts \
        apps/backend-rag/backend/tests/integration/test_partners_e2e.py
git commit -m "feat(partners): partner portal + middleware role-gate + E2E integration test

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 10.10: Push branch and open PR**

```bash
git push origin feat/crm-partners-module
gh pr create --title "feat(crm): Partners module v1" --body "$(cat <<'EOF'
## Summary

- New Postgres tables + append-only commission ledger (migration 119)
- 20 API endpoints with RBAC + finance permissions
- EventBus accrual on `practice.status_changed` (completed+paid)
- Team portal `/portal/partners/*` + partner portal `/portal/partner/*`
- Brevo welcome + commission-earned emails with UU PDP data sterilization

## Test plan

- [ ] `PYTHONPATH=. pytest backend/tests/services/crm/partners/ -v` green
- [ ] `PYTHONPATH=. pytest backend/tests/routers/test_partners.py -v` green
- [ ] `PYTHONPATH=. pytest backend/tests/integration/test_partners_e2e.py -v` green
- [ ] Migration 119 applies + rolls back cleanly on staging Postgres
- [ ] Team portal QA: create → activate → welcome email received
- [ ] Partner portal QA: login → dashboard → referrals sterilized
- [ ] Finance QA: approve + mark-paid from admin view → commission email CC to team owner

Spec: `docs/superpowers/specs/2026-04-20-crm-partners-module.md`
Council: `docs/superpowers/specs/2026-04-20-partners-brainstorm/99-synthesis.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Post-merge verification

After PR merges to main and `fly-deploy.yml` ships `nuzantara-rag`:

```bash
# 1. Migration applied on Fly Postgres
fly ssh console -a nuzantara-postgres -C "psql -c '\d partners'"

# 2. Endpoint live
curl -s https://nuzantara-rag.fly.dev/api/partners \
  -H "Cookie: nz_access_token=..." | jq 'length'

# 3. EventBus handler registered
fly logs -a nuzantara-rag | grep "Partner handlers registered"

# 4. Subdomain team portal
open https://kita.balizero.com/portal/partners

# 5. Subdomain partner portal (with partner user)
open https://kita.balizero.com/portal/partner/dashboard
```

Telegram to `1125336968` on first real partner creation is a nice-to-have follow-up, not blocking.
