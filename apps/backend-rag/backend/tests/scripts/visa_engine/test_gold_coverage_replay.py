"""Offline unit coverage for the gold-coverage corpus replay CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import gold_coverage_replay as replay
from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR,
    select_highest_repository_pack,
)

# PINNED to the highest signed pack's own `signed_at`, never the wall clock:
# the selected pack's source_records carry a freshness_policy
# (MAX_AGE_SINCE_VERIFIED_AT) with as little as a 604800s (7-day) window, so
# calling `replay.main` without `--as-of` evaluates at `datetime.now(UTC)` —
# a clock bomb guaranteed to go stale exactly 7 days after the newest
# source's verified_at, with zero code change. It took the ENTIRE merge
# queue down on 2026-08-30 (verified_at 2026-08-23T10:44:48Z + 604800s =
# 2026-08-30T10:44:48Z); at that instant the engine correctly started
# returning HUMAN_REVIEW_REQUIRED — the engine was right, the wall-clock
# evaluation was the bug. `signed_at` (not `payload.created_at`) because
# `--as-of` also drives `verify_rule_pack`'s `observed_at`, which rejects a
# signature dated AFTER the observation instant — see
# gold_coverage_eval.py's `test_persona_gold_7_spouse_resolves_to_e31a_candidate`
# for the same anchor, used here so both CLIs' test suites derive the
# instant from the same field for the same reason.
_, _HIGHEST_SIGNED_PACK = select_highest_repository_pack(PACKS_DIR)
_AS_OF = _HIGHEST_SIGNED_PACK["protected"]["signed_at"]

#: The exact overrides of the canonical gold persona-7 ("adult spouse,
#: registered marriage, confirmed sponsor" — ``test_evaluator_gold.PERSONAS``
#: id=7), copied verbatim so this suite evaluates the same real-world shape
#: the corpus-authoring lane will actually author, not a synthetic stand-in.
_PERSONA_7_OVERRIDES: dict[str, dict[str, Any]] = {
    "intent.purposes": {"status": "KNOWN", "value": ["FAMILY"]},
    "family.relation_to_sponsor": {"status": "KNOWN", "value": "SPOUSE"},
    "family.sponsor_nationalities": {"status": "KNOWN", "value": ["ID"]},
    "family.marriage_registered": {"status": "KNOWN", "value": True},
    "family.sponsor_confirmed": {"status": "KNOWN", "value": True},
}


def _parse_json_stdout(raw: str) -> Any:
    """Parse the JSON payload out of captured stdout, defensively from the
    first ``{`` — this module imports ``gold_coverage_eval`` (itself
    importing ``gold_replay_driver``, which owns a module logger), so a
    future stray log line landing on stdout ahead of the payload must not
    break this suite.
    """
    idx = raw.find("{")
    assert idx != -1, f"no JSON object found in captured stdout: {raw!r}"
    return json.loads(raw[idx:])


def _write_persona(path: Path, **overrides: Any) -> Path:
    spec: dict[str, Any] = {
        "label": "persona-7-spouse",
        "product_code": "E31A",
        "expected_state": "SUPPORTED_CANDIDATES",
        "expected_candidates": ["E31A"],
        "overrides": _PERSONA_7_OVERRIDES,
    }
    spec.update(overrides)
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_empty_corpus_fails_closed_not_green(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A coverage gate that reports pass on zero personas is the
    exists-!=-armed cron-theater shape (cicatrix family #2) — an empty
    corpus directory must exit 1 and explain why, never exit 0.
    """
    exit_code = replay.main(["--corpus", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""  # no report JSON was ever produced
    assert "empty" in captured.err
    assert str(tmp_path) in captured.err


def test_persona_gold_7_spouse_single_persona_corpus_passes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Gold persona-7, evaluated through the full corpus-replay path.

    Measured live 2026-08-28 against ``rulepack-prod-013.signed.json``
    (sequence=13): the pack resolves this persona to candidates
    ``["C1", "E31A", "E31B", "E31D"]``. This corpus declares only
    ``E31A`` as required (mirrors ``gold_coverage_eval.py``'s own
    ``test_persona_gold_7_spouse_resolves_to_e31a_candidate``), so a
    future pack revision that adds/removes sibling E31 sub-products
    doesn't need this test rewritten.
    """
    _write_persona(tmp_path / "E31A.json")

    exit_code = replay.main(["--corpus", str(tmp_path), "--as-of", _AS_OF])

    assert exit_code == 0
    report = _parse_json_stdout(capsys.readouterr().out)
    assert report["report_schema_version"] == "1.0.0"
    assert report["pack"]["sequence"] >= 13
    assert report["summary"]["total"] == 1
    assert report["summary"]["passed"] == 1
    assert report["summary"]["failed"] == 0
    assert report["summary"]["products_covered"] == ["E31A"]

    row = report["personas"][0]
    assert row["pass"] is True
    assert row["state_matches"] is True
    assert row["expected_candidates"] == ["E31A"]
    assert row["candidates_missing"] == []
    assert row["actual"]["state"] == "SUPPORTED_CANDIDATES"
    assert "E31A" in row["actual"]["candidates"]


def test_persona_expecting_a_missing_candidate_fails_the_replay(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Same real overrides as gold persona-7, but declaring a product the
    pack never actually returns for this applicant — the replay must catch
    the mismatch, never rubber-stamp it.
    """
    _write_persona(
        tmp_path / "D12.json",
        product_code="D12",
        expected_candidates=["D12"],
    )

    exit_code = replay.main(["--corpus", str(tmp_path), "--as-of", _AS_OF])

    assert exit_code == 1
    report = _parse_json_stdout(capsys.readouterr().out)
    assert report["summary"]["total"] == 1
    assert report["summary"]["passed"] == 0
    assert report["summary"]["failed"] == 1
    assert report["summary"]["products_covered"] == []

    row = report["personas"][0]
    assert row["pass"] is False
    assert row["state_matches"] is True  # the state itself still matched
    assert row["candidates_missing"] == ["D12"]
