"""TDD anchor for the 2026-09-18 PMA closed-list research ("segui il nostro naso").

The dossier `research/kbli/2026-09-18-kbli-codes-closed-to-pma-tier1-tier2-dossier.md`
found seven KBLI 2025 codes whose whole scope is a Perpres 49/2021 Lampiran II
row (DIALOKASIKAN untuk Koperasi dan UMKM) through a 1:1 BPS crosswalk. Six ship
here — 10307 10308 16291 16293 32201 55106 — through `apply_umkm_reservations.py
--spec cure_specs/lampiran2_coextensive_naso_2026_09_18.json --apply`. 13133
(batik) is deferred: its live Lampiran III slice disclosure would become
double-speak once the whole code reads TERBATAS, so it needs its own PR.

Each of the six must carry the SAME field tuple the certified template
(95291 96100 96210 96220, then the W-H lots) already carries: TERBATAS / 0 /
located, with a `pma_official_basis` that names Lampiran II and the code's own
row. This file reads the REAL canonical dataset, not a fixture: the deliverable
is that dataset state.

The locator assertion keeps the withdrawn inference dead: a 0% verdict here may
rest ONLY on a Lampiran II annex row, never on the absence of a Besar
`per_skala` row.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"

SIX = ["10307", "10308", "16291", "16293", "32201", "55106"]

REQUIRED = {
    "pma_status": "TERBATAS",
    "pma_max_asing": 0,
    "pma_verification_status": "located",
    "pma_cap_verified": True,
    "pma_source_vintage": "2021-05-25",
}

# The annex row each code is the whole of (dossier §3 + relation.json).
ROW_WORDS = {
    "10307": "tempe kedelai",
    "10308": "tahu kedelai",
    "16291": "Rotan dan bambu",
    "16293": "ukiran dari kayu",
    "32201": "alat musik tradisional",
    "55106": "Hotel Melati",
}

OPENNESS = (
    "100%",
    "100 percent",
    "fully open",
    "open to foreign",
    "nationally open",
    "PMA status: Open",
    "PT PMA incorporation",
)


def _by_code() -> dict[str, dict]:
    payload = json.loads(CANONICAL.read_text(encoding="utf-8"))
    return {str(r["kode_kbli_2025"]): r for r in payload["data"]}


@pytest.fixture(scope="module")
def by_code() -> dict[str, dict]:
    return _by_code()


@pytest.fixture(scope="module")
def gold() -> dict[str, dict]:
    raw = json.loads(GOLD.read_text(encoding="utf-8"))
    return raw.get("data", raw)


@pytest.mark.parametrize("code", SIX)
def test_tuple_matches_certified_template(code, by_code):
    rec = by_code[code]
    for field, expected in REQUIRED.items():
        assert rec.get(field) == expected, (
            f"{code}.{field} = {rec.get(field)!r}, want {expected!r}"
        )


@pytest.mark.parametrize("code", SIX)
def test_locator_names_lampiran_ii_row_never_per_skala(code, by_code):
    basis = by_code[code].get("pma_official_basis") or ""
    assert "Lampiran II" in basis, f"{code}: {basis!r}"
    assert ROW_WORDS[code].lower() in basis.lower(), (
        f"{code}: locator does not name its own annex row ({ROW_WORDS[code]!r}): {basis!r}"
    )
    assert "per_skala" not in basis and "Usaha Besar" not in basis, (
        f"{code}: locator leans on the withdrawn no-Besar inference"
    )
    assert "Koperasi" in basis or "UMKM" in basis


@pytest.mark.parametrize("code", SIX)
def test_kondisi_and_cells_state_zero(code, by_code):
    rec = by_code[code]
    kondisi = rec.get("pma_kondisi") or ""
    assert "0%" in kondisi and "Koperasi" in kondisi and "UMKM" in kondisi
    cells = (rec.get("intel_2026") or {}).get("editorial", {}).get("byTheNumbers") or []
    for cell in cells:
        blob = json.dumps(cell, ensure_ascii=False)
        if "foreign" in blob.lower() or "pma" in blob.lower():
            assert "100" not in blob, f"{code}: a byTheNumbers cell still says 100: {blob}"


@pytest.mark.parametrize("code", SIX)
def test_canonical_prose_no_longer_promises_a_pma_route(code, by_code):
    intel = by_code[code].get("intel_2026") or {}
    texts = [v for v in intel.values() if isinstance(v, str)]
    texts += [v for v in (intel.get("editorial") or {}).values() if isinstance(v, str)]
    for t in texts:
        for phrase in OPENNESS:
            assert phrase.lower() not in t.lower(), f"{code}: {phrase!r} in {t[:120]!r}"
    assert "Lampiran II" in intel.get("whatYouNeed", ""), f"{code}: whatYouNeed lacks the basis"


@pytest.mark.parametrize("code", ["16291", "16293", "32201", "55106"])
def test_gold_override_agrees_with_canonical(code, gold):
    """Gold OVERRIDES canonical on the rendered page (kbli-data.server.ts::
    transformCode); a cured canonical under an uncured gold is invisible."""
    rec = gold[code]
    for field in ("zantaraOpener", "whatYouNeed", "baliContext"):
        text = rec.get(field) or ""
        for phrase in OPENNESS:
            assert phrase.lower() not in text.lower(), f"gold {code}.{field}: {phrase!r}"
    assert "Lampiran II" in rec["whatYouNeed"]
    assert "**PMA:** Closed to foreign investment" in rec["whatYouNeed"]


def test_no_gold_entry_for_the_two_food_codes(gold):
    """10307/10308 have no gold override, so canonical is what renders."""
    assert "10307" not in gold and "10308" not in gold


def test_l4_bali_untouched(by_code):
    before = _by_code()
    for code in SIX:
        assert by_code[code].get("l4_bali") == before[code].get("l4_bali")


def test_out_of_scope_codes_untouched(by_code):
    """13133 (deferred), 55209/79110 (in review), the whole-row-unresolved set
    and the SEGMENT codes must not carry a naso verdict."""
    for code in ["13133", "55209", "79110", "02300", "10794", "13122", "16292",
                 "16294", "23932", "47192", "47243", "47721", "26513", "30301"]:
        rec = by_code.get(code)
        if rec is None:
            continue
        assert rec.get("pma_verification_status") == "declared_gap", (
            f"{code} is out of scope and must stay a declared gap: "
            f"{rec.get('pma_status')}/{rec.get('pma_max_asing')}/{rec.get('pma_verification_status')}"
        )
