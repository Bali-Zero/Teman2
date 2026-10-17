"""Family guide: answers -> visa code -> verdict. Data comes from family_<x>.json, built from law/<X>/*.json."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

HERE = Path(__file__).parent

OK = "OK"
OK_WITH_EXTENSION = "OK_WITH_EXTENSION"
NEEDS_SPONSOR = "NEEDS_SPONSOR"
STAY_TOO_LONG = "STAY_TOO_LONG"


@cache
def load_family(family: str) -> dict:
    return json.loads((HERE / f"family_{family.lower()}.json").read_text())


def max_total_days(visa: dict) -> int:
    if "max_total_days" in visa:
        return visa["max_total_days"]
    return visa["max_total_months"] * 30


def resolve(family: str, answers: dict) -> dict:
    """Return {"ask": question_id} while an answer is missing, else {"code", "verdict"}."""
    data = load_family(family)
    questions = data["questions"]
    choice = questions["activity"]["options"].get(answers.get("activity"))
    if choice is None:
        return {"ask": "activity"}
    while isinstance(choice, dict):
        sub = choice["ask"]
        if sub not in answers:
            return {"ask": sub}
        choice = questions[sub]["options"].get(answers[sub])
        if choice is None:
            return {"ask": sub}
    code = choice
    visa = data["visas"][code]
    if visa["sponsor_required"]:
        if "sponsor" not in answers:
            return {"ask": "sponsor", "code": code}
        if not answers["sponsor"]:
            return {"code": code, "verdict": NEEDS_SPONSOR}
    if "stay_days" not in answers:
        return {"ask": "stay_days", "code": code}
    days = int(answers["stay_days"])
    if days <= visa["stay_days"]:
        return {"code": code, "verdict": OK}
    if visa["extendable"] and days <= max_total_days(visa):
        return {"code": code, "verdict": OK_WITH_EXTENSION}
    return {"code": code, "verdict": STAY_TOO_LONG}
