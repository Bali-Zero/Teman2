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
    # This line read `assert "CHIUSO_MORATORIA_BALI" in note` until 2026-08-05,
    # which pinned a leak as if it were a feature: the note ended with
    # `Verdict code: <symbol>` and production read that symbol out to a client.
    # The stated cause carries the meaning; the symbol carried our vocabulary.
    assert "CHIUSO_MORATORIA_BALI" not in note
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
    assert 'prefix="kbli_explain_v29"' in text
    assert 'prefix="kbli_explain_v28"' not in text


def test_the_fill_runs_inside_the_function_every_answer_passes_through():
    """Coverage, asserted rather than trusted: the backfill must sit in the
    shared explanation builder, not in one of the seven constructors."""
    import inspect

    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation

    fn = getattr(_generate_kbli_explanation, "__wrapped__", _generate_kbli_explanation)
    assert "_fill_bali_verdicts(results)" in inspect.getsource(fn)


# ================================================================== national scope
#
# ADDED 2026-08-05. The note above reached the model, and then told 77 codes'
# readers the wrong thing about WHERE the closure applies. Asked about 64110
# (Bank Sentral) in production, the bot was right on the substance and framed a
# Bank Indonesia State monopoly as a Bali provincial rule — whose natural next
# step for a client is "then I will register it in Jakarta". It also printed the
# internal verdict symbol.
#
# The corpus below pulls in three directions, because there are three ways to be
# wrong here: calling a national closure provincial (the bug), calling a
# provincial one national (the over-correction, which would tell a client Bali's
# moratorium reaches Java), and reading an ABSENT field as a closure.

import json  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

from backend.app.routers.kbli_notebook_chat import (  # noqa: E402
    _NATIONAL_CLOSURE_CODES,
    _NATIONAL_CLOSURE_STATUSES,
    _is_zero_ceiling,
    _national_closure_basis,
)

_PROVINCIAL_SENTENCE = "This is a PROVINCIAL restriction"
_NATIONAL_SENTENCE = "NATIONALLY, not only in Bali"

# backend/tests/unit/routers/ -> repo root (the same arithmetic
# test_kbli_hardcoded_fallback_matches_catalogue.py already uses).
_CANONICAL = (
    Path(__file__).resolve().parents[6] / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
)

# An underscore-joined token is pipeline vocabulary by construction. No allow
# list: the point is to cover the symbol nobody has invented yet.
_SYMBOL_RE = re.compile(r"\b[A-Za-z]+(?:_[A-Za-z]+)+\b")


@pytest.fixture(scope="module")
def catalogue() -> list[dict]:
    """The real 1,559-code canonical. A missing file FAILS rather than skips —
    a gate that quietly stops running is the failure mode this repo pays for
    most often (superscar #2)."""
    assert _CANONICAL.is_file(), f"canonical dataset not found at {_CANONICAL}"
    records = json.loads(_CANONICAL.read_text(encoding="utf-8"))["data"]
    assert len(records) > 1000, f"catalogue looks truncated: {len(records)} records"
    return records


def _result_for(record: dict) -> KBLISearchResult:
    """A search result carrying exactly what the Qdrant payload carries."""
    l4 = record.get("l4_bali") or {}
    return KBLISearchResult(
        code=record["kode_kbli_2025"],
        title=record.get("judul") or "",
        description="",
        score=1.0,
        pma_status=record.get("pma_status") or "UNKNOWN",
        pma_max_asing=record.get("pma_max_asing"),
        bali_status=l4.get("status"),
        bali_blocked=l4.get("blocked"),
        bali_reason=l4.get("reason") or "",
    )


# --------------------------------------------------------------- guilt: national


def test_a_state_monopoly_is_not_described_as_a_bali_restriction():
    """64110, the code that produced the wrong answer in production."""
    note = _bali_verdict_context_note(
        _result(
            "64110",
            title="Bank Sentral",
            pma_status="TERBUKA",
            pma_max_asing=100,
            bali_blocked=True,
            bali_status="CHIUSO_REGOLATORE_SETTORIALE",
            bali_reason="Bank Sentral — exclusive State monopoly operated by Bank Indonesia.",
        ),
    )
    assert _NATIONAL_SENTENCE in note
    assert _PROVINCIAL_SENTENCE not in note
    assert "another province does NOT change the answer" in note
    assert "Bank Indonesia" in note  # the stated cause still passes through
    assert "CHIUSO_REGOLATORE_SETTORIALE" not in note


