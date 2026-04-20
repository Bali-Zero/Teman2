"""
Tests for Migration 119: Partners module — 4 tables + users.partner_id + 2 system settings.

Verifies SQL structure, required columns, indexes, constraints, and idempotency
without requiring a live database connection (AsyncMock pattern).

Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3
Plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 1 (lines 98-318)
"""
from __future__ import annotations

import re
from unittest.mock import AsyncMock

import pytest

from backend.migrations.migration_119_partners import apply, rollback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_sql(calls) -> str:
    """Concatenate all SQL strings passed to conn.execute."""
    return "\n".join(call.args[0] for call in calls if call.args)


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql)


# ---------------------------------------------------------------------------
# Table presence (maps to plan test_migration_119_creates_4_tables)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_119_creates_4_tables():
    """All 4 partner tables must be mentioned in CREATE TABLE blocks."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)
    expected = {"partners", "partner_referrals", "partner_commissions", "partner_audit_log"}
    for table in expected:
        assert table in sql, f"Missing table reference: {table}"


# ---------------------------------------------------------------------------
# Column presence — partners table (maps to plan test_migration_119_creates_partners)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_119_creates_partners():
    """partners table must contain all required columns from spec §3.1."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)
    norm = _normalize(sql)

    # Columns that the plan specifically asserts
    assert "default_commission_value" in norm
    assert "tax_withholding_category" in norm
    assert "welcome_email_sent_at" in norm
    assert "pdp_consent_version" in norm

    # Additional required columns from spec §3.1
    assert "full_name" in norm
    assert "entity_type" in norm
    assert "onboarding_status" in norm
    assert "pdp_consent_at" in norm
    assert "terms_accepted_at" in norm
    assert "terms_version" in norm


# ---------------------------------------------------------------------------
# System settings seed (maps to plan test_migration_119_seeds_system_settings)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_119_seeds_system_settings():
    """apply() must INSERT both partner_* system_settings rows."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    assert "partner_clawback_auto_writeoff_idr" in sql
    assert "partner_accrual_cooling_off_days" in sql
    assert "ON CONFLICT (key) DO NOTHING" in sql


# ---------------------------------------------------------------------------
# Idempotency (maps to plan test_migration_119_idempotent)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_119_idempotent():
    """apply() uses IF NOT EXISTS / DO $$ guards — safe to call twice."""
    conn = AsyncMock()
    await apply(conn)
    await apply(conn)  # must not raise
    sql = _collect_sql(conn.execute.call_args_list)
    norm = _normalize(sql)

    # All CREATE TABLE must be inside DO $$ IF NOT EXISTS blocks
    assert "IF NOT EXISTS" in norm

    # All CREATE INDEX (including UNIQUE) must use IF NOT EXISTS
    all_create_idx = re.findall(r"CREATE (?:UNIQUE )?INDEX", sql)
    all_if_not_exists = re.findall(r"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS", sql)
    assert len(all_create_idx) > 0
    assert len(all_create_idx) == len(all_if_not_exists), (
        f"Every CREATE INDEX (including UNIQUE) must use IF NOT EXISTS "
        f"({len(all_create_idx)} total vs {len(all_if_not_exists)} with IF NOT EXISTS)"
    )


# ---------------------------------------------------------------------------
# Rollback (maps to plan test_migration_119_rollback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_119_rollback():
    """rollback() must drop all 4 tables and clean system_settings."""
    conn = AsyncMock()
    await apply(conn)
    await rollback(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    assert "DROP TABLE IF EXISTS partner_audit_log" in sql
    assert "DROP TABLE IF EXISTS partner_commissions" in sql
    assert "DROP TABLE IF EXISTS partner_referrals" in sql
    assert "DROP TABLE IF EXISTS partners" in sql
    assert "partner_clawback_auto_writeoff_idr" in sql
    assert "partner_accrual_cooling_off_days" in sql
    assert "DROP INDEX IF EXISTS idx_users_partner_id" in sql
    assert "DROP COLUMN IF EXISTS partner_id" in sql


# ---------------------------------------------------------------------------
# FK-safe drop order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_119_rollback_fk_order():
    """Rollback must drop child tables before parent (FK-safe order per spec §3.6)."""
    conn = AsyncMock()
    await rollback(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    pos_audit = sql.find("partner_audit_log")
    pos_commissions = sql.find("partner_commissions")
    pos_referrals = sql.find("partner_referrals")
    pos_partners = sql.find("DROP TABLE IF EXISTS partners")

    pos_users_partner_id = sql.find("DROP COLUMN IF EXISTS partner_id")
    assert pos_users_partner_id != -1, "rollback must drop users.partner_id column"
    assert pos_users_partner_id < pos_partners, \
        "users.partner_id must be dropped before DROP TABLE partners"

    # Children must be dropped before parent
    assert pos_audit < pos_partners, "partner_audit_log must be dropped before partners"
    assert pos_commissions < pos_partners, "partner_commissions must be dropped before partners"
    assert pos_referrals < pos_partners, "partner_referrals must be dropped before partners"


# ---------------------------------------------------------------------------
# users.partner_id column
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_119_adds_users_partner_id():
    """apply() must include ALTER TABLE users ADD COLUMN partner_id."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)
    assert "partner_id" in sql
    assert "users" in sql
    assert "idx_users_partner_id" in sql


# ---------------------------------------------------------------------------
# CHECK constraints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_119_check_constraints():
    """spec §3.1-§3.3 CHECK constraints must appear in the migration SQL."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    # partners checks
    assert "'individual','corporate_pt','corporate_cv','foreign'" in sql
    assert "'pph21','pph23','exempt','tbd'" in sql
    assert "'percentage','flat'" in sql
    assert "'pending_approval','active','inactive'" in sql

    # partner_referrals check
    assert "share_percent > 0 AND share_percent <= 100" in sql

    # partner_commissions checks
    assert "'accrual','clawback','manual_adjustment'" in sql
    assert "'accrued','approved','paid'" in sql


# ---------------------------------------------------------------------------
# Indexes — all named indexes from spec §3.1-§3.4
# ---------------------------------------------------------------------------


EXPECTED_INDEXES = [
    "idx_partners_email",
    "idx_partners_assigned_to",
    "idx_partners_onboarding_status",
    "idx_partners_entity_type",
    "idx_partner_referrals_partner_id",
    "idx_partner_referrals_process_id",
    "idx_partner_commissions_partner_id",
    "idx_partner_commissions_process_id",
    "idx_partner_commissions_status",
    "idx_partner_commissions_eligible_at",
    "idx_partner_commissions_assigned_to_snapshot",
    "idx_partner_audit_log_partner_id",
    "idx_partner_audit_log_at",
    "idx_users_partner_id",
]


@pytest.mark.asyncio
async def test_migration_119_all_indexes_created():
    """All named indexes from spec §3.1-§3.4 must appear in the migration."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)
    missing = [idx for idx in EXPECTED_INDEXES if idx not in sql]
    assert not missing, f"Missing indexes: {missing}"
