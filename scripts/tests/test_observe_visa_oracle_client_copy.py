"""Guilt and innocence for the Visa Oracle client-copy observer's jargon guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = (
    Path(__file__).resolve().parents[1] / "ci" / "observe_visa_oracle_client_copy.py"
)
_SPEC = importlib.util.spec_from_file_location("observe_vo_copy", _PATH)
assert _SPEC and _SPEC.loader
obs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(obs)


def _hits(text: str) -> list[str]:
    visible = obs.PLACEHOLDER.sub(" ", text)
    for allowed in obs.ALLOWED_PHRASES:
        visible = visible.replace(allowed, " ")
    return [w.pattern for w in obs.BANNED_WORDS if w.search(visible)]


def test_a_leaked_engine_identifier_is_caught() -> None:
    assert _hits("The answer maps directly to work.indonesia_source_compensation.")
    assert _hits("Ini dipetakan ke investment.pt_pma_committed.")


def test_the_engine_word_is_caught_in_either_language() -> None:
    assert _hits("The engine receives your answer.")
    assert _hits("Mesin menerima jawaban Anda.")


def test_plain_copy_and_placeholders_are_innocent() -> None:
    assert not _hits(
        "Your answer sets {{plural:this detail|these details}}, which we use:"
    )
    assert not _hits("Used to decide: {{facts}}")
    assert not _hits("Only your yes or no is used here.")
    assert not _hits("Enter the amount, e.g. 5.000 per month.")


def test_a_dotted_dictionary_key_is_not_copy() -> None:
    assert obs.DOTTED_KEY.match("q.permit_expiry.hint")
    assert not obs.DOTTED_KEY.match("Only your yes or no.")
