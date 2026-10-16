"""Reproducibility and evidence separation from a checkout without local receipts."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AREA = Path(__file__).resolve().parent
ROOT = AREA.parents[3]
SPEC = importlib.util.spec_from_file_location("b05_input_validation", AREA / "b05_contracts_validator.py")
assert SPEC and SPEC.loader
B05 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B05)


@pytest.fixture
def clean_root(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    destination = root / AREA.relative_to(ROOT)
    shutil.copytree(AREA, destination, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    matrix = root / B05.MATRIX_FIXTURE
    matrix.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / B05.MATRIX_FIXTURE, matrix)
    assert not (root / ".git").exists()
    assert not (root / ".agent-receipts").exists()
    return root


def test_default_clean_checkout_replays_exact_original_bytes(clean_root: Path) -> None:
    area = clean_root / AREA.relative_to(ROOT)
    result = subprocess.run(
        [sys.executable, str(area / "b05_contracts_validator.py"), "--validate"],
        cwd=clean_root, capture_output=True,
    )
    assert result.returncode == 0
    output = clean_root / "generated"
    assert B05.main(["--repo-root", str(clean_root), "--out-dir", str(output), "--generate", "--validate"]) == 0
    for name in ("operation-contracts.json", "operation-contracts.csv"):
        assert (output / name).read_bytes() == (AREA / name).read_bytes()
    data = json.loads((output / "operation-contracts.json").read_text())
    denominator = data["denominator_accounting"]
    assert denominator["total_leads"] == 6030
    assert denominator["consumer_matrix_csv_rows"] == 6029
    assert denominator["census_bucket_count"] == 33
    assert denominator["complete_operation_contracts"] == 0
    assert denominator["active_consumer_denominator"] == "UNKNOWN"
    assert len(data["operation_contracts"]) == 23


@pytest.mark.parametrize("rel", [*B05.HISTORICAL_INPUTS, B05.MATRIX_INPUT])
@pytest.mark.parametrize("damage", ["missing", "tampered"])
def test_every_historical_input_is_required_and_pinned(clean_root: Path, rel: str, damage: str) -> None:
    target = B05.resolve_input(clean_root, rel)
    if damage == "missing":
        target.unlink()
    else:
        target.write_bytes(target.read_bytes() + b"\nTAMPERED\n")
    output = clean_root / "rejected-output"
    assert B05.main(["--repo-root", str(clean_root), "--out-dir", str(output), "--generate"]) == 1
    assert not (output / "operation-contracts.json").exists()


def test_current_changes_do_not_rewrite_history_or_claim_coverage(clean_root: Path) -> None:
    for rel in B05.SOURCE_INPUTS:
        destination = clean_root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, destination)
    historical = json.dumps(B05.build_artifact_payload(clean_root), sort_keys=True)
    output = clean_root / "observations"
    args = ["--repo-root", str(clean_root), "--out-dir", str(output), "--mode", "current"]
    assert B05.main([*args, "--generate", "--validate"]) == 0
    before = json.loads((output / "current-source-observation.json").read_text())
    rel = B05.PINNED_RELPATHS["conversation_repository.py"]
    with (clean_root / rel).open("a") as stream:
        stream.write("\n# Test source version change.\n")
    assert B05.main([*args, "--validate"]) == 1
    assert B05.main([*args, "--generate", "--validate"]) == 0
    after = json.loads((output / "current-source-observation.json").read_text())
    assert before["source_sha256"][rel] != after["source_sha256"][rel]
    assert after["ast_observations"]["conversation_repository"]["sha256"] == after["source_sha256"][rel]
    assert after["operation_contracts"] == []
    assert after["operation_contracts_status"] == "UNASSESSED"
    assert after["active_consumer_denominator"] == "UNKNOWN"
    assert not (output / "operation-contracts.json").exists()
    assert json.dumps(B05.build_artifact_payload(clean_root), sort_keys=True) == historical


def test_missing_current_source_fails_without_fabricating_report(clean_root: Path) -> None:
    output = clean_root / "observations"
    assert B05.main(["--repo-root", str(clean_root), "--out-dir", str(output), "--mode", "current", "--generate"]) == 1
    assert not (output / "current-source-observation.json").exists()
