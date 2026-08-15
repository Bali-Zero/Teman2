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
        "was": was
        if was is not None
        else {"pma_status": "TERBUKA", "pma_max_asing": 100},
    }


def split_item(
    code, split, siblings, was=None, locator="L-II p1", judged_as=None, agreed_by=None
):
    it = item(code, judged_as=judged_as, was=was, locator=locator)
    it["judged_as_split_heir"] = split
    it["siblings_left_open"] = siblings
    # Two lanes by DEFAULT, so that every other test in this file exercises the
    # ordinary case and only the tests that mean to attack precondition 6 pass
    # something else. A helper whose default is invalid makes every test a test
    # of the same one check.
    it["agreed_by"] = (
        ["lane-a (proposer)", "lane-b (blind re-derivation)"]
        if agreed_by is None
        else agreed_by
    )
    return it


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
    """A locator alone is not a completed cure; the missing fields still apply."""
    todo, refusals = run(
        [item("01111", locator="L-II p1")],
        [rec("01111", basis="L-II p1")],
    )
    assert refusals == [] and len(todo) == 1


def test_a_fully_applied_patch_is_an_idempotent_noop():
    it = item("01111", locator="L-II p1")
    cured = rec("01111", status="TERBATAS", maxa=0, basis="L-II p1")
    cured.update(A.patch_for(it))

    todo, refusals = run([it], [cured])

    assert todo == []
    assert refusals == []


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


# --------------------------------------------------------------------------
# The SPLIT-HEIR gate — a second, narrower door, not a hole in the first one
#
# `judged_as` refuses every split, and that refusal is correct for what it
# guards: the crosswalk alone cannot name which heir the annex row means. This
# gate admits the sub-case where the REVERSE direction can — the heir that
# absorbs no other 2020 code cannot be wider than the row. Each mechanical
# precondition below gets its own guilt test, because a gate whose conditions
# are only tested in aggregate is a gate with untested conditions.
# --------------------------------------------------------------------------


def test_innocence_a_split_heir_that_absorbs_nothing_else_applies():
    """`96111` (Pangkas rambut) fans out to barbering and to an intermediation
    platform. Barbering absorbs only 96111, so it cannot over-reach."""
    todo, refusals = run(
        [split_item("96210", "96111", ["96400"])],
        [
            rec("96210", ancestors=["96111"]),
            rec("96400", ancestors=["96111", "96112", "96200"]),
        ],
    )
    assert refusals == []
    assert [i["code"] for i in todo] == ["96210"]


def test_guilt_a_split_heir_that_absorbs_another_2020_code_is_refused():
    """The whole point. `96400` is also an heir of 96111, and closing it would
    bar the eight other activities it swallowed."""
    todo, refusals = run(
        [split_item("96400", "96111", ["96210"])],
        [
            rec("96400", ancestors=["96111", "96112", "96200"]),
            rec("96210", ancestors=["96111"]),
        ],
    )
    assert todo == []
    assert "also absorbs" in refusals[0] and "96112" in refusals[0]


def test_guilt_a_split_heir_whose_named_ancestor_is_not_an_ancestor_is_refused():
    """A typo in the spec must not become a 0% verdict on an unrelated code."""
    todo, refusals = run(
        [split_item("96210", "96119", ["96400"])],
        [rec("96210", ancestors=["96111"]), rec("96400", ancestors=["96119", "96129"])],
    )
    assert todo == []
    assert "not among its ancestors" in refusals[0]


def test_guilt_an_undeclared_sibling_is_refused():
    """The siblings left open are the population this cure DROPS. A spec that
    names one while the dataset says there are four is describing a different
    world than the one being patched — and the drop would be invisible."""
    todo, refusals = run(
        [split_item("55105", "55110", ["55101"])],
        [rec(c, ancestors=["55110"]) for c in ("55101", "55102", "55105")],
    )
    assert todo == []
    assert "also went to" in refusals[0] and "55102" in refusals[0]


