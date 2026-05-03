"""
LKPM Data Collector — collects investment data from forms and Jurnal.id.

Transaction categorization is deterministic (Chart of Account → LKPM category).
AI is used ONLY as fallback for unmapped accounts, with explicit "da verificare" flag.
"""

import logging
from datetime import date
from typing import Any

import asyncpg

from backend.app.models.lkpm import (
    DataSource,
    EmploymentData,
    InvestmentRealization,
    LKPMClientSubmission,
    LKPMDraft,
    TransactionCategorization,
)
from backend.services.integrations.jurnal_service import JurnalService

logger = logging.getLogger(__name__)

# Deterministic mapping: Jurnal Chart of Account category → LKPM investment category
# Keys are lowercase account category/name patterns from Jurnal.id
COA_TO_LKPM_MAPPING: dict[str, tuple[str, str]] = {
    # Equipment
    "peralatan": ("equipment", "domestic"),
    "mesin": ("equipment", "domestic"),
    "equipment": ("equipment", "domestic"),
    "machinery": ("equipment", "domestic"),
    "komputer": ("equipment", "domestic"),
    "computer": ("equipment", "domestic"),
    "furnitur": ("equipment", "domestic"),
    "furniture": ("equipment", "domestic"),
    "inventaris": ("equipment", "domestic"),
    "perlengkapan kantor": ("equipment", "domestic"),
    "office equipment": ("equipment", "domestic"),
    # Equipment Import
    "import equipment": ("equipment", "import"),
    "peralatan impor": ("equipment", "import"),
    "mesin impor": ("equipment", "import"),
    # Building
    "bangunan": ("building", "domestic"),
    "building": ("building", "domestic"),
    "gedung": ("building", "domestic"),
    "renovasi": ("building", "domestic"),
    "renovation": ("building", "domestic"),
    "konstruksi": ("building", "domestic"),
    "construction": ("building", "domestic"),
    # Vehicle
    "kendaraan": ("vehicle", "domestic"),
    "vehicle": ("vehicle", "domestic"),
    "mobil": ("vehicle", "domestic"),
    "motor": ("vehicle", "domestic"),
    "transportasi": ("vehicle", "domestic"),
    # Land
    "tanah": ("land", "domestic"),
    "land": ("land", "domestic"),
    "hak pakai": ("land", "domestic"),
    "sewa tanah": ("land", "domestic"),
    # Working Capital
    "modal kerja": ("working_capital", "domestic"),
    "working capital": ("working_capital", "domestic"),
    "kas": ("working_capital", "domestic"),
    "bank": ("working_capital", "domestic"),
    "piutang": ("working_capital", "domestic"),
    "persediaan": ("working_capital", "domestic"),
    "inventory": ("working_capital", "domestic"),
}


