"""Family C: data must equal the Law cards, and every Guide path must give the expected verdict."""

import json
import re

import pytest

from backend.services.visa_engine.families import guide
from backend.services.visa_engine.families.guide import (
    NEEDS_SPONSOR,
    NOT_COVERED,
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


CONDITIONAL_SPONSOR = {"C1", "C2"}
GATED = {"C8A", "C8B"}


def prefix_for(code, path):
    """Answers that get a path past the gate questions (travel document, non-commercial sport)."""
    extra = {}
    if code in CONDITIONAL_SPONSOR:
        extra["travel_document"] = "national_passport"
    if code in GATED:
        extra["sport_non_commercial"] = "yes"
    return answers_for(path, **extra)


@pytest.mark.parametrize("path,code", PATH_TO_CODE.items())
def test_path(path, code):
    sponsor_needed, stay, max_ok = EXPECTED[code]

    # questions come in order: activity -> (sub) -> gate -> sponsor (if needed) -> days
    assert resolve("C", {}) == {"ask": "activity"}
    if len(path) == 2:
        assert resolve("C", {"activity": path[0]}) == {"ask": SUB_QUESTION[path[0]]}
    nxt = resolve("C", answers_for(path))
    if code in CONDITIONAL_SPONSOR:
        assert nxt == {"ask": "travel_document", "code": code}
    elif code in GATED:
        assert nxt == {"ask": "sport_non_commercial", "code": code}
    else:
        assert nxt == {"ask": "sponsor" if sponsor_needed else "stay_days", "code": code}

    base = prefix_for(code, path)
    if sponsor_needed:
        assert resolve("C", {**base}) == {"ask": "sponsor", "code": code}
        assert resolve("C", {**base, "sponsor": "no"}) == {"code": code, "verdict": NEEDS_SPONSOR}
        base = {**base, "sponsor": "yes"}
    assert resolve("C", base) == {"ask": "stay_days", "code": code}

    def verdict(days):
        return resolve("C", {**base, "stay_days": days})

    assert verdict(1) == {"code": code, "verdict": OK}
    assert verdict(stay) == {"code": code, "verdict": OK}
    assert verdict(str(stay)) == {"code": code, "verdict": OK}
    if max_ok is None:
        assert verdict(stay + 1) == {"code": code, "verdict": STAY_TOO_LONG}
    else:
        assert verdict(stay + 1) == {"code": code, "verdict": OK_WITH_EXTENSION}
        assert verdict(max_ok) == {"code": code, "verdict": OK_WITH_EXTENSION}
        assert verdict(max_ok + 1) == {"code": code, "verdict": STAY_TOO_LONG}


@pytest.mark.parametrize("code,activity", [("C1", "holiday"), ("C2", "business_meetings")])
def test_conditional_sponsor_other_document_needs_sponsor(code, activity):
    a = {"activity": activity, "travel_document": "other_document"}
    assert resolve("C", a) == {"ask": "sponsor", "code": code}
    assert resolve("C", {**a, "sponsor": "no"}) == {"code": code, "verdict": NEEDS_SPONSOR}
    assert resolve("C", {**a, "sponsor": "yes"}) == {"ask": "stay_days", "code": code}
    assert resolve("C", {**a, "sponsor": "yes", "stay_days": 30}) == {"code": code, "verdict": OK}


@pytest.mark.parametrize("code,activity", [("C1", "holiday"), ("C2", "business_meetings")])
def test_conditional_sponsor_national_passport_skips_sponsor(code, activity):
    a = {"activity": activity, "travel_document": "national_passport"}
    assert resolve("C", a) == {"ask": "stay_days", "code": code}
    # a stray sponsor answer is ignored
    assert resolve("C", {**a, "sponsor": "no", "stay_days": 30}) == {"code": code, "verdict": OK}


@pytest.mark.parametrize("code,role", [("C8A", "athlete"), ("C8B", "official")])
def test_commercial_sport_is_not_covered(code, role):
    a = {"activity": "sport", "sport_role": role, "sport_non_commercial": "no"}
    assert resolve("C", a) == {"code": code, "verdict": NOT_COVERED}
    # not covered wins over every later answer
    assert resolve("C", {**a, "sponsor": "yes", "stay_days": 10}) == {
        "code": code,
        "verdict": NOT_COVERED,
    }


def test_sport_non_commercial_unknown_key_asks_again():
    a = {"activity": "sport", "sport_role": "athlete"}
    for bad in (None, True, "maybe"):
        assert resolve("C", {**a, "sport_non_commercial": bad}) == {
            "ask": "sport_non_commercial",
            "code": "C8A",
        }


def test_non_gated_codes_never_ask_the_gate_questions():
    assert resolve("C", {"activity": "speaker"}) == {"ask": "sponsor", "code": "C10"}
    assert resolve("C", {"activity": "holiday", "travel_document": "national_passport"}) == {
        "ask": "stay_days",
        "code": "C1",
    }


@pytest.mark.parametrize(
    "bad", [True, False, 0, -1, -30, 1.5, 30.0, None, "", "abc", "-5", "0", "1.5", " 7", "٣٠"]
)
def test_invalid_stay_days_asks_again(bad):
    a = {"activity": "speaker", "sponsor": "yes", "stay_days": bad}
    assert resolve("C", a) == {"ask": "stay_days", "code": "C10"}


def test_valid_stay_days_forms():
    a = {"activity": "speaker", "sponsor": "yes"}
    assert resolve("C", {**a, "stay_days": 60})["verdict"] == OK
    assert resolve("C", {**a, "stay_days": "60"})["verdict"] == OK


@pytest.mark.parametrize("bad", [True, False, None, "", "maybe", "YES", 1])
def test_unknown_sponsor_key_asks_again(bad):
    a = {"activity": "speaker", "sponsor": bad, "stay_days": 30}
    assert resolve("C", a) == {"ask": "sponsor", "code": "C10"}


def test_unknown_travel_document_asks_again():
    for bad in (None, True, "passport"):
        a = {"activity": "holiday", "travel_document": bad}
        assert resolve("C", a) == {"ask": "travel_document", "code": "C1"}


def test_unknown_answer_asks_again():
    assert resolve("C", {"activity": "space_tourism"}) == {"ask": "activity"}
    assert resolve("C", {"activity": "music", "music_role": "dj"}) == {"ask": "music_role"}
