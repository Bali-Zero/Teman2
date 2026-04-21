"""Migration 119: Partners module — 4 tables + 2 system settings.

Why
---
Formalizes Bali Zero's informal third-party referral network (hotels, property
managers, consultants, agents) into a first-class CRM module with full
Indonesian fiscal profile, an append-only commission ledger, and GDPR/UU PDP
consent tracking.

Schema
------
- partners: anagrafica + fiscal profile + payment rail + commission defaults
- partner_referrals: links partners to existing practices (v1: 1-to-1)
- partner_commissions: append-only ledger (accrued → approved → paid, with clawback)
- partner_audit_log: immutable event trail for every partner/commission state change
- users.partner_id: reverse FK so partner-role users can resolve their own record

System settings
---------------
- partner_clawback_auto_writeoff_idr: auto-waive threshold (default 0 = disabled)
- partner_accrual_cooling_off_days: days before accrual becomes eligible (default 30)

Idempotent: safe to re-run.

Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3
Plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 1
Author: Claude Opus 4.7
Date: 2026-04-20
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    # -------------------------------------------------------------------------
    # 1. partners
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partners'
            ) THEN
                CREATE TABLE partners (
                    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                    -- anagrafica
                    full_name                 TEXT NOT NULL,
                    work_role                 TEXT,
                    company_name              TEXT,
                    office_address            TEXT,
                    email                     TEXT NOT NULL UNIQUE,
                    phone                     TEXT,
                    preferred_language        TEXT DEFAULT 'id',

                    -- fiscal (Indonesia)
                    entity_type               TEXT NOT NULL
                        CHECK (entity_type IN ('individual','corporate_pt','corporate_cv','foreign')),
                    npwp                      TEXT,
                    nik                       TEXT,
                    tax_withholding_category  TEXT NOT NULL DEFAULT 'tbd'
                        CHECK (tax_withholding_category IN ('pph21','pph23','exempt','tbd')),
                    fiscal_address            TEXT,

                    -- payment rail
                    bank_name                 TEXT,
                    bank_account_holder       TEXT,
                    bank_account_number       TEXT,
                    ewallet_type              TEXT,
                    ewallet_number            TEXT,
                    payment_currency          TEXT NOT NULL DEFAULT 'IDR',
                    iban                      TEXT,
                    payment_notes             TEXT,

                    -- commission policy (v1 uses partner-level defaults)
                    default_commission_type   TEXT NOT NULL DEFAULT 'percentage'
                        CHECK (default_commission_type IN ('percentage','flat')),
                    default_commission_value  NUMERIC(14,4) NOT NULL DEFAULT 10.0,

                    -- lifecycle
                    onboarding_status         TEXT NOT NULL DEFAULT 'pending_approval'
                        CHECK (onboarding_status IN ('pending_approval','active','inactive')),
                    assigned_to               UUID REFERENCES users(id) ON DELETE SET NULL,

                    -- UU PDP + T&C
                    pdp_consent_at            TIMESTAMPTZ,
                    pdp_consent_version       TEXT,
                    terms_accepted_at         TIMESTAMPTZ,
                    terms_version             TEXT,

                    -- audit + idempotency
                    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
                    created_by                UUID REFERENCES users(id) ON DELETE SET NULL,
                    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
                    deactivated_at            TIMESTAMPTZ,
                    welcome_email_sent_at     TIMESTAMPTZ
                );
            END IF;
        END $$;
    """)

    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_email"
        " ON partners (email);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partners_assigned_to"
        " ON partners (assigned_to)"
        " WHERE assigned_to IS NOT NULL;"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partners_onboarding_status"
        " ON partners (onboarding_status);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partners_entity_type"
        " ON partners (entity_type);"
    )

    # -------------------------------------------------------------------------
    # 2. users.partner_id — reverse FK so partner-role users resolve their record
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'partner_id'
            ) THEN
                ALTER TABLE users ADD COLUMN partner_id UUID REFERENCES partners(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_partner_id"
        " ON users (partner_id) WHERE partner_id IS NOT NULL;"
    )

    # -------------------------------------------------------------------------
    # 3. partner_referrals
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partner_referrals'
            ) THEN
                CREATE TABLE partner_referrals (
                    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    partner_id           UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
                    practice_id          UUID NOT NULL REFERENCES practices(id) ON DELETE RESTRICT,
                    share_percent        NUMERIC(5,2) NOT NULL DEFAULT 100.00
                        CHECK (share_percent > 0 AND share_percent <= 100),
                    referred_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                    referred_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
                    notes                TEXT,

                    CONSTRAINT partner_referrals_practice_unique_v1 UNIQUE (practice_id)
                    -- v2: drop this constraint when enabling split commissions
                );
            END IF;
        END $$;
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_referrals_partner_id"
        " ON partner_referrals (partner_id);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_referrals_practice_id"
        " ON partner_referrals (practice_id);"
    )

    # -------------------------------------------------------------------------
    # 4. partner_commissions (append-only ledger)
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partner_commissions'
            ) THEN
                CREATE TABLE partner_commissions (
                    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    partner_id               UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
                    referral_id              UUID REFERENCES partner_referrals(id) ON DELETE RESTRICT,
                    practice_id              UUID REFERENCES practices(id) ON DELETE RESTRICT,

                    -- row type
                    entry_type               TEXT NOT NULL
                        CHECK (entry_type IN ('accrual','clawback','manual_adjustment')),
                    related_commission_id    UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,

                    -- immutable snapshot
                    base_amount_idr          NUMERIC(16,2) NOT NULL,
                    commission_type_snapshot TEXT NOT NULL
                        CHECK (commission_type_snapshot IN ('percentage','flat')),
                    commission_value_snapshot NUMERIC(14,4) NOT NULL,
                    rule_source              TEXT NOT NULL DEFAULT 'partner_default'
                        CHECK (rule_source IN ('partner_default','manual_override')),
                    assigned_to_snapshot     UUID REFERENCES users(id) ON DELETE SET NULL,

                    -- amounts (IDR; clawbacks store NEGATIVE)
                    gross_amount_idr         NUMERIC(16,2) NOT NULL,
                    withholding_category     TEXT NOT NULL DEFAULT 'tbd'
                        CHECK (withholding_category IN ('pph21','pph23','exempt','tbd')),
                    withholding_rate         NUMERIC(6,4) NOT NULL DEFAULT 0.0,
                    withholding_amount_idr   NUMERIC(16,2) NOT NULL DEFAULT 0.0,
                    net_amount_idr           NUMERIC(16,2) NOT NULL,

                    -- status lifecycle
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

                    -- finance / clawback audit
                    manual_override_reason   TEXT,
                    clawback_reason          TEXT,
                    waiver_reason            TEXT,
                    idempotency_key          TEXT UNIQUE,
                    commission_email_sent_at TIMESTAMPTZ,

                    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            END IF;
        END $$;
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_partner_id"
        " ON partner_commissions (partner_id);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_practice_id"
        " ON partner_commissions (practice_id);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_status"
        " ON partner_commissions (status);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_eligible_at"
        " ON partner_commissions (eligible_for_approval_at)"
        " WHERE status = 'accrued';"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_assigned_to_snapshot"
        " ON partner_commissions (assigned_to_snapshot)"
        " WHERE assigned_to_snapshot IS NOT NULL;"
    )

    # -------------------------------------------------------------------------
    # 5. partner_audit_log
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partner_audit_log'
            ) THEN
                CREATE TABLE partner_audit_log (
                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    partner_id    UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
                    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    action        TEXT NOT NULL,
                    before_json   JSONB,
                    after_json    JSONB,
                    reason        TEXT,
                    at            TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            END IF;
        END $$;
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_audit_log_partner_id"
        " ON partner_audit_log (partner_id);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_audit_log_at"
        " ON partner_audit_log (at DESC);"
    )

    # -------------------------------------------------------------------------
    # 6. system_settings seed rows (spec §3.5 + CRIT-7)
    # -------------------------------------------------------------------------
    await conn.execute("""
        INSERT INTO system_settings (key, value, description) VALUES
          ('partner_clawback_auto_writeoff_idr', '0',
           'If > 0, clawback rows below this IDR amount auto-waive on creation. Default 0 = disabled.'),
          ('partner_accrual_cooling_off_days', '30',
           'Days between accrual and eligibility for approval. Default 30.'),
          ('partner_withholding_rate_pph21', '2.5',
           'Default PPh21 withholding rate (percent) for individual partners with NPWP. Asya to confirm.'),
          ('partner_withholding_rate_pph23', '2.0',
           'Default PPh23 withholding rate (percent) for corporate partners. Asya to confirm.'),
          ('partner_withholding_no_npwp_surcharge', '20',
           'Additional percentage surcharge on PPh rates for partners without NPWP (Indonesian tax law default).')
        ON CONFLICT (key) DO NOTHING;
    """)

    logger.info(
        "Migration 119: partners + partner_referrals + partner_commissions"
        " + partner_audit_log + users.partner_id + 5 system_settings rows"
    )


async def rollback(conn: Any) -> None:
    # Drop in FK-safe order: children first, parent last (spec §3.6)
    await conn.execute("DROP TABLE IF EXISTS partner_audit_log;")
    await conn.execute("DROP TABLE IF EXISTS partner_commissions;")
    await conn.execute("DROP TABLE IF EXISTS partner_referrals;")
    # Drop users.partner_id index + column before dropping partners (it references partners.id)
    await conn.execute("DROP INDEX IF EXISTS idx_users_partner_id;")
    await conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS partner_id;")
    await conn.execute("DROP TABLE IF EXISTS partners;")
    await conn.execute(
        "DELETE FROM system_settings WHERE key IN ("
        "'partner_clawback_auto_writeoff_idr','partner_accrual_cooling_off_days',"
        "'partner_withholding_rate_pph21','partner_withholding_rate_pph23',"
        "'partner_withholding_no_npwp_surcharge'"
        ");"
    )
    logger.info(
        "Migration 119 rollback: 4 tables dropped, users.partner_id removed,"
        " 5 system_settings rows deleted"
    )
