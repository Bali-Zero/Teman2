"""Tests for Sprint 19 MdxExtras + extended frontmatter + reading-time."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from backend.services.publisher.base import DraftPayload, SlidePayload
from backend.services.publisher.mdx_template import (
    WORDS_PER_MINUTE,
    MdxExtras,
    calculate_reading_time_min,
    render_frontmatter,
    render_full_mdx,
)
from backend.services.war_room.models import RegisterTone

DID = UUID("12345678-1234-1234-1234-123456789abc")


def _draft(main_caption: str = "Una lettura.") -> DraftPayload:
    return DraftPayload(
        draft_id=DID,
        topic="Permenkumham 22/2023",
        tone_register=RegisterTone.TECNICO,
        cover_image_url="https://tigris/c.png",
        main_caption=main_caption,
        slides=[
            SlidePayload(
                slide_number=2,
                image_url="https://tigris/s1.png",
                caption="Slide A",
                final_text="body A " * 50,
            ),
        ],
        hashtags=["KBLI"],
    )


# ── calculate_reading_time_min ────────────────────────────


def test_reading_time_empty_is_one():
    assert calculate_reading_time_min("") == 1
    assert calculate_reading_time_min(None) == 1


def test_reading_time_short_text_is_one():
    assert calculate_reading_time_min("hello world") == 1


def test_reading_time_scales_with_length():
    text = "word " * (WORDS_PER_MINUTE * 4)
    assert calculate_reading_time_min(text) >= 4


def test_reading_time_never_zero():
    assert calculate_reading_time_min("a") >= 1


# ── extras rendering ───────────────────────────────────────


def test_frontmatter_without_extras_stays_unchanged():
    fm = render_frontmatter(
        title="T",
        slug="s",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        tone_register=None,
        cover_image_url="",
        hashtags=[],
        draft_id=DID,
    )
    # extras fields absent
    assert "dossier_id" not in fm
    assert "source_theses" not in fm
    assert "composite_score" not in fm
    assert "reading_time_min" not in fm
    assert "category" not in fm


def test_frontmatter_with_dossier_and_score():
    fm = render_frontmatter(
        title="T",
        slug="s",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        tone_register=None,
        cover_image_url="",
        hashtags=[],
        draft_id=DID,
        extras=MdxExtras(
            dossier_id="doss-123",
            composite_score=0.784,
            category="visa",
            reading_time_min=4,
        ),
    )
    assert 'dossier_id: "doss-123"' in fm
    assert "composite_score: 0.784" in fm
    assert 'category: "visa"' in fm
    assert "reading_time_min: 4" in fm


def test_frontmatter_source_theses_caps_at_ten():
    extras = MdxExtras(source_theses=[f"thesis-{i}" for i in range(20)])
    fm = render_frontmatter(
        title="T", slug="s",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        tone_register=None, cover_image_url="",
        hashtags=[], draft_id=DID, extras=extras,
    )
    # Should contain at most 10 theses (cap from impl)
    assert 'thesis-0' in fm
    assert 'thesis-9' in fm
    assert 'thesis-10' not in fm


def test_frontmatter_composite_score_clamped():
    fm_hi = render_frontmatter(
        title="T", slug="s",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        tone_register=None, cover_image_url="",
        hashtags=[], draft_id=DID,
        extras=MdxExtras(composite_score=1.5),
    )
    assert "composite_score: 1.000" in fm_hi

    fm_lo = render_frontmatter(
        title="T", slug="s",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        tone_register=None, cover_image_url="",
        hashtags=[], draft_id=DID,
        extras=MdxExtras(composite_score=-0.5),
    )
    assert "composite_score: 0.000" in fm_lo


def test_frontmatter_escapes_dossier_id():
    extras = MdxExtras(dossier_id='ab"cd')
    fm = render_frontmatter(
        title="T", slug="s",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        tone_register=None, cover_image_url="",
        hashtags=[], draft_id=DID, extras=extras,
    )
    assert 'dossier_id: "ab\\"cd"' in fm


# ── render_full_mdx + auto_reading_time ────────────────────


def test_full_mdx_with_auto_reading_time():
    draft = _draft(main_caption="word " * 500)
    mdx = render_full_mdx(
        draft,
        slug="slug-abc",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        auto_reading_time=True,
    )
    assert "reading_time_min:" in mdx


def test_full_mdx_without_auto_reading_time_omits_field():
    draft = _draft()
    mdx = render_full_mdx(
        draft,
        slug="slug-abc",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        auto_reading_time=False,
    )
    assert "reading_time_min:" not in mdx


def test_full_mdx_preserves_explicit_extras_reading_time():
    draft = _draft()
    extras = MdxExtras(reading_time_min=99)
    mdx = render_full_mdx(
        draft,
        slug="s",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        extras=extras,
        auto_reading_time=True,  # shouldn't override the explicit value
    )
    assert "reading_time_min: 99" in mdx


def test_full_mdx_extras_merged_with_auto_reading_time():
    draft = _draft(main_caption="word " * 500)
    extras = MdxExtras(dossier_id="doss-1")
    mdx = render_full_mdx(
        draft,
        slug="s",
        published_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        extras=extras,
        auto_reading_time=True,
    )
    assert 'dossier_id: "doss-1"' in mdx
    assert "reading_time_min:" in mdx
