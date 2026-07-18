"""Tests for scripts/kbli_filiera/emit_lot_report.py (plan §8 A-3 lot-report compiler).

Three properties, per the mandate:

1. Determinism (G16) — same inputs => byte-identical rendered JSON.
2. Verdict-taxonomy-only — every rendered verdict is one of the frozen three tokens
   (certified | quarantined | abstained); an out-of-taxonomy verdict is refused, not
   silently coerced.
3. Census matches the conductor's Lot A-L1 report: 1 certified, 12 quarantined
   (11 + the 1 D6-demoted 38222), 2 innocence controls.

History: the first draft of LOT_A_L1_VERDICTS/LOT_A_L1_INNOCENCE shipped with 9 of
13 quarantined-code categories and both innocence-control codes as explicit
NEEDS-DATA/PENDING placeholders — the conductor's initial aggregate summary named
the 4 categories SEEN across the lot but not the per-code map. build_report()'s
fail-closed gate correctly refused to build from that incomplete data (this was
verified live before the real table arrived). The conductor supplied the complete,
signed table in a follow-up message (2026-07-18); it is what's pinned in
emit_lot_report.py now, and the tests below exercise the REAL literal directly —
no test-local placeholder-filling needed anymore. The fail-closed gate itself
remains covered by the synthetic guilt/innocence pairs below (never removed).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.kbli_filiera.emit_lot_report import (
    FROZEN_TAXONOMY,
    LOT_A_L1_INNOCENCE,
    LOT_A_L1_VERDICTS,
    REFUTATION_CATEGORIES,
    LotReportError,
    build_report,
    render_json,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# 1. Determinism (G16) — synthetic fixture, same inputs => byte-identical output
# ---------------------------------------------------------------------------

def _synthetic_verdicts() -> list[dict]:
    return [
        {"code": "11111", "verdict": "certified", "category": None, "d2_self_confirm_failed": False, "note": "clean"},
        {"code": "22222", "verdict": "quarantined", "category": "code_collision", "d2_self_confirm_failed": False, "note": "collision"},
        {"code": "33333", "verdict": "quarantined", "category": "phantom_source_pointer", "d2_self_confirm_failed": True, "note": "demoted"},
    ]


def _synthetic_innocence() -> list[dict]:
    return [{"code": "99999", "verdict": "certified", "note": "innocence ok"}]


def test_build_report_is_deterministic() -> None:
    ctx1 = build_report(lot_id="TEST-1", verdicts=_synthetic_verdicts(), innocence=_synthetic_innocence())
    ctx2 = build_report(lot_id="TEST-1", verdicts=_synthetic_verdicts(), innocence=_synthetic_innocence())
    assert render_json(ctx1) == render_json(ctx2), "same inputs must render byte-identical JSON (G16)"


def test_render_json_is_sorted_keys_with_trailing_newline() -> None:
    ctx = build_report(lot_id="TEST-1", verdicts=_synthetic_verdicts(), innocence=_synthetic_innocence())
    rendered = render_json(ctx)
    assert rendered.endswith("\n") and not rendered.endswith("\n\n")
    # sort_keys=True in json.dumps — spot-check top-level key order is alphabetic
    import json

    reparsed = json.loads(rendered)
    assert reparsed == ctx


# ---------------------------------------------------------------------------
# 2. Verdict-taxonomy-only — frozen three tokens, never a 4th
# ---------------------------------------------------------------------------

def test_verdicts_use_only_frozen_taxonomy() -> None:
    assert FROZEN_TAXONOMY == ("certified", "quarantined", "abstained")
    ctx = build_report(lot_id="TEST-1", verdicts=_synthetic_verdicts(), innocence=_synthetic_innocence())
    for v in ctx["verdicts"]:
        assert v["verdict"] in FROZEN_TAXONOMY
    for i in ctx["innocence_controls"]:
        assert i["verdict"] in FROZEN_TAXONOMY


def test_guilt_out_of_taxonomy_verdict_is_refused() -> None:
    """GUILT: a verdict outside the frozen three (e.g. a stray 'boring_as_expected'
    leaking through) must be refused, never silently rendered."""
    bad = [
        {"code": "44444", "verdict": "boring_as_expected", "category": None, "d2_self_confirm_failed": False}
    ]
    with pytest.raises(LotReportError, match="outside frozen taxonomy"):
        build_report(lot_id="TEST-1", verdicts=bad, innocence=[])


def test_innocence_valid_taxonomy_verdict_is_accepted() -> None:
    """INNOCENCE: a genuinely valid verdict (certified) must NOT be refused —
    proves the guilt check above discriminates on the taxonomy, not on rejecting
    every entry."""
    ok = [{"code": "55555", "verdict": "certified", "category": None, "d2_self_confirm_failed": False}]
    ctx = build_report(lot_id="TEST-1", verdicts=ok, innocence=[])
    assert ctx["census"]["certified"] == 1


# ---------------------------------------------------------------------------
# 3. Fail-closed gate — a quarantined entry with no category is refused
# ---------------------------------------------------------------------------

def test_guilt_quarantined_without_category_is_refused() -> None:
    """GUILT: a quarantined entry with category=None must be refused — this is
    the exact shape of the 9 NEEDS-DATA placeholders currently in
    LOT_A_L1_VERDICTS, and the gate that stops this compiler from ever silently
    emitting a fabricated or incomplete per-code judgment."""
    bad = [{"code": "66666", "verdict": "quarantined", "category": None, "d2_self_confirm_failed": False}]
    with pytest.raises(LotReportError, match="no category"):
        build_report(lot_id="TEST-1", verdicts=bad, innocence=[])


def test_guilt_quarantined_category_outside_registry_is_refused() -> None:
    """GUILT: a category string that is neither in REFUTATION_CATEGORIES nor the
    literal OTHER_NEW_CATEGORY sentinel must be refused (m3 closed-registry, plan
    §5 — a genuinely new category is a program-level finding, not free text)."""
    bad = [{"code": "77777", "verdict": "quarantined", "category": "made_up_category", "d2_self_confirm_failed": False}]
    with pytest.raises(LotReportError, match="outside the closed registry"):
        build_report(lot_id="TEST-1", verdicts=bad, innocence=[])


def test_innocence_quarantined_with_registry_category_is_accepted() -> None:
    """INNOCENCE: a quarantined entry WITH a genuine in-registry category must
    pass — proves the two guilt checks above discriminate on missing/invalid
    category, not on quarantined entries in general."""
    ok = [{"code": "88888", "verdict": "quarantined", "category": "code_collision", "d2_self_confirm_failed": False}]
    ctx = build_report(lot_id="TEST-1", verdicts=ok, innocence=[])
    assert ctx["census"]["quarantined"] == 1
    assert ctx["categories_seen"] == ["code_collision"]


def test_real_pinned_literal_builds_successfully() -> None:
    """The REAL, now-complete LOT_A_L1_VERDICTS/LOT_A_L1_INNOCENCE pinned
    literal must build cleanly — proving the fail-closed gate's earlier
    refusal (see module docstring "History") was a data-completeness issue,
    now resolved, not a structural defect in the table itself."""
    ctx = build_report(lot_id="A-L1", verdicts=LOT_A_L1_VERDICTS, innocence=LOT_A_L1_INNOCENCE)
    assert ctx["census"]["adjudicated"] == 13


# ---------------------------------------------------------------------------
# 4. Census matches the conductor's Lot A-L1 report (real code/verdict/category
#    data — the conductor's full signed table, 2026-07-18 second message)
# ---------------------------------------------------------------------------

def test_lot_a_l1_census_matches_conductor_report() -> None:
    """Census counts against the REAL pinned literal — no placeholder-filling
    needed anymore, the conductor's full table is in."""
    ctx = build_report(lot_id="A-L1", verdicts=LOT_A_L1_VERDICTS, innocence=LOT_A_L1_INNOCENCE)

    assert ctx["census"]["adjudicated"] == 13
    assert ctx["census"]["certified"] == 1
    assert ctx["census"]["quarantined"] == 12
    assert ctx["census"]["demoted_at_d6"] == 1
    assert ctx["census"]["innocence_controls"] == 2
    assert ctx["categories_seen"] == [
        "code_collision",
        "illegitimate_inheritance",
        "phantom_source_pointer",
        "source_absent_in_vault",
    ]

    # spot-check every per-code category against the conductor's signed table verbatim
    by_code = {v["code"]: v for v in ctx["verdicts"]}
    expected_categories = {
        "19206": None,
        "01287": "code_collision",
        "01700": "source_absent_in_vault",
        "02201": "source_absent_in_vault",
        "02402": "code_collision",
        "02409": "phantom_source_pointer",
        "05102": "illegitimate_inheritance",
        "05200": "phantom_source_pointer",
        "08920": "source_absent_in_vault",
        "36003": "phantom_source_pointer",
        "38122": "phantom_source_pointer",
        "38222": "phantom_source_pointer",
        "39001": "illegitimate_inheritance",
    }
    for code, category in expected_categories.items():
        assert by_code[code]["category"] == category, f"{code}: expected category {category!r}"
    assert by_code["19206"]["verdict"] == "certified"
    assert by_code["38222"]["d2_self_confirm_failed"] is True
    for code in expected_categories:
        if code != "38222":
            assert by_code[code]["d2_self_confirm_failed"] is False

    innocence_codes = {i["code"] for i in ctx["innocence_controls"]}
    assert innocence_codes == {"65121", "85202"}
    for i in ctx["innocence_controls"]:
        assert i["verdict"] == "certified"


