"""Guilt and innocence for the negative locator.

The dangerous direction on this axis is not symmetric, and the tests are shaped
around that. Calling a RESTRICTED code residual publishes freedom the law does
not grant — that is the one this file spends most of its assertions on. Calling
a residual code restricted is friction, recoverable by reading the page.

Every constant asserted here was MEASURED against the real catalogue and the
vaulted PDF, never carried over from a plan.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

from perpres_body_default_relation import (  # noqa: E402
    BESAR,
    BODY_OTHER_REQUIREMENT,
    BODY_TERTUTUP,
    CannotVerify,
    ancestors,
    annex_codes,
    besar_state,
    body_codes_absent_from_catalogue,
    classify,
    pasal7_review_flags,
    priority_codes,
    load_canonical,
    locate,
    locator_line,
    locators,
    renders_as_open,
    overlay_reconciliation,
    report,
    scales,
)

VAULT_BODY_49 = Path.home() / "nuzantara-vault" / "perpres" / "161562__Perpres Nomor 49 Tahun 2021.pdf"


@pytest.fixture(scope="module")
def canonical():
    return load_canonical()


@pytest.fixture(scope="module")
def annexes():
    return annex_codes()


@pytest.fixture(scope="module")
def prio():
    return priority_codes()


@pytest.fixture(scope="module")
def rep(canonical, annexes, prio):
    return report(canonical, *annexes, prio)


# --------------------------------------------------------------------------
# The readers, pinned. A probe that silently returns nothing reports a clean
# catalogue, so each one is proven on a POSITIVE case before it is trusted.
# --------------------------------------------------------------------------

def test_ancestors_reads_the_codes_key_not_the_block_as_a_list(canonical):
    """`bps_2020_ancestors` is a DICT carrying `codes` plus provenance.

    Read as a list it yields an empty set for all 1,559 and the annex join finds
    nothing — the probe measures its own breakage and calls the catalogue clean.
    That happened on the first pass; this is the pin.
    """
    assert ancestors(canonical["55203"]) == {"55193"}
    assert ancestors({"bps_2020_ancestors": {"codes": []}}) == set()
    assert ancestors({}) == set()


def test_scales_reads_the_list_valued_skala_usaha(canonical):
    """`skala_usaha` is a LIST on each `per_skala` entry, never a string."""
    assert BESAR in scales(canonical["56101"])
    assert scales({"per_skala": [{"skala_usaha": ["Mikro", "Kecil"]}]}) == {"Mikro", "Kecil"}
    assert scales({"per_skala": []}) == set()


# --------------------------------------------------------------------------
# GUILT — the direction that publishes freedom the law does not grant
# --------------------------------------------------------------------------

def test_a_code_named_only_through_its_2020_ancestor_is_not_residual(canonical, annexes, prio):
    """`55203` (Aktivitas Vila) is absent from the annexes BY ITS OWN CODE; its
    2020 predecessor `55193` is in Lampiran II. Joining on identity alone would
    hand it the body's open default.
    """
    umkm, caps = annexes
    assert "55203" not in umkm and "55203" not in caps
    bucket, ev = classify("55203", canonical["55203"], umkm, caps, prio)
    assert bucket == "named-in-annex"
    assert ev["lampiran_ii"] == ["55193"]
    assert ev["via_ancestor_only"] is True


def test_the_ancestor_join_is_load_bearing_for_a_hundred_codes(canonical, annexes, prio):
    """Not one special case: measured, 102 codes reach an annex ONLY through the
    crosswalk. A regression that drops the join turns all of them open.

    The expected set is derived here WITHOUT calling `ancestors()`. Using the
    module's own reader on both sides would compute the same value twice and
    agree with itself — a broken reader would still produce a matching 102.
    """
    umkm, caps = annexes
    annex = umkm | caps
    via_ancestor_only = {
        code for code, rec in canonical.items()
        if code not in annex
        and {str(c) for c in ((rec.get("bps_2020_ancestors") or {}).get("codes") or [])} & annex
    }
    assert len(via_ancestor_only) == 102
    assert {"55203", "55201", "96210", "96220"} <= via_ancestor_only
    # And the module must actually route them: not one may come back RESIDUAL,
    # which is the only failure that publishes an open default. `47221` lands in
    # `body-other-requirement` rather than `named-in-annex` because the body
    # outranks an annex — a stricter equality here would have failed on correct
    # precedence, i.e. asserted the wrong thing about the right behaviour.
    routed = {code: classify(code, canonical[code], umkm, caps, prio)[0] for code in via_ancestor_only}
    assert not [c for c, b in routed.items() if b.startswith("residual")]
    assert set(routed.values()) == {"named-in-annex", "body-other-requirement"}


def test_a_body_tertutup_code_is_located_by_the_body_not_by_absence(canonical, annexes, prio):
    """The `BODY_TERTUTUP` branch, which nothing else in this file exercises.
    `11010`/`11020` are named tertutup by Pasal 2(2)(b) and are in no annex.
    """
    umkm, caps = annexes
    for code in ("11010", "11020"):
        assert code not in umkm and code not in caps
        bucket, ev = classify(code, canonical[code], umkm, caps, prio)
        assert bucket == "body-tertutup"
        assert "Pasal 2 ayat (2) huruf b" in ev["body"]


def test_a_string_where_a_list_belongs_raises_instead_of_iterating_characters(canonical):
    """`"55193"` iterated yields five one-character "codes"; `"Besar"` yields
    five letters and the Besar test silently fails forever. Both are shapes the
    upstream producer could emit, and both would read as a clean catalogue.
    """
    with pytest.raises(CannotVerify):
        ancestors({"bps_2020_ancestors": {"codes": "55193"}})
    with pytest.raises(CannotVerify):
        scales({"per_skala": [{"skala_usaha": BESAR}]})


def test_a_body_named_code_is_never_treated_as_residual(canonical, annexes, prio):
    """`46333` and `47221` are named in the BODY (Pasal 6(3a)), not in an annex.
    Reading "absent from both annexes" as "residual" would give the alcohol
    trade the open default.
    """
    umkm, caps = annexes
    for code in ("46333", "47221"):
        bucket, ev = classify(code, canonical[code], umkm, caps, prio)
        assert bucket == "body-other-requirement"
        assert ev["body"] and "Pasal 6 ayat (3a)" in ev["body"]


def test_an_empty_annex_is_cannot_verify_not_a_catalogue_of_open_codes(tmp_path):
    """The empty set disguises itself as everything.

    This module asks "is the code ABSENT from the annexes?", so a missing or
    empty input makes all 1,559 look residual and the report reads "every code
    is open by default" — maximally wrong, maximally confident, exit 0.
    """
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"rows": []}))
    real = Path(_FILIERA_DIR).parents[1] / "data" / "kbli-filiera" / "perpres-foreign-caps.json"
    with pytest.raises(CannotVerify):
        annex_codes(umkm_path=empty, caps_path=real)
    with pytest.raises(CannotVerify):
        annex_codes(umkm_path=tmp_path / "nope.json", caps_path=real)


# --------------------------------------------------------------------------
# INNOCENCE — a genuinely unnamed code keeps the body's default
# --------------------------------------------------------------------------

def test_a_genuinely_unnamed_code_with_a_besar_row_is_residual_and_open(canonical, annexes, prio):
    """`56101` (restaurant) — the highest-traffic question this product gets.
    Named by nothing, and its scales include Besar, so Pasal 3(1)(d)+(2) leaves
    it open to all investors. The guard must not fire here.
    """
    umkm, caps = annexes
    bucket, ev = classify("56101", canonical["56101"], umkm, caps, prio)
    assert bucket == "residual-besar-observed"
    assert ev["lampiran_ii"] == [] and ev["lampiran_iii"] == [] and ev["body"] is None
    assert ev["besar"] == "observed"


def test_the_residual_bucket_is_the_bulk_of_the_catalogue(rep):
    """Innocence at population scale: if the locator over-fired, this collapses."""
    assert rep["buckets"]["residual-besar-observed"] == 882


# --------------------------------------------------------------------------
# THREE STATES, NEVER TWO — a gap in our data is not a bar in the law
# --------------------------------------------------------------------------

def test_an_absent_per_skala_is_unobserved_not_an_absence_of_besar(canonical):
    """217 records carry no scale data at all (the OSS ruang-lingkup 404s).
    Collapsing them into "no Besar" would report OUR gap as the law's bar — and
    it is exactly the reading 17 of the overlay's closures already rest on.
    """
    assert besar_state({"per_skala": []}) == "unobserved"
    assert besar_state({"per_skala": [{"skala_usaha": ["Mikro"]}]}) == "absent"
    assert besar_state({"per_skala": [{"skala_usaha": ["Mikro", BESAR]}]}) == "observed"
    unobserved = [c for c, r in canonical.items() if besar_state(r) == "unobserved"]
    assert len(unobserved) == 217


def test_the_besar_axis_partitions_every_record(rep):
    assert sum(rep["besar_axis"].values()) == rep["codes"] == 1559
    assert rep["besar_axis"] == {"observed": 1318, "absent": 24, "unobserved": 217}


# --------------------------------------------------------------------------
# THE TWO AXES ARE SEPARATE — the defect the first draft had
# --------------------------------------------------------------------------

def test_a_code_named_in_an_annex_still_reports_its_besar_state(canonical, annexes, prio):
    """The first draft made the locator a partition, so for the ten codes that
    are BOTH annex-named and Besar-less the scale question silently vanished —
    and those ten are villa, homestay, hair salon, beauty care: the questions
    this agency is asked daily. Locator and eligibility are two axes.
    """
    umkm, caps = annexes
    _, ev = classify("55203", canonical["55203"], umkm, caps, prio)
    assert ev["lampiran_ii"] == ["55193"] and ev["besar"] == "absent"


def test_the_barred_but_open_list_reads_across_every_bucket(rep):
    """Measured: 23 codes publish TERBUKA while their own scale data names no
    Besar row. A locator-partitioned reading found only 14.
    """
    rows = pasal7_review_flags(rep)
    assert len(rows) == 23
    codes = {r["code"] for r in rows}
    assert {"55203", "55201", "96210", "96220"} <= codes  # annex-named AND Besar-less
    assert {"56304", "70201", "86995"} <= codes           # residual AND Besar-less
    assert all(r["besar"] == "absent" for r in rows)


def test_open_means_what_the_RENDERER_calls_open_not_the_TERBUKA_label():
    """`kbli-data.server.ts::mapPmaStatus` returns "restricted" for TERBATAS,
    "closed" for TERTUTUP and **"open" for everything else** — a null included.
    A detector filtering on `== "TERBUKA"` would be blind to precisely the codes
    the page treats most generously. The two readings coincide on today's data;
    this pins the one that will still be right when they stop coinciding.
    """
    assert renders_as_open({"pma_status": "TERBUKA"}) is True
    assert renders_as_open({"pma_status": None}) is True
    assert renders_as_open({}) is True
    assert renders_as_open({"pma_status": "TERBATAS"}) is False
    assert renders_as_open({"pma_status": "TERTUTUP"}) is False


def test_a_null_status_with_no_besar_row_is_caught_not_skipped(rep):
    """Guilt for the line above, on the real report shape: inject a record the
    page would render open via the null branch and require it to surface.
    """
    doctored = json.loads(json.dumps({k: v for k, v in rep.items() if k != "detail"}))
    doctored["detail"] = {"residual-besar-absent": [
        {"code": "99999", "pma_status": None, "pma_max_asing": None,
         "judul": "synthetic", "besar": "absent", "scales": ["Mikro"], "lampiran_ii": []}
    ]}
    assert [r["code"] for r in pasal7_review_flags(doctored)] == ["99999"]


def test_a_code_can_carry_more_than_one_locator(canonical, annexes, prio):
    """`47221` is under Pasal 6(3a) in the body AND reaches Lampiran II through
    its 2020 ancestor `47911`. Returning only the winning locator would hide the
    second from whoever reads the row.
    """
    umkm, caps = annexes
    ev = locate("47221", canonical["47221"], umkm, caps, prio)
    assert ev["body"] is not None
    assert ev["lampiran_ii"] == ["47911"]


# --------------------------------------------------------------------------
# THE HARD-CODED BODY LISTS — pinned to the instrument, and to the catalogue
# --------------------------------------------------------------------------

def test_body_codes_the_catalogue_lacks_are_reported_not_absorbed(canonical):
    """`11031` and `47826` are named by the body and are NOT among the 1,559
    (47826 survives as a 2020 ancestor of 47221). A hard-coded list whose
    members quietly fail to exist is the phantom-code class.
    """
    assert body_codes_absent_from_catalogue(canonical) == ["11031", "47826"]


# How a digit can render in THIS document's text layer. Measured on the six
# occurrences, not carried over: the body prints `46333` as `a6333` (4 -> a) and
# splits `11031` as `1 1031`. `a` is deliberately NOT added to the annex readers'
# shared SUBSTITUTIONS table — it is a very common letter and widening a table
# used to decode 180 annex rows to accommodate one body glyph would trade a
# failing test for silent over-matching where it costs something.
_BODY_GLYPHS = {"0": "0oO", "1": "1lLiI", "2": "2Z", "4": "4a", "5": "5Ss", "8": "8B"}


def _tolerant(code: str) -> str:
    return r"\s*".join(f"[{_BODY_GLYPHS.get(d, d)}]" for d in code)


def test_every_body_code_is_findable_in_the_vaulted_instrument():
    """The six constants are transcribed, so they are checked against the PDF.

    NOT by grepping the bare digits: the body's text layer carries the same
    deterministic corruption as the annexes, so `46333` is simply not present as
    digits and a naive check reads as if the constant were invented. It is the
    check that must tolerate the corruption, not the constant that must bend.

    The tolerance is bounded on both sides so it cannot go vacuous: each code
    must appear EXACTLY once, and an invented neighbour must appear zero times.
    """
    if not VAULT_BODY_49.is_file():
        pytest.skip(f"{VAULT_BODY_49} absent — CANNOT VERIFY, not verified. "
                    "Run: python scripts/kbli_filiera/vault_fetch_perpres.py")
    proc = subprocess.run(["pdftotext", "-layout", str(VAULT_BODY_49), "-"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        pytest.skip(f"pdftotext unavailable ({proc.returncode}) — CANNOT VERIFY")
    text = proc.stdout

    for code in sorted(BODY_TERTUTUP | BODY_OTHER_REQUIREMENT):
        hits = re.findall(_tolerant(code), text)
        assert len(hits) == 1, f"{code}: expected exactly one occurrence, found {hits}"

    # NEGATIVE CONTROL — the tolerant pattern must still be able to say no.
    for invented in ("46334", "11032", "47827"):
        assert re.findall(_tolerant(invented), text) == [], f"{invented} matched a document that lacks it"


def test_the_body_lists_carry_their_article(canonical):
    """An entry without its article is an assertion with no locator behind it —
    the exact defect this module exists to close for the other 1,288 codes.
    """
    assert all("Pasal 2 ayat (2) huruf b" in v for v in BODY_TERTUTUP.values())
    assert all("Pasal 6 ayat (3a)" in v for v in BODY_OTHER_REQUIREMENT.values())


# --------------------------------------------------------------------------
# THE OVERLAY ALREADY TOOK THIS READING — on what evidence
# --------------------------------------------------------------------------

def test_the_overlay_closes_only_adjudicated_reservations(canonical):
    ov = overlay_reconciliation(canonical)
    assert ov["overlay_closed"] == 7
    assert len(ov["corroborated_by_scales"]) == 7
    assert ov["closed_on_empty_scales"] == []
    assert ov["closed_with_a_besar_row"] == []


def test_the_overlay_reports_absent_besar_codes_not_closed_as_reservations(canonical):
    ov = overlay_reconciliation(canonical)
    not_closed = {r["code"]: r for r in ov["absent_besar_not_closed"]}
    assert set(not_closed) == {
        "38110", "43110", "55202", "55209", "55300", "56102", "56304",
        "56306", "70201", "73300", "74199", "79110", "79901", "79902",
        "86995", "93114", "93119",
    }
    assert not_closed["93114"]["l4_bali"] == "APERTO_BALI_RISCHIO_ALTO"


# --------------------------------------------------------------------------
# CONSERVATION AND CONTRACT
# --------------------------------------------------------------------------

def test_no_record_is_lost_between_the_catalogue_and_the_buckets(rep):
    assert sum(rep["buckets"].values()) == rep["codes"] == 1559


def test_the_reporter_writes_nothing_and_exits_zero_while_divergences_stand(tmp_path):
    """A reporter that gated would re-label client-facing pages on a reading
    nobody made (Legge 5). And a persisted join would be a fourth source of
    truth that goes stale the moment an input moves.
    """
    repo_root = Path(_FILIERA_DIR).parents[1]
    before = {p: p.stat().st_mtime_ns for p in (repo_root / "data" / "kbli-filiera").glob("*.json")}
    proc = subprocess.run(
        [sys.executable, str(Path(_FILIERA_DIR) / "perpres_body_default_relation.py"), "--json"],
        capture_output=True, text=True, cwd=tmp_path, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["codes"] == 1559
    after = {p: p.stat().st_mtime_ns for p in (repo_root / "data" / "kbli-filiera").glob("*.json")}
    assert before == after, "the reporter touched a data file"
    assert not list(tmp_path.iterdir()), "the reporter left residue in its cwd"


# --------------------------------------------------------------------------
# LAMPIRAN I — the annex the first version omitted, and what that cost
# --------------------------------------------------------------------------

def test_a_priority_code_is_not_cited_under_the_residual_article(canonical, annexes, prio):
    """`01271` (Pertanian Kopi) is a `Bidang Usaha Prioritas`, Pasal 3(1)(a).

    The first version checked the body's lists, Lampiran II and Lampiran III and
    called everything else residual — so it cited **Pasal 3(1)(d)** for 175
    codes that are category (a). Priority restricts nobody, so no ownership
    verdict was wrong; the LOCATOR was, and the locator is this module's entire
    product. Caught by an independent cross-family legal review, not by a test.
    """
    umkm, caps = annexes
    bucket, ev = classify("01271", canonical["01271"], umkm, caps, prio)
    assert bucket == "priority-lampiran-i"
    assert ev["basis"] == "Pasal 3 ayat (1) huruf a"
    assert ev["lampiran_ii"] == [] and ev["lampiran_iii"] == []


def test_a_restriction_outranks_a_priority_listing(canonical, annexes, prio):
    """46 codes are in BOTH Lampiran I and Lampiran II — `01111` (jagung) among
    them. An incentive never cancels a reservation, so the restricting annex
    must win the locator; reporting it as merely "priority" would drop the bar.
    """
    umkm, caps = annexes
    bucket, ev = classify("01111", canonical["01111"], umkm, caps, prio)
    assert bucket == "named-in-annex"
    assert ev["lampiran_i"] and ev["lampiran_ii"]  # both are still visible


def test_the_priority_annex_moved_175_codes_out_of_the_residual_bucket(rep):
    """The size of the omission, pinned. `residual-besar-observed` was 1055 and
    is 882; a regression that drops the Lampiran I read restores the wrong 1055
    and every one of those rows starts citing the wrong article again.
    """
    assert rep["buckets"]["priority-lampiran-i"] == 175
    assert rep["annex_codes"]["lampiran_i"] == 194


def test_a_missing_priority_artifact_is_cannot_verify_not_a_bigger_residual(tmp_path):
    """Same shape as the empty-annex guard: silence here does not read as an
    error, it reads as 175 more residual codes with a confident wrong citation.
    """
    with pytest.raises(CannotVerify):
        priority_codes(path=tmp_path / "nope.json")
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"codes": []}))
    with pytest.raises(CannotVerify):
        priority_codes(path=empty)


def test_pasal7_flags_are_a_review_queue_and_the_name_says_so():
    """The rename is the correction, so it is pinned.

    `pasal7_review_flags` replaced `foreign_barred_but_published_open`. Pasal
    7(1) conditions the INVESTOR ("Penanam Modal asing hanya dapat melakukan
    kegiatan usaha pada Usaha Besar"), not the activity, and `per_skala` is OSS
    licensing data rather than a determination that the activity cannot be run
    at Besar scale. A module-level function whose name asserts a bar would put
    that assertion into every caller.
    """
    import perpres_body_default_relation as mod
    assert not hasattr(mod, "foreign_barred_but_published_open")
    assert "REVIEW FLAG" in mod.pasal7_review_flags.__doc__
    assert "conditions the INVESTOR, not the ACTIVITY" in mod.pasal7_review_flags.__doc__


# --------------------------------------------------------------------------
# THE CATALOGUE ALREADY HAS A "PRIORITY" FIELD, AND IT TRACKS SOMETHING ELSE
# --------------------------------------------------------------------------

def test_pma_prioritas_disagrees_with_the_operative_annex_in_both_directions(canonical, prio):
    """`pma_prioritas` asserts Pasal 3(1)(a) from an unknown source.

    Measured against `Perpres 49/2021 Lampiran I`, the operative priority list:
    the catalogue flags **18** codes, the annex names **194**, and they agree on
    **6**. Twelve flagged codes are absent from the annex entirely — checked
    line-by-line against the vaulted PDF with positive and negative controls,
    not by a whole-document search (joining a 70-page layout into one string
    fuses adjacent columns and manufactures five-digit matches; that probe first
    reported `35111` as present, and it is not).

    Latent rather than visible: `isPriority` is carried through
    `kbli-data.ts:406`, `kbli-data.server.ts:302` and two type modules and has
    **no render site**, so no page states it today (family #2, exists != armed).
    Pinned so the divergence cannot drift silently in either direction, and so
    that whoever wires a priority badge reads this first and takes the set from
    the instrument rather than from the flag.
    """
    flagged = {c for c, r in canonical.items() if r.get("pma_prioritas")}
    reached = {c for c, r in canonical.items() if ({c} | ancestors(r)) & prio}
    assert len(flagged) == 18
    assert len(flagged & reached) == 6
    assert len(flagged - reached) == 12
    assert len(reached - flagged) == 219


# --------------------------------------------------------------------------
# THE EMITTED ARTIFACT — and proof that the gate guarding it bites
# --------------------------------------------------------------------------

def test_the_citation_names_an_article_for_every_code(rep):
    """`pma_source` says "Perpres 10/2021, 49/2021" on all 1,559 records — the
    instrument, never the article. A citation that did the same would be the
    same blanket attribution wearing a new key.
    """
    built = locators(rep)
    assert built["codes"] == 1559
    cites = {v["cite"] for v in built["locators"].values()}
    assert len(cites) > 1
    assert all("Pasal" in c or "Lampiran" in c for c in cites)


def test_the_citation_says_when_a_code_is_named_through_its_predecessor(rep):
    """A reader who greps the annex for `55203` finds nothing — the annex names
    `55193`. Without the "via" clause the citation looks invented."""
    built = locators(rep)["locators"]
    assert "via KBLI-2020 55193" in built["55203"]["cite"]
    assert "via" not in built["01111"]["cite"]  # named under its own code


def test_the_citation_never_carries_the_oss_scale_axis(rep):
    """Pasal 7(1) conditions the INVESTOR, and an absent Besar row is licensing
    data rather than a finding about the activity. Folding it into a citation
    would print a bar the instrument does not state — the exact overreach an
    independent review caught upstream of here.
    """
    built = locators(rep)["locators"]
    absent = [c for c, v in built.items() if v["besar"] == "absent"]
    assert len(absent) == 24
    for code in absent:
        assert "Besar" not in built[code]["cite"]
        assert "Pasal 7" not in built[code]["cite"]


def test_check_artifact_fails_on_a_drifted_file(tmp_path, monkeypatch, rep):
    """MUTATION PROOF. A gate nobody has seen fail is decoration (W108).

    Writes a correct artifact, mutates one citation, and requires the checker to
    exit non-zero — because the page renders whatever this file says, so a
    silent drift would put a wrong article on a public page.
    """
    import perpres_body_default_relation as mod
    out = tmp_path / "perpres-locators.json"
    monkeypatch.setattr(mod, "LOCATORS_OUT", out)

    assert mod.main(["--emit"]) == 0
    assert mod.main(["--check-artifact"]) == 0, "a freshly emitted artifact must pass"

    payload = json.loads(out.read_text())
    payload["locators"]["56101"]["cite"] = "Perpres 49/2021 Lampiran III"
    out.write_text(json.dumps(payload, ensure_ascii=False))
    assert mod.main(["--check-artifact"]) != 0, "a drifted artifact must fail"

    out.unlink()
    assert mod.main(["--check-artifact"]) != 0, "a missing artifact must fail, not pass"
