"""test_contract_replay.py — the table in scripts/ci/contract_checks.yml is pinned
to what CI actually judged on the eight heads closed unmerged in #6633..#6682.

Three arms:
  1. --selftest (offline): loader guilt+innocence, matcher, classifier matrix.
  2. fixture ↔ table parity (offline): every `killed:` PR is pinned; every
     pinned verdict names a context the table knows.
  3. --replay --expect over the pinned heads (needs the commits — present on
     any clone that fetches refs/pull/N/head; contract_verify fetches on demand):
     RED on #6664/#6665/#6670/#6676/#6655, GREEN on the cures #6666/#6667,
     NOT-LOCALLY-PREVENTABLE on #6673. A mismatch is a table that drifted.

Arm 3 is FAILED, not skipped, when the heads cannot be obtained — a skip is a
green nobody consumes. Set CONTRACT_REPLAY_OFFLINE=1 to opt out EXPLICITLY.
Runs under the nightly scripts/tests sweep; run locally with
    python3 -m pytest scripts/tests/test_contract_replay.py -q
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "contract_verify.py"
TABLE = ROOT / "scripts" / "ci" / "contract_checks.yml"
FIXTURE = ROOT / "scripts" / "tests" / "fixtures" / "contract_replay_expected.yml"


def _run(*args: str, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=timeout)


def test_selftest_passes():
    p = _run("--selftest")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "0 failure(s)" in p.stdout


def test_fixture_and_table_agree():
    table = yaml.safe_load(TABLE.read_text(encoding="utf-8"))
    fixture = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    contexts = {row["context"] for row in table["contexts"]}
    killed = {int(n) for row in table["contexts"] for n in (row.get("killed") or [])}
    heads = {int(k): v for k, v in fixture["heads"].items()}
    assert killed <= set(heads), f"killed PRs not pinned in the fixture: {sorted(killed - set(heads))}"
    for pr, head in heads.items():
        assert len(head["sha"]) == 40, f"#{pr}: sha must be the full 40-char head sha"
        unknown = set(head["expect"]) - contexts
        assert not unknown, f"#{pr}: fixture names contexts the table does not know: {sorted(unknown)}"
        for ctx, verdict in head["expect"].items():
            assert verdict in {"RED", "GREEN", "NOT-LOCALLY-PREVENTABLE"}, f"#{pr}/{ctx}: {verdict}"
    # the four paid successors the preflight would have prevented, and the honest one it could not
    assert heads[6664]["expect"]["R1 gate — adversarial review present"] == "RED"
    assert heads[6665]["expect"]["R1 gate — adversarial review present"] == "RED"
    assert heads[6666]["expect"]["R1 gate — adversarial review present"] == "GREEN"
    assert heads[6667]["expect"]["R1 gate — adversarial review present"] == "GREEN"
    assert heads[6673]["expect"]["Harness floor recompute"] == "NOT-LOCALLY-PREVENTABLE"


def test_replay_reproduces_the_pinned_verdicts():
    if os.environ.get("CONTRACT_REPLAY_OFFLINE") == "1":
        pytest.skip("CONTRACT_REPLAY_OFFLINE=1 — replay opted out explicitly")
    p = _run("--replay", "--expect", str(FIXTURE))
    assert p.returncode == 0, "replay verdicts differ from the fixture (or a head was unreachable):\n" + p.stdout + p.stderr
    assert "MISMATCH" not in p.stdout
    assert p.stdout.rstrip().endswith("verdict(s) differ from " + str(FIXTURE)) and " 0 verdict(s) differ" in p.stdout
