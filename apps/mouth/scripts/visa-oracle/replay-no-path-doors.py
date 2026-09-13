"""Generator for `_lib/fixtures/no-path-doors.replay.json` — the PROOF behind
every "door that is open" the Visa Oracle names on a dead end.

The outcome sheet may not assert an alternative product from prose. It names
one only where the SIGNED pack, replayed on the applicant's OWN stated facts
with exactly ONE declared field changed, returns that product as supported.
This script produces that evidence and nothing else:

  * `doors.TOURISM` / `doors.SECOND_HOME` — the same walk, same facts, with
    `intent.purposes` set to that purpose alone. Nothing is invented: every
    other fact (including every UNKNOWN one) is carried over verbatim.
  * `doors.AGE_55` — the same walk with `person.birth_date` set to a date that
    makes the applicant exactly 55 at the evaluation instant. It is the only
    honest way to back the "when you turn 55" sentence on an `AGE_BELOW_55`
    dead end, and it is deliberately NOT rendered as a button: nothing the
    visitor can answer today opens it.

Read-only: it never writes to the backend, never touches the DB, and pins
`as_of` to the census test's own instant (inside the signed pack's validity
window — a replay outside it measures a pack that is not in force).

    apps/backend-rag/.venv/bin/python \
      apps/mouth/scripts/visa-oracle/replay-no-path-doors.py

Re-run it whenever the interview corpus moves: `no-path-doors.test.ts`
fingerprints the walk files this evidence was measured on and goes red the
moment they change, because a door proven on stale facts is not proven.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BACKEND = REPO / "apps" / "backend-rag"
OUT = (
    HERE.parents[1]
    / "src/app/(visa-oracle)/visa-oracle/_lib/fixtures/no-path-doors.replay.json"
)

sys.path.insert(0, str(BACKEND))

from backend.scripts.visa_engine import gold_coverage_eval as gce  # noqa: E402
from backend.tests.services.visa_engine.test_interview_walk_census import (  # noqa: E402
    _AS_OF,
    CORPUS_DIR,
)

# Exactly 55 at `_AS_OF` (2026-09-06): the age the `AGE_BELOW_55` reason code
# names, not a year past it.
AGE_55_BIRTH_DATE = "1971-09-01"
PURPOSE_DOORS = ("TOURISM", "SECOND_HOME")

# Counterexamples — the adversarial half of the evidence (Codex council round
# 1, 2026-09-13: "the rules are proven on 17 synthetic fact sets and
# generalised to every visitor"). Each row changes ONE answer a real visitor
# can give, on a walk that keeps its dead end, and records the doors the pack
# leaves SHUT. `no-path-doors.test.tsx` asserts the UI names none of them —
# the innocence half of the guilt/innocence pair, without which a door rule is
# only ever tested where it happens to be right.
#
# `ui` is the interview answer; `engine` is the wire fact the mapper derives
# from it. The two are written side by side on purpose: a counterexample that
# cannot be expressed as an ANSWER is not a counterexample about this UI.
COUNTEREXAMPLES = (
    {
        "id": "indonesian-nationality",
        "walk_fixture": "offshore_business.json",
        "ui": {"nationalities": "ID"},
        "engine": {"person.nationalities": ["ID"]},
        "why": "the pack answers APPLICANT_IS_INDONESIAN_CITIZEN under every purpose",
    },
    {
        "id": "stay-beyond-tourist-bound",
        "walk_fixture": "offshore_business.json",
        "ui": {"stay_days": "400"},
        "engine": {"intent.stay_days": 400},
        "why": "C1 covers the declared stay up to 180 days; 181 already has no path",
    },
    {
        "id": "deposit-not-at-state-bank",
        "walk_fixture": "offshore_retirement_bank_deposit.json",
        "ui": {"secondhome_state_bank": "no"},
        "engine": {"secondhome.bank_deposit_at_state_bank": False},
        "why": "the Second Home deposit basis is conditioned on the bank, not only the amount",
    },
    {
        "id": "deposit-not-in-own-name",
        "walk_fixture": "offshore_retirement_bank_deposit.json",
        "ui": {"secondhome_own_name": "no"},
        "engine": {"secondhome.bank_deposit_in_own_name": False},
        "why": "same basis, conditioned on whose name holds the deposit",
    },
    {
        "id": "no-passive-income",
        "walk_fixture": "offshore_retirement_bank_deposit.json",
        "ui": {"secondhome_passive_income_usd": "0"},
        "engine": {"secondhome.passive_monthly_income_usd": 0},
        "why": "age is still the only named cause, yet at 55 the pack supports nothing",
    },
)


def supported_codes(actual: dict) -> list[str]:
    """The products the pack supports behind this door — empty when the door
    is shut (any state other than SUPPORTED_CANDIDATES carries no candidate)."""
    if actual["state"] != "SUPPORTED_CANDIDATES":
        return []
    return list(actual.get("candidates") or [])


def doors_for(overrides: dict) -> dict:
    """The three doors, replayed on one fact record."""
    doors = {}
    for purpose in PURPOSE_DOORS:
        variant = json.loads(json.dumps(overrides))
        variant["intent.purposes"] = {"status": "KNOWN", "value": [purpose]}
        doors[purpose] = supported_codes(
            gce._evaluate(variant, f"door::{purpose}", as_of=_AS_OF)["actual"]
        )
    variant = json.loads(json.dumps(overrides))
    variant["person.birth_date"] = {"status": "KNOWN", "value": AGE_55_BIRTH_DATE}
    doors["AGE_55"] = supported_codes(
        gce._evaluate(variant, "door::age55", as_of=_AS_OF)["actual"]
    )
    return doors


def counterexamples() -> list[dict]:
    rows = []
    for row in COUNTEREXAMPLES:
        overrides = json.loads(
            (CORPUS_DIR / row["walk_fixture"]).read_text(encoding="utf-8")
        )["overrides"]
        for path, value in row["engine"].items():
            overrides[path] = {"status": "KNOWN", "value": value}
        actual = gce._evaluate(overrides, row["id"], as_of=_AS_OF)["actual"]
        rows.append(
            {
                "id": row["id"],
                "walk_fixture": row["walk_fixture"],
                "why": row["why"],
                "ui": row["ui"],
                "state": actual["state"],
                "no_path_reason_codes": list(actual.get("no_path_reason_codes") or []),
                "doors": doors_for(overrides),
            }
        )
    return rows


def main() -> int:
    walks = []
    pack = None
    digest = hashlib.sha256()
    for path in sorted(CORPUS_DIR.glob("*.json")):
        raw = path.read_bytes()
        spec = json.loads(raw)
        label = str(spec["label"])
        base = gce._evaluate(spec["overrides"], label, as_of=_AS_OF)
        pack = base["pack"]
        actual = base["actual"]
        if actual["state"] == "SUPPORTED_CANDIDATES":
            continue
        digest.update(path.name.encode("utf-8"))
        digest.update(hashlib.sha256(raw).hexdigest().encode("utf-8"))
        doors = doors_for(spec["overrides"])
        walks.append(
            {
                "label": label,
                "walk_fixture": path.name,
                "state": actual["state"],
                "no_path_reason_codes": list(actual.get("no_path_reason_codes") or []),
                "missing_facts": list(actual.get("missing_facts") or []),
                "doors": doors,
            }
        )

    # Hand-rolled so each walk stays a readable 8 lines and each `doors` map
    # stays on ONE line: this file is evidence a human reads in review, and
    # 17 walks expanded key-per-line is 400 lines of noise.
    head = {
        "generator": "apps/mouth/scripts/visa-oracle/replay-no-path-doors.py",
        "pack": pack,
        "as_of": str(_AS_OF),
        "age_55_birth_date": AGE_55_BIRTH_DATE,
        "walk_corpus_fingerprint": digest.hexdigest(),
    }
    lines = ["{"]
    for key, value in head.items():
        lines.append(f"  {json.dumps(key)}: {json.dumps(value)},")
    lines.append('  "walks": [')
    for index, walk in enumerate(walks):
        tail = "" if index == len(walks) - 1 else ","
        lines.append("    {")
        lines.append(f'      "label": {json.dumps(walk["label"])},')
        lines.append(f'      "walk_fixture": {json.dumps(walk["walk_fixture"])},')
        lines.append(f'      "state": {json.dumps(walk["state"])},')
        lines.append(
            f'      "no_path_reason_codes": {json.dumps(walk["no_path_reason_codes"])},'
        )
        lines.append(f'      "missing_facts": {json.dumps(walk["missing_facts"])},')
        lines.append(f'      "doors": {json.dumps(walk["doors"])}')
        lines.append(f"    }}{tail}")
    lines.append("  ],")
    lines.append('  "counterexamples": [')
    rows = counterexamples()
    for index, row in enumerate(rows):
        tail = "" if index == len(rows) - 1 else ","
        lines.append("    {")
        lines.append(f'      "id": {json.dumps(row["id"])},')
        lines.append(f'      "walk_fixture": {json.dumps(row["walk_fixture"])},')
        lines.append(f'      "why": {json.dumps(row["why"])},')
        lines.append(f'      "ui": {json.dumps(row["ui"])},')
        lines.append(f'      "state": {json.dumps(row["state"])},')
        lines.append(
            f'      "no_path_reason_codes": {json.dumps(row["no_path_reason_codes"])},'
        )
        lines.append(f'      "doors": {json.dumps(row["doors"])}')
        lines.append(f"    }}{tail}")
    lines.append("  ]")
    lines.append("}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Hand it to the repo's own formatter: lint-staged reformats this file on
    # commit either way, and a generator whose output differs from what lands
    # in the tree makes every regeneration look like a change.
    prettier = REPO / "node_modules" / ".bin" / "prettier"
    if prettier.exists():
        subprocess.run([str(prettier), "--write", str(OUT)], check=True, cwd=REPO)
    print(f"{len(walks)} non-supported walks -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
