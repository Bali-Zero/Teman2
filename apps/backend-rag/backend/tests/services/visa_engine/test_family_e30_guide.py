"""E30: Law-derived data, all four-question paths and exact month boundaries."""

import json
import re
from pathlib import Path

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

DATA = guide.load_family("E30")
LAW_DIR = guide.HERE / "law" / "E30"
PATHS = {
    "secondary_or_below": "E30A",
    "undergraduate": "E30B",
    "postgraduate": "E30B",
    "doctoral": "E30B",
}
YEARS = {"E30A": [1, 2], "E30B": [1, 2, 4]}


def law(code: str) -> dict:
    return json.loads((LAW_DIR / f"{code}.json").read_text())


def answers(level: str, **extra: object) -> dict:
    return {
        "study_level": level,
        "admission": "yes",
        "sponsor": "individual",
        "stay_months": 12,
        **extra,
    }


def test_only_source_verified_codes_are_reachable() -> None:
    assert DATA["questions"]["study_level"]["options"] == PATHS
    assert set(DATA["visas"]) == {"E30", "E30A", "E30B", "E30E", "E30F"}
    for code in set(DATA["visas"]) - set(PATHS.values()):
        assert law(code)["status"] == "NOT_FOUND"
        assert DATA["visas"][code]["stay_options"] is None
    assert "sekolah menengah atas dan jenjang di bawahnya" in law("E30A")["definition_verbatim"]
    assert "sarjana, pascasarjana hingga doktoral" in law("E30B")["definition_verbatim"]


@pytest.mark.parametrize("code", YEARS)
def test_data_equals_each_codes_law(code: str) -> None:
    card = law(code)
    visa = DATA["visas"][code]
    assert visa["sponsor_required"] is card["sponsor_required"]["as_stated_boolean"] is True
    assert visa["extendable"] is ("dapat diperpanjang" in " ".join(card["extendable"]))
    assert visa["entry_type"] == card["entry"].upper() == "MULTIPLE"
    assert visa["stay_options"] == [{"value": y, "unit": "YEAR"} for y in YEARS[code]]
    assert [
        int(y)
        for y in re.findall(
            r"Masa tinggal (\d+) tahun", "\n".join(card["pnbp_verbatim_for_reference_only"])
        )
    ] == YEARS[code]
    stay = " ".join(card["stay_days"])
    assert ("1 atau 2 tahun" if code == "E30A" else "1 tahun 2 tahun, atau 4 tahun") in stay
    assert "perorangan atau institusi pendidikan" in card["requirements_verbatim"][5]["text"]
    assert "Surat penerimaan" in card["requirements_verbatim"][6]["text"]
    assert card["total_max_verbatim"] is None
    assert "max_total_days" not in visa and "max_total_months" not in visa


@pytest.mark.parametrize("level,code", PATHS.items())
def test_questions_in_order(level: str, code: str) -> None:
    assert resolve("E30", {}) == {"ask": "study_level"}
    a = {"study_level": level}
    assert resolve("E30", a) == {"ask": "admission", "code": code}
    a["admission"] = "yes"
    assert resolve("E30", a) == {"ask": "sponsor", "code": code}
    a["sponsor"] = "education_institution"
    assert resolve("E30", a) == {"ask": "stay_months", "code": code}


@pytest.mark.parametrize("level,code", PATHS.items())
@pytest.mark.parametrize("sponsor", ["individual", "education_institution"])
def test_every_initial_stay_month(level: str, code: str, sponsor: str) -> None:
    for months in range(1, YEARS[code][-1] * 12 + 1):
        year = next(y for y in YEARS[code] if months <= y * 12)
        assert resolve("E30", answers(level, sponsor=sponsor, stay_months=months)) == {
            "code": code,
            "verdict": OK,
            "stay_option": {"value": year, "unit": "YEAR"},
        }
    for months in (YEARS[code][-1] * 12 + 1, 1200):
        # Extendable, but the Law publishes no total maximum: largest option, total_max_known false.
        assert resolve("E30", answers(level, sponsor=sponsor, stay_months=months)) == {
            "code": code,
            "verdict": OK_WITH_EXTENSION,
            "stay_option": {"value": YEARS[code][-1], "unit": "YEAR"},
            "total_max_known": False,
        }


