"""
Tests for the enriched-prompt bug fix in scripts/wr2_draft_generator.py.

Locks down PR-1 §C bug fix: when an enrichment object is available and the
WR2_USE_FULL_ENRICHED_PROMPT flag is on, the draft prompt is built from the
structured 1400-2000-word enrichment fields instead of summary[:3500].

The previous behavior shipped only 25% of the available material to Claude;
this fix is the difference between "11 slides built on a paragraph" and
"11 slides built on the_facts + bali_zero_take + in_practice + next_steps + faq".

2026-07-17 (B1/B2, draft 1229c367): a SECOND bug in the same neighborhood —
when enrichment was truthy but only carried a grounding-injected citation block
(wr2_grounding.py `_grounding_injected_only`), it SHADOWED the real article
summary outright and Claude invented the story. B1 below locks the fix
(compose both, article leads); B2 locks the park backstop for when there is
truly no source anywhere.

These tests don't call Claude — they verify the prompt construction
deterministically, which is the unit boundary we control.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# wr2_draft_generator imports asyncpg/httpx at module load. Both are in the
# backend-rag venv → available when run via PYTHONPATH=. + venv python.
SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_draft_generator as dg  # noqa: E402
from wr2_draft_generator import (  # noqa: E402
    _build_draft_prompt,
    _build_enriched_brief,
    _cap_subhead,
    _has_usable_source,
    _is_news_shaped,
    _normalise_slides,
)


# ─────────────────────────────────────────────────────────────────────────
# _build_enriched_brief
# ─────────────────────────────────────────────────────────────────────────

def test_enriched_brief_renders_all_sections() -> None:
    """Full enrichment object → all 6 section labels appear in output."""
    enrichment = {
        "thirty_second_brief": {
            "what": "BKPM raided unlicensed PMAs",
            "why_it_matters": "Compliance risk for foreign investors",
            "who": "Foreign-owned PT PMA without OSS",
            "risk_level": "high",
        },
        "the_facts": "Paragraph 1.\n\nParagraph 2.",
        "bali_zero_take": "Editorial perspective.",
        "in_practice": "What expats should do.",
        "next_steps": "Action items.",
        "faq": [
            {"question": "Q1?", "answer": "A1."},
            {"question": "Q2?", "answer": "A2."},
        ],
    }
    brief = _build_enriched_brief(enrichment, live_reasons=None)
    assert "30-second brief" in brief
    assert "The facts" in brief
    assert "Bali Zero editorial take" in brief
    assert "In practice" in brief
    assert "Next steps" in brief
    assert "FAQ" in brief


def test_enriched_brief_includes_field_content() -> None:
    """Verbatim content from each field must appear in the rendered brief."""
    enrichment = {
        "the_facts": "BKPM published Reg 5/2026 on 2026-04-23.",
        "bali_zero_take": "This shifts the compliance burden to consultants.",
        "next_steps": "Audit OSS status within 30 days.",
    }
    brief = _build_enriched_brief(enrichment, live_reasons=None)
    assert "Reg 5/2026 on 2026-04-23" in brief
    assert "compliance burden to consultants" in brief
    assert "Audit OSS status within 30 days" in brief


def test_enriched_brief_handles_empty_enrichment() -> None:
    """Empty dict → empty brief (caller falls back to summary path)."""
    assert _build_enriched_brief({}, live_reasons=None) == ""
    assert _build_enriched_brief({"unknown_field": "noise"}, live_reasons=None) == ""


def test_enriched_brief_coerces_non_dict_enrichment_instead_of_raising() -> None:
    """GUILT (round-2 red-team MUST-FIX #2, scar family #9): a hand-edited/
    legacy staging JSON can carry a truthy non-dict `enrichment` (e.g. a
    list) that survives the upstream projection and topic-selector guards.
    Every field access in this function is an unguarded `enrichment.get(...)`
    — pre-fix, a list argument raised AttributeError (`'list' object has no
    attribute 'get'`) which was NOT caught by the local caller handlers and
    sent the whole draft to REJECTED. Must degrade to the empty-brief
    fallback instead."""
    assert _build_enriched_brief(["bad"], live_reasons=None) == ""
    assert _build_enriched_brief("not a dict either", live_reasons=None) == ""
    assert _build_enriched_brief(None, live_reasons=None) == ""


def test_enriched_brief_skips_missing_sections() -> None:
    """Partial enrichment renders only the sections that exist."""
    brief = _build_enriched_brief(
        {"the_facts": "Only the facts here.", "in_practice": ""},
        live_reasons=None,
    )
    assert "The facts" in brief
    assert "Only the facts here." in brief
    # No bali_zero_take / next_steps / faq → labels absent
    assert "Bali Zero editorial take" not in brief
    assert "Next steps" not in brief
    assert "FAQ" not in brief


def test_enriched_brief_thirty_second_partial_fields() -> None:
    """Partial 30-second brief renders only present subfields."""
    brief = _build_enriched_brief(
        {"thirty_second_brief": {"what": "Decree published", "risk_level": "medium"}},
        live_reasons=None,
    )
    assert "What: Decree published" in brief
    assert "Risk level: medium" in brief
    assert "Why it matters" not in brief
    assert "Who is affected" not in brief


def test_enriched_brief_appends_live_reasons() -> None:
    enrichment = {"the_facts": "Facts."}
    brief = _build_enriched_brief(
        enrichment,
        live_reasons=[
            "BKPM Reg 5/2026 published 2026-04-23",
            "Deportation of 12 nationals 2026-04-25",
        ],
    )
    assert "Live news signals" in brief
    assert "BKPM Reg 5/2026 published 2026-04-23" in brief
    assert "Deportation of 12 nationals 2026-04-25" in brief


def test_enriched_brief_caps_live_reasons_at_three() -> None:
    brief = _build_enriched_brief(
        {"the_facts": "Facts."},
        live_reasons=["one", "two", "three", "four", "five"],
    )
    assert "one" in brief
    assert "three" in brief
    assert "four" not in brief
    assert "five" not in brief


def test_enriched_brief_empty_live_reasons_no_section() -> None:
    """Empty list → no Live news signals section (avoid empty header)."""
    brief = _build_enriched_brief({"the_facts": "Facts."}, live_reasons=[])
    assert "Live news signals" not in brief


def test_enriched_brief_caps_faq_at_six() -> None:
    enrichment = {
        "faq": [{"question": f"Q{i}?", "answer": f"A{i}."} for i in range(10)]
    }
    brief = _build_enriched_brief(enrichment, live_reasons=None)
    assert "Q5?" in brief
    assert "Q6?" not in brief


def test_enriched_brief_skips_malformed_faq_entries() -> None:
    enrichment = {
        "faq": [
            {"question": "Q1?", "answer": "A1."},
            "not a dict",
            {"question": "", "answer": "missing question"},
            {"question": "Q4?", "answer": "A4."},
        ],
    }
    brief = _build_enriched_brief(enrichment, live_reasons=None)
    assert "Q1?" in brief
    assert "Q4?" in brief
    assert "missing question" not in brief


# ─────────────────────────────────────────────────────────────────────────
# _build_draft_prompt — flag gating
# ─────────────────────────────────────────────────────────────────────────

def test_legacy_path_used_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default behavior: enriched ignored, summary[:3500] used. Preserves
    pre-§C behavior for safe rollback."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "false")
    enrichment = {
        "the_facts": "ENRICHED FACT TEXT",
        "bali_zero_take": "ENRICHED TAKE",
    }
    prompt = _build_draft_prompt(
        topic="Test topic",
        summary="LEGACY SUMMARY CONTENT",
        source_url="https://example.com",
        enrichment=enrichment,
        live_reasons=["should not appear"],
    )
    assert "LEGACY SUMMARY CONTENT" in prompt
    assert "ENRICHED FACT TEXT" not in prompt
    assert "ENRICHED TAKE" not in prompt


def test_enriched_path_used_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag on + enrichment present → prompt is built from structured fields."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    enrichment = {
        "the_facts": "ENRICHED FACT TEXT",
        "bali_zero_take": "ENRICHED TAKE",
        "in_practice": "ENRICHED PRACTICE",
    }
    prompt = _build_draft_prompt(
        topic="Test topic",
        summary="LEGACY SUMMARY CONTENT",
        source_url="https://example.com",
        enrichment=enrichment,
        live_reasons=None,
    )
    assert "ENRICHED FACT TEXT" in prompt
    assert "ENRICHED TAKE" in prompt
    assert "ENRICHED PRACTICE" in prompt
    # Section labels present → confirms _build_enriched_brief path was taken
    assert "The facts" in prompt
    assert "Bali Zero editorial take" in prompt


def test_falls_back_to_summary_when_flag_on_but_no_enrichment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag on but enrichment empty → graceful fallback to summary path.

    Critical: items that pre-date §B (enrichment=None) must still produce a
    valid prompt instead of crashing or sending Claude an empty body.
    """
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    prompt = _build_draft_prompt(
        topic="Legacy topic",
        summary="LEGACY SUMMARY CONTENT",
        source_url="https://example.com",
        enrichment=None,
        live_reasons=None,
    )
    assert "LEGACY SUMMARY CONTENT" in prompt


def test_falls_back_to_summary_when_enrichment_is_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag on but enrichment={} → also falls back to summary path."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    prompt = _build_draft_prompt(
        topic="t",
        summary="LEGACY SUMMARY CONTENT",
        source_url="",
        enrichment={},
        live_reasons=None,
    )
    assert "LEGACY SUMMARY CONTENT" in prompt


