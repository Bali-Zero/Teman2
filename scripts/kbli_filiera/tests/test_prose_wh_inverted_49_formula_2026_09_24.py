"""Pins for the inverted 49% PT PMA formula cure
(`cure_specs/prose_wh_inverted_49_formula_2026_09_24.json`).

"a PT PMA can hold up to 49% of the company" says the company is capped at 49%
of itself. The PT PMA IS the company; its FOREIGN SHAREHOLDERS may hold up to
49%, and the rest belongs to Indonesian shareholders. Guilt: the inverted shape
is gone from every intel_2026 string in the canonical and each of the 16 codes
carries the corrected sentence. Innocence: the detector does not fire on the
correct wording, nor on 50142's "a foreign-owned PT PMA can hold 100%", which is
right for an open code.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_FILIERA = str(Path(__file__).resolve().parents[1])
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)

import cure_prose_national_openness as C  # noqa: E402
import editorial_record_conformance as E  # noqa: E402

SPEC = C.SPEC.parent / "prose_wh_inverted_49_formula_2026_09_24.json"
INVERTED = re.compile(r"PT PMA (can|may) (hold|own)[^.]{0,40}49%|A PT PMA can hold up to that 49%", re.I)
CORRECTED = re.compile(r"foreign shareholders can hold up to (that )?49% of a (PT PMA|courier company set up as a PT PMA)", re.I)
CODES = {
    "25200", "30400", "50124", "50125", "50131", "50132", "50133", "50134",
    "50135", "50211", "50212", "50213", "50221", "50222", "50223", "53200",
}


def _strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)
    elif isinstance(node, str):
        yield node


def test_the_spec_names_the_sixteen_codes_and_twentynine_fields():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["compiler"] == C.LANE
    assert set(spec["codes"]) == CODES
    assert sum(len(e["fields"]) for e in spec["codes"].values()) == 29


def test_guilt_no_intel_string_in_the_canonical_carries_the_inverted_formula():
    hits = [
        r["kode_kbli_2025"]
        for r in E.load_records()
        for s in _strings(r.get("intel_2026") or {})
        if INVERTED.search(s)
    ]
    assert hits == []


def test_guilt_each_of_the_sixteen_carries_exactly_the_graded_text():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    by_code = {r.get("kode_kbli_2025"): r for r in E.load_records()}
    for code, entry in spec["codes"].items():
        record = by_code[code]
        C.check_premise(record, code, entry["expect"])
        for path, patch in entry["fields"].items():
            assert C.read_field(record, path) == patch["new"], f"{code}.{path} was edited after grading"
        assert any(CORRECTED.search(s) for s in _strings(record["intel_2026"])), code


def test_innocence_the_detector_spares_the_correct_wordings():
    assert not INVERTED.search("foreign shareholders can hold up to 49% of a PT PMA")
    assert not INVERTED.search("Foreign shareholders can hold up to that 49% of a PT PMA and no more")
    by_code = {r.get("kode_kbli_2025"): r for r in E.load_records()}
    open_code = " ".join(_strings(by_code["50142"].get("intel_2026") or {}))
    assert "PT PMA can hold 100%" in open_code
    assert not INVERTED.search(open_code)
