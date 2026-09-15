"""TDD anchor for SAETTA-20260915 / W-H PR-3a.

Three codes — 55201 (homestay), 55203 (vila), 79903 (pramuwisata) — must
carry the SAME field tuple the certified template (95291 96100 96210 96220)
already carries: TERBATAS / 0 / located, with a `pma_official_basis` that
names Lampiran II. This file reads the REAL canonical dataset (not a
fixture): the deliverable is that dataset state, and a fixture could pass
while the file on disk still says TERBUKA/100.

Fails on `main` (dataset unchanged, all three still TERBUKA/100/declared_gap).
Passes once `apply_umkm_reservations.py --spec
cure_specs/lampiran2_allocation_wh_pr3_2026_09_15.json --apply` has run.

PR-3a ships only these 3 whole-code allocations; the 8 specialised-retail
codes of Lampiran II entry 46 are PR-3b (a sibling lane, not this file).

The locator assertion is the antidote this dossier exists to keep alive
(`scripts/kbli_filiera/tests/test_withdrawn_umkm_inference_absent.py`,
`apps/mouth/src/lib/kbli-withdrawn-umkm-inference.test.ts`): a 0% verdict here
may rest ONLY on a Lampiran II annex row, never on the absence of a Besar
`per_skala` row.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

WHOLE_CODE = ["55201", "55203", "79903"]

# Every other Lampiran II tuple field this compile MUST also carry — matched
# to the certified template on 96220/95291/96100/96210 (`apply_umkm_reservations.
# patch_for`). Checked as a set, not as an exhaustive dict, so an extra field
# the template does NOT carry is not silently required here too.
REQUIRED = {
    "pma_status": "TERBATAS",
    "pma_max_asing": 0,
    "pma_verification_status": "located",
    "pma_cap_verified": True,
    "pma_source_vintage": "2021-05-25",
}


def _by_code() -> dict[str, dict]:
    payload = json.loads(CANONICAL.read_text(encoding="utf-8"))
    records = payload["data"] if isinstance(payload, dict) else payload
    return {str(r["kode_kbli_2025"]): r for r in records}


@pytest.fixture(scope="module")
def by_code() -> dict[str, dict]:
    return _by_code()


@pytest.mark.parametrize("code", WHOLE_CODE)
def test_tuple_matches_certified_template(code, by_code):
    rec = by_code[code]
    for field, expected in REQUIRED.items():
        assert rec.get(field) == expected, (
            f"{code}.{field} = {rec.get(field)!r}, want {expected!r} "
            "(96220-style Lampiran II tuple)"
        )


@pytest.mark.parametrize("code", WHOLE_CODE)
def test_locator_names_lampiran_ii_never_per_skala(code, by_code):
    basis = by_code[code].get("pma_official_basis") or ""
    assert "Lampiran II" in basis, f"{code}: pma_official_basis does not cite Lampiran II: {basis!r}"
    assert "per_skala" not in basis, f"{code}: locator leans on per_skala — the withdrawn inference"
    assert "Usaha Besar" not in basis, (
        f"{code}: locator leans on absence of an Usaha Besar row — the withdrawn inference"
    )
    assert "Koperasi" in basis or "UMKM" in basis, f"{code}: locator does not name the K-UMKM allocation"


def test_kondisi_field_matches_template(by_code):
    for code in WHOLE_CODE:
        kondisi = by_code[code].get("pma_kondisi") or ""
        assert "0%" in kondisi, f"{code}: pma_kondisi does not state 0%: {kondisi!r}"
        assert "Koperasi" in kondisi and "UMKM" in kondisi


def test_l4_bali_untouched(by_code):
    """A sibling window (W-J / B1) owns the Bali overlay; this PR must not
    touch `l4_bali` of any code."""
    before = _by_code()
    for code in WHOLE_CODE:
        assert by_code[code].get("l4_bali") == before[code].get("l4_bali")


def test_out_of_scope_codes_untouched(by_code):
    """55209 and 79110 are IN REVIEW (dossier §2) — never touch them. 43110,
    93114 and the 12 hold codes belong to other W-H lanes; the 8 specialised
    retail codes of Lampiran II entry 46 are PR-3b (a sibling lane)."""
    for code in [
        "55209",
        "79110",
        "43110",
        "93114",
        "47241",
        "47242",
        "47244",
        "47245",
        "47246",
        "47249",
        "47712",
        "47722",
    ]:
        rec = by_code.get(code)
        if rec is None:
            continue
        assert rec.get("pma_status") != "TERBATAS" or rec.get("pma_official_basis") is None or (
            "Lampiran II" not in (rec.get("pma_official_basis") or "")
        ), f"{code} is out of PR-3a scope and must not carry a Lampiran II verdict from this lane"
