"""
Test for finding #6 of the 2026-07-16 red-team (pre-existing, not introduced
by the take_label variety patch, but touched by it since that patch edited
the same JSON example's slide-2 headline).

SYSTEM_INSTRUCTIONS embeds a "Structure:" JSON example that is prompt text
shown to the model, never parsed by our own code at runtime -- but it was
NOT literally valid JSON: it contained a `// ...` elision comment and only
5 concrete slide objects, while the real _normalise_slides guard requires
6-11. If the model ever echoed the elision comment verbatim, or matched the
example's slide count, downstream parsing/normalization would break. This
test extracts the literal example, json.loads()s it, and runs it through
the real normalizer to prove it is a legitimate, parseable, in-range
example of what the model should produce.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_draft_generator import SYSTEM_INSTRUCTIONS, _normalise_slides  # noqa: E402


def _extract_structure_example(text: str) -> str:
    """Pull the literal JSON example between "Structure:\\n" and the
    "REPEAT (MUST OBEY)" marker that immediately follows it in
    SYSTEM_INSTRUCTIONS -- both are stable anchors verbatim in the prompt."""
    before, _, after = text.partition("Structure:\n")
    assert after, "SYSTEM_INSTRUCTIONS must contain a 'Structure:' JSON example"
    json_block, _, _rest = after.partition("\n\nREPEAT (MUST OBEY)")
    assert json_block, "SYSTEM_INSTRUCTIONS must contain the closing 'REPEAT (MUST OBEY)' marker"
    return json_block.strip()


def test_structure_example_contains_no_elision_comment():
    """The bug this finding fixes: `// ...` is not valid JSON. If the model
    ever echoed it back verbatim, json.loads() would break real output."""
    block = _extract_structure_example(SYSTEM_INSTRUCTIONS)
    assert "//" not in block, "JSON example must not contain elision comments"


def test_structure_example_is_valid_json():
    block = _extract_structure_example(SYSTEM_INSTRUCTIONS)
    parsed = json.loads(block)  # must not raise
    assert isinstance(parsed, dict)
    assert "register" in parsed
    assert "slides" in parsed


def test_structure_example_has_at_least_six_slides():
    """_normalise_slides hard-rejects <6 or >11 slides -- the worked example
    the model sees must itself be in-range, not just documentation-legal."""
    block = _extract_structure_example(SYSTEM_INSTRUCTIONS)
    parsed = json.loads(block)
    assert 6 <= len(parsed["slides"]) <= 11


def test_structure_example_passes_the_real_normalizer():
    """End-to-end: json.loads() the example, then run the REAL
    _normalise_slides used on live model output -- confirms the example
    is not just syntactically valid JSON but semantically acceptable to
    the actual downstream contract."""
    block = _extract_structure_example(SYSTEM_INSTRUCTIONS)
    parsed = json.loads(block)
    register, normalised = _normalise_slides(parsed)
    assert register  # non-empty, valid tone slug
    assert len(normalised) == len(parsed["slides"])
    assert normalised[0]["is_cover"] is True
    assert normalised[0]["is_hero_image"] is True


def test_structure_example_never_recommends_the_bottom_line():
    """2026-07-16 red-team finding #3: the worked example previously used
    "THE BOTTOM LINE: ..." as the slide-2 headline -- the exact phrase
    banned as a filler heading pattern elsewhere in the doctrine. Guard
    against reintroducing it here."""
    block = _extract_structure_example(SYSTEM_INSTRUCTIONS)
    assert "THE BOTTOM LINE" not in block.upper()
