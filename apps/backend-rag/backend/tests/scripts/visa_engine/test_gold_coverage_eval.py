"""Offline unit coverage for the gold-coverage single-persona evaluator CLI."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import gold_coverage_eval as gce

#: Every ``FactPath``/baseline key this CLI ever emits is a two-segment
#: dotted lower_snake_case string (e.g. ``person.birth_date``) — the CLI's
#: own docstring examples use this shape throughout.
_DOTTED_PATH_RE = re.compile(r"^[a-z_]+\.[a-z_]+$")


def _parse_json_stdout(raw: str) -> Any:
    """Parse the JSON payload out of captured stdout.

    ``gold_coverage_eval.py`` never imports ``logging`` itself and always
    writes its JSON as the first thing on stdout, but it imports
    ``gold_replay_driver`` (which owns a module logger) — be defensive
    against a future stray log line landing on stdout ahead of the payload
    by parsing from the first ``{`` or ``[``, exactly as the task brief for
    this suite asks.
    """
    candidates = [idx for idx in (raw.find("{"), raw.find("[")) if idx != -1]
    assert candidates, f"no JSON object/array found in captured stdout: {raw!r}"
    return json.loads(raw[min(candidates) :])


def test_dump_registry_lists_every_known_fact_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = gce.main(["--dump-registry"])

    assert exit_code == 0
    rows = _parse_json_stdout(capsys.readouterr().out)
    assert isinstance(rows, list)
    assert len(rows) >= 44

    paths = [row["path"] for row in rows]
    for path in paths:
        assert isinstance(path, str)
        assert _DOTTED_PATH_RE.match(path), f"non dotted-lowercase FactPath: {path!r}"
    assert "person.birth_date" in paths
    assert "intent.purposes" in paths


def test_dump_baseline_returns_dotted_paths_with_known_or_unknown_status(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = gce.main(["--dump-baseline"])

    assert exit_code == 0
    baseline = _parse_json_stdout(capsys.readouterr().out)
    assert isinstance(baseline, dict)
    assert baseline, "baseline must not be empty"

    for path, entry in baseline.items():
        assert _DOTTED_PATH_RE.match(path), f"non dotted-lowercase FactPath key: {path!r}"
        assert isinstance(entry, dict)
        assert entry.get("status") in {"KNOWN", "UNKNOWN"}


def test_persona_gold_7_spouse_resolves_to_e31a_candidate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Gold persona-7 (adult spouse, registered marriage, confirmed sponsor).

    Overrides mirror ``test_evaluator_gold.PERSONAS[6]`` (id=7) verbatim.
    Measured live 2026-08-28 against ``rulepack-prod-013.signed.json``
    (sequence=13): the pack resolves this persona to candidates
    ``["C1", "E31A", "E31B", "E31D"]`` — this test asserts only that
    ``E31A`` is present and the state matches, per the task brief, so a
    future pack revision that adds/removes sibling E31 sub-products
    doesn't need this test rewritten.
    """
    persona_path = tmp_path / "persona-7.json"
    persona_path.write_text(
        json.dumps(
            {
                "label": "persona-7-spouse",
                "overrides": {
                    "intent.purposes": {"status": "KNOWN", "value": ["FAMILY"]},
                    "family.relation_to_sponsor": {"status": "KNOWN", "value": "SPOUSE"},
                    "family.sponsor_nationalities": {"status": "KNOWN", "value": ["ID"]},
                    "family.marriage_registered": {"status": "KNOWN", "value": True},
                    "family.sponsor_confirmed": {"status": "KNOWN", "value": True},
                },
                "expected_state": "SUPPORTED_CANDIDATES",
                "expected_candidates": ["E31A"],
            }
        ),
        encoding="utf-8",
    )

    exit_code = gce.main(["--persona", str(persona_path)])

    assert exit_code == 0
    out = _parse_json_stdout(capsys.readouterr().out)
    assert out["actual"]["state"] == "SUPPORTED_CANDIDATES"
    assert "E31A" in out["actual"]["candidates"]
    assert out["state_matches"] is True
    assert out["candidates_missing"] == []
    assert out["pack"]["sequence"] >= 13


def test_persona_overrides_must_be_an_object(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    persona_path = tmp_path / "bad-overrides.json"
    persona_path.write_text(
        json.dumps({"label": "bad-overrides", "overrides": ["not", "an", "object"]}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        gce.main(["--persona", str(persona_path)])

    assert exc_info.value.code == 2
    assert "overrides" in capsys.readouterr().err


def test_main_requires_a_mode_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        gce.main([])

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "--dump-baseline" in stderr
    assert "--dump-registry" in stderr
