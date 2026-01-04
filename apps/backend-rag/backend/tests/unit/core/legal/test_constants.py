"""
Unit tests for legal constants
Target: >95% coverage
"""

import re
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.legal.constants import (
    AYAT_PATTERN,
    BAB_PATTERN,
    BAGIAN_PATTERN,
    CONTEXT_TEMPLATE,
    KONSIDERANS_MARKERS,
    LEGAL_TYPE_ABBREV,
    LEGAL_TYPE_PATTERN,
    MAX_PASAL_TOKENS,
    NOISE_PATTERNS,
    NUMBER_PATTERN,
    PARAGRAF_PATTERN,
    PASAL_PATTERN,
    PENJELASAN_PATTERN,
    STATUS_PATTERNS,
    TOPIC_PATTERN,
    WHITESPACE_FIXES,
    YEAR_PATTERN,
)


class TestLegalConstants:
    """Tests for legal constants"""

    def test_noise_patterns_exist(self):
        """Test that noise patterns exist"""
        assert len(NOISE_PATTERNS) > 0
        assert all(isinstance(p, re.Pattern) for p in NOISE_PATTERNS)

    def test_legal_type_pattern(self):
        """Test legal type pattern matching"""
        assert LEGAL_TYPE_PATTERN.search("UNDANG-UNDANG REPUBLIK INDONESIA")
        assert LEGAL_TYPE_PATTERN.search("PERATURAN PEMERINTAH")
        assert LEGAL_TYPE_PATTERN.search("KEPUTUSAN PRESIDEN")

    def test_legal_type_abbrev(self):
        """Test legal type abbreviations"""
        assert LEGAL_TYPE_ABBREV["UNDANG-UNDANG"] == "UU"
        assert LEGAL_TYPE_ABBREV["PERATURAN PEMERINTAH"] == "PP"
        assert LEGAL_TYPE_ABBREV["KEPUTUSAN PRESIDEN"] == "Keppres"

    def test_number_pattern(self):
        """Test number pattern matching"""
        match = NUMBER_PATTERN.search("NOMOR 12 TAHUN 2024")
        assert match is not None
        assert match.group(1) == "12"

    def test_year_pattern(self):
        """Test year pattern matching"""
        match = YEAR_PATTERN.search("TAHUN 2024")
        assert match is not None
        assert match.group(1) == "2024"

    def test_topic_pattern(self):
        """Test topic pattern matching"""
        text = "TENTANG Perubahan Atas Undang-Undang DENGAN RAHMAT"
        match = TOPIC_PATTERN.search(text)
        assert match is not None

    def test_status_patterns(self):
        """Test status patterns"""
        assert STATUS_PATTERNS["dicabut"].search("DICABUT")
        assert STATUS_PATTERNS["berlaku"].search("BERLAKU")

    def test_konsiderans_markers(self):
        """Test konsiderans markers"""
        assert "Menimbang" in KONSIDERANS_MARKERS
        assert "Mengingat" in KONSIDERANS_MARKERS

    def test_bab_pattern(self):
        """Test BAB pattern matching"""
        match = BAB_PATTERN.search("BAB I KETENTUAN UMUM")
        assert match is not None

    def test_bagian_pattern(self):
        """Test Bagian pattern matching"""
        match = BAGIAN_PATTERN.search("Bagian Kesatu Ketentuan")
        assert match is not None

    def test_paragraf_pattern(self):
        """Test Paragraf pattern matching"""
        match = PARAGRAF_PATTERN.search("Paragraf 1 Ketentuan")
        assert match is not None

    def test_pasal_pattern(self):
        """Test Pasal pattern matching"""
        match = PASAL_PATTERN.search("Pasal 1 Ketentuan umum")
        assert match is not None

    def test_ayat_pattern(self):
        """Test Ayat pattern matching"""
        match = AYAT_PATTERN.search("(1) Ketentuan pertama")
        assert match is not None

    def test_penjelasan_pattern(self):
        """Test Penjelasan pattern matching"""
        match = PENJELASAN_PATTERN.search("Penjelasan Umum")
        assert match is not None

    def test_max_pasal_tokens(self):
        """Test max pasal tokens constant"""
        assert MAX_PASAL_TOKENS == 1000

    def test_context_template(self):
        """Test context template format"""
        assert "{type}" in CONTEXT_TEMPLATE
        assert "{number}" in CONTEXT_TEMPLATE
        assert "{year}" in CONTEXT_TEMPLATE
        assert "{topic}" in CONTEXT_TEMPLATE

    def test_whitespace_fixes(self):
        """Test whitespace fixes patterns"""
        assert len(WHITESPACE_FIXES) > 0
        assert all(isinstance(fix, tuple) and len(fix) == 2 for fix in WHITESPACE_FIXES)