def test_summary_truncated_at_3500_in_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy invariant preserved: summary[:3500] cap stays in place to
    avoid blowing the context budget on the back-compat path."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "false")
    long_summary = "x" * 5000 + "TAIL_MARKER"
    prompt = _build_draft_prompt(
        topic="t", summary=long_summary, source_url="",
        enrichment=None, live_reasons=None,
    )
    assert "TAIL_MARKER" not in prompt  # everything past 3500 is dropped


def test_enriched_prompt_is_substantially_longer_than_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of this bug fix: with the enriched object, the
    prompt body Claude sees is materially larger than ~3500 chars. We
    don't pin exact size (it's content-dependent), only that the
    enriched-mode prompt is meaningfully bigger than the legacy one
    on the same data — confirming we're shipping more material.
    """
    enrichment = {
        "thirty_second_brief": {
            "what": "What happened.",
            "why_it_matters": "Why it matters.",
            "who": "Who is affected.",
            "risk_level": "medium",
        },
        "the_facts": "x" * 1500,
        "bali_zero_take": "y" * 600,
        "in_practice": "z" * 600,
        "next_steps": "w" * 400,
        "faq": [{"question": f"Q{i}?", "answer": "a" * 100} for i in range(4)],
    }

    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "false")
    legacy = _build_draft_prompt(
        topic="t", summary="short summary", source_url="",
        enrichment=enrichment, live_reasons=None,
    )

    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    enriched = _build_draft_prompt(
        topic="t", summary="short summary", source_url="",
        enrichment=enrichment, live_reasons=None,
    )

    # System prompt is fixed ~2000 chars; only the body section changes
    # between modes. Enriched body must be substantially larger than the
    # legacy "short summary" path. We assert delta >= 3000 chars — enough
    # to confirm we're shipping the_facts + take + practice + steps + faq
    # instead of the truncated paragraph.
    assert len(enriched) - len(legacy) >= 3000
    assert len(enriched) > 4000  # crosses the 3500 ceiling the bug imposed


def test_topic_and_source_appear_in_both_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Common-prompt invariants: topic and source_url labels appear
    regardless of which body path was taken."""
    for flag in ("false", "true"):
        monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", flag)
        prompt = _build_draft_prompt(
            topic="My Topic",
            summary="summary",
            source_url="https://example.com/article",
            enrichment={"the_facts": "facts"},
            live_reasons=None,
        )
        assert "My Topic" in prompt
        assert "https://example.com/article" in prompt