class LKPMDataCollector:
    """Collects and categorizes LKPM investment data."""

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        jurnal_service: JurnalService | None = None,
    ) -> None:
        self.db_pool = db_pool
        self.jurnal_service = jurnal_service or JurnalService()

    def collect_from_form(self, submission: LKPMClientSubmission) -> LKPMDraft:
        """Convert client form submission into an LKPM draft."""
        logger.info(
            f"Collecting form data for client {submission.client_id}, "
            f"{submission.quarter} {submission.year}",
        )

        realized = InvestmentRealization(
            equipment_domestic=submission.equipment_domestic,
            equipment_import=submission.equipment_import,
            building_domestic=submission.building_domestic,
            building_import=submission.building_import,
            vehicle_domestic=submission.vehicle_domestic,
            vehicle_import=submission.vehicle_import,
            land=submission.land,
            working_capital=submission.working_capital,
            other=submission.other,
        )

        employment = EmploymentData(
            tki=submission.tki,
            tka=submission.tka,
        )

        return LKPMDraft(
            client_id=submission.client_id,
            quarter=submission.quarter,
            year=submission.year,
            realized=realized,
            employment=employment,
            quarterly_revenue=submission.quarterly_revenue,
            annual_revenue=submission.annual_revenue,
            narrative_obstacles=submission.narrative_obstacles,
            narrative_plans=submission.narrative_plans,
            data_source=DataSource.MANUAL,
        )

    async def collect_from_jurnal(
        self,
        client_id: int,
        quarter: str,
        year: int,
        api_key: str | None = None,
        company_id: str | None = None,
    ) -> LKPMDraft:
        """Pull data from Jurnal.id and categorize into LKPM format."""
        logger.info(f"Collecting Jurnal data for client {client_id}, {quarter} {year}")

        start_date, end_date = self._quarter_dates(quarter, year)

        # Fetch journal entries
        entries = await self.jurnal_service.get_all_journal_entries(
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
            company_id=company_id,
        )

        # Categorize transactions
        categorized = self.categorize_transactions(entries)

        # Aggregate into investment realization
        realized = self._aggregate_categorized(categorized)
        ai_count = sum(1 for c in categorized if c.ai_needs_review)

        # Collect employment data from CRM
        employment = await self.collect_employment(client_id)

        return LKPMDraft(
            client_id=client_id,
            quarter=quarter,
            year=year,
            realized=realized,
            employment=employment,
            data_source=DataSource.JURNAL,
            has_ai_categorized_items=ai_count > 0,
            ai_categorized_count=ai_count,
        )

    def categorize_transactions(
        self, entries: list[dict[str, Any]],
    ) -> list[TransactionCategorization]:
        """
        Map journal entries to LKPM categories deterministically.

        Uses COA_TO_LKPM_MAPPING for known account types.
        Unknown accounts are flagged as "ai_needs_review" for manual verification.
        """
        categorized: list[TransactionCategorization] = []

        for entry in entries:
            entry_id = str(entry.get("id", "unknown"))
            description = entry.get("description", entry.get("memo", ""))
            amount = int(entry.get("debit", 0) or 0) - int(entry.get("credit", 0) or 0)
            account_code = str(entry.get("account_code", entry.get("account_number", "")))
            account_name = str(entry.get("account_name", entry.get("account", "")))

            # Skip zero-amount entries
            if amount == 0:
                continue

            # Deterministic mapping: try account name patterns
            category, sub_category, is_deterministic = self._map_account(account_name, description)

            categorized.append(
                TransactionCategorization(
                    journal_entry_id=entry_id,
                    description=description[:200] if description else "",
                    amount=abs(amount),
                    category=category,
                    sub_category=sub_category,
                    confidence="deterministic" if is_deterministic else "ai_suggested",
                    ai_needs_review=not is_deterministic,
                    original_account_code=account_code,
                    original_account_name=account_name[:100] if account_name else None,
                ),
            )

        logger.info(
            f"Categorized {len(categorized)} transactions: "
            f"{sum(1 for c in categorized if c.confidence == 'deterministic')} deterministic, "
            f"{sum(1 for c in categorized if c.ai_needs_review)} need review",
        )
        return categorized

    def _map_account(self, account_name: str, description: str) -> tuple[str, str, bool]:
        """
        Map account name to LKPM category using deterministic rules.

        Returns (category, sub_category, is_deterministic).
        """
        search_text = f"{account_name} {description}".lower()

        for pattern, (category, sub_cat) in COA_TO_LKPM_MAPPING.items():
            if pattern in search_text:
                return category, sub_cat, True

        # Fallback: unknown account → "other" with review flag
        return "other", "domestic", False

    def _aggregate_categorized(
        self, items: list[TransactionCategorization],
    ) -> InvestmentRealization:
        """Sum categorized transactions into InvestmentRealization."""
        totals: dict[str, int] = {
            "equipment_domestic": 0,
            "equipment_import": 0,
            "building_domestic": 0,
            "building_import": 0,
            "vehicle_domestic": 0,
            "vehicle_import": 0,
            "land": 0,
            "working_capital": 0,
            "other": 0,
        }

        for item in items:
            if item.category == "land":
                totals["land"] += item.amount
            elif item.sub_category == "import":
                key = f"{item.category}_import"
                if key in totals:
                    totals[key] += item.amount
                else:
                    totals["other"] += item.amount
            else:
                key = f"{item.category}_domestic"
                if key in totals:
                    totals[key] += item.amount
                else:
                    totals["other"] += item.amount

        return InvestmentRealization(**totals)

    async def collect_employment(self, client_id: int) -> EmploymentData:
        """Query CRM for current employment data (KITAS count = TKA)."""
        try:
            async with self.db_pool.acquire() as conn:
                # TKA: count active KITAS practices
                tka_row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as tka_count
                    FROM practices
                    WHERE client_id = $1
                      AND practice_type ILIKE '%kitas%'
                      AND status IN ('active', 'in_progress', 'completed')
                    """,
                    client_id,
                )
                tka = tka_row["tka_count"] if tka_row else 0

                # TKI: from client custom_fields or default 0
                client_row = await conn.fetchrow(
                    """
                    SELECT custom_fields
                    FROM clients
                    WHERE id = $1
                    """,
                    client_id,
                )
                tki = 0
                if client_row and client_row["custom_fields"]:
                    import json

                    fields = client_row["custom_fields"]
                    if isinstance(fields, str):
                        fields = json.loads(fields)
                    tki = int(fields.get("tki_count", 0))

        except Exception as e:
            logger.warning(f"Employment data query failed: {e}")
            tka = 0
            tki = 0

        return EmploymentData(tki=tki, tka=tka)

    @staticmethod
    def _quarter_dates(quarter: str, year: int) -> tuple[date, date]:
        """Convert quarter string to start/end dates."""
        quarters = {
            "Q1": (date(year, 1, 1), date(year, 3, 31)),
            "Q2": (date(year, 4, 1), date(year, 6, 30)),
            "Q3": (date(year, 7, 1), date(year, 9, 30)),
            "Q4": (date(year, 10, 1), date(year, 12, 31)),
        }
        if quarter not in quarters:
            raise ValueError(f"Invalid quarter: {quarter}")
        return quarters[quarter]
