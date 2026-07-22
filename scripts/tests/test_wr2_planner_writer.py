"""Tests for wr2_planner_writer.py — the planner/writer split (WR2
editorial-intelligence Phase 3, spec §2 "Mossa B").

Five batteries, mirroring the guilt+innocence discipline
`test_wr2_carousel_ir.py` / `test_wr2_editorial_pregate.py` already use
(cicatrix-superscar.md family #3):

  - DeckPlan/SlotPlan validation (guilt+innocence): a bad arc id, prose
    smuggled into a plan's `body` field, and a missing `arc_reason` must all
    be rejected; the innocent counterparts must all pass.
  - build_arc_priors: cooldown lowers a recently-used arc's weight but NEVER
    to zero (no hard mask on arc — a ratified, non-negotiable design rule);
    cold-start (no history, no tier) is exactly uniform.
  - write_slot kind-preservation: a fake call_fn that keeps returning the
    WRONG kind must retry then raise SlotWriteExhausted, never silently
    accept/coerce a different kind than the plan locked; the innocent
    counterpart (correct kind, first try) must return the right Slide type.
  - sibling_intents propagation: the writer prompt must contain the sibling
    slots' heading_intent TEXT — and nothing resembling their actual copy,
    which the function signature structurally cannot receive in the first
    place (sibling_intents is list[str] of intents only).
  - produce_deck assembly: spine/arc land on the assembled SlideDeck, and
    the closer slot is last.

Zero network, zero DB, zero CLI subprocess — every call_fn here is a plain
Python fake, exactly mirroring wr2_carousel_ir.py's own test discipline
(the module under test has zero I/O side effects by design).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_carousel_ir as ir  # noqa: E402
import wr2_planner_writer as pw  # noqa: E402


def _slot(**overrides) -> dict:
    base = {
        "slot_id": 1,
        "role": "hook",
        "kind": "cover",
        "heading_intent": "the headline number",
        "bullet_promise_n": None,
        "hero": True,
        "body": None,
    }
    base.update(overrides)
    return base


def _plan(**overrides) -> dict:
    base = {
        "spine": "PMK 37/2025 changes the levy math for every PMA.",
        "arc": "news_alert",
        "arc_reason": "Breaking regulation drop — needs the tight news_alert arc.",
        "slides": [_slot()],
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────────────────
# DeckPlan / SlotPlan validation — guilt + innocence
# ─────────────────────────────────────────────────────────────────────────


class TestDeckPlanValidation:
    def test_guilt_bad_arc_id_rejected(self):
        with pytest.raises(ValidationError):
            ir.DeckPlan.model_validate(_plan(arc="not_a_real_arc"))

    def test_innocence_every_ratified_arc_accepted(self):
        for arc_id in ir.ARCS:
            plan = ir.DeckPlan.model_validate(_plan(arc=arc_id))
            assert plan.arc == arc_id

    def test_guilt_prose_smuggled_into_body_slot_rejected(self):
        # A plan is zero-prose BY CONSTRUCTION — body must be null. A writer
        # or a hand-edited plan attempting to smuggle actual slide copy into
        # a slot's `body` field is a content violation, not a legitimate
        # "already-written" plan.
        with pytest.raises(ValidationError):
            ir.DeckPlan.model_validate(
                _plan(slides=[_slot(body="This slide already has real prose in it.")])
            )

    def test_innocence_null_body_in_slot_accepted(self):
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot(body=None)]))
        assert plan.slides[0].body is None

    def test_innocence_absent_body_key_defaults_to_none(self):
        slot = _slot()
        del slot["body"]
        plan = ir.DeckPlan.model_validate(_plan(slides=[slot]))
        assert plan.slides[0].body is None

    def test_innocence_empty_string_body_coerced_to_none(self):
        # "" is one of the legitimate "no content yet" spellings a
        # planner-LLM might emit — treated the same as null, not a violation.
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot(body="")]))
        assert plan.slides[0].body is None

    def test_guilt_missing_arc_reason_rejected(self):
        payload = _plan()
        del payload["arc_reason"]
        with pytest.raises(ValidationError):
            ir.DeckPlan.model_validate(payload)

    def test_guilt_empty_arc_reason_rejected(self):
        with pytest.raises(ValidationError):
            ir.DeckPlan.model_validate(_plan(arc_reason=""))

    def test_innocence_nonempty_arc_reason_accepted(self):
        plan = ir.DeckPlan.model_validate(_plan(arc_reason="A real one-line justification."))
        assert plan.arc_reason == "A real one-line justification."

    def test_guilt_missing_spine_rejected(self):
        payload = _plan()
        del payload["spine"]
        with pytest.raises(ValidationError):
            ir.DeckPlan.model_validate(payload)

    def test_guilt_unknown_slot_kind_rejected(self):
        with pytest.raises(ValidationError):
            ir.DeckPlan.model_validate(_plan(slides=[_slot(kind="not_a_real_kind")]))

    def test_innocence_every_ratified_kind_accepted_on_a_slot(self):
        for kind in ir.SLIDE_KIND_TO_FAMILY:
            plan = ir.DeckPlan.model_validate(_plan(slides=[_slot(kind=kind)]))
            assert plan.slides[0].kind == kind

    def test_guilt_missing_heading_intent_rejected(self):
        slot = _slot()
        del slot["heading_intent"]
        with pytest.raises(ValidationError):
            ir.DeckPlan.model_validate(_plan(slides=[slot]))

    def test_guilt_empty_heading_intent_rejected(self):
        with pytest.raises(ValidationError):
            ir.DeckPlan.model_validate(_plan(slides=[_slot(heading_intent="")]))


# ─────────────────────────────────────────────────────────────────────────
# build_arc_priors — CHI PROPONE, mai CHI DISPONE
# ─────────────────────────────────────────────────────────────────────────


class TestBuildArcPriors:
    def test_cold_start_is_exactly_uniform(self):
        priors = pw.build_arc_priors([], None)
        assert set(priors) == set(ir.ARCS)
        values = set(priors.values())
        assert len(values) == 1, f"cold-start priors are not uniform: {priors}"

    def test_cold_start_uniform_even_with_unknown_tier(self):
        # An unknown/manual liveness tier ("" — wr2_draft_generator's own
        # _normalise_liveness_tier collapse target) must not silently boost
        # anything: only "breaking"/"evergreen" carry a tier preference.
        priors = pw.build_arc_priors([], "")
        assert len(set(priors.values())) == 1

    def test_cooldown_lowers_recently_used_arc(self):
        priors = pw.build_arc_priors(["news_alert"], None)
        assert priors["news_alert"] < priors["deadline"]

    def test_cooldown_never_reaches_zero(self):
        # Even with the SAME arc reappearing across the whole cooldown
        # window, the floor keeps it selectable — no hard mask on arc
        # (spec §2 hard rule).
        priors = pw.build_arc_priors(["news_alert", "news_alert", "news_alert", "news_alert"], None)
        assert priors["news_alert"] > 0.0

    def test_cooldown_never_goes_negative_or_zero_across_all_arcs(self):
        recent = list(ir.ARCS) * 2  # every arc used repeatedly
        priors = pw.build_arc_priors(recent, None)
        assert all(w > 0.0 for w in priors.values())

    def test_breaking_tier_boosts_news_alert_and_deadline(self):
        uniform = pw.build_arc_priors([], None)
        breaking = pw.build_arc_priors([], "breaking")
        assert breaking["news_alert"] > uniform["news_alert"]
        assert breaking["deadline"] > uniform["deadline"]
        # Non-preferred arcs are untouched by the tier boost.
        assert breaking["myth_buster"] == uniform["myth_buster"]

    def test_evergreen_tier_boosts_worked_example_and_explainer(self):
        uniform = pw.build_arc_priors([], None)
        evergreen = pw.build_arc_priors([], "evergreen")
        assert evergreen["worked_example"] > uniform["worked_example"]
        assert evergreen["explainer"] > uniform["explainer"]
        assert evergreen["news_alert"] == uniform["news_alert"]

    def test_unknown_arc_string_in_recent_arcs_is_ignored(self):
        priors = pw.build_arc_priors(["not_a_real_arc"], None)
        assert len(set(priors.values())) == 1

    def test_returns_all_seven_ratified_arcs(self):
        priors = pw.build_arc_priors(["news_alert"], "breaking")
        assert set(priors) == set(ir.ARCS) == {
            "news_alert", "deadline", "myth_buster", "worked_example",
            "comparison", "explainer", "status_roundup",
        }


# ─────────────────────────────────────────────────────────────────────────
# write_slot — kind-preservation hard rule
# ─────────────────────────────────────────────────────────────────────────


class TestWriteSlotKindPreservation:
    def test_wrong_kind_retries_then_raises(self):
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot(kind="statement")]))
        slot = plan.slides[0]
        calls = {"n": 0}

        def bad_call_fn(prompt: str) -> str:
            calls["n"] += 1
            # ALWAYS returns the wrong kind — the writer ignoring the locked
            # plan and collapsing back onto a different shape.
            return '{"kind": "prose", "headline": "H", "body": "some body text"}'

        with pytest.raises(pw.SlotWriteExhausted) as excinfo:
            pw.write_slot("BRIEF", plan, slot, [], bad_call_fn, max_retries=3)

        assert calls["n"] == 3
        assert excinfo.value.slot_id == slot.slot_id

    def test_correct_kind_first_try_returns_matching_slide(self):
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot(kind="statement")]))
        slot = plan.slides[0]

        def good_call_fn(prompt: str) -> str:
            return '{"kind": "statement", "statement": "PMK 37/2025 changes everything."}'

        slide = pw.write_slot("BRIEF", plan, slot, [], good_call_fn, max_retries=3)
        assert isinstance(slide, ir.StatementSlide)
        assert slide.kind == "statement"

    def test_wrong_kind_then_correct_kind_recovers_on_retry(self):
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot(kind="statement")]))
        slot = plan.slides[0]
        calls = {"n": 0}

        def flaky_call_fn(prompt: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                return '{"kind": "prose", "headline": "H", "body": "wrong kind"}'
            return '{"kind": "statement", "statement": "Correct kind on retry."}'

        slide = pw.write_slot("BRIEF", plan, slot, [], flaky_call_fn, max_retries=3)
        assert isinstance(slide, ir.StatementSlide)
        assert calls["n"] == 2

    def test_malformed_json_retries_then_raises(self):
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot(kind="cover")]))
        slot = plan.slides[0]

        def broken_call_fn(prompt: str) -> str:
            return "not json at all, sorry"

        with pytest.raises(pw.SlotWriteExhausted):
            pw.write_slot("BRIEF", plan, slot, [], broken_call_fn, max_retries=2)

    def test_right_kind_but_missing_required_field_retries_then_raises(self):
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot(kind="fact_stack")]))
        slot = plan.slides[0]

        def missing_facts_call_fn(prompt: str) -> str:
            # Right kind, but `facts` (required, min_length=1) is absent.
            return '{"kind": "fact_stack", "heading": "THE NUMBERS"}'

        with pytest.raises(pw.SlotWriteExhausted):
            pw.write_slot("BRIEF", plan, slot, [], missing_facts_call_fn, max_retries=2)


# ─────────────────────────────────────────────────────────────────────────
# sibling_intents propagation — headings only, never copy
# ─────────────────────────────────────────────────────────────────────────


class TestSiblingIntentsPropagation:
    def test_writer_prompt_contains_sibling_heading_intents(self):
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot()]))
        slot = plan.slides[0]
        siblings = ["MARKER-INTENT-ALPHA the 3 conditions", "MARKER-INTENT-BETA the closing take"]

        prompt = pw._build_writer_prompt("BRIEF TEXT", plan, slot, siblings)

        for intent in siblings:
            assert intent in prompt

    def test_writer_prompt_omits_sibling_intents_when_none_given(self):
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot()]))
        slot = plan.slides[0]

        prompt = pw._build_writer_prompt("BRIEF TEXT", plan, slot, [])

        assert "none — this is the only slide" in prompt

    def test_write_slot_signature_cannot_receive_sibling_copy(self):
        # sibling_intents is typed list[str] — the ONLY thing a caller can
        # thread through is heading_intent TEXT (produce_deck below builds
        # it from `SlotPlan.heading_intent`, never from a written Slide's
        # body/facts/etc). This test locks that structural guarantee: build
        # the prompt with intents that are DELIBERATELY distinct from any
        # plausible slide copy, and assert the brief/plan frame is present
        # while nothing resembling a full written slide (e.g. a JSON blob,
        # which only a Slide's own copy would produce) appears.
        plan = ir.DeckPlan.model_validate(_plan(slides=[_slot()]))
        slot = plan.slides[0]
        siblings = ["short editorial direction only"]

        prompt = pw._build_writer_prompt("BRIEF TEXT", plan, slot, siblings)

        assert "short editorial direction only" in prompt
        assert '"kind":' not in prompt.split("SIBLING SLIDES")[1].split("OUTPUT")[0]

    def test_produce_deck_threads_only_heading_intent_never_copy(self):
        # End-to-end: produce_deck builds sibling_intents FROM plan.slides'
        # heading_intent fields — assert the writer for slot 2 actually saw
        # slot 1's heading_intent text in its prompt.
        seen_prompts: list[str] = []

        def planner_fn(prompt: str) -> str:
            return (
                '{"spine": "S", "arc": "news_alert", "arc_reason": "r", "slides": ['
                '{"slot_id": 1, "role": "hook", "kind": "cover", '
                '"heading_intent": "UNIQUE-SIBLING-MARKER-COVER", "bullet_promise_n": null, '
                '"hero": true, "body": null}, '
                '{"slot_id": 2, "role": "close", "kind": "statement", '
                '"heading_intent": "closer", "bullet_promise_n": null, "hero": false, '
                '"body": null}]}'
            )

        def writer_fn(prompt: str) -> str:
            seen_prompts.append(prompt)
            if '"kind": "cover"' in prompt:
                return '{"kind": "cover", "headline": "H", "subhead": "S"}'
            return '{"kind": "statement", "statement": "Final line."}'

        pw.produce_deck("BRIEF", "analitico", None, [], planner_fn, writer_fn)

        # The statement writer's prompt (2nd call) must have seen slide 1's
        # heading_intent as a SIBLING, never slide 1's actual written copy
        # ("H"/"S" never appear as a sibling marker anywhere).
        statement_prompt = seen_prompts[1]
        assert "UNIQUE-SIBLING-MARKER-COVER" in statement_prompt


# ─────────────────────────────────────────────────────────────────────────
# produce_deck — assembly
# ─────────────────────────────────────────────────────────────────────────


class TestProduceDeckAssembly:
    def _planner_fn(self, prompt: str) -> str:
        return (
            '{"spine": "PMK 37/2025 changes the levy math for every PMA.", '
            '"arc": "news_alert", "arc_reason": "Breaking regulation drop.", "slides": ['
            '{"slot_id": 1, "role": "hook", "kind": "cover", "heading_intent": "the number", '
            '"bullet_promise_n": null, "hero": true, "body": null}, '
            '{"slot_id": 2, "role": "fact_stack", "kind": "fact_stack", '
            '"heading_intent": "3 numbers", "bullet_promise_n": 3, "hero": false, "body": null}, '
            '{"slot_id": 3, "role": "close", "kind": "statement", '
            '"heading_intent": "The Bali Zero read — echo PMK 37/2025", "bullet_promise_n": null, '
            '"hero": false, "body": null}]}'
        )

    def _writer_fn(self, prompt: str) -> str:
        if '"kind": "cover"' in prompt:
            return '{"kind": "cover", "headline": "PMK 37 RAISES THE BAR", "subhead": "TAX", "regulation_code": "37/2025"}'
        if '"kind": "fact_stack"' in prompt:
            return '{"kind": "fact_stack", "heading": "THE NUMBERS", "facts": ["a", "b", "c"]}'
        return '{"kind": "statement", "statement": "PMK 37/2025 changes everything — read the fine print."}'

    def test_spine_and_arc_are_set_on_the_assembled_deck(self):
        deck = pw.produce_deck("BRIEF", "analitico", "breaking", [], self._planner_fn, self._writer_fn)
        assert deck.spine == "PMK 37/2025 changes the levy math for every PMA."
        assert deck.arc == "news_alert"

    def test_closer_slot_is_last(self):
        deck = pw.produce_deck("BRIEF", "analitico", "breaking", [], self._planner_fn, self._writer_fn)
        assert deck.slides[-1].kind == "statement"
        assert isinstance(deck.slides[-1], ir.StatementSlide)

    def test_cover_slot_is_first(self):
        deck = pw.produce_deck("BRIEF", "analitico", "breaking", [], self._planner_fn, self._writer_fn)
        assert deck.slides[0].kind == "cover"
        assert isinstance(deck.slides[0], ir.CoverSlide)

    def test_register_passed_through_unchanged(self):
        deck = pw.produce_deck("BRIEF", "pedagogico", "breaking", [], self._planner_fn, self._writer_fn)
        assert deck.register == "pedagogico"

    def test_slide_count_matches_plan_slot_count(self):
        deck = pw.produce_deck("BRIEF", "analitico", "breaking", [], self._planner_fn, self._writer_fn)
        assert len(deck.slides) == 3

    def test_slides_ordered_by_slot_id_even_if_plan_lists_them_out_of_order(self):
        def out_of_order_planner_fn(prompt: str) -> str:
            return (
                '{"spine": "S", "arc": "news_alert", "arc_reason": "r", "slides": ['
                '{"slot_id": 2, "role": "fact_stack", "kind": "fact_stack", '
                '"heading_intent": "3 numbers", "bullet_promise_n": 3, "hero": false, "body": null}, '
                '{"slot_id": 1, "role": "hook", "kind": "cover", "heading_intent": "the number", '
                '"bullet_promise_n": null, "hero": true, "body": null}, '
                '{"slot_id": 3, "role": "close", "kind": "statement", '
                '"heading_intent": "close", "bullet_promise_n": null, "hero": false, "body": null}]}'
            )

        deck = pw.produce_deck("BRIEF", "analitico", "breaking", [], out_of_order_planner_fn, self._writer_fn)
        assert [s.kind for s in deck.slides] == ["cover", "fact_stack", "statement"]
