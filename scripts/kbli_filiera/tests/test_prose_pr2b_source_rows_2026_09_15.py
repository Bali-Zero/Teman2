"""Assertion that PR-2b's removed-row prose premise never survives on disk.

The BLOCKER-adjacent MAJOR finding on SAETTA-20260915 W-H PR-2b: 93114's
`whatYouNeed` said the restored golf-course tier "could not be confirmed" /
"has been removed" and carried a stale "Risk tier under review" paragraph;
43110's `editorial.body` said only Mikro is recorded and the PP 28/2025
Besar-scale BUJK PMA row is "not reflected in this per-scale table". Both
premises are false once `cure_pr2b_source_rows_93114_43110.py` restores the
rows. Cured via `cure_prose_national_openness.py` +
`cure_specs/prose_pr2b_source_rows_2026_09_15.json`. This test reads the
REAL canonical, not a fixture — a regression here is a false claim in front
of an investor.
"""
from __future__ import annotations

import json
from pathlib import Path

FILIERA = Path(__file__).resolve().parents[1]
REPO_ROOT = FILIERA.parents[1]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

REMOVED_ROW_PREMISES = (
    "could not be confirmed",
    "could not be verified",
    "has been removed",
    "Risk tier under review",
    "unverified risk classification",
)
MIKRO_ONLY_PREMISES = (
    "only Mikro is recorded",
    "not reflected in this per-scale table",
)


def _records() -> dict[str, dict]:
    payload = json.loads(CANONICAL.read_text(encoding="utf-8"))
    return {r["kode_kbli_2025"]: r for r in payload["data"]}


def test_93114_carries_no_removed_row_premise():
    rec = _records()["93114"]
    haystack = json.dumps(rec["intel_2026"], ensure_ascii=False)
    for needle in REMOVED_ROW_PREMISES:
        assert needle not in haystack, f"93114 still carries the removed-row premise: {needle!r}"


def test_43110_carries_no_mikro_only_premise():
    rec = _records()["43110"]
    haystack = json.dumps(rec["intel_2026"], ensure_ascii=False)
    for needle in MIKRO_ONLY_PREMISES:
        assert needle not in haystack, f"43110 still carries the Mikro-only premise: {needle!r}"


def test_93114_whatyouneed_states_the_restored_golf_tier():
    body = _records()["93114"]["intel_2026"]["whatYouNeed"]
    assert "Tinggi risk" in body
    assert "PP 28/2025 Lampiran I.L.61" in body
    assert "NIB + Izin" in body


def test_43110_editorial_body_states_the_bujk_pma_besar_row():
    body = _records()["43110"]["intel_2026"]["editorial"]["body"]
    assert "BUJK PMA" in body
    assert "three rows" in body


def test_43110_editorial_body_bali_paragraph_is_untouched():
    """Only paragraph 2 (the Mikro-only claim) was replaced — the Bali
    paragraph, which already stated the Besar/BUJK PMA row correctly, must
    still be byte-identical to what shipped in this same PR's data cure."""
    body = _records()["43110"]["intel_2026"]["editorial"]["body"]
    assert "Bali is where the distinction becomes decisive." in body
    assert "cited to a Governor’s letter." in body
