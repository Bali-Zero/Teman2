"""Guilt and innocence for the PT PMA paid-up figure in the KBLI gold file.

The P0 claim `CAPITAL-PAIDUP-10B` lives in
`apps/mouth/src/content/_regulatory-claim-ledger.json` and has exactly one
executor, `content-freshness-sentinel.test.ts`, whose header declares "Scope:
English canonical .mdx only". `kbli-gold-all.json` is not an .mdx, so 37 of the
428 gold codes carried the revoked 10-billion paid-up figure while the ledger
read green. This file is the reach that was missing.

Three distinct live rules share the string "10 billion" — paid-up (2.5bn since
Permen BKPM 5/2025), total investment (>10bn, stands), and the E28A
Investor-KITAS shareholding threshold (10bn, an immigration rule that stands).
So the innocence tests here matter as much as the guilt ones: a guard that
convicts every "10 billion" would break two rules to fix one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_FILIERA = Path(__file__).resolve().parents[1]
if str(_FILIERA) not in sys.path:
    sys.path.insert(0, str(_FILIERA))

import cure_gold_paidup_capital as C  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def gold():
    raw = json.loads(
        (REPO_ROOT / "apps/mouth/data/kbli-gold-all.json").read_text(encoding="utf-8")
    )
    return raw.get("data", raw)


# Codes where the ten-billion figure sits beside "paid-up" and is NOT the PT PMA
# paid-up minimum. May only shrink; each needs a reason.
NOT_THE_PAIDUP_MINIMUM = {
    "65121": "OJK paid-up (100bn) + PT PMA STATED capital (10B) — already separated",
    "66151": "OJK paid-up (200mn) + PT PMA STATED capital (10B) — already separated",
    "85102": "attached to Satuan Pendidikan Kerjasama registration, a sector regime",
}


# ── the live ledger ─────────────────────────────────────────────────────────


def test_no_gold_code_states_the_paidup_minimum_as_ten_billion(gold):
    cure, _refused = C.scan(gold)
    assert cure == {}, (
        "gold tells a client to deposit IDR 10 billion; the minimum is 2.5 "
        f"(Permen BKPM 5/2025 art. 26(10)). Codes: {sorted(cure)}. Run "
        "scripts/kbli_filiera/cure_gold_paidup_capital.py --apply."
    )


def test_the_refusals_are_exactly_the_named_ones(gold):
    _cure, refused = C.scan(gold)
    assert set(refused) == set(NOT_THE_PAIDUP_MINIMUM)


def test_refusal_list_only_shrinks():
    assert len(NOT_THE_PAIDUP_MINIMUM) <= 3
    assert all(v.strip() for v in NOT_THE_PAIDUP_MINIMUM.values())


def test_the_cure_kept_the_paragraphs_it_landed_in(gold):
    """A cure is not a licence to rewrite the sentence it corrected.

    `32112` opens with where silver work is done in Bali; `53200` carries the
    49% foreign-ownership cap in the same sentence, applied an hour earlier by
    a different cure. Both must survive the figure swap.
    """
    assert "popular around Celuk" in gold["32112"]["baliContext"]
    assert "capped at 49%" in gold["53200"]["baliContext"]
    assert "IDR 2.5 billion" in gold["53200"]["baliContext"]


def test_the_other_threshold_is_stated_wherever_the_figure_was_corrected(gold):
    """Dropping the 10-billion figure entirely would make a reader under-plan
    the investment requirement, which is a real rule and still stands."""
    for code in ("32112", "53200", "91426", "10798"):
        txt = gold[code]["baliContext"]
        assert "IDR 2.5 billion" in txt
        assert "exceed IDR 10 billion per 5-digit KBLI per location" in txt


# ── guilt ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "sentence",
    [
        "A standard PT PMA requires a minimum paid-up capital of IDR 10 billion.",
        "You need IDR 10 billion paid-up capital.",
        "As a PT PMA, the minimum paid-up capital is IDR 10 billion.",
        "The PT PMA requires IDR 10 billion paid-up capital (modal disetor).",
        "Be prepared to invest IDR 10 billion in paid-up capital as a PT PMA.",
        "Modal disetor minimal IDR 10 miliar.",
    ],
)
def test_guilt_every_phrasing_is_caught(sentence):
    cure, _ = C.scan({"90001": {"baliContext": f"Some local colour. {sentence}"}})
    assert "90001" in cure, f"missed: {sentence}"


def test_guilt_the_ledger_pattern_would_have_missed_five_of_these():
    """The reason this file exists rather than a ledger entry: the ledger
    matches two literal phrases, and gold uses nine."""
    ledger_patterns = ("Paid-up Capital: IDR 10 billion", "Minimum paid-up capital IDR 10 billion")
    ours = "A standard PT PMA requires a minimum paid-up capital of IDR 10 billion."
    assert not any(p in ours for p in ledger_patterns)
    assert "90001" in C.scan({"90001": {"baliContext": ours}})[0]


# ── innocence — the two rules that legitimately say ten billion ─────────────


def test_innocence_the_total_investment_threshold_is_not_touched():
    text = "Total investment must exceed IDR 10 billion per 5-digit KBLI per location."
    cure, refused = C.scan({"90001": {"baliContext": text}})
    assert cure == {} and refused == {}


def test_innocence_the_e28a_shareholding_threshold_is_not_touched():
    text = ("An Investor KITAS (E28A) requires IDR 10 billion of shareholding in "
            "the company — an immigration rule, separate from BKPM.")
    assert C.scan({"90001": {"baliContext": text}})[0] == {}


def test_innocence_a_code_already_saying_two_point_five_is_not_a_finding():
    text = "A PT PMA requires a minimum paid-up capital of IDR 2.5 billion."
    assert C.scan({"90001": {"baliContext": text}})[0] == {}


def test_innocence_stated_capital_beside_a_regulator_figure_is_refused_not_cured():
    text = "**Minimum capital:** IDR 100 billion paid-up (OJK requirement) + IDR 10B PT PMA stated capital."
    cure, refused = C.scan({"90001": {"whatYouNeed": text}})
    assert cure == {} and "90001" in refused


def test_innocence_the_match_never_crosses_a_sentence_boundary():
    """"…paid-up capital." then a NEW sentence mentioning ten billion is two
    facts, not one claim."""
    text = ("A PT PMA requires a minimum paid-up capital of IDR 2.5 billion. "
            "Total investment must exceed IDR 10 billion per location.")
    assert C.scan({"90001": {"baliContext": text}})[0] == {}


def test_two_ten_billion_figures_in_one_clause_are_refused_not_guessed():
    gold = {"90001": {"baliContext":
        "Paid-up capital IDR 10 billion and investment IDR 10 billion apply"}}
    with pytest.raises(C.CureError, match="not a deduction"):
        C.plan(gold)


# ── the figure is not this file's to assert ─────────────────────────────────


def test_the_claim_ledger_still_states_two_point_five(gold):
    """W106: a constant nobody re-measures is a countdown. The compiler refuses
    to run if the ledger stops saying 2.5, rather than carrying its own copy of
    a fact that can be superseded."""
    ledger = json.loads(
        (REPO_ROOT / "apps/mouth/src/content/_regulatory-claim-ledger.json").read_text(
            encoding="utf-8"
        )
    )
    claims = ledger.get("claims", ledger)
    entries = list(claims.values()) if isinstance(claims, dict) else list(claims)
    fact = next(c["current_fact"] for c in entries
                if isinstance(c, dict) and c.get("id") == "CAPITAL-PAIDUP-10B")
    assert "IDR 2.5 billion" in fact and "Pasal 26(10)" in fact
