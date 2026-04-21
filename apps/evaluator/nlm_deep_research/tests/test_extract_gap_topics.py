"""Regression test for _extract_gap_topics JSON-envelope corruption.

Context (wave 1 triage, PR #174): the NLM CLI periodically wraps its answer
in a JSON envelope like

    {"answer": "...", "conversation_id": "...", "sources_used": [],
     "citations": {}, "references": []}

The previous implementation split the whole envelope by newlines and kept
every line longer than 15 chars that didn't start with a bullet — producing
fake gap topics such as ``"conversation_id": "3e8fe6db-..."`` that ended
up in ``coverage_matrix.json``. 35 such corrupted entries were observed in
the 2026-04-03 run.

This test locks the behaviour: bare JSON envelope → extract ``answer``
field → split that. No envelope keys should leak into the return value.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from apps.evaluator.nlm_deep_research.gap_scanner import _extract_gap_topics


def test_json_envelope_answer_field_used() -> None:
    """The answer inside the envelope is what should be split into gaps."""
    response = (
        '{\n'
        '  "answer": "Quali sono i requisiti SBU per PT PMA?\\n'
        'Quando firmerà Prabowo la revisione PP 55/2022?\\n'
        'Come cambia il regime UMKM nel 2026?",\n'
        '  "conversation_id": "abc-123",\n'
        '  "sources_used": [],\n'
        '  "citations": {},\n'
        '  "references": []\n'
        '}'
    )
    gaps = _extract_gap_topics(response)
    # All three questions from the answer must be present.
    assert len(gaps) == 3
    assert any("SBU" in g for g in gaps)
    assert any("Prabowo" in g for g in gaps)
    assert any("UMKM" in g for g in gaps)
    # None of the envelope metadata must leak.
    combined = " | ".join(gaps)
    assert "conversation_id" not in combined
    assert "sources_used" not in combined
    assert "citations" not in combined
    assert "references" not in combined


def test_plain_text_response_unchanged() -> None:
    """Non-JSON responses still work as before."""
    response = (
        "1. Come ottenere il KITAS?\n"
        "2. Quando scade il visto B211A?\n"
        "Requisiti per il PT PMA in Bali\n"
    )
    gaps = _extract_gap_topics(response)
    assert len(gaps) == 3
    assert any("KITAS" in g for g in gaps)
    assert any("B211A" in g for g in gaps)
    assert any("PT PMA" in g for g in gaps)


def test_malformed_json_fallback_filters_key_lines() -> None:
    """If JSON parsing fails, line-level filter should still drop JSON-key
    leakage so we never produce corrupted matrix entries like the 35 observed
    on 2026-04-03."""
    response = (
        '{\n'
        '  "answer": "Qual è la procedura aggiornata per il KITAS lansia?"\n'
        '  "conversation_id": "abc-123",\n'  # malformed: missing comma above
        '  "sources_used": [],\n'
        '  "citations": {},\n'
    )
    gaps = _extract_gap_topics(response)
    # Defensive filter still drops the envelope keys.
    for g in gaps:
        assert not (g.startswith('"') and '":' in g[:60]), (
            f"envelope key leaked into gaps: {g!r}"
        )


def test_empty_response_returns_empty_list() -> None:
    assert _extract_gap_topics("") == []
    assert _extract_gap_topics("   \n  ") == []


def test_max_eight_gaps_enforced() -> None:
    """The 8-gap cap survives the JSON-envelope path too."""
    answer_lines = [f"Domanda numero {i} sulla procedura?" for i in range(1, 15)]
    response = (
        '{"answer": "' + "\\n".join(answer_lines) + '", '
        '"conversation_id": "x", "sources_used": []}'
    )
    gaps = _extract_gap_topics(response)
    assert len(gaps) == 8
