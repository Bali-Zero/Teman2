"""Tests for backend.services.knowledge_graph.advanced_quality"""

import pytest

from backend.services.knowledge_graph.advanced_quality import (
    EnhancementStats,
    _infer_relationship_type,
    detect_hierarchical_relationships,
    extract_cross_references,
    infer_domain_relationships,
    normalize_entity_name,
)


# ── normalize_entity_name ────────────────────────────────────────────────────


class TestNormalizeEntityName:
    def test_uu_short_form(self):
        # regex + undang_undang type: "UU No. 6 Tahun 2023" -> upper -> "UU NO. 6 TAHUN 2023"
        # then re-sub NO -> No., TAHUN -> Tahun  =>  "UU No.. 6 Tahun 2023"
        result = normalize_entity_name("UU 6/2023", "undang_undang")
        assert "UU" in result and "6" in result and "2023" in result

    def test_uu_nomor_form(self):
        result = normalize_entity_name("UU Nomor 11/2020", "undang_undang")
        assert "UU" in result and "11" in result and "2020" in result

    def test_undang_undang_full(self):
        result = normalize_entity_name("Undang-Undang No 6/2023", "undang_undang")
        assert "UU" in result and "6" in result and "2023" in result

    def test_pp_normalization(self):
        result = normalize_entity_name("PP 28/2025", "peraturan_pemerintah")
        assert "PP" in result and "28" in result and "2025" in result

    def test_peraturan_pemerintah_full(self):
        result = normalize_entity_name("Peraturan Pemerintah No 10/2021", "peraturan_pemerintah")
        assert "PP" in result and "10" in result and "2021" in result

    def test_perpres_normalization(self):
        result = normalize_entity_name("Perpres 20/2024", "perpres")
        assert "PERPRES" in result and "20" in result and "2024" in result

    def test_permen_normalization(self):
        result = normalize_entity_name("Permen Hukum 10/2023", "permen")
        assert "PERMEN" in result
        assert "10" in result
        assert "2023" in result

    def test_perda_normalization(self):
        result = normalize_entity_name("Perda 5/2022", "other")
        assert "Perda No. 5 Tahun 2022" in result

    def test_pasal_ayat_normalization(self):
        result = normalize_entity_name("Pasal 10 ayat 2", "pasal")
        assert result == "Pasal 10 Ayat 2"

    def test_pasal_capitalization(self):
        result = normalize_entity_name("pasal 5", "pasal")
        assert "Pasal" in result

    def test_huruf_capitalization(self):
        result = normalize_entity_name("huruf a", "pasal")
        assert "Huruf" in result

    def test_kbli_bare_code(self):
        result = normalize_entity_name("56101", "kbli")
        assert result == "KBLI 56101"

    def test_kbli_with_prefix(self):
        result = normalize_entity_name("KBLI 56101", "kbli")
        assert result == "KBLI 56101"

    def test_kbli_typo_ibli(self):
        result = normalize_entity_name("IBLI 56101", "kbli")
        assert result == "KBLI 56101"

    def test_currency_rp(self):
        result = normalize_entity_name("Rp.1.000.000", "biaya")
        assert "Rp" in result

    def test_currency_usd(self):
        result = normalize_entity_name("USD 100", "biaya")
        assert "USD" in result

    def test_strip_whitespace(self):
        assert normalize_entity_name("  test  ", "other") == "test"

    def test_undang_undang_type_uppercase(self):
        result = normalize_entity_name("UU 6/2023", "undang_undang")
        assert "No." in result
        assert "Tahun" in result


# ── extract_cross_references ────────────────────────────────────────────────


