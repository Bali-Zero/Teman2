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
NOT_COVERED = "NOT_COVERED"  # the activity is outside what this visa allows (e.g. commercial sport on C8A/C8B)


@cache
def load_family(family: str) -> dict:
    return json.loads((HERE / f"family_{family.lower()}.json").read_text())


def max_total_days(visa: dict) -> int:
    if "max_total_days" in visa:
        return visa["max_total_days"]
    return visa["max_total_months"] * 30


def _positive_int(value: object) -> int | None:
    """A positive integer, from an int or a string of digits; anything else is None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value) or None
    return None


def resolve(family: str, answers: dict) -> dict:
    """Return {"ask": question_id} while an answer is missing, else {"code", "verdict"}."""
    data = load_family(family)
    questions = data["questions"]
    start = data.get("start_question", "activity")
    choice = questions[start]["options"].get(answers.get(start))
    if choice is None:
        return {"ask": start}
    while isinstance(choice, dict):
        sub = choice["ask"]
        if sub not in answers:
            return {"ask": sub}
        choice = questions[sub]["options"].get(answers[sub])
        if choice is None:
            return {"ask": sub}
    code = choice
    visa = data["visas"][code]
    gate = visa.get("requires_question")
    if gate:
        if answers.get(gate) not in questions[gate]["options"]:
            return {"ask": gate, "code": code}
        if not questions[gate]["options"][answers[gate]]:
            return {"code": code, "verdict": NOT_COVERED}
    if visa["sponsor_required"]:
        needs_sponsor_question = True
    else:
        # Sponsor is conditional (stateless / non-national travel document / listed countries).
        if answers.get("travel_document") not in questions["travel_document"]["options"]:
            return {"ask": "travel_document", "code": code}
        needs_sponsor_question = questions["travel_document"]["options"][answers["travel_document"]]
    if needs_sponsor_question:
        if answers.get("sponsor") not in questions["sponsor"]["options"]:
            return {"ask": "sponsor", "code": code}
        if not questions["sponsor"]["options"][answers["sponsor"]]:
            return {"code": code, "verdict": NEEDS_SPONSOR}
    if visa.get("stay_options"):
        months = _positive_int(answers.get("stay_months"))
        if months is None:
            return {"ask": "stay_months", "code": code}
        # Compare only exact calendar-month units, never approximate a day option.
        options = sorted(
            (o for o in visa["stay_options"] if o["unit"] in {"MONTH", "YEAR"}),
            key=lambda o: o["value"] * (12 if o["unit"] == "YEAR" else 1),
        )
        for option in options:
            if months <= option["value"] * (12 if option["unit"] == "YEAR" else 1):
                return {"code": code, "verdict": OK, "stay_option": option}
        if visa["extendable"]:
            # The Law says the stay "dapat diperpanjang" but publishes no cumulative maximum.
            return {
                "code": code,
                "verdict": OK_WITH_EXTENSION,
                "stay_option": options[-1],
                "total_max_known": False,
            }
        return {"code": code, "verdict": STAY_TOO_LONG}
    days = _positive_int(answers.get("stay_days"))
    if days is None:
        return {"ask": "stay_days", "code": code}
    if days <= visa["stay_days"]:
        return {"code": code, "verdict": OK}
    if visa["extendable"] and days <= max_total_days(visa):
        return {"code": code, "verdict": OK_WITH_EXTENSION}
    return {"code": code, "verdict": STAY_TOO_LONG}