# ---------------------------------------------------------------------------
# _cap_subhead -- template contract (1-6 words) backstop
# ---------------------------------------------------------------------------

SENTENCE_SUBHEAD = "KPK is investigating Indonesia's Deputy Minister of Immigration"


def test_cap_subhead_truncates_full_sentence() -> None:
    """A full-sentence subhead is capped to <=6 words AND <=32 chars,
    never cutting a word in half."""
    out = _cap_subhead(SENTENCE_SUBHEAD)
    words = out.split()
    assert len(words) <= 6, f"too many words: {out!r}"
    assert len(out) <= 32, f"too long: {out!r} ({len(out)} chars)"
    assert "..." not in out
    original = SENTENCE_SUBHEAD.split()
    assert words == original[: len(words)]


def test_cap_subhead_passes_conforming_kicker() -> None:
    """An already-conforming kicker is returned unchanged."""
    assert _cap_subhead("VISA UPDATE") == "VISA UPDATE"


def test_cap_subhead_empty_is_empty() -> None:
    """Empty / whitespace input does not crash and returns ''."""
    assert _cap_subhead("") == ""
    assert _cap_subhead("   ") == ""


def test_cap_subhead_word_cap_only_when_short() -> None:
    """6 short words under the char cap survive intact; a 7th is dropped."""
    assert _cap_subhead("ONE TWO THREE FOUR FIVE SIX") == "ONE TWO THREE FOUR FIVE SIX"
    assert _cap_subhead("ONE TWO THREE FOUR FIVE SIX SEVEN") == "ONE TWO THREE FOUR FIVE SIX"


