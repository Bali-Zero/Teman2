"""Tests for wr2_carousel_ir.py — the typed Carousel IR (WR2 editorial-
intelligence Phase 1, spec §2 "Mossa A").

Four batteries:
  - Guilt+innocence corpus for SlideDeck/Slide validation (guard-conformance
    discipline — cicatrix-superscar.md family #3: no gate ships without
    both a colpevolezza AND an innocenza case).
  - extract_json_from_codeblock edges (ported from instructor v2, MIT).
  - Projection: for EVERY one of the 11 kinds, to_composer_dict(...) ->
    the REAL (imported, not reimplemented) composer.map_slide_to_family
    resolves to the intended layout family. This is the core Phase-1
    assertion — the whole point of the typed IR is that it reaches the 11
    layouts the autonomous producer currently can't (spec §0.2).
  - generate_slides_typed's validate-and-retry loop against a fake call_fn.

No DB, no CLI subprocess, no network — wr2_carousel_ir.py has zero I/O side
effects by design, so all but the smoke test in wr2_ir_shadow_replay.py run
instantly and deterministically.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_carousel_ir as ir  # noqa: E402
from wr2_html_renderer.composer import map_slide_to_family  # noqa: E402


def _deck(slides: list[dict], register: str = "analitico") -> dict:
    return {"register": register, "slides": slides}


# ─────────────────────────────────────────────────────────────────────────
# Guilt corpus — payloads that MUST fail
# ─────────────────────────────────────────────────────────────────────────


class TestGuiltCorpus:
    def test_unknown_kind_rejected(self):
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(_deck([{"kind": "bogus", "headline": "x"}]))

    def test_missing_required_field_per_kind_rejected(self):
        # prose requires `body` — absent here.
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(_deck([{"kind": "prose", "headline": "H"}]))

    def test_empty_facts_list_rejected(self):
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(_deck([{"kind": "fact_stack", "heading": "H", "facts": []}]))

    def test_qa_single_pair_rejected(self):
        # qa-dialogue is a fixed 2-voice layout — 1 pair cannot fill it.
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(
                _deck([{"kind": "qa", "pairs": [{"voice": "A", "line": "x"}]}])
            )

    def test_triad_single_item_rejected(self):
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(
                _deck([{"kind": "triad", "heading": "H", "items": [{"title": "A", "desc": "a"}]}])
            )

    def test_status_list_empty_items_rejected(self):
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(_deck([{"kind": "status_list", "heading": "H", "items": []}]))

    def test_timeline_empty_steps_rejected(self):
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(_deck([{"kind": "timeline", "heading": "H", "steps": []}]))

    def test_citation_empty_sources_rejected(self):
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(
                _deck([{"kind": "citation", "claim": "C", "sources": []}])
            )

    def test_kind_flip_mid_list_rejected(self):
        """Second slide DECLARES kind=prose but only carries fact_stack-shaped
        fields (heading/facts, no body) — kind and shape disagree, so the
        REQUIRED `body` field for prose is missing."""
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(_deck([
                {"kind": "cover", "headline": "OK COVER"},
                {"kind": "prose", "heading": "H", "facts": ["a", "b"]},
            ]))

    def test_invalid_register_rejected(self):
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(
                _deck([{"kind": "statement", "statement": "X"}], register="not-a-real-tone")
            )

    def test_empty_required_string_after_coercion_rejected(self):
        # whitespace-only "statement" coerces to "" — still required content.
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(_deck([{"kind": "statement", "statement": "   "}]))

    def test_wrong_type_for_list_field_rejected(self):
        with pytest.raises(ValidationError):
            ir.SlideDeck.model_validate(
                _deck([{"kind": "fact_stack", "heading": "H", "facts": "not a list"}])
            )


# ─────────────────────────────────────────────────────────────────────────
# Innocence corpus — edge-legit payloads that MUST pass
# ─────────────────────────────────────────────────────────────────────────


class TestInnocenceCorpus:
    def test_long_headline_truncated_not_rejected(self):
        deck = ir.SlideDeck.model_validate(
            _deck([{"kind": "prose", "headline": "X" * 300, "body": "body text"}])
        )
        assert len(deck.slides[0].headline) == 80

    def test_long_body_truncated_not_rejected(self):
        deck = ir.SlideDeck.model_validate(
            _deck([{"kind": "prose", "headline": "H", "body": "Y" * 900}])
        )
        assert len(deck.slides[0].body) == 500

    def test_long_cover_image_prompt_truncated_not_rejected(self):
        deck = ir.SlideDeck.model_validate(
            _deck([{"kind": "cover", "headline": "H", "image_prompt": "P" * 900}])
        )
        assert len(deck.slides[0].image_prompt) == 600

    def test_missing_optional_subhead_defaults_empty(self):
        deck = ir.SlideDeck.model_validate(_deck([{"kind": "prose", "headline": "H", "body": "b"}]))
        assert deck.slides[0].subhead == ""

    def test_unicode_content_passes(self):
        deck = ir.SlideDeck.model_validate(_deck([
            {
                "kind": "prose",
                "headline": "Perpres No. 5 — İstisna €",
                "body": "Teks unicode berjalan lancar ✓ 日本語 test",
            },
        ]))
        assert "İstisna" in deck.slides[0].headline
        assert "日本語" in deck.slides[0].body

    def test_extra_unknown_fields_tolerated(self):
        deck = ir.SlideDeck.model_validate(_deck([
            {"kind": "statement", "statement": "ZERO PENALTY", "totally_unexpected_field": {"nested": True}},
        ]))
        assert deck.slides[0].statement == "ZERO PENALTY"

    def test_status_item_invalid_status_token_defaults_neutral(self):
        deck = ir.SlideDeck.model_validate(_deck([
            {
                "kind": "status_list",
                "heading": "H",
                "items": [{"label": "A", "value": "B", "status": "not-a-real-status"}],
            },
        ]))
        assert deck.slides[0].items[0].status == "neutral"

    def test_mixed_kind_list_is_fine(self):
        """A list with DIFFERENT kinds across slides is normal, not guilt —
        each element validates independently against its own declared kind."""
        deck = ir.SlideDeck.model_validate(_deck([
            {"kind": "cover", "headline": "COVER"},
            {"kind": "qa", "pairs": [{"voice": "A", "line": "q"}, {"voice": "B", "line": "a"}]},
            {"kind": "statement", "statement": "DONE"},
        ]))
        assert [s.kind for s in deck.slides] == ["cover", "qa", "statement"]

    def test_non_string_scalar_coerced_not_rejected(self):
        # a number where a string was expected — lenient coercion, not a hard fail.
        deck = ir.SlideDeck.model_validate(_deck([{"kind": "stat", "value": 2815}]))
        assert deck.slides[0].value == "2815"

    def test_triad_extra_items_within_cap_pass(self):
        items = [{"title": f"T{i}", "desc": f"D{i}"} for i in range(5)]
        deck = ir.SlideDeck.model_validate(_deck([{"kind": "triad", "heading": "H", "items": items}]))
        assert len(deck.slides[0].items) == 5


# ─────────────────────────────────────────────────────────────────────────
# extract_json_from_codeblock — ported from instructor v2 (MIT)
# ─────────────────────────────────────────────────────────────────────────


class TestExtractJsonFromCodeblock:
    def test_fenced_json_block(self):
        raw = 'Here is your answer:\n```json\n{"a": 1}\n```\nThanks!'
        assert ir.extract_json_from_codeblock(raw) == '{"a": 1}'

    def test_fenced_block_no_json_tag(self):
        raw = '```\n{"a": 1}\n```'
        assert ir.extract_json_from_codeblock(raw) == '{"a": 1}'

    def test_bare_json(self):
        raw = '{"a": 1, "b": [1, 2, 3]}'
        assert ir.extract_json_from_codeblock(raw) == raw

    def test_prose_wrapped_json(self):
        raw = "Sure, here you go: {\"a\": 1} — hope that helps!"
        assert ir.extract_json_from_codeblock(raw) == '{"a": 1}'

    def test_trailing_junk_after_json(self):
        raw = '{"a": 1}\n\nEOF garbage garbage'
        assert ir.extract_json_from_codeblock(raw) == '{"a": 1}'

    def test_nested_braces_in_strings(self):
        raw = '{"a": "text with { and } inside a string", "b": 2}'
        result = ir.extract_json_from_codeblock(raw)
        assert json.loads(result) == {"a": "text with { and } inside a string", "b": 2}

    def test_escaped_quote_inside_string_does_not_confuse_scanner(self):
        raw = r'{"a": "she said \"hi\" to {ignore this}"}'
        result = ir.extract_json_from_codeblock(raw)
        assert json.loads(result)["a"] == 'she said "hi" to {ignore this}'

    def test_no_json_returns_content_unchanged(self):
        raw = "no json here at all"
        assert ir.extract_json_from_codeblock(raw) == raw

    def test_realistic_wrapper_object(self):
        raw = (
            'Here is the deck:\n```json\n'
            '{"register": "analitico", "slides": [{"kind": "statement", "statement": "X"}]}\n'
            '```\n'
        )
        result = ir.extract_json_from_codeblock(raw)
        parsed = json.loads(result)
        assert parsed["register"] == "analitico"
        assert parsed["slides"][0]["kind"] == "statement"


# ─────────────────────────────────────────────────────────────────────────
# Projection -> REAL composer.map_slide_to_family (core Phase-1 assertion)
# ─────────────────────────────────────────────────────────────────────────

_SAMPLE_SLIDES: dict[str, dict] = {
    "cover": {"kind": "cover", "headline": "Cover Headline", "subhead": "tag"},
    "prose": {"kind": "prose", "headline": "H", "body": "body text long enough to be real"},
    "statement": {"kind": "statement", "statement": "ZERO PENALTY"},
    "fact_stack": {"kind": "fact_stack", "heading": "Facts", "facts": ["fact one", "fact two"]},
    "status_list": {
        "kind": "status_list",
        "heading": "Status",
        "items": [{"label": "A", "value": "B", "status": "positive"}],
    },
    "timeline": {
        "kind": "timeline",
        "heading": "TL",
        "steps": [{"date": "2026", "label": "X", "current": True}],
    },
    "triad": {
        "kind": "triad",
        "heading": "Forces",
        "items": [{"title": "A", "desc": "a"}, {"title": "B", "desc": "b"}, {"title": "C", "desc": "c"}],
    },
    "qa": {"kind": "qa", "pairs": [{"voice": "A", "line": "q"}, {"voice": "B", "line": "a"}]},
    "stat": {"kind": "stat", "value": "2.815T", "unit": "IDR", "label": "REVENUE", "context": "context text"},
    "citation": {
        "kind": "citation",
        "claim": "Claim text",
        "sources": [{"code": "PMK 37/2025", "issuer": "DJP"}],
    },
    "cta": {"kind": "cta", "invite": "Learn more", "trust_marker": "Verified", "reach": "10k"},
}


class TestProjectionResolvesRealFamily:
    """The core Phase-1 assertion: every one of the 11 kinds, projected via
    to_composer_dict, resolves to its intended family through the REAL
    (imported, not reimplemented) composer.map_slide_to_family."""

    def test_all_11_kinds_covered_by_the_sample_set(self):
        assert set(_SAMPLE_SLIDES) == set(ir.SLIDE_KIND_TO_FAMILY)
        assert len(_SAMPLE_SLIDES) == 11

    @pytest.mark.parametrize("kind", sorted(_SAMPLE_SLIDES))
    def test_kind_resolves_intended_family(self, kind: str):
        payload = _SAMPLE_SLIDES[kind]
        deck = ir.SlideDeck.model_validate(_deck([payload]))
        slide = deck.slides[0]
        cdict = ir.to_composer_dict(slide, index=1, total=1)
        resolved = map_slide_to_family(cdict, 1, 1)
        assert resolved == ir.SLIDE_KIND_TO_FAMILY[kind]
        # every resolved family must also be one composer actually skeletons
        # (never one of the UNDEFINED_FAMILIES from tokens.json with no .md).
        from wr2_html_renderer.composer import RENDERABLE_FAMILIES
        assert resolved in RENDERABLE_FAMILIES

    def test_fact_stack_facts_become_numbered_dict_rows(self):
        deck = ir.SlideDeck.model_validate(_deck([_SAMPLE_SLIDES["fact_stack"]]))
        cdict = ir.to_composer_dict(deck.slides[0], index=1, total=1)
        assert cdict["facts"] == [
            {"idx": 1, "this": "fact one"},
            {"idx": 2, "this": "fact two"},
        ]

    def test_triad_numeral_prefix_injected_into_headline(self):
        deck = ir.SlideDeck.model_validate(_deck([_SAMPLE_SLIDES["triad"]]))
        cdict = ir.to_composer_dict(deck.slides[0], index=1, total=1)
        # numbered-forces-list extracts {{numeral}} by regex on a leading
        # integer in the headline (composer.py `^(\d+)\s+(.*)$`) — the
        # projection must supply it there, there is no other way to set it.
        assert cdict["headline"].startswith("3 ")

    def test_qa_pairs_use_voice_line_keys_not_q_a(self):
        deck = ir.SlideDeck.model_validate(_deck([_SAMPLE_SLIDES["qa"]]))
        cdict = ir.to_composer_dict(deck.slides[0], index=1, total=1)
        assert cdict["qa_pairs"][0] == {"voice": "A", "line": "q"}
        assert cdict["qa_pairs"][1] == {"voice": "B", "line": "a"}

    def test_timeline_current_step_maps_to_yellow_accent(self):
        deck = ir.SlideDeck.model_validate(_deck([_SAMPLE_SLIDES["timeline"]]))
        cdict = ir.to_composer_dict(deck.slides[0], index=1, total=1)
        assert cdict["events"][0]["accent"] == "yellow"

    def test_timeline_non_current_step_maps_to_white_accent(self):
        payload = {
            "kind": "timeline",
            "heading": "TL",
            "steps": [{"date": "2020", "label": "past", "current": False}],
        }
        deck = ir.SlideDeck.model_validate(_deck([payload]))
        cdict = ir.to_composer_dict(deck.slides[0], index=1, total=1)
        assert cdict["events"][0]["accent"] == "white"

    def test_stat_unit_value_split_into_lead_rest_headline(self):
        deck = ir.SlideDeck.model_validate(_deck([_SAMPLE_SLIDES["stat"]]))
        cdict = ir.to_composer_dict(deck.slides[0], index=1, total=1)
        assert cdict["headline"] == "IDR / 2.815T"

    def test_stat_without_unit_headline_is_bare_value(self):
        payload = {"kind": "stat", "value": "42%"}
        deck = ir.SlideDeck.model_validate(_deck([payload]))
        cdict = ir.to_composer_dict(deck.slides[0], index=1, total=1)
        assert cdict["headline"] == "42%"

    def test_cover_is_flagged_hero_and_cover(self):
        deck = ir.SlideDeck.model_validate(_deck([_SAMPLE_SLIDES["cover"]]))
        cdict = ir.to_composer_dict(deck.slides[0], index=1, total=1)
        assert cdict["is_cover"] is True
        assert cdict["is_hero_image"] is True

    def test_non_cover_slide_is_not_flagged_hero(self):
        deck = ir.SlideDeck.model_validate(_deck([_SAMPLE_SLIDES["prose"]]))
        cdict = ir.to_composer_dict(deck.slides[0], index=2, total=5)
        assert cdict["is_cover"] is False
        assert cdict["is_hero_image"] is False

    def test_citation_row_body_key_carries_the_code(self):
        deck = ir.SlideDeck.model_validate(_deck([_SAMPLE_SLIDES["citation"]]))
        cdict = ir.to_composer_dict(deck.slides[0], index=1, total=1)
        assert cdict["citations"][0]["body"] == "PMK 37/2025"
        assert cdict["citations"][0]["issuer"] == "DJP"

    def test_explicit_layout_family_pin_is_honoured_before_auto_routing(self):
        """composer.map_slide_to_family checks an explicit `layout_family`
        pin FIRST (composer.py:143-145) — this is exactly why the projection
        works regardless of index/total/slide_type auto-routing heuristics.
        Prove it directly: a mid-deck fact_stack (index != 1, index != total)
        still resolves to evidence-carved, not the auto-router's default."""
        deck = ir.SlideDeck.model_validate(_deck([_SAMPLE_SLIDES["fact_stack"]]))
        cdict = ir.to_composer_dict(deck.slides[0], index=3, total=7)
        resolved = map_slide_to_family(cdict, 3, 7)
        assert resolved == "evidence-carved"


