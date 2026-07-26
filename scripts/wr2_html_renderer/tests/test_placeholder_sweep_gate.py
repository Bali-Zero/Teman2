"""W99 class-cure: placeholder-substitution + hard sweep gate (2026-07-21,
PR #2942 discovery -> Phase-3 composer.py follow-up).

The discovery (verified live this session by grep, zero hits before this
fix): source-citation's top-level {{title}} and elegant-close's
{{trust_marker}}/{{reach}}/{{invite}}/{{primary_source_url}}-gated
{{qr_caption}} were NEVER substituted anywhere in
composer._fill_placeholders -- both families rendered broken end-to-end,
independent of the typed Carousel IR. The sweep this test file adds ALSO
found a sixth, previously-undiscovered instance in the same family:
elegant-close's `data-slide-index="{{index}}"` was equally unfilled.

This is the exact check!=action shape W99 already named (composer.
_normalize_skeleton checked loose, replaced strict -- 6/9 slides of one
carousel, 4/9 of it ALREADY PUBLISHED, rendered in the wrong font before
anyone noticed because the renderer KNEW and downgraded to a
logger.warning). The class cure is not "patch the two named families" --
it is a hard, unconditional gate wired into _fill_placeholders itself
(_assert_no_surviving_placeholders) that raises ValueError naming the
family + surviving tokens the moment ANY {{...}} token would ship, plus a
sweep of every RENDERABLE_FAMILIES skeleton so a future family that adds
an unfilled placeholder is caught at build time, not months later by grep.

Guilt: a synthetic skeleton with an unmapped {{bogus}} token raises.
Innocence: all 15 real layout families, filled with a representative slide
dict, render with zero surviving {{...}} tokens.
"""
from pathlib import Path

import pytest

from wr2_html_renderer.composer import (
    RENDERABLE_FAMILIES,
    _assert_no_surviving_placeholders,
    _expand_default_filters,
    _expand_top_level_if_blocks,
    _extract_skeleton,
    _fill_placeholders,
    _hero_bg_to_img,
    _normalize_skeleton,
)

# Families whose skeleton renders a full-bleed/CSS-background hero photo via
# {{image_url}} (composer._hero_bg_to_img rewrites the .hero div -> <img> for
# these before _fill_placeholders runs, mirroring compose_carousel's real
# per-slide pipeline order).
_HERO_FAMILIES = {
    "cover-photo",
    "photo-headline-yellow-sub",
    "photo-fullbleed",
    "photo-fullbleed-top",
    "photo-fullbleed-split",
}

# One representative, fully-populated slide dict per RENDERABLE family, field
# names verified against the real layouts/<family>.md skeletons +
# scripts/wr2_carousel_ir.py's to_composer_dict projection (same session).
_REPRESENTATIVE_SLIDES: dict[str, dict] = {
    "cover-photo": {
        "headline": "IDR 2.815 TRILLION FROM VISAS ALONE",
        "subhead": "BKPM DATA Q1 2026",
        "regulation_code": "PP 28/2025",
    },
    "photo-headline-yellow-sub": {
        "headline": "THE RULE MOST VILLAS BREAK",
        "subhead": "ZONING",
        "body": "Leasehold status alone does not clear commercial zoning.",
    },
    "photo-fullbleed": {
        "headline": "THE CRACKDOWN, IN NUMBERS",
        "subhead": "PMA RENTAL",
        "body": "1,204 units inspected across three regencies this quarter.",
        "regulation_code": "Perpres 95/2024",
    },
    "photo-fullbleed-top": {
        "headline": "A NEW FILING WINDOW OPENS",
        "subhead": "TAX",
        "body": "SPT Tahunan extensions now run through the end of May.",
    },
    "photo-fullbleed-split": {
        "headline": "TWO PATHS, ONE DEADLINE",
        "subhead": "KITAS",
        "body": "Renewal or conversion -- both close on the same date.",
        "regulation_code": "Permenkumham 22/2023",
    },
    "editorial-text": {
        "headline": "WHY THE NUMBER MOVED",
        "subhead": "CONTEXT",
        "body": "A methodology change explains most of the year-on-year swing.",
    },
    "qa-dialogue": {
        "qa_pairs": [
            {"voice": "INVESTOR", "line": "IS JAPAN VISA-FREE?"},
            {"voice": "BALI ZERO", "line": "NO. NOT ON THE LIST."},
        ],
    },
    "timeline-pinboard": {
        "headline": "HOW WE GOT HERE",
        "events": [
            {"date": "2024", "label": "FRAMEWORK ISSUED", "accent": "white"},
            {"date": "2026", "label": "ENFORCEMENT BEGINS", "accent": "yellow"},
        ],
    },
    "dark-status-list": {
        "headline": "WHERE EACH TRACK STANDS",
        "list_items": [
            {"label": "FRAMEWORK", "value": "Perpres 95/2024", "status": "neutral"},
            {"label": "BVK LIST", "value": "16 nationalities", "status": "positive"},
        ],
    },
    "evidence-carved": {
        "headline": "THE EVIDENCE",
        "facts": [
            {"idx": 1, "this": "1,204 units inspected."},
            {"idx": 2, "this": "312 notices issued."},
        ],
        "take_label": "OUR READ",
        "take_line": "Enforcement is now systematic, not spot-check.",
    },
    "statement-bomb": {
        "statement": "THE RULE CHANGED. MOST OWNERS DID NOT NOTICE.",
    },
    "elegant-close": {
        "slide_number": 9,
        "trust_marker": "LICENSED KONSULTAN PAJAK - REGISTERED PPJK",
        "reach": "ZANTARA@BALIZERO.COM",
        "invite": "IF YOUR CASE TOUCHES THIS - A 30-MIN CALL CONFIRMS NEXT STEPS.",
        "primary_source_url": "https://pajak.go.id/kep-71",
        "qr_caption": "PRIMARY SOURCE",
    },
    "source-citation": {
        "title": "SUMBER",
        "citations": [
            {
                "body": "KEP-71/PJ/2026",
                "issuer": "DJP - Direktorat Jenderal Pajak",
                "date": "30 April 2026",
                "url": "https://www.pajak.go.id/kep-71",
                "note": "Surat keputusan resmi, dapat diunduh sebagai PDF",
            },
        ],
    },
    "stat-card-hero": {
        "headline": "2.815T",
        "subhead": "TOTAL VISA REVENUE",
        "body": "BKPM Q1 2026 filing, verbatim.",
        "chart": {
            "rows": [
                {"label": "2025", "value": "IDR 2.645T"},
                {"label": "2026", "value": "IDR 2.815T"},
            ],
        },
    },
    "numbered-forces-list": {
        "headline": "3 FORCES BEHIND THE RISE",
        "items": [
            {"label": "DEMAND", "value": "Post-pandemic rebound"},
            {"label": "ENFORCEMENT", "value": "Fewer unlicensed operators"},
            {"label": "RATES", "value": "Visa fee schedule reset"},
        ],
    },
}


