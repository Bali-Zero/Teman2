"""No Tier-1 notice may order the model to open in a fixed language.

The system prompt carries ``<language_protocol priority="ABSOLUTE">``: the
reply MUST match the user's language. Until 2026-08-11 two of the three
Tier-1 notices — the ones behind 4 of the 6 call sites in ``reasoning.py`` —
told the model, in the user turn, to "MUST START your response with:"
followed by an Italian sentence, with no translation clause. Two ABSOLUTE
instructions in direct contradiction, and the more proximate one dictated
Italian.

Only ``TRANSPARENCY_INSTRUCTION_FINAL`` had the clause. That is the shape of
the defect: the rule existed, in one copy of three.

These tests enumerate the notices from the module rather than naming them,
so a FOURTH notice added later inherits the guard instead of quietly
reopening the hole.
"""

import pytest

from backend.services.rag.agentic import _reasoning_tier1 as tier1


def _all_notices() -> dict[str, str]:
    """Every TRANSPARENCY_INSTRUCTION_* constant the module exposes."""
    return {
        name: value
        for name, value in vars(tier1).items()
        if name.startswith("TRANSPARENCY_INSTRUCTION_") and isinstance(value, str)
    }


def test_the_enumeration_actually_finds_the_notices():
    """Guard the guard: an empty sweep must not read as a clean sweep.

    Rename the constants and every test below would pass over nothing.
    """
    notices = _all_notices()
    assert len(notices) >= 3, f"expected the three known notices, found {sorted(notices)}"


class TestGuilt:
    @pytest.mark.parametrize("name", sorted(_all_notices()))
    def test_every_notice_orders_the_opening_translated(self, name):
        """The opening sentence must be marked as a reference, not as output."""
        notice = _all_notices()[name]
        assert "TRANSLATED INTO THE USER'S LANGUAGE" in notice, (
            f"{name} dictates a fixed-language opening"
        )

    @pytest.mark.parametrize("name", sorted(_all_notices()))
    def test_every_notice_gags_meta_commentary(self, name):
        """Same rule its twin `_REPHRASE_OUTPUT_RULES` already carries."""
        notice = _all_notices()[name]
        assert "Return ONLY the answer itself" in notice, f"{name} lets the model narrate"

    def test_the_rule_has_exactly_one_definition(self):
        """Three copies of a rule is how two of them ended up without it.

        Every notice must be built from the shared constants, not from its own
        transcription of them.
        """
        for name, notice in _all_notices().items():
            assert tier1._OPENING_RULE in notice, f"{name} carries its own copy of the rule"
            assert tier1._OUTPUT_HYGIENE in notice, f"{name} carries its own copy of the gag"

    def test_the_prompt_the_model_actually_receives_carries_both(self):
        """The constants are not the artefact — the assembled prompt is."""
        prompt = tier1.build_tier1_prompt("Berapa lama proses KITAS?", ["some context"])

        assert "TRANSLATED INTO THE USER'S LANGUAGE" in prompt
        assert "Return ONLY the answer itself" in prompt


class TestInnocence:
    def test_the_italian_reference_wording_survives(self):
        """The cure is about the ORDER, not the sentence.

        The agreed disclosure wording stays: dropping it would silently remove
        the "this is general knowledge, not verified" contract.
        """
        for name, notice in _all_notices().items():
            assert "Non ho trovato documenti interni verificati" in notice, (
                f"{name} lost the disclosure sentence"
            )

    def test_each_notice_keeps_its_own_distinct_content(self):
        """Sharing the rule must not collapse three notices into one.

        FINAL keeps its point 5; NO_CONTEXT keeps its own header.
        """
        assert "suggest contacting the team" in tier1.TRANSPARENCY_INSTRUCTION_FINAL
        assert "suggest contacting the team" not in tier1.TRANSPARENCY_INSTRUCTION_DEFAULT
        assert "NO INTERNAL DOCUMENTS FOUND" in tier1.TRANSPARENCY_INSTRUCTION_NO_CONTEXT
        assert "LOW CONFIDENCE RETRIEVAL" in tier1.TRANSPARENCY_INSTRUCTION_DEFAULT

    def test_the_prompt_structure_is_unchanged(self):
        """`build_tier1_prompt` still assembles notice + query + context + tail."""
        prompt = tier1.build_tier1_prompt("Berapa lama proses KITAS?", ["ctx-A", "ctx-B"])

        assert "User Query: Berapa lama proses KITAS?" in prompt
        assert "Retrieved Context (limited):" in prompt
        assert "ctx-A" in prompt
        assert "ctx-B" in prompt
        assert prompt.rstrip().endswith("not verified internal information.")

    def test_the_no_context_branch_still_omits_the_context_section(self):
        prompt = tier1.build_tier1_prompt(
            "Berapa lama proses KITAS?",
            None,
            transparency_instruction=tier1.TRANSPARENCY_INSTRUCTION_NO_CONTEXT,
            include_context_section=False,
        )

        assert "Retrieved Context (limited):" not in prompt
        assert "No verified documents found in internal knowledge base." not in prompt
