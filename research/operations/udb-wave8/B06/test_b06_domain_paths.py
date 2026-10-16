"""Hermetic pytest suite for B06 Business-Domain Paths (D04--D10).

Strictly stdlib + pytest only. Zero live database connections, zero network
calls, and frozen metadata plus synthetic person fixtures (``+00-000-0000``, ``user@example.invalid``).
"""

from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_MANIFEST = FIXTURE_DIR / "manifest.json"


@pytest.fixture(scope="module")
def b06_mod():
    """Load ``b06_domain_paths.py`` directly by file path."""
    mod_path = Path(__file__).resolve().parent / "b06_domain_paths.py"
    spec = importlib.util.spec_from_file_location("b06_domain_paths", mod_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def matrix_index(b06_mod, repo_root: Path) -> dict[str, Any]:
    """Committed metadata projection is mandatory; absence fails rather than skips."""
    return b06_mod.load_consumer_matrix_index(
        repo_root, metadata_fixture=FIXTURE_MANIFEST
    )


def _check_convention_shape(
    b06_mod,
    repo_root: Path,
    record: dict[str, Any],
    known_consumer_ids: set[str] | None = None,
) -> list[str]:
    """Check CONTRACT-CONVENTIONS.md shape directly inside the B06 test suite."""
    errors: list[str] = []
    keys = list(record.keys())

    if len(keys) < len(b06_mod.CANONICAL_19_KEYS):
        errors.append(
            f"Record has only {len(keys)} keys; expected >= {len(b06_mod.CANONICAL_19_KEYS)}."
        )
    else:
        first_19 = tuple(keys[: len(b06_mod.CANONICAL_19_KEYS)])
        if first_19 != b06_mod.CANONICAL_19_KEYS:
            errors.append(
                f"First 19 keys do not match canonical order: got {first_19}."
            )

    extra_keys = [k for k in keys if k not in b06_mod.CANONICAL_19_KEYS]
    for extra in extra_keys:
        if not extra.startswith("x_"):
            errors.append(f"Non-canonical key '{extra}' must start with 'x_'.")
    if "x_evidence_ref" not in record:
        errors.append("Missing required 'x_evidence_ref' extension key.")

    cid = record.get("consumer_id")
    if not isinstance(cid, str) or not cid:
        errors.append("consumer_id must be a non-empty string.")
    elif known_consumer_ids is not None and cid not in known_consumer_ids:
        errors.append(f"consumer_id '{cid}' does not exist in consumer-matrix.csv.")

    unknowns = record.get("unknowns")
    if not isinstance(unknowns, list) or not all(isinstance(u, str) for u in unknowns):
        errors.append("unknowns must be a list of strings.")
        unknowns_list: list[str] = []
    else:
        unknowns_list = unknowns
        for tok in unknowns_list:
            if not b06_mod.UNKNOWN_TOKEN_RE.match(tok):
                errors.append(f"Unknown token '{tok}' is not UPPER_SNAKE.")

    op_id = record.get("operation_id")
    if op_id != "UNASSIGNED_B05":
        errors.append(
            f"B06 records must use operation_id='UNASSIGNED_B05' (got '{op_id}')."
        )
    if "OPERATION_ID_PENDING_B05" not in unknowns_list:
        errors.append("UNASSIGNED_B05 requires 'OPERATION_ID_PENDING_B05' in unknowns.")

    store_id = record.get("store_id")
    if not isinstance(store_id, str) or not b06_mod.STORE_ID_GRAMMAR_RE.match(store_id):
        errors.append(
            f"store_id '{store_id}' violates <engine>:<platform>:<instance> grammar."
        )
    if store_id == "unknown:unknown:unknown" and not any(
        u.startswith("STORE_ID_PROPOSED:") for u in unknowns_list
    ):
        errors.append(
            "store_id='unknown:unknown:unknown' requires a STORE_ID_PROPOSED:<value> token in unknowns."
        )

    if record.get("source_version") != b06_mod.BASE_COMMIT_SHA:
        errors.append("source_version must match base commit SHA.")

    if record.get("evidence_timestamp") != b06_mod.STATIC_EVIDENCE_TIMESTAMP:
        errors.append(
            f"evidence_timestamp must equal '{b06_mod.STATIC_EVIDENCE_TIMESTAMP}'."
        )
    if "STATIC_SOURCE_ONLY" not in unknowns_list:
        errors.append(
            "Static repository evidence requires 'STATIC_SOURCE_ONLY' in unknowns."
        )

    ev_sha = record.get("evidence_sha256")
    if not isinstance(ev_sha, str) or not b06_mod.SHA256_HEX_RE.match(ev_sha):
        errors.append("evidence_sha256 must be 64 lowercase hex chars.")
    elif isinstance(record.get("x_evidence_ref"), str):
        ref_rel = record["x_evidence_ref"].split(":", 1)[0]
        ref_path = repo_root / ref_rel
        if not ref_path.exists():
            errors.append(f"x_evidence_ref file '{ref_rel}' does not exist.")
        else:
            actual_sha = hashlib.sha256(ref_path.read_bytes()).hexdigest()
            if ev_sha != actual_sha:
                errors.append(
                    f"evidence_sha256 '{ev_sha}' does not match sha256 of '{ref_rel}' ('{actual_sha}')."
                )

    status = record.get("status")
    if status not in b06_mod.ALLOWED_STATUS_VALUES:
        errors.append(
            f"status '{status}' not in {sorted(b06_mod.ALLOWED_STATUS_VALUES)}."
        )

    for ikey in b06_mod.INSTANCE_11_KEYS:
        fval = record.get(ikey)
        if not isinstance(fval, dict) or set(fval.keys()) != {
            "value",
            "status",
            "evidence_ref",
        }:
            errors.append(
                f"Instance field '{ikey}' must be an object with keys {{value, status, evidence_ref}}."
            )
            continue
        fstatus = fval.get("status")
        if fstatus not in b06_mod.ALLOWED_STATUS_VALUES:
            errors.append(
                f"Instance field '{ikey}' status '{fstatus}' not in allowed enum."
            )
        if status == "EVIDENCED" and fstatus != "EVIDENCED":
            errors.append(
                f"Record status='EVIDENCED' requires field '{ikey}' status='EVIDENCED' (got '{fstatus}')."
            )

    if status == "EVIDENCED" and len(unknowns_list) > 0:
        errors.append(
            "Record cannot claim status='EVIDENCED' when unknowns is non-empty."
        )

    return errors


# ---------------------------------------------------------------------------
# 1. Explicit frozen projection with unchanged semantic census assertions
# ---------------------------------------------------------------------------


def test_pinned_csv_source_and_prefix_census_parity(
    b06_mod,
    repo_root: Path,
    matrix_index: dict[str, Any],
) -> None:
    """Compute both censuses from consumer-matrix.csv and require exact equality with 01.out and 03.out."""
    pinned = b06_mod.load_pinned_census_receipts(
        repo_root, receipts_dir=FIXTURE_DIR / "receipts"
    )
    assert pinned["shas"] == {
        "DUX-REQ-B06-01.cmd.sh": b06_mod.DUX_REQ_B06_01_CMD_SHA256,
        "DUX-REQ-B06-01.out": b06_mod.DUX_REQ_B06_01_SHA256,
        "DUX-REQ-B06-03.cmd.sh": b06_mod.DUX_REQ_B06_03_CMD_SHA256,
        "DUX-REQ-B06-03.out": b06_mod.DUX_REQ_B06_03_SHA256,
    }

    assert matrix_index["comparison_errors"] == []
    projected_reference = dict(pinned["receipt_01"], sha256=matrix_index["csv_sha256"])
    assert matrix_index["source_census"] == projected_reference
    assert matrix_index["prefix_census"] == pinned["receipt_03"]
    assert matrix_index["source_csv_sha256"] == b06_mod.CONSUMER_MATRIX_SHA256
    assert (
        matrix_index["csv_sha256"]
        == b06_mod.load_metadata_fixture(FIXTURE_MANIFEST)["projection_sha256"]
    )
    assert matrix_index["csv_sha256"] != matrix_index["source_csv_sha256"]
    assert matrix_index["raw_source_csv_read"] is False
    assert matrix_index["input_kind"] == "FROZEN_METADATA_PROJECTION"
    assert matrix_index["total_rows"] == 6029
    assert matrix_index["prefix_census"]["total_rows_in_prefixes"] == 683
    assert matrix_index["prefix_scope_status_counts"] == {
        "NOT_ENRICHED_THIS_PHASE": 504,
        "MATCHED_SOURCE_PATH_ONLY; ACTOR_IDENTITY_UNRESOLVED": 179,
    }

    summary = b06_mod.verify_all(repo_root, metadata_fixture=FIXTURE_MANIFEST)
    assert summary["ok"] is True
    assert summary["csv_present"] is True
    assert summary["errors"] == []


def test_canonical_instances_match_json_artifact_and_contract(
    b06_mod,
    repo_root: Path,
    matrix_index: dict[str, Any],
) -> None:
    """Every emitted operation instance must match domain-operation-instances.json and CONTRACT-CONVENTIONS.md."""
    instances = b06_mod.get_domain_operation_instances(repo_root)
    assert len(instances) == 21

    json_path = Path(__file__).resolve().parent / "domain-operation-instances.json"
    on_disk = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(on_disk) == 21
    assert instances == on_disk

    for idx, disk_rec in enumerate(on_disk):
        errs = _check_convention_shape(
            b06_mod, repo_root, disk_rec, matrix_index["all_consumer_ids"]
        )
        assert errs == [], f"Disk record {idx} failed contract shape: {errs}"


def test_rejects_non_x_prefixed_extension_key(
    b06_mod,
    repo_root: Path,
    matrix_index: dict[str, Any],
) -> None:
    """Guilt test: any non-canonical key without 'x_' prefix must fail."""
    bad = copy.deepcopy(b06_mod.get_domain_operation_instances(repo_root)[0])
    bad["domain_line"] = "D04"
    errs = _check_convention_shape(
        b06_mod, repo_root, bad, matrix_index["all_consumer_ids"]
    )
    assert any("must start with 'x_'" in e for e in errs)


def test_rejects_wrong_canonical_key_order(
    b06_mod,
    repo_root: Path,
    matrix_index: dict[str, Any],
) -> None:
    """Guilt test: permuting the first 19 canonical keys must fail."""
    orig = b06_mod.get_domain_operation_instances(repo_root)[0]
    swapped: dict[str, Any] = {}
    keys = list(orig.keys())
    keys[0], keys[1] = keys[1], keys[0]
    for k in keys:
        swapped[k] = orig[k]
    errs = _check_convention_shape(
        b06_mod, repo_root, swapped, matrix_index["all_consumer_ids"]
    )
    assert any("First 19 keys do not match canonical order" in e for e in errs)


def test_rejects_fabricated_consumer_id_and_operation_id(
    b06_mod,
    repo_root: Path,
    matrix_index: dict[str, Any],
) -> None:
    """Guilt test: invented consumer_id or invented B05 operation_id must fail."""
    bad = copy.deepcopy(b06_mod.get_domain_operation_instances(repo_root)[0])
    bad["consumer_id"] = "src_deadbeef00000000"
    bad["operation_id"] = "op:crm:invented:clients"
    errs = _check_convention_shape(
        b06_mod, repo_root, bad, matrix_index["all_consumer_ids"]
    )
    assert any("does not exist in consumer-matrix.csv" in e for e in errs)
    assert any("UNASSIGNED_B05" in e for e in errs)


def test_rejects_evidenced_status_when_unknowns_or_fields_incomplete(
    b06_mod,
    repo_root: Path,
    matrix_index: dict[str, Any],
) -> None:
    """Guilt test: claiming status='EVIDENCED' with non-empty unknowns or non-EVIDENCED fields must fail."""
    bad = copy.deepcopy(b06_mod.get_domain_operation_instances(repo_root)[0])
    bad["status"] = "EVIDENCED"
    errs = _check_convention_shape(
        b06_mod, repo_root, bad, matrix_index["all_consumer_ids"]
    )
    assert any("cannot claim status='EVIDENCED'" in e for e in errs)
    assert any("requires field 'role' status='EVIDENCED'" in e for e in errs)


# ---------------------------------------------------------------------------
# 2. Hermetic Synthetic Fixture Tests (Always Run via tmp_path)
# ---------------------------------------------------------------------------


def test_synthetic_csv_census_separates_source_taxonomy_from_business_labels(
    b06_mod,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    """Synthetic CSV proves source census counts real source columns/EMPTY and never business labels."""
    csv_file = tmp_path / "synthetic-consumer-matrix.csv"
    rows = [
        {
            "domain": "source-entry-candidate",
            "domain_hint": "knowledge_rag (path heuristic)",
            "disposition": "BLOCKED_DISCOVERY",
            "blocker": "ACTOR_IDENTITY_UNRESOLVED",
            "activation_status": "ACTIVE",
            "contract_coverage_status": "NOT_ESTABLISHED",
            "phase_source_scope_status": "NOT_ENRICHED_THIS_PHASE",
            "phase_source_path_evidence": "",
            "phase_factory_candidate_count": "",
            "entry_point": "apps/backend-rag/backend/services/rag/agentic.py",
            "consumer_id": "src_0000000000000001",
        },
        {
            "domain": "UNKNOWN",
            "domain_hint": "UNKNOWN",
            "disposition": "PARTIAL_DISCOVERY",
            "blocker": "",
            "activation_status": "ACTIVE",
            "contract_coverage_status": "UNCLOSED",
            "phase_source_scope_status": "MATCHED_SOURCE_PATH_ONLY; ACTOR_IDENTITY_UNRESOLVED",
            "phase_source_path_evidence": "SOURCE-REEXPORT-JOIN.json",
            "phase_factory_candidate_count": "0",
            "entry_point": "apps/backend-rag/backend/app/routers/crm_practices.py",
            "consumer_id": "src_0000000000000002",
        },
        {
            "domain": "",
            "domain_hint": "",
            "disposition": "",
            "blocker": "",
            "activation_status": "",
            "contract_coverage_status": "",
            "phase_source_scope_status": "",
            "phase_source_path_evidence": "",
            "phase_factory_candidate_count": "",
            "entry_point": "scripts/outside_prefixes.py",
            "consumer_id": "src_0000000000000003",
        },
    ]
    with csv_file.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(b06_mod.REQUIRED_CSV_HEADERS))
        writer.writeheader()
        writer.writerows(rows)

    src_census = b06_mod.compute_source_census(csv_file)
    assert src_census["total"] == 3
    assert src_census["by_domain"] == {
        "source-entry-candidate": 1,
        "UNKNOWN": 1,
        "EMPTY": 1,
    }
    assert src_census["by_domain_hint"] == {
        "knowledge_rag (path heuristic)": 1,
        "UNKNOWN": 1,
        "EMPTY": 1,
    }
    assert src_census["by_disposition_contract_status"] == {
        "BLOCKED_DISCOVERY|NOT_ESTABLISHED": 1,
        "PARTIAL_DISCOVERY|UNCLOSED": 1,
        "EMPTY|EMPTY": 1,
    }

    # Business-domain inventory uses D04..D10 in x_domain_line; none of those appear in source census
    business_lines = {
        rec["x_domain_line"]
        for rec in b06_mod.get_domain_operation_instances(repo_root)
    }
    assert business_lines == {"D04", "D05", "D06", "D07", "D08", "D09", "D10"}
    assert business_lines.isdisjoint(src_census["by_domain"].keys())
    assert business_lines.isdisjoint(src_census["by_domain_hint"].keys())

    pref_census = b06_mod.compute_prefix_census(csv_file)
    assert pref_census["total_rows_in_prefixes"] == 2
    assert b06_mod.summarize_prefix_scope_status(pref_census) == {
        "NOT_ENRICHED_THIS_PHASE": 1,
        "MATCHED_SOURCE_PATH_ONLY; ACTOR_IDENTITY_UNRESOLVED": 1,
    }


def test_tampered_receipt_counter_fails_census_compare(
    b06_mod,
    repo_root: Path,
) -> None:
    """Guilt test: mutating a counter in a receipt causes compare_census_to_receipts to report a mismatch."""
    pinned = b06_mod.load_pinned_census_receipts(
        repo_root, receipts_dir=FIXTURE_DIR / "receipts"
    )
    r01 = copy.deepcopy(pinned["receipt_01"])
    r03 = copy.deepcopy(pinned["receipt_03"])

    tampered_01 = copy.deepcopy(r01)
    tampered_01["by_domain_hint"]["UNKNOWN"] += 1
    errs_01 = b06_mod.compare_census_to_receipts(r01, r03, tampered_01, r03)
    assert any("by_domain_hint" in e for e in errs_01)

    tampered_03 = copy.deepcopy(r03)
    tampered_03["total_rows_in_prefixes"] = 999
    errs_03 = b06_mod.compare_census_to_receipts(r01, r03, r01, tampered_03)
    assert any("total_rows_in_prefixes" in e for e in errs_03)


def test_missing_csv_header_raises_value_error(
    b06_mod,
    tmp_path: Path,
) -> None:
    """Guilt test: a CSV missing phase_source_scope_status (or using 'status' instead) must raise ValueError."""
    bad_csv = tmp_path / "bad-headers.csv"
    bad_headers = [
        h if h != "phase_source_scope_status" else "status"
        for h in b06_mod.REQUIRED_CSV_HEADERS
    ]
    with bad_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=bad_headers)
        writer.writeheader()

    with pytest.raises(ValueError, match="missing required headers"):
        b06_mod.compute_source_census(bad_csv)

    with pytest.raises(ValueError, match="missing required headers"):
        b06_mod.compute_prefix_census(bad_csv)