def test_guilt_a_sibling_the_spec_calls_open_but_the_dataset_has_shut_is_refused():
    """Precondition 5. Naming the siblings is not sparing them. `96400` is what
    makes closing `96210` narrow — it carries the rest of what 96111 became. If
    some other cure had already restricted 96400, the spec's sentence "the
    sibling stays open" would be false about the catalogue, and the split it
    describes would not be the split on disk.
    """
    todo, refusals = run(
        [split_item("96210", "96111", ["96400"])],
        [
            rec("96210", ancestors=["96111"]),
            rec(
                "96400",
                ancestors=["96111", "96112", "96200"],
                status="TERBATAS",
                maxa=0,
            ),
        ],
    )
    assert todo == []
    assert "does not show them open" in refusals[0] and "96400" in refusals[0]


def test_guilt_a_sibling_whose_status_cannot_be_read_is_refused_not_assumed_open():
    """The same precondition, from the direction that fails OPEN if it is written
    as a negative. A record with no `pma_status` at all is not evidence that the
    sibling is open; it is the absence of evidence, and this gate exists to
    establish a positive fact. The first draft asked `not in (None, "TERBUKA")`
    and would have waved this through.
    """
    silent = {
        "kode_kbli_2025": "96400",
        "bps_2020_ancestors": {"codes": ["96111", "96112"]},
    }
    todo, refusals = run(
        [split_item("96210", "96111", ["96400"])],
        [rec("96210", ancestors=["96111"]), silent],
    )
    assert todo == []
    assert "does not show them open" in refusals[0]


def test_guilt_a_split_heir_adjudicated_by_one_lane_is_refused():
    """Precondition 6. Identity here is a judgment, not a crosswalk lookup, so
    one lane's word is not an adjudication."""
    todo, refusals = run(
        [split_item("96210", "96111", ["96400"], agreed_by=["lane-a (proposer)"])],
        [rec("96210", ancestors=["96111"]), rec("96400", ancestors=["96111", "96112"])],
    )
    assert todo == []
    assert "two independent lanes" in refusals[0]


def test_guilt_the_same_lane_written_twice_is_still_one_lane():
    """Two entries are not two lanes. This is the shape a copy-paste produces,
    and it is the one a length check would wave through."""
    todo, refusals = run(
        [split_item("96210", "96111", ["96400"], agreed_by=["lane-a", " lane-a "])],
        [rec("96210", ancestors=["96111"]), rec("96400", ancestors=["96111", "96112"])],
    )
    assert todo == []
    assert "two independent lanes" in refusals[0]


def test_guilt_one_seat_wearing_two_role_labels_is_still_one_seat():
    """The shape a whitespace-dedupe cannot see, and the one a spec author
    actually produces: the same model named twice with different roles. A second
    review pointed out that comparing whole strings ATTESTED independence rather
    than enforcing it — the two entries differ, the seat does not."""
    todo, refusals = run(
        [
            split_item(
                "96210",
                "96111",
                ["96400"],
                agreed_by=["claude-sonnet-5 (proposer)", "claude-sonnet-5 (grader)"],
            )
        ],
        [rec("96210", ancestors=["96111"]), rec("96400", ancestors=["96111", "96112"])],
    )
    assert todo == []
    assert "two independent lanes" in refusals[0]


def test_innocence_two_genuinely_different_seats_are_accepted():
    """The other half: the real spec's shape must still pass, or the check would
    be a blanket refusal rather than an independence test."""
    todo, refusals = run(
        [
            split_item(
                "96210",
                "96111",
                ["96400"],
                agreed_by=[
                    "claude-sonnet-5 (proposer)",
                    "codex-gpt-5.6 (blind re-derivation)",
                ],
            )
        ],
        [rec("96210", ancestors=["96111"]), rec("96400", ancestors=["96111", "96112"])],
    )
    assert refusals == [] and [i["code"] for i in todo] == ["96210"]


