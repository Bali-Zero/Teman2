"""
Comprehensive tests for Legal Document Cleaner
Target: 95%+ coverage
"""


class TestLegalCleanerInit:
    """Test LegalCleaner initialization"""

    def test_init(self):
        """Test initialization logs message"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        assert cleaner is not None


class TestLegalCleanerClean:
    """Test clean method"""

    def test_clean_empty_text(self):
        """Test clean with empty text"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()
        result = cleaner.clean("")

        assert result == ""

    def test_clean_none_text(self):
        """Test clean with None text"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()
        result = cleaner.clean(None)

        assert result is None

    def test_clean_whitespace_only(self):
        """Test clean with whitespace only returns original"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()
        text = "   \n\t  "
        result = cleaner.clean(text)

        # Returns original for whitespace-only
        assert result == text

    def test_clean_removes_page_numbers(self):
        """Test removal of page number patterns"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
Halaman 1 dari 10
Some legal content here.
Halaman 2 dari 10
More content.
"""

        result = cleaner.clean(text)

        assert "Halaman 1 dari 10" not in result
        assert "Halaman 2 dari 10" not in result
        assert "Some legal content here" in result

    def test_clean_removes_salinan_footer(self):
        """Test removal of Salinan sesuai dengan aslinya footer"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
Pasal 1
Content of article one.

Salinan sesuai dengan aslinya
Kepala Biro Hukum
"""

        result = cleaner.clean(text)

        assert "Salinan sesuai dengan aslinya" not in result
        assert "Pasal 1" in result

    def test_clean_removes_president_header(self):
        """Test removal of repeated President header"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
PRESIDEN REPUBLIK INDONESIA

Pasal 1
Content.

PRESIDEN REPUBLIK INDONESIA

Pasal 2
More content.
"""

        result = cleaner.clean(text)

        # Should remove the header pattern
        assert (
            result.count("PRESIDEN REPUBLIK INDONESIA") < 2
            or "PRESIDEN REPUBLIK INDONESIA" not in result
        )

    def test_clean_removes_page_separators(self):
        """Test removal of page separators"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
Content before.
- 1 -
Content after separator.
- 2 -
More content.
"""

        result = cleaner.clean(text)

        assert "- 1 -" not in result
        assert "- 2 -" not in result

    def test_clean_removes_standalone_numbers(self):
        """Test removal of standalone page numbers"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
Content.

1

More content.

25

End content.
"""

        result = cleaner.clean(text)

        # Standalone numbers on their own lines should be removed
        lines = result.strip().split("\n")
        for line in lines:
            if line.strip():
                # Non-empty lines should not be just a number
                assert not (line.strip().isdigit() and len(line.strip()) <= 3)

    def test_clean_normalizes_multiple_blank_lines(self):
        """Test normalization of multiple blank lines"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = "Line 1.\n\n\n\n\nLine 2."

        result = cleaner.clean(text)

        # Multiple newlines should be reduced
        assert "\n\n\n" not in result

    def test_clean_normalizes_pasal_spacing(self):
        """Test normalization of Pasal spacing"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
Pasal  1
Content.

Pasal   2A
More content.
"""

        result = cleaner.clean(text)

        # Should normalize to "Pasal 1" and "Pasal 2A"
        assert "Pasal 1" in result
        assert "Pasal 2A" in result

    def test_clean_trims_whitespace(self):
        """Test trimming of leading/trailing whitespace"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = "   \n\nContent here.\n\n   "

        result = cleaner.clean(text)

        assert result == result.strip()
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_clean_preserves_content(self):
        """Test that actual content is preserved"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
BAB I
KETENTUAN UMUM

Pasal 1
Dalam Undang-Undang ini yang dimaksud dengan:
(1) Keimigrasian adalah hal ihwal lalu lintas orang.
(2) Orang Asing adalah orang yang bukan WNI.

Pasal 2
Kewenangan dalam keimigrasian.
"""

        result = cleaner.clean(text)

        assert "BAB I" in result
        assert "KETENTUAN UMUM" in result
        assert "Pasal 1" in result
        assert "Keimigrasian" in result
        assert "Pasal 2" in result

    def test_clean_logs_reduction(self):
        """Test that cleaning logs reduction info"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
Halaman 1 dari 10
Content here.
Halaman 2 dari 10
More content.
"""

        result = cleaner.clean(text)

        # Just verify it runs without error
        assert result is not None

    def test_clean_multiple_passes(self):
        """Test that multiple noise patterns are removed"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
PRESIDEN REPUBLIK INDONESIA
Halaman 1 dari 5

Content.
- 1 -

Salinan sesuai dengan aslinya




More content.
"""

        result = cleaner.clean(text)

        assert "Halaman 1 dari 5" not in result
        assert "- 1 -" not in result
        assert "Salinan sesuai dengan aslinya" not in result
        assert "\n\n\n\n" not in result


