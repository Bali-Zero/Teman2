"""Thin wiring tests for the G-b replay evidence artifact
(``gold_replay.build_report`` + ``scripts/visa_gold_replay.py``).

The heavy assertion — every one of the 20 canonical personas replaying
through the real evaluator with its exact expected outcome — already lives
in ``test_evaluator_gold.py``. This file asserts only what the ARTIFACT
itself must guarantee for the gate's independent-grader flow:

1. the report agrees with the canonical suite (zero divergences, all 20
   personas pass) when computed independently of pytest;
2. it is byte-deterministic (same fixed ``generated_at`` -> byte-identical
   JSON; different ``generated_at`` -> difference confined to that one key);
3. the CLI runs in-process, exits 0, and the file it writes parses back to
   the same zero-divergence report;
4. a pinned fixed-seed option matrix replays four fact permutations in each
   of three legal branches against the highest signed production pack.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from types import ModuleType
from typing import Any

from backend.scripts.visa_engine import gold_coverage_eval
from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR,
    _parse_utc,
    select_highest_repository_pack,
)
from backend.tests.services.visa_engine import gold_replay

_FIXED_NOW = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc)
_OTHER_NOW = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)

_SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "visa_gold_replay.py"
_MATRIX_PATH = Path(__file__).resolve().parent / "gold_coverage" / "fixtures" / "option_matrix.json"
_, _MATRIX_PACK = select_highest_repository_pack(PACKS_DIR)
_MATRIX_AS_OF = _parse_utc(_MATRIX_PACK["protected"]["signed_at"])


def _serialize(report: dict) -> str:
    """Exactly the CLI's own serialization (sorted keys, trailing newline)."""
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def _load_cli_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("visa_gold_replay_cli", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _matrix_key(values: tuple[Any, ...]) -> str:
    return "|".join(json.dumps(value, separators=(",", ":")) for value in values)


def _matrix_report() -> dict[str, Any]:
    """Replay the pinned option matrix in a fixed-seed order."""
    artifact = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))
    seed = int(artifact["seed"])
    cases: list[dict[str, Any]] = []
    pack: dict[str, Any] = {}

    for branch in artifact["branches"]:
        axes = branch["axes"]
        combinations = list(product(*(axis["values"] for axis in axes)))
        assert len(combinations) == 4, branch["id"]
        assert set(branch["expectations"]) == {_matrix_key(values) for values in combinations}
        for values in combinations:
            case_key = _matrix_key(values)
            raw_overrides = dict(branch["base_overrides"])
            raw_overrides.update(
                {axis["fact"]: value for axis, value in zip(axes, values, strict=True)}
            )
            overrides = {
                fact: {"status": "KNOWN", "value": value}
                for fact, value in raw_overrides.items()
            }
            result = gold_coverage_eval._evaluate(
                overrides,
                f"{branch['id']}:{case_key}",
                as_of=_MATRIX_AS_OF,
            )
            pack = result["pack"]
            actual = {
                "state": result["actual"]["state"],
                "candidates": result["actual"]["candidates"],
            }
            expected = branch["expectations"][case_key]
            cases.append(
                {
                    "branch": branch["id"],
                    "case": case_key,
                    "legal_citations": branch["legal_citations"],
                    "expected": expected,
                    "actual": actual,
                    "pass": actual == expected,
                }
            )

    cases.sort(
        key=lambda case: hashlib.sha256(
            f"{seed}:{case['branch']}:{case['case']}".encode()
        ).hexdigest()
    )
    passed = sum(case["pass"] for case in cases)
    return {
        "schema_version": artifact["schema_version"],
        "seed": seed,
        "pack": pack,
        "cases": cases,
        "summary": {"total": len(cases), "passed": passed, "failed": len(cases) - passed},
    }


def test_report_has_zero_divergences() -> None:
    report = gold_replay.build_report(generated_at=_FIXED_NOW)
    assert report["overall_pass"] is True
    assert report["divergences"] == []
    assert report["summary"] == {
        "personas_total": 20,
        "personas_pass": 20,
        "personas_with_divergence": 0,
        "divergence_count": 0,
    }
    assert len(report["personas"]) == 20
    for persona in report["personas"]:
        assert persona["pass"] is True
        assert persona["expected"] == persona["actual"]


def test_report_is_byte_deterministic_for_a_fixed_generated_at() -> None:
    first = _serialize(gold_replay.build_report(generated_at=_FIXED_NOW))
    second = _serialize(gold_replay.build_report(generated_at=_FIXED_NOW))
    assert first == second


def test_generated_at_is_the_only_run_varying_field() -> None:
    first = gold_replay.build_report(generated_at=_FIXED_NOW)
    second = gold_replay.build_report(generated_at=_OTHER_NOW)
    assert first != second  # the timestamps themselves differ
    assert {**first, "generated_at": None} == {**second, "generated_at": None}


def test_cli_in_process_writes_a_zero_divergence_artifact(tmp_path: Path) -> None:
    cli = _load_cli_module()
    out = tmp_path / "gold-replay.json"
    exit_code = cli.main(["--out", str(out), "--fixed-now", _FIXED_NOW.isoformat()])
    assert exit_code == 0

    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["overall_pass"] is True
    assert artifact["divergences"] == []
    assert artifact["persona_count"] == 20
    assert artifact["engine"]["combined_sha256"]
    assert len(artifact["engine"]["modules"]) == 7
    assert artifact["pack"]["payload_computed_sha256"]
    assert artifact["generated_at"] == _FIXED_NOW.isoformat()


def test_cli_artifact_is_reproducible_across_runs(tmp_path: Path) -> None:
    cli = _load_cli_module()
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    argv = ["--fixed-now", _FIXED_NOW.isoformat()]
    assert cli.main([*argv, "--out", str(out_a)]) == 0
    assert cli.main([*argv, "--out", str(out_b)]) == 0
    assert out_a.read_bytes() == out_b.read_bytes()


def test_option_matrix_is_bounded_and_legally_anchored() -> None:
    artifact = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))
    assert artifact["seed"] == 9062026
    assert len(artifact["branches"]) == 3
    for branch in artifact["branches"]:
        assert len(branch["axes"]) == 2
        assert all(len(axis["values"]) == 2 for axis in branch["axes"])
        assert len(branch["expectations"]) == 4
        assert branch["legal_citations"]


def test_option_matrix_replay_matches_all_twelve_pinned_cases() -> None:
    report = _matrix_report()
    assert report["summary"] == {"total": 12, "passed": 12, "failed": 0}, [
        case for case in report["cases"] if not case["pass"]
    ]


def test_option_matrix_report_is_byte_identical_across_two_runs(tmp_path: Path) -> None:
    out_a = tmp_path / "matrix-a.json"
    out_b = tmp_path / "matrix-b.json"
    out_a.write_text(_serialize(_matrix_report()), encoding="utf-8")
    out_b.write_text(_serialize(_matrix_report()), encoding="utf-8")
    assert out_a.read_bytes() == out_b.read_bytes()