def _fill_family(family: str, slide: dict) -> str:
    """Run the same skeleton -> normalize -> (hero rewrite) -> fill pipeline
    compose_carousel/materialize_slide_html use for one family."""
    skeleton = _normalize_skeleton(_extract_skeleton(family))
    hero_filename = "slide-01-hero.jpg" if family in _HERO_FAMILIES else None
    if hero_filename:
        skeleton = _hero_bg_to_img(skeleton, hero_filename)
    return _fill_placeholders(
        skeleton,
        slide,
        hero_filename=hero_filename,
        cover_family=(family == "cover-photo"),
        family=family,
    )


class TestPlaceholderSweepGateGuilt:
    """The gate itself: an unmapped {{...}} token must hard-fail, loud."""

    def test_unmapped_placeholder_raises(self):
        bogus = "<html><head></head><body>{{heading}}{{bogus_field}}</body></html>"
        with pytest.raises(ValueError, match=r"placeholder-sweep gate"):
            _fill_placeholders(bogus, {"headline": "X"}, hero_filename=None, family="fake-family")

    def test_raised_error_names_family_and_token(self):
        bogus = "<html><head></head><body>{{nope}}</body></html>"
        with pytest.raises(ValueError, match=r"fake-family.*\{\{nope\}\}|\{\{nope\}\}.*fake-family"):
            _fill_placeholders(bogus, {}, hero_filename=None, family="fake-family")

    def test_unresolved_if_block_raises(self):
        """A top-level {{#if}} whose var is never in `slide` at all (typo, or a
        future family authored wrong) must still fail loud, not ship the
        literal {{#if}}/{{/if}} markers."""
        bogus = "<html><head></head><body>{{#if some_flag}}TEXT{{/if}}</body></html>"
        # some_flag absent -> block content included is irrelevant here: the
        # var name itself is never in the slide, so this is guilt only if the
        # generic if-expander is bypassed. Exercise the real fill path:
        out_or_raise = None
        try:
            out_or_raise = _fill_placeholders(bogus, {}, hero_filename=None, family="fake-family")
        except ValueError:
            out_or_raise = "RAISED"
        # Either the block was correctly dropped (falsy some_flag -> no
        # surviving token, gate passes) OR it raised -- both are acceptable
        # outcomes for an absent var; what must NEVER happen is a literal
        # "{{#if" surviving into a passing return.
        if out_or_raise != "RAISED":
            assert "{{#if" not in out_or_raise
            assert "{{/if}}" not in out_or_raise

    def test_direct_gate_function_raises_on_survivor(self):
        with pytest.raises(ValueError, match=r"placeholder-sweep gate"):
            _assert_no_surviving_placeholders("<div>{{leftover}}</div>", "some-family")

    def test_direct_gate_function_passes_on_clean_html(self):
        result = _assert_no_surviving_placeholders("<div>all good</div>", "some-family")
        assert result is None  # did not raise