def test_a_code_reserved_by_name_is_national_even_when_pma_status_says_open():
    """69104 (notary/PPAT) reads TERBUKA/100 on the record — the ownership fields
    never learned about the reservation. Without the code list the note would
    call a personal State office a Bali problem."""
    note = _bali_verdict_context_note(
        _result(
            "69104",
            pma_status="TERBUKA",
            pma_max_asing=100,
            bali_blocked=True,
            bali_status="TERTUTUP",
            bali_reason="Notary/PPAT is a personal State office, WNI only (UU 30/2004).",
        ),
    )
    assert _NATIONAL_SENTENCE in note
    assert _PROVINCIAL_SENTENCE not in note
    assert "notary/PPAT" in note


def test_a_tertutup_pma_status_makes_the_closure_national():
    note = _bali_verdict_context_note(
        _result(
            "01287",
            pma_status="TERTUTUP",
            pma_max_asing=0,
            bali_blocked=True,
            bali_status="TERTUTUP",
            bali_reason="Closed to foreign ownership at the national level.",
        ),
    )
    assert _NATIONAL_SENTENCE in note
    assert _PROVINCIAL_SENTENCE not in note


def test_a_zero_ceiling_makes_the_closure_national_even_under_a_terbatas_label():
    """The word says "restricted", the number says 0%. A reader shown only the
    word hears "find a local partner"; there is nothing to partner into."""
    note = _bali_verdict_context_note(
        _result(
            "16221",
            pma_status="TERBATAS",
            pma_max_asing=0,
            bali_blocked=True,
            bali_status="BLOCCATO_CLASSE_RISCHIO",
            bali_reason="blocked in Bali by the PMA moratorium",
        ),
    )
    assert _NATIONAL_SENTENCE in note
    assert "ceiling is 0%" in note


def test_not_blocked_in_bali_is_not_permission_when_the_national_door_is_shut():
    """79122 — Umrah/Hajj travel. TERBATAS with a ceiling of 0, and the Bali
    moratorium does not reach it, so the old note said "NOT blocked" and stopped.
    That sentence has exactly one reading, and it is the wrong one."""
    note = _bali_verdict_context_note(
        _result(
            "79122",
            title="Biro Perjalanan Ibadah Umrah dan Haji Khusus",
            pma_status="TERBATAS",
            pma_max_asing=0,
            bali_blocked=False,
            bali_status="OK_or_HIGHER_RISK",
        ),
    )
    assert "NOT permission" in note
    assert "NATIONAL level" in note
    assert "MUST NOT present it as registrable" in note


# ------------------------------------------------------------ innocence: provincial


def test_a_real_moratorium_block_is_still_called_provincial():
    """86995, the case the previous lane shipped. Over-correcting here would tell
    a client that Bali's moratorium reaches Java."""
    note = _bali_verdict_context_note(
        _result(
            bali_blocked=True,
            bali_status="CHIUSO_MORATORIA_BALI",
            bali_reason="blocked in Bali by the PMA moratorium: risk tier ['Menengah Rendah']",
            pma_status="TERBUKA",
            pma_max_asing=100,
        ),
    )
    assert _PROVINCIAL_SENTENCE in note
    assert _NATIONAL_SENTENCE not in note
    assert "can be 100% open nationally" in note


def test_an_open_code_that_is_not_blocked_gets_no_national_warning():
    note = _bali_verdict_context_note(
        _result(bali_blocked=False, bali_status="OK_or_HIGHER_RISK", pma_status="TERBUKA", pma_max_asing=100),
    )
    assert "NOT blocked" in note
    assert "NOT permission" not in note
    assert "NATIONAL level" not in note


# -------------------------------------------- innocence: absence is not a closure