def test_every_domain_line_d04_through_d10_has_at_least_three_paths_and_computed_shas(
    b06_mod,
    repo_root: Path,
) -> None:
    """Each of D04..D10 must have >= 3 operation instances with real per-file SHA-256."""
    instances = b06_mod.get_domain_operation_instances(repo_root)
    counts: dict[str, int] = {}
    for rec in instances:
        line = rec["x_domain_line"]
        counts[line] = counts.get(line, 0) + 1
        errs = _check_convention_shape(b06_mod, repo_root, rec)
        assert errs == [], f"Instance {rec['consumer_id']} failed shape check: {errs}"

    for expected in ("D04", "D05", "D06", "D07", "D08", "D09", "D10"):
        assert counts.get(expected, 0) >= 3, f"Missing coverage for {expected}"


def test_synthetic_phone_normalization_and_duplicate_detection(b06_mod) -> None:
    """Verify synthetic fixture '+00-000-0000' normalization without real PII."""
    digits = b06_mod.normalize_phone_digits(b06_mod.SYNTHETIC_PHONE_FIXTURE)
    assert digits == "000000000"
    assert len(digits) == 9

    existing = [
        {"id": 101, "phone": "+00 (000) 0000", "deleted_at": None},
    ]
    gate = b06_mod.evaluate_phone_duplicate_gate(
        b06_mod.SYNTHETIC_PHONE_FIXTURE, existing
    )
    assert gate["checked"] is True
    assert gate["duplicate_client_id"] == 101
    assert gate["atomic_db_constraint"] is False

    short_gate = b06_mod.evaluate_phone_duplicate_gate("+00-123", [])
    assert short_gate["checked"] is False

    deleted_existing = [
        {
            "id": 202,
            "phone": b06_mod.SYNTHETIC_PHONE_FIXTURE,
            "deleted_at": "2026-10-15T00:00:00Z",
        }
    ]
    del_gate = b06_mod.evaluate_phone_duplicate_gate(
        b06_mod.SYNTHETIC_PHONE_FIXTURE, deleted_existing
    )
    assert del_gate["checked"] is True
    assert del_gate["duplicate_client_id"] is None