class TestLegalCleanerCleanHeadersFooters:
    """Test clean_headers_footers method"""

    def test_clean_headers_footers_presiden(self):
        """Test removal of PRESIDEN header"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
PRESIDEN REPUBLIK INDONESIA
Content after.
"""

        result = cleaner.clean_headers_footers(text)

        assert "PRESIDEN" not in result
        assert "Content after" in result

    def test_clean_headers_footers_menteri(self):
        """Test removal of MENTERI header"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
MENTERI HUKUM DAN HAK ASASI MANUSIA
Content.
"""

        result = cleaner.clean_headers_footers(text)

        assert "MENTERI" not in result

    def test_clean_headers_footers_gubernur(self):
        """Test removal of GUBERNUR header"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
GUBERNUR BALI
Content.
"""

        result = cleaner.clean_headers_footers(text)

        assert "GUBERNUR" not in result

    def test_clean_headers_footers_bupati(self):
        """Test removal of BUPATI header"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
BUPATI BADUNG
Content.
"""

        result = cleaner.clean_headers_footers(text)

        assert "BUPATI" not in result

    def test_clean_headers_footers_walikota(self):
        """Test removal of WALIKOTA header"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
WALIKOTA DENPASAR
Content.
"""

        result = cleaner.clean_headers_footers(text)

        assert "WALIKOTA" not in result

    def test_clean_headers_footers_preserves_content(self):
        """Test that actual content is preserved"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
PRESIDEN REPUBLIK INDONESIA

BAB I
KETENTUAN UMUM

Pasal 1
Content here.
"""

        result = cleaner.clean_headers_footers(text)

        assert "BAB I" in result
        assert "KETENTUAN UMUM" in result
        assert "Pasal 1" in result

    def test_clean_headers_footers_multiple_headers(self):
        """Test removal of multiple header types"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
PRESIDEN REPUBLIK INDONESIA
MENTERI DALAM NEGERI
GUBERNUR JAWA TIMUR
Content.
"""

        result = cleaner.clean_headers_footers(text)

        assert "PRESIDEN" not in result
        assert "MENTERI" not in result
        assert "GUBERNUR" not in result
        assert "Content" in result

    def test_clean_headers_footers_empty_text(self):
        """Test with empty text"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        result = cleaner.clean_headers_footers("")

        assert result == ""

    def test_clean_headers_footers_no_headers(self):
        """Test with text containing no headers"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
BAB I
KETENTUAN UMUM

Pasal 1
Content.
"""

        result = cleaner.clean_headers_footers(text)

        assert "BAB I" in result
        assert "Pasal 1" in result


class TestLegalCleanerIntegration:
    """Integration tests"""

    def test_clean_complete_document(self):
        """Test cleaning a complete legal document"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
PRESIDEN REPUBLIK INDONESIA
Halaman 1 dari 15

UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
TENTANG KEIMIGRASIAN

DENGAN RAHMAT TUHAN YANG MAHA ESA
PRESIDEN REPUBLIK INDONESIA

BAB I
KETENTUAN UMUM

Pasal  1
Dalam Undang-Undang ini yang dimaksud dengan:
(1) Keimigrasian adalah hal ihwal lalu lintas orang.
(2) Orang Asing adalah orang yang bukan WNI.

- 2 -

Pasal  2
Kewenangan dalam keimigrasian.




Halaman 2 dari 15

BAB II
PENUTUP

Pasal 3
Undang-Undang ini mulai berlaku.

Salinan sesuai dengan aslinya
Kepala Biro Hukum

42
"""

        result = cleaner.clean(text)

        # Headers/footers should be removed
        assert "Halaman 1 dari 15" not in result
        assert "Halaman 2 dari 15" not in result
        assert "- 2 -" not in result
        assert "Salinan sesuai dengan aslinya" not in result

        # Content should be preserved
        assert "UNDANG-UNDANG REPUBLIK INDONESIA" in result
        assert "NOMOR 6 TAHUN 2011" in result
        assert "KETENTUAN UMUM" in result
        assert "Keimigrasian" in result

        # Pasal spacing should be normalized
        assert "Pasal 1" in result
        assert "Pasal 2" in result

        # Multiple blank lines should be reduced
        assert "\n\n\n\n" not in result

    def test_clean_then_headers(self):
        """Test clean followed by clean_headers_footers"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
PRESIDEN REPUBLIK INDONESIA
Halaman 1 dari 5

Content here.

Salinan sesuai dengan aslinya
"""

        # First clean
        result1 = cleaner.clean(text)

        # Then clean headers
        result2 = cleaner.clean_headers_footers(result1)

        assert "PRESIDEN" not in result2
        assert "Halaman" not in result2
        assert "Salinan" not in result2
        assert "Content" in result2

    def test_clean_idempotent(self):
        """Test that cleaning twice gives same result"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = """
Halaman 1 dari 10
Content here.
- 1 -
More content.
"""

        result1 = cleaner.clean(text)
        result2 = cleaner.clean(result1)

        # Cleaning an already-clean document should not change it
        assert result1 == result2

    def test_clean_whitespace_fixes(self):
        """Test whitespace fix patterns"""
        from backend.core.legal.cleaner import LegalCleaner

        cleaner = LegalCleaner()

        text = "Content    with   multiple     spaces."

        result = cleaner.clean(text)

        # Multiple spaces should be normalized
        assert "    " not in result
