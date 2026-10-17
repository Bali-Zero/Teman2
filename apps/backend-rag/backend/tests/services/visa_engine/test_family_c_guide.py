"""Family C: data must equal the Law cards, and every Guide path must give the expected verdict."""

import json
import re

import pytest

from backend.services.visa_engine.families import guide
from backend.services.visa_engine.families.guide import (
    NEEDS_SPONSOR,
    OK,
    OK_WITH_EXTENSION,
    STAY_TOO_LONG,
    resolve,
)

DATA = guide.load_family("C")
LAW_DIR = guide.HERE / "law" / "C"
CODES = sorted(DATA["visas"])

# Expected answers written by hand from the Law cards (independent of family_c.json).
PATH_TO_CODE = {
    ("holiday",): "C1",
    ("business_meetings",): "C2",
    ("explore_investment",): "C12",
    ("social_activity",): "C6",
    ("music", "performer"): "C7A",
    ("music", "crew"): "C7B",
    ("other_arts",): "C7C",
    ("sport", "athlete"): "C8A",
    ("sport", "official"): "C8B",
    ("speaker",): "C10",
    ("skill_test",): "C18",
    ("internship", "studies"): "C22A",
    ("internship", "skills"): "C22B",
}
SUB_QUESTION = {"music": "music_role", "sport": "sport_role", "internship": "internship_type"}
# code: (sponsor needed, stay days, last day still OK with extension or None)
EXPECTED = {
    "C1": (False, 60, 180),
    "C2": (False, 60, 180),
    "C6": (True, 60, 180),
    "C7A": (True, 30, None),
    "C7B": (True, 30, None),
    "C7C": (True, 30, None),
    "C8A": (True, 60, 180),
    "C8B": (True, 60, 180),
    "C10": (True, 60, 180),
    "C12": (True, 180, 360),
    "C18": (True, 90, None),
    "C22A": (True, 180, 360),
    "C22B": (True, 180, 360),
}


def law(code):
    return json.loads((LAW_DIR / f"{code}.json").read_text())


def answers_for(path, **extra):
    a = {"activity": path[0]}
    if len(path) == 2:
        a[SUB_QUESTION[path[0]]] = path[1]
    return {**a, **extra}


# --- 1. Data = Law -------------------------------------------------------


def test_every_visa_has_a_law_card_and_vice_versa():
    assert {p.stem for p in LAW_DIR.glob("C*.json")} == set(CODES)


@pytest.mark.parametrize("code", CODES)
def test_sponsor_matches_law(code):
    assert (
        DATA["visas"][code]["sponsor_required"]
        is law(code)["sponsor_required"]["as_stated_boolean"]
    )


@pytest.mark.parametrize("code", CODES)
def test_stay_days_match_law(code):
    text = " ".join(law(code)["stay_days"])
    assert int(re.search(r"maksimal (\d+) hari", text).group(1)) == DATA["visas"][code]["stay_days"]


@pytest.mark.parametrize("code", CODES)
def test_extension_matches_law(code):
    text = " ".join(law(code)["extendable"])
    visa = DATA["visas"][code]
    assert visa["extendable"] is ("tidak dapat memperpanjang" not in text)
    if not visa["extendable"]:
        return
    days = re.search(r"hingga maksimal (\d+) hari", text)
    months = re.search(r"(?:hingga maksimal|tidak lebih dari) (\d+)\s*(?:\([^)]*\)\s*)?bulan", text)
    if "max_total_days" in visa:
        assert days and int(days.group(1)) == visa["max_total_days"]
    else:
        assert months and int(months.group(1)) == visa["max_total_months"]


@pytest.mark.parametrize("code", CODES)
def test_non_extendable_total_equals_stay_days(code):
    visa = DATA["visas"][code]
    if visa["extendable"]:
        return
    assert visa["max_total_days"] == visa["stay_days"]
    assert "max_total_months" not in visa


# --- 2. Every path -------------------------------------------------------


def test_every_code_is_reached_by_exactly_one_path():
    assert sorted(PATH_TO_CODE.values()) == CODES


@pytest.mark.parametrize("path,code", PATH_TO_CODE.items())
def test_path(path, code):
    sponsor_needed, stay, max_ok = EXPECTED[code]

    # questions come in order: activity -> (sub) -> sponsor (if needed) -> days
    assert resolve("C", {}) == {"ask": "activity"}
    if len(path) == 2:
        assert resolve("C", {"activity": path[0]}) == {"ask": SUB_QUESTION[path[0]]}
    nxt = resolve("C", answers_for(path))
    assert nxt == {"ask": "sponsor" if sponsor_needed else "stay_days", "code": code}

    sp = {"sponsor": True} if sponsor_needed else {}
    if sponsor_needed:
        assert resolve("C", answers_for(path, sponsor=False)) == {
            "code": code,
            "verdict": NEEDS_SPONSOR,
        }

    def verdict(days):
        return resolve("C", answers_for(path, stay_days=days, **sp))

    assert verdict(1) == {"code": code, "verdict": OK}
    assert verdict(stay) == {"code": code, "verdict": OK}
    if max_ok is None:
        assert verdict(stay + 1) == {"code": code, "verdict": STAY_TOO_LONG}
    else:
        assert verdict(stay + 1) == {"code": code, "verdict": OK_WITH_EXTENSION}
        assert verdict(max_ok) == {"code": code, "verdict": OK_WITH_EXTENSION}
        assert verdict(max_ok + 1) == {"code": code, "verdict": STAY_TOO_LONG}


def test_unknown_answer_asks_again():
    assert resolve("C", {"activity": "space_tourism"}) == {"ask": "activity"}
    assert resolve("C", {"activity": "music", "music_role": "dj"}) == {"ask": "music_role"}