def test_naga_instance_is_grounded_in_actual_save_session_source(b06_mod, repo_root):
    """The NAGA record must describe the existing writer, not an absent bridge."""
    import ast
    import hashlib
    import re

    rel = "apps/backend-rag/backend/services/naga/persist.py"
    source = (repo_root / rel).read_bytes()
    tree = ast.parse(source)
    save = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "save_session"
    )
    sql_tables = {
        table
        for node in ast.walk(save)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for table in re.findall(r"INSERT INTO\s+([a-z_]+)", node.value)
    }
    assert sql_tables == {
        "naga_sessions",
        "naga_sources",
        "naga_claims",
        "naga_claim_evidence",
    }
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "transaction"
        for node in ast.walk(save)
    )
    assert any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and node.value.value is None
        for handler in ast.walk(save)
        if isinstance(handler, ast.ExceptHandler)
        for node in ast.walk(handler)
    )

    record = next(
        row
        for row in b06_mod.get_domain_operation_instances(repo_root)
        if row["consumer_id"] == "src_b3bccbae2cc91a8c"
    )
    span = f"{save.lineno}-{save.end_lineno}"
    assert record["x_evidence_ref"] == f"{rel}:{span}"
    assert record["x_source_line_span"] == span
    assert record["evidence_sha256"] == hashlib.sha256(source).hexdigest()
    assert record["role"]["status"] == "UNKNOWN"
    assert record["status"] == "PARTIAL"
    assert {
        "STATIC_SOURCE_ONLY",
        "ACTOR_IDENTITY_UNRESOLVED",
        "REPLAY_IDEMPOTENCY_UNPROVED",
        "CLAIM_EXPIRY_NOT_ERASURE_PROOF",
    }.issubset(record["unknowns"])
    assert record["effects"]["value"] == [
        "INSERT INTO naga_sessions",
        "INSERT INTO naga_sources; ON CONFLICT (url, session_id) DO NOTHING",
        "INSERT INTO naga_claims",
        "INSERT INTO naga_claim_evidence; ON CONFLICT (claim_id, source_id, relation) DO NOTHING",
    ]
    assert "new session UUID" in record["idempotency"]["value"]
    assert "returns None" in record["failure"]["value"]
    assert (
        "30 days" in record["retention"]["value"]
        and "90 days" in record["retention"]["value"]
    )
    assert "does not prove erasure" in record["retention"]["value"]
    assert "research_os_objects" not in json.dumps(record)