def test_cap_subhead_single_long_word_not_split() -> None:
    """A single word longer than max_chars is returned whole (never cut)."""
    long_word = "Superlongunbreakablekickerwordthatexceedslimit"
    assert _cap_subhead(long_word) == long_word


def test_normalise_slides_caps_subhead_field() -> None:
    """End-to-end through _normalise_slides: a long cover subhead is capped
    on the 'subhead' field of the persisted slide dict."""
    slides_in = []
    for i in range(1, 9):
        slides_in.append({
            "slide_number": i,
            "slide_type": "cover" if i == 1 else "body",
            "is_cover": i == 1,
            "is_hero_image": i == 1,
            "headline": f"Headline {i}",
            "subhead": SENTENCE_SUBHEAD if i == 1 else "",
            "body": f"Body text for slide {i}.",
            "image_prompt": "editorial scene",
        })
    parsed = {"register": "analitico", "slides": slides_in}
    _register, slides = _normalise_slides(parsed)
    cover_subhead = slides[0]["subhead"]
    assert len(cover_subhead.split()) <= 6
    assert len(cover_subhead) <= 32
    assert "..." not in cover_subhead


# ─────────────────────────────────────────────────────────────────────────
# B1 — facts-first composition (draft 1229c367, 2026-07-16)
#
# Bug: a citations-only grounding injection was TRUTHY, so it fully replaced
# the real article summary — Claude composed from a legal-brief fragment
# instead of the actual news event. Fix: when BOTH are usable, the article
# leads and the enriched brief follows as supporting material.
# ─────────────────────────────────────────────────────────────────────────

_DISTINCTIVE_FACTS_SENTENCE = (
    "Three foreign nationals have been deported from Bali after Indonesian "
    "immigration officials determined they were engaged in work activities."
)


def test_guilt_facts_shadowed_by_citations_only_enrichment_fails_on_old_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GUILT: reproduces draft 1229c367 exactly — enrichment.the_facts is a
    grounding-injected citations-only block (the `_grounding_injected_only`
    marker set), article_summary carries the real event. The built prompt
    MUST contain the article's facts AND the citations — this is the
    assertion that failed on the pre-fix code (enrichment alone replaced the
    body, so the distinctive facts sentence was absent)."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    enrichment = {
        "the_facts": "Riferimenti normativi (verbatim, citare senza parafrasare): PP 31/2013 · Pasal 187",
        "_grounding_injected_only": True,
    }
    prompt = _build_draft_prompt(
        topic="Bali Deports Three Foreigners Caught Working on Tourist Visas",
        summary=_DISTINCTIVE_FACTS_SENTENCE + " Full article body continues here.",
        source_url="https://example.com/deported",
        enrichment=enrichment,
        live_reasons=None,
    )
    assert _DISTINCTIVE_FACTS_SENTENCE in prompt
    assert "PP 31/2013" in prompt
    assert "Pasal 187" in prompt


