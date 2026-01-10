"""
Tests for preview_generator.py - BaliZero Article Preview Generator
Covers: PreviewArticle, BaliZeroPreviewGenerator, helper functions
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import tempfile
import os

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from preview_generator import (
    PreviewArticle,
    BaliZeroPreviewGenerator,
    CATEGORY_COLORS,
    generate_article_id,
    create_preview_from_pipeline,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_preview_article():
    """Sample PreviewArticle for testing"""
    return PreviewArticle(
        article_id="test123abc",
        title="Indonesia Extends Digital Nomad Visa to 5 Years",
        subtitle="A groundbreaking policy change for remote workers",
        content="""## Executive Summary

The Indonesian government has extended the Digital Nomad Visa validity.

## Key Changes

- **Validity**: Extended to 5 years
- **Cost**: $500 USD
- **Requirements**: $2,000/month income

### Who Benefits

1. Remote workers
2. Freelancers
3. Digital nomads
""",
        category="immigration",
        source="Jakarta Post",
        source_url="https://jakartapost.com/news/visa",
        cover_image="https://images.unsplash.com/photo-123",
        published_at="2026-01-11T10:00:00Z",
        reading_time=5,
        keywords=["visa", "digital nomad", "Indonesia"],
        key_entities=["Indonesia", "Immigration", "BKPM"],
        faq_items=[
            {"question": "How long is the visa valid?", "answer": "5 years"},
            {"question": "What is the cost?", "answer": "$500 USD"},
        ],
        tldr_summary="Indonesia extended digital nomad visa to 5 years",
        schema_json_ld='{"@type": "NewsArticle"}',
        relevance_score=92,
        reviewed_by="Marco Rossi",
    )


@pytest.fixture
def minimal_preview_article():
    """Minimal PreviewArticle with required fields only"""
    return PreviewArticle(
        article_id="min123",
        title="Test Article",
        subtitle="",
        content="Simple content",
        category="general",
        source="Test",
        source_url="https://test.com",
        cover_image="",
        published_at="2026-01-11",
        reading_time=2,
        keywords=[],
        key_entities=[],
        faq_items=[],
        tldr_summary="",
        schema_json_ld="{}",
    )


@pytest.fixture
def generator_with_temp_dir():
    """BaliZeroPreviewGenerator with temporary output directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield BaliZeroPreviewGenerator(output_dir=tmpdir), tmpdir


# =============================================================================
# CATEGORY_COLORS TESTS
# =============================================================================


class TestCategoryColors:
    """Test category color constants"""

    def test_all_expected_categories_present(self):
        """Verify all expected categories exist"""
        expected = ["immigration", "business", "tax", "property", "lifestyle", "tech"]
        for cat in expected:
            assert cat in CATEGORY_COLORS

    def test_category_has_required_keys(self):
        """Each category should have primary, bg, and name"""
        for cat, data in CATEGORY_COLORS.items():
            assert "primary" in data, f"{cat} missing primary"
            assert "bg" in data, f"{cat} missing bg"
            assert "name" in data, f"{cat} missing name"

    def test_primary_is_valid_hex(self):
        """Primary colors should be valid hex codes"""
        for cat, data in CATEGORY_COLORS.items():
            assert data["primary"].startswith("#"), f"{cat} primary not hex"
            assert len(data["primary"]) == 7, f"{cat} primary wrong length"

    def test_bg_is_rgba(self):
        """Background colors should be rgba format"""
        for cat, data in CATEGORY_COLORS.items():
            assert "rgba(" in data["bg"], f"{cat} bg not rgba"


# =============================================================================
# PreviewArticle TESTS
# =============================================================================


