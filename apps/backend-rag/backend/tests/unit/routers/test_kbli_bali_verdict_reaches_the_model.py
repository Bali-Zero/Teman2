"""The Bali provincial verdict must reach the model, and must never be invented.

WHAT THIS IS FOR. On 2026-08-03 `chat_kbli` was asked, in production, whether a
foreign-owned company could open a massage parlour (KBLI 86995) in Bali. It
answered *"Yes, you absolutely can"* — with capital figures and next steps.
The live Qdrant point for 86995 carried `bali_blocked: true` at that moment. The
store knew; nothing read the field into the LLM context, because
`KBLISearchResult` had no place to put it.

So the corpus is built around the two ways this can go wrong, and they pull in
opposite directions:

  * GUILT — a blocked activity must produce a note the model cannot miss, naming
    the block and its stated cause.
  * INNOCENCE — an ABSENT verdict must produce SILENCE. "We were not told" is not
    "it is open", and a payload written before the Bali layer existed must never
    be read as a green light. This is the same inference the KBLI lane spent a
    week withdrawing from 32 codes; re-introducing it here would undo that.

The third failure mode is coverage: seven call sites in the router build a
`KBLISearchResult` and only two of them see a Qdrant payload, so the fix lives at
the single choke point every answer passes through, and that is asserted here.
"""

from __future__ import annotations

import pytest

from backend.app.routers.kbli_notebook import KBLISearchResult
from backend.app.routers.kbli_notebook_chat import (
    _bali_verdict_context_note,
    _fill_bali_verdicts,
)


def _result(code: str = "86995", **kwargs) -> KBLISearchResult:
    base = {
        "code": code,
        "title": "Aktivitas Rumah Pijat",
        "description": "...",
        "score": 0.9,
    }
    base.update(kwargs)
    return KBLISearchResult(**base)


# --------------------------------------------------------------- guilt


def test_a_blocked_code_produces_a_note_the_model_cannot_read_as_permission():
    """The exact production failure, frozen: 86995 blocked, and the note has to
    say so in words that cannot be summarised into "yes you can"."""
    note = _bali_verdict_context_note(
        _result(
            bali_blocked=True,
            bali_status="CHIUSO_MORATORIA_BALI",
            bali_reason="blocked in Bali by the PMA moratorium: risk tier ['Menengah Rendah']",
        ),
    )
    assert "BLOCKED FOR A FOREIGN-OWNED COMPANY" in note
    assert "CHIUSO_MORATORIA_BALI" in note
    assert "Menengah Rendah" in note
    assert "Do not answer that it can be registered in Bali." in note


def test_the_note_says_the_provincial_block_is_independent_of_national_openness():
    """86995 is nationally TERBUKA/100% AND blocked in Bali. Without this
    sentence the model reconciles the two by dropping the inconvenient one —
    which is what it did."""
    note = _bali_verdict_context_note(
        _result(bali_blocked=True, bali_status="CHIUSO_MORATORIA_BALI", bali_reason="x"),
    )
    assert "independent of the national PMA status" in note


@pytest.mark.asyncio
async def test_a_result_built_without_a_payload_is_backfilled_at_the_choke_point():
    """THE class fix. Five of the seven constructors build from Postgres, the KG
    or a hardcoded fallback — none of which carry the Bali layer — so a code
    typed directly would otherwise answer blind."""
    result = _result()
    assert result.bali_blocked is None  # as the Postgres path leaves it

    async def fake_payload(code: str) -> dict:
        assert code == "86995"
        return {
            "bali_blocked": True,
            "bali_status": "CHIUSO_MORATORIA_BALI",
            "bali_reason": "the moratorium",
        }

    import backend.app.routers.kbli_notebook_chat as mod

    original = mod._get_kbli_payload_from_qdrant
    mod._get_kbli_payload_from_qdrant = fake_payload
    try:
        await _fill_bali_verdicts([result])
    finally:
        mod._get_kbli_payload_from_qdrant = original

    assert result.bali_blocked is True
    assert result.bali_status == "CHIUSO_MORATORIA_BALI"
    assert "BLOCKED" in _bali_verdict_context_note(result)


# ----------------------------------------------------------- innocence


