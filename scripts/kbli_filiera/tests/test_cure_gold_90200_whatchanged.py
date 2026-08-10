"""Guilt and innocence for the 90200 whatChanged cure.

Same one-field-one-code pattern as the 86101 cure
(test_cure_gold_86101_government_hospital.py) — the facts-basis guard here
keys on canonical's `bps_2020_ancestors.codes` for 90200 rather than a
PMA-cap pair, since the card's whole claim is "this code merges four 2020
codes", not a PMA/routing fact.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import cure_gold_90200_whatchanged as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_SPEC = json.loads(
    (
        REPO_ROOT
        / "scripts"
        / "kbli_filiera"
        / "cure_specs"
        / "gold_90200_whatchanged_merged_2026_08_07.json"
    ).read_text(encoding="utf-8")
)


def _gold_file(tmp_path, records):
    p = tmp_path / "gold.json"
    p.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def _spec(fields=None, code="90200"):
    fields = (
        fields
        if fields is not None
        else {"whatChanged": {"old": "OLD TEXT", "new": "NEW TEXT naming the truth"}}
    )
    return {"code": code, "fields": fields}


def _canonical_file(tmp_path, records, name="canon.json"):
    p = tmp_path / name
    p.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def _valid_canonical_records():
    return [
        {
            "kode_kbli_2025": "90200",
            "bps_2020_ancestors": {"codes": ["90011", "90021", "90022", "90024"]},
        }
    ]


# --- the real record, post-cure ---------------------------------------------


def test_the_real_90200_card_is_cured():
    gold_raw = json.loads(mod.GOLD_PATH.read_text(encoding="utf-8"))
    gold = gold_raw.get("data", gold_raw)
    rec = gold["90200"]
    assert "Merged in KBLI 2025 from four KBLI 2020 codes" in rec["whatChanged"]
    assert "no equivalent in KBLI 2020" not in rec["whatChanged"]


def test_the_real_spec_names_exactly_one_field():
    assert set(REAL_SPEC["fields"]) == {"whatChanged"}


def test_the_real_canonical_satisfies_the_facts_basis_guard():
    records = mod.load_canonical(mod.CANONICAL_PATH)
    mod.assert_facts_basis(records)  # raises on failure; no assertion needed


def test_the_real_cure_is_a_clean_noop_without_writing():
    """W96: never risk writing production state, even a believed no-op."""
    canonical_records = mod.load_canonical(mod.CANONICAL_PATH)
    mod.assert_facts_basis(canonical_records)  # must not raise
    _, gold, _ = mod.load_gold(mod.GOLD_PATH)
    verdicts = mod.plan(REAL_SPEC, gold)
    assert verdicts and all(v["action"] == "noop" for v in verdicts.values())


# --- guilt --------------------------------------------------------------------


def test_apply_patches_the_named_field(tmp_path):
    rec = {"whatChanged": "OLD TEXT", "tkaInfo": {"a": 1}}
    path = _gold_file(tmp_path, {"90200": rec})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"]["90200"]
    assert after["whatChanged"] == "NEW TEXT naming the truth"
    assert after["tkaInfo"] == {"a": 1}  # untouched field survives


def test_second_run_is_a_no_op(tmp_path, capsys):
    rec = {"whatChanged": "OLD TEXT"}
    path = _gold_file(tmp_path, {"90200": rec})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 0
    capsys.readouterr()
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 0
    assert "already cured" in capsys.readouterr().out


# --- guilt: refusals ---------------------------------------------------------


def test_refuses_when_the_code_is_missing(tmp_path):
    path = _gold_file(tmp_path, {"99999": {"whatChanged": "x"}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_spec_names_a_field_the_record_lacks(tmp_path):
    path = _gold_file(tmp_path, {"90200": {"whatItMeans": "x"}})  # no whatChanged
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_live_text_has_drifted(tmp_path):
    path = _gold_file(tmp_path, {"90200": {"whatChanged": "SOMETHING ELSE ENTIRELY"}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_on_a_non_string_field(tmp_path):
    path = _gold_file(tmp_path, {"90200": {"whatChanged": {"nested": True}}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


# --- guilt: the facts-basis guard --------------------------------------------


def test_refuses_when_90200_ancestors_have_drifted(tmp_path):
    gold_path = _gold_file(tmp_path, {"90200": {"whatChanged": "OLD TEXT"}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    records = _valid_canonical_records()
    records[0]["bps_2020_ancestors"]["codes"] = ["90011"]  # drifted: only one now
    canon_path = _canonical_file(tmp_path, records)
    before = gold_path.read_text(encoding="utf-8")
    assert mod.main([
        "--apply", "--gold", str(gold_path), "--spec", str(spec_path),
        "--canonical", str(canon_path),
    ]) == 2
    assert gold_path.read_text(encoding="utf-8") == before


def test_refuses_when_90200_has_no_ancestors_at_all(tmp_path):
    gold_path = _gold_file(tmp_path, {"90200": {"whatChanged": "OLD TEXT"}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    canon_path = _canonical_file(tmp_path, [{"kode_kbli_2025": "90200"}])
    before = gold_path.read_text(encoding="utf-8")
    assert mod.main([
        "--apply", "--gold", str(gold_path), "--spec", str(spec_path),
        "--canonical", str(canon_path),
    ]) == 2
    assert gold_path.read_text(encoding="utf-8") == before


def test_facts_basis_guard_blocks_even_an_idempotent_noop(tmp_path):
    gold_path = _gold_file(
        tmp_path, {"90200": {"whatChanged": "NEW TEXT naming the truth"}}
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    records = _valid_canonical_records()
    records[0]["bps_2020_ancestors"]["codes"] = []  # drifted regardless
    canon_path = _canonical_file(tmp_path, records)
    assert mod.main([
        "--apply", "--gold", str(gold_path), "--spec", str(spec_path),
        "--canonical", str(canon_path),
    ]) == 2


def test_innocence_a_valid_canonical_fixture_permits_the_write(tmp_path):
    gold_path = _gold_file(tmp_path, {"90200": {"whatChanged": "OLD TEXT"}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    canon_path = _canonical_file(tmp_path, _valid_canonical_records())
    assert mod.main([
        "--apply", "--gold", str(gold_path), "--spec", str(spec_path),
        "--canonical", str(canon_path),
    ]) == 0
    after = json.loads(gold_path.read_text(encoding="utf-8"))["data"]["90200"]
    assert after["whatChanged"] == "NEW TEXT naming the truth"


# --- innocence ----------------------------------------------------------------


def test_a_neighbor_record_in_a_fixture_is_never_touched(tmp_path):
    neighbor = {"whatChanged": "a completely different, correct paragraph"}
    path = _gold_file(
        tmp_path, {"90200": {"whatChanged": "OLD TEXT"}, "90011": neighbor}
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"]
    assert after["90011"] == neighbor


def test_dry_run_writes_nothing(tmp_path):
    path = _gold_file(tmp_path, {"90200": {"whatChanged": "OLD TEXT"}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--gold", str(path), "--spec", str(spec_path)]) == 0
    assert path.read_text(encoding="utf-8") == before


def test_untouched_fields_survive_a_full_real_spec_apply(tmp_path):
    """Runs the REAL spec against a fixture carrying the real 90200 old-text
    plus other fields, and proves everything but whatChanged is untouched."""
    gold_raw = json.loads(mod.GOLD_PATH.read_text(encoding="utf-8"))
    gold = gold_raw.get("data", gold_raw)
    rec = dict(gold["90200"])
    for field, pair in REAL_SPEC["fields"].items():
        rec[field] = pair["old"]
    rec["tkaInfo"] = {"categoryId": 42}
    rec["whatItMeans"] = "untouched paragraph"
    path = _gold_file(tmp_path, {"90200": rec})
    real_spec_path = (
        REPO_ROOT
        / "scripts"
        / "kbli_filiera"
        / "cure_specs"
        / "gold_90200_whatchanged_merged_2026_08_07.json"
    )
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(real_spec_path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"]["90200"]
    assert after["tkaInfo"] == {"categoryId": 42}
    assert after["whatItMeans"] == "untouched paragraph"
    assert after["whatChanged"] == REAL_SPEC["fields"]["whatChanged"]["new"]
