"""
Tests for LegalStructureParser
"""

from core.legal.structure_parser import LegalStructureParser


class TestLegalStructureParser:
    """Test suite for LegalStructureParser"""

    def test_init(self):
        """Test parser initialization"""
        parser = LegalStructureParser()
        assert parser is not None

    def test_parse_empty_text(self):
        """Test parsing empty text"""
        parser = LegalStructureParser()
        result = parser.parse("")
        assert result == {}

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only text"""
        parser = LegalStructureParser()
        result = parser.parse("   \n\t  ")
        assert result == {}

    def test_parse_with_konsiderans(self):
        """Test parsing document with Konsiderans"""
        text = """Menimbang:
a. Pertimbangan pertama
b. Pertimbangan kedua

Mengingat:
1. Undang-undang dasar
2. Peraturan lainnya

MEMUTUSKAN:
Menetapkan: UNDANG-UNDANG TENTANG TEST

BAB I
KETENTUAN UMUM

Pasal 1
Dalam Undang-undang ini yang dimaksud dengan:
(1) Test adalah test
(2) Test2 adalah test2

Penjelasan Umum
Ini adalah penjelasan umum."""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert "konsiderans" in result
        assert result["konsiderans"] is not None
        assert "Menimbang" in result["konsiderans"]
        assert "batang_tubuh" in result
        assert len(result["batang_tubuh"]) > 0
        assert "penjelasan" in result
        assert result["penjelasan"] is not None
        assert "pasal_list" in result
        assert len(result["pasal_list"]) > 0

    def test_parse_without_konsiderans(self):
        """Test parsing document without Konsiderans"""
        text = """BAB I
KETENTUAN UMUM

Pasal 1
Test content

Pasal 2
More test content"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert result["konsiderans"] is None
        assert len(result["batang_tubuh"]) > 0
        assert len(result["pasal_list"]) > 0

    def test_parse_batang_tubuh_structure(self):
        """Test parsing Batang Tubuh with BAB structure"""
        text = """BAB I
KETENTUAN UMUM

Pasal 1
Content of Pasal 1

BAB II
KETENTUAN KHUSUS

Pasal 2
Content of Pasal 2"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["batang_tubuh"]) == 2
        assert result["batang_tubuh"][0]["number"] == "I"
        assert "KETENTUAN UMUM" in result["batang_tubuh"][0]["title"]
        assert result["batang_tubuh"][1]["number"] == "II"
        assert "KETENTUAN KHUSUS" in result["batang_tubuh"][1]["title"]

    def test_parse_bagian_structure(self):
        """Test parsing Bagian within BAB"""
        text = """BAB I
KETENTUAN UMUM

Bagian Kesatu
PENDAHULUAN

Pasal 1
Content

Bagian Kedua
LANJUTAN

Pasal 2
Content"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["batang_tubuh"]) > 0
        bab = result["batang_tubuh"][0]
        assert "bagian" in bab
        assert len(bab["bagian"]) > 0

    def test_parse_paragraf_structure(self):
        """Test parsing Paragraf within Bagian"""
        text = """BAB I
KETENTUAN UMUM

Bagian Kesatu
PENDAHULUAN

Paragraf 1
PENDAHULUAN PARAGRAF

Pasal 1
Content

Paragraf 2
LANJUTAN PARAGRAF

Pasal 2
Content"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["batang_tubuh"]) > 0
        bab = result["batang_tubuh"][0]
        assert len(bab["bagian"]) > 0
        bagian = bab["bagian"][0]
        assert "paragraf" in bagian
        assert len(bagian["paragraf"]) > 0

    def test_parse_pasal_with_ayat(self):
        """Test parsing Pasal with Ayat"""
        text = """Pasal 1
