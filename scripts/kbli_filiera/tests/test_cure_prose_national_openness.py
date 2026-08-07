"""Guilt, innocence and REFUSAL for the prose replacement cure.

This module rewrites AUTHORED, client-facing sentences, so the tests that carry
weight are the ones about what it must refuse. A wrong stat card is a wrong
number; a wrong sentence is a wrong instruction, and it reads as considered
advice because it is prose.

The specific failure being guarded against is not "it missed a field". It is
"it wrote a graded replacement onto a paragraph that is no longer the paragraph
that was graded".
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

_FILIERA = str(Path(__file__).resolve().parents[1])
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)

import cure_prose_national_openness as C  # noqa: E402
import editorial_record_conformance as E  # noqa: E402


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


OLD = "Nationally, this activity is open to 100% foreign ownership."
NEW = (
    "The national foreign-ownership ceiling for this activity is 0%: it is allocated "
    "to Koperasi and UMKM under Perpres 49/2021's Lampiran II."
)


def rec(code="96210", cap=0, status="TERBATAS", body=OLD, kondisi=None):
    return {
        "kode_kbli_2025": code,
        "pma_status": status,
        "pma_max_asing": cap,
        "pma_kondisi": (
            kondisi
            if kondisi is not None
            else "Bidang usaha dialokasikan untuk Koperasi dan UMKM (Perpres 49/2021 Lampiran II)"
        ),
        "intel_2026": {"editorial": {"body": body, "byTheNumbers": []}},
    }


def entry(old=OLD, new=NEW, cap=0, status="TERBATAS"):
    return {
        "expect": {
            "pma_max_asing": cap,
            "pma_status": status,
            "pma_kondisi_contains": "dialokasikan untuk Koperasi dan UMKM",
        },
        "fields": {"editorial.body": {"old_sha256": sha(old), "new": new}},
    }


def spec_file(tmp_path: Path, codes: dict, compiler: str | None = C.LANE) -> Path:
    p = tmp_path / "spec.json"
    body: dict = {"_meta": {}, "codes": codes}
    if compiler is not None:
        body = {"compiler": compiler, **body}
    p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return p


def canonical_file(tmp_path: Path, records: list[dict]) -> Path:
    p = tmp_path / "canonical.json"
    p.write_text(json.dumps({"data": records}, ensure_ascii=False), encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# GUILT — the replacement lands, and the page stops asserting the falsehood
# --------------------------------------------------------------------------


def test_guilt_the_graded_replacement_is_written(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(C, "run_sync_script", lambda: None)
    monkeypatch.setattr(C, "reconcile_sidecar", lambda path: False)
    p = canonical_file(tmp_path, [rec()])
    s = spec_file(tmp_path, {"96210": entry()})

    assert E.classify(rec())["body_asserts_national_openness"] is True
    assert C.run(s, p, None, apply=True) == 0

    after = json.loads(p.read_text(encoding="utf-8"))["data"][0]
    assert after["intel_2026"]["editorial"]["body"] == NEW
    assert E.classify(after)["body_asserts_national_openness"] is False


def test_guilt_a_by_the_numbers_CELL_is_reachable_and_replaced(tmp_path: Path, monkeypatch):
    """The number a reader meets first is not always in a paragraph.

    Two of the fourteen transport codes state their (wrong) ceiling ONLY in an
    `editorial.byTheNumbers` cell — a list element, invisible to a path language
    that walks dicts. A cure that cannot address it leaves "Maximum foreign
    ownership: 100%" sitting above prose that now says 49%, which is worse than
    either alone: the page argues with itself and the reader picks.
    """
    monkeypatch.setattr(C, "run_sync_script", lambda: None)
    monkeypatch.setattr(C, "reconcile_sidecar", lambda path: False)
    record = rec()
    record["intel_2026"]["editorial"]["byTheNumbers"] = [
        {"label": "Maximum foreign ownership", "value": "100%"},
        {"label": "Risk class", "value": "Low"},
    ]
    p = canonical_file(tmp_path, [record])
    e = entry()
    e["fields"]["editorial.byTheNumbers[0].value"] = {"old_sha256": sha("100%"), "new": "0%"}
    s = spec_file(tmp_path, {"96210": e})

    assert C.run(s, p, None, apply=True) == 0
    cells = json.loads(p.read_text(encoding="utf-8"))["data"][0]["intel_2026"]["editorial"][
        "byTheNumbers"
    ]
    assert cells[0]["value"] == "0%"
    assert cells[1] == {"label": "Risk class", "value": "Low"}, "a sibling cell was disturbed"


def test_refusal_when_a_spec_carries_no_compiler_marker(tmp_path: Path):
    """The marker is what makes "everything this lane shipped" enumerable.

    Guilt: an unmarked spec is refused (exit 2) and writes nothing. Innocence:
    the same spec, marked, lands. Without the run-time refusal the marker is a
    convention, and a convention is exactly what the filename prefix was.
    """
    p = canonical_file(tmp_path, [rec()])
    before = p.read_bytes()
    unmarked = spec_file(tmp_path, {"96210": entry()}, compiler=None)
    assert C.main(["--spec", str(unmarked), "--canonical", str(p), "--apply"]) == 2
    assert p.read_bytes() == before

    other = tmp_path / "other"
    other.mkdir()
    wrong = spec_file(other, {"96210": entry()}, compiler="some_other_cure")
    assert C.main(["--spec", str(wrong), "--canonical", str(p), "--apply"]) == 2
    assert p.read_bytes() == before


def test_an_indexed_path_that_does_not_resolve_is_a_REFUSAL_not_a_silent_skip(tmp_path: Path):
    """An out-of-range cell must stop the run, not read as "nothing to do".

    `read_field` returning None for a missing index would otherwise reach the
    "field is NoneType, not prose" refusal — which is the correct outcome, and is
    what this pins. The failure mode being excluded is a cure that writes the
    prose half of a page and silently drops the number half.
    """
    p = canonical_file(tmp_path, [rec()])  # byTheNumbers is []
    e = entry()
    e["fields"]["editorial.byTheNumbers[0].value"] = {"old_sha256": sha("100%"), "new": "0%"}
    s = spec_file(tmp_path, {"96210": e})
    before = p.read_bytes()
    assert C.main(["--spec", str(s), "--canonical", str(p), "--apply"]) == 2
    assert p.read_bytes() == before


def test_dry_run_writes_nothing(tmp_path: Path):
    p = canonical_file(tmp_path, [rec()])
    s = spec_file(tmp_path, {"96210": entry()})
    before = p.read_bytes()
    assert C.run(s, p, None, apply=False) == 0
    assert p.read_bytes() == before


# --------------------------------------------------------------------------
# REFUSAL — the premise moved, so the graded text no longer describes anything
# --------------------------------------------------------------------------


def test_refusal_when_the_field_moved_since_it_was_graded(tmp_path: Path):
    """The one that matters most.

    The replacement was authored against a specific paragraph and refuted
    against that one. If the live text has changed, re-matching would write a
    graded sentence onto ungraded prose — which is the cure becoming an author.
    """
    p = canonical_file(tmp_path, [rec(body="Somebody rewrote this paragraph last week.")])
    s = spec_file(tmp_path, {"96210": entry()})
    before = p.read_bytes()
    assert C.main(["--spec", str(s), "--canonical", str(p), "--apply"]) == 2
    assert p.read_bytes() == before


@pytest.mark.parametrize(
    ("field", "value"),
    [("pma_max_asing", 49), ("pma_status", "TERBUKA")],
)
def test_refusal_when_the_record_moved_under_the_spec(tmp_path: Path, field, value):
    """A cap of 0 is WHY these sentences say what they say. If the record now
    says 49, the graded replacement asserts a fact the record no longer holds."""
    r = rec()
    r[field] = value
    p = canonical_file(tmp_path, [r])
    s = spec_file(tmp_path, {"96210": entry()})
    before = p.read_bytes()
    assert C.main(["--spec", str(s), "--canonical", str(p), "--apply"]) == 2
    assert p.read_bytes() == before


def test_refusal_when_the_reason_left_the_record(tmp_path: Path):
    """Every replacement in this spec names the Koperasi/UMKM allocation as the
    REASON the ceiling is zero. Without it on the record, the sentence would be
    asserting its own basis rather than reading it off a field."""
    p = canonical_file(tmp_path, [rec(kondisi="Reserved by a different instrument entirely")])
    s = spec_file(tmp_path, {"96210": entry()})
    assert C.main(["--spec", str(s), "--canonical", str(p), "--apply"]) == 2


def test_refusal_when_any_cited_field_no_longer_carries_its_basis(tmp_path: Path):
    """`<field>_contains` is generic, and it had to become generic.

    The first spec only checked `pma_kondisi`, because the Koperasi/UMKM
    allocation lives there. The transport batch cites `pma_official_basis`
    instead — "Perpres 49/2021 Lampiran III … entry #22", a different number on
    every code — and a premise check that cannot see the field a sentence quotes
    is decoration.
    """
    r = rec()
    r["pma_official_basis"] = "Perpres 49/2021 Lampiran III entry #22"
    p = canonical_file(tmp_path, [r])
    e = entry()
    e["expect"]["pma_official_basis_contains"] = "Lampiran III entry #22"
    assert C.main(["--spec", str(spec_file(tmp_path, {"96210": e})),
                   "--canonical", str(p), "--apply"]) != 2, "premise holds, so it must not refuse"

    r["pma_official_basis"] = "Perpres 49/2021 Lampiran III entry #99"
    p2 = canonical_file(tmp_path, [r])
    before = p2.read_bytes()
    assert C.main(["--spec", str(spec_file(tmp_path, {"96210": e})),
                   "--canonical", str(p2), "--apply"]) == 2
    assert p2.read_bytes() == before


def test_refusal_when_a_replacement_states_a_percentage_the_record_denies(tmp_path: Path):
    """The one machine-checkable property of an authored sentence, and it does
    not get to disagree with the field it narrates."""
    p = canonical_file(tmp_path, [rec()])
    s = spec_file(
        tmp_path,
        {"96210": entry(new="Nationally the ceiling is 49% for this activity.")},
    )
    before = p.read_bytes()
    assert C.main(["--spec", str(s), "--canonical", str(p), "--apply"]) == 2
    assert p.read_bytes() == before


def test_refusal_when_the_replacement_still_asserts_openness(tmp_path: Path, monkeypatch):
    """A half-cure leaves a page consistent enough to be believed and wrong
    where it counts, so nothing is written at all."""
    monkeypatch.setattr(C, "run_sync_script", lambda: None)
    monkeypatch.setattr(C, "reconcile_sidecar", lambda path: False)
    p = canonical_file(tmp_path, [rec()])
    s = spec_file(
        tmp_path,
        {"96210": entry(new="This bidang usaha remains nationally open to foreign investment.")},
    )
    before = p.read_bytes()
    assert C.run(s, p, None, apply=True) == 1
    assert p.read_bytes() == before


def test_refusal_when_the_verdict_moves_on_a_code_the_spec_never_named(
    tmp_path: Path, monkeypatch
):
    """A cure that alters a record it was not asked to touch is the failure this
    directory keeps rediscovering.

    Simulated by a planner that emits an edit for a code the spec never named,
    which is what a path-resolution bug looks like from the write loop's side.

    The first version of this test wired a sibling REFERENCE into the fixture
    and then round-tripped it through `json.dumps` — which serialises the
    reference as a copy, so the sabotage mutated a nested duplicate and reached
    nothing. It reported the guard as absent while measuring only the poverty of
    its own fake world.
    """
    monkeypatch.setattr(C, "run_sync_script", lambda: None)
    monkeypatch.setattr(C, "reconcile_sidecar", lambda path: False)
    innocent = rec(code="99999", body="This activity is nationally open to full foreign ownership.")
    p = canonical_file(tmp_path, [rec(), innocent])
    s = spec_file(tmp_path, {"96210": entry()})
    before = p.read_bytes()

    real_plan = C.plan_for

    def reaches_sideways(record, code, entry_):
        edits = real_plan(record, code, entry_)
        edits.append({"code": "99999", "field": "editorial.body", "was": "", "now": NEW})
        return edits

    monkeypatch.setattr(C, "plan_for", reaches_sideways)
    assert C.run(s, p, None, apply=True) == 1
    assert p.read_bytes() == before, "it must not write when it refuses"


def test_refusal_when_only_names_a_code_the_spec_does_not_carry(tmp_path: Path):
    p = canonical_file(tmp_path, [rec()])
    s = spec_file(tmp_path, {"96210": entry()})
    assert C.main(["--spec", str(s), "--canonical", str(p), "--only", "12345", "--apply"]) == 2


# --------------------------------------------------------------------------
# THE REAL SPEC, AGAINST THE REAL CATALOGUE
# --------------------------------------------------------------------------


def _lane_specs() -> list[Path]:
    """Every spec THIS compiler has shipped, selected by a marker in the file.

    It used to be `glob("prose_umkm_reserved_openness*.json")` — a filename
    prefix, which is a proxy for authorship and lies the moment a batch is named
    after something else. The transport batch is called
    `prose_perpres_cap49_transport_*`, so the class guard below would have skipped
    all fourteen codes and still passed, reporting a clean sweep of a population
    it never looked at.

    The first repair swapped the prefix for `prose_*` and demanded the marker on
    every match — and it failed immediately on `prose_unverifiable_tier.json`,
    which belongs to a different compiler entirely. The filename was still doing
    the work. So the marker is enforced by `C.run` at apply time instead
    (`test_refusal_when_a_spec_carries_no_compiler_marker`): an unmarked spec
    cannot land, which makes the marked set on disk the complete set of specs this
    lane has ever applied. Here it is only read.
    """
    marked = [
        path
        for path in sorted(C.SPEC.parent.glob("*.json"))
        if json.loads(path.read_text(encoding="utf-8")).get("compiler") == C.LANE
    ]
    assert C.SPEC in marked, "the module's own default spec is unmarked — selection is broken"
    return marked


def test_the_cure_has_landed_and_the_six_now_carry_exactly_the_graded_text():
    """The pin that replaced "the spec still matches the live records".

    Before the cure ran, this asserted that every `old_sha256` still described
    the live field — a drift tripwire. Once the cure lands that assertion is
    false BY DESIGN, because the text it hashed no longer exists. Preserving it
    would have meant re-hashing the spec against its own output, which is a
    tautology wearing a tripwire's clothes.

    So the property becomes the one worth keeping afterwards: each of the 21
    fields holds EXACTLY the graded replacement, and none of the six asserts a
    national openness its record denies. A failure here means somebody edited
    one of these paragraphs without re-grading it.
    """
    spec = json.loads(C.SPEC.read_text(encoding="utf-8"))
    by_code = {r.get("kode_kbli_2025"): r for r in E.load_records()}
    for code, e in spec["codes"].items():
        record = by_code[code]
        C.check_premise(record, code, e["expect"])
        for path, patch in e["fields"].items():
            assert C.read_field(record, path) == patch["new"], (
                f"{code}.{path} is not the graded replacement — it was edited after grading"
            )
        assert E.classify(record)["body_asserts_national_openness"] is False


def test_the_shipped_spec_covers_six_codes_and_twentyone_fields():
    """Pinned as a SET, so a change names what moved instead of shifting a count.

    21 fields on 6 codes: most of these pages lie in more than one place, which
    is precisely why the cure replaces fields rather than sentences.
    """
    spec = json.loads(C.SPEC.read_text(encoding="utf-8"))
    assert set(spec["codes"]) == {"95220", "95291", "95299", "96100", "96210", "96220"}
    assert sum(len(e["fields"]) for e in spec["codes"].values()) == 21


def test_running_the_landed_cure_a_second_time_REFUSES(tmp_path: Path, monkeypatch):
    """Idempotence here is a REFUSAL, not a no-op, and that is the safer shape.

    Every replacement is bound by hash to the paragraph it was graded against.
    Once it has landed, that paragraph is gone, so a second run cannot identify
    its target and says so (exit 2) instead of matching something approximate.
    A cure that quietly finds "close enough" text on a re-run is the one that
    eventually writes a graded sentence onto ungraded prose.
    """
    monkeypatch.setattr(C, "run_sync_script", lambda: None)
    monkeypatch.setattr(C, "reconcile_sidecar", lambda path: False)

    original = json.loads(E.CANONICAL.read_text(encoding="utf-8"))
    p = tmp_path / "canonical.json"
    p.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    before = p.read_bytes()

    assert C.main(["--spec", str(C.SPEC), "--canonical", str(p), "--apply"]) == 2
    assert p.read_bytes() == before, "a refusing run must not write"


def test_the_six_are_gone_from_the_live_backlog_and_the_rest_are_untouched():
    """What the cure was FOR, measured on the real catalogue rather than on the
    run's own report — counting edits proves what a pass intended, not what it
    wrote.

    The backlog went 34 -> 28 -> 21 -> 7 -> 0 across the four lots, and the
    difference at each step is exactly the codes they name.

    With the backlog at zero the intersection below is empty for a trivial
    reason, so the assertion that carries the weight is the other one: every
    code this lane CLAIMS to have cured must be absent from the live backlog.
    That still fails if a spec names a code it did not actually fix, which is
    the failure this test was written for.
    """
    cured = set()
    for sp in _lane_specs():
        cured |= set(json.loads(sp.read_text(encoding="utf-8"))["codes"])
    assert cured, "the lane marker matched no spec — this test would pass on nothing"
    rep = E.report(E.load_records())
    remaining = set(rep["needs_an_author"]["codes"])
    assert len(remaining) == 0
    assert cured & remaining == set(), f"a cured code still lies: {sorted(cured & remaining)}"


def test_no_cured_code_still_carries_a_numeric_openness_claim_the_other_lint_can_see():
    """The antidote of class, and it exists because this bit once.

    `editorial_record_conformance` requires a national scope word in the SAME
    sentence as the openness claim. `55105` carried a field reading

        **PMA Status:** Fully open (Terbuka) — 100% foreign ownership.

    with no "national" anywhere near it, so the detector that owns this cure was
    structurally blind to it — while the page's standfirst and body had just been
    corrected. A page that reads cured and still prints the number a client acts
    on is worse than one that is uniformly wrong.

    It was found by the relationship pin between this module and lint rule L10
    going red, not by the detector. So the check belongs here permanently: after
    ANY prose cure, the neighbouring rule — which reads for a PERCENTAGE rather
    than for an assertion — must find nothing on the codes just cured.

    NOT asserted here: that L10 finds nothing anywhere. It still flags `41011`
    and `52292`, both running the opposite direction (prose more restrictive than
    the record), and those are a different adjudication.
    """
    import kbli_dataset_lint as lint

    records = E.load_records()
    by_code = {r["kode_kbli_2025"]: r for r in records}
    maxa_by_code = {r["kode_kbli_2025"]: r.get("pma_max_asing") for r in records}

    cured: set[str] = set()
    for spec_path in _lane_specs():
        cured |= set(json.loads(spec_path.read_text(encoding="utf-8"))["codes"])

    survivors = []
    for code in sorted(cured):
        record = by_code[code]
        maxa = record.get("pma_max_asing")
        for field, text in lint.iter_prose(record):
            hit = lint.l10_ownership_contradiction(text, code, maxa, maxa_by_code)
            if hit:
                survivors.append((code, field, hit[0], maxa))

    assert survivors == [], (
        "a cured page still states a foreign-ownership percentage its record denies: "
        f"{survivors}"
    )
