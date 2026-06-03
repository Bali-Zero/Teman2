from scripts.wa_corpus.prompt_master import (
    PROMPT_MASTER,
    REQUIRED_SECTIONS,
    recap_is_valid,
)


def test_prompt_contains_all_six_sections():
    for sec in REQUIRED_SECTIONS:
        assert sec in PROMPT_MASTER


def test_prompt_demands_verbatim_and_english():
    assert "verbatim" in PROMPT_MASTER.lower()
    assert "english" in PROMPT_MASTER.lower()
    assert "not mentioned" in PROMPT_MASTER.lower()


def test_valid_recap_has_all_sections():
    recap = "\n".join(f"## {s}\nnot mentioned" for s in REQUIRED_SECTIONS)
    assert recap_is_valid(recap) is True


def test_recap_missing_a_section_is_invalid():
    recap = "\n".join(f"## {s}\nx" for s in list(REQUIRED_SECTIONS)[:-1])
    assert recap_is_valid(recap) is False
