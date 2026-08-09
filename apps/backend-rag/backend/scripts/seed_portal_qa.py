"""Seed the disposable my.balizero.com prod-like QA database.

The script is deliberately fail-closed: only a loopback PostgreSQL database
whose name starts with ``my_portal_qa`` is accepted. Credentials arrive via
environment variables and are never logged.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import asyncpg
import bcrypt

logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_DATABASE_PREFIX = "my_portal_qa"
_SYNTHETIC_EMAIL_DOMAIN = "example.com"
_SYNTHETIC_DOCUMENT_PATTERN = re.compile(r"synthetic-portal-[a-z0-9-]+\.pdf")
_SYNTHETIC_INVOICE_FILE_ID_PATTERN = re.compile(
    r"synthetic_invoice_pdf_[a-z0-9_-]{10,200}",
)
_SYNTHETIC_ADDRESS = "Synthetic QA Address"
_SYNTHETIC_TEAM_MESSAGE = "Synthetic QA message from the Bali Zero team"
_SYNTHETIC_NOTIFICATION_TITLE = "Synthetic QA notification"
_SYNTHETIC_COMPANY_NAME = "Synthetic Portal Company"
_SYNTHETIC_INVOICE_NUMBER = "QA-INV-2026-0001"
_SYNTHETIC_ADULT_NAME = "Synthetic Adult Member"
_SYNTHETIC_MINOR_NAME = "Synthetic Minor Member"
_SYNTHETIC_LKPM_RECEIPT_NUMBER = "QA-LKPM-2026-0001"
_SYNTHETIC_PARTNER_NAME = "Synthetic Portal Partner"
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "scripts" / "qa" / "portal_qa_schema.sql"


def validate_qa_database_url(database_url: str) -> str:
    """Return the database name after proving the target is disposable."""
    parsed = urlparse(database_url)
    database_name = parsed.path.lstrip("/")
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("QA seed requires a PostgreSQL DATABASE_URL")
    if (parsed.hostname or "").lower() not in _LOOPBACK_HOSTS:
        raise ValueError("QA seed refuses non-loopback database hosts")
    if not database_name.startswith(_DATABASE_PREFIX):
        raise ValueError(
            f"QA seed database name must start with {_DATABASE_PREFIX!r}",
        )
    return database_name


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def validate_synthetic_email(email: str) -> str:
    """Accept only a reserved, application-valid synthetic email domain."""
    normalized = email.strip().lower()
    if normalized.rpartition("@")[2] != _SYNTHETIC_EMAIL_DOMAIN:
        raise ValueError("Synthetic account email must use example.com")
    return normalized


def validate_synthetic_pin(pin: str) -> str:
    """Accept the same numeric PIN contract enforced by portal registration."""
    normalized = pin.strip()
    if not normalized.isdigit() or not (4 <= len(normalized) <= 6):
        raise ValueError("Synthetic client PIN must be 4-6 digits")
    return normalized


def validate_synthetic_document_fixture(file_name: str) -> str:
    """Accept only a reserved, path-free PDF fixture name."""
    normalized = file_name.strip().lower()
    if Path(normalized).name != normalized or not _SYNTHETIC_DOCUMENT_PATTERN.fullmatch(
        normalized,
    ):
        raise ValueError(
            "Synthetic document fixture must match synthetic-portal-<slug>.pdf",
        )
    return normalized


def validate_synthetic_invoice_file_id(file_id: str) -> str:
    """Accept only the reserved opaque identifier preloaded by the QA sink."""
    normalized = file_id.strip()
    if not _SYNTHETIC_INVOICE_FILE_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Synthetic invoice file ID must use the reserved QA sink namespace",
        )
    return normalized


async def _upsert_synthetic_client(
    conn: asyncpg.Connection,
    *,
    email: str,
    pin_hash: str,
    full_name: str,
    assigned_to: str | None,
) -> int:
    """Create or refresh one synthetic portal principal and return its tenant id."""
    client_id = await conn.fetchval(
        """
        INSERT INTO clients (
            full_name, email, nationality, address, phone, whatsapp, assigned_to
        )
        VALUES ($1, $2, 'Synthetic', $3, NULL, NULL, $4)
        ON CONFLICT (email) DO UPDATE
        SET full_name = EXCLUDED.full_name,
            nationality = EXCLUDED.nationality,
            address = EXCLUDED.address,
            phone = NULL,
            whatsapp = NULL,
            assigned_to = EXCLUDED.assigned_to,
            deleted_at = NULL,
            updated_at = NOW()
        RETURNING id
        """,
        full_name,
        email,
        _SYNTHETIC_ADDRESS,
        assigned_to,
    )
    await conn.execute(
        """
        INSERT INTO team_members (
            email, full_name, name, pin_hash, role, language, active,
            linked_client_id, portal_access
        )
        VALUES ($1, $2, $2, $3, 'client', 'en', TRUE, $4, TRUE)
        ON CONFLICT (email) DO UPDATE
        SET full_name = EXCLUDED.full_name,
            name = EXCLUDED.name,
            pin_hash = EXCLUDED.pin_hash,
            role = 'client',
            language = 'en',
            active = TRUE,
            linked_client_id = EXCLUDED.linked_client_id,
            portal_access = TRUE,
            failed_attempts = 0,
            updated_at = NOW()
        """,
        email,
        full_name,
        pin_hash,
        client_id,
    )
    await conn.execute(
        """
        INSERT INTO client_preferences (
            client_id, email_notifications, whatsapp_notifications,
            language, timezone
        )
        VALUES ($1, FALSE, FALSE, 'en', 'Asia/Makassar')
        ON CONFLICT (client_id) DO UPDATE
        SET email_notifications = FALSE,
            whatsapp_notifications = FALSE,
            language = 'en',
            timezone = 'Asia/Makassar',
            updated_at = NOW()
        """,
        client_id,
    )
    await conn.execute(
        """
        INSERT INTO notification_prefs (
            user_id, email_enabled, wa_enabled, wa_phone, updated_at
        )
        SELECT id, TRUE, FALSE, NULL, NOW()
        FROM team_members
        WHERE email = $1
        ON CONFLICT (user_id) DO UPDATE
        SET email_enabled = TRUE,
            wa_enabled = FALSE,
            wa_phone = NULL,
            updated_at = NOW()
        """,
        email,
    )
    return int(client_id)


async def _upsert_portal_disabled_client(
    conn: asyncpg.Connection,
    *,
    email: str,
    pin_hash: str,
    linked_client_id: int,
) -> None:
    """Create a valid-credential principal whose portal entitlement is disabled."""
    await conn.execute(
        """
        INSERT INTO team_members (
            email, full_name, name, pin_hash, role, language, active,
            linked_client_id, portal_access, last_login
        )
        VALUES ($1, $2, $2, $3, 'client', 'en', TRUE, $4, FALSE, NULL)
        ON CONFLICT (email) DO UPDATE
        SET full_name = EXCLUDED.full_name,
            name = EXCLUDED.name,
            pin_hash = EXCLUDED.pin_hash,
            role = 'client',
            language = 'en',
            active = TRUE,
            linked_client_id = EXCLUDED.linked_client_id,
            portal_access = FALSE,
            last_login = NULL,
            failed_attempts = 0,
            updated_at = NOW()
        """,
        email,
        "Synthetic Portal Disabled Client",
        pin_hash,
        linked_client_id,
    )


async def _upsert_synthetic_partner(
    conn: asyncpg.Connection,
    *,
    email: str,
    pin_hash: str,
) -> UUID:
    """Create or refresh the isolated Partner principal and profile."""
    partner_id = await conn.fetchval(
        """
        INSERT INTO partners (
            full_name, work_role, company_name, email, phone,
            preferred_language, entity_type, tax_withholding_category,
            bank_name, bank_account_holder, bank_account_number,
            default_commission_type, default_commission_value,
            onboarding_status, pdp_consent_at, pdp_consent_version,
            terms_accepted_at, terms_version
        )
        VALUES (
            $1, 'Synthetic Referral Partner', 'Synthetic Partner Company',
            $2, NULL, 'en', 'individual', 'pph21',
            'Synthetic QA Bank', $1, 'SYNTHETIC-NON-PAYABLE',
            'percentage', 10, 'active',
            TIMESTAMPTZ '2026-01-15 00:00:00+00', 'qa-v1',
            TIMESTAMPTZ '2026-01-15 00:00:00+00', 'qa-v1'
        )
        ON CONFLICT (email) DO UPDATE
        SET full_name = EXCLUDED.full_name,
            work_role = EXCLUDED.work_role,
            company_name = EXCLUDED.company_name,
            phone = NULL,
            preferred_language = 'en',
            entity_type = 'individual',
            tax_withholding_category = 'pph21',
            bank_name = EXCLUDED.bank_name,
            bank_account_holder = EXCLUDED.bank_account_holder,
            bank_account_number = EXCLUDED.bank_account_number,
            default_commission_type = 'percentage',
            default_commission_value = 10,
            onboarding_status = 'active',
            pdp_consent_at = EXCLUDED.pdp_consent_at,
            pdp_consent_version = EXCLUDED.pdp_consent_version,
            terms_accepted_at = EXCLUDED.terms_accepted_at,
            terms_version = EXCLUDED.terms_version,
            deactivated_at = NULL,
            updated_at = NOW()
        RETURNING id
        """,
        _SYNTHETIC_PARTNER_NAME,
        email,
    )
    await conn.execute(
        """
        INSERT INTO team_members (
            email, full_name, name, pin_hash, role, language, active,
            linked_client_id, portal_access, partner_id
        )
        VALUES ($1, $2, $2, $3, 'partner', 'en', TRUE, NULL, FALSE, $4)
        ON CONFLICT (email) DO UPDATE
        SET full_name = EXCLUDED.full_name,
            name = EXCLUDED.name,
            pin_hash = EXCLUDED.pin_hash,
            role = 'partner',
            language = 'en',
            active = TRUE,
            linked_client_id = NULL,
            portal_access = FALSE,
            partner_id = EXCLUDED.partner_id,
            failed_attempts = 0,
            updated_at = NOW()
        """,
        email,
        _SYNTHETIC_PARTNER_NAME,
        pin_hash,
        partner_id,
    )
    return partner_id


async def _reset_tenant_product_data(conn: asyncpg.Connection, client_id: int) -> None:
    """Remove synthetic product rows so every QA run starts deterministically."""
    await conn.execute(
        """
        DELETE FROM lkpm_receipts
        WHERE lkpm_report_id IN (
            SELECT id FROM lkpm_reports WHERE client_id = $1
        )
        """,
        client_id,
    )
    await conn.execute("DELETE FROM lkpm_reports WHERE client_id = $1", client_id)
    await conn.execute("DELETE FROM lkpm_client_config WHERE client_id = $1", client_id)
    await conn.execute(
        """
        DELETE FROM practice_required_documents
        WHERE practice_id IN (SELECT id FROM practices WHERE client_id = $1)
        """,
        client_id,
    )
    for table in (
        "invoices",
        "client_family_members",
        "documents",
        "portal_messages",
        "crm_workspace_ai_snapshots",
        "client_company_links",
        "timeline_events",
        "portal_notifications",
        "notification_alerts",
        "practices",
    ):
        await conn.execute(f"DELETE FROM {table} WHERE client_id = $1", client_id)


async def seed() -> None:
    """Create disposable client and Partner principals plus safe fixtures."""
    database_url = _required_environment("DATABASE_URL")
    validate_qa_database_url(database_url)
    active_email = validate_synthetic_email(
        _required_environment("MY_PORTAL_SYNTHETIC_CLIENT_EMAIL"),
    )
    active_pin = validate_synthetic_pin(
        _required_environment("MY_PORTAL_SYNTHETIC_CLIENT_PIN"),
    )
    empty_email = validate_synthetic_email(
        _required_environment("MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_EMAIL"),
    )
    empty_pin = validate_synthetic_pin(
        _required_environment("MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_PIN"),
    )
    disabled_email = validate_synthetic_email(
        _required_environment("MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_EMAIL"),
    )
    disabled_pin = validate_synthetic_pin(
        _required_environment("MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_PIN"),
    )
    partner_email = validate_synthetic_email(
        _required_environment("MY_PORTAL_SYNTHETIC_PARTNER_EMAIL"),
    )
    partner_pin = validate_synthetic_pin(
        _required_environment("MY_PORTAL_SYNTHETIC_PARTNER_PIN"),
    )
    support_recipient = validate_synthetic_email(
        _required_environment("MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT"),
    )
    document_fixture = validate_synthetic_document_fixture(
        _required_environment("MY_PORTAL_SYNTHETIC_DOCUMENT_FIXTURE"),
    )
    invoice_file_id = validate_synthetic_invoice_file_id(
        _required_environment("MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID"),
    )
    account_emails = {active_email, empty_email, disabled_email, partner_email}
    if len(account_emails) != 4:
        raise ValueError("Synthetic portal account emails must be distinct")
    if support_recipient in account_emails:
        raise ValueError("Synthetic support recipient must be distinct from portal accounts")

    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    active_pin_hash = bcrypt.hashpw(
        active_pin.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")
    empty_pin_hash = bcrypt.hashpw(
        empty_pin.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")
    disabled_pin_hash = bcrypt.hashpw(
        disabled_pin.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")
    partner_pin_hash = bcrypt.hashpw(
        partner_pin.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")
    conn = await asyncpg.connect(database_url)
    try:
        async with conn.transaction():
            await conn.execute(schema_sql)
            partner_id = await _upsert_synthetic_partner(
                conn,
                email=partner_email,
                pin_hash=partner_pin_hash,
            )
            await conn.execute(
                "DELETE FROM partner_commissions WHERE partner_id = $1",
                partner_id,
            )
            await conn.execute(
                "DELETE FROM partner_referrals WHERE partner_id = $1",
                partner_id,
            )
            active_client_id = await _upsert_synthetic_client(
                conn,
                email=active_email,
                pin_hash=active_pin_hash,
                full_name="Synthetic Active Portal Client",
                assigned_to=support_recipient,
            )
            empty_client_id = await _upsert_synthetic_client(
                conn,
                email=empty_email,
                pin_hash=empty_pin_hash,
                full_name="Synthetic Empty Portal Client",
                assigned_to=None,
            )
            await _upsert_portal_disabled_client(
                conn,
                email=disabled_email,
                pin_hash=disabled_pin_hash,
                linked_client_id=empty_client_id,
            )
            await _reset_tenant_product_data(conn, active_client_id)
            await _reset_tenant_product_data(conn, empty_client_id)
            await conn.execute(
                """
                DELETE FROM companies
                WHERE company_name = $1 AND company_email = 'company@example.com'
                """,
                _SYNTHETIC_COMPANY_NAME,
            )
            practice_type_id = await conn.fetchval(
                """
                SELECT id FROM practice_types
                WHERE code = 'QA_COMPANY_SERVICE'
                ORDER BY id
                LIMIT 1
                """
            )
            if practice_type_id is None:
                practice_type_id = await conn.fetchval(
                    """
                    INSERT INTO practice_types (code, name, category)
                    VALUES ('QA_COMPANY_SERVICE', 'Synthetic Company Service', 'company')
                    RETURNING id
                    """
                )
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type_id, practice_type_code, status,
                    client_visible, start_date, expiry_date, payment_status,
                    quoted_price, service_type
                )
                VALUES ($1, $2, 'QA_COMPANY_SERVICE', 'active', TRUE,
                        TIMESTAMPTZ '2026-08-01 00:00:00+00',
                        TIMESTAMPTZ '2027-08-01 00:00:00+00',
                        'pending', 1250000, 'KITAS E33G')
                RETURNING id
                """,
                active_client_id,
                practice_type_id,
            )
            referral_id = await conn.fetchval(
                """
                INSERT INTO partner_referrals (
                    partner_id, practice_id, share_percent, referred_at, notes
                )
                VALUES ($1, $2, 100,
                        TIMESTAMPTZ '2026-07-01 00:00:00+00',
                        'Synthetic prod-like referral')
                RETURNING id
                """,
                partner_id,
                practice_id,
            )
            await conn.executemany(
                """
                INSERT INTO partner_commissions (
                    partner_id, referral_id, practice_id, entry_type,
                    base_amount_idr, commission_type_snapshot,
                    commission_value_snapshot, rule_source,
                    gross_amount_idr, withholding_category, withholding_rate,
                    withholding_amount_idr, net_amount_idr, status,
                    accrued_at, eligible_for_approval_at, paid_at, paid_via,
                    payment_reference, idempotency_key, created_at
                )
                VALUES (
                    $1, $2, $3, 'accrual', $4, 'percentage', 10,
                    'partner_default', $5, 'pph21', 0.1, $6, $7, $8,
                    $9, $10, $11, $12, $13, $14, $9
                )
                """,
                [
                    (
                        partner_id,
                        referral_id,
                        practice_id,
                        20_000_000,
                        2_000_000,
                        200_000,
                        1_800_000,
                        "paid",
                        datetime(2026, 7, 10, tzinfo=timezone.utc),
                        datetime(2026, 7, 15, tzinfo=timezone.utc),
                        datetime(2026, 7, 20, tzinfo=timezone.utc),
                        "synthetic_qa",
                        "QA-PARTNER-PAID-0001",
                        "synthetic-portal-partner-paid-0001",
                    ),
                    (
                        partner_id,
                        referral_id,
                        practice_id,
                        10_000_000,
                        1_000_000,
                        100_000,
                        900_000,
                        "accrued",
                        datetime(2026, 7, 25, tzinfo=timezone.utc),
                        datetime(2026, 8, 25, tzinfo=timezone.utc),
                        None,
                        None,
                        None,
                        "synthetic-portal-partner-accrued-0001",
                    ),
                ],
            )
            company_id = await conn.fetchval(
                """
                INSERT INTO companies (
                    company_name, company_type, status, registered_address,
                    company_email, akta_pendirian_no, akta_pendirian_date,
                    sk_menhumkam_no, custom_fields
                )
                VALUES ($1, 'PT PMA', 'active', 'Synthetic Company Address',
                        'company@example.com', 'SYNTHETIC-AKTA', DATE '2026-01-15',
                        'SYNTHETIC-SK',
                        '{"company_status":"ACTIVE","investment_type":"PMA","authorized_capital":1000000}'::jsonb)
                RETURNING id
                """,
                _SYNTHETIC_COMPANY_NAME,
            )
            await conn.execute(
                """
                INSERT INTO client_company_links (
                    client_id, company_id, role, is_primary,
                    ownership_percentage, status
                )
                VALUES ($1, $2, 'director', TRUE, 100, 'active')
                """,
                active_client_id,
                company_id,
            )
            await conn.execute(
                """
                INSERT INTO lkpm_client_config (
                    client_id, company_id, company_name, npwp, nib, kbli_codes
                )
                VALUES ($1, $2, $3, 'SYNTHETIC-NPWP', 'SYNTHETIC-NIB', ARRAY['56101'])
                """,
                active_client_id,
                company_id,
                _SYNTHETIC_COMPANY_NAME,
            )
            await conn.execute(
                """
                INSERT INTO lkpm_reports (
                    client_id, company_id, quarter, year, status,
                    realized_working_capital, validation_status,
                    client_approved, oss_submitted, updated_at
                )
                VALUES ($1, $2, 'Q2', 2026, 'validated', 1000000000,
                        'passed', FALSE, FALSE,
                        TIMESTAMPTZ '2026-07-01 00:00:00+00')
                """,
                active_client_id,
                company_id,
            )
            submitted_lkpm_report_id = await conn.fetchval(
                """
                INSERT INTO lkpm_reports (
                    client_id, company_id, quarter, year, status,
                    realized_working_capital, validation_status,
                    client_approved, oss_submitted, oss_receipt_number,
                    updated_at
                )
                VALUES ($1, $2, 'Q1', 2026, 'submitted', 750000000,
                        'passed', TRUE, TRUE, $3,
                        TIMESTAMPTZ '2026-04-10 00:00:00+00')
                RETURNING id
                """,
                active_client_id,
                company_id,
                _SYNTHETIC_LKPM_RECEIPT_NUMBER,
            )
            await conn.execute(
                """
                INSERT INTO lkpm_receipts (
                    lkpm_report_id, nomor_laporan, nomor_kegiatan_usaha,
                    kbli_code, kegiatan_usaha_desc, stage, oss_status,
                    tanggal_diterima, nama_perusahaan_oss, file_drive_id,
                    file_name, source
                )
                VALUES ($1, $2, 'SYNTHETIC-NKU-1', '56101',
                        'Synthetic QA business activity', 'PRODUKSI',
                        'Disetujui', DATE '2026-04-10', $3,
                        'synthetic_lkpm_receipt_fixture_0001',
                        'synthetic-lkpm-q1-2026.pdf', 'synthetic_qa')
                """,
                submitted_lkpm_report_id,
                _SYNTHETIC_LKPM_RECEIPT_NUMBER,
                _SYNTHETIC_COMPANY_NAME,
            )
            await conn.executemany(
                """
                INSERT INTO client_family_members (
                    client_id, full_name, relationship, date_of_birth,
                    nationality
                )
                VALUES ($1, $2, $3, $4, 'Synthetic')
                """,
                [
                    (active_client_id, _SYNTHETIC_ADULT_NAME, "spouse", date(1990, 1, 1)),
                    (active_client_id, _SYNTHETIC_MINOR_NAME, "child", date(2018, 1, 1)),
                ],
            )
            await conn.execute(
                """
                INSERT INTO invoices (
                    client_id, practice_id, invoice_number, amount_idr,
                    invoice_source, drive_file_id, email_sent_to_client,
                    generated_at, created_at
                )
                VALUES ($1, $2, $3, 1250000, 'synthetic_qa', $4, FALSE,
                        TIMESTAMPTZ '2026-08-01 00:00:00+00',
                        TIMESTAMPTZ '2026-08-01 00:00:00+00')
                """,
                active_client_id,
                practice_id,
                _SYNTHETIC_INVOICE_NUMBER,
                invoice_file_id,
            )
            await conn.execute(
                """
                INSERT INTO documents (
                    client_id, document_type, file_name, status, client_visible,
                    file_size_kb, mime_type, document_purpose
                )
                VALUES ($1, 'qa_boundary', $2, 'verified', TRUE, 1,
                        'application/pdf', 'Synthetic tenant-isolation sentinel')
                """,
                active_client_id,
                document_fixture,
            )
            await conn.execute(
                """
                INSERT INTO portal_messages (
                    client_id, subject, direction, content, sent_by
                )
                VALUES ($1, 'Synthetic QA', 'team_to_client', $2, 'qa-team@example.com')
                """,
                active_client_id,
                _SYNTHETIC_TEAM_MESSAGE,
            )
            await conn.execute(
                """
                INSERT INTO portal_notifications (
                    client_id, type, title, body, data
                )
                VALUES ($1, 'qa_boundary', $2,
                        'Synthetic tenant-isolation notification',
                        '{"source":"portal_prodlike"}'::jsonb)
                """,
                active_client_id,
                _SYNTHETIC_NOTIFICATION_TITLE,
            )
    finally:
        await conn.close()

    logger.info(
        "Synthetic portal QA tenants and isolation sentinel ready in disposable loopback database",
    )


def main() -> None:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())


if __name__ == "__main__":
    main()