class TestPreviewArticle:
    """Test PreviewArticle dataclass"""

    def test_create_full_article(self, sample_preview_article):
        """Test creating article with all fields"""
        assert sample_preview_article.article_id == "test123abc"
        assert sample_preview_article.title == "Indonesia Extends Digital Nomad Visa to 5 Years"
        assert sample_preview_article.relevance_score == 92
        assert sample_preview_article.reviewed_by == "Marco Rossi"

    def test_create_minimal_article(self, minimal_preview_article):
        """Test creating article with minimal fields"""
        assert minimal_preview_article.article_id == "min123"
        assert minimal_preview_article.relevance_score == 0  # Default
        assert minimal_preview_article.reviewed_by is None  # Default
        assert minimal_preview_article.author == "BaliZero Intelligence"  # Default

    def test_default_author(self):
        """Test default author value"""
        article = PreviewArticle(
            article_id="a1",
            title="Test",
            subtitle="",
            content="Content",
            category="general",
            source="Src",
            source_url="http://test.com",
            cover_image="",
            published_at="2026-01-01",
            reading_time=1,
            keywords=[],
            key_entities=[],
            faq_items=[],
            tldr_summary="",
            schema_json_ld="{}",
        )
        assert article.author == "BaliZero Intelligence"


# =============================================================================
# BaliZeroPreviewGenerator INIT TESTS
# =============================================================================


class TestBaliZeroPreviewGeneratorInit:
    """Test BaliZeroPreviewGenerator initialization"""

    def test_default_output_dir(self):
        """Test default output directory is created"""
        gen = BaliZeroPreviewGenerator()
        assert gen.output_dir.exists()

    def test_custom_output_dir(self):
        """Test custom output directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "custom_previews")
            gen = BaliZeroPreviewGenerator(output_dir=custom_path)
            assert gen.output_dir == Path(custom_path)
            assert gen.output_dir.exists()

    def test_creates_nested_dirs(self):
        """Test creates nested directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "a", "b", "c")
            gen = BaliZeroPreviewGenerator(output_dir=nested)
            assert Path(nested).exists()


# =============================================================================
# HELPER METHOD TESTS
# =============================================================================


class TestGetCategoryStyle:
    """Test _get_category_style method"""

    def test_known_category(self):
        """Test known category returns correct style"""
        gen = BaliZeroPreviewGenerator()
        style = gen._get_category_style("immigration")
        assert style["primary"] == "#2251ff"
        assert "Immigration" in style["name"]

    def test_unknown_category_returns_general(self):
        """Test unknown category falls back to general"""
        gen = BaliZeroPreviewGenerator()
        style = gen._get_category_style("unknown_category")
        assert style == CATEGORY_COLORS["general"]

    def test_case_insensitive(self):
        """Test category lookup is case insensitive"""
        gen = BaliZeroPreviewGenerator()
        style1 = gen._get_category_style("IMMIGRATION")
        style2 = gen._get_category_style("immigration")
        assert style1 == style2

    def test_with_spaces(self):
        """Test category with spaces converted to dashes"""
        gen = BaliZeroPreviewGenerator()
        style = gen._get_category_style("tax legal")
        # Should convert "tax legal" to "tax-legal"
        assert "primary" in style


class TestSlugify:
    """Test _slugify method"""

    def test_basic_slugify(self):
        """Test basic text slugification"""
        gen = BaliZeroPreviewGenerator()
        assert gen._slugify("Hello World") == "hello-world"

    def test_special_chars_removed(self):
        """Test special characters are removed"""
        gen = BaliZeroPreviewGenerator()
        assert gen._slugify("Hello! World?") == "hello-world"

    def test_multiple_spaces_collapsed(self):
        """Test multiple spaces become single dash"""
        gen = BaliZeroPreviewGenerator()
        assert gen._slugify("Hello   World") == "hello-world"

    def test_length_limit(self):
        """Test slug is limited to 50 chars"""
        gen = BaliZeroPreviewGenerator()
        long_text = "a" * 100
        assert len(gen._slugify(long_text)) <= 50

    def test_leading_trailing_dashes_removed(self):
        """Test leading/trailing dashes are removed"""
        gen = BaliZeroPreviewGenerator()
        assert gen._slugify("---hello---") == "hello"


