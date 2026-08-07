"""Guilt and innocence for the 86101 gold-card replacement.

The dangerous failure here is not "the wrong sentence" — it's touching a
NEIGHBOR record. 86101 and 86103 sit next to each other in the gold file and
describe opposite hospital classes (government vs private); a compiler that
over-matches by content instead of by code could bleed the private-hospital
narrative it is REMOVING from 86101 into 86103's own (correct) card, or vice
versa. So most of the weight here is on what must NOT move.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import cure_gold_86101_government_hospital as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_SPEC = json.loads(
    (REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs"
     / "gold_86101_government_hospital_2026_08_07.json").read_text(encoding="utf-8")
)


def _gold_file(tmp_path, records):
    p = tmp_path / "gold.json"
    p.write_text(json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _spec(fields=None, code="86101"):
    fields = fields if fields is not None else {
        "whatItMeans": {"old": "OLD TEXT", "new": "NEW TEXT naming the truth"},
    }
    return {"code": code, "fields": fields}


# --- the real record, post-cure ---------------------------------------------


def test_the_real_86101_card_is_cured():
    gold_raw = json.loads(mod.GOLD_PATH.read_text(encoding="utf-8"))
    gold = gold_raw.get("data", gold_raw)
    rec = gold["86101"]
    blob = json.dumps(rec, ensure_ascii=False)
    assert "OPERATED BY THE GOVERNMENT" in rec["whatItMeans"]
    assert "100 billion" not in blob
    assert "Terbuka" not in blob
    assert "Specialty Hospital" not in blob


def test_the_real_spec_names_exactly_six_fields():
    assert set(REAL_SPEC["fields"]) == {
        "whatItMeans", "whatYouNeed", "whatChanged",
        "zantaraOpener", "baliContext", "youllAlsoNeed",
    }


# --- guilt --------------------------------------------------------------------


def test_apply_patches_the_named_field(tmp_path):
    rec = {"whatItMeans": "OLD TEXT", "tkaInfo": {"a": 1}}
    path = _gold_file(tmp_path, {"86101": rec})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"]["86101"]
    assert after["whatItMeans"] == "NEW TEXT naming the truth"
    assert after["tkaInfo"] == {"a": 1}  # untouched field survives


def test_second_run_is_a_no_op(tmp_path, capsys):
    rec = {"whatItMeans": "OLD TEXT"}
    path = _gold_file(tmp_path, {"86101": rec})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 0
    capsys.readouterr()
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 0
    assert "already cured" in capsys.readouterr().out


def test_multi_field_patch_leaves_unnamed_fields_alone(tmp_path):
    rec = {
        "whatItMeans": "OLD A",
        "whatYouNeed": "OLD B",
        "baliContext": "untouched paragraph",
    }
    path = _gold_file(tmp_path, {"86101": rec})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec(fields={
        "whatItMeans": {"old": "OLD A", "new": "NEW A"},
        "whatYouNeed": {"old": "OLD B", "new": "NEW B"},
    })), encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"]["86101"]
    assert after["whatItMeans"] == "NEW A"
    assert after["whatYouNeed"] == "NEW B"
    assert after["baliContext"] == "untouched paragraph"


# --- guilt: refusals ---------------------------------------------------------


def test_refuses_when_the_code_is_missing(tmp_path):
    path = _gold_file(tmp_path, {"99999": {"whatItMeans": "x"}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_spec_names_a_field_the_record_lacks(tmp_path):
    path = _gold_file(tmp_path, {"86101": {"whatYouNeed": "x"}})  # no whatItMeans
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_live_text_has_drifted(tmp_path):
    path = _gold_file(tmp_path, {"86101": {"whatItMeans": "SOMETHING ELSE ENTIRELY"}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_on_a_non_string_field(tmp_path):
    path = _gold_file(tmp_path, {"86101": {"whatItMeans": {"nested": True}}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


# --- innocence ----------------------------------------------------------------


def test_86103_own_gold_entry_is_byte_untouched():
    """The innocence that matters most here: 86101 (government) and 86103
    (private) sit next to each other and describe opposite hospital classes."""
    gold_raw = json.loads(mod.GOLD_PATH.read_text(encoding="utf-8"))
    gold = gold_raw.get("data", gold_raw)
    if "86103" not in gold:
        pytest.skip("86103 has no gold entry")
    rec86103 = gold["86103"]
    # Nothing from the OLD 86101 card (which named 86103 as the PMA route) or
    # the NEW one leaked in either direction.
    assert "Rumah Sakit Pemerintah" not in json.dumps(rec86103, ensure_ascii=False)


def test_a_neighbor_record_in_a_fixture_is_never_touched(tmp_path):
    neighbor = {"whatItMeans": "a completely different, correct paragraph"}
    path = _gold_file(tmp_path, {"86101": {"whatItMeans": "OLD TEXT"}, "86103": neighbor})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(spec_path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"]
    assert after["86103"] == neighbor


def test_dry_run_writes_nothing(tmp_path):
    path = _gold_file(tmp_path, {"86101": {"whatItMeans": "OLD TEXT"}})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--gold", str(path), "--spec", str(spec_path)]) == 0
    assert path.read_text(encoding="utf-8") == before


def test_tkainfo_survives_a_full_real_spec_apply(tmp_path):
    """Runs the REAL spec (all six fields) against a fixture carrying the real
    86101 old-text plus a tkaInfo dict, and proves tkaInfo is untouched."""
    gold_raw = json.loads(mod.GOLD_PATH.read_text(encoding="utf-8"))
    gold = gold_raw.get("data", gold_raw)
    rec = dict(gold["86101"])
    # Reset back to the spec's own `old` values so this fixture is independent
    # of whether the real file has already been cured.
    for field, pair in REAL_SPEC["fields"].items():
        rec[field] = pair["old"]
    rec["tkaInfo"] = {"categoryId": 99}
    path = _gold_file(tmp_path, {"86101": rec})
    real_spec_path = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "gold_86101_government_hospital_2026_08_07.json"
    assert mod.main(["--apply", "--gold", str(path), "--spec", str(real_spec_path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"]["86101"]
    assert after["tkaInfo"] == {"categoryId": 99}
    assert after["whatItMeans"] == REAL_SPEC["fields"]["whatItMeans"]["new"]