def test_missing_evidence_file_still_fails_closed(b06_mod, tmp_path):
    """Missing source evidence must never receive a fabricated or fallback digest."""
    with pytest.raises(FileNotFoundError):
        b06_mod._compute_ref_file_sha256(tmp_path, "absent_writer.py:1-9")


def _copy_metadata_fixture(tmp_path: Path) -> Path:
    import shutil

    root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, root)
    return root / "manifest.json"


def test_projection_byte_tamper_fails_before_census(
    b06_mod, repo_root: Path, tmp_path: Path
) -> None:
    manifest = _copy_metadata_fixture(tmp_path)
    csv_path = manifest.parent / "consumer-matrix-metadata.csv"
    csv_path.write_bytes(csv_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Metadata projection SHA256 mismatch"):
        b06_mod.load_consumer_matrix_index(repo_root, metadata_fixture=manifest)


def test_fixture_manifest_source_pin_tamper_is_rejected(
    b06_mod, tmp_path: Path
) -> None:
    manifest = _copy_metadata_fixture(tmp_path)
    data = json.loads(manifest.read_text())
    data["source_csv_sha256"] = "0" * 64
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="manifest SHA256 mismatch"):
        b06_mod.load_metadata_fixture(manifest)


def test_missing_projection_fails_instead_of_skip(
    b06_mod, repo_root: Path, tmp_path: Path
) -> None:
    manifest = _copy_metadata_fixture(tmp_path)
    (manifest.parent / "consumer-matrix-metadata.csv").unlink()
    with pytest.raises(FileNotFoundError):
        b06_mod.load_consumer_matrix_index(repo_root, metadata_fixture=manifest)


def test_admitted_counter_receipt_byte_tamper_is_rejected(
    b06_mod, repo_root: Path, tmp_path: Path
) -> None:
    manifest = _copy_metadata_fixture(tmp_path)
    receipt = manifest.parent / "receipts/DUX-REQ-B06-01.out"
    receipt.write_bytes(receipt.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Pinned receipt SHA-256 mismatch"):
        b06_mod.load_consumer_matrix_index(repo_root, metadata_fixture=manifest)


def test_clean_checkout_fixture_cli_labels_both_byte_identities(
    b06_mod, repo_root: Path, capsys
) -> None:
    assert (
        b06_mod.main(
            ["--repo-root", str(repo_root), "--metadata-fixture", str(FIXTURE_MANIFEST)]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["instance_count"] == 21
    assert output["source_census_total"] == 6029
    assert output["prefix_census_total"] == 683
    assert output["source_csv_sha256"] == b06_mod.CONSUMER_MATRIX_SHA256
    assert output["processed_csv_sha256"] != output["source_csv_sha256"]
    assert output["raw_source_csv_read"] is False
    assert output["input_kind"] == "FROZEN_METADATA_PROJECTION"
