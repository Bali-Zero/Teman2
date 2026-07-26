"""Tests for the WR2 production cutover — `wr2_draft_generator.py` now
drives the planner/writer engine (Phases 1-3: `wr2_carousel_ir` /
`wr2_editorial_pregate` / `wr2_planner_writer`) behind the
`WR2_COMPOSE_ENGINE` kill-switch, per
`.claude/skills/wr2/_research/2026-07-21-editorial-intelligence-design.md`
§3 rollout step 3 ("Planner/Writer dual-run — shadow accanto al monolite,
poi cutover").

Batteries:
  - engine resolution: default/explicit/invalid `WR2_COMPOSE_ENGINE` env.
  - dispatch routing: `_process_one` calls the right per-engine function
    (monolith path proven UNTOUCHED by routing, not by re-running it here —
    the existing `test_wr2_draft_generator_*` suites already cover its
    internals byte-for-byte since that code moved verbatim).
  - `_generate_planner_writer_deck`: happy path / pregate-FAIL -> repair ->
    PASS / repair-exhausted -> raises `PregateRepairExhausted`.
  - plan-level fail-fast re-plan when the closer's kind is unsafe.
  - guard adapters (`_closer_word_count_typed` / `_closer_too_long_typed` /
    `_kicker_collision_typed`) — guilt+innocence, mirroring the monolith
    guards' own test discipline.
  - `_pregate_fail_reasons_by_slot` / `_pregate_failing_slot_ids` — the
    FAIL-reason-to-slot-id mapping the repair loop depends on.
  - `_build_brief_ctx` — facts-first composition (source article leads,
    enriched brief supports — same B1 doctrine as the monolith).
  - `_pick_register_for_planner_writer` — deterministic tier-preference
    pick, anti-sameness aware.
  - `_load_forbidden_phrases_for_writer` — real constitution.md read +
    fail-open on a missing file.
  - persistence-shape assertions: `to_composer_dict` projections carry
    every field the two real downstream consumers need (composer's
    family-resolution via explicit `layout_family` pin; `wr2_html_render_
    apply`'s pass-through reader contract — `slides_json.get("slides")`, a
    plain list of dicts, no required-key assumptions beyond what
    `_normalize_heroes`/`_take_label_hard_gate_violations` already use).

Zero network, zero DB, zero CLI subprocess — every planner_fn/writer_fn
here is a plain Python fake, exactly mirroring
`test_wr2_planner_writer.py`'s own test discipline (the engine modules have
zero I/O side effects by design; the wiring in this file stays testable at
the same layer by keeping the async DB/OAuth calls at the OUTER edges only —
`_generate_planner_writer_deck` itself is the pure(ish) sync core).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_carousel_ir as ir  # noqa: E402
import wr2_draft_generator as dg  # noqa: E402
import wr2_editorial_pregate as pregate  # noqa: E402
import wr2_planner_writer as pw  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────
# Fixed fake planner/writer plumbing (mirrors test_wr2_planner_writer.py)
# ─────────────────────────────────────────────────────────────────────────

_HAPPY_PLAN = (
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


def _happy_planner_fn(prompt: str) -> str:
    return _HAPPY_PLAN


def _happy_writer_fn(prompt: str) -> str:
    if '"kind": "cover"' in prompt:
        return '{"kind": "cover", "headline": "PMK 37 RAISES THE BAR", "subhead": "TAX", "regulation_code": "37/2025"}'
    if '"kind": "fact_stack"' in prompt:
        return '{"kind": "fact_stack", "heading": "THE NUMBERS", "facts": ["a", "b", "c"]}'
    return '{"kind": "statement", "statement": "PMK 37/2025 changes everything — read the fine print now."}'


# ─────────────────────────────────────────────────────────────────────────
# Engine resolution (kill-switch)
# ─────────────────────────────────────────────────────────────────────────


class TestComposeEngineResolution:
    def test_default_is_planner_writer(self, monkeypatch):
        monkeypatch.delenv("WR2_COMPOSE_ENGINE", raising=False)
        assert dg._resolve_compose_engine() == "planner_writer"

    def test_explicit_monolith(self, monkeypatch):
        monkeypatch.setenv("WR2_COMPOSE_ENGINE", "monolith")
        assert dg._resolve_compose_engine() == "monolith"

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("WR2_COMPOSE_ENGINE", "MONOLITH")
        assert dg._resolve_compose_engine() == "monolith"

    def test_unrecognized_value_falls_back_to_planner_writer(self, monkeypatch):
        monkeypatch.setenv("WR2_COMPOSE_ENGINE", "some_typo")
        assert dg._resolve_compose_engine() == "planner_writer"

    def test_whitespace_tolerant(self, monkeypatch):
        monkeypatch.setenv("WR2_COMPOSE_ENGINE", "  monolith  ")
        assert dg._resolve_compose_engine() == "monolith"


# ─────────────────────────────────────────────────────────────────────────
# Dispatch routing — _process_one calls the right per-engine function
# ─────────────────────────────────────────────────────────────────────────


class TestDispatchRouting:
    def _row(self) -> dict:
        return {
            "id": "11111111-1111-1111-1111-111111111111",
            # Deliberately NOT news-shaped (no news-event verb, no staging_type
            # 'news', no liveness_tier) so the shared B2 park-check short-circuits
            # to False and both branches are reachable without a real DB/park path.
            "topic": "Understanding Indonesian company registration timelines",
            "brief_json": '{"article_summary": "some summary text here"}',
        }

    @pytest.mark.asyncio
    async def test_monolith_engine_calls_process_one_monolith(self, monkeypatch):
        monkeypatch.setenv("WR2_COMPOSE_ENGINE", "monolith")
        called = {}

        async def fake_monolith(conn, draft_id, topic, brief, summary, source_url, enrichment, live_reasons, liveness_tier):
            called["engine"] = "monolith"
            return "success"

        async def fake_planner_writer(*args, **kwargs):
            called["engine"] = "planner_writer"
            return "success"

        monkeypatch.setattr(dg, "_process_one_monolith", fake_monolith)
        monkeypatch.setattr(dg, "_process_one_planner_writer", fake_planner_writer)

        outcome = await dg._process_one(conn=None, row=self._row())
        assert outcome == "success"
        assert called["engine"] == "monolith"

    @pytest.mark.asyncio
    async def test_default_engine_calls_process_one_planner_writer(self, monkeypatch):
        monkeypatch.delenv("WR2_COMPOSE_ENGINE", raising=False)
        called = {}

        async def fake_monolith(*args, **kwargs):
            called["engine"] = "monolith"
            return "success"

        async def fake_planner_writer(conn, draft_id, topic, brief, summary, source_url, enrichment, live_reasons, liveness_tier):
            called["engine"] = "planner_writer"
            return "success"

        monkeypatch.setattr(dg, "_process_one_monolith", fake_monolith)
        monkeypatch.setattr(dg, "_process_one_planner_writer", fake_planner_writer)

        outcome = await dg._process_one(conn=None, row=self._row())
        assert outcome == "success"
        assert called["engine"] == "planner_writer"


# ─────────────────────────────────────────────────────────────────────────
# _generate_planner_writer_deck — happy path / repair / exhaustion
# ─────────────────────────────────────────────────────────────────────────


class TestGenerateDeckHappyPath:
    def test_happy_path_no_repair_needed(self):
        deck, meta = dg._generate_planner_writer_deck(
            "BRIEF", "analitico", "breaking", [], _happy_planner_fn, _happy_writer_fn, [],
        )
        assert meta["pregate_verdict"] in ("PASS", "WARN")
        assert meta["repair_rounds"] == 0
        assert deck.arc == "news_alert"
        assert deck.spine == "PMK 37/2025 changes the levy math for every PMA."
        assert [s.kind for s in deck.slides] == ["cover", "fact_stack", "statement"]

    def test_forbidden_phrases_threaded_into_writer_prompt(self):
        seen_prompts = []

        def spying_writer_fn(prompt: str) -> str:
            seen_prompts.append(prompt)
            return _happy_writer_fn(prompt)

        dg._generate_planner_writer_deck(
            "BRIEF", "analitico", "breaking", [], _happy_planner_fn, spying_writer_fn,
            ["some banned phrase"],
        )
        assert any('"some banned phrase"' in p for p in seen_prompts)


class TestGenerateDeckRepair:
    def test_pregate_fail_then_repair_then_pass(self):
        plan = (
            '{"spine": "PMK 37/2025 changes the levy math for every PMA.", '
            '"arc": "news_alert", "arc_reason": "Breaking regulation drop.", "slides": ['
            '{"slot_id": 1, "role": "hook", "kind": "cover", "heading_intent": "the number", '
            '"bullet_promise_n": null, "hero": true, "body": null}, '
            '{"slot_id": 2, "role": "close", "kind": "statement", '
            '"heading_intent": "The Bali Zero read", "bullet_promise_n": null, "hero": false, '
            '"body": null}]}'
        )

        def planner_fn(prompt: str) -> str:
            return plan

        calls = {"n": 0}

        def writer_fn(prompt: str) -> str:
            calls["n"] += 1
            if '"kind": "cover"' in prompt:
                return '{"kind": "cover", "headline": "PMK 37 RAISES THE BAR", "subhead": "TAX"}'
            # First attempt: closer shares ZERO fact-key tokens with the spine
            # (no "PMK"/"37"/"2025") -> check_spine_echo FAILs. The repair round
            # injects PREGATE FEEDBACK into the prompt; only THEN does the writer
            # echo the spine's fact-key tokens.
            if "PREGATE FEEDBACK" in prompt:
                return '{"kind": "statement", "statement": "PMK 37/2025 changes everything now."}'
            return '{"kind": "statement", "statement": "Read the fine print before you file anything."}'

        deck, meta = dg._generate_planner_writer_deck(
            "BRIEF", "analitico", "breaking", [], planner_fn, writer_fn, [],
        )
        assert meta["pregate_verdict"] == "PASS"
        assert meta["repair_rounds"] == 1
        assert calls["n"] == 3  # cover + closer(fail) + closer(repaired)
        assert "PMK 37/2025" in deck.slides[-1].statement

    def test_repair_targets_only_the_failing_slot(self):
        # Same setup, but track WHICH slot_id gets a second write call — the
        # cover slide must be written exactly once (it never fails any check
        # here), the closer twice (fail then repair).
        plan = (
            '{"spine": "PMK 37/2025 changes the levy math for every PMA.", '
            '"arc": "news_alert", "arc_reason": "r", "slides": ['
            '{"slot_id": 1, "role": "hook", "kind": "cover", "heading_intent": "the number", '
            '"bullet_promise_n": null, "hero": true, "body": null}, '
            '{"slot_id": 2, "role": "close", "kind": "statement", '
            '"heading_intent": "close", "bullet_promise_n": null, "hero": false, "body": null}]}'
        )

        def planner_fn(prompt: str) -> str:
            return plan

        cover_calls = {"n": 0}
        closer_calls = {"n": 0}

        def writer_fn(prompt: str) -> str:
            if '"kind": "cover"' in prompt:
                cover_calls["n"] += 1
                return '{"kind": "cover", "headline": "H", "subhead": "S"}'
            closer_calls["n"] += 1
            if "PREGATE FEEDBACK" in prompt:
                return '{"kind": "statement", "statement": "PMK 37/2025, read this now."}'
            return '{"kind": "statement", "statement": "Totally unrelated punch line."}'

        dg._generate_planner_writer_deck(
            "BRIEF", "analitico", "breaking", [], planner_fn, writer_fn, [],
        )
        assert cover_calls["n"] == 1
        assert closer_calls["n"] == 2


class TestGenerateDeckRepairExhausted:
    def test_repair_exhausted_raises_pregate_repair_exhausted(self):
        plan = (
            '{"spine": "PMK 37/2025 changes the levy math for every PMA.", '
            '"arc": "news_alert", "arc_reason": "r", "slides": ['
            '{"slot_id": 1, "role": "hook", "kind": "cover", "heading_intent": "the number", '
            '"bullet_promise_n": null, "hero": true, "body": null}, '
            '{"slot_id": 2, "role": "close", "kind": "statement", '
            '"heading_intent": "close", "bullet_promise_n": null, "hero": false, "body": null}]}'
        )

        def planner_fn(prompt: str) -> str:
            return plan

        def writer_fn(prompt: str) -> str:
            if '"kind": "cover"' in prompt:
                return '{"kind": "cover", "headline": "H", "subhead": "S"}'
            # NEVER echoes the spine, regardless of repair rounds.
            return '{"kind": "statement", "statement": "Completely unrelated to the topic."}'

        with pytest.raises(dg.PregateRepairExhausted) as excinfo:
            dg._generate_planner_writer_deck(
                "BRIEF", "analitico", "breaking", [], planner_fn, writer_fn, [],
            )
        assert excinfo.value.report.verdict == "FAIL"
        assert any(c.check == "check_spine_echo" for c in excinfo.value.report.checks if c.verdict == "FAIL")

    def test_never_ships_a_failing_deck(self):
        # The exhaustion path must ALWAYS raise, never silently return a
        # deck whose pregate verdict is FAIL. Spine MUST carry an
        # extractable fact-key token (>=5 char content word / acronym /
        # number) or check_spine_echo SKIPs instead of FAILing — mirrors
        # the real-world spine shape (a regulation reference), not a
        # degenerate fixture.
        plan = (
            '{"spine": "PMK 37/2025 changes the levy math for every PMA.", '
            '"arc": "news_alert", "arc_reason": "r", "slides": ['
            '{"slot_id": 1, "role": "hook", "kind": "cover", "heading_intent": "h", '
            '"bullet_promise_n": null, "hero": true, "body": null}, '
            '{"slot_id": 2, "role": "close", "kind": "statement", "heading_intent": "c", '
            '"bullet_promise_n": null, "hero": false, "body": null}]}'
        )

        def planner_fn(prompt: str) -> str:
            return plan

        def writer_fn(prompt: str) -> str:
            if '"kind": "cover"' in prompt:
                return '{"kind": "cover", "headline": "H", "subhead": "S"}'
            return '{"kind": "statement", "statement": "Nothing to do with the spine at all."}'

        try:
            dg._generate_planner_writer_deck("BRIEF", "analitico", None, [], planner_fn, writer_fn, [])
            pytest.fail("expected PregateRepairExhausted, deck was returned instead")
        except dg.PregateRepairExhausted:
            pass


class TestPlanLevelCloserSafetyFailFast:
    def test_replans_when_closer_kind_is_unsafe(self):
        # First plan attempt gives the closer an unsafe kind (fact_stack —
        # not in _CLOSER_SAFE_KINDS); the SECOND plan attempt fixes it. This
        # must re-plan (a fresh plan_deck call), never force a kind onto the
        # planner's own choice.
        plan_calls = {"n": 0}

        def flaky_planner_fn(prompt: str) -> str:
            plan_calls["n"] += 1
            if plan_calls["n"] == 1:
                return (
                    '{"spine": "S.", "arc": "news_alert", "arc_reason": "r", "slides": ['
                    '{"slot_id": 1, "role": "hook", "kind": "cover", "heading_intent": "h", '
                    '"bullet_promise_n": null, "hero": true, "body": null}, '
                    '{"slot_id": 2, "role": "close", "kind": "fact_stack", "heading_intent": "c", '
                    '"bullet_promise_n": 2, "hero": false, "body": null}]}'
                )
            return (
                '{"spine": "S.", "arc": "news_alert", "arc_reason": "r", "slides": ['
                '{"slot_id": 1, "role": "hook", "kind": "cover", "heading_intent": "h", '
                '"bullet_promise_n": null, "hero": true, "body": null}, '
                '{"slot_id": 2, "role": "close", "kind": "statement", "heading_intent": "c", '
                '"bullet_promise_n": null, "hero": false, "body": null}]}'
            )

        def writer_fn(prompt: str) -> str:
            if '"kind": "cover"' in prompt:
                return '{"kind": "cover", "headline": "H", "subhead": "S"}'
            return '{"kind": "statement", "statement": "S echoes S here now."}'

        deck, meta = dg._generate_planner_writer_deck(
            "BRIEF", "analitico", None, [], flaky_planner_fn, writer_fn, [],
        )
        assert plan_calls["n"] == 2
        assert deck.slides[-1].kind == "statement"

    def test_gives_up_after_max_plan_attempts_and_lets_pregate_catch_it(self):
        # Every plan attempt keeps the unsafe kind — after max_plan_attempts
        # the function proceeds anyway (never infinite-loops); the ensuing
        # check_cta_presence FAIL is caught by the normal repair/exhaustion
        # path, never silently accepted.
        def stubborn_planner_fn(prompt: str) -> str:
            return (
                '{"spine": "S.", "arc": "news_alert", "arc_reason": "r", "slides": ['
                '{"slot_id": 1, "role": "hook", "kind": "cover", "heading_intent": "h", '
                '"bullet_promise_n": null, "hero": true, "body": null}, '
                '{"slot_id": 2, "role": "close", "kind": "fact_stack", "heading_intent": "c", '
                '"bullet_promise_n": 2, "hero": false, "body": null}]}'
            )

        def writer_fn(prompt: str) -> str:
            if '"kind": "cover"' in prompt:
                return '{"kind": "cover", "headline": "H", "subhead": "S"}'
            return '{"kind": "fact_stack", "heading": "S", "facts": ["S one", "S two"]}'

        with pytest.raises(dg.PregateRepairExhausted) as excinfo:
            dg._generate_planner_writer_deck(
                "BRIEF", "analitico", None, [], stubborn_planner_fn, writer_fn, [],
                max_plan_attempts=2,
            )
        assert any(c.check == "check_cta_presence" for c in excinfo.value.report.checks if c.verdict == "FAIL")


# ─────────────────────────────────────────────────────────────────────────
# _pregate_fail_reasons_by_slot / _pregate_failing_slot_ids
# ─────────────────────────────────────────────────────────────────────────


class TestPregateFailReasonMapping:
    def _deck(self) -> ir.SlideDeck:
        return ir.SlideDeck.model_validate({
            "register": "analitico",
            "spine": "PMK 37/2025 changes the levy math.",
            "arc": "news_alert",
            "slides": [
                {"kind": "cover", "headline": "PMK 37 RAISES THE BAR", "subhead": "TAX"},
                {"kind": "fact_stack", "heading": "THE NUMBERS", "facts": ["a", "b", "c"]},
                {"kind": "fact_stack", "heading": "THE NUMBERS", "facts": ["a", "b", "c"]},
            ],
        })

    def test_maps_fail_reasons_to_slot_ids(self):
        report = pregate.pregate_typed(self._deck(), spine="PMK 37/2025 changes the levy math.")
        assert report.verdict == "FAIL"
        ids = dg._pregate_failing_slot_ids(report)
        # Slide 3 is the closer (fails check_cta_presence + check_spine_echo +
        # shares its kicker with slide 2); slide 2 shares the kicker with 3.
        assert 3 in ids
        assert 2 in ids

    def test_never_names_a_passing_check(self):
        report = pregate.pregate_typed(self._deck(), spine="PMK 37/2025 changes the levy math.")
        reasons_by_slot = dg._pregate_fail_reasons_by_slot(report)
        for reasons in reasons_by_slot.values():
            for reason in reasons:
                check_name = reason.split(":", 1)[0]
                matching = [c for c in report.checks if c.check == check_name]
                assert matching and matching[0].verdict == "FAIL"

    def test_pass_verdict_yields_empty_mapping(self):
        deck = ir.SlideDeck.model_validate({
            "register": "analitico",
            "spine": "PMK 37/2025 changes the levy math for every PMA.",
            "arc": "news_alert",
            "slides": [
                {"kind": "cover", "headline": "PMK 37 RAISES THE BAR", "subhead": "TAX"},
                {"kind": "statement", "statement": "PMK 37/2025 changes everything, read the fine print."},
            ],
        })
        report = pregate.pregate_typed(deck, spine=deck.spine)
        assert report.verdict != "FAIL"
        assert dg._pregate_failing_slot_ids(report) == set()


# ─────────────────────────────────────────────────────────────────────────
# Guard adapters — guilt + innocence
# ─────────────────────────────────────────────────────────────────────────


class TestClosestWordCountTypedAdapter:
    def test_reads_statement_field(self):
        slides = [{}, {"statement": "one two three"}]
        assert dg._closer_word_count_typed(slides) == 3

    def test_reads_invite_field_when_no_statement(self):
        slides = [{}, {"invite": "if your case touches this a call confirms next steps"}]
        assert dg._closer_word_count_typed(slides) == 10

    def test_statement_takes_precedence_over_invite(self):
        slides = [{}, {"statement": "one two", "invite": "one two three four five"}]
        assert dg._closer_word_count_typed(slides) == 2

    def test_empty_list_is_zero(self):
        assert dg._closer_word_count_typed([]) == 0

    def test_short_closer_not_flagged(self):
        slides = [{}, {"statement": "Bali doesn't wait. Neither should you."}]
        assert not dg._closer_too_long_typed(slides)

    def test_long_closer_flagged(self):
        long_statement = " ".join(f"word{i}" for i in range(dg.CLOSER_MAX_WORDS + 3))
        slides = [{}, {"statement": long_statement}]
        assert dg._closer_too_long_typed(slides)


class TestKickerCollisionTypedAdapter:
    def test_guilt_take_label_collides_with_recent(self):
        slides = [{}, {"layout_family": "evidence-carved", "take_label": "THE SIGNAL"}]
        hit = dg._kicker_collision_typed(slides, ["THE SIGNAL"])
        assert hit == "THE SIGNAL"

    def test_innocence_no_recent_kickers(self):
        slides = [{}, {"take_label": "THE SIGNAL"}]
        assert dg._kicker_collision_typed(slides, []) is None

    def test_innocence_substring_does_not_collide(self):
        # scar family #3: "TAKEAWAY FOR SELLERS" must NOT match "TAKE".
        slides = [{}, {"take_label": "TAKEAWAY FOR SELLERS"}]
        assert dg._kicker_collision_typed(slides, ["TAKE"]) is None

    def test_innocence_no_take_label_field(self):
        slides = [{}, {"layout_family": "statement-bomb", "statement": "no kicker here"}]
        assert dg._kicker_collision_typed(slides, ["THE SIGNAL"]) is None

    def test_whole_string_normalization_still_collides(self):
        slides = [{}, {"take_label": "the signal:"}]
        assert dg._kicker_collision_typed(slides, ["THE SIGNAL"]) == "the signal:"


# ─────────────────────────────────────────────────────────────────────────
# _build_brief_ctx — facts-first composition
# ─────────────────────────────────────────────────────────────────────────


class TestBuildBriefCtx:
    def test_article_summary_leads_when_both_present(self):
        ctx = dg._build_brief_ctx(
            topic="Deportation case", summary="A concrete deportation event happened yesterday.",
            source_url="https://example.com", enrichment={"the_facts": "Some enriched facts here."},
            live_reasons=[], liveness_tier="breaking",
        )
        source_idx = ctx.find("Source article")
        support_idx = ctx.find("Supporting brief")
        assert source_idx != -1 and support_idx != -1
        assert source_idx < support_idx
        assert "A concrete deportation event happened yesterday." in ctx

    def test_liveness_framing_injected_for_breaking(self):
        ctx = dg._build_brief_ctx(
            topic="T", summary="S", source_url="", enrichment=None, live_reasons=[],
            liveness_tier="breaking",
        )
        assert "BREAKING" in ctx

    def test_no_framing_for_unknown_tier(self):
        ctx = dg._build_brief_ctx(
            topic="T", summary="S", source_url="", enrichment=None, live_reasons=[],
            liveness_tier="",
        )
        assert "EDITORIAL CONTEXT" not in ctx

    def test_falls_back_to_summary_only_when_no_enrichment(self):
        ctx = dg._build_brief_ctx(
            topic="T", summary="Just the summary text.", source_url="", enrichment=None,
            live_reasons=[], liveness_tier="",
        )
        assert "Just the summary text." in ctx
        assert "Supporting brief" not in ctx


# ─────────────────────────────────────────────────────────────────────────
# _pick_register_for_planner_writer
# ─────────────────────────────────────────────────────────────────────────


class TestPickRegister:
    def test_breaking_picks_a_preferred_tone(self):
        register = dg._pick_register_for_planner_writer("breaking", [])
        assert register in dg._TONE_PREFERENCE["breaking"]

    def test_avoids_most_recently_used_preferred_tone(self):
        prefs = dg._TONE_PREFERENCE["breaking"]
        register = dg._pick_register_for_planner_writer("breaking", [prefs[0]])
        assert register == prefs[1]

    def test_unknown_tier_falls_back_to_full_valid_tones(self):
        register = dg._pick_register_for_planner_writer("", [])
        assert register in dg.VALID_TONES

    def test_always_returns_a_valid_tone(self):
        for tier in ("breaking", "developing", "evergreen", ""):
            assert dg._pick_register_for_planner_writer(tier, []) in dg.VALID_TONES


# ─────────────────────────────────────────────────────────────────────────
# _load_forbidden_phrases_for_writer — real file + fail-open
# ─────────────────────────────────────────────────────────────────────────


class TestForbiddenPhrasesLoader:
    def test_loads_real_constitution_nonempty(self):
        phrases = dg._load_forbidden_phrases_for_writer()
        assert isinstance(phrases, list)
        assert len(phrases) > 0

    def test_fail_open_on_missing_file(self, tmp_path):
        missing = tmp_path / "does_not_exist.md"
        phrases = dg._load_forbidden_phrases_for_writer(missing)
        assert phrases == []

    def test_fail_open_on_file_with_no_article_7(self, tmp_path):
        p = tmp_path / "constitution.md"
        p.write_text("# Some doc\n\n## Article 1 — Nothing relevant\n\nblah\n\n## Article 2 — Also nothing\n")
        assert dg._load_forbidden_phrases_for_writer(p) == []


# ─────────────────────────────────────────────────────────────────────────
# Persistence shape — every consumer in the map keeps working
# ─────────────────────────────────────────────────────────────────────────


class TestPersistenceShapeConsumerContract:
    def _happy_deck(self) -> ir.SlideDeck:
        deck, _meta = dg._generate_planner_writer_deck(
            "BRIEF", "analitico", "breaking", [], _happy_planner_fn, _happy_writer_fn, [],
        )
        return deck

    def test_projected_slides_are_plain_dicts_in_a_list(self):
        deck = self._happy_deck()
        projected = [ir.to_composer_dict(s, index=i, total=len(deck.slides)) for i, s in enumerate(deck.slides, start=1)]
        assert isinstance(projected, list)
        assert all(isinstance(s, dict) for s in projected)

    def test_every_slide_has_an_explicit_renderable_layout_family(self):
        # composer.map_slide_to_family honours an explicit `layout_family`
        # pin before any auto-routing heuristic — the contract this whole
        # cutover leans on to reach the 11 non-auto-reachable families.
        deck = self._happy_deck()
        projected = [ir.to_composer_dict(s, index=i, total=len(deck.slides)) for i, s in enumerate(deck.slides, start=1)]
        for slide in projected:
            assert slide.get("layout_family") in ir.SLIDE_KIND_TO_FAMILY.values()

    def test_cover_slide_carries_is_cover_is_hero_and_image_prompt(self):
        # wr2_html_render_apply._normalize_heroes reads is_hero_image (or
        # falls back to index==1) + image_url/hero_image_path;
        # generate_cover_image (the shared cron helper) reads
        # projected[0]["image_prompt"].
        deck = self._happy_deck()
        cover = ir.to_composer_dict(deck.slides[0], index=1, total=len(deck.slides))
        assert cover["is_cover"] is True
        assert cover["is_hero_image"] is True
        assert "image_prompt" in cover

    def test_persisted_council_meta_carries_arc_spine_reason(self):
        # fetch_recent_arcs reads council_debate_json->>'arc' — this is the
        # ONLY place `arc` is persisted (no schema migration; the existing
        # council_debate_json JSON column, least-invasive per the cutover
        # mandate).
        deck, meta = dg._generate_planner_writer_deck(
            "BRIEF", "analitico", "breaking", [], _happy_planner_fn, _happy_writer_fn, [],
        )
        council_meta = {
            "engine": "planner_writer",
            "spine": deck.spine,
            "arc": deck.arc,
            "arc_reason": meta.get("arc_reason"),
        }
        assert council_meta["arc"] == "news_alert"
        assert council_meta["spine"]
        assert council_meta["arc_reason"]

    def test_render_apply_take_label_hard_gate_sees_no_banned_vocabulary(self):
        # wr2_html_render_apply._take_label_hard_gate_violations reads
        # slide.get("take_label") on every slide — the writer's per-kind
        # constitutional constraints block explicitly bans the same
        # TAKE_LABEL_BANNED vocabulary composer.py enforces at render time.
        # This is a SMOKE check the projected fact_stack slide's take_label
        # (if any) is not literally one of the banned strings when the
        # writer never used one (the happy-path fixture writer never sets
        # take_label at all).
        deck = self._happy_deck()
        projected = [ir.to_composer_dict(s, index=i, total=len(deck.slides)) for i, s in enumerate(deck.slides, start=1)]
        for slide in projected:
            take_label = str(slide.get("take_label") or "").strip().upper()
            assert take_label not in pw._TAKE_LABEL_BANNED


# ─────────────────────────────────────────────────────────────────────────
# fetch_recent_arcs / fetch_recent_editorial_signatures — pure parsing
# (via a fake asyncpg-shaped connection; no real DB)
# ─────────────────────────────────────────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        return dict.__getitem__(self, key)


class _FakeConn:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    async def fetch(self, *args, **kwargs):
        return [_FakeRow(r) for r in self._rows]


class TestFetchRecentArcs:
    @pytest.mark.asyncio
    async def test_extracts_arc_from_council_debate_json(self):
        conn = _FakeConn([
            {"council_debate_json": '{"engine": "planner_writer", "arc": "news_alert"}'},
            {"council_debate_json": '{"engine": "planner_writer", "arc": "myth_buster"}'},
        ])
        arcs = await dg.fetch_recent_arcs(conn, limit=8)
        assert arcs == ["news_alert", "myth_buster"]

    @pytest.mark.asyncio
    async def test_monolith_rows_with_no_arc_key_contribute_nothing(self):
        conn = _FakeConn([
            {"council_debate_json": '{"register_reason": "some monolith row", "cover_url": null}'},
        ])
        arcs = await dg.fetch_recent_arcs(conn, limit=8)
        assert arcs == []

    @pytest.mark.asyncio
    async def test_malformed_row_isolated_others_survive(self):
        conn = _FakeConn([
            {"council_debate_json": "not json at all"},
            {"council_debate_json": '{"arc": "deadline"}'},
        ])
        arcs = await dg.fetch_recent_arcs(conn, limit=8)
        assert arcs == ["deadline"]

    @pytest.mark.asyncio
    async def test_cold_start_empty_list(self):
        conn = _FakeConn([])
        arcs = await dg.fetch_recent_arcs(conn, limit=8)
        assert arcs == []

    @pytest.mark.asyncio
    async def test_connection_error_returns_empty_never_raises(self):
        class BoomConn:
            async def fetch(self, *args, **kwargs):
                raise RuntimeError("connection lost")

        arcs = await dg.fetch_recent_arcs(BoomConn(), limit=8)
        assert arcs == []


class TestFetchRecentEditorialSignaturesExtendedForTakeLabel:
    @pytest.mark.asyncio
    async def test_take_label_recognized_as_kicker_source(self):
        conn = _FakeConn([
            {"slides_json": '{"slides": [{"kind": "fact_stack", "layout_family": "evidence-carved", '
             '"take_label": "THE PRECEDENT", "headline": "H"}]}'},
        ])
        sig = await dg.fetch_recent_editorial_signatures(conn, limit=10)
        assert "THE PRECEDENT" in sig["kickers"]

    @pytest.mark.asyncio
    async def test_monolith_and_planner_writer_kickers_share_one_dedup_set(self):
        conn = _FakeConn([
            {"slides_json": '{"slides": [{"slide_type": "take", "headline": "THE SIGNAL: a headline"}]}'},
            {"slides_json": '{"slides": [{"take_label": "THE SIGNAL"}]}'},
        ])
        sig = await dg.fetch_recent_editorial_signatures(conn, limit=10)
        # Both rows normalize to the same kicker key — only the FIRST
        # occurrence's casing survives (dedup, mirroring the existing
        # kickers/subheads dedup discipline).
        assert sig["kickers"].count("THE SIGNAL") + sum(1 for k in sig["kickers"] if k.upper() == "THE SIGNAL") >= 1
        normalized = {dg._normalize_kicker(k) for k in sig["kickers"]}
        assert dg._normalize_kicker("THE SIGNAL") in normalized
        assert len([k for k in sig["kickers"] if dg._normalize_kicker(k) == dg._normalize_kicker("THE SIGNAL")]) == 1