class TestMarkdownToHtml:
    """Test _markdown_to_html method"""

    def test_headers_converted(self):
        """Test markdown headers converted to HTML"""
        gen = BaliZeroPreviewGenerator()
        result = gen._markdown_to_html("## Test Header")
        assert "<h2" in result
        assert "Test Header" in result

    def test_bold_converted(self):
        """Test bold markdown converted"""
        gen = BaliZeroPreviewGenerator()
        result = gen._markdown_to_html("**bold text**")
        assert "<strong>bold text</strong>" in result

    def test_italic_converted(self):
        """Test italic markdown converted"""
        gen = BaliZeroPreviewGenerator()
        result = gen._markdown_to_html("*italic text*")
        assert "<em>italic text</em>" in result

    def test_lists_converted(self):
        """Test list items converted"""
        gen = BaliZeroPreviewGenerator()
        result = gen._markdown_to_html("- Item 1\n- Item 2")
        assert "<li>Item 1</li>" in result
        assert "<ul>" in result

    def test_links_converted(self):
        """Test links converted with target blank"""
        gen = BaliZeroPreviewGenerator()
        result = gen._markdown_to_html("[Link](https://test.com)")
        assert 'href="https://test.com"' in result
        assert 'target="_blank"' in result

    def test_empty_text_returns_empty(self):
        """Test empty text returns empty string"""
        gen = BaliZeroPreviewGenerator()
        assert gen._markdown_to_html("") == ""
        assert gen._markdown_to_html(None) == ""


class TestExtractHeadings:
    """Test _extract_headings method"""

    def test_extract_markdown_headings(self):
        """Test extracting markdown headings"""
        gen = BaliZeroPreviewGenerator()
        content = "# H1\n## H2\n### H3"
        headings = gen._extract_headings(content)
        assert len(headings) >= 3

    def test_heading_has_level_text_id(self):
        """Test each heading has level, text, id"""
        gen = BaliZeroPreviewGenerator()
        headings = gen._extract_headings("## Test Heading")
        assert len(headings) > 0
        h = headings[0]
        assert "level" in h
        assert "text" in h
        assert "id" in h

    def test_empty_content_returns_empty(self):
        """Test empty content returns empty list"""
        gen = BaliZeroPreviewGenerator()
        assert gen._extract_headings("") == []


class TestGenerateTldrHtml:
    """Test _generate_tldr_html method"""

    def test_with_summary(self):
        """Test generates HTML with summary"""
        gen = BaliZeroPreviewGenerator()
        result = gen._generate_tldr_html("Test summary")
        assert "tldr-box" in result
        assert "Test summary" in result

    def test_empty_summary_returns_empty(self):
        """Test empty summary returns empty string"""
        gen = BaliZeroPreviewGenerator()
        assert gen._generate_tldr_html("") == ""
        assert gen._generate_tldr_html(None) == ""


class TestGenerateCoverImageHtml:
    """Test _generate_cover_image_html method"""

    def test_with_image(self):
        """Test generates HTML with image"""
        gen = BaliZeroPreviewGenerator()
        result = gen._generate_cover_image_html("https://img.com/test.jpg", "Test Alt")
        assert "cover-image-container" in result
        assert "https://img.com/test.jpg" in result
        assert "Test Alt" in result

    def test_empty_image_returns_empty(self):
        """Test empty image returns empty string"""
        gen = BaliZeroPreviewGenerator()
        assert gen._generate_cover_image_html("", "Title") == ""
        assert gen._generate_cover_image_html(None, "Title") == ""


# =============================================================================
# PREVIEW GENERATION TESTS
# =============================================================================