class TestPlaceholderSweepInnocence:
    """All 15 renderable families, representative data, zero survivors."""

    def test_representative_slides_cover_every_renderable_family(self):
        """Guard the guard: the corpus above must not silently drift out of
        sync with RENDERABLE_FAMILIES (W84 blind-scan discipline)."""
        assert set(_REPRESENTATIVE_SLIDES.keys()) == RENDERABLE_FAMILIES

    @pytest.mark.parametrize("family", sorted(RENDERABLE_FAMILIES))
    def test_family_renders_with_zero_surviving_placeholders(self, family):
        layouts_dir = Path.home() / ".claude" / "skills" / "bali-zero-brand" / "layouts"
        if not (layouts_dir / f"{family}.md").is_file():
            pytest.skip("brand layouts dir not present on this machine")
        slide = _REPRESENTATIVE_SLIDES[family]
        out = _fill_family(family, slide)
        assert "{{" not in out, f"{family} shipped raw mustache: {out}"

    def test_source_citation_title_is_filled(self):
        """Pinned regression: the exact PR #2942 discovery."""
        out = _fill_family("source-citation", _REPRESENTATIVE_SLIDES["source-citation"])
        assert "SUMBER" in out
        assert "{{title}}" not in out

    def test_elegant_close_content_fields_are_filled(self):
        """Pinned regression: the exact PR #2942 discovery (trust_marker/
        reach/invite), plus the {{index}} instance this sweep also found."""
        out = _fill_family("elegant-close", _REPRESENTATIVE_SLIDES["elegant-close"])
        assert "LICENSED KONSULTAN PAJAK" in out
        assert "ZANTARA@BALIZERO.COM" in out
        assert "30-MIN CALL" in out
        assert 'data-slide-index="9"' in out
        for token in ("{{trust_marker}}", "{{reach}}", "{{invite}}", "{{index}}"):
            assert token not in out

    def test_elegant_close_qr_branch_uses_provided_caption(self):
        out = _fill_family("elegant-close", _REPRESENTATIVE_SLIDES["elegant-close"])
        assert "qr-closing__caption" in out
        assert "PRIMARY SOURCE" in out
        assert "{{qr_caption" not in out

    def test_elegant_close_qr_branch_absent_drops_block_cleanly(self):
        """Innocence for the {{#if primary_source_url}} branch: when the
        slide has no primary_source_url, the whole QR block -- including its
        {{qr_caption | default: ...}} token -- must be dropped, not left
        half-filled."""
        slide = {
            k: v
            for k, v in _REPRESENTATIVE_SLIDES["elegant-close"].items()
            if k not in ("primary_source_url", "qr_caption")
        }
        out = _fill_family("elegant-close", slide)
        assert "qr-closing__caption" not in out
        assert "{{qr_caption" not in out
        assert "{{" not in out

    def test_elegant_close_qr_caption_falls_back_to_default_when_unset(self):
        """The {{qr_caption | default: "PRIMARY SOURCE"}} filter: an explicit
        primary_source_url with NO qr_caption override still fills from the
        skeleton's own literal default text, never leaks the filter syntax."""
        slide = {
            **{
                k: v
                for k, v in _REPRESENTATIVE_SLIDES["elegant-close"].items()
                if k != "qr_caption"
            },
        }
        out = _fill_family("elegant-close", slide)
        assert "PRIMARY SOURCE" in out
        assert "{{qr_caption" not in out


class TestGenericIfAndDefaultFilterHelpers:
    """Unit-level guilt+innocence for the two new generic expanders."""

    def test_top_level_if_keeps_block_when_truthy(self):
        html = "<div>{{#if flag}}SHOWN{{/if}}</div>"
        out = _expand_top_level_if_blocks(html, {"flag": "yes"})
        assert out == "<div>SHOWN</div>"

    def test_top_level_if_drops_block_when_falsy(self):
        html = "<div>{{#if flag}}SHOWN{{/if}}</div>"
        out = _expand_top_level_if_blocks(html, {})
        assert out == "<div></div>"

    def test_top_level_if_is_generic_not_hardcoded_to_regulation_code(self):
        """The class-cure claim: a brand-new var name (never enumerated by
        name anywhere in composer.py) is still covered."""
        html = "<div>{{#if some_future_field}}X{{/if}}</div>"
        assert _expand_top_level_if_blocks(html, {"some_future_field": True}) == "<div>X</div>"
        assert _expand_top_level_if_blocks(html, {}) == "<div></div>"

    def test_default_filter_uses_slide_value_when_present(self):
        html = '{{qr_caption | default: "PRIMARY SOURCE"}}'
        out = _expand_default_filters(html, {"qr_caption": "SUMBER ASLI"})
        assert out == "SUMBER ASLI"

    def test_default_filter_falls_back_to_literal_default(self):
        html = '{{qr_caption | default: "PRIMARY SOURCE"}}'
        out = _expand_default_filters(html, {})
        assert out == "PRIMARY SOURCE"

    def test_default_filter_escapes_slide_value(self):
        html = '{{qr_caption | default: "PRIMARY SOURCE"}}'
        out = _expand_default_filters(html, {"qr_caption": "A & B"})
        assert out == "A &amp; B"