def test_an_absent_ceiling_is_never_read_as_zero_percent():
    """The indexer writes an absent cap as `""`. Reading absence as 0% would
    invent a national closure on every point written before the field existed —
    the same inference this lane spent a week withdrawing from `bali_blocked`."""
    for absent in (None, "", "  "):
        assert not _is_zero_ceiling(absent), f"{absent!r} must not read as a 0% ceiling"
        note = _bali_verdict_context_note(
            _result(
                bali_blocked=True,
                bali_status="BLOCCATO_CLASSE_RISCHIO",
                bali_reason="risk class",
                pma_status="TERBUKA",
                pma_max_asing=absent,
            ),
        )
        assert _PROVINCIAL_SENTENCE in note
        assert _NATIONAL_SENTENCE not in note


def test_the_ceiling_test_reads_a_real_zero_in_either_shape_and_never_a_boolean():
    assert _is_zero_ceiling(0) is True
    assert _is_zero_ceiling("0") is True  # a digit string still means 0%
    assert _is_zero_ceiling(False) is False  # bool is an int in Python; not a cap
    assert _is_zero_ceiling(100) is False
    assert _is_zero_ceiling("100") is False


def test_an_absent_verdict_still_produces_silence_after_the_national_branch():
    """The silence-on-absence contract is the innocence property the previous
    lane shipped; the national branch must not have opened a hole in it."""
    assert _bali_verdict_context_note(_result(pma_status="TERTUTUP", pma_max_asing=0)) == ""


# ------------------------------------------------------ the pipeline's vocabulary


def test_a_symbol_written_inside_a_reason_is_spoken_not_quoted():
    """The `Verdict code:` suffix was the leak that bled. This is the OTHER route
    in: `bali_reason` is passed to the model verbatim, so a symbol inside the
    sentence would leak just the same. Measured 2026-08-05, 9 reasons quote a
    symbol and none is on a blocked code — so this guards a population of zero
    today and exists because reasons are rewritten most weeks."""
    note = _bali_verdict_context_note(
        _result(
            bali_blocked=True,
            bali_status="BLOCCATO_CLASSE_RISCHIO",
            bali_reason="tier carried over from OK_or_HIGHER_RISK; see pma_cap_verified",
            pma_status="TERBUKA",
            pma_max_asing=100,
        ),
    )
    assert "OK_or_HIGHER_RISK" not in note
    assert "pma_cap_verified" not in note
    assert "not reached by the moratorium" in note
    assert "foreign-ownership cap verified" in note


def test_an_unmapped_symbol_degrades_to_words_rather_than_reaching_a_client():
    """Fail-CLOSED: the next symbol nobody has mapped must not leak while waiting
    for someone to notice it."""
    note = _bali_verdict_context_note(
        _result(
            bali_blocked=True,
            bali_status="BLOCCATO_CLASSE_RISCHIO",
            bali_reason="verdict CHIUSO_QUALCOSA_DI_NUOVO applies",
            pma_status="TERBUKA",
            pma_max_asing=100,
        ),
    )
    assert "CHIUSO_QUALCOSA_DI_NUOVO" not in note
    assert "CHIUSO QUALCOSA DI NUOVO" in note


# ---------------------------------------------------------- the whole catalogue


def test_no_note_in_the_whole_catalogue_hands_the_model_an_internal_symbol(catalogue):
    """Measured on the REAL canonical, not on fixtures, and stated as a PROPERTY
    rather than a frozen count — the dataset is edited by cure lanes most weeks,
    and a gate that breaks on every data PR is a gate that gets deleted.

    Deliberately NOT an allow list of the symbols we know: an underscore-joined
    token is pipeline vocabulary by construction, so a symbol invented tomorrow
    is covered the day it appears. `TERTUTUP` and `TERBATAS` carry no underscore
    and are official regulatory words — they are not, and must not become, leaks.
    """
    offenders = []
    for record in catalogue:
        note = _bali_verdict_context_note(_result_for(record))
        offenders.extend((record["kode_kbli_2025"], sym) for sym in _SYMBOL_RE.findall(note))
    assert offenders == [], f"internal symbols reaching the model: {offenders[:10]}"


