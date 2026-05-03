"""Unit tests for register prompt definitions + rendering."""

from __future__ import annotations

from backend.services.council.prompts import (
    CLICKBAIT_BANLIST,
    PROPONENT_PERSONAS,
    REGISTER_PROMPTS,
    render_round_0_prompt,
    render_round_1_prompt,
    render_round_2_judge_prompt,
)
from backend.services.war_room.models import RegisterTone


def test_all_seven_registers_present():
    assert set(REGISTER_PROMPTS.keys()) == set(RegisterTone)


def test_each_register_has_complete_definition():
    for tone, definition in REGISTER_PROMPTS.items():
        assert definition.name == tone.value
        assert len(definition.voice) > 10
        assert len(definition.when_to_use) > 10
        assert len(definition.platforms) >= 1
        assert len(definition.example_headline) > 5
        assert len(definition.example_opening) > 5
        assert len(definition.anti_pattern) > 5


def test_banlist_includes_scar_formulas():
    """The banlist must include formulas detected in War Room v1 clickbait audit."""
    banlist_lower = {b.lower() for b in CLICKBAIT_BANLIST}
    assert "quello che non ti dicono" in banlist_lower
    assert "trap" in banlist_lower
    assert "death clock" in banlist_lower
    assert "kill-switch" in banlist_lower


def test_proponent_personas_for_three_models():
    assert set(PROPONENT_PERSONAS) == {"claude", "gemini", "deepseek"}


def test_round_0_prompt_contains_all_seven_registers():
    prompt = render_round_0_prompt(
        proponent="claude",
        topic="B211A extension",
        research_json='{"facts": []}',
        brand_constraints="editorial, no clickbait",
    )
    for tone in RegisterTone:
        assert tone.value in prompt
    assert "B211A extension" in prompt
    assert "critico editoriale" in prompt  # claude persona


def test_round_0_prompt_uses_gemini_persona():
    prompt = render_round_0_prompt(
        proponent="gemini",
        topic="x",
        research_json="{}",
        brand_constraints="",
    )
    assert "linguista pragmatico" in prompt


def test_round_0_prompt_handles_missing_reflection():
    prompt = render_round_0_prompt(
        proponent="claude",
        topic="x",
        research_json="{}",
        brand_constraints="",
        self_reflection="",
    )
    assert "nessuna riflessione precedente" in prompt


def test_round_1_challenge_prompt_shape():
    prompt = render_round_1_prompt(
        "claude",
        '[{"author": "gemini", "register": "ironico"}]',
    )
    assert "best_not_mine" in prompt
    assert "worst" in prompt
    assert "niente insulti" in prompt
    assert "critico editoriale" in prompt


def test_round_2_judge_prompt_includes_banlist_and_hard_rules():
    prompt = render_round_2_judge_prompt(
        topic="Permenkumham 22/2023",
        brand_constraints="editorial",
        registers_last_14d="analitico=4, ironico=1",
        recent_scars="avoided trap metaphor",
        all_proposals_json="[]",
        challenges_json="[]",
    )
    assert "Max 3 post dello stesso registro" in prompt
    assert '"quello che non ti dicono"' in prompt
    assert "Permenkumham 22/2023" in prompt
    assert "analitico=4" in prompt


def test_register_definition_prompt_block_deterministic():
    """Same RegisterDefinition rendered twice must produce identical output."""
    tone = RegisterTone.TECNICO
    a = REGISTER_PROMPTS[tone].as_prompt_block()
    b = REGISTER_PROMPTS[tone].as_prompt_block()
    assert a == b
    assert "tecnico" in a
    assert "Permenkumham" in a
