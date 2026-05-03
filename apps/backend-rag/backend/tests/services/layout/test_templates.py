"""Tests for PlatformTemplate registry + TemplateSpec completeness."""

from __future__ import annotations

from backend.services.layout.templates import (
    BRAND_BG,
    BRAND_TEXT_ACCENT,
    BRAND_TEXT_PRIMARY,
    PLATFORM_DEFAULT_TEMPLATE,
    PlatformTemplate,
    get_template,
    list_templates,
)
from backend.services.war_room.models import Platform


def test_all_platform_templates_enumerated():
    assert {t.value for t in PlatformTemplate} == {
        "ig_carousel_cover",
        "ig_carousel_slide",
        "x_thread_image",
        "linkedin_post",
        "newsletter",
    }


def test_all_templates_have_valid_spec():
    for spec in list_templates():
        assert spec.width > 0
        assert spec.height > 0
        assert spec.required_vars
        assert "$patch_css" in spec.html, (
            f"template {spec.name} missing $patch_css slot — patch loop will not work"
        )


def test_ig_cover_dimensions():
    spec = get_template(PlatformTemplate.IG_CAROUSEL_COVER)
    assert spec.width == 1080
    assert spec.height == 1350


def test_ig_slide_dimensions():
    spec = get_template(PlatformTemplate.IG_CAROUSEL_SLIDE)
    assert spec.width == 1080
    assert spec.height == 1350


def test_x_dimensions():
    spec = get_template(PlatformTemplate.X_THREAD_IMAGE)
    assert (spec.width, spec.height) == (1600, 900)


def test_linkedin_dimensions():
    spec = get_template(PlatformTemplate.LINKEDIN_POST)
    assert (spec.width, spec.height) == (1200, 628)


def test_newsletter_email_safe_uses_tables():
    spec = get_template(PlatformTemplate.NEWSLETTER)
    assert "<table" in spec.html


def test_brand_colors_present_in_templates():
    for spec in list_templates():
        if spec.platform_template == PlatformTemplate.NEWSLETTER:
            # newsletter uses hex literals (email-safe), not CSS vars
            assert "#F4A01C" in spec.html
            continue
        assert BRAND_BG in spec.html
        assert BRAND_TEXT_PRIMARY in spec.html
        assert BRAND_TEXT_ACCENT in spec.html


def test_platform_default_template_covers_all_platforms():
    for platform in Platform:
        assert platform in PLATFORM_DEFAULT_TEMPLATE


def test_required_vars_appear_in_template_html():
    """Each declared required var MUST appear as $varname in the template."""
    for spec in list_templates():
        for var in spec.required_vars:
            assert f"${var}" in spec.html, (
                f"{spec.name} declares ${var} but template body doesn't reference it"
            )
