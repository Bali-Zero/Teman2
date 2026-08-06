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


def test_guilt_a_2025_code_that_absorbs_other_2020_codes_is_refused():
    """`79110` (Aktivitas Agen Perjalanan) is the live shape: the annex reserves
    the 2020 row `79111`, but the 2025 code also absorbs `79112` and `79119`, so
    a 0% verdict on it closes activities the annex never named."""
    todo, refusals = run(
        [item("79110", judged_as="79111")],
        [rec("79110", ancestors=["79111", "79112", "79119"])],
    )
    assert todo == []
    assert "broader than the reserved activity" in refusals[0]
    assert "79112" in refusals[0], "the refusal must name what makes it broader"


def test_innocence_a_clean_one_to_one_carry_over_still_applies():
    """Six of the seven vintage rows ARE 1:1 (`55193`->`55203` villa). A rule
    that refused those too would withdraw six real determinations to catch one."""
    todo, refusals = run(
        [item("55203", judged_as="55193")],
        [rec("55203", ancestors=["55193"])],
    )
    assert refusals == [] and [i["code"] for i in todo] == ["55203"]


def test_the_two_directions_are_different_questions():
    """Forward: did the 2020 activity SPLIT? Reverse: did the 2025 code MERGE?
    A record can pass one and fail the other, which is why both are asked — the
    first rule was there from the start and could not have caught 79110."""
    records = [rec("79110", ancestors=["79111", "79112", "79119"])]
    heirs = A.heirs_of(records)
    assert heirs["79111"] == ["79110"], "forward check passes: one heir"
    todo, refusals = run([item("79110", judged_as="79111")], records)
    assert todo == [] and refusals, "reverse check refuses"


def test_the_readjudication_scope_is_named_and_small():
    """The withdrawal's own follow-up scope, pinned so it cannot drift back into
    "recheck all 68". Measured by diffing each verdict's annex row before and
    after the parent/fusion cures: 11 had a restricting parent hidden from the
    lane, 2 had their row text change, 26 read exactly what the annex says."""
    d = json.loads(A.SPEC.read_text(encoding="utf-8"))["withdrawn"]["evidence_delta_2026_08_06"]
    hidden = d["restricting_parent_was_hidden"]
    changed = d["row_text_changed_by_the_fusion_cure"]
    assert len(hidden) + len(changed) == 13, "the re-adjudication is thirteen codes"
    assert d["evidence_unchanged"] == 26
    assert "42912" in changed, "the fused-cell row is one of the two"
    # …and 26 unchanged is NOT a licence to revive them; the spec has to keep
    # saying which axes are still open on that group.
    assert "same ACTIVITY" in d["meaning"] and "OCR" in d["meaning"]


def test_the_readjudication_overturned_eleven_of_the_thirteen():
    """The 13 named codes, re-judged on evidence that finally carries the parent
    bidang usaha. Pinned because it is the reason the withdrawal was right: the
    six 25-Ha crops and the five simple/intermediate-technology grades are
    reserved only as a SEGMENT, not as whole codes."""
    r = json.loads(A.SPEC.read_text(encoding="utf-8"))["withdrawn"]["readjudication_2026_08_06"]
    v = r["verdicts"]
    assert len(v["REFUSE_SEGMENT"]) == 11
    assert v["PATCH_ZERO"] == ["95299"] and v["REFUSE_BROADER"] == ["42912"]
    assert sum(len(x) for x in v.values()) == 13
    # 01111 is the worked example of the whole defect; it must not drift back
    # into a whole-code reservation without this test failing.
    assert "01111" in v["REFUSE_SEGMENT"]
    # …and the run's own weakness stays written down next to its result.
    assert "handed both lanes the conclusion" in r["declared_weakness"]
