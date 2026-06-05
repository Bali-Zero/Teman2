"""Unit tests for the WR2 autopsy fixes (2026-06-04) + 4-LLM panel fixes (2026-06-05).

Tests PURE functions only — no DB, no network, no browser. All three modules
under test (wr2_image_generator, wr2_fact_checker, wr2_draft_generator) import
cleanly standalone from the scripts/ dir under the backend-rag venv (verified),
so plain imports suffice.

Run:
    cd scripts && source ../apps/backend-rag/.venv/bin/activate \
        && python -m pytest test_wr2_autopsy_fixes.py -q
"""
from __future__ import annotations

import wr2_draft_generator as dg
import wr2_fact_checker as fc
import wr2_image_generator as ig


# The exact historical brand string the renderer emitted before the per-slide
# tonal refactor. The panel's CRITICAL fix requires _brand_block(None) and
# BRAND_SUFFIX to reproduce this VERBATIM (any drift silently re-styles every
# image and invalidates the whole back-catalogue look). em-dash in "faces
# visible —"; comma after "film grain,".
HISTORICAL_BRAND_SUFFIX = (
    "Editorial photography, shot on 35mm film, subtle film grain, "
    "chiaroscuro lighting, low-key exposure, desaturated muted palette of "
    "deep charcoals and warm ochre accents. Minimalist composition with "
    "vast negative space. No human faces visible — silhouettes or objects "
    "only. Photorealistic. CRITICAL ASPECT RATIO: 4:5 portrait, 1080x1350 "
    "pixels, full-bleed, no border, no whitespace on any side."
)


# ─────────────────────────────────────────────────────────────────────────
# Fix #1/#2 — wr2_image_generator: per-slide tonal palettes (autopsy #3)
# ─────────────────────────────────────────────────────────────────────────


def test_resolve_tonal_cool_teal_returns_teal_directive():
    out = ig._resolve_tonal("cool-teal")
    assert "teal" in out
    # cool-teal is a DISTINCT look, not the historical charcoal clamp
    assert "deep charcoals" not in out


def test_resolve_tonal_none_returns_default_charcoal():
    out = ig._resolve_tonal(None)
    assert "deep charcoals" in out


def test_resolve_tonal_warm_ochre_equals_default_look():
    # warm-ochre reproduces the historical default exactly (back-compat)
    assert ig._resolve_tonal("warm-ochre") == ig._resolve_tonal(None)


def test_resolve_tonal_substring_branch_monochrome():
    # PANEL FIX 1: free-text hint resolves via the substring branch.
    assert ig._resolve_tonal("please use a monochrome look") == ig.TONAL_PALETTES["monochrome"]


def test_compose_final_prompt_cool_teal():
    out = ig._compose_final_prompt("a dark room", "cool-teal")
    assert "teal" in out
    # the hard charcoal clamp must NOT leak into a cool-teal slide
    assert "deep charcoals" not in out


def test_compose_final_prompt_none_is_backward_compatible():
    # unspecified slide keeps the historical charcoal look
    out = ig._compose_final_prompt("a dark room", None)
    assert "deep charcoals" in out


def test_brand_block_none_byte_equals_historical_literal():
    # PANEL FIX 1 (CRITICAL regression): the default brand block must reproduce
    # the pre-refactor string VERBATIM, else every image silently re-styles.
    assert ig._brand_block(None) == HISTORICAL_BRAND_SUFFIX


def test_brand_suffix_byte_equals_historical_literal():
    # PANEL FIX 1 (CRITICAL): BRAND_SUFFIX is the default block and must match
    # both _brand_block(None) and the historical literal exactly.
    assert ig.BRAND_SUFFIX == ig._brand_block(None)
    assert ig.BRAND_SUFFIX == HISTORICAL_BRAND_SUFFIX


def test_brand_block_cool_teal_preserves_opener_and_tech_rest():
    # PANEL FIX 1: swapping the tonal directive must keep the universal opener
    # and the technical tail intact — only the palette/lighting changes.
    block = ig._brand_block("cool-teal")
    assert "teal" in block
    assert "charcoal" not in block
    assert block.startswith("Editorial photography, shot on 35mm film")
    assert block.endswith("no whitespace on any side.")


def test_brand_suffix_back_compat_alias_keeps_full_string():
    # anything still importing BRAND_SUFFIX gets the full historical look
    assert "deep charcoals and warm ochre" in ig.BRAND_SUFFIX


def test_brand_technical_has_no_palette_clamp():
    # the TECHNICAL scaffold is non-aesthetic only (film/faces/aspect) — the
    # palette clamp is gone (now lives in TONAL_PALETTES["default"]).
    assert "charcoal" not in ig.BRAND_TECHNICAL


# ─────────────────────────────────────────────────────────────────────────
# Fix — wr2_fact_checker: external-truth gating + extended citations (P-5)
#       + 4-LLM panel fixes (Pasal regex, _has_external_truth rewrite)
# ─────────────────────────────────────────────────────────────────────────


def test_find_law_citations_matches_all_instrument_classes():
    cites = fc._find_law_citations(
        "Permenkumham 22/2023 Pasal 198 Perpres 21/2016 Permenimipas 5/2025"
    )
    assert any("PERMENKUMHAM" in c for c in cites)
    assert any("PASAL" in c for c in cites)
    assert any("PERPRES" in c for c in cites)
    assert any("PERMENIMIPAS" in c for c in cites)


def test_pasal_ayat_forms_cross_match_bare_article():
    # PANEL FIX 2: "Pasal 26 ayat (2)", "Pasal 26 (2)" and "Pasal 26" must all
    # normalise to the same bare article so subsection wording doesn't break
    # citation matching against the source.
    ayat = fc._find_law_citations("Pasal 26 ayat (2)")
    paren = fc._find_law_citations("Pasal 26 (2)")
    bare = fc._find_law_citations("Pasal 26")
    assert ayat == paren == bare == {"PASAL 26"}


