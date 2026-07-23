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
   the same zero-divergence report.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

from backend.tests.services.visa_engine import gold_replay

_FIXED_NOW = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc)
_OTHER_NOW = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)

_SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "visa_gold_replay.py"


def _serialize(report: dict) -> str:
    """Exactly the CLI's own serialization (sorted keys, trailing newline)."""
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def _load_cli_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("visa_gold_replay_cli", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