@pytest.mark.parametrize("level,code", PATHS.items())
def test_admission_and_sponsor_rejection_paths(level: str, code: str) -> None:
    assert resolve("E30", answers(level, admission="no")) == {"code": code, "verdict": NOT_COVERED}
    for sponsor in ("none", "other"):
        assert resolve("E30", answers(level, sponsor=sponsor)) == {
            "code": code,
            "verdict": NEEDS_SPONSOR,
        }


@pytest.mark.parametrize("value", [None, "", "invalid", True, False, 1, 0])
@pytest.mark.parametrize("question", ["study_level", "admission", "sponsor"])
def test_invalid_choices_ask_again(question: str, value: object) -> None:
    result = resolve("E30", answers("undergraduate", **{question: value}))
    assert result["ask"] == question


@pytest.mark.parametrize(
    "value", [None, "", "0", 0, -1, True, False, 1.5, "1.5", "１２", "-1", " 12 "]
)
def test_invalid_months_ask_again(value: object) -> None:
    assert resolve("E30", answers("undergraduate", stay_months=value)) == {
        "ask": "stay_months",
        "code": "E30B",
    }


def test_numeric_string_months() -> None:
    assert resolve("E30", answers("undergraduate", stay_months="25"))["stay_option"] == {
        "value": 4,
        "unit": "YEAR",
    }


def test_month_choices_are_exact_and_day_choices_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    data = json.loads(json.dumps(DATA))
    data["visas"]["E30B"]["stay_options"] = [
        {"value": 4, "unit": "YEAR"},
        {"value": 4000, "unit": "DAY"},
        {"value": 6, "unit": "MONTH"},
        {"value": 1, "unit": "YEAR"},
    ]
    monkeypatch.setattr(guide, "load_family", lambda family: data)
    assert resolve("E30", answers("undergraduate", stay_months=6))["stay_option"] == {
        "value": 6,
        "unit": "MONTH",
    }
    assert resolve("E30", answers("undergraduate", stay_months=7))["stay_option"] == {
        "value": 1,
        "unit": "YEAR",
    }
    assert resolve("E30", answers("undergraduate", stay_months=49))["verdict"] == OK_WITH_EXTENSION


def test_over_max_not_extendable_is_stay_too_long(monkeypatch: pytest.MonkeyPatch) -> None:
    data = json.loads(json.dumps(DATA))
    data["visas"]["E30B"]["extendable"] = False
    monkeypatch.setattr(guide, "load_family", lambda family: data)
    assert resolve("E30", answers("undergraduate", stay_months=49)) == {
        "code": "E30B",
        "verdict": STAY_TOO_LONG,
    }


@pytest.mark.parametrize("stay_days", [None, 30])
def test_null_stay_options_falls_through_to_stay_days(
    monkeypatch: pytest.MonkeyPatch, stay_days: int | None
) -> None:
    data = json.loads(json.dumps(DATA))
    data["visas"]["E30B"]["stay_options"] = None
    data["visas"]["E30B"]["stay_days"] = 60
    data["visas"]["E30B"]["extendable"] = False
    monkeypatch.setattr(guide, "load_family", lambda family: data)
    a = answers("undergraduate")
    assert resolve("E30", a) == {"ask": "stay_days", "code": "E30B"}
    a["stay_days"] = 60 if stay_days is None else stay_days
    assert resolve("E30", a) == {"code": "E30B", "verdict": OK}


def test_itap_stays_unknown_for_every_code() -> None:
    evidence = json.loads((LAW_DIR / "ITAP.json").read_text())
    assert {m["code"] for m in evidence["code_mapping"]} == set(DATA["visas"])
    for mapping in evidence["code_mapping"]:
        assert mapping["itas_to_itap_eligible_as_stated"] is None
        assert mapping["status"] == "TO_VERIFY"
        assert law(mapping["code"])["itap_assessment"]["itas_to_itap_eligible_as_stated"] is None


@pytest.mark.parametrize("path", sorted(LAW_DIR.glob("*.json")), ids=lambda p: p.name)
def test_law_source_identity(path: Path) -> None:
    card = json.loads(path.read_text())
    if path.stem != "ITAP":
        assert re.fullmatch(r"[0-9a-f]{64}", card["page_sha256"])
        assert card["source_url"].endswith("/" + path.stem)
