"""
Unit tests for backend/app/routers/intel_scraper.py

Tests route handler functions and helpers directly (no TestClient) with mocked dependencies.
Covers:
- POST /api/intel/staging/register-notification -> register_notification
- POST /api/intel/scraper/submit               -> submit_from_scraper
- POST /api/intel/staging/publish/{type}/{id}   -> publish_staging_item
- convert_staging_to_enriched_article (helper)
- ingest_intel_to_qdrant (helper)
"""

import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# Helper: convert_staging_to_enriched_article
# ---------------------------------------------------------------------------


class TestConvertStagingToEnrichedArticle:
    def test_basic(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "New Visa Rule",
            "content": "## Summary\nNew rule.\n## Facts\nEffective Jan 2026.\n## Bali Zero Take\nImportant.\n## Next Steps\n- Step one",
            "category": "visa",
            "relevance_score": 80,
            "source_url": "https://example.com",
            "source_name": "Test Scraper",
        }
        result = convert_staging_to_enriched_article(data)

        assert result["title"] == "New Visa Rule"
        assert result["category"] == "visa"
        assert result["priority"] == "high"
        assert "tldr" in result
        assert "bali_zero_take" in result
        assert "next_steps" in result
        assert result["source"] == "Test Scraper"

    def test_low_relevance(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Minor Update",
            "content": "Some minor content.",
            "category": "news",
            "relevance_score": 30,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["priority"] == "low"
        assert result["tldr"] == {"what": "Some minor content."}

    def test_medium_relevance(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Medium Update",
            "content": "Some content here.",
            "category": "business",
            "relevance_score": 60,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["priority"] == "medium"
        assert set(result["tldr"]) == {"what"}

    def test_high_relevance_does_not_become_reader_risk(self) -> None:
        """Guilt: the GloBE article (2026-09-24) told expats "Should I Worry? Yes /
        Risk Level: High / Expats and investors in Indonesia" because relevance
        85 was read as reader risk. Priority stays editorial; the TL;DR keeps
        only what the draft says."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Indonesia Records 1,460 GloBE Taxpayer Registrations",
            "content": "## Facts\nThe tax office recorded 1,460 GloBE registrations.",
            "category": "tax-legal",
            "relevance_score": 85,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["priority"] == "high"
        assert result["tldr"] == {"what": "The tax office recorded 1,460 GloBE registrations."}

    def test_no_sections(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Plain Article",
            "content": "Just plain text without any markdown sections or structure.",
            "category": "news",
            "relevance_score": 50,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["ai_summary"]
        assert result["facts"]

    def test_fallback_summary_uses_complete_sentences(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        content = (
            "## Facts\n\n"
            "Indonesia is moving forward with a sweeping reclassification of its official "
            "business activity codes — the Klasifikasi Baku Lapangan Usaha Indonesia "
            "(KBLI) — updating the system to its 2025 edition. To manage the changeover, "
            "the government has produced a Joint Circular Letter that sets out the rules.\n\n"
            "Second paragraph."
        )

        result = convert_staging_to_enriched_article({"content": content})

        assert "#" not in result["ai_summary"]
        assert result["ai_summary"].endswith(".")
        assert result["ai_summary"].count("(") == result["ai_summary"].count(")")
        assert len(result["ai_summary"]) <= 300
        assert result["ai_summary"] == content.split("\n\n")[1].split(" To manage")[0]

    def test_fallback_summary_truncates_long_first_sentence_at_word_boundary(self) -> None:
        from backend.app.routers.intel_scraper import _summary_from_content

        content = "word " * 79 + "word."

        result = _summary_from_content(content)

        assert result.endswith("…")
        assert len(result) <= 301
        assert result[-2] != " "

    def test_fallback_summary_with_only_headings_is_empty(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        result = convert_staging_to_enriched_article({"content": "## Facts\n\n### Details"})

        assert result["ai_summary"] == ""

    def test_with_timeline_keywords(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Timeline Article",
            "content": "## Summary\nNew timeline and date information.\n## Facts\nTimeline of events.",
            "category": "news",
            "relevance_score": 75,
        }
        result = convert_staging_to_enriched_article(data)
        assert "timeline" in result["suggested_components"]

    def test_with_comparison_keywords(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Comparison Article",
            "content": "## Summary\nOld vs new regulations.\n## Facts\nComparison of approaches.",
            "category": "news",
            "relevance_score": 75,
        }
        result = convert_staging_to_enriched_article(data)
        assert "comparison-table" in result["suggested_components"]

    def test_with_expat_investor_steps(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Steps Article",
            "content": (
                "## Summary\nSummary here.\n"
                "## Facts\nFacts here.\n"
                "## Bali Zero Take\nOur take.\n"
                "## Next Steps\n"
                "### For Expats\n"
                "- Check your visa status\n"
                "- Update documents\n"
                "### For Investors\n"
                "- Review investment plan\n"
                "- Consult advisor\n"
            ),
            "category": "visa",
            "relevance_score": 80,
        }
        result = convert_staging_to_enriched_article(data)
        assert len(result["next_steps"]["expat"]) >= 1
        assert len(result["next_steps"]["investor"]) >= 1
        # Innocence: a draft with real For Expats/For Investors subsections
        # never grows a fabricated neutral group on top of them.
        assert result["next_steps"]["general"] == []

    def test_next_steps_without_audience_split_is_one_neutral_group(self) -> None:
        """Guilt: the GloBE article (2026-09-23) had no "For Expats"/"For
        Investors" subsections — a single audience-neutral Next Steps body —
        and the converter split it 50/50 between the two, inventing an
        audience the draft never named. It must land in one neutral group
        instead, never split, never filled with a stock filler."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "GloBE Registrations",
            "content": (
                "## Facts\nFacts here.\n"
                "## Bali Zero Take\nOur take.\n"
                "## Next Steps\n"
                "Ask the group tax team to confirm the scope assessment first.\n\n"
                "Review the separate reporting obligations with a qualified adviser."
            ),
            "category": "tax",
            "relevance_score": 92,
        }
        result = convert_staging_to_enriched_article(data)
        next_steps = result["next_steps"]
        assert next_steps["expat"] == []
        assert next_steps["investor"] == []
        assert len(next_steps["general"]) >= 1
        joined = " ".join(next_steps["general"])
        assert "Review the article for specific actions" not in joined
        assert "confirm the scope assessment" in joined

    def test_neutral_steps_that_mention_expats_or_investors_stay_neutral(self) -> None:
        """Guilt (gate BLOCK on #7322): the audience regex matched "expat" /
        "investor" as a SUBSTRING anywhere in the body, so a neutral step that
        merely mentioned them ("Expats should…", "an expatriate-friendly…")
        was relabelled to that audience and truncated from the match onward
        ("expatriate" → "riate…"). Only a label LINE names an audience."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        steps = [
            "Expats should renew their KITAS before it lapses.",
            "Investors must file the LKPM report every quarter.",
            "Hire an expatriate-friendly tax adviser for the annual SPT.",
        ]
        data = {
            "title": "Neutral Steps",
            "content": (
                "## Facts\nFacts here.\n"
                "## Bali Zero Take\nOur take.\n"
                "## Next Steps\n" + "\n".join(f"- {s}" for s in steps)
            ),
            "category": "visa",
            "relevance_score": 80,
        }
        next_steps = convert_staging_to_enriched_article(data)["next_steps"]
        assert next_steps["expat"] == []
        assert next_steps["investor"] == []
        assert next_steps["general"] == steps

    def test_neutral_steps_keep_the_old_ten_item_ceiling_and_short_steps(self) -> None:
        """Guilt (gate findings on #7322): the neutral group was capped at 5
        items where main still rendered 10 (5 expat + 5 investor), and the
        >10-char noise filter measured the raw "- " item, so a real short
        step like "- Pay PBB." vanished."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        steps = ["File SPT.", "Pay PBB."] + [
            f"Action item number {n} for readers to complete now." for n in range(3, 11)
        ]
        data = {
            "title": "Many Steps",
            "content": "## Facts\nF.\n## Next Steps\n" + "\n".join(f"- {s}" for s in steps),
            "category": "tax",
            "relevance_score": 60,
        }
        assert convert_staging_to_enriched_article(data)["next_steps"]["general"] == steps

    def test_a_step_that_opens_in_bold_keeps_its_bold(self) -> None:
        """Guilt (gate finding E22 on #7331): stripping the bullet with
        lstrip("- ").lstrip("* ") also ate the opening "**" of a step that
        starts in bold, leaving an orphan "**" mid-text."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Bold Steps",
            "content": (
                "## Facts\nF.\n## Next Steps\n"
                "- **Deadline**: file the SPT by 31 March.\n"
                "* Keep the receipt on file.\n"
            ),
            "category": "tax",
            "relevance_score": 60,
        }
        assert convert_staging_to_enriched_article(data)["next_steps"]["general"] == [
            "**Deadline**: file the SPT by 31 March.",
            "Keep the receipt on file.",
        ]

    def test_crlf_draft_extracts_every_mapped_section(self) -> None:
        """Guilt (gate finding on #7331): with CRLF line endings the
        extractors' `[ \\t]*\\n` never consumed the "\\r", so a colon heading
        or "## Bali Zero Take" was classified as known but never extracted."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Windows Draft",
            "content": (
                "## Facts\r\nThe rule starts in March.\r\n"
                "## Bali Zero Take\r\nOur take on the rule.\r\n"
                "## Next Steps:\r\n- Renew the permit before expiry.\r\n"
            ),
            "category": "visa",
            "relevance_score": 60,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["facts"] == "The rule starts in March."
        assert "Our take on the rule." in str(result["bali_zero_take"])
        assert result["next_steps"]["general"] == ["Renew the permit before expiry."]
        assert result["extra_sections"] == []

    def test_mapped_headings_with_a_trailing_colon_are_extracted(self) -> None:
        """Guilt (gate finding F4 on #7322): "## Next Steps:" / "## Facts:"
        were classified as known headings (so never kept as extra sections)
        but the extractors required a newline right after the name, so the
        steps and facts silently vanished."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Colon Headings",
            "content": (
                "## Summary:\nShort summary of the change.\n"
                "## Facts:\nThe regulation takes effect in March.\n"
                "## Next Steps:\n- Renew the permit before expiry.\n- Book the notary slot early.\n"
            ),
            "category": "visa",
            "relevance_score": 60,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["facts"] == "The regulation takes effect in March."
        assert result["next_steps"]["general"] == [
            "Renew the permit before expiry.",
            "Book the notary slot early.",
        ]
        assert result["extra_sections"] == []

    def test_audience_label_lines_in_heading_bold_and_colon_forms(self) -> None:
        """Innocence for the fix above: a real label LINE still names its
        audience whether it is a heading, a bold line or a bare "For X:"
        line, and a step under it that mentions the other audience stays
        where it is."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        for expat_label, investor_label in [
            ("### For Expats", "### For Investors"),
            ("**For Expats:**", "**For Investors:**"),
            ("For Expats:", "For Investors:"),
            ("##### For Expats", "##### For Investors"),
        ]:
            data = {
                "title": "Labelled Steps",
                "content": (
                    "## Facts\nFacts here.\n"
                    "## Next Steps\n"
                    f"{expat_label}\n"
                    "- Check your visa status\n"
                    "- Ask your investor sponsor for the RPTKA letter\n"
                    f"{investor_label}\n"
                    "- Review investment plan\n"
                ),
                "category": "visa",
                "relevance_score": 80,
            }
            next_steps = convert_staging_to_enriched_article(data)["next_steps"]
            assert next_steps["expat"] == [
                "Check your visa status",
                "Ask your investor sponsor for the RPTKA letter",
            ], expat_label
            assert next_steps["investor"] == ["Review investment plan"], investor_label
            assert next_steps["general"] == [], expat_label

    def test_next_steps_never_emits_filler_and_omits_empty_groups(self) -> None:
        """Guilt: a Next Steps section too short to yield any real item must
        stay empty (and the MDX layer omits the section), never the
        "Review the article for specific actions" filler."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Thin Article",
            "content": "## Facts\nFacts here.\n## Next Steps\nTBD",
            "category": "news",
            "relevance_score": 50,
        }
        result = convert_staging_to_enriched_article(data)
        next_steps = result["next_steps"]
        for group in (next_steps["expat"], next_steps["investor"], next_steps["general"]):
            for item in group:
                assert "Review the article for specific actions" not in item
        assert next_steps["expat"] == []
        assert next_steps["investor"] == []
        assert next_steps["general"] == []

    def test_next_steps_absent_yields_no_filler(self) -> None:
        """Guilt: a draft with no "## Next Steps" section at all must not
        grow one out of filler text."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "No Next Steps",
            "content": "## Facts\nJust the facts.",
            "category": "news",
            "relevance_score": 50,
        }
        result = convert_staging_to_enriched_article(data)
        next_steps = result["next_steps"]
        assert next_steps == {"expat": [], "investor": [], "general": []}

    def test_extra_sections_preserved_in_draft_order(self) -> None:
        """Guilt: the GloBE article (2026-09-23) lost its "## In Practice"
        and "## Sources" sections — the converter only ever extracted
        Summary/Facts/Bali Zero Take/Next Steps and silently dropped any
        other "##" section. Every other section must survive, in order,
        anchored to the mapped section it followed."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "GloBE Registrations",
            "content": (
                "## Facts\nFacts here.\n\n"
                "## In Practice\nPractical detail here.\n\n"
                "## Bali Zero Take\nOur take.\n\n"
                "## Next Steps\n- Do the thing.\n\n"
                "## Sources\n"
                "- [Source One](https://example.com/one)\n"
                "- [Source Two](https://example.com/two)\n"
            ),
            "category": "tax",
            "relevance_score": 92,
        }
        result = convert_staging_to_enriched_article(data)
        extras = result["extra_sections"]
        assert [section["heading"] for section in extras] == ["In Practice", "Sources"]
        in_practice, sources = extras
        assert in_practice["insert_after"] == "facts"
        assert "Practical detail here." in in_practice["body"]
        assert sources["insert_after"] == "next_steps"
        assert "[Source One](https://example.com/one)" in sources["body"]
        assert "[Source Two](https://example.com/two)" in sources["body"]

    def test_extra_sections_do_not_duplicate_mapped_headings(self) -> None:
        """Guilt: Summary/Facts/Bali Zero Take/Next Steps must never also
        appear a second time in extra_sections."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Mapped Only",
            "content": (
                "## Summary\nSum.\n## Facts\nFacts.\n"
                "## Bali Zero Take\nTake.\n## Next Steps\n- Step one here.\n"
            ),
            "category": "news",
            "relevance_score": 50,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["extra_sections"] == []

    def test_draft_without_facts_heading_does_not_emit_sections_twice(self) -> None:
        """Guilt (gate finding F2 on #7322): with no "## Facts" heading the
        whole draft falls back into `facts`, so an unmapped section is
        already there verbatim — carrying it again as an extra section
        printed it twice."""
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "No Facts Heading",
            "content": (
                "Opening paragraph.\n"
                "## In Practice\nWhat this changes for a PT PMA.\n"
                "## Next Steps\n- Confirm the filing deadline.\n"
            ),
            "category": "tax",
            "relevance_score": 60,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["facts"].count("What this changes for a PT PMA.") == 1
        assert result["extra_sections"] == []

    def test_tags_generation(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Important Regulation Update for Businesses",
            "content": "Content.",
            "category": "business",
            "relevance_score": 50,
        }
        result = convert_staging_to_enriched_article(data)
        assert "business" in result["ai_tags"]
        assert len(result["ai_tags"]) <= 5

    def test_defaults(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {}
        result = convert_staging_to_enriched_article(data)
        assert result["title"] == "Untitled"
        assert result["category"] == "news"
        assert result["source"] == "Bali Intel Scraper"

    def test_enriched_at_timestamp(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {"title": "T", "content": "C", "category": "news", "relevance_score": 50}
        result = convert_staging_to_enriched_article(data)
        assert "enriched_at" in result
        assert result["cover_image"] is None

    def test_bali_zero_take_subsections(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Take Article",
            "content": (
                "## Summary\nSum.\n## Facts\nFacts.\n"
                "## Bali Zero Take\n"
                "### Hidden Insight\nHidden text here.\n"
                "### Our Analysis\nAnalysis text here.\n"
                "### Our Advice\nAdvice text here.\n"
                "## Next Steps\n- Step\n"
            ),
            "category": "news",
            "relevance_score": 75,
        }
        result = convert_staging_to_enriched_article(data)
        assert "Hidden text" in result["bali_zero_take"]["hidden_insight"]
        assert "Analysis text" in result["bali_zero_take"]["our_analysis"]
        assert "Advice text" in result["bali_zero_take"]["our_advice"]

    def test_plain_bali_zero_take_is_not_split_mid_word(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        take = "word " * 39 + "IDR 250 million must remain intact.\n\n" + "word " * 90
        result = convert_staging_to_enriched_article(
            {"content": f"## Facts\nFacts.\n## Bali Zero Take\n{take}"}
        )

        assert result["bali_zero_take"] == {
            "hidden_insight": "",
            "our_analysis": take.strip(),
            "our_advice": "",
        }

        from backend.app.routers.article_composer import EnrichedArticle, generate_mdx_content

        mdx = generate_mdx_content(EnrichedArticle(**result), "test-property-tax", None)
        assert take.strip() in mdx
        assert "### Our Analysis" in mdx
        assert "### The Hidden Insight" not in mdx
        assert "### Our Advice" not in mdx

    def test_take_labels_preserve_duplicate_sections_and_do_not_match_prose(self) -> None:
        from backend.app.routers.intel_scraper import _parse_bali_zero_take

        result = _parse_bali_zero_take(
            "### Our Analysis\nOur Advice is to read the full rule.\n"
            "### Hidden Insight\nFirst insight.\n"
            "Hidden Insight: Second insight.\nOur Advice: Check first."
        )

        assert result == {
            "hidden_insight": "First insight.\n\nSecond insight.",
            "our_analysis": "Our Advice is to read the full rule.",
            "our_advice": "Check first.",
        }

    def test_tldr_facts_stop_at_word_boundary(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        facts = "word " * 28 + "IDR 250 million applies."
        result = convert_staging_to_enriched_article({"content": f"## Facts\n{facts}"})

        assert result["tldr"]["what"] == " ".join(["word"] * 28) + "…"

    @pytest.mark.parametrize("heading", ["## Bali Zero Take:", "## Bali Zero's Take"])
    def test_take_heading_variants_preserve_editorial_content(self, heading: str) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        result = convert_staging_to_enriched_article(
            {"content": f"## Facts\nFacts.\n{heading}\nFull editorial analysis."}
        )
        assert result["bali_zero_take"]["our_analysis"] == "Full editorial analysis."

    def test_markdown_take_labels_preserve_sections(self) -> None:
        from backend.app.routers.intel_scraper import _parse_bali_zero_take

        result = _parse_bali_zero_take(
            "### The Hidden Insight\nInsight.\n"
            "  #### Our Analysis\nAnalysis.\n- **Our Advice:** Check first."
        )
        assert result == {
            "hidden_insight": "Insight.",
            "our_analysis": "Analysis.",
            "our_advice": "Check first.",
        }

    def test_missing_take_does_not_reclassify_other_sections(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        result = convert_staging_to_enriched_article(
            {"content": "## Facts\nFacts.\n## Next Steps\n- Check the source."}
        )

        assert result["bali_zero_take"] == {
            "hidden_insight": "",
            "our_analysis": "",
            "our_advice": "",
        }
        from backend.app.routers.article_composer import EnrichedArticle, generate_mdx_content

        mdx = generate_mdx_content(EnrichedArticle(**result), "test-missing-take", None)
        assert "## Bali Zero Take" not in mdx

    def test_partial_take_preserves_unlabelled_prose(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        result = convert_staging_to_enriched_article(
            {"content": "## Bali Zero Take\nOpening context.\n\nOur Advice: Check first."}
        )

        assert result["bali_zero_take"] == {
            "hidden_insight": "",
            "our_analysis": "Opening context.",
            "our_advice": "Check first.",
        }

    def test_explicit_summary_stops_at_word_boundary(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        result = convert_staging_to_enriched_article(
            {"content": "## Summary\n" + "word " * 55 + "250million applies."}
        )

        assert result["ai_summary"] == " ".join(["word"] * 55) + "…"


# ---------------------------------------------------------------------------
# Helper: ingest_intel_to_qdrant
# ---------------------------------------------------------------------------


class TestIngestIntelToQdrant:
    @pytest.mark.asyncio
    async def test_item_not_found(self) -> None:
        from backend.app.routers.intel_scraper import ingest_intel_to_qdrant

        with patch("backend.app.routers.intel_scraper.staging_service") as mock_svc:
            mock_svc.load_staging_item.return_value = None
            result = await ingest_intel_to_qdrant("item-1", "news")
        assert result is False

    @pytest.mark.asyncio
    async def test_no_collection(self) -> None:
        from backend.app.routers.intel_scraper import ingest_intel_to_qdrant

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_svc,
            patch("backend.app.routers.intel_scraper.INTEL_COLLECTIONS", {}),
        ):
            mock_svc.load_staging_item.return_value = {"title": "T", "content": "C"}
            result = await ingest_intel_to_qdrant("item-1", "unknown_type")
        assert result is False

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from backend.app.routers.intel_scraper import ingest_intel_to_qdrant

        mock_embedder = MagicMock()
        mock_embedder.generate_single_embedding = AsyncMock(return_value=[0.1] * 1536)

        mock_qdrant = MagicMock()
        mock_qdrant.upsert_documents = AsyncMock(return_value=None)

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_svc,
            patch("backend.app.routers.intel_scraper.INTEL_COLLECTIONS", {"news": "intel_news"}),
            patch("backend.app.routers.intel_scraper.get_embedder", return_value=mock_embedder),
            patch("backend.app.routers.intel_scraper.QdrantClient", return_value=mock_qdrant),
        ):
            mock_svc.load_staging_item.return_value = {
                "title": "Test Article",
                "content": "Some content",
                "source_url": "https://example.com",
                "category": "news",
                "source_name": "scraper",
                "relevance_score": 80,
            }
            result = await ingest_intel_to_qdrant("item-1", "news")
        assert result is True

    @pytest.mark.asyncio
    async def test_qdrant_exception(self) -> None:
        from backend.app.routers.intel_scraper import ingest_intel_to_qdrant

        mock_embedder = MagicMock()
        mock_embedder.generate_single_embedding = AsyncMock(return_value=[0.1] * 1536)

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_svc,
            patch("backend.app.routers.intel_scraper.INTEL_COLLECTIONS", {"news": "intel_news"}),
            patch("backend.app.routers.intel_scraper.get_embedder", return_value=mock_embedder),
            patch(
                "backend.app.routers.intel_scraper.QdrantClient",
                side_effect=Exception("Qdrant down"),
            ),
        ):
            mock_svc.load_staging_item.return_value = {"title": "T", "content": "C"}
            result = await ingest_intel_to_qdrant("item-1", "news")
        assert result is False


# ---------------------------------------------------------------------------
# Endpoint: register_notification
# ---------------------------------------------------------------------------


class TestRegisterNotification:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from backend.app.routers.intel import RegisterNotificationRequest
        from backend.app.routers.intel_scraper import register_notification

        mock_handler = MagicMock()
        mock_handler.register_notification = MagicMock()

        with patch("backend.services.intel.intel_cover_handler.intel_cover_handler", mock_handler):
            req = RegisterNotificationRequest(
                telegram_message_id=123,
                chat_id=456,
                intel_type="news",
                item_id="news-2026-01",
                title="Test",
            )
            result = await register_notification(request=req, _api_key_verified=None)

        assert result["success"] is True
        assert result["message_id"] == 123
        mock_handler.register_notification.assert_called_once()


# ---------------------------------------------------------------------------
# Endpoint: submit_from_scraper
# ---------------------------------------------------------------------------


class TestSubmitFromScraper:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_submitted") as mock_metric,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "visa"
            mock_stg.generate_item_id.return_value = "visa-2026-test"
            mock_stg.check_duplicate.return_value = None
            mock_stg.save_staging_item.return_value = "/tmp/staging/visa/visa-2026-test.json"
            mock_stg.update_staging_queue_metrics = MagicMock()
            mock_metric.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="New visa rule",
                content="## Summary\nNew rule.\n## Facts\nEffective.",
                source_url="https://example.com",
                source_name="test-scraper",
                category="visa",
                relevance_score=80,
                extraction_method="auto",
                tier="tier1",
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True
        assert result["intel_type"] == "visa"
        assert result["duplicate"] is False

    @pytest.mark.asyncio
    async def test_duplicate(self) -> None:
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup"
            mock_stg.check_duplicate.return_value = {"item_id": "news-2026-existing"}
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Duplicate",
                content="Content",
                source_url="https://example.com/dup",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["duplicate"] is True
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_duplicate_backfills_enrichment_when_existing_item_lacks_it(self) -> None:
        """GUILT (round-2 red-team MUST-FIX #3, scar family #9): a
        duplicate hit against an existing staging item with no usable
        enrichment must be healed in place when the new submission carries
        one — the early-return dedup response happens BEFORE staging_data
        is built, so without this fix the existing item's future draft
        would stay stuck at {} forever (7-day dedup window)."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup"
            existing_item = {
                "item_id": "news-2026-existing",
                "title": "Existing",
                "source_url": "https://example.com/dup",
                "enrichment": {},
            }
            mock_stg.check_duplicate.return_value = existing_item
            mock_stg.backfill_enrichment_if_absent.return_value = True
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            enrichment_obj = {
                "the_facts": "Fresh facts.",
                "bali_zero_take": "Fresh take.",
            }
            submission = ScraperSubmission(
                title="Duplicate with enrichment",
                content="Content",
                source_url="https://example.com/dup",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
                enrichment=enrichment_obj,
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["duplicate"] is True
        assert result["success"] is True
        assert result["enrichment_backfilled"] is True
        # Merge goes through the locked helper (W-L610), not a raw load/save —
        # see backfill_enrichment_if_absent in intel_staging_service.py.
        mock_stg.backfill_enrichment_if_absent.assert_called_once_with(
            "news", "news-2026-existing", enrichment_obj
        )

    @pytest.mark.asyncio
    async def test_duplicate_skips_backfill_when_existing_already_has_enrichment(
        self,
    ) -> None:
        """INNOCENCE: an existing duplicate that ALREADY carries a
        non-empty enrichment dict must not be overwritten. The router no
        longer short-circuits on the (possibly stale, read-outside-any-lock)
        `duplicate` snapshot's own `enrichment` field — that pre-check was
        itself part of the W-L610 race — so it still calls the atomic
        `backfill_enrichment_if_absent` helper, which re-checks under its
        per-item lock and correctly no-ops here."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup2"
            mock_stg.check_duplicate.return_value = {
                "item_id": "news-2026-existing2",
                "enrichment": {"the_facts": "Already there."},
            }
            mock_stg.backfill_enrichment_if_absent.return_value = False
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            new_enrichment = {"the_facts": "New but should not overwrite."}
            submission = ScraperSubmission(
                title="Duplicate again",
                content="Content",
                source_url="https://example.com/dup2",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
                enrichment=new_enrichment,
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["duplicate"] is True
        assert "enrichment_backfilled" not in result
        mock_stg.backfill_enrichment_if_absent.assert_called_once_with(
            "news", "news-2026-existing2", new_enrichment
        )

    @pytest.mark.asyncio
    async def test_duplicate_skips_backfill_when_existing_is_published(self) -> None:
        """INNOCENCE (round-3 NICE fix, scar family #9): a duplicate hit
        against an existing staging item that is already `status: published`
        must NOT be healed even when it lacks enrichment and the new
        submission carries one. Published items still live in the staging
        root (the Telegram-quorum publish path never archives them), so an
        unconditional heal would write to a closed/live record. No
        downstream reader depends on this today (topic-selector filters
        status=="pending"), but the write itself must not happen."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup4"
            mock_stg.check_duplicate.return_value = {
                "item_id": "news-2026-existing4",
                "enrichment": {},
                "status": "published",
            }
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Duplicate against published item",
                content="Content",
                source_url="https://example.com/dup4",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
                enrichment={"the_facts": "New but must not land on a published item."},
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["duplicate"] is True
        assert "enrichment_backfilled" not in result
        mock_stg.load_staging_item.assert_not_called()
        mock_stg.save_staging_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_backfill_failure_does_not_break_dedup_response(self) -> None:
        """Heal-attempt failures must never turn a successful dedup into a
        500 — log and fall through to the unchanged response shape."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup3"
            mock_stg.check_duplicate.return_value = {
                "item_id": "news-2026-existing3",
                "enrichment": {},
            }
            mock_stg.backfill_enrichment_if_absent.side_effect = OSError("disk error")
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Duplicate heal failure",
                content="Content",
                source_url="https://example.com/dup3",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
                enrichment={"the_facts": "New."},
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True
        assert result["duplicate"] is True
        assert "enrichment_backfilled" not in result

    @pytest.mark.asyncio
    async def test_service_error(self) -> None:
        from fastapi import HTTPException

        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with patch("backend.app.routers.intel_scraper.classification_service") as mock_cls:
            mock_cls.classify_intel_type.side_effect = Exception("Classification error")

            submission = ScraperSubmission(
                title="Err",
                content="Content",
                source_url="https://example.com/err",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
            )
            with pytest.raises(HTTPException) as exc_info:
                await submit_from_scraper(submission=submission, _api_key_verified=None)
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_enrichment_persisted(self) -> None:
        """GUILT (WR2 enrichment passthrough, scar family #9): a
        ScraperSubmission carrying a full structured `enrichment` object
        must round-trip it verbatim into staging_data."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_submitted") as mock_metric,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-enriched"
            mock_stg.check_duplicate.return_value = None
            mock_stg.save_staging_item.return_value = "/tmp/staging/news/news-2026-enriched.json"
            mock_stg.update_staging_queue_metrics = MagicMock()
            mock_metric.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            enrichment_obj = {
                "the_facts": "Facts here.",
                "bali_zero_take": "Our take.",
                "thirty_second_brief": "Brief.",
                "faq": [{"q": "Q1", "a": "A1"}],
            }
            submission = ScraperSubmission(
                title="Enriched article",
                content="Content",
                source_url="https://example.com/enriched",
                source_name="test-scraper",
                category="news",
                relevance_score=70,
                extraction_method="auto",
                tier="tier1",
                enrichment=enrichment_obj,
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True
        mock_stg.save_staging_item.assert_called_once()
        staging_data = mock_stg.save_staging_item.call_args[0][2]
        assert staging_data["enrichment"] == enrichment_obj

    @pytest.mark.asyncio
    async def test_enrichment_defaults_to_empty_dict_when_absent(self) -> None:
        """INNOCENCE: a legacy submission WITHOUT `enrichment` must still
        validate (backward-compat) and default to {} in staging_data — not
        crash, not omit the key entirely."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_submitted") as mock_metric,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-legacy"
            mock_stg.check_duplicate.return_value = None
            mock_stg.save_staging_item.return_value = "/tmp/staging/news/news-2026-legacy.json"
            mock_stg.update_staging_queue_metrics = MagicMock()
            mock_metric.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Legacy article",
                content="Content",
                source_url="https://example.com/legacy",
                source_name="test-scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True
        staging_data = mock_stg.save_staging_item.call_args[0][2]
        assert staging_data["enrichment"] == {}

    @pytest.mark.asyncio
    async def test_with_cover_image(self) -> None:
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_submitted") as mock_metric,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-img"
            mock_stg.check_duplicate.return_value = None
            mock_stg.save_staging_item.return_value = "/tmp/staging/news/news-2026-img.json"
            mock_stg.update_staging_queue_metrics = MagicMock()
            mock_metric.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Image article",
                content="Content with image.",
                source_url="https://example.com/img",
                source_name="scraper",
                category="news",
                relevance_score=60,
                extraction_method="auto",
                tier="tier1",
                cover_image="https://example.com/cover.jpg",
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True


# ---------------------------------------------------------------------------
# Endpoint: publish_staging_item
# ---------------------------------------------------------------------------


class TestPublishStagingItem:
    @staticmethod
    def _fake_pool() -> tuple[MagicMock, MagicMock]:
        connection = MagicMock()
        connection.execute = AsyncMock()
        acquired = MagicMock()
        acquired.__aenter__ = AsyncMock(return_value=connection)
        acquired.__aexit__ = AsyncMock(return_value=False)
        pool = MagicMock()
        pool.acquire.return_value = acquired
        return pool, connection

    @pytest.mark.asyncio
    async def test_workspace_cover_is_slug_named_jpeg_before_publish(self, tmp_path) -> None:
        """A workspace PNG reaches the composer as the canonical slug-named JPEG."""
        from backend.app.routers.article_composer import generate_slug
        from backend.app.routers.intel_scraper import publish_staging_item_internal

        title = "Indonesia Activates Global 15% Minimum Tax — Can DJP Deliver?"
        item_id = "news_20260903_173409_3446a476"
        cover_dir = tmp_path / "covers"
        cover_dir.mkdir()
        cover_path = cover_dir / f"{item_id}.png"
        image_output = BytesIO()
        Image.new("RGB", (2100, 900), color="navy").save(image_output, format="PNG")
        cover_path.write_bytes(image_output.getvalue())

        staging_data = {
            "title": title,
            "content": "## Summary\nTax update.\n## Facts\nDetails.\n## Bali Zero Take\nImpact.\n## Next Steps\nAct.",
            "category": "tax",
            "relevance_score": 80,
            "cover_image": f"covers/{item_id}.png",
        }
        publish_response = SimpleNamespace(
            success=True,
            article_url="https://balizero.com/tax-legal/example",
            commit_sha="abc123",
            mdx_path="apps/mouth/src/content/articles/tax-legal/example.mdx",
            pull_request_number=1,
            auto_merge_enabled=True,
            image_path=f"/static/news/{generate_slug(title)}.jpg",
        )
        pool, connection = self._fake_pool()

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_staging,
            patch("backend.app.routers.intel_scraper.intel_user_actions_total") as mock_metric,
            patch(
                "backend.app.routers.intel_scraper.ingest_intel_to_qdrant",
                new=AsyncMock(return_value=True),
            ),
            patch("backend.app.routers.intel_scraper.invalidate_cache", new=AsyncMock()),
            patch(
                "backend.app.routers.article_composer.publish_article_internal",
                new=AsyncMock(return_value=publish_response),
            ) as mock_publish,
        ):
            mock_staging.load_staging_item.return_value = staging_data
            mock_staging.get_staging_dir.return_value = tmp_path
            mock_metric.labels.return_value.inc = MagicMock()

            result = await publish_staging_item_internal(
                "news", item_id, actor="test", allow_generated_cover=False, pool=pool
            )

        assert result["success"] is True
        request = mock_publish.await_args.args[0]
        assert request.cover_image_filename == f"{generate_slug(title)}.jpg"
        assert base64.b64decode(request.cover_image_base64).startswith(b"\xff\xd8")
        calls_by_statement = {
            call.args[0]: call.args for call in connection.execute.await_args_list
        }
        news_args = next(
            args for statement, args in calls_by_statement.items() if "INSERT INTO news_items" in statement
        )
        queue_args = next(
            args
            for statement, args in calls_by_statement.items()
            if "INSERT INTO post_publish_queue" in statement
        )
        assert news_args[2] == "example"
        assert news_args[9] == "/static/news/example.jpg"
        assert queue_args[1] == "example"
        # news_items.slug carries no unique constraint on prod: ON CONFLICT (slug)
        # raises InvalidColumnReferenceError there, so the insert must be guarded
        # by existence instead (measured 2026-09-04).
        assert "ON CONFLICT" not in news_args[0]
        assert "WHERE NOT EXISTS (SELECT 1 FROM news_items WHERE slug = $2)" in news_args[0]

    @pytest.mark.asyncio
    async def test_internal_publish_without_pool_keeps_returning_successfully(self, tmp_path) -> None:
        from backend.app.routers.intel_scraper import publish_staging_item_internal

        _unused_pool, connection = self._fake_pool()
        item_id = "news-without-pool"
        cover_dir = tmp_path / "covers"
        cover_dir.mkdir()
        image_output = BytesIO()
        Image.new("RGB", (1200, 630), color="navy").save(image_output, format="PNG")
        (cover_dir / f"{item_id}.png").write_bytes(image_output.getvalue())
        staging_data = {
            "title": "Article without a database pool",
            "content": "Content for the published article.",
            "category": "business",
            "relevance_score": 80,
            "cover_image": f"covers/{item_id}.png",
        }
        publish_response = SimpleNamespace(
            success=True,
            article_url="https://balizero.com/business/no-pool",
            commit_sha="abc123",
            mdx_path="apps/mouth/src/content/articles/business/no-pool.mdx",
            pull_request_number=1,
            auto_merge_enabled=True,
            image_path=None,
        )

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_staging,
            patch("backend.app.routers.intel_scraper.intel_user_actions_total") as mock_metric,
            patch(
                "backend.app.routers.intel_scraper.ingest_intel_to_qdrant",
                new=AsyncMock(return_value=True),
            ),
            patch("backend.app.routers.intel_scraper.invalidate_cache", new=AsyncMock()),
            patch(
                "backend.app.routers.article_composer.publish_article_internal",
                new=AsyncMock(return_value=publish_response),
            ),
        ):
            mock_staging.load_staging_item.return_value = staging_data
            mock_staging.get_staging_dir.return_value = tmp_path
            mock_metric.labels.return_value.inc = MagicMock()

            result = await publish_staging_item_internal(
                "news", item_id, actor="test", allow_generated_cover=False, pool=None
            )

        assert result["success"] is True
        connection.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        from fastapi import HTTPException

        from backend.app.routers.intel_scraper import publish_staging_item_internal

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_user_actions_total") as mock_metric,
        ):
            mock_stg.load_staging_item.return_value = None
            mock_metric.labels.return_value.inc = MagicMock()

            with pytest.raises(HTTPException) as exc_info:
                await publish_staging_item_internal("news", "nonexistent", actor="test")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_qdrant_failure(self) -> None:
        from fastapi import HTTPException

        from backend.app.routers.intel_scraper import publish_staging_item_internal

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_user_actions_total") as mock_metric,
            patch(
                "backend.app.routers.intel_scraper.ingest_intel_to_qdrant",
                new=AsyncMock(return_value=False),
            ),
        ):
            mock_stg.load_staging_item.return_value = {
                "title": "T",
                "content": "C",
                "category": "news",
            }
            mock_metric.labels.return_value.inc = MagicMock()

            with pytest.raises(HTTPException) as exc_info:
                await publish_staging_item_internal("news", "item-1", actor="test")
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_github_publish_failure_appends_cause(self, monkeypatch) -> None:
        """A 301 owner-redirect surfaced as publish_result.error must reach the
        News Room message, not just the backend log (2026-08-28, 2026-09-04)."""
        from backend.app.routers.article_composer import PublishResponse
        from backend.app.routers.intel_scraper import publish_staging_item_internal

        monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)

        failed_result = PublishResponse(
            success=False,
            message="GitHub publish failed",
            error="Failed to look up publication pull request: 301",
        )

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_user_actions_total") as mock_metric,
            patch(
                "backend.app.routers.intel_scraper.ingest_intel_to_qdrant",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "backend.app.routers.article_composer.publish_article_internal",
                new=AsyncMock(return_value=failed_result),
            ),
        ):
            mock_stg.load_staging_item.return_value = {
                "title": "New Visa Rule",
                "content": "## Summary\nNew rule.\n## Facts\nEffective Jan 2026.",
                "category": "visa",
                "relevance_score": 80,
                "source_url": "https://example.com",
            }
            mock_stg.save_staging_item.return_value = None
            mock_metric.labels.return_value.inc = MagicMock()

            result = await publish_staging_item_internal(
                "news", "item-1", actor="test"
            )

            assert result["success"] is False
            assert result["github_published"] is False
            assert (
                "Cause: Failed to look up publication pull request: 301" in result["message"]
            )

    @pytest.mark.asyncio
    async def test_github_publish_exception_appends_cause(self, monkeypatch) -> None:
        """Regression guard: the except-branch used to build ``github_error``
        with ``type(e).__name__``, but ``type`` is this function's route
        parameter (shadows the builtin) and would raise TypeError instead of
        recording the cause."""
        from backend.app.routers.intel_scraper import publish_staging_item_internal

        monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_user_actions_total") as mock_metric,
            patch(
                "backend.app.routers.intel_scraper.ingest_intel_to_qdrant",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "backend.app.routers.article_composer.publish_article_internal",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            mock_stg.load_staging_item.return_value = {
                "title": "New Visa Rule",
                "content": "## Summary\nNew rule.\n## Facts\nEffective Jan 2026.",
                "category": "visa",
                "relevance_score": 80,
                "source_url": "https://example.com",
            }
            mock_stg.save_staging_item.return_value = None
            mock_metric.labels.return_value.inc = MagicMock()

            result = await publish_staging_item_internal(
                "news", "item-1", actor="test"
            )

            assert result["success"] is False
            assert "Cause: RuntimeError: boom" in result["message"]


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


class TestModuleConstants:
    def test_router_exists(self) -> None:
        from backend.app.routers.intel_scraper import router

        assert router is not None
        assert router.tags == ["intel-scraper"]