class TestExtractCrossReferences:
    def test_sebagaimana_diatur(self):
        text = "sebagaimana diatur dalam UU No. 6 Tahun 2023"
        refs = extract_cross_references(text)
        assert len(refs) == 1
        assert refs[0]["relationship"] == "REFERENCES"
        assert refs[0]["target_name"] == "UU No. 6 Tahun 2023"

    def test_berdasarkan(self):
        text = "berdasarkan PP No. 28/2025"
        refs = extract_cross_references(text)
        assert len(refs) == 1
        assert refs[0]["relationship"] == "REFERENCES"
        assert refs[0]["target_type"] == "peraturan_pemerintah"

    def test_mengacu_pada(self):
        text = "mengacu pada Perpres No. 20 Tahun 2024"
        refs = extract_cross_references(text)
        assert len(refs) == 1
        assert refs[0]["relationship"] == "REFERENCES"
        assert refs[0]["target_type"] == "perpres"

    def test_diubah_dengan(self):
        text = "telah diubah dengan UU No. 11 Tahun 2020"
        refs = extract_cross_references(text)
        assert len(refs) == 1
        assert refs[0]["relationship"] == "AMENDS"

    def test_mencabut(self):
        text = "mencabut PP No. 5 Tahun 2010"
        refs = extract_cross_references(text)
        assert len(refs) == 1
        assert refs[0]["relationship"] == "REPLACES"

    def test_pelaksanaan(self):
        text = "untuk pelaksanaan UU No. 6 Tahun 2023"
        refs = extract_cross_references(text)
        assert len(refs) == 1
        assert refs[0]["relationship"] == "IMPLEMENTS"

    def test_multiple_references(self):
        text = (
            "sebagaimana diatur dalam UU No. 6 Tahun 2023 "
            "dan mencabut PP No. 5 Tahun 2010"
        )
        refs = extract_cross_references(text)
        assert len(refs) == 2

    def test_no_references(self):
        text = "ini adalah teks tanpa referensi hukum"
        refs = extract_cross_references(text)
        assert len(refs) == 0


# ── detect_hierarchical_relationships ────────────────────────────────────────


class TestDetectHierarchicalRelationships:
    def test_pasal_links_to_matching_law(self):
        entities = [
            {"id": "p1", "type": "pasal", "name": "Pasal 10 UU"},
            {"id": "u1", "type": "undang_undang", "name": "UU No. 6 Tahun 2023"},
        ]
        rels = detect_hierarchical_relationships(entities)
        assert len(rels) >= 1
        assert rels[0]["type"] == "PART_OF"
        assert rels[0]["source_id"] == "p1"

    def test_pasal_links_to_first_law_if_no_match(self):
        entities = [
            {"id": "p1", "type": "pasal", "name": "Pasal 5"},
            {"id": "u1", "type": "undang_undang", "name": "UU No. 6 Tahun 2023"},
        ]
        rels = detect_hierarchical_relationships(entities)
        assert len(rels) >= 1
        assert rels[0]["confidence"] == 0.6

    def test_kbli_hierarchy(self):
        entities = [
            {"id": "k1", "type": "kbli", "name": "KBLI 56101"},
            {"id": "k2", "type": "kbli", "name": "KBLI 5610"},
        ]
        rels = detect_hierarchical_relationships(entities)
        assert len(rels) == 1
        assert rels[0]["type"] == "PART_OF"
        assert rels[0]["source_id"] == "k1"
        assert rels[0]["target_id"] == "k2"
        assert rels[0]["confidence"] == 0.95

    def test_no_entities(self):
        rels = detect_hierarchical_relationships([])
        assert rels == []

    def test_no_pasals_no_kblis(self):
        entities = [
            {"id": "d1", "type": "dokumen", "name": "Passport"},
        ]
        rels = detect_hierarchical_relationships(entities)
        assert rels == []


# ── infer_domain_relationships ───────────────────────────────────────────────


class TestInferDomainRelationships:
    def test_izin_kbli_relationship(self):
        entities = [
            {"id": "i1", "type": "izin_usaha", "name": "NIB"},
            {"id": "k1", "type": "kbli", "name": "KBLI 56101"},
        ]
        text = "klasifikasi kegiatan usaha sesuai KBLI"
        rels = infer_domain_relationships(entities, text)
        assert len(rels) >= 1
        assert rels[0]["type"] == "CLASSIFIED_AS"

    def test_izin_dokumen_relationship(self):
        entities = [
            {"id": "i1", "type": "izin_usaha", "name": "NIB"},
            {"id": "d1", "type": "dokumen", "name": "Akta Notaris"},
        ]
        text = "persyaratan dokumen kelengkapan"
        rels = infer_domain_relationships(entities, text)
        assert len(rels) >= 1
        assert rels[0]["type"] == "REQUIRES"

    def test_visa_biaya_relationship(self):
        entities = [
            {"id": "v1", "type": "visa", "name": "KITAS"},
            {"id": "b1", "type": "biaya", "name": "PNBP"},
        ]
        text = "biaya visa fee PNBP retribusi"
        rels = infer_domain_relationships(entities, text)
        assert len(rels) >= 1
        assert rels[0]["type"] == "HAS_FEE"

    def test_no_matching_keywords(self):
        entities = [
            {"id": "i1", "type": "izin_usaha", "name": "NIB"},
            {"id": "k1", "type": "kbli", "name": "KBLI 56101"},
        ]
        text = "teks biasa tanpa kata kunci"
        rels = infer_domain_relationships(entities, text)
        assert rels == []

    def test_no_matching_entity_types(self):
        entities = [
            {"id": "x1", "type": "other", "name": "Something"},
        ]
        text = "klasifikasi kegiatan usaha KBLI"
        rels = infer_domain_relationships(entities, text)
        assert rels == []


