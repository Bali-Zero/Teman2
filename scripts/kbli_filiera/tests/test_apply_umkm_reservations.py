"""Guilt + innocence for the Lampiran II applier.

The patch itself is four constant fields; nothing interesting can go wrong
there. What can go wrong is the applier writing a client-facing 0%-foreign
verdict onto a record it should have refused, so every test below is about a
REFUSAL — and one about the refusals not being so eager that nothing applies.

`check()` aborts the whole run on a single refusal by design: a spec that is
wrong about one code has not earned trust about the other thirty-nine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import apply_umkm_reservations as A  # noqa: E402


def rec(code, status="TERBUKA", maxa=100, ancestors=None, basis=None):
    r = {"kode_kbli_2025": code, "pma_status": status, "pma_max_asing": maxa}
    if ancestors is not None:
        r["bps_2020_ancestors"] = {"codes": ancestors}
    if basis is not None:
        r["pma_official_basis"] = basis
    return r


def item(code, judged_as=None, was=None, locator="L-II p1"):
    return {
        "code": code,
        "judged_as": judged_as,
        "locator": locator,
        "was": was if was is not None else {"pma_status": "TERBUKA", "pma_max_asing": 100},
    }


def run(items, records):
    return A.check({"items": items}, records)


# --------------------------------------------------------------------------
# INNOCENCE — the ordinary case must actually go through
# --------------------------------------------------------------------------


def test_a_matching_record_is_applicable():
    todo, refusals = run([item("01111")], [rec("01111")])
    assert refusals == []
    assert [i["code"] for i in todo] == ["01111"]


def test_a_row_judged_on_a_2020_code_applies_to_its_single_heir():
    """`55193` (villa) is not a 2025 code; `55203` is, and is its only heir."""
    todo, refusals = run(
        [item("55203", judged_as="55193")],
        [rec("55203", ancestors=["55193"])],
    )
    assert refusals == []
    assert [i["code"] for i in todo] == ["55203"]


def test_the_same_locator_already_present_is_not_an_obstacle():
    """Re-running the cure must be idempotent, not self-blocking."""
    todo, refusals = run(
        [item("01111", locator="L-II p1")],
        [rec("01111", basis="L-II p1")],
    )
    assert refusals == [] and len(todo) == 1


# --------------------------------------------------------------------------
# GUILT — every way this must refuse rather than write
# --------------------------------------------------------------------------


def test_refuses_a_code_absent_from_the_dataset():
    todo, refusals = run([item("99999")], [rec("01111")])
    assert todo == [] and len(refusals) == 1 and "not in the dataset" in refusals[0]


def test_refuses_when_the_2020_code_has_several_heirs():
    """The split-heirs case: the annex reserves ONE segment, so a 2020 code
    that fans out to several 2025 codes cannot hand its verdict to one of them."""
    todo, refusals = run(
        [item("55203", judged_as="55110")],
        [rec("55203", ancestors=["55110"]), rec("55201", ancestors=["55110"])],
    )
    assert todo == []
    assert "resolves to" in refusals[0]


def test_refuses_when_the_2020_code_has_no_heir_at_all():
    todo, refusals = run([item("55203", judged_as="55193")], [rec("55203")])
    assert todo == [] and "no 2025 heir" in refusals[0]


def test_refuses_a_record_already_adjudicated_by_hand():
    """A different `pma_official_basis` is someone else's later word, and this
    tool is not entitled to overwrite it."""
    todo, refusals = run(
        [item("47111", locator="L-II p14")],
        [rec("47111", basis="Perpres 10/2021 Lampiran II line 3722 — hand-adjudicated")],
    )
    assert todo == [] and "different pma_official_basis" in refusals[0]


def test_refuses_when_the_record_moved_since_the_adjudication():
    """Someone cured this code between the adjudication and the apply; the
    verdict was formed against a world that no longer exists."""
    todo, refusals = run(
        [item("01111", was={"pma_status": "TERBUKA", "pma_max_asing": 100})],
        [rec("01111", status="TERBATAS", maxa=49)],
    )
    assert todo == [] and "moved since adjudication" in refusals[0]


def test_one_bad_row_stops_the_whole_run():
    todo, refusals = run([item("01111"), item("99999")], [rec("01111")])
    assert len(refusals) == 1
    assert len(todo) == 1  # collected, but main() aborts on any refusal


# --------------------------------------------------------------------------
# The patch, and what the real spec is allowed to contain
# --------------------------------------------------------------------------


def test_patch_states_zero_foreign_and_names_its_basis():
    p = A.patch_for(item("01111", locator="L-II p1"))
    assert p["pma_max_asing"] == 0
    assert p["pma_status"] == "TERBATAS"
    assert p["pma_official_basis"] == "L-II p1"
    assert p["pma_cap_verified"] is True


def test_the_shipped_spec_carries_only_unanimous_verdicts():
    """Structural pin on the real artifact: the excluded populations must still
    be declared in it, so a future regeneration cannot quietly absorb the
    disagreements into the patch set. Reads `withdrawn_items` when the spec has
    been withdrawn — the verdicts are still a record worth pinning even though
    none of them may be applied."""
    spec = json.loads(A.SPEC.read_text(encoding="utf-8"))
    ex = spec["excluded"]
    assert ex["disagreements"] > 0 and ex["agreed_unclear"] > 0
    assert ex["ocr_illegible"], "the illegible row must stay named, not vanish"
    verdicts = spec.get("items") or spec["withdrawn_items"]
    codes = [i["code"] for i in verdicts]
    assert len(codes) == len(set(codes)), "a code patched twice"
    for i in verdicts:
        assert "Lampiran II" in i["locator"] and "Pasal 3(1)(b)" in i["locator"]


def test_guilt_a_withdrawn_spec_is_refused_before_anything_is_read(tmp_path, capsys):
    """The shipped spec IS withdrawn, so this is the live path. `items: []` alone
    would make the run a silent no-op that prints "applied 0 codes" — which reads
    like success. The refusal has to name itself."""
    p = tmp_path / "s.json"
    p.write_text(json.dumps({
        "withdrawn": {"date": "2026-08-06", "by": "review", "reason": "why", "next": "what"},
        "items": [], "withdrawn_items": [], "excluded": {},
    }), encoding="utf-8")
    assert A.main(["--apply", "--spec", str(p)]) == A.EXIT_REFUSED
    assert "REFUSING" in capsys.readouterr().out


def test_innocence_a_spec_without_that_marker_still_runs():
    """The guard must not turn every spec into a refusal — the tool has to stay
    usable for the re-adjudicated spec that replaces this one."""
    spec = json.loads(A.SPEC.read_text(encoding="utf-8"))
    assert "withdrawn" in spec, "the shipped spec is the withdrawn one"
    todo, refusals = run([item("01111")], [rec("01111")])
    assert refusals == [] and [i["code"] for i in todo] == ["01111"]


def test_the_withdrawal_names_the_codes_whose_evidence_was_short():
    """Not a count: the eleven codes judged under a restricting parent are named,
    so the re-adjudication cannot start from "39 codes, re-check them all" and
    lose which ones were actually compromised."""
    w = json.loads(A.SPEC.read_text(encoding="utf-8"))["withdrawn"]
    tainted = w["codes_judged_under_a_restricting_parent"]
    assert len(tainted) == w["count_tainted"] > 0
    assert "01111" in tainted, "the 25-Ha food crops are the clearest members"
    assert "43215" in tainted, "so is the simple/intermediate technology grade"
