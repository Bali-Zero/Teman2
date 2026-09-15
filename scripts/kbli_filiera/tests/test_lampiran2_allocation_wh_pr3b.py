"""TDD anchor for SAETTA-20260915 / W-H PR-3b.

Restricted from `test_lampiran2_allocation_wh_pr3.py` (the PR-3/PR-3a lane's
11-code version) to the 8 specialised-retail codes of Lampiran II entry 46
that belong to THIS PR: 47241 47242 47244 47245 47246 47249 47712 47722.
55201/55203/79903 belong to PR-3a and are asserted there, not here.

Each of the 8 must carry the SAME field tuple the certified template
(95291 96100 96210 96220) already carries: TERBATAS / 0 / located, with a
`pma_official_basis` that names Lampiran II entry 46 and the code's own
sub-row product (D5b: the reservation is of the WHOLE specialised code, and
the client text must name activity AND product). This file reads the REAL
canonical dataset (not a fixture): the deliverable is that dataset state, and
a fixture could pass while the file on disk still said TERBUKA/100.

Fails on `main` (dataset unchanged, all 8 still TERBUKA/100/declared_gap).
Passes once `cure_pma_lampiran2_specialised_retail.py --spec
cure_specs/lampiran2_specialised_retail_wh_pr3_2026_09_15.json --apply` has run.

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

RETAIL = ["47241", "47242", "47244", "47245", "47246", "47249", "47712", "47722"]

# Every other Lampiran II tuple field this compiler MUST also carry — matched
# to the certified template on 96220/95291/96100/96210 (`apply_umkm_reservations.
# patch_for`, reused unmodified by `cure_pma_lampiran2_specialised_retail.py`).
# Checked as a set, not as an exhaustive dict, so an extra field the template
# does NOT carry is not silently required here too.
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


@pytest.mark.parametrize("code", RETAIL)
def test_tuple_matches_certified_template(code, by_code):
    rec = by_code[code]
    for field, expected in REQUIRED.items():
        assert rec.get(field) == expected, (
            f"{code}.{field} = {rec.get(field)!r}, want {expected!r} "
            "(96220-style Lampiran II tuple)"
        )


@pytest.mark.parametrize("code", RETAIL)
def test_locator_names_lampiran_ii_never_per_skala(code, by_code):
    basis = by_code[code].get("pma_official_basis") or ""
    assert "Lampiran II" in basis, f"{code}: pma_official_basis does not cite Lampiran II: {basis!r}"
    assert "per_skala" not in basis, f"{code}: locator leans on per_skala — the withdrawn inference"
    assert "Usaha Besar" not in basis, (
        f"{code}: locator leans on absence of an Usaha Besar row — the withdrawn inference"
    )
    assert "Koperasi" in basis or "UMKM" in basis, f"{code}: locator does not name the K-UMKM allocation"


def test_kondisi_field_matches_template(by_code):
    for code in RETAIL:
        kondisi = by_code[code].get("pma_kondisi") or ""
        assert "0%" in kondisi, f"{code}: pma_kondisi does not state 0%: {kondisi!r}"
        assert "Koperasi" in kondisi and "UMKM" in kondisi


def test_retail_locator_names_the_specific_product(by_code):
    """D5b (Zero, 2026-09-15): the retail reservation is of the WHOLE
    specialised code, and the client text must name activity AND product —
    so the locator must not be the generic Lampiran II sentence alone; it
    must carry the code's own sub-row text (entry 46)."""
    product_words = {
        "47241": "Beras",
        "47242": "Roti",
        "47244": "Tahu",
        "47245": "Daging",
        "47246": "Ikan",
        "47249": "Makanan",
        "47712": "Alas Kaki",
        "47722": "farmasi",
    }
    for code, word in product_words.items():
        basis = by_code[code].get("pma_official_basis") or ""
        assert word.lower() in basis.lower(), (
            f"{code}: locator does not name its own product ({word!r}): {basis!r}"
        )


def test_l4_bali_untouched(by_code):
    """A sibling window (W-J / B1) owns the Bali overlay; this PR must not
    touch `l4_bali` of any code."""
    before = _by_code()
    for code in RETAIL:
        assert by_code[code].get("l4_bali") == before[code].get("l4_bali")


def test_out_of_scope_codes_untouched(by_code):
    """55201/55203/79903 belong to PR-3a. 55209 and 79110 are IN REVIEW
    (dossier §2) — never touch them. 55203/79903 not present here should still
    stay out of a Lampiran-II-from-this-lane verdict; other codes belong to
    other W-H lanes (43110, 93114)."""
    for code in ["55201", "55203", "79903", "55209", "79110", "43110", "93114"]:
        rec = by_code.get(code)
        if rec is None:
            continue
        assert rec.get("pma_status") != "TERBATAS" or rec.get("pma_official_basis") is None or (
            "Lampiran II" not in (rec.get("pma_official_basis") or "")
        ) or "entry 46" not in (rec.get("pma_official_basis") or ""), (
            f"{code} is out of PR-3b scope and must not carry a PR-3b entry-46 verdict"
        )
