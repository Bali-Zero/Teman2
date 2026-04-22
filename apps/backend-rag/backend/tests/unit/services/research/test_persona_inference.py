"""Tests for persona_inference — Persona dataclass + Gate 4 validator."""

from __future__ import annotations

import pytest
from backend.services.research.persona_inference import (
    Persona,
    PersonaInferenceAgent,
    PersonaValidationError,
)


def _complete_persona_kwargs() -> dict:
    """Helper: kwargs for a Persona that passes Gate 4."""
    return dict(
        slug="expat_boomer_retiree",
        market_segment="expat",
        age_range="55-70",
        geo_origin="EU + North America",
        gender_split="50/50",
        profession_past="middle manager, doctor, lawyer",
        wealth_level="300k-1M USD liquid",
        primary_goal="retire in Bali legally",
        pain_points=["KITAS renewal complexity", "tax residency confusion", "healthcare"],
        platforms_used=["facebook_groups", "instagram", "newsletter"],
        content_preferences=["long form", "case studies"],
        language_primary="english",
        language_secondary=["italian", "german"],
        decision_journey_stages=["awareness", "research", "consideration", "decision"],
        tone_resonance={"pedagogico": 0.4, "analitico": 0.3, "rituale": 0.2, "tecnico": 0.1},
        hook_patterns_that_work=["story", "question"],
        verbatim_quotes=[
            "I'm 62, wife 58, we want a 10-year plan...",
            "My pension from Germany, does Indonesia tax it?",
            "I keep reading conflicting answers about KITAS 2...",
        ],
        trust_signals=["google_reviews", "referral_chain", "press_mentions"],
    )


def test_persona_validates_when_complete():
    p = Persona(**_complete_persona_kwargs())
    p.validate()  # no exception


def test_persona_counts_populated_attrs_excludes_slug_and_segment():
    """slug + market_segment are identity fields, not counted in ≥15 count."""
    p = Persona(**_complete_persona_kwargs())
    # 16 non-identity fields all populated → count should be 16
    assert p.count_populated_attrs() == 16


def test_persona_with_fewer_than_15_attrs_fails():
    p = Persona(slug="thin", market_segment="expat")
    with pytest.raises(PersonaValidationError, match="15 attribute"):
        p.validate()


def test_persona_with_fewer_than_3_quotes_fails():
    kwargs = _complete_persona_kwargs()
    kwargs["verbatim_quotes"] = ["only one"]
    p = Persona(**kwargs)
    with pytest.raises(PersonaValidationError, match="verbatim quote"):
        p.validate()


def test_persona_empty_string_counts_as_unpopulated():
    kwargs = _complete_persona_kwargs()
    kwargs["age_range"] = ""
    p = Persona(**kwargs)
    # age_range empty → 15 populated (still passes ≥15)
    assert p.count_populated_attrs() == 15
    p.validate()  # exactly 15 is OK


def test_persona_empty_list_counts_as_unpopulated():
    kwargs = _complete_persona_kwargs()
    kwargs["language_secondary"] = []
    p = Persona(**kwargs)
    assert p.count_populated_attrs() == 15


def test_inference_agent_exposes_expat_and_id_source_maps():
    """Agent must declare source signal mappings for all 6 persona slugs."""
    expat = PersonaInferenceAgent.EXPAT_SOURCES
    id_src = PersonaInferenceAgent.ID_SOURCES
    assert set(expat.keys()) == {
        "expat_boomer_retiree",
        "expat_techie_pma",
        "expat_italian_aire",
    }
    assert set(id_src.keys()) == {
        "id_konsultan_kadin",
        "id_founder_pma",
        "id_umkm_digital",
    }
    # Each mapping has ≥2 sources
    for slug, sources in {**expat, **id_src}.items():
        assert len(sources) >= 2, f"{slug} needs more sources"
