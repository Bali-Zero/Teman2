"""
Tests for LKPM (Investment Activity Report) system.

Covers: models, validator, data collector, service, ready pack.
All business logic is deterministic — same input = same output.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.models.lkpm import (
    DataSource,
    EmploymentData,
    InvestmentRealization,
    LKPMClientConfig,
    LKPMClientSubmission,
    LKPMDeadline,
    LKPMDraft,
    LKPMReadyPack,
    LKPMValidationResult,
    TransactionCategorization,
    ValidationAlert,
    ValidationSeverity,
)

# =====================================================================
# Model Tests
# =====================================================================


class TestInvestmentRealization:
    """Test InvestmentRealization model calculations."""

    def test_total_domestic(self) -> None:
        r = InvestmentRealization(
            equipment_domestic=100_000_000,
            building_domestic=200_000_000,
            vehicle_domestic=50_000_000,
            land=300_000_000,
            working_capital=150_000_000,
            other=25_000_000,
        )
        assert r.total_domestic == 825_000_000

    def test_total_import(self) -> None:
        r = InvestmentRealization(
            equipment_import=500_000_000,
            building_import=100_000_000,
            vehicle_import=75_000_000,
        )
        assert r.total_import == 675_000_000

    def test_grand_total(self) -> None:
        r = InvestmentRealization(
            equipment_domestic=100_000_000,
            equipment_import=200_000_000,
            land=50_000_000,
        )
        assert r.grand_total == 350_000_000

    def test_empty_realization(self) -> None:
        r = InvestmentRealization()
        assert r.total_domestic == 0
        assert r.total_import == 0
        assert r.grand_total == 0

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            InvestmentRealization(equipment_domestic=-100)


class TestEmploymentData:
    """Test EmploymentData model."""

    def test_total(self) -> None:
        e = EmploymentData(tki=10, tka=3)
        assert e.total == 13

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            EmploymentData(tki=-1)


class TestLKPMDraft:
    """Test LKPMDraft model validation."""

    def test_valid_quarter(self) -> None:
        draft = LKPMDraft(client_id=1, quarter="Q1", year=2026)
        assert draft.quarter == "Q1"

    def test_invalid_quarter(self) -> None:
        with pytest.raises(ValueError, match="Q1, Q2, Q3, or Q4"):
            LKPMDraft(client_id=1, quarter="Q5", year=2026)

    def test_invalid_year(self) -> None:
        with pytest.raises(ValueError, match="between 2020 and 2100"):
            LKPMDraft(client_id=1, quarter="Q1", year=1999)


# =====================================================================
# Data Collector Tests
# =====================================================================


class TestDataCollector:
    """Test LKPMDataCollector — form processing and transaction categorization."""

    def test_collect_from_form(self) -> None:
        from backend.services.compliance.lkpm_data_collector import LKPMDataCollector

        submission = LKPMClientSubmission(
            client_id=42,
            quarter="Q1",
            year=2026,
            equipment_domestic=100_000_000,
            equipment_import=50_000_000,
            building_domestic=200_000_000,
            tki=10,
            tka=2,
            quarterly_revenue=500_000_000,
        )

        collector = LKPMDataCollector(db_pool=MagicMock())
        draft = collector.collect_from_form(submission)

        assert draft.client_id == 42
        assert draft.quarter == "Q1"
        assert draft.year == 2026
        assert draft.realized.equipment_domestic == 100_000_000
        assert draft.realized.equipment_import == 50_000_000
        assert draft.realized.building_domestic == 200_000_000
        assert draft.employment.tki == 10
        assert draft.employment.tka == 2
        assert draft.quarterly_revenue == 500_000_000
        assert draft.data_source == DataSource.MANUAL

    def test_categorize_transactions_deterministic(self) -> None:
        from backend.services.compliance.lkpm_data_collector import LKPMDataCollector

        entries = [
            {
                "id": "1",
                "description": "Pembelian Mesin CNC",
                "account_name": "Peralatan Kantor",
                "debit": 50_000_000,
                "credit": 0,
            },
            {
                "id": "2",
                "description": "Renovasi Gedung",
                "account_name": "Bangunan",
                "debit": 100_000_000,
                "credit": 0,
            },
            {
                "id": "3",
                "description": "Beli Mobil Operasional",
                "account_name": "Kendaraan",
                "debit": 250_000_000,
                "credit": 0,
            },
            {
                "id": "4",
                "description": "Unknown misc expense",
                "account_name": "Sundry Expense",
                "debit": 10_000_000,
                "credit": 0,
            },
        ]

        collector = LKPMDataCollector(db_pool=MagicMock())
        categorized = collector.categorize_transactions(entries)

        assert len(categorized) == 4

        # Deterministic mappings
        assert categorized[0].category == "equipment"
        assert categorized[0].confidence == "deterministic"
        assert not categorized[0].ai_needs_review

        assert categorized[1].category == "building"
        assert categorized[1].confidence == "deterministic"

        assert categorized[2].category == "vehicle"
        assert categorized[2].confidence == "deterministic"

        # Unknown → other with review flag
        assert categorized[3].category == "other"
        assert categorized[3].confidence == "ai_suggested"
        assert categorized[3].ai_needs_review

    def test_categorize_skips_zero_amount(self) -> None:
        from backend.services.compliance.lkpm_data_collector import LKPMDataCollector

        entries = [
            {"id": "1", "description": "test", "account_name": "Kas", "debit": 0, "credit": 0},
        ]
        collector = LKPMDataCollector(db_pool=MagicMock())
        categorized = collector.categorize_transactions(entries)
        assert len(categorized) == 0

    def test_aggregate_categorized(self) -> None:
        from backend.services.compliance.lkpm_data_collector import LKPMDataCollector

        items = [
            TransactionCategorization(
                journal_entry_id="1",
                description="Equipment",
                amount=100,
                category="equipment",
                sub_category="domestic",
                confidence="deterministic",
            ),
            TransactionCategorization(
                journal_entry_id="2",
                description="Equipment Import",
                amount=200,
                category="equipment",
                sub_category="import",
                confidence="deterministic",
            ),
            TransactionCategorization(
                journal_entry_id="3",
                description="Land",
                amount=300,
                category="land",
                sub_category="domestic",
                confidence="deterministic",
            ),
        ]

        collector = LKPMDataCollector(db_pool=MagicMock())
        result = collector._aggregate_categorized(items)

        assert result.equipment_domestic == 100
        assert result.equipment_import == 200
        assert result.land == 300
        assert result.grand_total == 600

    def test_quarter_dates(self) -> None:
        from datetime import date

        from backend.services.compliance.lkpm_data_collector import LKPMDataCollector

        start, end = LKPMDataCollector._quarter_dates("Q1", 2026)
        assert start == date(2026, 1, 1)
        assert end == date(2026, 3, 31)

        start, end = LKPMDataCollector._quarter_dates("Q4", 2025)
        assert start == date(2025, 10, 1)
        assert end == date(2025, 12, 31)


# =====================================================================
# Validator Tests
# =====================================================================


class TestLKPMValidator:
    """Test LKPMValidator — deterministic validation rules."""

    def test_cross_check_consistency_within_plan(self) -> None:
        from backend.services.compliance.lkpm_validator import LKPMValidator

        validator = LKPMValidator(db_pool=MagicMock())

        draft = LKPMDraft(
            client_id=1,
            quarter="Q1",
            year=2026,
            cumulative=InvestmentRealization(
                equipment_domestic=50_000_000,
                building_domestic=100_000_000,
            ),
        )
        config = LKPMClientConfig(
            client_id=1,
            company_name="Test PT",
            planned=InvestmentRealization(
                equipment_domestic=200_000_000,
                building_domestic=500_000_000,
            ),
        )

        alerts = validator.cross_check_consistency(draft, config)
        # Should be green — within plan
        assert all(a.severity == ValidationSeverity.GREEN for a in alerts)

    def test_cross_check_consistency_over_plan(self) -> None:
        from backend.services.compliance.lkpm_validator import LKPMValidator

        validator = LKPMValidator(db_pool=MagicMock())

        draft = LKPMDraft(
            client_id=1,
            quarter="Q1",
            year=2026,
            cumulative=InvestmentRealization(equipment_domestic=300_000_000),
        )
        config = LKPMClientConfig(
            client_id=1,
            company_name="Test PT",
            planned=InvestmentRealization(equipment_domestic=200_000_000),
        )

        alerts = validator.cross_check_consistency(draft, config)
        yellow_alerts = [a for a in alerts if a.severity == ValidationSeverity.YELLOW]
        assert len(yellow_alerts) == 1
        assert "exceeds plan" in yellow_alerts[0].message

    def test_completeness_zero_realization_with_revenue(self) -> None:
        from backend.services.compliance.lkpm_validator import LKPMValidator

        validator = LKPMValidator(db_pool=MagicMock())

        draft = LKPMDraft(
            client_id=1,
            quarter="Q1",
            year=2026,
            quarterly_revenue=100_000_000,
        )

        alerts = validator.check_completeness(draft)
        assert any("zero" in a.message.lower() and "revenue" in a.message.lower() for a in alerts)

    def test_completeness_ai_categorized_items(self) -> None:
        from backend.services.compliance.lkpm_validator import LKPMValidator

        validator = LKPMValidator(db_pool=MagicMock())

        draft = LKPMDraft(
            client_id=1,
            quarter="Q1",
            year=2026,
            has_ai_categorized_items=True,
            ai_categorized_count=5,
        )

        alerts = validator.check_completeness(draft)
        assert any("5 transactions categorized by AI" in a.message for a in alerts)

    def test_completeness_tka_without_tki(self) -> None:
        from backend.services.compliance.lkpm_validator import LKPMValidator

        validator = LKPMValidator(db_pool=MagicMock())

        draft = LKPMDraft(
            client_id=1,
            quarter="Q1",
            year=2026,
            employment=EmploymentData(tki=0, tka=3),
        )

        alerts = validator.check_completeness(draft)
        assert any("zero local workers" in a.message.lower() for a in alerts)


# =====================================================================
# Ready Pack Tests
# =====================================================================


class TestReadyPack:
    """Test Ready Pack HTML generation."""

    def test_format_idr(self) -> None:
        from backend.services.compliance.lkpm_ready_pack import format_idr

        assert format_idr(0) == "0"
        assert format_idr(1000) == "1.000"
        assert format_idr(1_500_000) == "1.500.000"
        assert format_idr(100_000_000) == "100.000.000"
        assert format_idr(1_234_567_890) == "1.234.567.890"

    def test_generate_html_contains_key_fields(self) -> None:
        from backend.services.compliance.lkpm_ready_pack import generate_ready_pack_html

        pack = LKPMReadyPack(
            draft_id=1,
            client_id=42,
            company_name="PT Test Indonesia",
            npwp="01.234.567.8-901.000",
            nib="1234567890",
            quarter="Q1",
            year=2026,
            kbli_codes=["62011", "62012"],
            realized=InvestmentRealization(equipment_domestic=100_000_000),
            realized_total=100_000_000,
            cumulative=InvestmentRealization(equipment_domestic=300_000_000),
            cumulative_total=300_000_000,
            plan=InvestmentRealization(equipment_domestic=1_000_000_000),
            realization_percentage=30.0,
            employment=EmploymentData(tki=10, tka=2),
            quarterly_revenue=500_000_000,
        )

        html = generate_ready_pack_html(pack)

        assert "PT Test Indonesia" in html
        assert "01.234.567.8-901.000" in html
        assert "1234567890" in html
        assert "Q1 2026" in html
        assert "62011" in html
        assert "100.000.000" in html
        assert "300.000.000" in html
        assert "30.0%" in html
        assert "500.000.000" in html

    def test_generate_html_with_validation_alerts(self) -> None:
        from backend.services.compliance.lkpm_ready_pack import generate_ready_pack_html

        pack = LKPMReadyPack(
            draft_id=1,
            client_id=42,
            company_name="PT Test",
            quarter="Q1",
            year=2026,
            realized=InvestmentRealization(),
            cumulative=InvestmentRealization(),
            plan=InvestmentRealization(),
            employment=EmploymentData(),
            validation=LKPMValidationResult(
                is_valid=False,
                alerts=[
                    ValidationAlert(
                        field="kbli",
                        severity=ValidationSeverity.RED,
                        message="No KBLI codes registered",
                    ),
                ],
                red_count=1,
            ),
        )

        html = generate_ready_pack_html(pack)
        assert "No KBLI codes registered" in html
        assert "#dc3545" in html  # Red color


# =====================================================================
# Deadline Tests
# =====================================================================


class TestDeadlines:
    """Test deadline calculation — pure calendar math."""

    def test_get_deadlines(self) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        service = LKPMService(db_pool=MagicMock())
        deadlines = service.get_deadlines(days_ahead=365)

        # Should return at least some deadlines
        assert isinstance(deadlines, list)
        for d in deadlines:
            assert isinstance(d, LKPMDeadline)
            assert d.quarter in {"Q1", "Q2", "Q3", "Q4"}

    def test_deadlines_sorted_by_days_remaining(self) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        service = LKPMService(db_pool=MagicMock())
        deadlines = service.get_deadlines(days_ahead=365)

        if len(deadlines) > 1:
            for i in range(len(deadlines) - 1):
                assert deadlines[i].days_remaining <= deadlines[i + 1].days_remaining


# =====================================================================
# Service Integration Tests (with mocked DB)
# =====================================================================


class TestLKPMServiceWithMockedDB:
    """Test LKPMService with mocked database pool."""

    @pytest.fixture
    def mock_pool(self) -> MagicMock:
        pool = MagicMock()
        conn = AsyncMock()

        # Create a proper async context manager
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx
        pool._conn = conn  # Store for test access
        return pool

    @pytest.mark.asyncio
    async def test_get_client_config_not_found(self, mock_pool: MagicMock) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        mock_pool._conn.fetchrow.return_value = None

        service = LKPMService(db_pool=mock_pool)
        result = await service.get_client_config(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_submit_form_creates_draft(self, mock_pool: MagicMock) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        conn = mock_pool._conn
        # Mock cumulative query (no previous reports)
        conn.fetch.return_value = [
            {
                "eq_d": 0,
                "eq_i": 0,
                "bd_d": 0,
                "bd_i": 0,
                "vh_d": 0,
                "vh_i": 0,
                "land": 0,
                "wc": 0,
                "other": 0,
            },
        ]
        # Mock save (upsert returns id)
        conn.fetchrow.return_value = {"id": 1}

        service = LKPMService(db_pool=mock_pool)
        submission = LKPMClientSubmission(
            client_id=42,
            quarter="Q1",
            year=2026,
            equipment_domestic=100_000_000,
            tki=5,
            tka=1,
        )

        draft = await service.submit_form_data(submission)
        assert draft.id == 1
        assert draft.realized.equipment_domestic == 100_000_000
        assert draft.employment.tki == 5
