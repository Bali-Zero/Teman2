#!/usr/bin/env python3
"""observe_visa_oracle_replay_pins.py — bites: observation for the no-door replay and E33G copy pins.

# bites-observable — this script takes NO arguments: the program it runs and the
# test files it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle result page under the active signed pack.
The observation first regenerates the replay from the highest signed pack into a temp file
and requires it to equal the committed fixture, then runs the no-path-doors replay test and the engine-adapter test
from `apps/mouth` and requires every test to pass, and the walks that carry the
E33G income-threshold sentence (remote persona at foreign income 59,999) to be
reported as run. Exit 0 only on a full pass.
"""

# bites-observable — no arguments; one literal program, two literal test files.

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
LIB = "src/app/(visa-oracle)/visa-oracle/_lib/"
TEST_FILES = (LIB + "no-path-doors.test.tsx", LIB + "engine-adapter.test.ts")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
# The exact census of the two files: a lost test is a red observer, not a quiet drop.
EXPECTED_TESTS = 252
REPLAY = (
    MOUTH_DIR / "src" / "app" / "(visa-oracle)" / "visa-oracle" / "_lib" / "fixtures" / "no-path-doors.replay.json"
)
GENERATOR = MOUTH_DIR / "scripts" / "visa-oracle" / "replay-no-path-doors.py"
PACKS_DIR = REPO_ROOT / "apps" / "backend-rag" / "backend" / "services" / "visa_engine" / "contracts" / "packs"
REQUIRED_TESTS = (
    "covers the 17 dead ends, 3 held walks and 1 missing-input walk the current census reports",
    "names a door the pack actually supports: offshore/remote/foreign_only/income_59999",
    "states every cause in words, EN and ID: offshore/remote/foreign_only/income_59999",
    "pins the E33G income-threshold sentence in EN and ID, figure and yearly unit included: offshore/remote/foreign_only/income_59999",
)
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None, expected: int = EXPECTED_TESTS) -> bool:
    """True only for a Vitest line that is exactly `Tests  N passed (N)` with N == expected."""
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed == expected


def missing_tests(out: str, required: tuple[str, ...] = REQUIRED_TESTS) -> list[str]:
    """Required test titles absent from a passing (checkmark) verbose line."""
    passed = [l for l in out.splitlines() if "✓" in l or "✔" in l]
    return [t for t in required if not any(t in l for l in passed)]


def highest_signed_pack(packs_dir: Path = PACKS_DIR) -> str:
    """File name of the highest-sequence `rulepack-prod-NNN.signed.json` on disk."""
    names = sorted(p.name for p in packs_dir.glob("rulepack-prod-*.signed.json"))
    if not names:
        raise FileNotFoundError(f"no signed production pack in {packs_dir}")
    return names[-1]


def replay_drift(committed: dict, regenerated: dict, active_pack: str) -> list[str]:
    """Reasons the committed replay is not the regeneration against the active pack."""
    reasons = []
    if regenerated.get("pack", {}).get("file") != active_pack:
        reasons.append(f"regeneration measured {regenerated.get('pack')}, active pack is {active_pack}")
    if committed.get("pack") != regenerated.get("pack"):
        reasons.append("pack file/sequence/version differ from the regeneration")
    if committed != regenerated:
        reasons.append("committed replay differs from a fresh regeneration against the active pack")
    return reasons


def _python_candidates() -> list[str]:
    venv = Path("apps") / "backend-rag" / ".venv" / "bin" / "python"
    found = [REPO_ROOT / venv]
    if REPO_ROOT.parent.name == ".worktrees":
        found.append(REPO_ROOT.parent.parent / venv)
    return [str(c) for c in found if c.exists()] + [sys.executable]


def regenerate_replay() -> dict:
    """Run the generator against the active signed pack into a temp file and load it."""
    env = dict(os.environ)
    # Placeholders the backend settings import insists on; not credentials, nothing is reached.
    env.setdefault("API_KEYS", "observer-placeholder")
    env.setdefault("JWT_SECRET_KEY", "observer-placeholder-not-a-secret-0123456789")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "replay.json"
        result = subprocess.run(
            [_python_candidates()[0], str(GENERATOR), "--out", str(out)],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not out.exists():
            raise RuntimeError(f"generator exited {result.returncode}: {result.stderr[-800:]}")
        return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    result = subprocess.run(
        ["npx", "vitest", "run", "--reporter=verbose", *TEST_FILES],
        cwd=MOUTH_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    out = ANSI.sub("", result.stdout + result.stderr)
    tests = re.search(r"^\s*Tests\s.*$", out, re.MULTILINE)
    line = tests.group(0) if tests else None
    summary = line.strip() if line else "no Vitest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_visa_oracle_replay_pins: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    try:
        drift = replay_drift(
            json.loads(REPLAY.read_text(encoding="utf-8")), regenerate_replay(), highest_signed_pack()
        )
    except (OSError, RuntimeError, ValueError) as error:
        drift = [f"regeneration could not run: {error}"]
    if drift:
        print(f"observe_visa_oracle_replay_pins: FAILED (replay drift: {drift})")
        return 1
    absent = missing_tests(out)
    if absent:
        print(f"observe_visa_oracle_replay_pins: FAILED (required tests absent: {absent})")
        return 1
    print(f"observe_visa_oracle_replay_pins: {summary}")
    print("observe_visa_oracle_replay_pins: replay pins hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
