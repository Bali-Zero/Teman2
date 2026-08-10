"""Guilt and innocence for cure_whatchanged_corroborated_predecessor.py.

Ward-round 2026-08-07 (kbli-client-facing-content-defects): 49296 and 64210
get a CONFIRMED predecessor sentence (PP28 lampiran title-match AND the
independent BPS crosswalk agree); 46415 stays untouched (not in gold, still
genuinely disputed); 46496's canonical text stays "unconfirmed" but its
SEPARATE gold wording — never caught by L2.1's `KBLI 2020: NNNNN`-anchored
detector, because gold phrases the same false claim as "Previous code(s):
NNNNN" — is re-aligned to canonical's honest text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import cure_whatchanged_corroborated_predecessor as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_SPEC_PATH = (
    REPO_ROOT
    / "scripts"
    / "kbli_filiera"
    / "cure_specs"
    / "whatchanged_corroborated_predecessor_2026_08_08.json"
)
REAL_BPS_CROSSWALK = REPO_ROOT / "data" / "kbli-filiera" / "phase0" / "bps_crosswalk.json"


def _write(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _canonical_record(code, pp28_sources, kbli_2020_source, mapping_pct, what_changed):
    return {
        "kode_kbli_2025": code,
        "pp28_sources": pp28_sources,
        "kbli_2020_source": kbli_2020_source,
        "mapping_note": f"PP28 uses KBLI 2020 code {pp28_sources[0]}. Match: {mapping_pct}%",
        "intel_2026": {"whatChanged": what_changed},
    }


def _bps_relation(mapping):
    return {"relation": {code: {"codes": codes} for code, codes in mapping.items()}}


def _minimal_fixture(tmp_path, *, agree=True, canonical_text="OLD CANONICAL", gold_text="OLD GOLD"):
    """One code, '99911', with a spec entry that requires predecessor '11111'."""
    spec = {
        "codes": [
            {
                "code": "99911",
                "predecessor": "11111",
                "pp28_match_pct": 100,
                "canonical_whatChanged": {"old": canonical_text, "new": "NEW CANONICAL — confirmed"},
                "gold_whatChanged": {"old": gold_text, "new": "NEW GOLD — confirmed"},
            }
        ]
    }
    spec_path = _write(tmp_path / "spec.json", spec)
    bps_codes = ["11111"] if agree else ["22222"]
    bps_path = _write(tmp_path / "bps.json", _bps_relation({"99911": bps_codes}))
    canonical_path = _write(
        tmp_path / "canon.json",
        {"data": [_canonical_record("99911", ["11111"], "11111", 100, canonical_text)]},
    )
    gold_path = _write(tmp_path / "gold.json", {"99911": {"whatChanged": gold_text}})
    return spec_path, canonical_path, gold_path, bps_path


def _run(monkeypatch, *args):
    monkeypatch.setattr(mod, "run_sync_script", lambda: None)
    monkeypatch.setattr(mod, "update_sidecar", lambda: None)
    return mod.main(list(args))


# --- the real spec, against the real repo state ------------------------------


def test_real_spec_is_loadable_and_names_three_codes():
    entries = mod.load_spec(REAL_SPEC_PATH)
    assert {e["code"] for e in entries} == {"49296", "64210", "46496"}


def test_real_bps_relation_corroborates_49296_and_64210():
    relation = mod.load_bps_relation(REAL_BPS_CROSSWALK)
    assert relation["49296"]["codes"] == ["49424"]
    assert relation["64210"]["codes"] == ["64200"]


def test_real_facts_basis_holds_for_all_three_entries_against_live_canonical():
    entries = mod.load_spec(REAL_SPEC_PATH)
    _, records, _, _ = mod.load_canonical(mod.DEFAULT_CANONICAL)
    by_code = {r[mod.CODE_FIELD]: r for r in records if mod.CODE_FIELD in r}
    relation = mod.load_bps_relation(REAL_BPS_CROSSWALK)
    for entry in entries:
        mod.assert_facts_basis(entry, by_code[entry["code"]], relation)  # raises on failure


def test_46415_is_named_nowhere_in_this_spec():
    """46415 stays genuinely disputed (no gold entry, canonical already honest)
    — this cure must not touch it at all."""
    entries = mod.load_spec(REAL_SPEC_PATH)
    assert "46415" not in {e["code"] for e in entries}


# --- guilt: confirmed-predecessor patch (49296/64210 shape) ------------------


def test_apply_patches_canonical_and_gold_when_layers_agree(tmp_path, monkeypatch):
    spec_path, canon_path, gold_path, bps_path = _minimal_fixture(tmp_path)
    rc = _run(
        monkeypatch, "--apply",
        "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert rc == 0
    _, records, _, _ = mod.load_canonical(canon_path)
    after_canon = {r["kode_kbli_2025"]: r for r in records}["99911"]
    assert after_canon["intel_2026"]["whatChanged"] == "NEW CANONICAL — confirmed"
    _, gold, _ = mod.load_gold(gold_path)
    assert gold["99911"]["whatChanged"] == "NEW GOLD — confirmed"


def test_second_run_is_a_clean_noop(tmp_path, monkeypatch, capsys):
    spec_path, canon_path, gold_path, bps_path = _minimal_fixture(tmp_path)
    args = (
        "--apply", "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert _run(monkeypatch, *args) == 0
    capsys.readouterr()
    assert _run(monkeypatch, *args) == 0
    assert "already cured" in capsys.readouterr().out


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    spec_path, canon_path, gold_path, bps_path = _minimal_fixture(tmp_path)
    before_canon = canon_path.read_text(encoding="utf-8")
    before_gold = gold_path.read_text(encoding="utf-8")
    rc = _run(
        monkeypatch, "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert rc == 0
    assert canon_path.read_text(encoding="utf-8") == before_canon
    assert gold_path.read_text(encoding="utf-8") == before_gold


# --- guilt: facts-basis refusals ----------------------------------------------


def test_refuses_when_bps_and_pp28_disagree_for_a_confirmed_entry(tmp_path, monkeypatch):
    """The premise ('the two layers agree') has drifted — refuse rather than
    publish a confirmed claim the corroboration no longer supports."""
    spec_path, canon_path, gold_path, bps_path = _minimal_fixture(tmp_path, agree=False)
    before = canon_path.read_text(encoding="utf-8")
    rc = _run(
        monkeypatch, "--apply", "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert rc == 2
    assert canon_path.read_text(encoding="utf-8") == before


def test_refuses_when_mapping_note_percentage_drifted(tmp_path, monkeypatch):
    spec_path, canon_path, gold_path, bps_path = _minimal_fixture(tmp_path)
    dataset = json.loads(canon_path.read_text(encoding="utf-8"))
    dataset["data"][0]["mapping_note"] = "PP28 uses KBLI 2020 code 11111. Match: 60%"
    canon_path.write_text(json.dumps(dataset), encoding="utf-8")
    before = canon_path.read_text(encoding="utf-8")
    rc = _run(
        monkeypatch, "--apply", "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert rc == 2
    assert canon_path.read_text(encoding="utf-8") == before


def test_refuses_when_live_canonical_text_matches_neither_old_nor_new(tmp_path, monkeypatch):
    spec_path, canon_path, gold_path, bps_path = _minimal_fixture(tmp_path)
    dataset = json.loads(canon_path.read_text(encoding="utf-8"))
    dataset["data"][0]["intel_2026"]["whatChanged"] = "SOMETHING ELSE ENTIRELY"
    canon_path.write_text(json.dumps(dataset), encoding="utf-8")
    before = gold_path.read_text(encoding="utf-8")
    rc = _run(
        monkeypatch, "--apply", "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert rc == 2
    assert gold_path.read_text(encoding="utf-8") == before


# --- the "still disputed, gold-only" shape (46496) ----------------------------


def test_still_disputed_entry_patches_gold_only_when_layers_still_disagree(tmp_path, monkeypatch):
    spec = {
        "codes": [
            {
                "code": "88822",
                "predecessor": None,
                "canonical_whatChanged": None,
                "gold_whatChanged": {"old": "Previous code(s): 33333.", "new": "unconfirmed, honestly"},
            }
        ]
    }
    spec_path = _write(tmp_path / "spec.json", spec)
    bps_path = _write(tmp_path / "bps.json", _bps_relation({"88822": ["44444"]}))  # disagrees with pp28
    canon_path = _write(
        tmp_path / "canon.json",
        {"data": [_canonical_record("88822", ["33333"], "33333", 80, "canonical text, untouched")]},
    )
    gold_path = _write(tmp_path / "gold.json", {"88822": {"whatChanged": "Previous code(s): 33333."}})

    rc = _run(
        monkeypatch, "--apply", "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert rc == 0
    _, gold, _ = mod.load_gold(gold_path)
    assert gold["88822"]["whatChanged"] == "unconfirmed, honestly"
    # canonical untouched — no canonical_whatChanged in this entry
    _, records, _, _ = mod.load_canonical(canon_path)
    assert records[0]["intel_2026"]["whatChanged"] == "canonical text, untouched"


def test_still_disputed_entry_refuses_if_the_layers_now_agree(tmp_path, monkeypatch):
    """If a re-adjudication resolved the disagreement, this spec's premise is
    stale — refuse rather than silently keep publishing 'unconfirmed'."""
    spec = {
        "codes": [
            {
                "code": "88822",
                "predecessor": None,
                "canonical_whatChanged": None,
                "gold_whatChanged": {"old": "Previous code(s): 33333.", "new": "unconfirmed, honestly"},
            }
        ]
    }
    spec_path = _write(tmp_path / "spec.json", spec)
    bps_path = _write(tmp_path / "bps.json", _bps_relation({"88822": ["33333"]}))  # NOW agrees
    canon_path = _write(
        tmp_path / "canon.json",
        {"data": [_canonical_record("88822", ["33333"], "33333", 80, "canonical text, untouched")]},
    )
    gold_path = _write(tmp_path / "gold.json", {"88822": {"whatChanged": "Previous code(s): 33333."}})
    before = gold_path.read_text(encoding="utf-8")

    rc = _run(
        monkeypatch, "--apply", "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert rc == 2
    assert gold_path.read_text(encoding="utf-8") == before


# --- innocence -----------------------------------------------------------------


def test_innocence_a_neighbor_gold_record_is_never_touched(tmp_path, monkeypatch):
    spec_path, canon_path, gold_path, bps_path = _minimal_fixture(tmp_path)
    dataset = json.loads(gold_path.read_text(encoding="utf-8"))
    dataset["neighbor_code"] = {"whatChanged": "a completely different, correct paragraph"}
    gold_path.write_text(json.dumps(dataset), encoding="utf-8")
    rc = _run(
        monkeypatch, "--apply", "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert rc == 0
    _, gold, _ = mod.load_gold(gold_path)
    assert gold["neighbor_code"]["whatChanged"] == "a completely different, correct paragraph"


def test_innocence_a_code_absent_from_gold_is_not_an_error(tmp_path, monkeypatch):
    """46415's shape: no gold entry at all — the cure must degrade gracefully,
    never treat 'not in gold' as a refusal."""
    spec_path, canon_path, gold_path, bps_path = _minimal_fixture(tmp_path)
    gold_path.write_text(json.dumps({}), encoding="utf-8")
    rc = _run(
        monkeypatch, "--apply", "--spec", str(spec_path), "--canonical", str(canon_path),
        "--gold", str(gold_path), "--bps-crosswalk", str(bps_path),
    )
    assert rc == 0
    _, records, _, _ = mod.load_canonical(canon_path)
    assert records[0]["intel_2026"]["whatChanged"] == "NEW CANONICAL — confirmed"