class TestGeneratePreview:
    """Test generate_preview method"""

    def test_returns_html_string(self, sample_preview_article):
        """Test returns valid HTML string"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_contains_title(self, sample_preview_article):
        """Test HTML contains article title"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert sample_preview_article.title in html

    def test_contains_category_badge(self, sample_preview_article):
        """Test HTML contains category badge"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert "category-badge" in html

    def test_contains_preview_banner(self, sample_preview_article):
        """Test HTML contains preview banner"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert "preview-banner" in html
        assert "PREVIEW MODE" in html

    def test_contains_approve_reject_buttons(self, sample_preview_article):
        """Test HTML contains approve/reject buttons"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert "Approve" in html
        assert "Reject" in html

    def test_contains_article_content(self, sample_preview_article):
        """Test HTML contains article content"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert "article-content" in html

    def test_contains_source_link(self, sample_preview_article):
        """Test HTML contains source link"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert sample_preview_article.source in html
        assert sample_preview_article.source_url in html

    def test_contains_score_badge(self, sample_preview_article):
        """Test HTML contains score badge"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert "score-badge" in html
        assert str(sample_preview_article.relevance_score) in html

    def test_contains_review_badge_when_reviewed(self, sample_preview_article):
        """Test HTML contains review badge when reviewed_by is set"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert "review-badge" in html
        assert sample_preview_article.reviewed_by in html

    def test_no_review_badge_when_not_reviewed(self, minimal_preview_article):
        """Test no review badge when reviewed_by is None"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(minimal_preview_article)
        assert "Reviewed by" not in html

    def test_contains_faq_section(self, sample_preview_article):
        """Test HTML contains FAQ section"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert "faq-section" in html
        assert "Frequently Asked Questions" in html

    def test_no_faq_content_when_empty(self, minimal_preview_article):
        """Test no FAQ content when faq_items is empty"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(minimal_preview_article)
        # CSS class for styles exists, but no FAQ items content
        assert '<div class="faq-item">' not in html
        assert "accordion-btn" not in html or "faq-question" not in html

    def test_contains_keywords(self, sample_preview_article):
        """Test HTML contains keywords"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        for kw in sample_preview_article.keywords[:3]:
            assert kw in html

    def test_contains_schema_jsonld(self, sample_preview_article):
        """Test HTML contains schema.org JSON-LD"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert 'application/ld+json' in html

    def test_dark_theme_colors(self, sample_preview_article):
        """Test HTML uses dark theme colors"""
        gen = BaliZeroPreviewGenerator()
        html = gen.generate_preview(sample_preview_article)
        assert "#0c1f3a" in html  # Primary dark color
        assert "#0a1f3a" in html  # Secondary dark color


class TestSavePreview:
    """Test save_preview method"""

    def test_saves_file(self, sample_preview_article, generator_with_temp_dir):
        """Test saves HTML file"""
        gen, tmpdir = generator_with_temp_dir
        filepath = gen.save_preview(sample_preview_article)
        assert os.path.exists(filepath)

    def test_filename_matches_article_id(self, sample_preview_article, generator_with_temp_dir):
        """Test filename matches article_id"""
        gen, tmpdir = generator_with_temp_dir
        filepath = gen.save_preview(sample_preview_article)
        assert sample_preview_article.article_id in filepath
        assert filepath.endswith(".html")

    def test_file_contains_html(self, sample_preview_article, generator_with_temp_dir):
        """Test saved file contains valid HTML"""
        gen, tmpdir = generator_with_temp_dir
        filepath = gen.save_preview(sample_preview_article)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "<!DOCTYPE html>" in content


class TestGetPreviewUrl:
    """Test get_preview_url method"""

    def test_default_base_url(self):
        """Test default base URL"""
        gen = BaliZeroPreviewGenerator()
        url = gen.get_preview_url("abc123")
        assert url == "https://bali-intel-scraper.fly.dev/preview/abc123"

    def test_custom_base_url(self):
        """Test custom base URL"""
        gen = BaliZeroPreviewGenerator()
        url = gen.get_preview_url("abc123", base_url="https://custom.com")
        assert url == "https://custom.com/preview/abc123"


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestGenerateArticleId:
    """Test generate_article_id function"""

    def test_returns_string(self):
        """Test returns string"""
        result = generate_article_id("Title", "https://test.com")
        assert isinstance(result, str)

    def test_length_12_chars(self):
        """Test returns 12 character ID"""
        result = generate_article_id("Title", "https://test.com")
        assert len(result) == 12

    def test_deterministic(self):
        """Test same inputs produce same output"""
        id1 = generate_article_id("Title", "https://test.com")
        id2 = generate_article_id("Title", "https://test.com")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        """Test different inputs produce different IDs"""
        id1 = generate_article_id("Title1", "https://test1.com")
        id2 = generate_article_id("Title2", "https://test2.com")
        assert id1 != id2