def test_innocence_rich_enrichment_and_summary_both_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INNOCENCE: a real (non-injected) rich enrichment object alongside a
    real summary — both the article facts AND every enriched section must
    still appear; facts-first must not drop the enriched material."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    enrichment = {
        "the_facts": "Full journalism paragraph on the regulation change.",
        "bali_zero_take": "Our editorial take on what this means.",
        "in_practice": "What expats should actually do about it.",
    }
    prompt = _build_draft_prompt(
        topic="Test topic",
        summary=_DISTINCTIVE_FACTS_SENTENCE,
        source_url="https://example.com",
        enrichment=enrichment,
        live_reasons=None,
    )
    assert _DISTINCTIVE_FACTS_SENTENCE in prompt
    assert "Full journalism paragraph on the regulation change." in prompt
    assert "Our editorial take on what this means." in prompt
    assert "What expats should actually do about it." in prompt
    assert "Source article" in prompt
    assert "Supporting brief" in prompt


def test_legacy_opt_out_stays_summary_only_even_with_facts_first_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy opt-out (WR2_USE_FULL_ENRICHED_PROMPT=false) unaffected by B1:
    summary[:3500] only, enrichment never even considered."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "false")
    enrichment = {"the_facts": "ENRICHED", "_grounding_injected_only": True}
    prompt = _build_draft_prompt(
        topic="t",
        summary=_DISTINCTIVE_FACTS_SENTENCE,
        source_url="",
        enrichment=enrichment,
        live_reasons=None,
    )
    assert _DISTINCTIVE_FACTS_SENTENCE in prompt
    assert "ENRICHED" not in prompt
    assert "Source article" not in prompt


def test_facts_first_steer_line_present_only_when_both_sources_compose() -> None:
    """The SOURCE-GROUNDING steer line only fires when facts-first actually
    composed (both summary and enrichment usable) — never on the pure
    summary-only or pure-enrichment-only paths."""
    both = _build_draft_prompt(
        topic="t", summary="real summary text", source_url="",
        enrichment={"the_facts": "real facts"}, live_reasons=None,
    )
    assert dg._FACTS_FIRST_STEER in both

    summary_only = _build_draft_prompt(
        topic="t", summary="real summary text", source_url="",
        enrichment=None, live_reasons=None,
    )
    assert dg._FACTS_FIRST_STEER not in summary_only

    enrichment_only = _build_draft_prompt(
        topic="t", summary="", source_url="",
        enrichment={"the_facts": "real facts"}, live_reasons=None,
    )
    assert dg._FACTS_FIRST_STEER not in enrichment_only


# ─────────────────────────────────────────────────────────────────────────
# B2 — refuse-to-guess park backstop: _is_news_shaped / _has_usable_source
# ─────────────────────────────────────────────────────────────────────────

def test_is_news_shaped_by_staging_type() -> None:
    assert _is_news_shaped({"staging_type": "news"}, "", "Some headline") is True
    assert _is_news_shaped({"staging_type": "visa"}, "", "A generic guide") is False


def test_is_news_shaped_by_liveness_tier() -> None:
    assert _is_news_shaped({}, "breaking", "x") is True
    assert _is_news_shaped({}, "developing", "x") is True
    assert _is_news_shaped({}, "evergreen", "x") is False
    assert _is_news_shaped({}, "", "x") is False


def test_is_news_shaped_by_title_event_pattern() -> None:
    assert _is_news_shaped({}, "", "Bali Deports Three Foreigners") is True
    assert _is_news_shaped({}, "", "Immigration Raid Nets Five Overstayers") is True
    assert _is_news_shaped({}, "", "How KITAS Renewal Works: A Complete Guide") is False


def test_has_usable_source_true_when_summary_present() -> None:
    """A real summary is usable regardless of enrichment state — including
    when enrichment is citations-only (the marker doesn't matter here)."""
    assert _has_usable_source("Real article text.", None) is True
    assert _has_usable_source(
        "Real article text.", {"_grounding_injected_only": True}
    ) is True


