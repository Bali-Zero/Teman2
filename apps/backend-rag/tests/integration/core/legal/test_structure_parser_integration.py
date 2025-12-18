"""
Integration Tests for LegalStructureParser
Tests parsing hierarchical structure of Indonesian legal documents
"""

import os
import sys
from pathlib import Path

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestLegalStructureParserIntegration:
    """Comprehensive integration tests for LegalStructureParser"""

    @pytest.fixture
    def parser(self):
        """Create LegalStructureParser instance"""
        from core.legal.structure_parser import LegalStructureParser

        return LegalStructureParser()

    def test_initialization(self, parser):
        """Test parser initialization"""
        assert parser is not None

    def test_parse_with_konsiderans(self, parser):
        """Test parsing document with Konsiderans"""
        text = """
        MEMPERTIMBANGKAN:
        a. Bahwa visa diperlukan untuk masuk ke Indonesia.
        b. Bahwa prosedur harus diatur dengan jelas.

        MEMUTUSKAN:
        Menetapkan: UNDANG-UNDANG TENTANG VISA

        BAB I
        KETENTUAN UMUM

        Pasal 1
        Ketentuan umum.
        """

        structure = parser.parse(text)

        assert structure is not None
        assert "konsiderans" in structure
        assert "batang_tubuh" in structure
        assert structure["konsiderans"] is not None

    def test_parse_with_batang_tubuh(self, parser):
        """Test parsing document with Batang Tubuh"""
        text = """
        BAB I
        KETENTUAN UMUM

        Pasal 1
        Ketentuan umum tentang visa.

        Pasal 2
        Prosedur aplikasi.

        BAB II
        PROSEDUR

        Pasal 3
        Langkah-langkah aplikasi.
        """

        structure = parser.parse(text)

        assert structure is not None
        assert "batang_tubuh" in structure
        assert len(structure["batang_tubuh"]) >= 2

    def test_parse_with_penjelasan(self, parser):
        """Test parsing document with Penjelasan"""
        text = """
        BAB I
        KETENTUAN UMUM

        Pasal 1
        Ketentuan umum.

        PENJELASAN
        Pasal 1 menjelaskan tentang ketentuan umum.
        """

        structure = parser.parse(text)

        assert structure is not None
        assert "penjelasan" in structure
        assert structure["penjelasan"] is not None

    def test_parse_with_pasal_list(self, parser):
        """Test parsing document and extracting Pasal list"""
        text = """
        Pasal 1
        Ketentuan pertama.

        Pasal 2
        Ketentuan kedua.

        Pasal 3
        Ketentuan ketiga.
        """

        structure = parser.parse(text)

        assert structure is not None
        assert "pasal_list" in structure
        assert len(structure["pasal_list"]) >= 3

    def test_parse_empty_text(self, parser):
        """Test parsing empty text"""
        structure = parser.parse("")

        assert structure is not None
        assert structure.get("konsiderans") is None
        assert structure.get("batang_tubuh") == []

    def test_parse_with_bagian(self, parser):
        """Test parsing document with Bagian (Parts)"""
        text = """
        BAB I
        KETENTUAN UMUM

        Bagian Kesatu
        Umum

        Pasal 1
        Ketentuan umum.

        Bagian Kedua
        Khusus

        Pasal 2
        Ketentuan khusus.
        """

        structure = parser.parse(text)

        assert structure is not None
        assert "batang_tubuh" in structure
        if structure["batang_tubuh"]:
            assert "bagian" in structure["batang_tubuh"][0]

    def test_parse_with_paragraf(self, parser):
        """Test parsing document with Paragraf"""
        text = """
        BAB I
        KETENTUAN UMUM

        Paragraf 1
        Umum

        Pasal 1
        Ketentuan umum.
        """

        structure = parser.parse(text)

        assert structure is not None
        assert "batang_tubuh" in structure

    def test_parse_with_ayat(self, parser):
        """Test parsing Pasal with Ayat"""
        text = """
        Pasal 1
        (1) Ayat pertama tentang visa.
        (2) Ayat kedua tentang izin tinggal.
        (3) Ayat ketiga tentang prosedur.
        """

        structure = parser.parse(text)

        assert structure is not None
        assert "pasal_list" in structure
        if structure["pasal_list"]:
            pasal = structure["pasal_list"][0]
            assert "ayat" in pasal or "text" in pasal

    def test_extract_konsiderans(self, parser):
        """Test extracting Konsiderans"""
        text = """
        MEMPERTIMBANGKAN:
        a. Bahwa visa diperlukan.
        b. Bahwa prosedur harus diatur.

        MEMUTUSKAN:
        Menetapkan: UNDANG-UNDANG

        BAB I
        """

        konsiderans, end_index = parser._extract_konsiderans_with_index(text)

        assert konsiderans is not None
        assert "MEMPERTIMBANGKAN" in konsiderans
        assert end_index is not None

    def test_parse_batang_tubuh(self, parser):
        """Test parsing Batang Tubuh"""
        text = """
        BAB I
        KETENTUAN UMUM

        Pasal 1
        Ketentuan umum.

        BAB II
        PROSEDUR

        Pasal 2
        Prosedur aplikasi.
        """

        bab_list = parser._parse_batang_tubuh(text)

        assert bab_list is not None
        assert len(bab_list) >= 2
        assert all("number" in bab for bab in bab_list)
        assert all("title" in bab for bab in bab_list)
