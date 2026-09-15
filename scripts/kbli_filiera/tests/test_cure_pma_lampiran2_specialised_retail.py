"""Guilt + innocence for the specialised-retail Lampiran II applier.

Mirrors the shape of `test_apply_umkm_reservations.py`: every interesting
failure is a REFUSAL, because a wrong write here is a client-facing 0%
verdict. Fixture records only — the real dataset is exercised by
`test_lampiran2_allocation_wh_pr3.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import cure_pma_lampiran2_specialised_retail as C  # noqa: E402


def rec(code, status="TERBUKA", maxa=100, ancestors=None, basis=None):
    r = {"kode_kbli_2025": code, "pma_status": status, "pma_max_asing": maxa}
    if ancestors is not None:
        r["bps_2020_ancestors"] = {"codes": ancestors}
    if basis is not None:
        r["pma_official_basis"] = basis
    return r


def item(code, self_ancestor, split_siblings=None, was=None, locator="L-II entry 46"):
    return {
        "code": code,
        "self_ancestor": self_ancestor,
        "split_siblings": split_siblings or [],
        "locator": locator,
        "was": was if was is not None else {"pma_status": "TERBUKA", "pma_max_asing": 100},
    }


def test_simple_self_ancestor_applies():
    records = [rec("47241", ancestors=["47241", "47821", "47911"])]
    spec = {"items": [item("47241", "47241")]}
    todo, refusals = C.check(spec, records)
    assert refusals == []
    assert [t["code"] for t in todo] == ["47241"]


def test_split_pair_applies_when_both_declared():
    records = [
        rec("47245", ancestors=["47245", "47825"]),
        rec("47246", ancestors=["47245", "47825"]),
    ]
    spec = {
        "items": [
            item("47245", "47245", split_siblings=["47246"]),
            item("47246", "47245", split_siblings=["47245"]),
        ]
    }
    todo, refusals = C.check(spec, records)
    assert refusals == []
    assert {t["code"] for t in todo} == {"47245", "47246"}


def test_refuses_when_self_ancestor_not_in_bps_ancestors():
    records = [rec("47241", ancestors=["99999"])]
    spec = {"items": [item("47241", "47241")]}
    todo, refusals = C.check(spec, records)
    assert todo == []
    assert "not among its bps_2020_ancestors" in refusals[0]


def test_refuses_undeclared_sibling_sharing_the_ancestor():
    """A THIRD code silently shares the same 2020 ancestor and this spec
    never named it — must refuse rather than silently close it too, or
    silently leave it as an unexplained gap."""
    records = [
        rec("47245", ancestors=["47245"]),
        rec("47246", ancestors=["47245"]),
        rec("99999", ancestors=["47245"]),  # undeclared sibling
    ]
    spec = {
        "items": [
            item("47245", "47245", split_siblings=["47246"]),
            item("47246", "47245", split_siblings=["47245"]),
        ]
    }
    todo, refusals = C.check(spec, records)
    assert todo == []
    assert any("undeclared sibling" in r for r in refusals)


def test_refuses_partial_split_sibling_missing_from_spec():
    """47246 declares 47245 as its sibling, but 47245 is not itself an item
    in the spec — a partial split, refused even though the crosswalk math
    alone would look consistent."""
    records = [
        rec("47245", ancestors=["47245"]),
        rec("47246", ancestors=["47245"]),
    ]
    spec = {"items": [item("47246", "47245", split_siblings=["47245"])]}
    todo, refusals = C.check(spec, records)
    assert todo == []
    assert any("not themselves items in this spec" in r for r in refusals)


def test_refuses_conflicting_existing_basis():
    records = [rec("47241", ancestors=["47241"], basis="some other hand-adjudicated basis")]
    spec = {"items": [item("47241", "47241")]}
    todo, refusals = C.check(spec, records)
    assert todo == []
    assert "already carries a different pma_official_basis" in refusals[0]


def test_refuses_when_world_moved_since_adjudication():
    records = [rec("47241", status="TERTUTUP", maxa=0, ancestors=["47241"])]
    spec = {"items": [item("47241", "47241", was={"pma_status": "TERBUKA", "pma_max_asing": 100})]}
    todo, refusals = C.check(spec, records)
    assert todo == []
    assert "moved since adjudication" in refusals[0]


def test_idempotent_noop_when_already_applied():
    already = rec("47241", ancestors=["47241"])
    already.update(C.base.patch_for(item("47241", "47241", locator="L-II entry 46")))
    todo, refusals = C.check({"items": [item("47241", "47241", locator="L-II entry 46")]}, [already])
    assert refusals == []
    assert todo == []  # nothing left to do — already carries the target tuple


def test_a_single_refusal_names_the_bad_code_and_leaves_the_good_one_collected():
    """`check()` collects; `main()` is what aborts the whole run on any
    refusal (mirrors `apply_umkm_reservations.py` — see its own test file,
    `test_apply_umkm_reservations.py::…`: "collected, but main() aborts on
    any refusal"). 47241 is individually valid and lands in `todo`; 47242 is
    the one refusal, and its presence is what stops `main()` from writing
    ANYTHING, including the valid 47241."""
    records = [
        rec("47241", ancestors=["47241"]),
        rec("47242", ancestors=["99999"]),  # bad
    ]
    spec = {"items": [item("47241", "47241"), item("47242", "47242")]}
    todo, refusals = C.check(spec, records)
    assert [t["code"] for t in todo] == ["47241"]
    assert len(refusals) == 1
    assert "47242" in refusals[0]