def test_has_usable_source_false_when_summary_empty_and_enrichment_injected_only() -> None:
    """GUILT case for the park decision: nothing anywhere."""
    assert _has_usable_source("", {"_grounding_injected_only": True}) is False
    assert _has_usable_source("", None) is False
    assert _has_usable_source("   ", {}) is False


def test_has_usable_source_true_when_enrichment_has_real_facts_no_summary() -> None:
    """A real (non-injected) enrichment object counts as usable even with no
    article_summary at all."""
    assert _has_usable_source(
        "", {"the_facts": "Real journalism paragraph, no marker."}
    ) is True


def test_has_usable_source_false_when_article_summary_is_whitespace_only() -> None:
    """Red-team finding #1a companion: a whitespace-only summary must be
    treated the same as an empty one — it is truthy in Python but carries no
    real content, so it must NOT short-circuit `_has_usable_source` to True."""
    assert _has_usable_source("   ", {"_grounding_injected_only": True}) is False


def test_has_usable_source_false_when_facts_structurally_citations_only_without_marker_key() -> None:
    """Red-team finding #1b companion: the structural detector
    (wg.is_citations_only_the_facts) must catch a citations-only the_facts
    even when the `_grounding_injected_only` marker key was never set at all
    (the early-return gap in wr2_grounding.ground_enrichment) — detection
    must not depend on the marker alone."""
    enrichment = {
        "the_facts": (
            "Riferimenti normativi (verbatim, citare senza parafrasare): PP 31/2013"
        ),
    }
    assert _has_usable_source("", enrichment) is False


def test_has_usable_source_true_when_facts_citations_only_but_other_fields_real() -> None:
    """Red-team finding #2: the_facts is citations-only (marker set), but the
    enrichment object ALSO carries real content in another structured field.
    The old implementation returned False the moment it saw the
    citations-only signal, discarding real content elsewhere. The fix strips
    ONLY the_facts from consideration and still checks the rest
    (thirty_second_brief / bali_zero_take / in_practice / next_steps / faq)."""
    enrichment = {
        "the_facts": (
            "Riferimenti normativi (verbatim, citare senza parafrasare): PP 31/2013"
        ),
        "_grounding_injected_only": True,
        "thirty_second_brief": {
            "what": "Three foreigners were deported for working illegally."
        },
    }
    assert _has_usable_source("", enrichment) is True


def test_has_usable_source_false_when_only_citations_only_facts_and_nothing_else() -> None:
    """INNOCENCE for finding #2's fix: stripping the_facts must not create a
    false-positive when there really is nothing else — the marker-only case
    (no other structured fields) must still park."""
    enrichment = {
        "the_facts": (
            "Riferimenti normativi (verbatim, citare senza parafrasare): PP 31/2013"
        ),
        "_grounding_injected_only": True,
    }
    assert _has_usable_source("", enrichment) is False


# ─────────────────────────────────────────────────────────────────────────
# B2 — _process_one integration: park path vs. conservative no-park path
# ─────────────────────────────────────────────────────────────────────────

_FAKE_SLIDES_RESPONSE = {
    "register": "analitico",
    "register_reason": "test",
    "slides": [
        {
            "slide_number": i,
            "slide_type": "cover" if i == 1 else ("cta" if i == 6 else "body"),
            "is_cover": i == 1,
            "is_hero_image": i == 1,
            "headline": f"Headline {i}",
            "subhead": "TEST TAG" if i == 1 else "",
            "body": f"Body copy for slide {i}." if i < 6 else "Short close now.",
            "image_prompt": "editorial scene" if i == 1 else "",
        }
        for i in range(1, 7)
    ],
}