Dalam Undang-undang ini yang dimaksud dengan:
(1) Test adalah test pertama
(2) Test2 adalah test kedua
(3) Test3 adalah test ketiga"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["pasal_list"]) > 0
        pasal = result["pasal_list"][0]
        assert pasal["number"] == "1"
        assert "ayat" in pasal
        assert len(pasal["ayat"]) == 3
        assert pasal["ayat"][0]["number"] == "1"
        assert pasal["ayat"][1]["number"] == "2"
        assert pasal["ayat"][2]["number"] == "3"

    def test_parse_pasal_without_ayat(self):
        """Test parsing Pasal without Ayat"""
        text = """Pasal 1
Ini adalah pasal tanpa ayat yang memiliki konten langsung."""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["pasal_list"]) > 0
        pasal = result["pasal_list"][0]
        assert pasal["number"] == "1"
        assert "ayat" in pasal
        assert len(pasal["ayat"]) == 0

    def test_parse_penjelasan(self):
        """Test parsing Penjelasan section"""
        text = """BAB I
KETENTUAN UMUM

Pasal 1
Content

Penjelasan Umum
Ini adalah penjelasan umum tentang undang-undang ini."""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert result["penjelasan"] is not None
        assert "Penjelasan" in result["penjelasan"]

    def test_parse_penjelasan_pasal(self):
        """Test parsing Penjelasan Pasal"""
        text = """Pasal 1
Content

Penjelasan Pasal 1
Ini adalah penjelasan untuk Pasal 1."""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert result["penjelasan"] is not None
        assert "Penjelasan Pasal" in result["penjelasan"]

    def test_extract_konsiderans_with_index(self):
        """Test _extract_konsiderans_with_index method"""
        text = """Menimbang:
a. Pertimbangan pertama

MEMUTUSKAN:
Menetapkan: UNDANG-UNDANG

BAB I
KETENTUAN"""
        parser = LegalStructureParser()
        konsiderans, end_index = parser._extract_konsiderans_with_index(text)

        assert konsiderans is not None
        assert "Menimbang" in konsiderans
        assert end_index is not None
        assert end_index > 0

    def test_extract_konsiderans_no_marker(self):
        """Test _extract_konsiderans_with_index with no Konsiderans marker"""
        text = """BAB I
KETENTUAN UMUM

Pasal 1
Content"""
        parser = LegalStructureParser()
        konsiderans, end_index = parser._extract_konsiderans_with_index(text)

        assert konsiderans is None
        assert end_index is None

    def test_extract_konsiderans(self):
        """Test _extract_konsiderans wrapper method"""
        text = """Menimbang:
a. Pertimbangan

MEMUTUSKAN:
BAB I"""
        parser = LegalStructureParser()
        konsiderans = parser._extract_konsiderans(text)

        assert konsiderans is not None
        assert "Menimbang" in konsiderans

    def test_parse_batang_tubuh_multiple_bab(self):
        """Test parsing multiple BAB in Batang Tubuh"""
        text = """BAB I
KETENTUAN UMUM

Pasal 1
Content 1

BAB II
KETENTUAN KHUSUS

Pasal 2
Content 2

BAB III
KETENTUAN PENUTUP

Pasal 3
Content 3"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["batang_tubuh"]) == 3
        assert result["batang_tubuh"][0]["number"] == "I"
        assert result["batang_tubuh"][1]["number"] == "II"
        assert result["batang_tubuh"][2]["number"] == "III"

    def test_parse_pasal_list_with_bab_context(self):
        """Test _extract_pasal_list includes BAB context"""
        text = """BAB I
KETENTUAN UMUM

Pasal 1
Content 1

BAB II
KETENTUAN KHUSUS

Pasal 2
Content 2"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["pasal_list"]) == 2
        # Check that pasal_list includes bab_context
        pasal1 = result["pasal_list"][0]
        pasal2 = result["pasal_list"][1]
        assert pasal1["number"] == "1"
        assert pasal2["number"] == "2"
        # bab_context should be set if _find_bab_context works
        assert "bab_context" in pasal1

    def test_find_bab_context(self):
        """Test _find_bab_context method"""
        text = """BAB I
KETENTUAN UMUM

Pasal 1
Content

BAB II
KETENTUAN KHUSUS

Pasal 2
Content"""
        parser = LegalStructureParser()
        # Find position of Pasal 2
        pasal2_pos = text.find("Pasal 2")
        bab_context = parser._find_bab_context(text, pasal2_pos)

        # Should find BAB II
        assert bab_context is not None
        assert "BAB II" in bab_context

    def test_find_bab_context_no_match(self):
        """Test _find_bab_context with no matching BAB"""
        text = """Pasal 1
Content without BAB"""
        parser = LegalStructureParser()
        bab_context = parser._find_bab_context(text, 0)

        assert bab_context is None

    def test_parse_roman_numeral_bab(self):
        """Test parsing BAB with Roman numerals"""
        text = """BAB IV
KETENTUAN KHUSUS

Pasal 1
Content"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["batang_tubuh"]) > 0
        assert result["batang_tubuh"][0]["number"] == "IV"

    def test_parse_arabic_numeral_bab(self):
        """Test parsing BAB with Arabic numerals"""
        text = """BAB 1
KETENTUAN UMUM

Pasal 1
Content"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["batang_tubuh"]) > 0
        assert result["batang_tubuh"][0]["number"] == "1"

    def test_parse_pasal_roman_numeral(self):
        """Test parsing Pasal with Roman numerals"""
        text = """Pasal I
Content of Pasal I

Pasal II
Content of Pasal II"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["pasal_list"]) == 2
        assert result["pasal_list"][0]["number"] == "I"
        assert result["pasal_list"][1]["number"] == "II"

    def test_parse_pasal_with_letter_suffix(self):
        """Test parsing Pasal with letter suffix (e.g., Pasal 1A)"""
        text = """Pasal 1A
Content of Pasal 1A

Pasal 1B
Content of Pasal 1B"""
        parser = LegalStructureParser()
        result = parser.parse(text)

        assert len(result["pasal_list"]) >= 1
        # Check that at least one pasal has letter suffix
        pasal_numbers = [p["number"] for p in result["pasal_list"]]
        assert any("A" in num or "B" in num for num in pasal_numbers)
