"""
Tests for LegalCleaner
"""

from core.legal.cleaner import LegalCleaner


class TestLegalCleaner:
    """Test suite for LegalCleaner"""

    def test_init(self):
        """Test cleaner initialization"""
        cleaner = LegalCleaner()
        assert cleaner is not None

    def test_clean_empty_text(self):
        """Test cleaning empty text"""
        cleaner = LegalCleaner()
        result = cleaner.clean("")

        assert result == ""

    def test_clean_whitespace_only(self):
        """Test cleaning whitespace-only text"""
        cleaner = LegalCleaner()
        result = cleaner.clean("   \n\t  ")

        # Cleaner returns original text if it's only whitespace (after strip check)
        # But after processing, it should be cleaned
        assert result.strip() == "" or len(result) == 0

    def test_clean_removes_page_numbers(self):
        """Test cleaning removes page numbers"""
        cleaner = LegalCleaner()
        text = """Halaman 1 dari 10
Content here
Halaman 2 dari 10
More content"""
        result = cleaner.clean(text)

        assert "Halaman" not in result or "dari" not in result

    def test_clean_removes_certification_footer(self):
        """Test cleaning removes certification footer"""
        cleaner = LegalCleaner()
        text = """Content here
Salinan sesuai dengan aslinya
Kepala Bagian"""
        result = cleaner.clean(text)

        assert "Salinan sesuai dengan aslinya" not in result

    def test_clean_removes_president_header(self):
        """Test cleaning removes president header"""
        cleaner = LegalCleaner()
        text = """PRESIDEN REPUBLIK INDONESIA
Content here"""
        result = cleaner.clean(text)

        assert "PRESIDEN REPUBLIK INDONESIA" not in result

    def test_clean_normalizes_pasal_spacing(self):
        """Test cleaning normalizes Pasal spacing"""
        cleaner = LegalCleaner()
        text = """Pasal  1
Content
Pasal   2
More content"""
        result = cleaner.clean(text)

        assert "Pasal 1" in result
        assert "Pasal 2" in result
        assert "Pasal  1" not in result
        assert "Pasal   2" not in result

    def test_clean_removes_standalone_page_numbers(self):
        """Test cleaning removes standalone page numbers"""
        cleaner = LegalCleaner()
        text = """Content line 1
123
Content line 2
456
Content line 3"""
        result = cleaner.clean(text)

        # Standalone numbers should be removed
        lines = result.split("\n")
        assert "123" not in lines
        assert "456" not in lines

    def test_clean_removes_excessive_blank_lines(self):
        """Test cleaning removes excessive blank lines"""
        cleaner = LegalCleaner()
        text = """Line 1


Line 2


Line 3"""
        result = cleaner.clean(text)

        # Should have max 2 consecutive newlines
        assert "\n\n\n" not in result

    def test_clean_trims_whitespace(self):
        """Test cleaning trims whitespace"""
        cleaner = LegalCleaner()
        text = "   Content with spaces   "
        result = cleaner.clean(text)

        assert result == "Content with spaces"
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_clean_preserves_content(self):
        """Test cleaning preserves actual content"""
        cleaner = LegalCleaner()
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

Pasal 1
Ini adalah konten Pasal 1.

Pasal 2
Ini adalah konten Pasal 2."""
        result = cleaner.clean(text)

        assert "UNDANG-UNDANG" in result
        assert "NOMOR 12" in result
        assert "Pasal 1" in result
        assert "Pasal 2" in result
        assert "konten Pasal 1" in result
        assert "konten Pasal 2" in result

    def test_clean_handles_noise_patterns(self):
        """Test cleaning handles various noise patterns"""
        cleaner = LegalCleaner()
        text = """Content
- 1 -
More content
- 2 -
Even more"""
        result = cleaner.clean(text)

        # Page separators should be removed
        assert "- 1 -" not in result
        assert "- 2 -" not in result

    def test_clean_headers_footers_removes_president(self):
        """Test clean_headers_footers removes president header"""
        cleaner = LegalCleaner()
        text = """PRESIDEN REPUBLIK INDONESIA
