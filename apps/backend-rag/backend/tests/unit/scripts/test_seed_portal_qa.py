"""Safety tests for the disposable portal QA seeder."""

from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from backend.scripts.seed_portal_qa import (
    _upsert_portal_disabled_client,
    _upsert_synthetic_partner,
    validate_qa_database_url,
    validate_synthetic_document_fixture,
    validate_synthetic_email,
    validate_synthetic_invoice_file_id,
    validate_synthetic_pin,
)

QA_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "scripts" / "qa" / "portal_qa_schema.sql"
SECURITY_AUDIT_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3] / "migrations" / "migration_090_security_audit_log.py"
)
FUNNEL_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3] / "migrations" / "migration_109_funnel_sessions.py"
)


def test_portal_qa_security_audit_schema_matches_canonical_migration() -> None:
    """The prod-like revoke-all audit sink must mirror migration 090."""
    schema = QA_SCHEMA_PATH.read_text(encoding="utf-8")
    migration = SECURITY_AUDIT_MIGRATION_PATH.read_text(encoding="utf-8")
    security_audit_schema = schema.split(
        "CREATE TABLE IF NOT EXISTS security_audit_log (",
        maxsplit=1,
    )[1].split(
        ");",
        maxsplit=1,
    )[0]

    column_contract = (
        "id BIGSERIAL PRIMARY KEY",
        "user_id VARCHAR(255)",
        "user_email VARCHAR(255)",
        "action VARCHAR(100) NOT NULL",
        "resource_type VARCHAR(100)",
        "resource_id VARCHAR(255)",
        "ip_address INET",
        "user_agent TEXT",
        "details JSONB",
        "success BOOLEAN NOT NULL DEFAULT TRUE",
        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    )
    for column in column_contract:
        assert column in security_audit_schema
        assert column in migration

    for index in (
        "idx_security_audit_user",
        "idx_security_audit_action",
        "idx_security_audit_created",
    ):
        assert index in schema
        assert index in migration


