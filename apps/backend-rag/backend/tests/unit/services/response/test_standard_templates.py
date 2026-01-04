"""
Unit tests for Standard Templates
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.response.standard_templates import (
    get_company_setup_template,
    get_tax_template,
    get_visa_template,
)


class TestStandardTemplates:
    """Tests for standard template functions"""

    def test_get_visa_template_italian(self):
        """Test getting visa template in Italian"""
        template = get_visa_template("it")
        assert "[NOME_VISTO]" in template
        assert "[CODICE]" in template
        assert "Scheda Visto" in template

    def test_get_visa_template_english(self):
        """Test getting visa template in English"""
        template = get_visa_template("en")
        assert "[VISA_NAME]" in template
        assert "[CODE]" in template
        assert "Visa Snapshot" in template

    def test_get_visa_template_indonesian(self):
        """Test getting visa template in Indonesian"""
        template = get_visa_template("id")
        assert "[NAMA_VISA]" in template
        assert "[KODE]" in template
        assert "Detail Visa" in template

    def test_get_visa_template_default(self):
        """Test getting visa template default (English)"""
        template = get_visa_template()
        assert "[VISA_NAME]" in template

    def test_get_tax_template_italian(self):
        """Test getting tax template in Italian"""
        template = get_tax_template("it")
        assert "[TIPO_IMPOSTA]" in template
        assert "Riepilogo Fiscale" in template

    def test_get_tax_template_english(self):
        """Test getting tax template in English"""
        template = get_tax_template("en")
        assert "[TAX_TYPE]" in template
        assert "Tax Summary" in template

    def test_get_tax_template_indonesian(self):
        """Test getting tax template in Indonesian"""
        template = get_tax_template("id")
        assert "[JENIS_PAJAK]" in template
        assert "Ringkasan Pajak" in template

    def test_get_company_setup_template_italian(self):
        """Test getting company setup template in Italian"""
        template = get_company_setup_template("it")
        assert "[TIPO_AZIENDA]" in template
        assert "Setup Aziendale" in template

    def test_get_company_setup_template_english(self):
        """Test getting company setup template in English"""
        template = get_company_setup_template("en")
        assert "[COMPANY_TYPE]" in template or "[TIPE_PERUSAHAAN]" in template
        assert "Company Setup" in template

    def test_get_company_setup_template_indonesian(self):
        """Test getting company setup template in Indonesian"""
        template = get_company_setup_template("id")
        assert "[TIPE_PERUSAHAAN]" in template
        assert "Pendirian Perusahaan" in template
