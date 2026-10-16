"""Hermetic-input tests for `redis_consumer_census.py` (B02).

The census must be reproducible from COMMITTED files only: the gitignored `.agent-receipts/`
tree is used when present, otherwise the sha256-pinned `fixtures/` (frozen metadata test fixtures,
NOT new native observations). Every test here runs unconditionally: no skip, no xfail, and no
dependency on `.agent-receipts/` being absent or present.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any

import pytest

B02_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES_DIR = B02_DIR / "fixtures"
MATRIX_FIXTURE = "consumer-matrix.projection.csv"
SMALL_FIXTURES = ("LEAD-DELTA.json", "REDIS-PRO-METADATA.json", "REDIS-MINI-METADATA.json")
FIXTURE_KIND = "FROZEN_METADATA_TEST_FIXTURES_NOT_NEW_NATIVE_OBSERVATIONS"

# sha256 of the ledger the census writes from the original `.agent-receipts` inputs. Fixture mode
# must reproduce it byte for byte (the ledger carries no tmp path or timestamp of the run).
GOLDEN_LEDGER_SHA256 = "5b93933aa296d67458846521d1d7c1f2a192898fa5567f8ceeb1a4a5d72f62cc"

FORBIDDEN_CONTENT: dict[str, re.Pattern[str]] = {
    "absolute_users_path": re.compile(r"/Users/"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone_international": re.compile(r"(?<![\w+])\+\d[\d ().-]{7,}\d"),
    "phone_local": re.compile(r"(?<![\w-])0\d{2,3}[ .-]\d{3,4}[ .-]\d{3,5}(?![\w-])"),
    "pem_block": re.compile(r"-----BEGIN"),
    "url_userinfo": re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
    "token_shape": re.compile(
        r"sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_|xox[baprs]-|AKIA[0-9A-Z]{16}"
        r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    ),
    "assigned_secret": re.compile(
        r"(?i)(password|secret|token|api_?key)\s*[=:]\s*[^\s,;]{6,}"
    ),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _census() -> Any:
    name = "b02_redis_consumer_census_hermetic"
    spec = importlib.util.spec_from_file_location(name, B02_DIR / "redis_consumer_census.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _provenance() -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / "PROVENANCE.json").read_text(encoding="utf-8"))


def test_fixture_set_and_provenance_match_the_pinned_identities() -> None:
    census = _census()
    prov = _provenance()
    assert prov["kind"] == FIXTURE_KIND
    entries = {e["fixture"]: e for e in prov["files"]}
    assert set(entries) == {MATRIX_FIXTURE, *SMALL_FIXTURES}
    on_disk = {p.name for p in FIXTURES_DIR.iterdir() if not p.name.startswith(".")}
    assert on_disk == {*entries, "PROVENANCE.json"}, "fixtures/ holds only the declared data"

    for name, entry in entries.items():
        data = (FIXTURES_DIR / name).read_bytes()
        assert _sha(data) == entry["output_sha256"]
        assert len(data) == entry["output_bytes"]
        assert entry["source"].startswith(".agent-receipts/")

    matrix = entries[MATRIX_FIXTURE]
    assert matrix["relation"] == "PROJECTION_NOT_BYTE_IDENTICAL_TO_SOURCE"
    assert matrix["source_sha256"] == census.SOURCE_CSV_SHA256
    assert matrix["output_sha256"] == census.FIXTURE_PROJECTION_SHA256
    assert matrix["output_sha256"] != matrix["source_sha256"]
    assert matrix["projected_columns"] == list(census.PROJECTED_COLUMNS)
    text = (FIXTURES_DIR / MATRIX_FIXTURE).read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    assert reader.fieldnames == list(census.PROJECTED_COLUMNS)
    rows = list(reader)
    assert len(rows) == matrix["rows"] == 6029
    unread = matrix["blanked_cells"]["columns"]
    assert unread == [c for c in census.PROJECTED_COLUMNS if c not in census.ALL_ROWS_COLUMNS]
    redis_rows = [r for r in rows if "redis" in census._store_tokens(r)]
    assert len(redis_rows) == matrix["redis_tagged_rows"]
    assert matrix["blanked_cells"]["blanked_rows"] == len(rows) - len(redis_rows)
    for row in rows:
        if "redis" not in census._store_tokens(row):
            assert all(row[c] == "" for c in unread)
    # pre-commit check-added-large-files (--maxkb=1000) applies to every committed fixture
    assert all((FIXTURES_DIR / n).stat().st_size < 1000 * 1024 for n in entries)

    pinned = {
        "LEAD-DELTA.json": census.LEAD_DELTA_SHA256,
        "REDIS-PRO-METADATA.json": census.REDIS_PRO_METADATA_SHA256,
        "REDIS-MINI-METADATA.json": census.REDIS_MINI_METADATA_SHA256,
    }
    for name, want in pinned.items():
        assert entries[name]["relation"] == "BYTE_IDENTICAL_COPY"
        assert entries[name]["source_sha256"] == entries[name]["output_sha256"] == want


def test_fixtures_carry_no_home_path_contact_or_credential_shape() -> None:
    for path in sorted(p for p in FIXTURES_DIR.iterdir() if not p.name.startswith(".")):
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_CONTENT.items():
            assert pattern.search(text) is None, f"{path.name}: {label}"


def test_projection_encoding_is_reversible_and_reproduces_the_fixture() -> None:
    census = _census()
    fixture = (FIXTURES_DIR / MATRIX_FIXTURE).read_bytes()
    decoded = fixture.decode("utf-8").replace(
        census.USERS_ROOT_SENTINEL, census.USERS_ROOT_LITERAL
    )
    assert census.USERS_ROOT_SENTINEL not in decoded
    assert census.project_consumer_matrix(decoded.encode("utf-8")) == fixture


def test_fixture_mode_census_reproduces_the_golden_ledger(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    census = _census()
    out_file = tmp_path / "ledger.json"
    rc = census.main(
        ["--repo-root", str(REPO_ROOT), "--output", str(out_file), "--inputs", "fixtures"]
    )
    assert rc == 0
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["input_source"] == "committed-fixtures"
    assert stdout["matrix_projection_sha256"] == census.FIXTURE_PROJECTION_SHA256
    assert _sha(out_file.read_bytes()) == GOLDEN_LEDGER_SHA256 == stdout["output_sha256"]
    ledger = json.loads(out_file.read_text(encoding="utf-8"))
    assert ledger["summary"]["union_universe_count"] == 6030
    assert ledger["summary"]["csv_baseline_rows"] == 6029
    assert ledger["inputs_pinned"]["consumer_matrix_csv_sha256"] == census.SOURCE_CSV_SHA256


def test_auto_mode_matches_the_golden_ledger_with_or_without_receipts(tmp_path: Path) -> None:
    census = _census()
    receipts_matrix = REPO_ROOT / ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    inputs = census.resolve_inputs(REPO_ROOT)
    if receipts_matrix.exists():
        assert inputs.source == "agent-receipts"
        source = receipts_matrix.read_bytes()
        assert _sha(source) == census.SOURCE_CSV_SHA256
        assert _sha(census.project_consumer_matrix(source)) == census.FIXTURE_PROJECTION_SHA256
    else:
        assert inputs.source == "committed-fixtures"
    out_file = tmp_path / "ledger.json"
    assert census.main(["--repo-root", str(REPO_ROOT), "--output", str(out_file)]) == 0
    assert _sha(out_file.read_bytes()) == GOLDEN_LEDGER_SHA256


def test_tampered_or_missing_fixture_fails_closed(tmp_path: Path) -> None:
    census = _census()
    root = tmp_path / "repo"
    fixtures = root / census.FIXTURES_REL
    shutil.copytree(FIXTURES_DIR, fixtures)
    assert census.resolve_inputs(root, "fixtures").source == "committed-fixtures"

    with pytest.raises(ValueError):
        census.resolve_inputs(root, "bogus")

    matrix = fixtures / MATRIX_FIXTURE
    original = matrix.read_bytes()
    matrix.write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        census.resolve_inputs(root, "fixtures")
    matrix.write_bytes(original)

    lead = fixtures / "LEAD-DELTA.json"
    lead_original = lead.read_bytes()
    lead.write_bytes(lead_original + b" ")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        census.resolve_inputs(root, "fixtures")
    lead.write_bytes(lead_original)

    (fixtures / "REDIS-PRO-METADATA.json").unlink()
    with pytest.raises(FileNotFoundError):
        census.resolve_inputs(root, "fixtures")


def test_receipt_identity_does_not_require_unshipped_raw_outputs(tmp_path: Path) -> None:
    census = _census()
    root = tmp_path / "clean"
    fixture_dir = root / "research/operations/udb-wave8/B02/fixtures"
    shutil.copytree(FIXTURES_DIR, fixture_dir)
    expected = census.generate_census(REPO_ROOT, census.resolve_inputs(REPO_ROOT, "fixtures"))
    actual = census.generate_census(root, census.resolve_inputs(root, "fixtures"))
    assert actual == expected
    assert not (root / "research/operations/udb-wave8/B02/dux-requests").exists()


def test_present_but_unadmitted_raw_receipt_is_rejected(tmp_path: Path) -> None:
    census = _census()
    request_dir = tmp_path / "research/operations/udb-wave8/B02/dux-requests"
    request_dir.mkdir(parents=True)
    (request_dir / "DUX-REQ-B02-03.out").write_bytes(b"changed historical receipt")
    with pytest.raises(ValueError, match="^DUX_RECEIPT_PIN_MISMATCH$"):
        census.admitted_dux_receipt_hashes(tmp_path)


def test_symlink_receipt_is_not_an_admitted_historical_identity(tmp_path: Path) -> None:
    census = _census()
    request_dir = tmp_path / "research/operations/udb-wave8/B02/dux-requests"
    request_dir.mkdir(parents=True)
    target = tmp_path / "unadmitted"
    target.write_bytes(b"changed historical receipt")
    (request_dir / "DUX-REQ-B02-03.out").symlink_to(target)
    with pytest.raises(ValueError, match="^DUX_RECEIPT_PIN_MISMATCH$"):
        census.admitted_dux_receipt_hashes(tmp_path)
