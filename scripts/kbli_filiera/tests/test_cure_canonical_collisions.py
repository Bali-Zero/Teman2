"""Tests for the GARUDA-FILIERA Fase 1 canonical cure compiler.

Covers the v2 extension (2026-07-17): the compiler now also rewrites the
client-facing ``intel_2026.whatYouNeed`` to an honest-gap text, IN ADDITION to
the per_skala detach. The two parts must be independently idempotent — the 7
codes are already detached (#2589), so a whatYouNeed-only apply must NOT clobber
the preserved disputed block.

The whatYouNeed texts were authored from each code's image-verified data_note and
passed a 3-round Codex cross-family adversarial gate; ``_honest_gap_violations``
pins that discipline (guilt + innocence per scar #3) so a future edit that
reintroduces a forbidden pattern (an unproven "100%", a stale risk assertion,
a missing verify-with-team pointer) fails CI.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import cure_canonical_collisions as cure  # noqa: E402

DISPUTED_KEY = "per_skala_disputed_pp28_collision"


def _honest_gap_violations(text: str) -> list[str]:
    """Return the list of honest-gap rule violations in a whatYouNeed text.

    Empty list == compliant. Encodes the rules the Codex gate enforced:
    no unproven ownership %, no retained/asserted risk tier, must preserve
    PMA-open, must declare the gap, must route the client to verification.
    """
    v: list[str] = []
    low = text.lower()
    if "100%" in text or "100 %" in text:
        v.append("asserts an unproven ownership percentage")
    # a CURRENT risk-tier assertion (the stale collision-derived value) — the
    # cured text may only say risk is NOT defined, never state a tier.
    if re.search(r"(medium[- ]high|medium[- ]low|high risk|low risk|menengah|tinggi|rendah)", low):
        v.append("asserts/retains a specific risk tier")
    if "pma" not in low:
        v.append("drops the preserved PMA-open status")
    if not re.search(r"(not yet reliably defined|cannot reliably be applied|unconfirmed)", low):
        v.append("does not declare the risk/licensing gap")
    if "bali zero team" not in low:
        v.append("does not route the client to team verification")
    if len(text) < 120:
        v.append("too short to be a real disclosure")
    return v


def test_spec_ships_honest_gap_whatyouneed_for_every_code() -> None:
    spec = cure.load_spec(cure.DEFAULT_SPEC)
    codes = {e["code"]: e for e in spec["codes"]}
    assert len(codes) == 7, "Fase 1 spec should carry exactly the 7 quarantined codes"
    for code, entry in codes.items():
        wyn = entry.get("whatYouNeed")
        assert isinstance(wyn, str) and wyn, f"{code}: spec missing whatYouNeed"
        violations = _honest_gap_violations(wyn)
        assert not violations, f"{code}: honest-gap violations {violations}\n---\n{wyn}"


def test_guilt_a_bad_text_is_flagged() -> None:
    # INNOCENCE control for the guard: a legit honest-gap text passes (above);
    # GUILT: a text that reintroduces the disease must be caught.
    bad = (
        "Nationally, this activity is 100% open to foreign ownership. It is "
        "classified as medium-high risk, so expect closer scrutiny. Register via NIB."
    )
    violations = _honest_gap_violations(bad)
    assert "asserts an unproven ownership percentage" in violations
    assert "asserts/retains a specific risk tier" in violations
    assert "does not route the client to team verification" in violations


def _record(*, per_skala, whatYouNeed="stale prose", disputed=False):
    rec = {
        "kode_kbli_2025": "51103",
        "judul": "X",
        "per_skala": per_skala,
        "pma_status": "TERBUKA",
        "intel_2026": {"whatItMeans": "keep", "whatYouNeed": whatYouNeed},
    }
    if disputed:
        rec[DISPUTED_KEY] = [{"kategori_risiko": "Tinggi"}]
    return rec


def test_apply_sets_whatyouneed_on_already_detached_without_clobbering_disputed() -> None:
    original_disputed = [{"kategori_risiko": "Tinggi", "src": "collision"}]
    rec = {
        "kode_kbli_2025": "51103",
        "per_skala": [],
        DISPUTED_KEY: copy.deepcopy(original_disputed),
        "pma_status": "TERBUKA",
        "intel_2026": {"whatItMeans": "keep me", "whatYouNeed": "STALE medium-high risk"},
        "_data_note": "old note",
    }
    entry = {"code": "51103", "data_note": "new note", "whatYouNeed": "GAP text"}
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)

    assert out["per_skala"] == []
    assert out[DISPUTED_KEY] == original_disputed, "disputed block must NOT be clobbered with []"
    assert out["intel_2026"]["whatYouNeed"] == "GAP text"
    assert out["intel_2026"]["whatItMeans"] == "keep me", "other intel_2026 fields preserved"
    assert out["_data_note"] == "new note"


def test_apply_detach_and_whatyouneed_together_when_not_yet_detached() -> None:
    rec = _record(per_skala=[{"kategori_risiko": "Tinggi"}])
    entry = {"code": "51103", "data_note": "note", "whatYouNeed": "GAP text"}
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["per_skala"] == []
    assert out[DISPUTED_KEY] == [{"kategori_risiko": "Tinggi"}], "current per_skala preserved in disputed key"
    assert out["intel_2026"]["whatYouNeed"] == "GAP text"
    assert out["_data_note"] == "note"


def test_plan_apply_when_detached_but_whatyouneed_differs() -> None:
    rec = _record(per_skala=[], whatYouNeed="stale", disputed=True)
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "fresh gap"}
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.needs_whatyouneed is True
    assert plan.needs_detach is False


def test_plan_already_cured_when_detached_and_whatyouneed_matches() -> None:
    rec = _record(per_skala=[], whatYouNeed="fresh gap", disputed=True)
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "fresh gap"}
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "already-cured"


def test_plan_ambiguous_skip_when_empty_and_no_disputed_key() -> None:
    rec = _record(per_skala=[], whatYouNeed="stale", disputed=False)
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "fresh gap"}
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "ambiguous-skip", "unrecognised prior state must not be touched"


def test_apply_raises_when_intel_missing_but_whatyouneed_requested() -> None:
    rec = {"kode_kbli_2025": "51103", "per_skala": []}
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "gap"}
    with pytest.raises(cure.CureError):
        cure.apply_cure(rec, entry, DISPUTED_KEY)