def test_every_national_closure_in_the_catalogue_refuses_the_provincial_wording(catalogue):
    national = provincial = 0
    for record in catalogue:
        result = _result_for(record)
        note = _bali_verdict_context_note(result)
        if not note:
            continue
        if _national_closure_basis(result):
            assert _PROVINCIAL_SENTENCE not in note, record["kode_kbli_2025"]
            national += 1
        elif _PROVINCIAL_SENTENCE in note:
            provincial += 1
    # Both populations must be non-empty. A dataset shift that empties either one
    # would leave the assertions above trivially true — this makes that loud
    # instead of silent, without freezing a count the cure lanes move weekly.
    # Measured 2026-08-05: 78 national (77 blocked + 79122), 441 provincial.
    assert national > 0, "no national closure found — the gate would be vacuous"
    assert provincial > 0, "no provincial block found — the gate would be vacuous"


def test_a_non_string_reason_is_survived_rather_than_500ing_the_answer():
    """Two defects, one assertion, and the split is stated because measuring it
    changed the story.

    `bali_reason` is ASSIGNED onto the model from a Qdrant payload and Pydantic
    does not validate on assignment, so a point storing a number there reaches
    the formatter. `(42 or "").strip()` raises — and that ordering has been on
    main since the field was added, one malformed payload away from a 500 on a
    real question. NOT a regression: a latent defect this change had to walk past.

    What WAS mine: the first draft handed the value straight to `re.sub`, which
    also rejects the MagicMock the sibling suite uses as a double. The control
    said it plainly — 42 passed on origin/main, 8 failed with my file."""
    from backend.app.routers.kbli_notebook_chat import _speak_internal_symbols

    assert _speak_internal_symbols(123) == "123"
    assert _speak_internal_symbols(None) == "None"

    result = _result(bali_blocked=True, bali_status="BLOCCATO_CLASSE_RISCHIO")
    result.bali_reason = 42  # what a malformed payload would put there
    note = _bali_verdict_context_note(result)  # must not raise
    assert "BLOCKED FOR A FOREIGN-OWNED COMPANY" in note


# ------------------------------------------------- one verdict, two surfaces

_PAGE_RULE = (
    Path(__file__).resolve().parents[6]
    / "apps"
    / "mouth"
    / "src"
    / "lib"
    / "kbli-bali-block.ts"
)


def _page_rule_source() -> str:
    """A missing file is a FAILURE, never a skip. "I could not check" read as
    "clean" is how this repo loses gates (W106b: cannot-verify is its own state,
    and it is not innocence)."""
    assert _PAGE_RULE.is_file(), f"the page's rule is not where this test expects it: {_PAGE_RULE}"
    return _PAGE_RULE.read_text(encoding="utf-8")


def test_the_backend_and_the_page_name_the_same_national_closure_statuses():
    """`/kbli/69104` and WhatsApp answer the same question from the same record.
    They cannot share a module across TypeScript and Python, so the identity is
    asserted instead — otherwise each surface grows its own list and a client
    gets two answers, which is the defect this whole lane exists to remove."""
    block = re.search(
        r"NATIONAL_CLOSURE_STATUSES\s*=\s*new Set<string>\(\[(.*?)\]\)",
        _page_rule_source(),
        re.S,
    )
    assert block, "could not find NATIONAL_CLOSURE_STATUSES in the page's rule"
    page = set(re.findall(r'"([A-Z_]+)"', block.group(1)))
    assert page, "parsed the page's status set as EMPTY — the parser, not the rule, is broken"
    assert page == set(_NATIONAL_CLOSURE_STATUSES), (
        f"page={sorted(page)} backend={sorted(_NATIONAL_CLOSURE_STATUSES)}"
    )


def test_the_backend_and_the_page_name_the_same_national_closure_codes():
    block = re.search(
        r"NATIONAL_CLOSURE_CODES\s*=\s*new Map<string, string>\(\[(.*?)\n\]\);",
        _page_rule_source(),
        re.S,
    )
    assert block, "could not find NATIONAL_CLOSURE_CODES in the page's rule"
    page = set(re.findall(r'\[\s*\n?\s*"(\d{4,5})"', block.group(1)))
    assert page, "parsed the page's code list as EMPTY — the parser, not the rule, is broken"
    assert page == set(_NATIONAL_CLOSURE_CODES), (
        f"page={sorted(page)} backend={sorted(_NATIONAL_CLOSURE_CODES)}"
    )