def test_an_absent_verdict_produces_silence_never_a_claim_of_openness():
    """`None` means the payload carried nothing. The note must be empty — not a
    reassurance. Absence has been misread as permission in this dataset before."""
    assert _bali_verdict_context_note(_result()) == ""


def test_a_code_that_is_not_blocked_is_told_plainly_and_is_not_called_blocked():
    note = _bali_verdict_context_note(_result(bali_blocked=False, bali_status="OK"))
    assert "NOT blocked" in note
    assert "BLOCKED FOR A FOREIGN-OWNED COMPANY" not in note


@pytest.mark.asyncio
async def test_a_qdrant_failure_degrades_to_silence_and_never_to_a_guess():
    """Legge 6: offline is a natural state. An unreachable store must leave the
    verdict unknown, not resolve it to 'open'."""
    result = _result()

    async def boom(code: str):
        raise RuntimeError("qdrant unreachable")

    import backend.app.routers.kbli_notebook_chat as mod

    original = mod._get_kbli_payload_from_qdrant
    mod._get_kbli_payload_from_qdrant = boom
    try:
        await _fill_bali_verdicts([result])
    finally:
        mod._get_kbli_payload_from_qdrant = original

    assert result.bali_blocked is None
    assert _bali_verdict_context_note(result) == ""


@pytest.mark.asyncio
async def test_a_payload_without_the_bali_key_leaves_the_verdict_unknown():
    """Points indexed before the Bali layer existed. Reading a missing key as
    False would publish every one of them as registrable in Bali."""
    result = _result()

    async def no_bali(code: str) -> dict:
        return {"pma_status": "TERBUKA", "pma_max_asing": 100}

    import backend.app.routers.kbli_notebook_chat as mod

    original = mod._get_kbli_payload_from_qdrant
    mod._get_kbli_payload_from_qdrant = no_bali
    try:
        await _fill_bali_verdicts([result])
    finally:
        mod._get_kbli_payload_from_qdrant = original

    assert result.bali_blocked is None


@pytest.mark.asyncio
async def test_a_result_that_already_carries_a_verdict_is_not_refetched():
    """The two Qdrant-built constructors already fill these fields. Re-fetching
    would be a second read that could disagree with the first — and would let a
    later store overwrite the verdict the search actually returned."""
    result = _result(bali_blocked=True, bali_status="CHIUSO_MORATORIA_BALI", bali_reason="keep me")
    calls: list[str] = []

    async def spy(code: str) -> dict:
        calls.append(code)
        return {"bali_blocked": False, "bali_status": "OVERWRITTEN", "bali_reason": "no"}

    import backend.app.routers.kbli_notebook_chat as mod

    original = mod._get_kbli_payload_from_qdrant
    mod._get_kbli_payload_from_qdrant = spy
    try:
        await _fill_bali_verdicts([result])
    finally:
        mod._get_kbli_payload_from_qdrant = original

    assert calls == []
    assert result.bali_status == "CHIUSO_MORATORIA_BALI"
    assert result.bali_reason == "keep me"


# ----------------------------------------------------------- tripwires


def test_the_explanation_cache_prefix_moved_with_this_change():
    """A 12-hour cache keyed on this prefix would keep serving answers generated
    blind to the Bali block for half a day after the deploy. A cure the cache
    hides is not live."""
    import inspect
    from pathlib import Path

    import backend.app.routers.kbli_notebook_chat as mod

    # Asked of the imported module, not assembled from `__file__` — path
    # arithmetic across a worktree is its own way to fail while looking fine.
    source = Path(inspect.getsourcefile(mod))
    text = source.read_text(encoding="utf-8")
    assert 'prefix="kbli_explain_v28"' in text
    assert 'prefix="kbli_explain_v27"' not in text


def test_the_fill_runs_inside_the_function_every_answer_passes_through():
    """Coverage, asserted rather than trusted: the backfill must sit in the
    shared explanation builder, not in one of the seven constructors."""
    import inspect

    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation

    fn = getattr(_generate_kbli_explanation, "__wrapped__", _generate_kbli_explanation)
    assert "_fill_bali_verdicts(results)" in inspect.getsource(fn)