def test_portal_qa_funnel_schema_matches_canonical_migration() -> None:
    """Portal analytics must persist against the production funnel shape."""
    schema = QA_SCHEMA_PATH.read_text(encoding="utf-8")
    migration = FUNNEL_MIGRATION_PATH.read_text(encoding="utf-8")
    normalized_schema = " ".join(schema.split())
    normalized_migration = " ".join(migration.split())

    for table in ("funnel_sessions", "funnel_attributions"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration

    for column in (
        "session_id VARCHAR(64) PRIMARY KEY",
        "funnel funnel_type_enum NOT NULL",
        "step_state JSONB DEFAULT '{}'::jsonb",
        "lead_profile JSONB DEFAULT '{}'::jsonb",
        "first_touched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
        "last_touched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
        "converted_to_client_id UUID NULL",
        "ip_hash VARCHAR(64)",
        "client_id UUID NOT NULL",
        "first_funnel funnel_type_enum NOT NULL",
        "touchpoints JSONB DEFAULT '[]'::jsonb",
        "first_touch_at TIMESTAMP WITH TIME ZONE NOT NULL",
    ):
        assert column in normalized_schema
        assert column in normalized_migration

    for index in (
        "idx_funnel_sessions_funnel_last_touched",
        "idx_funnel_sessions_converted",
        "idx_funnel_sessions_expires_at",
        "idx_funnel_attributions_client",
    ):
        assert index in schema
        assert index in migration


def test_portal_qa_timeline_schema_matches_document_mutation_contract() -> None:
    """The prod-like schema must enforce the timeline values used in production."""
    schema = QA_SCHEMA_PATH.read_text(encoding="utf-8")
    timeline_schema = schema.split(
        "CREATE TABLE IF NOT EXISTS timeline_events (",
        maxsplit=1,
    )[1].split(
        ");",
        maxsplit=1,
    )[0]

    assert "color VARCHAR(50) DEFAULT 'info'" in timeline_schema
    assert "CONSTRAINT chk_timeline_event_type" in timeline_schema
    assert "CONSTRAINT chk_timeline_color" in timeline_schema
    for event_type in ("document_received", "status_change"):
        assert f"'{event_type}'" in timeline_schema
    for color in ("info", "warning", "success", "error"):
        assert f"'{color}'" in timeline_schema


def test_portal_qa_lkpm_schema_covers_client_safe_history_and_receipts() -> None:
    """The prod-like schema must support the two portal LKPM read paths."""
    schema = QA_SCHEMA_PATH.read_text(encoding="utf-8")

    for table in ("lkpm_client_config", "lkpm_reports", "lkpm_receipts"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
    assert "CONSTRAINT uq_lkpm_report UNIQUE (client_id, company_id, quarter, year)" in schema
    assert "REFERENCES lkpm_reports(id) ON DELETE CASCADE" in schema
    assert "file_drive_id TEXT" in schema
    assert "file_drive_url TEXT" in schema


def test_portal_qa_workspace_snapshot_schema_matches_matter_detail_contract() -> None:
    """The prod-like matter detail must exercise the production snapshot shape."""
    schema = QA_SCHEMA_PATH.read_text(encoding="utf-8")

    snapshot_schema = schema.split(
        "CREATE TABLE IF NOT EXISTS crm_workspace_ai_snapshots (",
        maxsplit=1,
    )[1].split(
        ");",
        maxsplit=1,
    )[0]

    for column in (
        "company_id BIGINT REFERENCES companies(id) ON DELETE SET NULL",
        "client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL",
        "company_name TEXT NOT NULL",
        "facts JSONB NOT NULL DEFAULT '[]'::jsonb",
        "status TEXT NOT NULL DEFAULT 'draft'",
        "approved_at TIMESTAMPTZ",
        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    ):
        assert column in snapshot_schema

    for index in (
        "idx_crm_workspace_ai_snapshots_company_status",
        "idx_crm_workspace_ai_snapshots_client_status",
        "idx_crm_workspace_ai_snapshots_facts",
    ):
        assert index in schema


def test_portal_qa_partner_schema_matches_self_service_contract() -> None:
    """The prod-like schema must exercise the canonical Partner read shapes."""
    schema = QA_SCHEMA_PATH.read_text(encoding="utf-8")
    commission_schema = schema.split(
        "CREATE TABLE IF NOT EXISTS partner_commissions (",
        maxsplit=1,
    )[1].split(
        ");",
        maxsplit=1,
    )[0]

    for table in ("partners", "partner_referrals", "partner_commissions"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
    assert "ADD COLUMN IF NOT EXISTS partner_id UUID REFERENCES partners(id)" in schema
    assert "ADD COLUMN IF NOT EXISTS service_type TEXT" in schema
    for column in (
        "base_amount_idr NUMERIC(16, 2) NOT NULL",
        "gross_amount_idr NUMERIC(16, 2) NOT NULL",
        "withholding_amount_idr NUMERIC(16, 2) NOT NULL DEFAULT 0.0",
        "net_amount_idr NUMERIC(16, 2) NOT NULL",
        "status TEXT NOT NULL DEFAULT 'accrued'",
        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    ):
        assert column in commission_schema


@pytest.mark.asyncio
async def test_portal_disabled_fixture_is_active_but_cannot_establish_a_session() -> None:
    conn = AsyncMock()

    await _upsert_portal_disabled_client(
        conn,
        email="portal-disabled@example.com",
        pin_hash="synthetic-hash",
        linked_client_id=42,
    )

    sql, email, _name, pin_hash, client_id = conn.execute.await_args.args
    assert "active,\n            linked_client_id, portal_access, last_login" in sql
    assert "TRUE, $4, FALSE, NULL" in sql
    assert "portal_access = FALSE" in sql
    assert "last_login = NULL" in sql
    assert email == "portal-disabled@example.com"
    assert pin_hash == "synthetic-hash"
    assert client_id == 42


@pytest.mark.asyncio
async def test_partner_fixture_links_a_partner_role_without_client_entitlement() -> None:
    conn = AsyncMock()
    partner_id = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    conn.fetchval.return_value = partner_id

    result = await _upsert_synthetic_partner(
        conn,
        email="portal-partner@example.com",
        pin_hash="synthetic-hash",
    )

    assert result == partner_id
    partner_sql, partner_name, email = conn.fetchval.await_args.args
    assert "INSERT INTO partners" in partner_sql
    assert "onboarding_status = 'active'" in partner_sql
    assert partner_name == "Synthetic Portal Partner"
    assert email == "portal-partner@example.com"

    team_sql, team_email, team_name, pin_hash, linked_partner_id = conn.execute.await_args.args
    assert "'partner', 'en', TRUE, NULL, FALSE, $4" in team_sql
    assert "linked_client_id = NULL" in team_sql
    assert "portal_access = FALSE" in team_sql
    assert "partner_id = EXCLUDED.partner_id" in team_sql
    assert team_email == "portal-partner@example.com"
    assert team_name == "Synthetic Portal Partner"
    assert pin_hash == "synthetic-hash"
    assert linked_partner_id == partner_id


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://portal_qa@localhost:55433/my_portal_qa",
        "postgresql://portal_qa@127.0.0.1:55433/my_portal_qa_run_1",
        "postgres://portal_qa@[::1]:55433/my_portal_qa_test",
    ],
)
def test_validate_qa_database_url_accepts_disposable_loopback_targets(
    database_url: str,
) -> None:
    assert validate_qa_database_url(database_url).startswith("my_portal_qa")


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://readonly@example.internal/nuzantara",
        "postgresql://portal_qa@127.0.0.1:55433/nuzantara_dev",
        "postgresql://portal_qa@127.0.0.1:55433/nuzantara_prod",
        "sqlite:///my_portal_qa",
    ],
)
def test_validate_qa_database_url_rejects_unsafe_targets(database_url: str) -> None:
    with pytest.raises(ValueError):
        validate_qa_database_url(database_url)