def test_guilt_an_absent_agreed_by_is_refused_rather_than_assumed():
    todo, refusals = run(
        [split_item("96210", "96111", ["96400"], agreed_by=[])],
        [rec("96210", ancestors=["96111"]), rec("96400", ancestors=["96111", "96112"])],
    )
    assert todo == []
    assert "found none" in refusals[0]


def test_guilt_a_code_whose_ancestor_did_not_split_is_refused_from_this_gate():
    """Not a split at all: it belongs on `judged_as`. Two gates that accept the
    same item drift apart, and then a change to one silently spares the other."""
    todo, refusals = run(
        [split_item("55203", "55193", [])],
        [rec("55203", ancestors=["55193"])],
    )
    assert todo == []
    assert "no other heir" in refusals[0] and "judged_as case" in refusals[0]


def test_guilt_an_item_claiming_both_gates_is_refused():
    """Which gate judged it has to be answerable from the item alone."""
    todo, refusals = run(
        [split_item("96210", "96111", ["96400"], judged_as="96111")],
        [rec("96210", ancestors=["96111"]), rec("96400", ancestors=["96111", "96112"])],
    )
    assert todo == []
    assert "both judged_as and judged_as_split_heir" in refusals[0]


def test_innocence_the_original_single_heir_gate_still_refuses_a_split():
    """The new door must not have widened the old one: an item that still uses
    `judged_as` on a split ancestor is refused exactly as before."""
    todo, refusals = run(
        [item("55203", judged_as="55110")],
        [rec("55203", ancestors=["55110"]), rec("55201", ancestors=["55110"])],
    )
    assert todo == [] and "resolves to" in refusals[0]


