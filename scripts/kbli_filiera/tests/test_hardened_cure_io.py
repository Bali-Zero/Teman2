"""Guilt and innocence for `_hardened_cure_io.py` — the shared old_sha256 /
atomic-write / untouched_fields primitives every NEW cure compiler from the
2026-08-08 sector-law PR onward is built on (item 6 of the brief).

`cure_canonical_47222_nota_kondisi.py` and `cure_gold_90200_whatchanged.py`
apply their old/new refusal correctly but never pinned old_sha256, never
wrote atomically, and declared `untouched_fields` only in a docstring —
retrofitting those two is explicitly OUT OF SCOPE here (ledgered, not done).
This file proves the shared module itself, independent of any one cure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _hardened_cure_io as H  # noqa: E402


# --- sha256_of ----------------------------------------------------------------


def test_sha256_of_is_order_independent():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert H.sha256_of(a) == H.sha256_of(b)


def test_sha256_of_detects_a_real_change():
    a = {"x": 1}
    b = {"x": 2}
    assert H.sha256_of(a) != H.sha256_of(b)


# --- has_field / read_field / write_field --------------------------------------


def test_has_field_and_read_field_walk_dotted_paths():
    rec = {"intel_2026": {"whatChanged": "old"}}
    assert H.has_field(rec, "intel_2026.whatChanged") is True
    assert H.read_field(rec, "intel_2026.whatChanged") == "old"


def test_has_field_is_false_when_parent_missing():
    rec = {"pma_status": "TERBUKA"}
    assert H.has_field(rec, "intel_2026.whatChanged") is False


def test_read_field_refuses_when_field_absent():
    rec = {"pma_status": "TERBUKA"}
    try:
        H.read_field(rec, "intel_2026.whatChanged")
        assert False, "expected CureError"
    except H.CureError:
        pass


def test_write_field_touches_only_the_named_leaf():
    rec = {"intel_2026": {"whatChanged": "old", "riskLabel": "Medium"}}
    H.write_field(rec, "intel_2026.whatChanged", "new")
    assert rec["intel_2026"]["whatChanged"] == "new"
    assert rec["intel_2026"]["riskLabel"] == "Medium"


def test_write_field_creates_missing_intermediate_dicts():
    rec = {}
    H.write_field(rec, "a.b.c", "value")
    assert rec == {"a": {"b": {"c": "value"}}}


# --- atomic_write_text ----------------------------------------------------------


def test_atomic_write_text_writes_and_leaves_no_tmp(tmp_path):
    target = tmp_path / "data.json"
    H.atomic_write_text(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"
    leftovers = [p for p in tmp_path.iterdir() if p.name != "data.json"]
    assert leftovers == []


def test_atomic_write_text_overwrites_existing_file(tmp_path):
    target = tmp_path / "data.json"
    target.write_text("old", encoding="utf-8")
    H.atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


# --- verify_untouched -----------------------------------------------------------


def _records(codes_and_fields):
    return [{"kode_kbli_2025": code, **fields} for code, fields in codes_and_fields.items()]


def test_verify_untouched_passes_when_only_declared_fields_move():
    before = _records(
        {
            "65111": {"pma_status": "TERBUKA", "pma_max_asing": 100},
            "65123": {"pma_status": "TERBUKA", "pma_max_asing": 100},
        }
    )
    after = [dict(r) for r in before]
    after[0]["pma_status"] = "TERBATAS"
    after[0]["pma_max_asing"] = 80
    raised = None
    try:
        H.verify_untouched(
            before,
            after,
            "kode_kbli_2025",
            touched_codes={"65111"},
            touched_field_paths={"65111": {"pma_status", "pma_max_asing"}},
        )
    except H.CureError as exc:  # pragma: no cover — proves the guilt half is real
        raised = exc
    assert raised is None, f"a declared-scope change must not raise: {raised}"


def test_verify_untouched_raises_when_an_undeclared_code_changes():
    before = _records(
        {
            "65111": {"pma_status": "TERBUKA"},
            "65123": {"pma_status": "TERBUKA"},
        }
    )
    after = [dict(r) for r in before]
    after[0]["pma_status"] = "TERBATAS"
    after[1]["pma_status"] = "TERBATAS"  # 65123 was never named — must abort
    try:
        H.verify_untouched(
            before,
            after,
            "kode_kbli_2025",
            touched_codes={"65111"},
            touched_field_paths={"65111": {"pma_status"}},
        )
        assert False, "expected CureError on an undeclared code changing"
    except H.CureError as exc:
        assert "65123" in str(exc)


def test_verify_untouched_raises_when_a_touched_code_moves_an_extra_field():
    before = _records({"65111": {"pma_status": "TERBUKA", "pma_nota": None}})
    after = [dict(r) for r in before]
    after[0]["pma_status"] = "TERBATAS"
    after[0]["pma_nota"] = "a field the plan never named"
    try:
        H.verify_untouched(
            before,
            after,
            "kode_kbli_2025",
            touched_codes={"65111"},
            touched_field_paths={"65111": {"pma_status"}},
        )
        assert False, "expected CureError on an extra field outside declared scope"
    except H.CureError as exc:
        assert "pma_nota" in str(exc)


def test_verify_untouched_raises_when_the_population_changes():
    before = _records({"65111": {"pma_status": "TERBUKA"}})
    after = before + _records({"99999": {"pma_status": "TERBUKA"}})
    try:
        H.verify_untouched(
            before, after, "kode_kbli_2025", touched_codes=set(), touched_field_paths={}
        )
        assert False, "expected CureError when a record is added"
    except H.CureError:
        pass


def test_verify_untouched_is_innocent_when_nothing_moves():
    before = _records({"65111": {"pma_status": "TERBUKA"}, "65123": {"pma_status": "TERBUKA"}})
    after = [dict(r) for r in before]
    raised = None
    try:
        H.verify_untouched(
            before, after, "kode_kbli_2025", touched_codes=set(), touched_field_paths={}
        )
    except H.CureError as exc:  # pragma: no cover — proves the guilt half is real
        raised = exc
    assert raised is None, f"an untouched fixture must not raise: {raised}"
