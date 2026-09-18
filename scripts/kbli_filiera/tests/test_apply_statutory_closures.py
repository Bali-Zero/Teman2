"""Guilt + innocence for `apply_statutory_closures.py` (naso PR-3, 2026-09-18).

The compiler relabels 59 already-closed records `declared_gap -> located` and
names the instrument. The tests pin (a) the dataset state the PR delivers, on
the REAL canonical, and (b) the refusal surface on a sandbox: a verdict is never
flipped, a title-derived class cannot absorb a code its rule reaches without
naming it, and an exclusion cannot hide an eligible code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FILIERA = REPO_ROOT / "scripts" / "kbli_filiera"
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import apply_statutory_closures as S  # noqa: E402

CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC = json.loads(S.SPEC.read_text(encoding="utf-8"))

CLOSED_ALL = ["11010", "11020", "01287", "92000"]
GOV_TITLES = [
    "59111", "59121", "59131", "60311",
    "85101", "85201", "85311", "85315", "85321", "85401", "85403", "85550", "85560",
    "86101", "86104", "87201", "87301",
    "91111", "91121", "91211", "91221",
]  # fmt: skip
NOT_TOUCHED = {
    "87101": "TERBUKA",
    "88101": "TERBUKA",
    "88901": "TERBUKA",
    "11030": "TERBUKA",
    "20119": "TERTUTUP",
}


@pytest.fixture(scope="module")
def by_code() -> dict[str, dict]:
    payload = json.loads(CANONICAL.read_text(encoding="utf-8"))
    return {str(r["kode_kbli_2025"]): r for r in payload["data"]}


def spec_codes() -> list[str]:
    return [str(i["code"]) for c in S.CLASSES for i in SPEC["classes"][c]["items"]]


# ---------------------------------------------------------------- dataset state


def test_the_spec_covers_exactly_the_59_and_the_class_census_is_the_dossiers():
    codes = spec_codes()
    assert len(codes) == 59 and len(set(codes)) == 59
    gov = SPEC["classes"]["government_activity"]["items"]
    assert sum(i["leg"] == "prefix_84" for i in gov) == 33
    assert {i["code"] for i in gov if i["leg"] == "title_pemerintah"} == set(GOV_TITLES)
    assert set(CLOSED_ALL) <= set(codes) and "99000" in codes


def test_every_spec_code_is_located_closed_and_names_its_instrument(by_code):
    for code in spec_codes():
        r = by_code[code]
        assert (r["pma_status"], r["pma_max_asing"]) == ("TERTUTUP", 0), code
        assert r["pma_verification_status"] == "located", code
        assert (
            r["pma_cap_verified"] is True and r["pma_source_vintage"] == "2021-05-25"
        ), code
        basis = r["pma_official_basis"]
        assert "Perpres 10/2021" in basis or "UU 25/2007 Pasal 12(2)" in basis, code
        assert "DIALOKASIKAN" not in basis and "UMKM" not in (
            r.get("pma_kondisi") or ""
        ), code


def test_named_codes_cite_the_perpres_and_title_derived_ones_say_so(by_code):
    for code in ("11010", "11020"):
        assert "Pasal 2(2)(b)" in by_code[code]["pma_official_basis"]
        assert S.TITLE_DERIVED not in by_code[code]["pma_official_basis"]
    for code in ("01287", "92000", "99000", "84111", *GOV_TITLES):
        assert S.TITLE_DERIVED in by_code[code]["pma_official_basis"], code
    assert "Pasal 12(2)(a)" in by_code["01287"]["pma_official_basis"]
    assert "Pasal 12(2)(b)" in by_code["92000"]["pma_official_basis"]
    assert "Pasal 2(1a)" in by_code["99000"]["pma_official_basis"]


def test_the_verdict_flips_are_not_taken_here(by_code):
    for code, status in NOT_TOUCHED.items():
        r = by_code[code]
        assert (
            r["pma_status"] == status and r["pma_verification_status"] == "declared_gap"
        ), code
    assert "11031" not in by_code


def test_rerun_on_the_shipped_canonical_is_a_clean_noop(by_code):
    todo, refusals = S.check(SPEC, list(by_code.values()))
    assert (todo, refusals) == ([], [])


# ---------------------------------------------------------------- refusal surface


def rec(code, judul, status="TERTUTUP", maxa=0, state="declared_gap", ancestors=None):
    r = {
        "kode_kbli_2025": code,
        "judul": judul,
        "pma_status": status,
        "pma_max_asing": maxa,
        "pma_verification_status": state,
    }
    if ancestors is not None:
        r["bps_2020_ancestors"] = {
            "codes": ancestors,
            "sebagian": [False] * len(ancestors),
        }
    return r


def mini_spec(gov_items, gov_excluded=None):
    spec = json.loads(json.dumps(SPEC))
    for cls in S.CLASSES:
        spec["classes"][cls]["items"] = []
        spec["classes"][cls]["excluded"] = {}
    spec["classes"]["government_activity"]["items"] = gov_items
    spec["classes"]["government_activity"]["excluded"] = gov_excluded or {}
    return spec


def test_a_terbuka_record_with_a_pemerintah_title_is_refused_not_flipped():
    spec = mini_spec([{"code": "87101", "leg": "title_pemerintah"}])
    todo, refusals = S.check(
        spec, [rec("87101", "Aktivitas X oleh Pemerintah", "TERBUKA", 100)]
    )
    assert todo == [] and any("never flips" in r for r in refusals)


def test_a_code_the_rule_reaches_but_nobody_names_blocks_the_write():
    spec = mini_spec([{"code": "84111", "leg": "prefix_84"}])
    records = [
        rec("84111", "Lembaga Legislatif"),
        rec("85101", "Pendidikan TK Pemerintah"),
    ]
    _, refusals = S.check(spec, records)
    assert refusals == [
        "85101: reached by the government_activity rule but neither item nor exclusion"
    ]


def test_an_exclusion_cannot_hide_an_eligible_closed_code():
    spec = mini_spec([{"code": "84111", "leg": "prefix_84"}], {"85101": "why"})
    records = [
        rec("84111", "Lembaga Legislatif"),
        rec("85101", "Pendidikan TK Pemerintah"),
    ]
    _, refusals = S.check(spec, records)
    assert any(r.startswith("85101: excluded") for r in refusals)


def test_a_title_leg_that_does_not_match_is_refused():
    spec = mini_spec([{"code": "85101", "leg": "title_pemerintah"}])
    _, refusals = S.check(spec, [rec("85101", "Pendidikan Taman Kanak-Kanak Swasta")])
    assert refusals and "does not reach it" in refusals[-1]


def test_the_named_code_leg_needs_a_sole_whole_ancestor():
    spec = mini_spec([])
    spec["classes"]["instrument_names_code"]["items"] = [
        {
            "code": "11030",
            "named_2020_code": "11031",
            "named_as": "Industri Minuman Mengandung Malt (KBLI 11031)",
        }
    ]
    _, refusals = S.check(
        spec, [rec("11030", "Industri Bir", ancestors=["11031", "11090"])]
    )
    assert refusals == [
        "11030: 2020 ancestry is ['11031', '11090']/[False, False], not sole whole 11031"
    ]
    _, ok = S.check(spec, [rec("11030", "Industri Bir", ancestors=["11031"])])
    assert ok == []


def test_already_located_under_another_basis_is_refused_and_same_basis_is_a_noop():
    spec = mini_spec([{"code": "84111", "leg": "prefix_84"}])
    r = rec("84111", "Lembaga Legislatif", state="located")
    r["pma_official_basis"] = "somebody else's instrument"
    _, refusals = S.check(spec, [r])
    assert refusals == ["84111: already located under a different basis"]
    r["pma_official_basis"] = S.basis_for(
        "government_activity", spec["classes"]["government_activity"]["items"][0], r
    )
    assert S.check(spec, [r]) == ([], [])


def test_apply_on_a_sandbox_writes_the_tuple_and_skips_propagation(tmp_path, capsys):
    spec = mini_spec([{"code": "84111", "leg": "prefix_84"}])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(
        json.dumps({"data": [rec("84111", "Lembaga Legislatif")]}) + "\n",
        encoding="utf-8",
    )
    assert (
        S.main(["--apply", "--dataset", str(data), "--spec", str(spec_path)])
        == S.EXIT_OK
    )
    out = capsys.readouterr().out
    assert "skipping consumer propagation" in out
    got = json.loads(data.read_text(encoding="utf-8"))["data"][0]
    assert (
        got["pma_verification_status"] == "located" and got["pma_status"] == "TERTUTUP"
    )
    assert got["pma_max_asing"] == 0 and got["pma_cap_verified"] is True
    assert (
        S.main(["--apply", "--dataset", str(data), "--spec", str(spec_path)])
        == S.EXIT_OK
    )
    assert "clean no-op" in capsys.readouterr().out
