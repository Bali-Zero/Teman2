"""Contract tests for infra/workflows/kbli-batch-a-lot.js — the JS Workflow script itself has no
Python test runner, so these tests parse it as TEXT (regex over the source) and assert three
things that are load-bearing per research/operations/2026-07-18-kbli-batch-a-plan.md §5 and the
pilot-report criterion-#6 fix:

1. The pinned m1/m2/m4 calibration numeric literals in the .js match
   data/kbli-filiera/batch-reports/batchA-calibration.json byte-for-byte (drift guard — the .js
   comment explicitly says these are PINNED LITERALS, never re-derived at runtime, so nothing
   short of a text-level check catches them drifting apart from the calibration artifact).
2. The frozen verdict taxonomy (certified | quarantined | abstained) is the ONLY vocabulary the
   script ever emits as a verdict value — `boring_as_expected` (the pilot's 4th-token deviation,
   pilot-report criterion #6) may appear ONLY inside a comment explaining the normalization, never
   as a live enum/string literal a seat could emit.
3. The three plan §8 amendment A-1 out-of-scope facets (pma_status, l4_bali, TKA) are named in the
   seat prompts as out-of-scope this pass.

The calibration artifact (data/kbli-filiera/batch-reports/batchA-calibration.json) ships on a
separate PR (agent/air-m5/kbli/batcha-calibration) — test 1 SKIPS (not fails) if that file is not
yet present on this branch, so this PR's CI stays green standalone; it becomes a real drift guard
the moment both PRs have landed on main.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LOT_RUNNER_JS = REPO_ROOT / "infra/workflows/kbli-batch-a-lot.js"
CALIBRATION_JSON = REPO_ROOT / "data/kbli-filiera/batch-reports/batchA-calibration.json"


@pytest.fixture(scope="module")
def js_source() -> str:
    assert LOT_RUNNER_JS.exists(), f"lot runner not found at {LOT_RUNNER_JS}"
    return LOT_RUNNER_JS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. m1/m2/m4 numeric literals must match the calibration artifact (drift guard)
# ---------------------------------------------------------------------------

def _extract_js_number(source: str, key: str) -> float:
    m = re.search(rf"{re.escape(key)}\s*:\s*([0-9]+(?:\.[0-9]+)?)", source)
    assert m, f"could not find pinned literal {key!r} in {LOT_RUNNER_JS}"
    return float(m.group(1))


@pytest.mark.skipif(
    not CALIBRATION_JSON.exists(),
    reason=(
        "data/kbli-filiera/batch-reports/batchA-calibration.json not on this branch yet "
        "(ships on agent/air-m5/kbli/batcha-calibration) — drift guard activates once both "
        "PRs land on main"
    ),
)
def test_m1_m2_m4_literals_match_calibration_artifact(js_source: str) -> None:
    calibration = json.loads(CALIBRATION_JSON.read_text(encoding="utf-8"))
    limits = calibration["control_limits"]

    js_m1_floor = _extract_js_number(js_source, "m1_blind_concordance_floor")
    js_m2_floor = _extract_js_number(js_source, "m2_certification_rate_floor")
    js_m2_ceiling = _extract_js_number(js_source, "m2_certification_rate_ceiling")
    js_m4_ceiling = _extract_js_number(js_source, "m4_tokens_per_dossier_ceiling")

    assert js_m1_floor == limits["m1_blind_concordance"]["floor"]
    assert js_m2_floor == limits["m2_certification_rate"]["floor"]
    assert js_m2_ceiling == limits["m2_certification_rate"]["ceiling"]
    assert js_m4_ceiling == limits["m4_tokens_per_dossier"]["ceiling"]


def test_m3_closed_registry_matches_calibration_categories(js_source: str) -> None:
    """m3's 5-category closed registry is pinned in the .js as a JS array — assert it appears
    verbatim, independent of whether the calibration JSON has landed yet (the registry is quoted
    in the plan doc too, so this half of the guard has no external-file dependency)."""
    expected = [
        "code_collision",
        "illegitimate_inheritance",
        "wrong_authority_level",
        "phantom_source_pointer",
        "source_absent_in_vault",
    ]
    for category in expected:
        assert f'"{category}"' in js_source, f"m3 category {category!r} missing from lot runner"

    if CALIBRATION_JSON.exists():
        calibration = json.loads(CALIBRATION_JSON.read_text(encoding="utf-8"))
        assert calibration["control_limits"]["m3_refutation_categories"]["categories"] == expected


# ---------------------------------------------------------------------------
# 2. frozen verdict taxonomy — boring_as_expected only in a comment, never emitted
# ---------------------------------------------------------------------------

FROZEN_TAXONOMY = ("certified", "quarantined", "abstained")


def test_frozen_taxonomy_tokens_present(js_source: str) -> None:
    for token in FROZEN_TAXONOMY:
        assert f'"{token}"' in js_source, f"frozen-taxonomy token {token!r} not found"


def test_boring_as_expected_never_emitted_as_a_verdict(js_source: str) -> None:
    """`boring_as_expected` (the pilot's 4th-token deviation) may only appear as prose inside a
    // comment explaining the normalization — never as a quoted string literal (enum value,
    schema default, or emitted verdict) that a seat could actually produce."""
    assert "boring_as_expected" in js_source, (
        "expected the normalization comment referencing the pilot's deviation to still be present"
    )
    for line in js_source.splitlines():
        if "boring_as_expected" not in line:
            continue
        stripped = line.strip()
        assert stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"), (
            f"boring_as_expected must appear only in a comment line, found: {line!r}"
        )
        # and never as a quoted literal even within the comment's own code-look-alike snippet
        assert '"boring_as_expected"' not in line and "'boring_as_expected'" not in line


def test_verdict_enums_use_only_frozen_taxonomy(js_source: str) -> None:
    """Every `enum: [...]` block that includes a verdict-shaped token set must be exactly the
    frozen three (order-independent) — catches a schema silently regaining a 4th state."""
    enum_blocks = re.findall(r"enum:\s*\[([^\]]*)\]", js_source)
    verdict_like = [
        blk for blk in enum_blocks
        if any(tok in blk for tok in FROZEN_TAXONOMY)
    ]
    assert verdict_like, "expected at least one verdict enum block in the lot runner"
    for blk in verdict_like:
        tokens = {t.strip().strip('"').strip("'") for t in blk.split(",") if t.strip()}
        assert tokens == set(FROZEN_TAXONOMY), f"verdict enum block drifted from frozen taxonomy: {tokens}"


# ---------------------------------------------------------------------------
# 3. abstain-classes (pma_status, l4_bali, TKA) marked out-of-scope in the seat prompts
# ---------------------------------------------------------------------------

def test_abstain_classes_marked_out_of_scope(js_source: str) -> None:
    assert "OUT OF SCOPE" in js_source
    for facet in ("pma_status", "l4_bali", "TKA"):
        assert facet in js_source, f"abstain-class facet {facet!r} not named in the lot runner"
    # and it must be reachable from the shared out-of-scope notice actually interpolated into
    # every seat prompt function, not just mentioned in a header comment
    assert "OUT_OF_SCOPE_NOTICE" in js_source
    for fn in ("d1Prompt", "d5Prompt", "d2Prompt", "innocencePrompt"):
        fn_match = re.search(rf"function {fn}\([^)]*\)\s*{{(.*?)\n}}", js_source, re.DOTALL)
        assert fn_match, f"could not locate {fn} in lot runner"
        assert "OUT_OF_SCOPE_NOTICE" in fn_match.group(1), f"{fn} does not interpolate the out-of-scope notice"
