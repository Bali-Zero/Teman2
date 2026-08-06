"""Guilt, innocence and REFUSAL for the mechanical stat-card cure.

This module writes the canonical KBLI dataset, so the tests that matter most
are the ones about what it must NOT do: not touch a lawfully Bali-scoped cell,
not touch prose, and not write at all when the result would be half-cured.

The dangerous direction here is not a missed cell. It is a cell rewritten from
a misread record, because the output looks authoritative — a number in a stat
card is the thing a client acts on money with, and it carries no hedge.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_FILIERA = str(Path(__file__).resolve().parents[1])
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)

import cure_editorial_cells_from_record as C  # noqa: E402
import editorial_record_conformance as E  # noqa: E402


def rec(code="01111", status="TERBATAS", cap=49, cells=None, body=""):
    return {
        "kode_kbli_2025": code,
        "pma_status": status,
        "pma_max_asing": cap,
        "intel_2026": {
            "editorial": {
                "headline": "",
                "standfirst": "",
                "body": body,
                "byTheNumbers": cells or [],
            }
        },
    }


def plan(record):
    return C.plan_for(record, E.classify(record))


# --------------------------------------------------------------------------
# GUILT — the copy is restored from the field it copies
# --------------------------------------------------------------------------


def test_guilt_a_stale_ceiling_is_rewritten_to_the_record_cap():
    r = rec(cap=49, cells=[{"label": "Foreign-ownership ceiling", "value": "100%"}])
    edits, refusals = plan(r)
    assert refusals == []
    assert [(e["was"], e["now"]) for e in edits] == [("100%", "49%")]


def test_guilt_a_stale_status_is_rewritten_to_the_record_status():
    r = rec(status="TERBATAS", cells=[{"label": "National PMA status", "value": "TERBUKA"}])
    edits, _ = plan(r)
    assert [(e["was"], e["now"]) for e in edits] == [("TERBUKA", "TERBATAS")]


def test_a_zero_ceiling_is_written_as_zero_not_softened_into_words():
    """`0%` reads oddly and is accurate. Writing "Not permitted" instead would
    be authoring a sentence, which is the other module's job and Legge 5."""
    r = rec(cap=0, cells=[{"label": "Foreign ownership ceiling", "value": "100%"}])
    assert plan(r)[0][0]["now"] == "0%"


# --------------------------------------------------------------------------
# INNOCENCE — what it must leave exactly where it is
# --------------------------------------------------------------------------


def test_innocence_a_bali_scoped_cell_is_never_rewritten():
    """The 132-cell trap. A closed Bali layer over an open national record is
    lawful, and 'correcting' it to the national value would destroy the one
    fact the page exists to convey."""
    r = rec(
        status="TERBUKA",
        cap=100,
        cells=[{"label": "Bali PMA status", "value": "TERTUTUP"}],
    )
    edits, refusals = plan(r)
    assert (edits, refusals) == ([], [])


def test_innocence_a_cell_that_already_agrees_is_untouched():
    r = rec(cap=49, cells=[{"label": "Foreign-ownership ceiling", "value": "49%"}])
    assert plan(r) == ([], [])


def test_innocence_an_unflagged_cell_on_a_flagged_record_is_untouched():
    """A record can hold one stale cell and several correct ones. The pass is
    driven by the detector's per-cell verdict, not by 'this record is dirty'."""
    r = rec(
        cap=49,
        cells=[
            {"label": "Foreign-ownership ceiling", "value": "100%"},
            {"label": "Minimum paid-up capital", "value": "IDR 10 billion"},
            {"label": "Risk category", "value": "Tinggi"},
        ],
    )
    edits, _ = plan(r)
    assert [e["label"] for e in edits] == ["Foreign-ownership ceiling"]


# --------------------------------------------------------------------------
# REFUSAL — ambiguity is named, never guessed
# --------------------------------------------------------------------------


def test_refusal_a_ceiling_holding_two_percentages_is_not_guessed_at():
    r = rec(cap=49, cells=[{"label": "Foreign-ownership ceiling", "value": "100% (was 67%)"}])
    edits, refusals = plan(r)
    assert edits == []
    assert len(refusals) == 1 and "cannot rewrite one" in refusals[0]


def test_refusal_a_non_numeric_cap_is_not_stamped_into_a_cell():
    """`special` is a real cap in this catalogue. Writing `special%` would be
    an invented value wearing a number's clothes."""
    r = rec(cap="special", cells=[{"label": "Foreign-ownership ceiling", "value": "100%"}])
    r["pma_status"] = "TERBATAS"
    verdict = E.classify(r)
    # the detector cannot flag it either — pinned so the two stay consistent
    assert verdict["ceiling_cells"] == []
    edits, refusals = C.plan_for(
        r, {"ceiling_cells": [{"label": "Foreign-ownership ceiling"}], "status_cells": []}
    )
    assert edits == []
    assert "not a number" in refusals[0]


# --------------------------------------------------------------------------
# THE WRITE PATH — dry-run writes nothing, a half-cure writes nothing
# --------------------------------------------------------------------------


def _write(tmp_path: Path, records: list[dict]) -> Path:
    p = tmp_path / "canonical.json"
    p.write_text(json.dumps({"data": records}, ensure_ascii=False), encoding="utf-8")
    return p


def test_dry_run_writes_nothing(tmp_path: Path):
    p = _write(tmp_path, [rec(cap=49, cells=[{"label": "Foreign-ownership ceiling", "value": "100%"}])])
    before = p.read_bytes()
    assert C.run(p, apply=False) == 0
    assert p.read_bytes() == before


