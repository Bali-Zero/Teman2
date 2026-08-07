"""Guilt and innocence for the 90200 canonical whatChanged cure (item 5 of
the 2026-08-08 sector-law brief): canonical's own intel_2026.whatChanged
contradicted canonical's own bps_2020_ancestors field on the same record.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _hardened_cure_io as H  # noqa: E402
import cure_canonical_90200_whatchanged as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_SPEC = json.loads(
    (
        REPO_ROOT
        / "scripts"
        / "kbli_filiera"
        / "cure_specs"
        / "canonical_90200_whatchanged_2026_08_08.json"
    ).read_text(encoding="utf-8")
)

NEW_TEXT = (
    "Merged in KBLI 2025 from four KBLI 2020 codes (90011, 90021, 90022, "
    "90024 — performing-arts activities and venues). If you held any of "
    "those, this is your code now."
)
OLD_TEXT = (
    "This is a completely new code in KBLI 2025 — it didn't exist as a "
    "separate code in 2020. Performing arts were previously bundled with "
    "broader entertainment or cultural activity codes. The 2025 "
    "classification gives performing arts its own dedicated code."
)


def _canonical_file(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def _base_record(**overrides):
    rec = {
        "kode_kbli_2025": "90200",
        "bps_2020_ancestors": {"codes": ["90011", "90021", "90022", "90024"]},
        "intel_2026": {"whatChanged": OLD_TEXT, "riskLabel": "Low"},
    }
    rec.update(overrides)
    return rec


def _spec(**overrides):
    rec = _base_record()
    spec = {
        "code": "90200",
        "old_sha256": H.sha256_of(rec),
        "expect": {"bps_2020_ancestors.codes": ["90011", "90021", "90022", "90024"]},
        "patch": {"intel_2026.whatChanged": NEW_TEXT},
    }
    spec.update(overrides)
    return spec


def test_the_real_90200_is_cured():
    _, records, _ = H.load_dataset(mod.CANONICAL)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    rec = by_code["90200"]
    what_changed = (rec.get("intel_2026") or {}).get("whatChanged") or ""
    assert "completely new code" not in what_changed
    assert "Merged in KBLI 2025 from four KBLI 2020 codes" in what_changed
    assert rec.get("bps_2020_ancestors", {}).get("codes") == [
        "90011",
        "90021",
        "90022",
        "90024",
    ]


def test_the_real_cure_is_a_clean_noop_without_writing():
    _, records, _ = H.load_dataset(mod.CANONICAL)
    verdict = mod.plan(REAL_SPEC, records)
    assert verdict["action"] == "noop"


def test_apply_patches_the_nested_field(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    assert records[0]["intel_2026"]["whatChanged"] == NEW_TEXT


def test_apply_leaves_sibling_intel_2026_keys_alone(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    assert records[0]["intel_2026"]["riskLabel"] == "Low"


def test_second_run_without_a_backfilled_new_sha256_refuses(tmp_path, capsys):
    """ITEM J, guilt: without an explicit `new_sha256` pin, `judge_patch`
    never mistakes a hash-mismatched record for "already cured" — the exact
    blind spot the old per-key `already_patched` guess had.
    """
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0
    before = path.read_text(encoding="utf-8")
    capsys.readouterr()
    assert mod.main(argv) == 2, "no new_sha256 pin yet — must refuse, not noop"
    assert "REFUSED" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == before


def test_second_run_is_a_noop_after_new_sha256_is_backfilled(tmp_path, capsys):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0

    _, records, _ = H.load_dataset(path)
    patched_rec = {str(r.get(mod.CODE_FIELD)): r for r in records}["90200"]
    spec["new_sha256"] = H.sha256_of(patched_rec)
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    capsys.readouterr()
    assert mod.main(argv) == 0
    assert "already cured" in capsys.readouterr().out


def test_unrelated_field_drift_after_backfill_is_refused_not_noop(tmp_path, capsys):
    """ITEM J's exact ask: `intel_2026.whatChanged` still reads exactly as
    patched, but an UNRELATED field (`intel_2026.riskLabel`) moved after
    `new_sha256` was pinned — must refuse.
    """
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    argv = ["--apply", "--dataset", str(path), "--spec", str(spec_path)]
    assert mod.main(argv) == 0

    _, records, _ = H.load_dataset(path)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    spec["new_sha256"] = H.sha256_of(by_code["90200"])
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    by_code["90200"]["intel_2026"]["riskLabel"] = "mutated by a different cure entirely"
    body = json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n"
    path.write_text(body, encoding="utf-8")

    before = path.read_text(encoding="utf-8")
    capsys.readouterr()
    assert mod.main(argv) == 2, "unrelated drift must refuse, never read as noop"
    assert "REFUSED" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == before


def test_a_neighbor_record_in_a_fixture_is_never_touched(tmp_path):
    neighbor = {"kode_kbli_2025": "90001", "intel_2026": {"whatChanged": "unrelated"}}
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record(), dict(neighbor)])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 0
    _, records, _ = H.load_dataset(path)
    by_code = {str(r.get(mod.CODE_FIELD)): r for r in records}
    assert by_code["90001"] == neighbor


def test_dry_run_writes_nothing(tmp_path):
    spec = _spec()
    path = _canonical_file(tmp_path, [_base_record()])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--dataset", str(path), "--spec", str(spec_path)]) == 0
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_ancestors_have_drifted(tmp_path):
    spec = _spec()
    path = _canonical_file(
        tmp_path, [_base_record(bps_2020_ancestors={"codes": ["90011"]})]
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_whatchanged_already_rewritten_differently(tmp_path):
    spec = _spec()
    path = _canonical_file(
        tmp_path,
        [_base_record(intel_2026={"whatChanged": "a human already rewrote this"})],
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_intel_2026_missing_entirely(tmp_path):
    rec = _base_record()
    del rec["intel_2026"]
    spec = _spec()
    path = _canonical_file(tmp_path, [rec])
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path), "--spec", str(spec_path)]) == 2
    assert path.read_text(encoding="utf-8") == before
