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
    foreign_barred_but_published_open,
    load_canonical,
    locate,
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
def rep(canonical, annexes):
    return report(canonical, *annexes)


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

def test_a_code_named_only_through_its_2020_ancestor_is_not_residual(canonical, annexes):
    """`55203` (Aktivitas Vila) is absent from the annexes BY ITS OWN CODE; its
    2020 predecessor `55193` is in Lampiran II. Joining on identity alone would
    hand it the body's open default.
    """
    umkm, caps = annexes
    assert "55203" not in umkm and "55203" not in caps
    bucket, ev = classify("55203", canonical["55203"], umkm, caps)
    assert bucket == "named-in-annex"
    assert ev["lampiran_ii"] == ["55193"]
    assert ev["via_ancestor_only"] is True


def test_the_ancestor_join_is_load_bearing_for_a_hundred_codes(canonical, annexes):
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
    routed = {code: classify(code, canonical[code], umkm, caps)[0] for code in via_ancestor_only}
    assert not [c for c, b in routed.items() if b.startswith("residual")]
    assert set(routed.values()) == {"named-in-annex", "body-other-requirement"}


def test_a_body_tertutup_code_is_located_by_the_body_not_by_absence(canonical, annexes):
    """The `BODY_TERTUTUP` branch, which nothing else in this file exercises.
    `11010`/`11020` are named tertutup by Pasal 2(2)(b) and are in no annex.
    """
    umkm, caps = annexes
    for code in ("11010", "11020"):
        assert code not in umkm and code not in caps
        bucket, ev = classify(code, canonical[code], umkm, caps)
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


def test_a_body_named_code_is_never_treated_as_residual(canonical, annexes):
    """`46333` and `47221` are named in the BODY (Pasal 6(3a)), not in an annex.
    Reading "absent from both annexes" as "residual" would give the alcohol
    trade the open default.
    """
    umkm, caps = annexes
    for code in ("46333", "47221"):
        bucket, ev = classify(code, canonical[code], umkm, caps)
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

def test_a_genuinely_unnamed_code_with_a_besar_row_is_residual_and_open(canonical, annexes):
    """`56101` (restaurant) — the highest-traffic question this product gets.
    Named by nothing, and its scales include Besar, so Pasal 3(1)(d)+(2) leaves
    it open to all investors. The guard must not fire here.
    """
    umkm, caps = annexes
    bucket, ev = classify("56101", canonical["56101"], umkm, caps)
    assert bucket == "residual-besar-observed"
    assert ev["lampiran_ii"] == [] and ev["lampiran_iii"] == [] and ev["body"] is None
    assert ev["besar"] == "observed"


def test_the_residual_bucket_is_the_bulk_of_the_catalogue(rep):
    """Innocence at population scale: if the locator over-fired, this collapses."""
    assert rep["buckets"]["residual-besar-observed"] == 1055


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

def test_a_code_named_in_an_annex_still_reports_its_besar_state(canonical, annexes):
    """The first draft made the locator a partition, so for the ten codes that
    are BOTH annex-named and Besar-less the scale question silently vanished —
    and those ten are villa, homestay, hair salon, beauty care: the questions
    this agency is asked daily. Locator and eligibility are two axes.
    """
    umkm, caps = annexes
    _, ev = classify("55203", canonical["55203"], umkm, caps)
    assert ev["lampiran_ii"] == ["55193"] and ev["besar"] == "absent"


def test_the_barred_but_open_list_reads_across_every_bucket(rep):
    """Measured: 23 codes publish TERBUKA while their own scale data names no
    Besar row. A locator-partitioned reading found only 14.
    """
    rows = foreign_barred_but_published_open(rep)
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
    assert [r["code"] for r in foreign_barred_but_published_open(doctored)] == ["99999"]


def test_a_code_can_carry_more_than_one_locator(canonical, annexes):
    """`47221` is under Pasal 6(3a) in the body AND reaches Lampiran II through
    its 2020 ancestor `47911`. Returning only the winning locator would hide the
    second from whoever reads the row.
    """
    umkm, caps = annexes
    ev = locate("47221", canonical["47221"], umkm, caps)
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

def test_the_overlay_closes_seventeen_codes_on_an_empty_per_skala(canonical):
    ov = overlay_reconciliation(canonical)
    assert ov["overlay_closed"] == 39
    assert len(ov["corroborated_by_scales"]) == 22
    assert len(ov["closed_on_empty_scales"]) == 17
    assert ov["closed_with_a_besar_row"] == []


def test_the_overlay_leaves_open_a_code_whose_scales_lack_besar(canonical):
    """The same rule, misapplied in the OTHER direction: `93114` is published
    APERTO on evidence the overlay treats as closing on 22 other codes.
    """
    ov = overlay_reconciliation(canonical)
    not_closed = {r["code"]: r for r in ov["absent_besar_not_closed"]}
    assert set(not_closed) == {"79110", "93114"}
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
