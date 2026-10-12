#!/usr/bin/env python3
"""observe_visa_oracle_e33_deposit_reason.py — bites: observation for the Second Home deposit reason.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page. The observation runs the
engine-adapter test file from `apps/mouth` and requires every test in it to pass:
a second_home / invest deposit of USD 130,000 or more that is not at a state bank
or not in the visitor's own name gets its own fact-derived reason (EN and ID),
while retirement walks and below-threshold deposits keep their existing copy.
It also renders the result sheet (OutcomeSheet test file) and replays the SIGNED
rule pack on second_home and invest walks at exactly USD 130,000 (and 129,999),
both age sides and every state-bank / own-name variant, so the reason codes the
adapter relies on are measured, not assumed.
Exit 0 only if Vitest reports each file passed with zero failures and the replay holds.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


MIN_TESTS = 100
SHEET_TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.e33-deposit-reason.test.tsx"
SHEET_MIN_TESTS = 4
BACKEND_DIR = REPO_ROOT / "apps" / "backend-rag"
# Titles of the tests that prove this change; each must be reported as run, so
# deleting one cannot hide behind the file total staying above MIN_TESTS.
REQUIRED_TESTS = (
    "pins the 130,000 figure to the pack's deposit-basis threshold",
    "state bank = no replaces the age sentence",
    "own name = no",
    "both answers = no",
    "is named as not sure, never as a told no",
    "the invest deposit route is covered too",
    "innocence: retirement walks keep the age sentence",
    "innocence: a deposit below the threshold keeps the existing copy",
    "innocence: both answers yes, a skipped answer",
)


SHEET_REQUIRED_TESTS = (
    "shows the holder sentence (EN)",
    "shows the Indonesian sentence in ID",
)


def missing_tests(out: str, required: tuple[str, ...] = REQUIRED_TESTS) -> list[str]:
    """Required test titles absent from a passing (checkmark) verbose line."""
    passed = [l for l in out.splitlines() if "\u2713" in l or "\u2714" in l]
    return [t for t in required if not any(t in l for l in passed)]
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None, minimum: int = MIN_TESTS) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)`, N >= minimum.

    Anything else (skipped, todo, failed, a reduced count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed >= minimum


REPLAY = r"""
import json, itertools
from backend.scripts.visa_engine import gold_coverage_eval as gce
from backend.tests.services.visa_engine.test_interview_walk_census import _AS_OF, CORPUS_DIR

AGE, OPS = "AGE_BELOW_55", "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES"
rows = 0
for fx in ("offshore_second_home_bank_deposit.json", "offshore_invest_bank_deposit.json"):
    base = json.loads((CORPUS_DIR / fx).read_text())["overrides"]
    for birth, code in (("2000-11-11", AGE), ("1961-11-11", OPS)):
        for deposit in (130000, 129999):
            for bank, name in itertools.product((True, False), (True, False)):
                o = json.loads(json.dumps(base))
                o["secondhome.bank_deposit_usd"] = {"status": "KNOWN", "value": deposit}
                o["secondhome.bank_deposit_at_state_bank"] = {"status": "KNOWN", "value": bank}
                o["secondhome.bank_deposit_in_own_name"] = {"status": "KNOWN", "value": name}
                o["person.birth_date"] = {"status": "KNOWN", "value": birth}
                a = gce._evaluate(o, "e33", as_of=_AS_OF)["actual"]
                tag = (fx, birth, deposit, bank, name)
                if deposit == 130000 and bank and name:
                    assert a["state"] == "SUPPORTED_CANDIDATES" and a["candidates"] == ["E33"], tag
                elif deposit == 130000:
                    assert a["state"] == "NO_SUPPORTED_PATH", tag
                    assert a["no_path_reason_codes"] == [code], (tag, a["no_path_reason_codes"])
                else:
                    assert a["state"] != "NO_SUPPORTED_PATH", tag
                rows += 1
print(rows)
"""


def run_vitest(test_file: str, minimum: int, required: tuple[str, ...], label: str) -> int:
    result = subprocess.run(
        ["npx", "vitest", "run", "--reporter=verbose", test_file],
        cwd=MOUTH_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    out = ANSI.sub("", result.stdout + result.stderr)
    tests = re.search(r"^\s*Tests\s.*$", out, re.MULTILINE)
    line = tests.group(0) if tests else None
    summary = line.strip() if line else "no Vitest summary"
    if result.returncode != 0 or not summary_ok(line, minimum):
        print(f"observe_visa_oracle_e33_deposit_reason: FAILED {label} ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    absent = missing_tests(out, required)
    if absent:
        print(f"observe_visa_oracle_e33_deposit_reason: FAILED {label} (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_e33_deposit_reason: {label} {summary}")
    return 0


def _backend_python() -> str:
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.is_file() else sys.executable


def main() -> int:
    code = run_vitest(TEST_FILE, MIN_TESTS, REQUIRED_TESTS, "adapter")
    if code:
        return code
    code = run_vitest(SHEET_TEST_FILE, SHEET_MIN_TESTS, SHEET_REQUIRED_TESTS, "sheet")
    if code:
        return code
    replay = subprocess.run(
        [_backend_python(), "-c", REPLAY],
        cwd=BACKEND_DIR,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )
    if replay.returncode != 0:
        print(f"observe_visa_oracle_e33_deposit_reason: FAILED pack replay\n{replay.stderr[-1500:]}")
        return replay.returncode
    print(f"observe_visa_oracle_e33_deposit_reason: pack replay {replay.stdout.strip()} walks hold")
    print("observe_visa_oracle_e33_deposit_reason: e33 deposit reason holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
