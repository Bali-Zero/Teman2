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


def spec_file(tmp_path: Path, codes: dict) -> Path:
    p = tmp_path / "spec.json"
    p.write_text(json.dumps({"_meta": {}, "codes": codes}, ensure_ascii=False), encoding="utf-8")
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

    The backlog went 34 -> 28 and the difference is exactly the spec's six. The
    28 that remain are named in the detector's own pin, so a code leaving this
    list without a cure would show up there.
    """
    spec = json.loads(C.SPEC.read_text(encoding="utf-8"))
    cured = set(spec["codes"])
    rep = E.report(E.load_records())
    remaining = set(rep["needs_an_author"]["codes"])
    assert len(remaining) == 28
    assert cured & remaining == set(), f"a cured code still lies: {sorted(cured & remaining)}"
