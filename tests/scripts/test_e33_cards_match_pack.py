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
    assert f"{rd.PACK_ID}.signed.json" in text
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


def test_cards_state_no_fee_split(cards):
    # An all-inclusive catalog price is stated; a PNBP / service-fee split never is.
    for code, text in cards.items():
        for word in ("PNBP", "Rp.", "Rp1", "service fee"):
            assert word not in text, f"{code} card carries {word}"


def test_a_changed_price_or_pricing_key_is_named(pack, cards):
    mutated = dict(cards)
    mutated["E33E"] = cards["E33E"].replace("45,000,000 IDR", "40,000,000 IDR")
    assert rd.diff(pack, mutated) == [
        "E33E: catalog price 45,000,000 IDR for E33E Second Home Senior (5 Years) is not stated on the card"
    ]
    mutated["E33E"] = cards["E33E"].replace("Second Home Senior (5 Years)", "Senior")
    assert any("pricing key" in line for line in rd.diff(pack, mutated))


def test_a_changed_threshold_is_named(pack, cards):
    mutated = dict(cards)
    mutated["E33G"] = cards["E33G"].replace("USD 60,000", "USD 6,000")
    lines = rd.diff(pack, mutated)
    assert lines and all("pack threshold 60000 is not stated" in x for x in lines)
    mutated = dict(cards)
    mutated["E33E"] = cards["E33E"].replace("age below 55", "age below 65")
    assert rd.diff(pack, mutated) == [
        "E33E: hf.e33e.age-below-55: pack threshold 55 is not stated on the card row"
    ]


@pytest.mark.parametrize("old,new", [("| HARD_FILTER |", "| ELIGIBILITY |"), ("EXCLUDE /", "SUPPORT /")])
def test_a_changed_stage_or_effect_is_named(pack, cards, old, new):
    row = "| `hf.e33f.age-below-55` | HARD_FILTER | EXCLUDE /"
    mutated = {**cards, "E33F": cards["E33F"].replace(row, row.replace(old, new))}
    assert len(rd.diff(pack, mutated)) == 1


def test_the_active_pack_is_the_highest_signed_prod_pack():
    names = sorted(p.name for p in rd.PACKS_DIR.glob("rulepack-prod-[0-9]*.signed.json"))
    assert rd.PACK.name == names[-1]


def test_a_newer_signed_pack_not_reflected_on_the_cards_is_named(monkeypatch, pack, cards):
    # Simulate the next activation: the section heading the diff expects moves to the new pack id.
    monkeypatch.setattr(rd, "SECTION", "## 2. Active rules (rulepack-prod-030)")
    lines = rd.diff(pack, cards)
    assert len(lines) == sum(PACK_COUNTS.values())
    assert all("missing on the card" in x for x in lines)


def test_registry_work_fact_says_rangkap_reporting():
    facts = {f["id"]: f for f in json.loads(REGISTRY.read_text(encoding="utf-8"))["facts"]}
    value = facts["e33_not_work_visa"]["value"]
    assert "rangkap-kegiatan" in value
    assert "only after" in value
    assert "does NOT authorize employment" not in value
    assert facts["e33_not_work_visa"]["source_date"] == "2026-10-13"


def test_registry_ids_are_unique_and_e33g_is_recorded():
    facts = json.loads(REGISTRY.read_text(encoding="utf-8"))["facts"]
    assert len({f["id"] for f in facts}) == len(facts)
    assert "USD 60,000 per year" in {f["id"]: f for f in facts}["e33g_requirements"]["value"]


def test_registry_e33f_sponsor_is_confirmed_and_matches_the_pack_metadata(pack):
    facts = {f["id"]: f for f in json.loads(REGISTRY.read_text(encoding="utf-8"))["facts"]}
    fact = facts["e33f_sponsor_requirement"]
    assert (fact["status"], fact["confidence"]) == ("confirmed", "JELAS")
    e33f = next(p for p in pack["payload"]["products"] if p["product_code"] == "E33F")
    assert e33f["sponsor_types"] == ["INDIVIDUAL"]