def test_refuses_a_record_already_adjudicated_by_hand():
    """A different `pma_official_basis` is someone else's later word, and this
    tool is not entitled to overwrite it."""
    todo, refusals = run(
        [item("47111", locator="L-II p14")],
        [
            rec(
                "47111",
                basis="Perpres 10/2021 Lampiran II line 3722 — hand-adjudicated",
            )
        ],
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
    assert p["pma_verification_status"] == "located"
    assert p["pma_cap_verified"] is True


def test_the_withdrawn_spec_still_declares_its_excluded_populations():
    """Structural pin on the withdrawn artifact: the excluded populations must
    still be declared in it, so a future regeneration cannot quietly absorb the
    disagreements into a patch set. Reads `withdrawn_items` — the verdicts are
    still a record worth pinning even though none of them may be applied."""
    spec = json.loads(A.WITHDRAWN_SPEC.read_text(encoding="utf-8"))
    ex = spec["excluded"]
    assert ex["disagreements"] > 0 and ex["agreed_unclear"] > 0
    assert ex["ocr_illegible"], "the illegible row must stay named, not vanish"
    verdicts = spec.get("items") or spec["withdrawn_items"]
    codes = [i["code"] for i in verdicts]
    assert len(codes) == len(set(codes)), "a code patched twice"
    for i in verdicts:
        assert "Lampiran II" in i["locator"] and "Pasal 3(1)(b)" in i["locator"]


def _sandbox_dataset(tmp_path):
    """A one-record stand-in for canonical.

    Both refusal tests below run with `--apply`, because the claim is that the
    refusal precedes the WRITE — a dry-run would prove something weaker. That
    makes the dataset argument load-bearing: with the guard mutated away, the
    run reaches the write, and pointed at the default it would rewrite the real
    37MB catalogue from inside pytest (W96). It writes here instead.
    """
    d = tmp_path / "canonical.json"
    d.write_text(json.dumps({"data": [rec("01111")]}), encoding="utf-8")
    return d


def test_guilt_a_withdrawn_spec_is_refused_before_anything_is_read(tmp_path, capsys):
    """`items: []` alone would make the run a silent no-op that prints "applied 0
    codes" — which reads like success. The refusal has to name itself."""
    p = tmp_path / "s.json"
    p.write_text(
        json.dumps(
            {
                "withdrawn": {
                    "date": "2026-08-06",
                    "by": "review",
                    "reason": "why",
                    "next": "what",
                },
                "items": [],
                "withdrawn_items": [],
                "excluded": {},
            }
        ),
        encoding="utf-8",
    )
    d = _sandbox_dataset(tmp_path)
    assert A.main(["--apply", "--spec", str(p), "--dataset", str(d)]) == A.EXIT_REFUSED
    assert "REFUSING" in capsys.readouterr().out


def test_guilt_the_real_withdrawn_spec_on_disk_is_still_refused(tmp_path, capsys):
    """Not a tmp fixture: the ACTUAL withdrawn artifact. Now that the default spec
    has moved to its replacement, nothing else would notice if someone deleted the
    `withdrawn` block and revived 39 codes whose evidence was measured short."""
    assert A.WITHDRAWN_SPEC.exists(), "the withdrawn spec must stay on disk as a record"
    d = _sandbox_dataset(tmp_path)
    rc = A.main(["--apply", "--spec", str(A.WITHDRAWN_SPEC), "--dataset", str(d)])
    assert rc == A.EXIT_REFUSED
    assert "REFUSING" in capsys.readouterr().out


def test_innocence_the_withdrawal_guard_does_not_refuse_a_spec_that_is_not_withdrawn():
    """The guard must not turn EVERY spec into a refusal. Named for what it
    actually exercises: the default spec is only read for the absence of a
    `withdrawn` block, and the applicability check below runs on a synthetic
    item. It used to be called `..._the_default_spec_is_not_withdrawn_and_runs`,
    which claimed the live spec's own items were exercised here. They are not —
    they are exercised by the test underneath, which had to be written for it.
    """
    spec = json.loads(A.SPEC.read_text(encoding="utf-8"))
    assert "withdrawn" not in spec, "the default spec must be the live one"
    todo, refusals = run([item("01111")], [rec("01111")])
    assert refusals == [] and [i["code"] for i in todo] == ["01111"]


def test_the_live_spec_applies_in_the_world_it_was_written_against():
    """The live spec CANNOT run against the cured catalogue — every item's `was`
    demands TERBUKA/100 and the records now read TERBATAS/0. That is the
    stale-world guard doing its job, not a defect: re-running an applied cure
    must refuse. But it makes the obvious end-to-end test impossible, and the
    cross-family review that observed the refusal was right that nothing else
    covered the gap.

    So: real ancestry from the real catalogue, with ONLY `pma_status` and
    `pma_max_asing` rewound to each item's own `was`. Ancestry and the sibling
    fan-out therefore come from the dataset, not from the spec, and this test
    fails if the spec's `siblings_left_open`, its named 2020 ancestor, or its
    `agreed_by` are wrong about the catalogue.
    """
    spec = json.loads(A.SPEC.read_text(encoding="utf-8"))
    canonical = json.loads(A.CANONICAL.read_text(encoding="utf-8"))
    records = canonical["data"]
    by_code = {str(r["kode_kbli_2025"]): r for r in records}

    codes = {i["code"] for i in spec["items"]}
    siblings = {s for i in spec["items"] for s in i["siblings_left_open"]}
    assert codes and siblings, "a spec with no split heirs would make this vacuous"

    world = []
    for c in sorted(codes | siblings):
        r = dict(by_code[c])
        if c in codes:
            was = next(i["was"] for i in spec["items"] if i["code"] == c)
            r["pma_status"], r["pma_max_asing"] = (
                was["pma_status"],
                was["pma_max_asing"],
            )
            r.pop("pma_official_basis", None)
        world.append(r)

    todo, refusals = A.check(spec, world)
    assert refusals == []
    assert sorted(i["code"] for i in todo) == sorted(codes)


def test_the_live_spec_is_a_clean_noop_against_the_cured_catalogue():
    """Re-running an applied cure verifies every owned field and succeeds
    without scheduling a second write."""
    spec = json.loads(A.SPEC.read_text(encoding="utf-8"))
    canonical = json.loads(A.CANONICAL.read_text(encoding="utf-8"))
    records = canonical["data"]
    todo, refusals = A.check(spec, records)
    assert todo == []
    assert refusals == []


def test_apply_on_a_fully_cured_sandbox_is_a_noop_without_propagation(
    tmp_path, capsys, monkeypatch
):
    spec_payload = json.loads(A.SPEC.read_text(encoding="utf-8"))
    canonical = json.loads(A.CANONICAL.read_text(encoding="utf-8"))
    by_code = {str(r["kode_kbli_2025"]): r for r in canonical["data"]}
    codes = {i["code"] for i in spec_payload["items"]}
    siblings = {s for i in spec_payload["items"] for s in i["siblings_left_open"]}
    payload = {"data": [by_code[c] for c in sorted(codes | siblings)]}
    dataset = tmp_path / "already.json"
    dataset.write_text(json.dumps(payload), encoding="utf-8")
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec_payload), encoding="utf-8")
    before = dataset.read_bytes()
    called = []
    monkeypatch.setattr(A, "propagate", lambda *a, **k: called.append(1) or [])

    rc = A.main(["--apply", "--spec", str(spec_path), "--dataset", str(dataset)])

    assert rc == A.EXIT_OK
    assert dataset.read_bytes() == before
    assert called == []
    assert "clean no-op" in capsys.readouterr().out