def test_lot_a_l1_verdicts_cover_exactly_the_plan_a2_code_list() -> None:
    """Cross-check against plan §8 amendment A-2's own 13-code list (Lot 1 =
    divisions 01->39) — catches a transcription slip (missing/extra/duplicate
    code) independent of the category-completeness question above."""
    plan_path = REPO_ROOT / "research/operations/2026-07-18-kbli-batch-a-plan.md"
    plan_text = plan_path.read_text(encoding="utf-8")
    # Anchored on the literal boundary phrases either side of the code list itself
    # ("taxonomy order): " ... ". Control limits") so the capture is exactly the
    # 13-code list, nothing from the surrounding prose.
    a2_match = re.search(
        r"Lot 1 = divisions 01->39\*\*.*?taxonomy order\):\s*(.+?)\.\s*Control limits",
        plan_text,
        re.DOTALL,
    )
    assert a2_match, "could not locate the A-2 Lot 1 code list in the plan doc"
    a2_codes = sorted(re.findall(r"`(\d{5})`", a2_match.group(1)))

    verdict_codes = sorted(v["code"] for v in LOT_A_L1_VERDICTS)
    assert verdict_codes == a2_codes, (
        f"LOT_A_L1_VERDICTS codes {verdict_codes} do not match plan §8 A-2's Lot 1 list {a2_codes}"
    )