def test_it_refuses_to_write_when_a_stale_cell_would_survive(tmp_path: Path, monkeypatch):
    """A half-cure is worse than a refusal: the page becomes consistent enough
    to be believed while still wrong where it counts. Simulated by making the
    planner blind to one cell, which is what any future predicate drift does."""
    p = _write(tmp_path, [rec(cap=49, cells=[{"label": "Foreign-ownership ceiling", "value": "100%"}])])
    before = p.read_bytes()
    monkeypatch.setattr(C, "plan_for", lambda record, verdict: ([], []))
    assert C.run(p, apply=True) == 1
    assert p.read_bytes() == before, "it must not write when it refuses"


def test_it_refuses_to_write_if_the_prose_verdict_moved(tmp_path: Path, monkeypatch):
    """The pass must not author. If patching a cell changed which codes need an
    author, something rewrote a string and the run is abandoned."""
    records = [rec(cap=49, cells=[{"label": "Foreign-ownership ceiling", "value": "100%"}])]
    p = _write(tmp_path, records)
    before = p.read_bytes()

    real_plan = C.plan_for

    def sneaky(record, verdict):
        edits, refusals = real_plan(record, verdict)
        record["intel_2026"]["editorial"]["body"] = (
            "This activity is nationally open to full foreign ownership."
        )
        return edits, refusals

    monkeypatch.setattr(C, "plan_for", sneaky)
    assert C.run(p, apply=True) == 1
    assert p.read_bytes() == before


def test_apply_writes_and_the_result_reports_zero_stale_cells(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(C, "run_sync_script", lambda: None)
    monkeypatch.setattr(C, "reconcile_sidecar", lambda path: False)
    p = _write(
        tmp_path,
        [
            rec(code="51101", cap=49, cells=[{"label": "Foreign-ownership ceiling", "value": "100%"}]),
            rec(code="79122", cap=0, status="TERBATAS",
                cells=[{"label": "National PMA status", "value": "TERBUKA"}]),
        ],
    )
    assert C.run(p, apply=True) == 0
    after = json.loads(p.read_text(encoding="utf-8"))["data"]
    assert E.report(after)["mechanically_correctable"]["codes"] == []
    cells = {r["kode_kbli_2025"]: r["intel_2026"]["editorial"]["byTheNumbers"][0]["value"]
             for r in after}
    assert cells == {"51101": "49%", "79122": "TERBATAS"}


# --------------------------------------------------------------------------
# THE LIVE CATALOGUE
# --------------------------------------------------------------------------


def test_the_live_catalogue_holds_no_stale_cell_and_none_it_could_not_rewrite():
    """The standing guard, and it is worth more than the backlog it replaced.

    This test used to pin "38 cells on 31 codes". That number was a measure of
    debt, and debt is exactly what a pin should not preserve: it goes green
    again the moment someone cures it and tells you nothing afterwards. The cure
    has now run, so the assertion is the property we actually want to keep —
    the catalogue holds NO stale stat card, and no card whose shape this pass
    would have to guess at.

    A failure here has two readings and both need a human eye: either a new
    contradiction was authored, or a cure moved a field and left the card
    behind, which is precisely how the original 31 came to exist.
    """
    records = E.load_records()
    edits, refusals = [], []
    for record in records:
        verdict = E.classify(record)
        if verdict["ceiling_cells"] or verdict["status_cells"]:
            e, r = C.plan_for(record, verdict)
            edits += e
            refusals += r
    assert refusals == [], f"the live catalogue holds a cell this cannot rewrite: {refusals}"
    assert edits == [], (
        "a stat card disagrees with its record again — either newly authored, or "
        f"a cure moved a field and left the card behind: "
        f"{[(e['code'], e['label'], e['was']) for e in edits]}"
    )


def test_the_live_run_writes_the_real_catalogue_into_a_copy_and_changes_only_cells(
    tmp_path: Path, monkeypatch
):
    """The whole cure, end to end, on the real 1,559 records — into a COPY.

    Three properties at once, and each has failed in some cure in this
    directory before: every stale cell is gone, the authored backlog is
    untouched, and NOTHING outside `byTheNumbers` moved. The third is checked by
    stripping the cells out of both documents and comparing what is left, which
    is the only version of "it only touched cells" that a reader can trust —
    counting edits proves what the pass INTENDED, not what it wrote.
    """
    monkeypatch.setattr(C, "run_sync_script", lambda: None)
    monkeypatch.setattr(C, "reconcile_sidecar", lambda path: False)

    original = json.loads(E.CANONICAL.read_text(encoding="utf-8"))
    p = tmp_path / "canonical.json"
    p.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

    authored_before = E.report(original["data"])["needs_an_author"]["codes"]
    assert len(authored_before) == 34, "the prose backlog, re-measured after the claim vocabulary was widened"

    # The catalogue is already cured, so this run is the IDEMPOTENCE check: a
    # second pass must find nothing, write nothing, and leave the document
    # byte-identical. A cure that keeps finding work on its own output is
    # rewriting something it should not have touched.
    assert C.run(p, apply=True) == 0

    after = json.loads(p.read_text(encoding="utf-8"))["data"]
    report = E.report(after)
    assert report["mechanically_correctable"]["codes"] == []
    assert report["needs_an_author"]["codes"] == authored_before

    def without_cells(records):
        out = []
        for r in records:
            r = json.loads(json.dumps(r))
            ed = (r.get("intel_2026") or {}).get("editorial")
            if isinstance(ed, dict):
                ed.pop("byTheNumbers", None)
            out.append(r)
        return out

    assert without_cells(after) == without_cells(original["data"]), (
        "the pass changed something outside byTheNumbers"
    )
