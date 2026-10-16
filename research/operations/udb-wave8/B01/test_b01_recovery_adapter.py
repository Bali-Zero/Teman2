"""Pytest suite for B01 recovery adapter, CONTRACT-CONVENTIONS.md compliance,
and the four adversary guilt/innocence cases.

Stdlib + pytest only. No network, no live production store connections, no PII.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parent


def _load_adapter():
    spec = importlib.util.spec_from_file_location(
        "b01_recovery_adapter", _DIR / "b01_recovery_adapter.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


adapter = _load_adapter()


def test_pinned_input_hashes_verify_cleanly():
    verified = adapter.verify_pinned_inputs(adapter.REPO_ROOT)
    assert (
        verified[".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json"]
        == "9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d"
    )
    assert (
        verified[".agent-receipts/udb-wave8-inputs/STATE.json"]
        == "caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4"
    )
    assert (
        verified[
            ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json"
        ]
        == "91e6bac9c91181a2b3aa3f6cd1dc6585671c18ce90cb887444229a1a17a084e7"
    )


def test_verify_pinned_inputs_refuses_on_hash_mismatch(tmp_path):
    """Negative case: corrupted input SHA-256 must raise ValueError."""
    inputs_dir = tmp_path / ".agent-receipts/udb-wave8-inputs"
    inputs_dir.mkdir(parents=True)
    (inputs_dir / "REAL-RUN-RECEIPT.json").write_text("{}", encoding="utf-8")
    (inputs_dir / "INPUT-MANIFEST.json").write_text(
        json.dumps(
            {
                "files": {
                    "REAL-RUN-RECEIPT.json": "0" * 64,
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        adapter.verify_pinned_inputs(tmp_path)


def test_b01_records_conform_to_contract_conventions():
    bundle = adapter.build_b01_records(adapter.REPO_ROOT)
    obs = bundle["real_run_observation"]

    # Verified receipt facts (B01-F1, B01-F2, B01-F8):
    assert obs["started_at"] == "2026-10-15T03:00:43.925327+00:00"
    assert obs["terminal_timestamp"] == "2026-10-15T03:02:11+00:00"
    assert obs["elapsed_seconds"] == 87.658
    assert obs["source_pin_matches"] == 6
    assert obs["verifier_aggregate"] == "CANNOT-VERIFY"
    assert obs["relation_count"] == 5
    assert (
        obs["raw_report_sha256"]
        == "1d368c2d16d32a0834bb7d120d75005423227b77239107b1dc1873f8140b5744"
    )
    assert obs["rows_counts_and_raw_errors_exported"] is False

    # Historical restore source references from LEAD-DELTA.json:
    hist_ids = [r["consumer_id"] for r in bundle["historical_restore_references"]]
    assert hist_ids == [
        "src_307bea3dfb94ec31",
        "src_d073f505ff1671ad",
        "src_def7a4c288a552af",
        "src_cdf3ae5e4ecf861c",
        "src_2f350566b97aee80",
    ]

    records = bundle["records"]
    assert len(records) == 1
    rec = records[0]
    assert rec["consumer_id"] == "runtime_mini_46522da0ef79d3aa7422ca41"
    assert rec["operation_id"] == "UNASSIGNED_B05"
    assert rec["store_id"] == "unknown:unknown:unknown"
    assert rec["source_version"] == "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
    assert rec["evidence_timestamp"] == "2026-10-15T03:02:11+00:00"
    assert (
        rec["evidence_sha256"]
        == "9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d"
    )
    assert rec["status"] == "BLOCKED"
    assert "OPERATION_ID_PENDING_B05" in rec["unknowns"]
    assert "STORE_ID_PROPOSED:pg:mini:nuzantara-pg-drill/public" in rec["unknowns"]
    assert rec["x_verifier_aggregate"] == "CANNOT-VERIFY"
    assert rec["x_mini_install_required"] is True


def test_validate_contract_instance_record_rejects_invalid_shapes():
    """Negative cases for CONTRACT-CONVENTIONS.md (X1, X2, X3, X4, X10, B01-F9)."""
    bundle = adapter.build_b01_records(adapter.REPO_ROOT)
    base_rec = bundle["records"][0]
    valid_ids = frozenset({"runtime_mini_46522da0ef79d3aa7422ca41"})

    # 1. Reject non-x_ extra key (X4)
    bad_extra = copy.deepcopy(base_rec)
    bad_extra["unprefixed_extra"] = 123
    with pytest.raises(ValueError, match="must start with 'x_'"):
        adapter.validate_contract_instance_record(bad_extra, valid_ids)

    # 2. Reject fabricated consumer_id not in 6,030-lead universe (X10, B01-F9)
    bad_cid = copy.deepcopy(base_rec)
    bad_cid["consumer_id"] = "mini.restore_drill"
    with pytest.raises(ValueError, match="not in pinned 6,030-lead universe"):
        adapter.validate_contract_instance_record(bad_cid, valid_ids)

    # 3. Reject non-conventions status 'FAIL' (X3, B01-F9)
    bad_status = copy.deepcopy(base_rec)
    bad_status["status"] = "FAIL"
    with pytest.raises(ValueError, match="Invalid row status"):
        adapter.validate_contract_instance_record(bad_status, valid_ids)

    # 4. Reject EVIDENCED when unknowns is non-empty
    bad_evidenced = copy.deepcopy(base_rec)
    bad_evidenced["status"] = "EVIDENCED"
    with pytest.raises(ValueError, match="unknowns must be empty when status is EVIDENCED"):
        adapter.validate_contract_instance_record(bad_evidenced, valid_ids)


def test_synthetic_pg17_four_adversary_guilt_and_innocence_cases():
    """Run the throwaway PG17 socket suite when local PG17 binaries are available."""
    res = adapter.run_synthetic_pg17_suite(adapter.REPO_ROOT)
    if res.get("status") == "SKIPPED_PG17_BINARIES_NOT_FOUND":
        pytest.skip("Local PostgreSQL 17 initdb/postgres/psql binaries not in PATH")
    assert res["synthetic_only"] is True
    assert res["production_connections_requested"] is False
    assert res["tcp_listener_requested"] is False
    for check_name, passed in res["checks"].items():
        assert passed is True, f"Synthetic PG17 check failed: {check_name} -> {res}"
    assert res["all_passed"] is True


# --- Hermetic inputs: a clean checkout has no gitignored `.agent-receipts/` ---------------------

_FIXTURES = _DIR / "fixtures"


def _fixture_only_checkout(tmp_path: Path) -> Path:
    """A clean checkout: the committed fixtures and NO `.agent-receipts/` directory."""
    shutil.copytree(_FIXTURES, tmp_path / adapter.FIXTURES_REL)
    return tmp_path


def test_clean_checkout_resolves_inputs_from_committed_fixtures(tmp_path):
    root = _fixture_only_checkout(tmp_path)
    assert not (root / ".agent-receipts").exists()
    assert adapter._use_fixtures(root) is True

    verified = adapter.verify_pinned_inputs(root)
    # Byte-identical copies report the SOURCE sha256 under the source path ...
    assert (
        verified[".agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json"]
        == "9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d"
    )
    assert (
        verified[".agent-receipts/udb-wave8-inputs/STATE.json"]
        == "caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4"
    )
    assert (
        verified[
            ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json"
        ]
        == "91e6bac9c91181a2b3aa3f6cd1dc6585671c18ce90cb887444229a1a17a084e7"
    )
    # ... the projection is reported under its OWN path and never as the source's bytes.
    assert ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv" not in verified
    assert (
        verified[f"{adapter.FIXTURES_REL}/consumer-matrix.projection.csv"]
        == "d743bfb90c0ece5c40288bac0bb041c1842db8cf1088255b38f8462061b6d70f"
    )

    bundle = adapter.build_b01_records(root)
    assert bundle["input_resolution"]["mode"] == "COMMITTED_FIXTURES"
    committed = json.loads((_DIR / "b01-recovery-instances.json").read_text(encoding="utf-8"))
    assert bundle["records"] == committed
    refs = bundle["historical_restore_references"]
    assert [r["consumer_id"] for r in refs] == [
        "src_307bea3dfb94ec31",
        "src_d073f505ff1671ad",
        "src_def7a4c288a552af",
        "src_cdf3ae5e4ecf861c",
        "src_2f350566b97aee80",
    ]
    for ref in refs:
        for column in ("entry_point", "store", "disposition", "evidence"):
            assert ref[column], f"projected column {column} is blank for {ref['consumer_id']}"


@pytest.mark.parametrize("name", list(adapter.FIXTURE_PINS))
def test_tampered_fixture_is_rejected(tmp_path, name):
    root = _fixture_only_checkout(tmp_path)
    target = root / adapter.FIXTURES_REL / name
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        adapter.verify_pinned_inputs(root)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        adapter.build_b01_records(root)


def test_tampered_fixture_with_rewritten_provenance_is_still_rejected(tmp_path):
    """PROVENANCE.json is not the trust anchor: the adapter pins win."""
    root = _fixture_only_checkout(tmp_path)
    fixtures = root / adapter.FIXTURES_REL
    projection = fixtures / "consumer-matrix.projection.csv"
    projection.write_bytes(projection.read_bytes() + b"runtime_forged_id,,,,\n")
    provenance = json.loads((fixtures / "PROVENANCE.json").read_text(encoding="utf-8"))
    provenance["fixtures"]["consumer-matrix.projection.csv"]["output_sha256"] = hashlib.sha256(
        projection.read_bytes()
    ).hexdigest()
    (fixtures / "PROVENANCE.json").write_text(json.dumps(provenance), encoding="utf-8")
    with pytest.raises(ValueError, match="disagrees with the adapter pin"):
        adapter.verify_pinned_inputs(root)


def test_fixture_provenance_separates_copies_from_the_projection():
    provenance = json.loads((_FIXTURES / "PROVENANCE.json").read_text(encoding="utf-8"))
    entries = provenance["fixtures"]
    assert set(entries) == set(adapter.FIXTURE_PINS)
    for name, entry in entries.items():
        assert entry["kind"] == "FROZEN_METADATA_TEST_FIXTURES_NOT_NEW_NATIVE_OBSERVATIONS"
        assert hashlib.sha256((_FIXTURES / name).read_bytes()).hexdigest() == entry["output_sha256"]
        is_copy = entry["identity"] == "BYTE_IDENTICAL_COPY"
        # A copy has the source's bytes; a projection must not claim them.
        assert (entry["source_sha256"] == entry["output_sha256"]) is is_copy
    assert entries["consumer-matrix.projection.csv"]["identity"] == "PROJECTION_NOT_SOURCE_BYTES"


def test_corrupt_receipts_are_not_masked_by_fixtures(tmp_path):
    root = _fixture_only_checkout(tmp_path)
    inputs_dir = root / ".agent-receipts/udb-wave8-inputs"
    inputs_dir.mkdir(parents=True)
    (inputs_dir / "REAL-RUN-RECEIPT.json").write_text("{}", encoding="utf-8")
    (inputs_dir / "INPUT-MANIFEST.json").write_text(
        json.dumps({"files": {"REAL-RUN-RECEIPT.json": "0" * 64}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="SHA-256 mismatch for REAL-RUN-RECEIPT.json"):
        adapter.verify_pinned_inputs(root)


def test_neither_receipts_nor_fixtures_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError, match="PROVENANCE.json"):
        adapter.verify_pinned_inputs(tmp_path)
