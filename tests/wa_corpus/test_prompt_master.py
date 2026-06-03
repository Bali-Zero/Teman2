from scripts.wa_corpus.prompt_master import (
    PROMPT_MASTER,
    REQUIRED_SECTIONS,
    recap_is_valid,
)


def test_prompt_contains_all_top_level_sections():
    for sec in REQUIRED_SECTIONS:
        assert sec in PROMPT_MASTER


def test_prompt_has_two_levels_and_perspectives():
    # PART A multi-perspective + PART B specific points (Antonello's requirement)
    for perspective in ("Operational", "Relationship", "Commercial", "Risk"):
        assert perspective in PROMPT_MASTER
    for point in ("Company / entity", "Deadlines", "Amounts / payments",
                  "Next concrete action"):
        assert point in PROMPT_MASTER


def test_prompt_demands_verbatim_and_english_and_no_invent():
    low = PROMPT_MASTER.lower()
    assert "verbatim" in low
    assert "english" in low
    assert "not mentioned" in low
    assert "never infer or invent" in low


def test_valid_recap_has_all_sections():
    recap = (
        "**HEADLINE**: x\n\nGENERAL RECAP\n- Operational: y\n\n"
        "SPECIFIC POINTS\n- Company / entity: z"
    )
    assert recap_is_valid(recap) is True


def test_recap_missing_a_section_is_invalid():
    recap = "**HEADLINE**: x\n\nGENERAL RECAP\n- Operational: y"  # no SPECIFIC POINTS
    assert recap_is_valid(recap) is False