def test_the_withdrawal_names_the_codes_whose_evidence_was_short():
    """Not a count: the eleven codes judged under a restricting parent are named,
    so the re-adjudication cannot start from "39 codes, re-check them all" and
    lose which ones were actually compromised."""
    w = json.loads(A.WITHDRAWN_SPEC.read_text(encoding="utf-8"))["withdrawn"]
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
    d = json.loads(A.WITHDRAWN_SPEC.read_text(encoding="utf-8"))["withdrawn"][
        "evidence_delta_2026_08_06"
    ]
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
    r = json.loads(A.WITHDRAWN_SPEC.read_text(encoding="utf-8"))["withdrawn"][
        "readjudication_2026_08_06"
    ]
    v = r["verdicts"]
    assert len(v["REFUSE_SEGMENT"]) == 11
    assert v["PATCH_ZERO"] == ["95299"] and v["REFUSE_BROADER"] == ["42912"]
    assert sum(len(x) for x in v.values()) == 13
    # 01111 is the worked example of the whole defect; it must not drift back
    # into a whole-code reservation without this test failing.
    assert "01111" in v["REFUSE_SEGMENT"]
    # …and the run's own weakness stays written down next to its result.
    assert "handed both lanes the conclusion" in r["declared_weakness"]


# --------------------------------------------------------------------------
# The REPLACEMENT spec — nine codes, and the populations it must keep naming
# --------------------------------------------------------------------------


def test_the_prior_spec_is_the_nine_that_survived_both_rounds():
    """Of the 39 codes the withdrawn patch would have written, nine survive. The
    list is pinned by NAME, not by count: a count alone would let a substitution
    pass, and every one of these publishes a 0%-foreign verdict to clients.

    Pinned against `PRIOR_SPEC` and not `SPEC`: this cure was applied on
    2026-08-06 (#3666) and `SPEC` has since moved on to the split heirs. An
    applied spec stays pinned — "what did we assert about this code, and on
    whose two signatures" outlives the run that asserted it."""
    spec = json.loads(A.PRIOR_SPEC.read_text(encoding="utf-8"))
    codes = [i["code"] for i in spec["items"]]
    assert codes == [
        "10214",
        "10722",
        "22121",
        "41016",
        "41018",
        "41020",
        "95220",
        "95291",
        "95299",
    ]
    assert len(codes) == len(set(codes)), "a code patched twice"
    for i in spec["items"]:
        assert "Lampiran II" in i["locator"] and "Pasal 3(1)(b)" in i["locator"]
        assert len(i["agreed_by"]) == 2, "one lane's word is not an adjudication"


