"""The rebind tool must carry explanations the DRIVER will actually match, and
must refuse — loudly — any whose divergence moved.

Both halves come from live failures on 2026-08-26:

* the first draft stamped each persona with the TOP-LEVEL pack block (one key
  wider than the per-persona one). `_matching_explanation` compares that block
  by exact dict equality, so every explanation was dropped SILENTLY and the
  regenerated gate read `explained 0` — indistinguishable from a real
  detachment. `test_a_rebound_report_is_actually_matched_by_the_driver` is the
  end-to-end tripwire: it asserts the driver MATCHES, never that the rebind
  script merely claims to have carried something.
* carrying an explanation whose divergence changed would re-attach a human
  judgement to something that no longer happens.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from backend.scripts.visa_engine.gold_replay_driver import (
    _load_accepted_explanations,
    _matching_explanation,
)
from backend.scripts.visa_engine.rebind_accepted_explanations import RebindError, rebind


def _persona(pid: int, *, explanation: str | None, state: str = "NEEDS_INPUT") -> dict[str, Any]:
    return {
        "persona_id": pid,
        "label": f"persona-{pid}",
        "divergence": True,
        "expected": {"state": "SUPPORTED_CANDIDATES"},
        "actual": {"state": state},
        "differences": [{"field": "state", "expected": "SUPPORTED_CANDIDATES", "actual": state}],
        "explanation": explanation,
        "pack": {
            "payload_sha256": "b" * 64,
            "rule_pack_id": "11111111-1111-5111-8111-111111111111",
            "sequence": 16,
            "version": "2026.8.26",
        },
    }


def _accepted() -> dict[str, Any]:
    old = _persona(1, explanation="CLASS 2 — a later safety rule firing, not a defect.")
    old["pack"] = {**old["pack"], "payload_sha256": "a" * 64, "sequence": 15}
    return {"pack": {**old["pack"], "consistent_across_personas": True}, "personas": [old]}


def _report() -> dict[str, Any]:
    fresh = _persona(1, explanation=None)
    return {
        "pack": {**fresh["pack"], "consistent_across_personas": True},
        "personas": [fresh],
    }


def test_a_rebound_report_is_actually_matched_by_the_driver(tmp_path) -> None:
    """The property that matters end to end: after rebinding, the DRIVER's own
    matcher returns the explanation. Asserting only that `rebind` reported a
    carry is what let the silent-drop bug through."""
    report = _report()
    # What a FRESH replay produces — captured BEFORE rebinding. The driver
    # compares against this, not against whatever the rebind wrote. Reading
    # these back out of `rebound` instead is what made an earlier version of
    # this test compare the generator's output with itself: it stayed green
    # while the silent-drop bug was present.
    fresh = copy.deepcopy(report["personas"][0])

    rebound = rebind(_accepted(), report)
    path = tmp_path / "rebound.json"
    path.write_text(json.dumps(rebound), encoding="utf-8")
    loaded = _load_accepted_explanations(path)

    matched = _matching_explanation(
        loaded,
        persona_id=fresh["persona_id"],
        expected=fresh["expected"],
        actual=fresh["actual"],
        pack=fresh["pack"],
        differences=fresh["differences"],
    )
    assert matched == "CLASS 2 — a later safety rule firing, not a defect."


def test_the_per_persona_pack_block_is_left_exactly_as_the_report_wrote_it() -> None:
    """The regression that caused the silent drop: never overwrite the row's
    pack block with the top-level one (which carries an extra key)."""
    report = _report()
    expected_block = copy.deepcopy(report["personas"][0]["pack"])
    rebound = rebind(_accepted(), report)

    assert rebound["personas"][0]["pack"] == expected_block
    assert "consistent_across_personas" not in rebound["personas"][0]["pack"]


@pytest.mark.parametrize(
    "field, mutate",
    [
        ("actual", lambda p: p["actual"].__setitem__("state", "NO_SUPPORTED_PATH")),
        ("expected", lambda p: p["expected"].__setitem__("state", "HUMAN_REVIEW_REQUIRED")),
        ("differences", lambda p: p["differences"].clear()),
        ("divergence", lambda p: p.__setitem__("divergence", False)),
    ],
)
def test_an_explanation_whose_divergence_moved_is_refused(field, mutate) -> None:
    report = _report()
    mutate(report["personas"][0])
    with pytest.raises(RebindError, match=field):
        rebind(_accepted(), report)


def test_a_report_without_a_pack_block_is_refused() -> None:
    report = _report()
    del report["pack"]
    with pytest.raises(RebindError, match="pack"):
        rebind(_accepted(), report)