@pytest.mark.asyncio
async def test_process_one_parks_news_shaped_draft_with_no_usable_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration GUILT: news-shaped (staging_type=news) + empty
    article_summary + citations-only enrichment -> parked, Claude NEVER
    called, no compose attempt."""
    draft_id = uuid.uuid4()
    row = {
        "id": draft_id,
        "topic": "Some News Event",
        "brief_json": {
            "article_summary": "",
            "enrichment": {
                "the_facts": (
                    "Riferimenti normativi (verbatim, citare senza parafrasare): "
                    "PP 31/2013"
                ),
                "_grounding_injected_only": True,
            },
            "staging_type": "news",
            "liveness_tier": None,
        },
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    compose_mock = AsyncMock()
    monkeypatch.setattr(dg, "claude_compose_slides", compose_mock)

    outcome = await dg._process_one(conn, row)

    assert outcome == "parked"
    compose_mock.assert_not_called()
    conn.execute.assert_awaited_once()
    args, _kwargs = conn.execute.call_args
    assert "parked" in args[0]
    assert args[1] == draft_id


@pytest.mark.asyncio
async def test_process_one_composes_when_news_shaped_but_summary_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration no-park (conservative): news-shaped AND enrichment is
    citations-only, BUT article_summary is real -> composes normally, never
    parked. Proves the backstop doesn't over-trigger on the common case
    (B1's facts-first fix handles this one, not B2's park)."""
    draft_id = uuid.uuid4()
    row = {
        "id": draft_id,
        "topic": "Bali Deports Three Foreigners Caught Working on Tourist Visas",
        "brief_json": {
            "article_summary": _DISTINCTIVE_FACTS_SENTENCE,
            "enrichment": {
                "the_facts": "Riferimenti normativi: PP 31/2013",
                "_grounding_injected_only": True,
            },
            "staging_type": "news",
            "liveness_tier": None,
            "source_url": "https://example.com",
        },
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    compose_mock = AsyncMock(return_value=_FAKE_SLIDES_RESPONSE)
    monkeypatch.setattr(dg, "claude_compose_slides", compose_mock)
    monkeypatch.setattr(dg, "generate_cover_image", AsyncMock(return_value=(None, "skip-in-test")))
    monkeypatch.setattr(dg, "_send_telegram", MagicMock())
    monkeypatch.setattr(dg.wom, "resolve_carousel_id", AsyncMock(return_value="cid-test"))
    monkeypatch.setattr(dg.wom, "record_step", AsyncMock())

    outcome = await dg._process_one(conn, row)

    assert outcome == "success"
    compose_mock.assert_awaited_once()
    # Persisted as a normal draft, not parked.
    persist_calls = [c for c in conn.execute.call_args_list if "status" in c.args[0]]
    assert any("'drafts'" in c.args[0] for c in persist_calls)
    assert not any("parked" in c.args[0] for c in persist_calls)


@pytest.mark.asyncio
async def test_process_one_composes_when_facts_citations_only_but_enrichment_rich(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration no-park for red-team finding #2: article_summary is
    EMPTY and the_facts IS citations-only (marker set) — but the enrichment
    object carries real content in another structured field
    (thirty_second_brief). The old _has_usable_source parked on the
    citations-only signal alone, discarding that real content. The fix must
    compose instead."""
    draft_id = uuid.uuid4()
    row = {
        "id": draft_id,
        "topic": "Bali Deports Three Foreigners Caught Working on Tourist Visas",
        "brief_json": {
            "article_summary": "",
            "enrichment": {
                "the_facts": "Riferimenti normativi: PP 31/2013",
                "_grounding_injected_only": True,
                "thirty_second_brief": {
                    "what": "Three foreigners were deported for working illegally on tourist visas."
                },
            },
            "staging_type": "news",
            "liveness_tier": None,
            "source_url": "https://example.com",
        },
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    compose_mock = AsyncMock(return_value=_FAKE_SLIDES_RESPONSE)
    monkeypatch.setattr(dg, "claude_compose_slides", compose_mock)
    monkeypatch.setattr(dg, "generate_cover_image", AsyncMock(return_value=(None, "skip-in-test")))
    monkeypatch.setattr(dg, "_send_telegram", MagicMock())
    monkeypatch.setattr(dg.wom, "resolve_carousel_id", AsyncMock(return_value="cid-test"))
    monkeypatch.setattr(dg.wom, "record_step", AsyncMock())

    outcome = await dg._process_one(conn, row)

    assert outcome == "success"
    compose_mock.assert_awaited_once()
    persist_calls = [c for c in conn.execute.call_args_list if "status" in c.args[0]]
    assert any("'drafts'" in c.args[0] for c in persist_calls)
    assert not any("parked" in c.args[0] for c in persist_calls)
