"""Tests for CRM-Guardian L1 schemas v2.0 (Phase 1 cross-folder activation).

Locks in the v1→v2 contract changes documented in
docs/superpowers/plans/2026-05-16-crm-guardian-activation-phase1.md:
  - SCHEMA_VERSION bumped to v2.0
  - Company gains tax_records / lkpm_history / source_company_folders
  - L1ClientSummary drops narrative_id (English-only narrative)
  - prompt_version default bumped to L1_extraction_v2

A regression here means downstream consumers (worker, AiSummaryCard frontend,
NB-CRM brief generator) will see a different shape than what they trust.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from backend.services.crm_guardian.schemas import (
    SCHEMA_VERSION,
    Company,
    L1ClientSummary,
    LkpmRecord,
    TaxRecord,
)


class TestSchemaVersion:
    def test_schema_version_is_v3(self) -> None:
        """Phase 1.5 (2026-05-18) bumped to v3.0 — same shape, content-grounded prompt."""
        assert SCHEMA_VERSION == "v3.0"

    def test_l1_client_summary_default_schema_version(self) -> None:
        summary = L1ClientSummary(
            client_id=1,
            generated_at="2026-05-16T10:00:00Z",
            source_folder_id="folder_abc",
            source_file_count=0,
            source_file_fingerprint="deadbeef",
        )
        assert summary.schema_version == "v3.0"
        assert summary.prompt_version == "L1_extraction_v3"


class TestTaxRecord:
    def test_minimal_tax_record(self) -> None:
        tr = TaxRecord(period="2024")
        assert tr.period == "2024"
        assert tr.spt_type is None
        assert tr.status == "unknown"

    def test_full_tax_record(self) -> None:
        tr = TaxRecord(
            period="Q1-2025",
            spt_type="SPT_Masa_PPN",
            filed_at=date(2025, 4, 30),
            amount_idr=1_500_000_000,
            status="filed",
            source_file_id="drive_file_xyz",
            notes="VAT remittance ok",
        )
        assert tr.amount_idr == 1_500_000_000
        assert tr.status == "filed"

    def test_invalid_spt_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaxRecord(period="2024", spt_type="SPT_Invented")  # type: ignore[arg-type]

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaxRecord(period="2024", extra_field="should-fail")  # type: ignore[call-arg]


class TestLkpmRecord:
    def test_minimal_lkpm_record(self) -> None:
        lr = LkpmRecord(period="Q1-2025")
        assert lr.period == "Q1-2025"
        assert lr.status == "unknown"

    def test_full_lkpm_record(self) -> None:
        lr = LkpmRecord(
            period="Q4-2024",
            reported_at=date(2025, 1, 10),
            realization_idr=5_000_000_000,
            employment_count=15,
            status="submitted",
            source_file_id="lkpm_file_id",
            notes="On time",
        )
        assert lr.employment_count == 15
        assert lr.status == "submitted"

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LkpmRecord(period="Q1-2025", status="invented")  # type: ignore[arg-type]


class TestCompanyV2Extension:
    def test_company_defaults_to_empty_cross_folder_fields(self) -> None:
        c = Company(legal_name="PT Sample", legal_form="PT_PMA")
        assert c.tax_records == []
        assert c.lkpm_history == []
        assert c.source_company_folders == []

    def test_company_with_tax_and_lkpm(self) -> None:
        c = Company(
            legal_name="PT Test Bali",
            legal_form="PT_PMA",
            tax_records=[TaxRecord(period="2024", status="filed")],
            lkpm_history=[LkpmRecord(period="Q1-2025", status="submitted")],
            source_company_folders=["folder_id_1", "folder_id_2"],
        )
        assert len(c.tax_records) == 1
        assert len(c.lkpm_history) == 1
        assert c.source_company_folders == ["folder_id_1", "folder_id_2"]


class TestL1ClientSummaryV2:
    def test_narrative_id_removed(self) -> None:
        """v2.0 removed narrative_id (Bahasa Indonesia). English-only output."""
        summary = L1ClientSummary(
            client_id=1,
            generated_at="2026-05-16T10:00:00Z",
            source_folder_id="folder_abc",
            source_file_count=0,
            source_file_fingerprint="deadbeef",
        )
        dump = summary.model_dump()
        assert "narrative_id" not in dump
        assert "narrative_en" in dump

    def test_narrative_id_is_ignored(self) -> None:
        """v2.0 removed narrative_id; now L1ClientSummary uses extra='ignore'."""
        summary = L1ClientSummary(
            client_id=1,
            generated_at="2026-05-16T10:00:00Z",
            source_folder_id="folder_abc",
            source_file_count=0,
            source_file_fingerprint="deadbeef",
            narrative_id="should-be-ignored",  # type: ignore[call-arg]
        )
        assert "narrative_id" not in summary.model_dump()

    def test_cross_folder_summary_roundtrip(self) -> None:
        """Worker writes L1 cross-folder → roundtrip through JSONB serialization."""
        summary = L1ClientSummary(
            client_id=42,
            generated_at="2026-05-16T10:00:00Z",
            source_folder_id="client_root_id",
            source_file_count=23,
            source_file_fingerprint="sha256deadbeef",
            company=Company(
                legal_name="PT Sample Bali",
                legal_form="PT_PMA",
                nib="1234567890123",
                kbli_primary="68111",
                tax_records=[
                    TaxRecord(period="2024", spt_type="SPT_Tahunan", status="filed"),
                ],
                lkpm_history=[
                    LkpmRecord(period="Q1-2025", status="submitted"),
                ],
                source_company_folders=["company_folder_1"],
            ),
            narrative_en="PT Sample Bali is a PT PMA in Kerobokan focused on rental.",
            extraction_confidence=0.85,
        )

        # Roundtrip through dict (simulates JSONB write+read)
        as_dict = summary.model_dump(mode="json")
        restored = L1ClientSummary.model_validate(as_dict)

        assert restored.schema_version == "v3.0"
        assert restored.prompt_version == "L1_extraction_v3"
        assert restored.company.legal_name == "PT Sample Bali"
        assert len(restored.company.tax_records) == 1
        assert len(restored.company.lkpm_history) == 1
        assert restored.company.source_company_folders == ["company_folder_1"]
        assert restored.narrative_en is not None
        assert restored.extraction_confidence == 0.85

    def test_extraction_confidence_bounds_enforced(self) -> None:
        """extraction_confidence MUST be in [0.0, 1.0] for manual review gate."""
        with pytest.raises(ValidationError):
            L1ClientSummary(
                client_id=1,
                generated_at="2026-05-16T10:00:00Z",
                source_folder_id="x",
                source_file_count=0,
                source_file_fingerprint="x",
                extraction_confidence=1.5,
            )
        with pytest.raises(ValidationError):
            L1ClientSummary(
                client_id=1,
                generated_at="2026-05-16T10:00:00Z",
                source_folder_id="x",
                source_file_count=0,
                source_file_fingerprint="x",
                extraction_confidence=-0.1,
            )


class TestShareholderRoleNormalizer:
    """Phase 1.5 hotfix 2026-05-18: Indonesian role names from akta OCR
    should normalize to the English enum before validation."""

    def test_indonesian_direktur_normalized(self) -> None:
        from backend.services.crm_guardian.schemas import Shareholder

        s = Shareholder(name="Gergely Gal", role="DIREKTUR", percentage=100.0)
        assert s.role == "Director"

    def test_indonesian_komisaris_lowercase_normalized(self) -> None:
        from backend.services.crm_guardian.schemas import Shareholder

        s = Shareholder(name="Test", role="Komisaris")
        assert s.role == "Commissioner"

    def test_indonesian_pemegang_saham_normalized(self) -> None:
        from backend.services.crm_guardian.schemas import Shareholder

        s = Shareholder(name="Test", role="PEMEGANG SAHAM")
        assert s.role == "Shareholder"

    def test_indonesian_pendiri_normalized(self) -> None:
        from backend.services.crm_guardian.schemas import Shareholder

        s = Shareholder(name="Test", role="PENDIRI")
        assert s.role == "Founder"

    def test_english_canonical_passthrough(self) -> None:
        from backend.services.crm_guardian.schemas import Shareholder

        s = Shareholder(name="Test", role="Director")
        assert s.role == "Director"

    def test_unknown_role_still_rejected(self) -> None:
        from backend.services.crm_guardian.schemas import Shareholder

        with pytest.raises(ValidationError):
            Shareholder(name="Test", role="INVENTED_ROLE")

    def test_none_role_preserved(self) -> None:
        from backend.services.crm_guardian.schemas import Shareholder

        s = Shareholder(name="Test", role=None)
        assert s.role is None
