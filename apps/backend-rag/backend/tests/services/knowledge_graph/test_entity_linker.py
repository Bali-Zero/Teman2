"""Tests for Entity Linker — cross-source entity resolution."""

from backend.services.knowledge_graph.entity_linker import extract_mentions


class TestExtractMentions:
    """Test regex-based entity mention extraction."""

    def test_kbli_code(self) -> None:
        mentions = extract_mentions("Untuk KBLI 56101 restoran ini perlu izin")
        types = [m["type"] for m in mentions]
        assert "kbli" in types

    def test_law_reference(self) -> None:
        mentions = extract_mentions("Berdasarkan UU No. 6 Tahun 2023 tentang cipta kerja")
        types = [m["type"] for m in mentions]
        assert "undang_undang" in types

    def test_government_regulation(self) -> None:
        mentions = extract_mentions("PP No. 35 Tahun 2021 mengatur tentang")
        types = [m["type"] for m in mentions]
        assert "peraturan_pemerintah" in types

    def test_visa_types(self) -> None:
        text = "Pemegang KITAS wajib memiliki IMTA yang valid"
        mentions = extract_mentions(text)
        types = [m["type"] for m in mentions]
        assert "visa" in types
        assert "izin" in types

    def test_company_types(self) -> None:
        mentions = extract_mentions("PT PMA dengan modal dasar 10 miliar")
        types = [m["type"] for m in mentions]
        assert "company" in types

    def test_tax_types(self) -> None:
        mentions = extract_mentions("Wajib membayar PPh 21 dan PPN setiap bulan")
        types = [m["type"] for m in mentions]
        assert "tax" in types

    def test_government_bodies(self) -> None:
        mentions = extract_mentions("Pendaftaran di BKPM melalui OSS")
        types = [m["type"] for m in mentions]
        assert "gov" in types
        assert "izin" in types  # OSS is also an izin

    def test_no_duplicates(self) -> None:
        """Same entity mentioned multiple times should not duplicate."""
        text = "KITAS diurus melalui KITAS card dan KITAS permit"
        mentions = extract_mentions(text)
        kitas_mentions = [m for m in mentions if "KITAS" in m["text"]]
        assert len(kitas_mentions) == 1

    def test_empty_text(self) -> None:
        assert extract_mentions("") == []

    def test_no_entities(self) -> None:
        assert extract_mentions("Hello, this is a general text about nothing specific") == []

    def test_mixed_entities(self) -> None:
        text = (
            "Untuk membuka restoran (KBLI 56101) melalui PT PMA, "
            "diperlukan KITAS dengan RPTKA dari BKPM sesuai UU No 6 Tahun 2023"
        )
        mentions = extract_mentions(text)
        types = {m["type"] for m in mentions}
        assert {"kbli", "company", "visa", "izin", "gov", "undang_undang"}.issubset(types)

    def test_presidential_regulation(self) -> None:
        mentions = extract_mentions("Perpres No 10 Tahun 2021")
        types = [m["type"] for m in mentions]
        assert "perpres" in types