def test_pasal_does_not_swallow_following_word():
    # PANEL FIX 2: the article regex must stop at the number, not eat the
    # next token.
    cites = fc._find_law_citations("Pasal 198 supersedes everything")
    assert "PASAL 198" in cites
    assert not any("SUPERSEDES" in c for c in cites)


def test_verify_law_claim_unverifiable_without_external_truth():
    result = fc._verify_law_claim(
        "Permenkumham 22/2023 x",
        set(),
        "draft repeats Permenkumham 22/2023",
        has_external_truth=False,
    )
    assert result["verdict"] == "unverifiable"


def test_verify_law_claim_verified_with_external_source():
    # source_laws must use the same uppercased form _find_law_citations emits
    source_laws = fc._find_law_citations("Permenkumham 22/2023")
    result = fc._verify_law_claim(
        "Permenkumham 22/2023 x",
        source_laws,
        "external ground truth: Permenkumham 22/2023",
        has_external_truth=True,
    )
    assert result["verdict"] == "verified"


def test_aggregate_status_verified_but_no_external_truth_is_degraded():
    # FAIL-CLOSED: "verified" against the draft itself never earns a clean pass
    assert (
        fc._aggregate_status([{"verdict": "verified"}], has_external_truth=False)
        == "degraded"
    )


def test_aggregate_status_verified_with_external_truth_is_pass():
    assert (
        fc._aggregate_status([{"verdict": "verified"}], has_external_truth=True)
        == "pass"
    )


def test_aggregate_status_empty_claims_is_pass():
    # nothing to mis-verify → vacuously pass even without external truth
    assert fc._aggregate_status([], has_external_truth=False) == "pass"


def test_has_external_truth_false_for_empty():
    assert fc._has_external_truth(None, None) is False


def test_has_external_truth_false_for_empty_dict():
    # PANEL FIX 2: an empty container is not ground truth.
    assert fc._has_external_truth({}, None) is False


def test_has_external_truth_false_for_blank_value():
    # PANEL FIX 2: a dict whose only leaf is "" carries no content.
    assert fc._has_external_truth({"k": ""}, None) is False


def test_has_external_truth_true_for_real_ground_truth():
    assert (
        fc._has_external_truth(
            {"f": "PMK 131/2024 long real ground truth text here"}, None
        )
        is True
    )


def test_has_external_truth_true_for_compact_law_research():
    # PANEL FIX 2 (the false-negative bug): a compact but real research blob
    # with a law citation must register as external truth — the old serialized
    # char-strip wrongly capped such drafts at 'degraded' forever.
    assert (
        fc._has_external_truth(
            {"claims": [{"type": "law", "text": "Perpres 37/2023"}]}, None
        )
        is True
    )


def test_has_external_truth_true_for_law_citation_signal():
    # PANEL FIX 2: a real law citation is a strong positive signal regardless
    # of overall length.
    assert fc._has_external_truth({"x": "PMK 131/2024"}, None) is True


def test_has_external_truth_true_for_interior_keyword_no_charstrip_bug():
    # PANEL FIX 2: the rewrite measures leaf-value text length, so interior
    # letters (the "n/u/l" of "annulled") are no longer deleted by a naive
    # char-strip of "{}[]...null".
    assert (
        fc._has_external_truth(
            {"note": "this regulation was annulled in 2024 by a later one here"},
            None,
        )
        is True
    )


def test_extract_source_text_excludes_slides_when_flagged():
    # PANEL FIX 2 (spalla regression): law verification passes
    # include_slides=False so a citation can never self-verify from the draft's
    # own slides. With slides excluded the body text must NOT appear; with
    # slides included it must.
    slides = [{"body": "Permenkumham 22/2023 governs"}]
    excluded = fc._extract_source_text(None, None, slides, include_slides=False)
    included = fc._extract_source_text(None, None, slides, include_slides=True)
    assert "Permenkumham" not in excluded
    assert "Permenkumham" in included


# ─────────────────────────────────────────────────────────────────────────
# Fix — wr2_draft_generator: _normalise_slides passes through tonal_palette
# ─────────────────────────────────────────────────────────────────────────


def _minimal_parsed(first_slide_extra: dict | None = None) -> dict:
    """A minimal _normalise_slides-valid parsed dict: valid register + 6 slides.

    Each slide carries the required headline/body/image_prompt. Optional
    `first_slide_extra` merges extra keys into slide 1 (e.g. tonal_palette).
    """
    slides: list[dict] = []
    for i in range(6):  # _normalise_slides requires 6-11 slides
        slide = {
            "headline": f"Headline {i}",
            "body": f"Body text for slide {i}",
            "image_prompt": f"editorial scene {i}",
        }
        if i == 0 and first_slide_extra:
            slide.update(first_slide_extra)
        slides.append(slide)
    return {"register": "analitico", "slides": slides}


def test_normalise_slides_tonal_palette_passthrough_lowercased():
    # PANEL FIX 3: a mixed-case tonal_palette hint is lowercased and preserved.
    _register, slides = dg._normalise_slides(
        _minimal_parsed({"tonal_palette": "Cool-Teal"})
    )
    assert slides[0]["tonal_palette"] == "cool-teal"


def test_normalise_slides_tonal_palette_absent_is_none():
    # PANEL FIX 3: a slide without tonal_palette gets None (default downstream).
    _register, slides = dg._normalise_slides(_minimal_parsed())
    # slide 2 (index 1) never had a tonal_palette set
    assert slides[1]["tonal_palette"] is None