# ── find_semantic_links ──────────────────────────────────────────────────────


class TestFindSemanticLinks:
    @pytest.mark.asyncio
    async def test_no_embeddings_cache(self):
        from backend.services.knowledge_graph.advanced_quality import find_semantic_links

        result = await find_semantic_links([], [], embeddings_cache=None)
        assert result == []

    @pytest.mark.asyncio
    async def test_with_similar_entities(self):
        from backend.services.knowledge_graph.advanced_quality import find_semantic_links

        orphans = [{"id": "o1", "type": "pasal", "name": "Pasal 5"}]
        all_entities = [
            {"id": "o1", "type": "pasal", "name": "Pasal 5"},
            {"id": "c1", "type": "undang_undang", "name": "UU 6/2023"},
        ]
        cache = {
            "o1": [1.0, 0.0, 0.0],
            "c1": [0.9, 0.1, 0.0],
        }
        result = await find_semantic_links(
            orphans, all_entities, embeddings_cache=cache, similarity_threshold=0.5,
        )
        assert len(result) == 1
        assert result[0]["source_id"] == "o1"
        assert result[0]["target_id"] == "c1"
        assert result[0]["type"] == "PART_OF"

    @pytest.mark.asyncio
    async def test_below_threshold(self):
        from backend.services.knowledge_graph.advanced_quality import find_semantic_links

        orphans = [{"id": "o1", "type": "other", "name": "Test"}]
        all_entities = [
            {"id": "o1", "type": "other", "name": "Test"},
            {"id": "c1", "type": "other", "name": "Unrelated"},
        ]
        cache = {
            "o1": [1.0, 0.0, 0.0],
            "c1": [0.0, 1.0, 0.0],
        }
        result = await find_semantic_links(
            orphans, all_entities, embeddings_cache=cache, similarity_threshold=0.9,
        )
        assert result == []


# ── _infer_relationship_type ─────────────────────────────────────────────────


class TestInferRelationshipType:
    def test_pasal_to_uu(self):
        assert _infer_relationship_type("pasal", "undang_undang") == "PART_OF"

    def test_kbli_to_izin(self):
        assert _infer_relationship_type("kbli", "izin_usaha") == "CLASSIFIED_AS"

    def test_biaya_to_izin(self):
        assert _infer_relationship_type("biaya", "izin_usaha") == "HAS_FEE"

    def test_unknown_pair(self):
        assert _infer_relationship_type("unknown", "other") == "RELATED_TO"


# ── EnhancementStats ────────────────────────────────────────────────────────


class TestEnhancementStats:
    def test_default_values(self):
        stats = EnhancementStats()
        assert stats.entities_normalized == 0
        assert stats.cross_references_found == 0

    def test_to_dict(self):
        stats = EnhancementStats(entities_normalized=5, semantic_links=3)
        d = stats.to_dict()
        assert d["entities_normalized"] == 5
        assert d["semantic_links"] == 3
        assert len(d) == 5


# ── enhance_kg_quality (async with DB mock) ──────────────────────────────────


class TestEnhanceKgQuality:
    @pytest.mark.asyncio
    async def test_missing_database_url(self, monkeypatch):
        from backend.services.knowledge_graph.advanced_quality import enhance_kg_quality

        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValueError, match="DATABASE_URL not set"):
            await enhance_kg_quality("test_collection")

    @pytest.mark.asyncio
    async def test_dry_run(self, monkeypatch):
        from unittest.mock import AsyncMock, MagicMock

        from backend.services.knowledge_graph.advanced_quality import enhance_kg_quality

        monkeypatch.setenv("DATABASE_URL", "postgres://fake:5432/test")

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.close = AsyncMock()

        monkeypatch.setattr(
            "backend.services.knowledge_graph.advanced_quality.asyncpg.connect",
            AsyncMock(return_value=mock_conn),
        )

        stats = await enhance_kg_quality("test", dry_run=True)
        assert isinstance(stats, EnhancementStats)
        assert stats.entities_normalized == 0
