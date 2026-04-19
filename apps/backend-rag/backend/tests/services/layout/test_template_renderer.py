"""Tests for TemplateRenderer substitution + validation + HTML escaping."""

from __future__ import annotations

import pytest

from backend.services.layout.template_renderer import (
    TemplateRenderer,
    TemplateValidationError,
)
from backend.services.layout.templates import PlatformTemplate


def _renderer() -> TemplateRenderer:
    return TemplateRenderer()


def test_ig_slide_happy_path():
    out = _renderer().render(
        PlatformTemplate.IG_CAROUSEL_SLIDE,
        {
            "slide_num": "2 / 6",
            "headline": "Permenkumham 22/2023",
            "body": "Articolo 51 comma 3.",
            "image_url": "https://example.com/a.jpg",
        },
    )
    assert out.width == 1080
    assert out.height == 1350
    assert out.template == PlatformTemplate.IG_CAROUSEL_SLIDE
    assert "Permenkumham 22/2023" in out.html
    assert "2 / 6" in out.html
    assert "https://example.com/a.jpg" in out.html


def test_missing_required_var_raises():
    with pytest.raises(TemplateValidationError) as exc:
        _renderer().render(
            PlatformTemplate.IG_CAROUSEL_COVER,
            {"kicker": "x", "headline": "h"},  # missing image_url, logo_url
        )
    msg = str(exc.value)
    assert "image_url" in msg
    assert "logo_url" in msg


def test_html_escaping_applied_to_headline():
    out = _renderer().render(
        PlatformTemplate.IG_CAROUSEL_SLIDE,
        {
            "slide_num": "1",
            "headline": '<script>alert("xss")</script>',
            "body": "safe text",
            "image_url": "https://example.com/a.jpg",
        },
    )
    # user content must be escaped
    assert "<script>" not in out.html
    assert "&lt;script&gt;" in out.html


def test_image_url_not_escaped():
    """URLs must NOT be escaped — browser can't resolve &amp; in background-image."""
    url_with_ampersand = "https://example.com/img?a=1&b=2"
    out = _renderer().render(
        PlatformTemplate.IG_CAROUSEL_SLIDE,
        {
            "slide_num": "1",
            "headline": "h",
            "body": "b",
            "image_url": url_with_ampersand,
        },
    )
    assert url_with_ampersand in out.html
    assert "a=1&b=2" in out.html


def test_patch_css_injected_when_provided():
    patch = ".headline { font-size: 42px; /* reason: overflow */ }"
    out = _renderer().render(
        PlatformTemplate.IG_CAROUSEL_SLIDE,
        {
            "slide_num": "1",
            "headline": "h",
            "body": "b",
            "image_url": "https://x/y.jpg",
        },
        patch_css=patch,
    )
    assert patch in out.html
    assert out.patch_css_applied == patch


def test_patch_css_defaults_to_empty():
    out = _renderer().render(
        PlatformTemplate.LINKEDIN_POST,
        {
            "kicker": "k",
            "headline": "h",
            "subhead": "s",
            "image_url": "https://x/y.jpg",
        },
    )
    assert out.patch_css_applied == ""


def test_unknown_vars_are_ignored():
    """String.Template.safe_substitute ignores extras."""
    out = _renderer().render(
        PlatformTemplate.X_THREAD_IMAGE,
        {
            "kicker": "Compliance",
            "headline": "B211A",
            "image_url": "https://x/y.jpg",
            "extra_unused_var": "whatever",
        },
    )
    assert "B211A" in out.html


def test_newsletter_uses_table_structure_after_render():
    out = _renderer().render(
        PlatformTemplate.NEWSLETTER,
        {
            "kicker": "settimanale",
            "headline": "Roundup #1",
            "body": "Cinque cose che contano",
            "image_url": "https://x/cover.jpg",
        },
    )
    assert "<table" in out.html
    assert "Roundup #1" in out.html
