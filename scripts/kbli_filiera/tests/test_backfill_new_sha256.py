"""Guilt and innocence for `backfill_new_sha256.py` (item J, 2026-08-08
fix-pack): the repo-wide tool that pins `new_sha256` into a cure spec AFTER
its patch has landed, so `H.judge_patch()` has both pins to resume against.

The dangerous direction here is not symmetric. Backfilling a record that has
NOT actually been patched yet would pin the UNPATCHED state as "new" —
silently disabling the idempotency check forever, the exact failure mode
this whole hardening effort exists to close, reintroduced by its own tool.
That refusal gets most of the guilt coverage below.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _hardened_cure_io as H  # noqa: E402
import backfill_new_sha256 as mod  # noqa: E402


def _canonical_file(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def _base_record(**overrides):
    rec = {"kode_kbli_2025": "65112", "pma_status": "TERBUKA", "pma_max_asing": 100}
    rec.update(overrides)
    return rec


def _patched_record(**overrides):
    return _base_record(pma_status="TERBATAS", pma_max_asing=80, **overrides)


# --------------------------------------------------------------------------
# GUILT — backfilling before the patch has landed must never pin the
# unpatched state as "new"
# --------------------------------------------------------------------------


def test_refuses_to_backfill_a_record_that_still_hashes_to_old_sha256(tmp_path):
    rec = _base_record()
    spec = {
        "codes": {
            "65112": {"old_sha256": H.sha256_of(rec), "patch": {"pma_status": "TERBATAS"}}
        }
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    dataset = _canonical_file(tmp_path, [rec])

    rc = mod.main(["--spec", str(spec_path), "--dataset", str(dataset), "--write"])
    assert rc == 2
    on_disk = json.loads(spec_path.read_text())
    assert "new_sha256" not in on_disk["codes"]["65112"]


def test_check_mode_is_the_default_and_writes_nothing(tmp_path):
    rec = _patched_record()
    spec = {
        "codes": {
            "65112": {"old_sha256": H.sha256_of(_base_record()), "patch": {"pma_status": "TERBATAS"}}
        }
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    dataset = _canonical_file(tmp_path, [rec])
    before = spec_path.read_text(encoding="utf-8")

    rc = mod.main(["--spec", str(spec_path), "--dataset", str(dataset)])
    assert rc == 0
    assert spec_path.read_text(encoding="utf-8") == before


def test_refuses_when_the_code_is_missing_from_canonical(tmp_path):
    spec = {
        "codes": {
            "65112": {"old_sha256": H.sha256_of(_base_record()), "patch": {"pma_status": "TERBATAS"}}
        }
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    dataset = _canonical_file(tmp_path, [{"kode_kbli_2025": "99999"}])

    rc = mod.main(["--spec", str(spec_path), "--dataset", str(dataset), "--write"])
    assert rc == 2


def test_refuses_to_overwrite_a_new_sha256_that_no_longer_matches_without_force(tmp_path):
    """A second, DIFFERENT cure moved the record again after the first
    backfill — must not silently re-pin over evidence of that move."""
    patched = _patched_record()
    stale_pin = "0" * 64
    spec = {
        "codes": {
            "65112": {
                "old_sha256": H.sha256_of(_base_record()),
                "new_sha256": stale_pin,
                "patch": {"pma_status": "TERBATAS"},
            }
        }
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    dataset = _canonical_file(tmp_path, [patched])

    rc = mod.main(["--spec", str(spec_path), "--dataset", str(dataset), "--write"])
    assert rc == 2
    on_disk = json.loads(spec_path.read_text())
    assert on_disk["codes"]["65112"]["new_sha256"] == stale_pin


# --------------------------------------------------------------------------
# INNOCENCE — the normal path, and the idempotent/force escape hatches
# --------------------------------------------------------------------------


def test_backfills_a_genuinely_patched_record_multi_code_shape(tmp_path):
    patched = _patched_record()
    spec = {
        "codes": {
            "65112": {"old_sha256": H.sha256_of(_base_record()), "patch": {"pma_status": "TERBATAS"}}
        }
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    dataset = _canonical_file(tmp_path, [patched])

    rc = mod.main(["--spec", str(spec_path), "--dataset", str(dataset), "--write"])
    assert rc == 0
    on_disk = json.loads(spec_path.read_text())
    assert on_disk["codes"]["65112"]["new_sha256"] == H.sha256_of(patched)


def test_backfills_a_genuinely_patched_record_single_code_shape(tmp_path):
    """`cure_canonical_47221_kondisi.py` / `cure_canonical_90200_whatchanged.py`
    use a top-level `code` + `old_sha256`, not a `codes` map."""
    patched = _patched_record()
    spec = {
        "code": "65112",
        "old_sha256": H.sha256_of(_base_record()),
        "patch": {"pma_status": "TERBATAS"},
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    dataset = _canonical_file(tmp_path, [patched])

    rc = mod.main(["--spec", str(spec_path), "--dataset", str(dataset), "--write"])
    assert rc == 0
    on_disk = json.loads(spec_path.read_text())
    assert on_disk["new_sha256"] == H.sha256_of(patched)
    assert on_disk["code"] == "65112", "the rest of the spec must survive untouched"
    assert on_disk["old_sha256"] == spec["old_sha256"]


def test_a_second_backfill_that_still_matches_is_a_clean_noop(tmp_path):
    patched = _patched_record()
    spec = {
        "codes": {
            "65112": {"old_sha256": H.sha256_of(_base_record()), "patch": {"pma_status": "TERBATAS"}}
        }
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    dataset = _canonical_file(tmp_path, [patched])

    assert mod.main(["--spec", str(spec_path), "--dataset", str(dataset), "--write"]) == 0
    after_first = spec_path.read_text(encoding="utf-8")
    assert mod.main(["--spec", str(spec_path), "--dataset", str(dataset), "--write"]) == 0
    assert spec_path.read_text(encoding="utf-8") == after_first, "a clean noop must not rewrite the file"


def test_force_overwrites_a_stale_new_sha256(tmp_path):
    patched = _patched_record()
    stale_pin = "0" * 64
    spec = {
        "codes": {
            "65112": {
                "old_sha256": H.sha256_of(_base_record()),
                "new_sha256": stale_pin,
                "patch": {"pma_status": "TERBATAS"},
            }
        }
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    dataset = _canonical_file(tmp_path, [patched])

    rc = mod.main(["--spec", str(spec_path), "--dataset", str(dataset), "--write", "--force"])
    assert rc == 0
    on_disk = json.loads(spec_path.read_text())
    assert on_disk["codes"]["65112"]["new_sha256"] == H.sha256_of(patched)