def test_validate_synthetic_email_accepts_reserved_example_domain() -> None:
    assert validate_synthetic_email("ACTIVE-CLIENT@example.com") == ("active-client@example.com")


@pytest.mark.parametrize(
    "email",
    [
        "active-client@my-portal-qa.example.test",
        "active-client@balizero.com",
        "active-client@qa.example.com",
        "missing-at-sign",
    ],
)
def test_validate_synthetic_email_rejects_non_fixture_domains(email: str) -> None:
    with pytest.raises(ValueError, match="example.com"):
        validate_synthetic_email(email)


@pytest.mark.parametrize("pin", ["1234", " 12345 ", "123456"])
def test_validate_synthetic_pin_accepts_registration_contract(pin: str) -> None:
    assert validate_synthetic_pin(pin) == pin.strip()


@pytest.mark.parametrize("pin", ["123", "1234567", "12ab", ""])
def test_validate_synthetic_pin_rejects_non_registration_values(pin: str) -> None:
    with pytest.raises(ValueError, match="4-6 digits"):
        validate_synthetic_pin(pin)


@pytest.mark.parametrize(
    "file_name",
    [
        "synthetic-portal-tenant-boundary.pdf",
        "  SYNTHETIC-PORTAL-DOCUMENT-1.PDF  ",
    ],
)
def test_validate_synthetic_document_fixture_accepts_reserved_pdf_name(
    file_name: str,
) -> None:
    assert validate_synthetic_document_fixture(file_name).startswith("synthetic-portal-")


@pytest.mark.parametrize(
    "file_name",
    [
        "passport.pdf",
        "client-passport.pdf",
        "../synthetic-portal-boundary.pdf",
        "synthetic-portal-boundary.docx",
    ],
)
def test_validate_synthetic_document_fixture_rejects_unsafe_names(file_name: str) -> None:
    with pytest.raises(ValueError, match="Synthetic document fixture"):
        validate_synthetic_document_fixture(file_name)


@pytest.mark.parametrize(
    "file_id",
    [
        "synthetic_invoice_pdf_fixture_00000001",
        " synthetic_invoice_pdf_chromium_prodlike_01 ",
    ],
)
def test_validate_synthetic_invoice_file_id_accepts_reserved_ids(file_id: str) -> None:
    assert validate_synthetic_invoice_file_id(file_id).startswith("synthetic_invoice_pdf_")


@pytest.mark.parametrize(
    "file_id",
    ["drive-file-id", "client_invoice_1", "synthetic_invoice_pdf_short", ""],
)
def test_validate_synthetic_invoice_file_id_rejects_unreserved_ids(file_id: str) -> None:
    with pytest.raises(ValueError, match="Synthetic invoice file ID"):
        validate_synthetic_invoice_file_id(file_id)
