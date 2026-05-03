"""Tests for domain-specific schemas."""

import pytest
from pydantic import ValidationError

from nuzantara_schemas.domain import (
    CompanyInfo,
    CompanyType,
    KBLIEntry,
    PropertyInfo,
    PropertyRight,
    TaxInfo,
    TaxType,
    VisaInfo,
    VisaType,
)


class TestCompanyInfo:
    def test_pt_pma(self):
        company = CompanyInfo(
            company_type=CompanyType.PT_PMA,
            kbli_codes=["56101", "55203"],
            min_investment_usd=1_200_000,
            foreign_ownership_pct=100.0,
        )
        assert company.company_type == CompanyType.PT_PMA

    def test_ownership_out_of_range(self):
        with pytest.raises(ValidationError):
            CompanyInfo(company_type=CompanyType.PT_PMA, foreign_ownership_pct=101.0)


class TestVisaInfo:
    def test_kitas(self):
        visa = VisaInfo(
            visa_type=VisaType.KITAS,
            sponsor_required=True,
            duration_months=12,
            extendable=True,
            work_permit_included=True,
        )
        assert visa.work_permit_included is True


class TestPropertyInfo:
    def test_hak_pakai(self):
        prop = PropertyInfo(
            right_type=PropertyRight.HAK_PAKAI,
            foreigner_eligible=True,
            duration_years=25,
            renewable=True,
        )
        assert prop.foreigner_eligible is True


class TestTaxInfo:
    def test_ppn(self):
        tax = TaxInfo(
            tax_type=TaxType.PPN,
            rate_pct=11.0,
            filing_frequency="monthly",
        )
        assert tax.rate_pct == 11.0

    def test_rate_out_of_range(self):
        with pytest.raises(ValidationError):
            TaxInfo(tax_type=TaxType.PPN, rate_pct=150.0)


class TestKBLIEntry:
    def test_valid_entry(self):
        entry = KBLIEntry(
            kode_kbli="56101",
            judul="Restoran",
            content="Usaha penyediaan makanan dan minuman",
            pma_status="open",
            foreign_ownership_max_pct=100.0,
        )
        assert entry.kode_kbli == "56101"