def test_the_prior_spec_names_every_population_it_left_behind():
    """The honest half of the cure. A spec that patches nine out of sixty-eight
    and does not say where the other fifty-nine went is a silent drop."""
    ex = json.loads(A.PRIOR_SPEC.read_text(encoding="utf-8"))["excluded"]
    for key in (
        "refuse_segment_round2",
        "refuse_broader_round2",
        "diverged_round2",
        "unclear_round2",
        "vintage_carry_not_yet_semantically_checked",
        "ocr_illegible",
    ):
        assert ex[key], f"{key} must stay named, not vanish"
    assert ex["disagreements"] > 0 and ex["agreed_unclear"] > 0
    # The six vintage carries are held for a reason that must stay written down:
    # a 1:1 crosswalk edge proves LINEAGE, never that the heir is the same
    # ACTIVITY the annex reserved.
    assert set(ex["vintage_carry_not_yet_semantically_checked"]) == {
        "10307",
        "10308",
        "55106",
        "55201",
        "55203",
        "79903",
    }


def test_guilt_no_patched_code_is_also_on_a_refusal_list():
    """The tripwire that matters: a code cannot be both reserved and refused. If
    a future edit moves one back into `items` without taking it off its refusal
    list, this fails rather than shipping a contradiction to clients."""
    spec = json.loads(A.PRIOR_SPEC.read_text(encoding="utf-8"))
    patched = {i["code"] for i in spec["items"]}
    ex = spec["excluded"]
    refused = set()
    for key in (
        "refuse_segment_round2",
        "refuse_broader_round2",
        "diverged_round2",
        "unclear_round2",
        "vintage_carry_not_yet_semantically_checked",
        "ocr_illegible",
    ):
        refused |= set(ex[key])
    assert not (patched & refused), (
        f"both patched and refused: {sorted(patched & refused)}"
    )


def test_the_prior_spec_supersedes_the_withdrawn_one_by_name():
    """A replacement that does not name what it replaces leaves the next reader
    to guess which of the two files on disk is the live one."""
    spec = json.loads(A.PRIOR_SPEC.read_text(encoding="utf-8"))
    assert A.WITHDRAWN_SPEC.name in spec["supersedes"]
    assert "sibling" in spec["adjudicated"], "round 2's added evidence must be stated"


def test_the_propagation_targets_are_the_ones_the_sync_script_knows():
    """`--apply` is only half a cure if it writes canonical and stops. This pins
    that the tool reaches for the SAME propagation the rest of the family uses,
    rather than a private list that can drift from it."""
    assert A.SYNC_SCRIPT.exists(), "the sync script the cure depends on must exist"
    assert A.SIDECAR_VERSION.exists() and A.SIDECAR_DATASET.exists()
    body = A.SYNC_SCRIPT.read_text(encoding="utf-8")
    assert str(A.SIDECAR_DATASET.relative_to(A.REPO_ROOT)) in body, (
        "the mouth copy this tool re-hashes must be one the sync script actually writes"
    )


def test_guilt_a_non_canonical_dataset_does_not_trigger_a_fleet_sync(
    tmp_path, capsys, monkeypatch
):
    """Found by mutation, not by reasoning: with the withdrawal guard deleted, the
    refusal tests ran on to `propagate()` and shelled out to the REAL repo-wide
    sync. Sandboxing the dataset was not enough — the propagation had its own
    path to production (W96). A run that did not write canonical must not push
    canonical anywhere."""
    called = []
    monkeypatch.setattr(A, "propagate", lambda *a, **k: called.append(1) or [])
    spec = tmp_path / "s.json"
    spec.write_text(
        json.dumps({"items": [item("01111")], "excluded": {}}), encoding="utf-8"
    )
    d = _sandbox_dataset(tmp_path)
    assert A.main(["--apply", "--spec", str(spec), "--dataset", str(d)]) == A.EXIT_OK
    assert called == [], "a scratch dataset must not propagate to the fleet"
    assert "skipping consumer propagation" in capsys.readouterr().out
    # …and the write itself still happened, so this is a scope guard, not a no-op.
    assert json.loads(d.read_text())["data"][0]["pma_max_asing"] == 0