class TestCreatePreviewFromPipeline:
    """Test create_preview_from_pipeline function"""

    def test_returns_tuple(self):
        """Test returns tuple of (article_id, preview_path)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(BaliZeroPreviewGenerator, '__init__', return_value=None):
                with patch.object(BaliZeroPreviewGenerator, 'save_preview', return_value=f"{tmpdir}/test.html"):
                    result = create_preview_from_pipeline(
                        title="Test",
                        content="Content",
                        category="general",
                        source="Test",
                        source_url="https://test.com",
                        cover_image="https://img.com/test.jpg",
                        seo_metadata={},
                    )
                    assert isinstance(result, tuple)
                    assert len(result) == 2

    def test_uses_seo_metadata(self):
        """Test uses SEO metadata fields"""
        seo = {
            "meta_description": "Test description",
            "reading_time_minutes": 10,
            "keywords": ["kw1", "kw2"],
            "key_entities": ["ent1"],
            "faq_items": [{"question": "Q", "answer": "A"}],
            "tldr_summary": "TLDR",
            "schema_json_ld": '{"test": true}',
        }
        # This tests the function constructs PreviewArticle correctly
        # by checking it doesn't raise errors with valid SEO metadata
        with patch.object(BaliZeroPreviewGenerator, 'save_preview', return_value="/tmp/test.html"):
            article_id, path = create_preview_from_pipeline(
                title="Test",
                content="Content",
                category="tax",
                source="Source",
                source_url="https://test.com",
                cover_image="https://img.com/x.jpg",
                seo_metadata=seo,
                relevance_score=85,
                reviewed_by="Reviewer",
            )
            assert article_id is not None


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_very_long_title(self):
        """Test handles very long title"""
        gen = BaliZeroPreviewGenerator()
        article = PreviewArticle(
            article_id="test",
            title="A" * 1000,
            subtitle="",
            content="Content",
            category="general",
            source="Test",
            source_url="https://test.com",
            cover_image="",
            published_at="2026-01-01",
            reading_time=1,
            keywords=[],
            key_entities=[],
            faq_items=[],
            tldr_summary="",
            schema_json_ld="{}",
        )
        html = gen.generate_preview(article)
        assert "A" * 100 in html  # At least part of title present

    def test_special_chars_in_content(self):
        """Test handles special characters in content"""
        gen = BaliZeroPreviewGenerator()
        article = PreviewArticle(
            article_id="test",
            title="Test <script>alert(1)</script>",
            subtitle="",
            content="Content with <>&\"' chars",
            category="general",
            source="Test",
            source_url="https://test.com",
            cover_image="",
            published_at="2026-01-01",
            reading_time=1,
            keywords=[],
            key_entities=[],
            faq_items=[],
            tldr_summary="",
            schema_json_ld="{}",
        )
        html = gen.generate_preview(article)
        assert isinstance(html, str)

    def test_invalid_date_format(self):
        """Test handles invalid date gracefully"""
        gen = BaliZeroPreviewGenerator()
        article = PreviewArticle(
            article_id="test",
            title="Test",
            subtitle="",
            content="Content",
            category="general",
            source="Test",
            source_url="https://test.com",
            cover_image="",
            published_at="invalid-date",
            reading_time=1,
            keywords=[],
            key_entities=[],
            faq_items=[],
            tldr_summary="",
            schema_json_ld="{}",
        )
        html = gen.generate_preview(article)
        assert isinstance(html, str)  # Should not crash

    def test_empty_faq_item_fields(self):
        """Test handles FAQ items with empty fields"""
        gen = BaliZeroPreviewGenerator()
        article = PreviewArticle(
            article_id="test",
            title="Test",
            subtitle="",
            content="Content",
            category="general",
            source="Test",
            source_url="https://test.com",
            cover_image="",
            published_at="2026-01-01",
            reading_time=1,
            keywords=[],
            key_entities=[],
            faq_items=[{"question": "", "answer": ""}],
            tldr_summary="",
            schema_json_ld="{}",
        )
        html = gen.generate_preview(article)
        assert "faq-section" in html  # FAQ section should still render