# ─────────────────────────────────────────────────────────────────────────
# generate_slides_typed — validate-and-retry loop against a fake call_fn
# ─────────────────────────────────────────────────────────────────────────


class TestGenerateSlidesTypedRetryLoop:
    def test_invalid_then_invalid_then_valid(self):
        responses = iter([
            "not json at all",
            '{"register": "analitico", "slides": [{"kind": "bogus"}]}',
            '{"register": "analitico", "slides": [{"kind": "statement", "statement": "OK"}]}',
        ])
        calls: list[str] = []

        def fake_call(prompt: str) -> str:
            calls.append(prompt)
            return next(responses)

        deck = ir.generate_slides_typed("base prompt", fake_call, max_retries=3)
        assert deck.slides[0].statement == "OK"
        assert len(calls) == 3
        # the 2nd/3rd prompts must carry the validation-error reask context,
        # not just the bare original prompt repeated verbatim.
        assert "Validation errors found" in calls[1]
        assert "Validation errors found" in calls[2]
        assert calls[0] == "base prompt"

    def test_always_invalid_raises_exhausted(self):
        def fake_call(prompt: str) -> str:
            return "garbage, not json"

        with pytest.raises(ir.IRValidationExhausted) as exc_info:
            ir.generate_slides_typed("base prompt", fake_call, max_retries=3)
        assert exc_info.value.last_raw_text == "garbage, not json"

    def test_valid_first_try_only_one_call(self):
        calls: list[str] = []

        def fake_call(prompt: str) -> str:
            calls.append(prompt)
            return '{"register": "analitico", "slides": [{"kind": "statement", "statement": "OK"}]}'

        ir.generate_slides_typed("base prompt", fake_call, max_retries=3)
        assert len(calls) == 1

    def test_exhausted_error_carries_last_raw_and_error(self):
        def fake_call(prompt: str) -> str:
            return '{"register": "not-a-tone", "slides": []}'

        with pytest.raises(ir.IRValidationExhausted) as exc_info:
            ir.generate_slides_typed("base prompt", fake_call, max_retries=2)
        assert exc_info.value.last_error
        assert "not-a-tone" in exc_info.value.last_raw_text
