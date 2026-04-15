"""
LKPM Core Service — deterministic business logic for LKPM reports.

No AI here — pure arithmetic, DB queries, and calendar math.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.app.models.lkpm import (
    DataSource,
    EmploymentData,
    InvestmentRealization,
    LKPMBatchItem,
    LKPMClientConfig,
    LKPMClientSubmission,
    LKPMDeadline,
    LKPMDraft,
    LKPMReadyPack,
    LKPMStatus,
    LKPMValidationResult,
)
from backend.services.compliance.lkpm_data_collector import LKPMDataCollector
from backend.services.compliance.lkpm_validator import LKPMValidator

logger = logging.getLogger(__name__)

# LKPM quarterly deadlines (PerBKPM 5/2025 — extended from 10th to 15th)
# Q1 (Jan-Mar) → due April 15
# Q2 (Apr-Jun) → due July 15
# Q3 (Jul-Sep) → due October 15
# Q4 (Oct-Dec) → due January 15 (next year)
QUARTER_DEADLINES = {
    "Q1": (4, 15),  # April 15
    "Q2": (7, 15),  # July 15
    "Q3": (10, 15),  # October 15
    "Q4": (1, 15),  # January 15 next year
}


class LKPMService:
    """Core LKPM business logic — deterministic calculations only."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.validator = LKPMValidator(db_pool)
        self.data_collector = LKPMDataCollector(db_pool)

    # ------------------------------------------------------------------
    # Client Config
    # ------------------------------------------------------------------

    async def get_client_config(self, client_id: int) -> LKPMClientConfig | None:
        """Get LKPM config for a client."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM lkpm_client_config WHERE client_id = $1",
                client_id,
            )
        if not row:
            return None

        return LKPMClientConfig(
            client_id=row["client_id"],
            company_id=row.get("company_id"),
            company_name=row["company_name"],
            npwp=row["npwp"],
            nib=row["nib"],
            kbli_codes=list(row["kbli_codes"] or []),
            planned=InvestmentRealization(
                equipment_domestic=row["planned_equipment_domestic"],
                equipment_import=row["planned_equipment_import"],
                building_domestic=row["planned_building_domestic"],
                building_import=row["planned_building_import"],
                vehicle_domestic=row["planned_vehicle_domestic"],
                vehicle_import=row["planned_vehicle_import"],
                land=row["planned_land"],
                working_capital=row["planned_working_capital"],
                other=row["planned_other"],
            ),
            planned_tki=row["planned_tki"],
            planned_tka=row["planned_tka"],
            jurnal_api_key=row["jurnal_api_key"],
            jurnal_company_id=row["jurnal_company_id"],
        )

    async def save_client_config(self, config: LKPMClientConfig) -> int:
        """Upsert client LKPM configuration."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO lkpm_client_config (
                    client_id, company_id, company_name, npwp, nib, kbli_codes,
                    planned_equipment_domestic, planned_equipment_import,
                    planned_building_domestic, planned_building_import,
                    planned_vehicle_domestic, planned_vehicle_import,
                    planned_land, planned_working_capital, planned_other,
                    planned_tki, planned_tka,
                    jurnal_api_key, jurnal_company_id,
                    updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6,
                    $7, $8, $9, $10, $11, $12,
                    $13, $14, $15,
                    $16, $17, $18, $19, NOW()
                )
                ON CONFLICT (client_id, company_id) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    npwp = EXCLUDED.npwp,
                    nib = EXCLUDED.nib,
                    kbli_codes = EXCLUDED.kbli_codes,
                    planned_equipment_domestic = EXCLUDED.planned_equipment_domestic,
                    planned_equipment_import = EXCLUDED.planned_equipment_import,
                    planned_building_domestic = EXCLUDED.planned_building_domestic,
                    planned_building_import = EXCLUDED.planned_building_import,
                    planned_vehicle_domestic = EXCLUDED.planned_vehicle_domestic,
                    planned_vehicle_import = EXCLUDED.planned_vehicle_import,
                    planned_land = EXCLUDED.planned_land,
                    planned_working_capital = EXCLUDED.planned_working_capital,
                    planned_other = EXCLUDED.planned_other,
                    planned_tki = EXCLUDED.planned_tki,
                    planned_tka = EXCLUDED.planned_tka,
                    jurnal_api_key = EXCLUDED.jurnal_api_key,
                    jurnal_company_id = EXCLUDED.jurnal_company_id,
                    updated_at = NOW()
                RETURNING id
                """,
                config.client_id,
                config.company_id,
                config.company_name,
                config.npwp,
                config.nib,
                config.kbli_codes,
                config.planned.equipment_domestic,
                config.planned.equipment_import,
                config.planned.building_domestic,
                config.planned.building_import,
                config.planned.vehicle_domestic,
                config.planned.vehicle_import,
                config.planned.land,
                config.planned.working_capital,
                config.planned.other,
                config.planned_tki,
                config.planned_tka,
                config.jurnal_api_key,
                config.jurnal_company_id,
            )
        return row["id"]

    # ------------------------------------------------------------------
    # Draft Generation
    # ------------------------------------------------------------------

    async def generate_draft(self, client_id: int, quarter: str, year: int) -> LKPMDraft:
        """
        Generate an LKPM draft for a client/quarter.

        Loads previous quarters to calculate cumulative realization.
        """
        logger.info(f"Generating LKPM draft: client={client_id}, {quarter} {year}")

        # Check if draft already exists
        existing = await self._load_draft(client_id, quarter, year)
        if existing:
            logger.info(f"Draft already exists: id={existing.id}")
            return existing

        # Load client config
        config = await self.get_client_config(client_id)
        if not config:
            raise ValueError(f"No LKPM config found for client {client_id}")

        # Calculate cumulative from previous reports
        cumulative = await self._calculate_cumulative(client_id, quarter, year)

        draft = LKPMDraft(
            client_id=client_id,
            quarter=quarter,
            year=year,
            cumulative=cumulative,
        )

        # Save draft
        draft_id = await self._save_draft(draft)
        draft.id = draft_id
        logger.info(f"Draft created: id={draft_id}")
        return draft

    async def _ensure_client_config(self, client_id: int) -> None:
        """Auto-create lkpm_client_config from CRM company data if missing."""
        async with self.db_pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM lkpm_client_config WHERE client_id = $1", client_id,
            )
            if existing:
                return

            # Resolve company from CRM
            row = await conn.fetchrow(
                """
                SELECT c.id AS company_id, c.company_name, c.npwp_company, c.nib, c.kbli_code
                FROM client_company_links ccl
                JOIN companies c ON c.id = ccl.company_id
                WHERE ccl.client_id = $1 AND ccl.status = 'active'
                ORDER BY ccl.is_primary DESC NULLS LAST
                LIMIT 1
            """,
                client_id,
            )

            if row:
                kbli = row["kbli_code"] or ""
                await conn.execute(
                    """
                    INSERT INTO lkpm_client_config (client_id, company_id, company_name, npwp, nib, kbli_codes)
                    VALUES ($1, $2, $3, $4, $5, ARRAY[$6])
                    ON CONFLICT (client_id, company_id) DO NOTHING
                """,
                    client_id,
                    row.get("company_id"),
                    row["company_name"],
                    row["npwp_company"],
                    row["nib"],
                    kbli,
                )
                logger.info(
                    f"Auto-created lkpm_client_config for client {client_id}: {row['company_name']}",
                )
            else:
                logger.warning(
                    f"No active company found for client {client_id}, cannot auto-create config",
                )

    async def get_history_for_portal_client(self, client_id: int) -> list[LKPMBatchItem]:
        """
        Get LKPM reports visible to a portal client (all companies where the
        user is a shareholder/director/commissioner, any ownership %).

        Cascade is via `lkpm_reports.company_id`, NOT via `r.client_id`.
        `r.client_id` is set by Lori's import convention (client_id=company_id)
        and may also hold a real clients.id for individually-created reports —
        so it's an unreliable join key. `company_id` is the authoritative FK.
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT r.*, COALESCE(c.company_name, co.company_name) AS company_name
                FROM lkpm_reports r
                LEFT JOIN lkpm_client_config c ON c.client_id = r.client_id
                    AND COALESCE(r.company_id, 0) = COALESCE(c.company_id, 0)
                LEFT JOIN companies co ON co.id = r.company_id
                WHERE r.company_id IN (
                    SELECT DISTINCT ccl.company_id
                    FROM client_company_links ccl
                    WHERE ccl.client_id = $1
                      AND ccl.status = 'active'
                )
                ORDER BY r.year DESC, r.quarter DESC
                """,
                client_id,
            )
        return [self._row_to_batch_item(row) for row in rows]

    # ------------------------------------------------------------------
    # OSS Tanda Terima (receipts) — migration 108
    # ------------------------------------------------------------------

    async def get_receipts_for_report(self, lkpm_report_id: int) -> list[dict[str, Any]]:
        """Return all OSS tanda terima rows attached to a single lkpm_reports row."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, lkpm_report_id,
                       nomor_laporan, nomor_kegiatan_usaha,
                       kbli_code, kegiatan_usaha_desc,
                       stage, oss_status,
                       lokasi, tanggal_diterima,
                       nama_perusahaan_oss,
                       file_drive_id, file_drive_url, file_name,
                       source, created_at, updated_at
                FROM lkpm_receipts
                WHERE lkpm_report_id = $1
                ORDER BY tanggal_diterima DESC NULLS LAST, id
                """,
                lkpm_report_id,
            )
        return [dict(r) for r in rows]

    async def get_receipts_for_portal_client(
        self, client_id: int,
    ) -> list[dict[str, Any]]:
        """
        Portal-facing: every OSS receipt of every company where the client is a
        shareholder/director/commissioner.

        Cascade is via `lkpm_reports.company_id`, not `r.client_id`. See
        `get_history_for_portal_client` docstring for the reasoning.
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT re.id, re.lkpm_report_id,
                       re.nomor_laporan, re.nomor_kegiatan_usaha,
                       re.kbli_code, re.kegiatan_usaha_desc,
                       re.stage, re.oss_status,
                       re.lokasi, re.tanggal_diterima,
                       re.nama_perusahaan_oss,
                       re.file_drive_id, re.file_drive_url, re.file_name,
                       r.quarter, r.year, r.client_id,
                       r.company_id,
                       COALESCE(cfg.company_name, co.company_name) AS company_name
                FROM lkpm_receipts re
                JOIN lkpm_reports r ON r.id = re.lkpm_report_id
                LEFT JOIN lkpm_client_config cfg ON cfg.client_id = r.client_id
                LEFT JOIN companies co ON co.id = r.company_id
                WHERE r.company_id IN (
                    SELECT DISTINCT ccl.company_id
                    FROM client_company_links ccl
                    WHERE ccl.client_id = $1
                      AND ccl.status = 'active'
                )
                ORDER BY r.year DESC, r.quarter DESC,
                         re.tanggal_diterima DESC NULLS LAST, re.id
                """,
                client_id,
            )
        return [dict(r) for r in rows]

    async def submit_form_data(self, submission: LKPMClientSubmission) -> LKPMDraft:
        """Process client form submission into a draft."""
        logger.info(
            f"Processing form submission: client={submission.client_id}, "
            f"{submission.quarter} {submission.year}",
        )

        # Auto-create config from CRM if missing
        await self._ensure_client_config(submission.client_id)

        draft = self.data_collector.collect_from_form(submission)

        # Calculate cumulative
        cumulative = await self._calculate_cumulative(
            submission.client_id, submission.quarter, submission.year,
        )
        draft.cumulative = InvestmentRealization(
            equipment_domestic=cumulative.equipment_domestic + draft.realized.equipment_domestic,
            equipment_import=cumulative.equipment_import + draft.realized.equipment_import,
            building_domestic=cumulative.building_domestic + draft.realized.building_domestic,
            building_import=cumulative.building_import + draft.realized.building_import,
            vehicle_domestic=cumulative.vehicle_domestic + draft.realized.vehicle_domestic,
            vehicle_import=cumulative.vehicle_import + draft.realized.vehicle_import,
            land=cumulative.land + draft.realized.land,
            working_capital=cumulative.working_capital + draft.realized.working_capital,
            other=cumulative.other + draft.realized.other,
        )

        draft_id = await self._save_draft(draft)
        draft.id = draft_id
        return draft

    async def sync_jurnal(self, client_id: int, quarter: str, year: int) -> LKPMDraft:
        """Pull data from Jurnal.id and create/update draft."""
        config = await self.get_client_config(client_id)
        if not config:
            raise ValueError(f"No LKPM config for client {client_id}")
        if not config.jurnal_api_key:
            raise ValueError(f"No Jurnal API key configured for client {client_id}")

        draft = await self.data_collector.collect_from_jurnal(
            client_id=client_id,
            quarter=quarter,
            year=year,
            api_key=config.jurnal_api_key,
            company_id=config.jurnal_company_id,
        )

        # Calculate cumulative
        cumulative = await self._calculate_cumulative(client_id, quarter, year)
        draft.cumulative = InvestmentRealization(
            equipment_domestic=cumulative.equipment_domestic + draft.realized.equipment_domestic,
            equipment_import=cumulative.equipment_import + draft.realized.equipment_import,
            building_domestic=cumulative.building_domestic + draft.realized.building_domestic,
            building_import=cumulative.building_import + draft.realized.building_import,
            vehicle_domestic=cumulative.vehicle_domestic + draft.realized.vehicle_domestic,
            vehicle_import=cumulative.vehicle_import + draft.realized.vehicle_import,
            land=cumulative.land + draft.realized.land,
            working_capital=cumulative.working_capital + draft.realized.working_capital,
            other=cumulative.other + draft.realized.other,
        )

        draft_id = await self._save_draft(draft)
        draft.id = draft_id
        return draft

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate_draft(self, draft_id: int) -> LKPMValidationResult:
        """Validate a draft and update its status."""
        draft = await self._load_draft_by_id(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        config = await self.get_client_config(draft.client_id)
        if not config:
            raise ValueError(f"No config for client {draft.client_id}")

        result = await self.validator.validate(draft, config)

        # Update draft with validation result
        async with self.db_pool.acquire() as conn:
            import json

            await conn.execute(
                """
                UPDATE lkpm_reports SET
                    validation_status = $1,
                    validation_alerts = $2::jsonb,
                    validated_at = NOW(),
                    status = $3,
                    updated_at = NOW()
                WHERE id = $4
                """,
                "valid" if result.is_valid else "invalid",
                json.dumps([a.model_dump() for a in result.alerts]),
                LKPMStatus.VALIDATED.value if result.is_valid else LKPMStatus.DRAFT.value,
                draft_id,
            )

        logger.info(
            f"Draft {draft_id} validated: valid={result.is_valid}, "
            f"red={result.red_count}, yellow={result.yellow_count}",
        )
        return result

    # ------------------------------------------------------------------
    # Ready Pack
    # ------------------------------------------------------------------

    async def get_ready_pack(self, draft_id: int) -> LKPMReadyPack:
        """Generate a Ready Pack for copy-paste into OSS."""
        draft = await self._load_draft_by_id(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        config = await self.get_client_config(draft.client_id)
        if not config:
            raise ValueError(f"No config for client {draft.client_id}")

        # Calculate realization percentage
        planned_total = config.planned.grand_total
        cumulative_total = draft.cumulative.grand_total
        pct = (cumulative_total / planned_total * 100) if planned_total > 0 else 0.0

        return LKPMReadyPack(
            draft_id=draft_id,
            client_id=draft.client_id,
            company_name=config.company_name,
            npwp=config.npwp,
            nib=config.nib,
            quarter=draft.quarter,
            year=draft.year,
            kbli_codes=config.kbli_codes,
            realized=draft.realized,
            realized_total=draft.realized.grand_total,
            cumulative=draft.cumulative,
            cumulative_total=cumulative_total,
            plan=config.planned,
            realization_percentage=round(pct, 2),
            employment=draft.employment,
            quarterly_revenue=draft.quarterly_revenue,
            annual_revenue=draft.annual_revenue,
            narrative_obstacles=draft.narrative_obstacles,
            narrative_plans=draft.narrative_plans,
            validation_summary=draft.validation,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Submission Tracking
    # ------------------------------------------------------------------

    async def approve_draft(self, draft_id: int) -> dict[str, Any]:
        """Mark draft as approved by client."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE lkpm_reports SET
                    client_approved = TRUE,
                    client_approved_at = NOW(),
                    status = $1,
                    updated_at = NOW()
                WHERE id = $2
                """,
                LKPMStatus.APPROVED.value,
                draft_id,
            )
        logger.info(f"Draft {draft_id} approved by client")
        return {"success": True, "draft_id": draft_id, "status": "approved"}

    async def mark_submitted(self, draft_id: int, submitted_by: str) -> dict[str, Any]:
        """Mark LKPM as submitted to OSS."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE lkpm_reports SET
                    oss_submitted = TRUE,
                    oss_submitted_at = NOW(),
                    oss_submitted_by = $1,
                    status = $2,
                    updated_at = NOW()
                WHERE id = $3
                """,
                submitted_by,
                LKPMStatus.SUBMITTED.value,
                draft_id,
            )
        logger.info(f"Draft {draft_id} marked as submitted by {submitted_by}")
        return {"success": True, "draft_id": draft_id, "status": "submitted"}

    async def upload_receipt(
        self,
        draft_id: int,
        receipt_number: str,
        receipt_file_url: str | None = None,
    ) -> dict[str, Any]:
        """Store OSS receipt information."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE lkpm_reports SET
                    oss_receipt_number = $1,
                    oss_receipt_file_url = $2,
                    updated_at = NOW()
                WHERE id = $3
                """,
                receipt_number,
                receipt_file_url,
                draft_id,
            )
        logger.info(f"Receipt uploaded for draft {draft_id}: {receipt_number}")
        return {"success": True, "draft_id": draft_id, "receipt_number": receipt_number}

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_draft(self, client_id: int, quarter: str, year: int) -> LKPMDraft | None:
        """Get a specific draft."""
        return await self._load_draft(client_id, quarter, year)

    async def get_history(self, client_id: int) -> list[LKPMBatchItem]:
        """
        Get LKPM report history visible to a client (workspace view).

        Cascade via `r.company_id` — shareholders of a PT see all reports of
        that PT even when `lkpm_reports.client_id` holds the primary contact's
        id (or the company_id per Lori's import convention). See SCAR in
        `.claude/rules/cicatrix-scars.md` for the r.client_id bug fixed on
        2026-04-15.
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT r.*,
                       COALESCE(c.company_name, co.company_name) AS company_name
                FROM lkpm_reports r
                LEFT JOIN lkpm_client_config c ON c.client_id = r.client_id
                    AND COALESCE(r.company_id, 0) = COALESCE(c.company_id, 0)
                LEFT JOIN companies co ON co.id = r.company_id
                WHERE r.company_id IN (
                    SELECT DISTINCT ccl.company_id
                    FROM client_company_links ccl
                    WHERE ccl.client_id = $1 AND ccl.status = 'active'
                )
                ORDER BY r.year DESC, r.quarter DESC
                """,
                client_id,
            )
        return [self._row_to_batch_item(row) for row in rows]

    async def get_receipts_for_client(self, client_id: int) -> list[dict[str, Any]]:
        """
        Workspace-side: OSS receipts of every company where the given client
        is a shareholder/director/commissioner.

        Same cascade as `get_receipts_for_portal_client`, but keyed by the
        client_id passed in (instead of the authenticated portal user). Used
        by the TaxTab in kita.balizero.com.
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT re.id, re.lkpm_report_id,
                       re.nomor_laporan, re.nomor_kegiatan_usaha,
                       re.kbli_code, re.kegiatan_usaha_desc,
                       re.stage, re.oss_status,
                       re.lokasi, re.tanggal_diterima,
                       re.nama_perusahaan_oss,
                       re.file_drive_id, re.file_drive_url, re.file_name,
                       r.quarter, r.year, r.client_id,
                       r.company_id,
                       COALESCE(cfg.company_name, co.company_name) AS company_name
                FROM lkpm_receipts re
                JOIN lkpm_reports r ON r.id = re.lkpm_report_id
                LEFT JOIN lkpm_client_config cfg ON cfg.client_id = r.client_id
                LEFT JOIN companies co ON co.id = r.company_id
                WHERE r.company_id IN (
                    SELECT DISTINCT ccl.company_id
                    FROM client_company_links ccl
                    WHERE ccl.client_id = $1 AND ccl.status = 'active'
                )
                ORDER BY r.year DESC, r.quarter DESC,
                         re.tanggal_diterima DESC NULLS LAST, re.id
                """,
                client_id,
            )
        return [dict(r) for r in rows]

    async def get_batch(self, quarter: str, year: int) -> list[LKPMBatchItem]:
        """Get all LKPM reports for a quarter (team batch view)."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.*, c.company_name
                FROM lkpm_reports r
                JOIN lkpm_client_config c ON r.client_id = c.client_id
                    AND COALESCE(r.company_id, 0) = COALESCE(c.company_id, 0)
                WHERE r.quarter = $1 AND r.year = $2
                ORDER BY c.company_name
                """,
                quarter,
                year,
            )
        return [self._row_to_batch_item(row) for row in rows]

    async def get_alerts(self) -> list[dict[str, Any]]:
        """Get active validation alerts across all clients."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.id, r.client_id, r.company_id, c.company_name, r.quarter, r.year,
                       r.validation_alerts, r.status
                FROM lkpm_reports r
                JOIN lkpm_client_config c ON r.client_id = c.client_id
                    AND COALESCE(r.company_id, 0) = COALESCE(c.company_id, 0)
                WHERE r.validation_status = 'invalid'
                  AND r.status NOT IN ('submitted', 'archived')
                ORDER BY r.year DESC, r.quarter DESC
                """,
            )

        alerts = []
        for row in rows:
            import json

            validation_alerts = row["validation_alerts"]
            if isinstance(validation_alerts, str):
                validation_alerts = json.loads(validation_alerts)
            red_count = sum(1 for a in validation_alerts if a.get("severity") == "red")
            alerts.append(
                {
                    "draft_id": row["id"],
                    "client_id": row["client_id"],
                    "company_name": row["company_name"],
                    "quarter": row["quarter"],
                    "year": row["year"],
                    "red_alerts": red_count,
                    "total_alerts": len(validation_alerts),
                    "status": row["status"],
                },
            )
        return alerts

    def get_deadlines(self, days_ahead: int = 30) -> list[LKPMDeadline]:
        """Calculate upcoming LKPM deadlines."""
        now = datetime.now(timezone.utc)
        deadlines: list[LKPMDeadline] = []

        for quarter, (month, day) in QUARTER_DEADLINES.items():
            # Current year deadline
            year = now.year
            if quarter == "Q4":
                year += 1  # Q4 deadline is in January next year

            deadline_dt = datetime(year, month, day, tzinfo=timezone.utc)
            days_remaining = (deadline_dt - now).days

            if -30 <= days_remaining <= days_ahead:
                deadlines.append(
                    LKPMDeadline(
                        quarter=quarter,
                        year=year if quarter != "Q4" else year - 1,
                        deadline=deadline_dt,
                        days_remaining=days_remaining,
                        is_overdue=days_remaining < 0,
                    ),
                )

        return sorted(deadlines, key=lambda d: d.days_remaining)

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    async def _load_draft(self, client_id: int, quarter: str, year: int) -> LKPMDraft | None:
        """Load a draft from DB."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM lkpm_reports
                WHERE client_id = $1 AND quarter = $2 AND year = $3
                """,
                client_id,
                quarter,
                year,
            )
        if not row:
            return None
        return self._row_to_draft(row)

    async def _load_draft_by_id(self, draft_id: int) -> LKPMDraft | None:
        """Load a draft by its ID."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM lkpm_reports WHERE id = $1",
                draft_id,
            )
        if not row:
            return None
        return self._row_to_draft(row)

    async def _save_draft(self, draft: LKPMDraft) -> int:
        """Insert or update a draft."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO lkpm_reports (
                    client_id, company_id, quarter, year, status,
                    realized_equipment_domestic, realized_equipment_import,
                    realized_building_domestic, realized_building_import,
                    realized_vehicle_domestic, realized_vehicle_import,
                    realized_land, realized_working_capital, realized_other,
                    cumulative_equipment_domestic, cumulative_equipment_import,
                    cumulative_building_domestic, cumulative_building_import,
                    cumulative_vehicle_domestic, cumulative_vehicle_import,
                    cumulative_land, cumulative_working_capital, cumulative_other,
                    current_tki, current_tka,
                    quarterly_revenue, annual_revenue,
                    narrative_obstacles, narrative_plans,
                    data_source, has_ai_categorized_items, ai_categorized_count,
                    updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9, $10, $11, $12, $13, $14,
                    $15, $16, $17, $18, $19, $20, $21, $22, $23,
                    $24, $25,
                    $26, $27,
                    $28, $29,
                    $30, $31, $32,
                    NOW()
                )
                ON CONFLICT (client_id, company_id, quarter, year) DO UPDATE SET
                    status = EXCLUDED.status,
                    realized_equipment_domestic = EXCLUDED.realized_equipment_domestic,
                    realized_equipment_import = EXCLUDED.realized_equipment_import,
                    realized_building_domestic = EXCLUDED.realized_building_domestic,
                    realized_building_import = EXCLUDED.realized_building_import,
                    realized_vehicle_domestic = EXCLUDED.realized_vehicle_domestic,
                    realized_vehicle_import = EXCLUDED.realized_vehicle_import,
                    realized_land = EXCLUDED.realized_land,
                    realized_working_capital = EXCLUDED.realized_working_capital,
                    realized_other = EXCLUDED.realized_other,
                    cumulative_equipment_domestic = EXCLUDED.cumulative_equipment_domestic,
                    cumulative_equipment_import = EXCLUDED.cumulative_equipment_import,
                    cumulative_building_domestic = EXCLUDED.cumulative_building_domestic,
                    cumulative_building_import = EXCLUDED.cumulative_building_import,
                    cumulative_vehicle_domestic = EXCLUDED.cumulative_vehicle_domestic,
                    cumulative_vehicle_import = EXCLUDED.cumulative_vehicle_import,
                    cumulative_land = EXCLUDED.cumulative_land,
                    cumulative_working_capital = EXCLUDED.cumulative_working_capital,
                    cumulative_other = EXCLUDED.cumulative_other,
                    current_tki = EXCLUDED.current_tki,
                    current_tka = EXCLUDED.current_tka,
                    quarterly_revenue = EXCLUDED.quarterly_revenue,
                    annual_revenue = EXCLUDED.annual_revenue,
                    narrative_obstacles = EXCLUDED.narrative_obstacles,
                    narrative_plans = EXCLUDED.narrative_plans,
                    data_source = EXCLUDED.data_source,
                    has_ai_categorized_items = EXCLUDED.has_ai_categorized_items,
                    ai_categorized_count = EXCLUDED.ai_categorized_count,
                    updated_at = NOW()
                RETURNING id
                """,
                draft.client_id,
                draft.company_id,
                draft.quarter,
                draft.year,
                draft.status.value,
                draft.realized.equipment_domestic,
                draft.realized.equipment_import,
                draft.realized.building_domestic,
                draft.realized.building_import,
                draft.realized.vehicle_domestic,
                draft.realized.vehicle_import,
                draft.realized.land,
                draft.realized.working_capital,
                draft.realized.other,
                draft.cumulative.equipment_domestic,
                draft.cumulative.equipment_import,
                draft.cumulative.building_domestic,
                draft.cumulative.building_import,
                draft.cumulative.vehicle_domestic,
                draft.cumulative.vehicle_import,
                draft.cumulative.land,
                draft.cumulative.working_capital,
                draft.cumulative.other,
                draft.employment.tki,
                draft.employment.tka,
                draft.quarterly_revenue,
                draft.annual_revenue,
                draft.narrative_obstacles,
                draft.narrative_plans,
                draft.data_source.value,
                draft.has_ai_categorized_items,
                draft.ai_categorized_count,
            )
        return row["id"]

    async def _calculate_cumulative(
        self, client_id: int, quarter: str, year: int,
    ) -> InvestmentRealization:
        """Sum all previous quarters' realization for cumulative total."""
        # Quarter ordering for comparison

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    COALESCE(SUM(realized_equipment_domestic), 0) as eq_d,
                    COALESCE(SUM(realized_equipment_import), 0) as eq_i,
                    COALESCE(SUM(realized_building_domestic), 0) as bd_d,
                    COALESCE(SUM(realized_building_import), 0) as bd_i,
                    COALESCE(SUM(realized_vehicle_domestic), 0) as vh_d,
                    COALESCE(SUM(realized_vehicle_import), 0) as vh_i,
                    COALESCE(SUM(realized_land), 0) as land,
                    COALESCE(SUM(realized_working_capital), 0) as wc,
                    COALESCE(SUM(realized_other), 0) as other
                FROM lkpm_reports
                WHERE client_id = $1
                  AND (year < $2 OR (year = $2 AND quarter < $3))
                """,
                client_id,
                year,
                quarter,
            )

        if not rows or not rows[0]:
            return InvestmentRealization()

        r = rows[0]
        return InvestmentRealization(
            equipment_domestic=r["eq_d"],
            equipment_import=r["eq_i"],
            building_domestic=r["bd_d"],
            building_import=r["bd_i"],
            vehicle_domestic=r["vh_d"],
            vehicle_import=r["vh_i"],
            land=r["land"],
            working_capital=r["wc"],
            other=r["other"],
        )

    @staticmethod
    def _row_to_draft(row: Any) -> LKPMDraft:
        """Convert DB row to LKPMDraft."""
        import json

        validation = None
        if row["validation_alerts"] and row["validation_status"] != "pending":
            alerts_data = row["validation_alerts"]
            if isinstance(alerts_data, str):
                alerts_data = json.loads(alerts_data)
            from backend.app.models.lkpm import ValidationAlert

            validation = LKPMValidationResult(
                is_valid=row["validation_status"] == "valid",
                alerts=[ValidationAlert(**a) for a in alerts_data],
            )

        return LKPMDraft(
            id=row["id"],
            client_id=row["client_id"],
            company_id=row.get("company_id"),
            quarter=row["quarter"],
            year=row["year"],
            status=LKPMStatus(row["status"]),
            realized=InvestmentRealization(
                equipment_domestic=row["realized_equipment_domestic"],
                equipment_import=row["realized_equipment_import"],
                building_domestic=row["realized_building_domestic"],
                building_import=row["realized_building_import"],
                vehicle_domestic=row["realized_vehicle_domestic"],
                vehicle_import=row["realized_vehicle_import"],
                land=row["realized_land"],
                working_capital=row["realized_working_capital"],
                other=row["realized_other"],
            ),
            cumulative=InvestmentRealization(
                equipment_domestic=row["cumulative_equipment_domestic"],
                equipment_import=row["cumulative_equipment_import"],
                building_domestic=row["cumulative_building_domestic"],
                building_import=row["cumulative_building_import"],
                vehicle_domestic=row["cumulative_vehicle_domestic"],
                vehicle_import=row["cumulative_vehicle_import"],
                land=row["cumulative_land"],
                working_capital=row["cumulative_working_capital"],
                other=row["cumulative_other"],
            ),
            employment=EmploymentData(
                tki=row["current_tki"],
                tka=row["current_tka"],
            ),
            quarterly_revenue=row["quarterly_revenue"],
            annual_revenue=row["annual_revenue"],
            narrative_obstacles=row["narrative_obstacles"],
            narrative_plans=row["narrative_plans"],
            validation=validation,
            client_approved=row["client_approved"],
            client_approved_at=row["client_approved_at"],
            oss_submitted=row["oss_submitted"],
            oss_submitted_at=row["oss_submitted_at"],
            oss_receipt_number=row["oss_receipt_number"],
            data_source=DataSource(row["data_source"]),
            has_ai_categorized_items=row["has_ai_categorized_items"],
            ai_categorized_count=row["ai_categorized_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_batch_item(row: Any) -> LKPMBatchItem:
        """Convert DB row to LKPMBatchItem."""
        import json

        validation_alerts = row.get("validation_alerts", [])
        if isinstance(validation_alerts, str):
            validation_alerts = json.loads(validation_alerts)
        red_count = sum(1 for a in validation_alerts if a.get("severity") == "red")
        yellow_count = sum(1 for a in validation_alerts if a.get("severity") == "yellow")

        # Compute realized_total from individual columns
        realized_total = sum(
            [
                row.get("realized_equipment_domestic", 0) or 0,
                row.get("realized_equipment_import", 0) or 0,
                row.get("realized_building_domestic", 0) or 0,
                row.get("realized_building_import", 0) or 0,
                row.get("realized_vehicle_domestic", 0) or 0,
                row.get("realized_vehicle_import", 0) or 0,
                row.get("realized_land", 0) or 0,
                row.get("realized_working_capital", 0) or 0,
                row.get("realized_other", 0) or 0,
            ],
        )

        # Compute days_to_deadline
        quarter = row["quarter"]
        year = row["year"]
        if quarter in QUARTER_DEADLINES:
            month, day = QUARTER_DEADLINES[quarter]
            deadline_year = year + 1 if quarter == "Q4" else year
            deadline_dt = datetime(deadline_year, month, day, tzinfo=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            days_to_deadline = (deadline_dt.date() - now.date()).days
        else:
            days_to_deadline = None

        return LKPMBatchItem(
            id=row["id"],
            client_id=row["client_id"],
            company_id=row.get("company_id"),
            company_name=row["company_name"],
            quarter=row["quarter"],
            year=row["year"],
            status=LKPMStatus(row["status"]),
            validation_status=row.get("validation_status", "pending"),
            realized_total=realized_total,
            red_alerts=red_count,
            yellow_alerts=yellow_count,
            oss_submitted=row["oss_submitted"],
            oss_receipt_number=row.get("oss_receipt_number"),
            client_approved=row.get("client_approved", False),
            lkpm_assigned_to=row.get("lkpm_assigned_to"),
            days_to_deadline=days_to_deadline,
            updated_at=row["updated_at"],
        )
