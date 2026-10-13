"""The E33-family doctrine cards and the E33 fact registry describe the active signed pack.

Guilt and innocence: the real cards agree with rulepack-prod-029.signed.json, and a card that
drops a rule, invents one, or loses its rules section is named by the diff.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import e33_cards_rule_diff as rd  # noqa: E402

REGISTRY = REPO_ROOT / "research" / "secondhome" / "e33-fact-registry.json"
PACK_COUNTS = {"E33": 6, "E33A": 2, "E33B": 3, "E33C": 2, "E33E": 4, "E33F": 3, "E33G": 6}


@pytest.fixture(scope="module")
def pack() -> dict:
    return json.loads(rd.PACK.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cards() -> dict[str, str]:
    return {c: (rd.CARDS_DIR / f"{c}.md").read_text(encoding="utf-8") for c in rd.CODES}


def test_rule_id_diff_is_empty(pack, cards):
    assert rd.diff(pack, cards) == []


def test_pack_rule_counts_per_product_are_pinned(pack):
    counts = {code: len(ids) for code, ids in rd.pack_rules_by_code(pack).items()}
    assert counts == PACK_COUNTS


@pytest.mark.parametrize("code", rd.CODES)
def test_each_card_names_the_active_pack_and_its_page(code, cards):
    text = cards[code]
    assert "rulepack-prod-029.signed.json" in text
    assert f"https://www.imigrasi.go.id/wna/daftar-visa-indonesia/{code}" in text
    assert rd.SECTION in text


def test_a_dropped_rule_is_named(pack, cards):
    mutated = dict(cards)
    mutated["E33G"] = cards["E33G"].replace("`hf.e33g.annual-income-below-minimum`", "`x`")
    assert rd.diff(pack, mutated) == [
        "E33G: in the pack, missing on the card: hf.e33g.annual-income-below-minimum"
    ]


def test_an_invented_rule_is_named(pack, cards):
    mutated = dict(cards)
    mutated["E33E"] = cards["E33E"].replace(
        "| `hf.e33e.age-below-55` |", "| `el.e33e.deposit-income-basis` | x | x | x |\n| `hf.e33e.age-below-55` |"
    )
    assert rd.diff(pack, mutated) == [
        "E33E: on the card, not in the pack: el.e33e.deposit-income-basis"
    ]


def test_a_retired_rule_outside_the_rules_section_is_not_counted(pack, cards):
    # E33 section 5 names a retired seq-7 rule in backticks; it must not count as active.
    assert "review.e33.work-rangkap-kegiatan" in cards["E33"]
    assert "review.e33.work-rangkap-kegiatan" not in rd.card_rule_ids(cards["E33"])
    assert rd.diff(pack, cards) == []


def test_a_card_without_the_rules_section_names_every_rule(pack, cards):
    mutated = dict(cards)
    mutated["E33C"] = cards["E33C"].replace(rd.SECTION, "## 2. Rules")
    assert rd.diff(pack, mutated) == [
        "E33C: in the pack, missing on the card: el.e33c.world-figure-invitation",
        "E33C: in the pack, missing on the card: hf.e33c.sponsor-not-government-or-none",
    ]


def test_a_card_swapped_with_another_is_named(pack, cards):
    mutated = dict(cards)
    mutated["E33F"] = cards["E33E"]
    assert len(rd.diff(pack, mutated)) == 7


def test_cards_state_no_fee_split(cards):
    for code, text in cards.items():
        for word in ("PNBP", "Rp.", "Rp1", "IDR"):
            assert word not in text, f"{code} card carries {word}"


def test_cards_no_longer_carry_the_stale_seq7_claims(cards):
    assert "seq-7, verified live" not in "".join(cards.values())
    assert "standard pension" not in cards["E33F"].split("## 1.")[1]
    assert "age-gated retirement" not in cards["E33"]


def test_registry_work_fact_says_rangkap_reporting():
    facts = {f["id"]: f for f in json.loads(REGISTRY.read_text(encoding="utf-8"))["facts"]}
    value = facts["e33_not_work_visa"]["value"]
    assert "rangkap-kegiatan" in value
    assert "only after" in value
    assert "does NOT authorize employment" not in value
    assert facts["e33_not_work_visa"]["source_date"] == "2026-10-13"


def test_registry_ids_are_unique_and_e33g_is_recorded():
    facts = json.loads(REGISTRY.read_text(encoding="utf-8"))["facts"]
    ids = [f["id"] for f in facts]
    assert len(ids) == len(set(ids))
    g = {f["id"]: f for f in facts}["e33g_requirements"]
    assert "USD 60,000 per year" in g["value"]
