"""
Tests for backend.channels.source_filter.public_sources.

Guards against the client-facing "📚 Fonti:" footer leaking internal RAG
source names (NotebookLM training-data labels, raw KB doc titles, generic
"Document" placeholders) to clients on any channel.

Author: Claude Sonnet 5
Date: 2026-07-18
"""

from backend.channels.source_filter import public_sources


class TestPublicSourcesDropsInternal:
    """Internal-looking sources must never survive the filter."""

    def test_drops_generic_document_title(self) -> None:
        sources = [{"title": "Document", "url": "https://example.com/doc"}]
        assert public_sources(sources) == []

    def test_drops_generic_documento_title_case_insensitive(self) -> None:
        sources = [{"title": "DOCUMENTO", "url": "https://example.com/doc"}]
        assert public_sources(sources) == []

    def test_drops_notebooklm_training_data_label(self) -> None:
        sources = [
            {
                "title": "NotebookLM Generated Training Data - Session 2",
                "url": "https://notebooklm.google.com/whatever",
            }
        ]
        assert public_sources(sources) == []

    def test_drops_raw_kb_doc_title_without_public_url(self) -> None:
        sources = [{"title": "B1 VISA SAAT KEDATANGAN (WISATA)"}]
        assert public_sources(sources) == []

    def test_drops_source_with_no_url_key_at_all(self) -> None:
        sources = [{"title": "Overstay, Deportation, Blacklist (Penangkalan)"}]
        assert public_sources(sources) == []

    def test_drops_source_with_empty_url(self) -> None:
        sources = [{"title": "Some internal chunk", "url": ""}]
        assert public_sources(sources) == []

    def test_drops_source_with_non_http_url(self) -> None:
        # Internal file:// or relative paths are not public links.
        sources = [{"title": "Local KB file", "url": "file:///data/kb/doc.md"}]
        assert public_sources(sources) == []

    def test_drops_title_containing_chunk_marker(self) -> None:
        sources = [{"title": "kb_chunk_0042", "url": "https://example.com/x"}]
        assert public_sources(sources) == []

    def test_drops_title_containing_curated_qa_marker(self) -> None:
        sources = [{"title": "curated_qa entry", "url": "https://example.com/x"}]
        assert public_sources(sources) == []

    def test_all_four_leak_examples_dropped_together(self) -> None:
        sources = [
            {"title": "Document", "url": "https://example.com/doc"},
            {
                "title": "NotebookLM Generated Training Data - Session 2",
                "url": "https://notebooklm.google.com/whatever",
            },
            {"title": "B1 VISA SAAT KEDATANGAN (WISATA)"},
            {"title": "Overstay, Deportation, Blacklist (Penangkalan)"},
        ]
        assert public_sources(sources) == []


class TestPublicSourcesKeepsLegitimate:
    """A genuinely public, well-formed source must pass through untouched."""

    def test_keeps_legitimate_public_source(self) -> None:
        source = {
            "title": "Imigrasi B1 page",
            "url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/B1",
        }
        assert public_sources([source]) == [source]

    def test_keeps_http_scheme_too(self) -> None:
        source = {"title": "Official gazette", "url": "http://peraturan.go.id/x"}
        assert public_sources([source]) == [source]

    def test_mixed_list_keeps_only_legitimate_entry(self) -> None:
        legit = {
            "title": "Imigrasi B1 page",
            "url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/B1",
        }
        sources = [
            {"title": "Document", "url": "https://example.com/doc"},
            legit,
            {"title": "B1 VISA SAAT KEDATANGAN (WISATA)"},
        ]
        assert public_sources(sources) == [legit]


class TestPublicSourcesEdgeCases:
    def test_none_input_returns_empty_list(self) -> None:
        assert public_sources(None) == []

    def test_empty_list_returns_empty_list(self) -> None:
        assert public_sources([]) == []
