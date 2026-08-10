"""
Tests for backend.channels.source_filter.public_sources.

Guards against the client-facing "📚 Fonti:" footer leaking internal RAG
source names (NotebookLM training-data labels, raw KB doc titles, generic
"Document" placeholders) to clients on any channel.

Author: Claude Sonnet 5
Date: 2026-07-18
"""

import pytest

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


class TestPublicSourcesToleratesForeignShapes:
    """The `sources` field carries more than one shape, so this must not crash.

    `agentic_rag.py:474` declares `sources: list[Any]`. Measured live
    2026-08-10 on /api/agentic-rag/query, two shapes came back from the same
    endpoint in one session: the retrieval path returns
    {title,url,collection,score,snippet} dicts, and the PricingTool path
    returns `str(dict)` Python reprs. `"...".get(...)` is an AttributeError,
    and all four live channel formatters (web, instagram, telegram, whatsapp)
    call `public_sources`.
    """

    # Verbatim prefix of what the pricing path actually emitted (str, not JSON).
    PRICING_SHAPED = (
        "{'official_notice': '\U0001f512 PREZZI UFFICIALI BALI ZERO 2026', "
        "'search_query': 'PT PMA', 'results': {}}"
    )

    def test_a_stringified_dict_does_not_raise(self) -> None:
        """GUILT: before the isinstance guard this raised AttributeError."""
        assert public_sources([self.PRICING_SHAPED]) == []

    @pytest.mark.parametrize("foreign", [None, 42, ["nested"], ("a", "b")])
    def test_no_scalar_or_sequence_shape_raises(self, foreign: object) -> None:
        assert public_sources([foreign]) == []

    def test_a_legitimate_source_survives_beside_a_foreign_one(self) -> None:
        """INNOCENCE — the load-bearing half.

        A guard that skips non-dicts is worthless if it also swallows the real
        source sitting next to one. This is what distinguishes the fix from
        `except AttributeError: return []`.
        """
        legit = {
            "title": "Imigrasi B1 page",
            "url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/B1",
        }
        assert public_sources([self.PRICING_SHAPED, legit, None]) == [legit]

    def test_the_existing_filtering_rules_still_apply_around_a_foreign_entry(
        self,
    ) -> None:
        """INNOCENCE: skipping non-dicts must not weaken the internal blocklist."""
        legit = {"title": "Official gazette", "url": "https://peraturan.go.id/x"}
        sources = [
            self.PRICING_SHAPED,
            {"title": "Document", "url": "https://example.com/doc"},  # generic
            {"title": "notebooklm export", "url": "https://example.com/nb"},  # internal
            {"title": "No link here"},  # no url
            legit,
        ]
        assert public_sources(sources) == [legit]
