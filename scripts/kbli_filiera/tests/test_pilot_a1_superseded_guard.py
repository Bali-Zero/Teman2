"""Contract tests for infra/workflows/kbli-pilot-a1.js's SUPERSEDED entry guard.

The JS Workflow script has no Python test runner, so — following the pattern established by
test_lot_runner_contract.py — these tests parse it as TEXT (regex/substring over the source).

Background (2026-07-18 conductor finding, see kbli-batch-a-lot.js's own "D5 BLIND-REFUTATION FIX"
comment): kbli-pilot-a1.js's D5 refutation seat is NOT blind — its d5Prompt(code, d1Result)
embeds D1's own proposal (`JSON.stringify(d1Result)`) directly in the refuter's prompt, so the
"re-derive BEFORE reading the proposal" instruction is anchoring theater, not an independent
verification. This was fixed in the successor runner, infra/workflows/kbli-batch-a-lot.js (blind
d5Prompt(code) + deterministic diffD1D5() compiler) — the pilot's own d5Prompt is intentionally
left unfixed (out of scope: porting the blind architecture into the pilot would obscure the
historical record of what was actually run). Instead the pilot script is marked SUPERSEDED and
gets a hard entry guard (args.allowAnchoredPilot) so it cannot be re-dispatched for a new run and
mistaken for a valid calibration baseline. Plan reference: research/operations/2026-07-18-kbli-
batch-a-plan.md §8 amendment A-4 (m1 BREACH on Lot 1 root-caused to this exact defect class).

1. GUILT: the pilot file must contain both the `allowAnchoredPilot` guard AND a SUPERSEDED marker
   — a regression here means the pilot could be re-run silently with anchored-refuter numbers
   passed off as a fresh baseline.
2. INNOCENCE: the live batch runner (kbli-batch-a-lot.js) must NEVER contain `allowAnchoredPilot`
   — proves the guard is scoped to the superseded pilot only and never leaks into the calibration-
   enforced runner that Batch A lots actually dispatch (cicatrix family #3 discipline: a guard/
   exemption needs both a guilt and an innocence test, never one alone).
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PILOT_JS = REPO_ROOT / "infra/workflows/kbli-pilot-a1.js"
LOT_RUNNER_JS = REPO_ROOT / "infra/workflows/kbli-batch-a-lot.js"


@pytest.fixture(scope="module")
def pilot_source() -> str:
    assert PILOT_JS.exists(), f"pilot script not found at {PILOT_JS}"
    return PILOT_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def lot_runner_source() -> str:
    assert LOT_RUNNER_JS.exists(), f"lot runner not found at {LOT_RUNNER_JS}"
    return LOT_RUNNER_JS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. GUILT — the pilot must be marked SUPERSEDED and hard-guarded
# ---------------------------------------------------------------------------

def test_guilt_pilot_has_superseded_marker(pilot_source: str) -> None:
    assert "SUPERSEDED" in pilot_source, (
        "kbli-pilot-a1.js is missing its SUPERSEDED marker — the header comment warning that its "
        "D5 seat is anchored and its m1 baseline is invalid must be present"
    )
    assert "kbli-batch-a-lot.js" in pilot_source, (
        "the SUPERSEDED header must point to the successor runner, infra/workflows/kbli-batch-a-lot.js"
    )


def test_guilt_pilot_has_allow_anchored_pilot_guard(pilot_source: str) -> None:
    assert "allowAnchoredPilot" in pilot_source, (
        "kbli-pilot-a1.js is missing the args.allowAnchoredPilot entry guard — without it the "
        "script can be dispatched for a fresh run whose anchored-refuter numbers could be mistaken "
        "for a valid calibration baseline"
    )
    assert "A.allowAnchoredPilot !== true" in pilot_source, (
        "the guard must default-refuse (only proceed when allowAnchoredPilot is explicitly true) — "
        "an inverted or missing condition would defeat the guard entirely"
    )
    assert "throw new Error" in pilot_source


def test_guilt_pilot_guard_precedes_evidence_root_parse(pilot_source: str) -> None:
    """The guard must fire BEFORE the script does any other work — otherwise a caller could hit a
    different error first and never see the SUPERSEDED message."""
    guard_pos = pilot_source.index("A.allowAnchoredPilot !== true")
    evidence_root_pos = pilot_source.index("const evidenceRoot = A.evidenceRoot;")
    assert guard_pos < evidence_root_pos, (
        "the allowAnchoredPilot guard must be positioned before the evidenceRoot parse, right "
        "after args are parsed, so it is the first thing a caller hits"
    )


# ---------------------------------------------------------------------------
# 2. INNOCENCE — the guard must never leak into the live batch runner
# ---------------------------------------------------------------------------

def test_innocence_lot_runner_has_no_allow_anchored_pilot_guard(lot_runner_source: str) -> None:
    assert "allowAnchoredPilot" not in lot_runner_source, (
        "infra/workflows/kbli-batch-a-lot.js must NEVER contain allowAnchoredPilot — that guard "
        "belongs only to the superseded pilot; its presence here would mean the anchored-pilot "
        "escape hatch leaked into the calibration-enforced runner Batch A lots actually dispatch"
    )


def test_innocence_lot_runner_has_no_superseded_marker(lot_runner_source: str) -> None:
    """The live runner is the CURRENT method, not superseded — it must not carry the pilot's
    SUPERSEDED marker (would be a copy-paste leak of the header block itself)."""
    assert "SUPERSEDED" not in lot_runner_source