Content here"""
        result = cleaner.clean_headers_footers(text)

        assert "PRESIDEN REPUBLIK INDONESIA" not in result
        assert "Content here" in result

    def test_clean_headers_footers_removes_menteri(self):
        """Test clean_headers_footers removes menteri header"""
        cleaner = LegalCleaner()
        text = """MENTERI KESEHATAN
Content here"""
        result = cleaner.clean_headers_footers(text)

        assert "MENTERI" not in result
        assert "Content here" in result

    def test_clean_headers_footers_removes_gubernur(self):
        """Test clean_headers_footers removes gubernur header"""
        cleaner = LegalCleaner()
        text = """GUBERNUR JAWA BARAT
Content here"""
        result = cleaner.clean_headers_footers(text)

        assert "GUBERNUR" not in result
        assert "Content here" in result

    def test_clean_headers_footers_removes_bupati(self):
        """Test clean_headers_footers removes bupati header"""
        cleaner = LegalCleaner()
        text = """BUPATI BANDUNG
Content here"""
        result = cleaner.clean_headers_footers(text)

        assert "BUPATI" not in result
        assert "Content here" in result

    def test_clean_headers_footers_removes_walikota(self):
        """Test clean_headers_footers removes walikota header"""
        cleaner = LegalCleaner()
        text = """WALIKOTA BANDUNG
Content here"""
        result = cleaner.clean_headers_footers(text)

        assert "WALIKOTA" not in result
        assert "Content here" in result

    def test_clean_headers_footers_preserves_content(self):
        """Test clean_headers_footers preserves content"""
        cleaner = LegalCleaner()
        text = """PRESIDEN REPUBLIK INDONESIA
Pasal 1
Content of Pasal 1."""
        result = cleaner.clean_headers_footers(text)

        assert "Pasal 1" in result
        assert "Content of Pasal 1" in result

    def test_clean_headers_footers_trims_whitespace(self):
        """Test clean_headers_footers trims whitespace"""
        cleaner = LegalCleaner()
        text = """PRESIDEN REPUBLIK INDONESIA
Content"""
        result = cleaner.clean_headers_footers(text)

        assert not result.startswith("\n")
        assert not result.endswith("\n")

    def test_clean_with_salinan_footer(self):
        """Test clean removes Salinan footer"""
        cleaner = LegalCleaner()
        text = """Content here
Salinan sesuai dengan aslinya
Kepala Bagian Administrasi"""
        result = cleaner.clean(text)

        assert "Salinan sesuai dengan aslinya" not in result

    def test_clean_with_multiple_noise_patterns(self):
        """Test clean handles multiple noise patterns"""
        cleaner = LegalCleaner()
        text = """PRESIDEN REPUBLIK INDONESIA
Halaman 1 dari 10
Content
- 1 -
More content
123
Salinan sesuai dengan aslinya"""
        result = cleaner.clean(text)

        assert "PRESIDEN REPUBLIK INDONESIA" not in result
        assert "Halaman" not in result
        assert "- 1 -" not in result
        assert "Salinan sesuai dengan aslinya" not in result
        assert "Content" in result
        assert "More content" in result

    def test_clean_normalizes_whitespace(self):
        """Test clean normalizes whitespace"""
        cleaner = LegalCleaner()
        text = "Content    with    multiple    spaces"
        result = cleaner.clean(text)

        # Should normalize multiple spaces
        assert "    " not in result

    def test_clean_handles_pasal_with_letter(self):
        """Test clean handles Pasal with letter suffix"""
        cleaner = LegalCleaner()
        text = """Pasal  1A
Content
Pasal   2B
More content"""
        result = cleaner.clean(text)

        assert "Pasal 1A" in result
        assert "Pasal 2B" in result

    def test_clean_case_insensitive_pasal(self):
        """Test clean handles case-insensitive Pasal"""
        cleaner = LegalCleaner()
        text = """pasal  1
PASAL  2
Pasal  3"""
        result = cleaner.clean(text)

        assert "Pasal 1" in result or "pasal 1" in result
        assert "Pasal 2" in result or "PASAL 2" in result
        assert "Pasal 3" in result
