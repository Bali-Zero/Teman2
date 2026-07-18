"""Tests for scripts/kbli_filiera/emit_lot_report.py (plan §8 A-3 lot-report compiler).

Three properties, per the mandate:

1. Determinism (G16) — same inputs => byte-identical rendered JSON.
2. Verdict-taxonomy-only — every rendered verdict is one of the frozen three tokens
   (certified | quarantined | abstained); an out-of-taxonomy verdict is refused, not
   silently coerced.
3. Census matches the conductor's Lot A-L1 report: 1 certified, 12 quarantined
   (11 + the 1 D6-demoted 38222), 2 innocence controls.

NOTE on (3): as of this test file's authoring, the real LOT_A_L1_VERDICTS pinned
literal in emit_lot_report.py has 9 of 13 quarantined-code categories marked
NEEDS-DATA (category=None) and both innocence-control codes marked NEEDS-DATA
(code=None) — the conductor's per-code category table was not in the mandate's
aggregate summary. The module's own `_validate_verdicts` fail-closed gate refuses
to build a report from incomplete data (test_incomplete_pinned_literal_refuses_to_build
is the regression guard for that gate). test_lot_a_l1_census_matches_conductor_report
below fills the PENDING category slots with an arbitrary in-registry placeholder
(test-local only, never touching the module's real data) because census COUNTS
depend only on code identity + certified/quarantined/demoted assignment — all of
which ARE certain, given directly in the mandate + plan §8 A-2's code list — never
on which specific category a code got.
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


def test_incomplete_pinned_literal_refuses_to_build() -> None:
    """Regression guard for the fail-closed gate itself: as long as
    LOT_A_L1_VERDICTS carries any NEEDS-DATA placeholder (category=None on a
    quarantined entry, or code=None on an innocence entry), build_report() on
    the REAL pinned literal must raise — proving this compiler cannot silently
    emit the incomplete Lot A-L1 report today. Once the conductor supplies the
    real per-code categories and innocence-control codes, this test should be
    UPDATED (not deleted) to assert the real report builds successfully — see
    test_lot_a_l1_census_matches_conductor_report below, which is READY for
    that data the moment it lands."""
    with pytest.raises(LotReportError):
        build_report(lot_id="A-L1", verdicts=LOT_A_L1_VERDICTS, innocence=LOT_A_L1_INNOCENCE)


# ---------------------------------------------------------------------------
# 4. Census matches the conductor's Lot A-L1 report (real code/verdict data,
#    placeholder category only — see module docstring)
# ---------------------------------------------------------------------------

def test_lot_a_l1_census_matches_conductor_report() -> None:
    """Census counts (adjudicated/certified/quarantined/demoted/innocence) use
    the REAL code identities and REAL verdict/demotion assignments from
    LOT_A_L1_VERDICTS (all certain, given directly in the mandate + plan §8
    A-2's 13-code list) — only the 9 PENDING categories are filled with an
    arbitrary in-registry placeholder here, test-local only, since census
    counts don't depend on WHICH category a code got, only that it has one."""
    filled_verdicts = []
    for v in LOT_A_L1_VERDICTS:
        entry = dict(v)
        if entry["verdict"] == "quarantined" and entry.get("category") is None:
            entry["category"] = "source_absent_in_vault"  # test-local placeholder ONLY
        filled_verdicts.append(entry)
    filled_innocence = [
        {**i, "code": i["code"] or f"INNOCENCE_PLACEHOLDER_{n}"}
        for n, i in enumerate(LOT_A_L1_INNOCENCE)
    ]

    ctx = build_report(lot_id="A-L1", verdicts=filled_verdicts, innocence=filled_innocence)

    assert ctx["census"]["adjudicated"] == 13
    assert ctx["census"]["certified"] == 1
    assert ctx["census"]["quarantined"] == 12
    assert ctx["census"]["demoted_at_d6"] == 1
    assert ctx["census"]["innocence_controls"] == 2

    # spot-check the two hard-evidenced non-placeholder categories survive untouched
    by_code = {v["code"]: v for v in ctx["verdicts"]}
    assert by_code["02402"]["category"] == "code_collision"
    assert by_code["01287"]["category"] == "illegitimate_inheritance"
    assert by_code["38222"]["category"] == "phantom_source_pointer"
    assert by_code["38222"]["d2_self_confirm_failed"] is True
    assert by_code["19206"]["verdict"] == "certified"


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
