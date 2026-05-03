"""Tests for MDX template + frontmatter builder."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from backend.services.publisher.base import DraftPayload, SlidePayload
from backend.services.publisher.mdx_template import (
    build_slug,
    filename_for,
    render_body,
    render_frontmatter,
    render_full_mdx,
)
from backend.services.war_room.models import RegisterTone

DID = UUID("12345678-1234-1234-1234-123456789abc")


def _draft(slides: int = 2) -> DraftPayload:
    return DraftPayload(
        draft_id=DID,
        topic="Permenkumham 22/2023",
        tone_register=RegisterTone.TECNICO,
        cover_image_url="https://tigris/cover.png",
        main_caption="Una lettura dell'articolo 51 comma 3.",
        slides=[
            SlidePayload(
                slide_number=i + 2,
                image_url=f"https://tigris/s{i}.png",
                caption=f"Slide {i} titolo",
                final_text=f"Body paragraph {i}",
            )
            for i in range(slides)
        ],
        hashtags=["B211A", "Imigrasi"],
    )


# ── build_slug ────────────────────────────────────────────────────


def test_build_slug_basic():
    slug = build_slug("Permenkumham 22/2023", DID)
    assert slug.startswith("permenkumham-22-2023-")
    assert slug.endswith("3456789abc"[-8:])


def test_build_slug_strips_invalid_chars():
    slug = build_slug("!!! Weird --- Title", DID)
    # no consecutive dashes, no leading/trailing
    assert "---" not in slug
    assert not slug.startswith("-")


def test_build_slug_empty_topic_fallback():
    slug = build_slug("", DID)
    assert slug.startswith("war-room-")


def test_build_slug_deterministic():
    assert build_slug("x", DID) == build_slug("x", DID)


def test_build_slug_different_topics_different_slug():
    assert build_slug("a", DID) != build_slug("b", DID)


# ── filename_for ──────────────────────────────────────────────────


def test_filename_includes_date_and_slug():
    dt = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    name = filename_for(dt, "b211a-abcd1234")
    assert name == "2026-04-18-b211a-abcd1234.mdx"


# ── render_frontmatter ────────────────────────────────────────────


def test_frontmatter_contains_required_fields():
    dt = datetime(2026, 4, 18, 9, 30, tzinfo=timezone.utc)
    fm = render_frontmatter(
        title="My title",
        slug="my-slug-aaaa0000",
        published_at=dt,
        tone_register=RegisterTone.ANALITICO,
        cover_image_url="https://x/y.png",
        hashtags=["kbli", "bali"],
        draft_id=DID,
    )
    assert fm.startswith("---")
    assert fm.endswith("---")
    assert 'title: "My title"' in fm
    assert 'date: "2026-04-18T09:30:00Z"' in fm
    assert 'tone_register: "analitico"' in fm
    assert 'cover_image: "https://x/y.png"' in fm
    assert 'hashtags: ["kbli", "bali"]' in fm
    assert f'draft_id: "{DID}"' in fm


def test_frontmatter_escapes_quotes_in_title():
    fm = render_frontmatter(
        title='He said "hi" loud',
        slug="x",
        published_at=datetime.now(timezone.utc),
        tone_register=None,
        cover_image_url="",
        hashtags=[],
        draft_id=DID,
    )
    assert 'title: "He said \\"hi\\" loud"' in fm


def test_frontmatter_handles_missing_register():
    fm = render_frontmatter(
        title="t",
        slug="s",
        published_at=datetime.now(timezone.utc),
        tone_register=None,
        cover_image_url="",
        hashtags=[],
        draft_id=DID,
    )
    assert "tone_register" not in fm


# ── render_body ───────────────────────────────────────────────────


def test_body_has_title_main_cover_sections():
    draft = _draft(slides=2)
    body = render_body(draft)
    assert body.startswith("# Permenkumham 22/2023\n")
    assert "![Permenkumham 22/2023](https://tigris/cover.png)" in body
    assert "## Slide 0 titolo" in body
    assert "## Slide 1 titolo" in body
    assert "Body paragraph 0" in body
    assert "Body paragraph 1" in body


def test_body_escapes_mdx_hazards():
    draft = _draft(slides=0)
    draft.main_caption = "If x < 5 and y > {foo}"
    body = render_body(draft)
    # JSX-sensitive characters escaped
    assert "<" not in body.split("![")[0]  # cover alt shouldn't mask this
    assert "&lt;" in body
    assert "&gt;" in body
    assert "&#123;" in body
    assert "&#125;" in body


def test_body_ends_with_hashtag_line_when_tags_present():
    draft = _draft(slides=0)
    draft.hashtags = ["bali", "kbli"]
    body = render_body(draft)
    assert body.rstrip().endswith("#bali #kbli")


def test_body_without_hashtags_has_no_tag_line():
    draft = _draft(slides=0)
    draft.hashtags = []
    body = render_body(draft)
    assert "#bali" not in body


# ── render_full_mdx ───────────────────────────────────────────────


def test_full_mdx_has_frontmatter_then_body():
    draft = _draft(slides=1)
    dt = datetime(2026, 4, 18, tzinfo=timezone.utc)
    slug = build_slug(draft.topic, draft.draft_id)
    mdx = render_full_mdx(draft, slug=slug, published_at=dt)
    assert mdx.startswith("---\n")
    assert mdx.count("---\n") >= 2  # open + close frontmatter
    assert "# Permenkumham 22/2023" in mdx
    assert f'draft_id: "{DID}"' in mdx
