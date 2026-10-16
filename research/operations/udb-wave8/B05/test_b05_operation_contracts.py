"""Pytest suite for B05 Effective Operation Contracts schema, validator, AST checks, and artifacts."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest


def _get_validator_module() -> Any:
    import importlib.util

    mod_path = Path(__file__).resolve().parent / "b05_contracts_validator.py"
    spec = importlib.util.spec_from_file_location("b05_contracts_validator", mod_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


B05 = _get_validator_module()
B05_DIR = Path(__file__).resolve().parent
REPO_ROOT = B05_DIR.parents[3]


def _make_innocent_complete_contract() -> dict[str, Any]:
    """Construct a synthetic 19-key fully EVIDENCED contract instance."""
    record: dict[str, Any] = {
        "consumer_id": "src_6ad3cb3fa4349521",
        "operation_id": "op:crm-conversations:write:conversation-messages",
        "store_id": "pg:fly:nuzantara-postgres/public",
        "source_version": "8061c88e0c43dd42e735fd012f9ed072df3ef3d6",
        "evidence_timestamp": "2026-10-15T09:00:00Z",
        "evidence_sha256": "c3a9c44b8f97b4ef2155194d440feb2f1a23216057eba94eb91d51e988dd15fe",
        "status": "EVIDENCED",
        "unknowns": [],
    }
    for field_name in B05.INSTANCE_FIELDS:
        record[field_name] = {
            "value": f"evidenced-{field_name}-specification",
            "status": "EVIDENCED",
            "evidence_ref": "apps/backend-rag/backend/db/repositories/conversation_repository.py:L72-L146",
        }
    return record


def test_innocence_fully_evidenced_19_key_contract_passes_and_is_complete() -> None:
    """Innocence test: a fully evidenced 19-key contract passes validation and counts as complete."""
    record = _make_innocent_complete_contract()
    assert len(record) == 19
    errors = B05.validate_operation_instance(record)
    assert errors == []
    assert B05.is_complete_contract(record) is True


def test_b06_25_key_record_with_x_prefixed_extensions_passes_and_unprefixed_fails() -> None:
    """B06-shaped 25-key record test: 6 x_-prefixed keys pass; unprefixed extra keys fail."""
    valid_25 = _make_innocent_complete_contract()
    b06_extensions = {
        "x_execution_plane": "cron_pro",
        "x_trigger_surface": "crontab",
        "x_schedule_spec": "15 3 * * *",
        "x_target_host": "pro",
        "x_wrapper_script": "scripts/automation/run_with_lock.sh",
        "x_log_sink": "logs/cron/job.log",
    }
    valid_25.update(b06_extensions)
    assert len(valid_25) == 25
    assert B05.validate_operation_instance(valid_25) == []
    assert B05.is_complete_contract(valid_25) is True

    invalid_25 = _make_innocent_complete_contract()
    invalid_25.update(
        {
            "execution_plane": "cron_pro",
            "trigger_surface": "crontab",
            "schedule_spec": "15 3 * * *",
            "target_host": "pro",
            "wrapper_script": "scripts/automation/run_with_lock.sh",
            "log_sink": "logs/cron/job.log",
        }
    )
    assert len(invalid_25) == 25
    errors = B05.validate_operation_instance(invalid_25)
    assert len(errors) == 6
    assert all("Illegal unprefixed extra key" in err for err in errors)


def test_grammar_and_value_domain_rejections() -> None:
    """Verify strict grammar and value-domain enforcement across all frozen and instance fields."""
    # 1. Human alias in consumer_id rejected
    bad_consumer = _make_innocent_complete_contract()
    bad_consumer["consumer_id"] = "mini.restore_drill"
    errs = B05.validate_operation_instance(bad_consumer)
    assert any("human alias forbidden" in e for e in errs)

    # 2. Invalid operation_id grammar rejected
    for bad_op in ["op:Backup:verify:drill", "op:garuda:read", "op:garuda_orders:read:row"]:
        rec = _make_innocent_complete_contract()
        rec["operation_id"] = bad_op
        errs = B05.validate_operation_instance(rec)
        assert any("operation_id" in e for e in errs), f"Expected failure for {bad_op}"

    # 3. UNASSIGNED_B05 requires OPERATION_ID_PENDING_B05 in unknowns
    unassigned_bad = _make_innocent_complete_contract()
    unassigned_bad["operation_id"] = "UNASSIGNED_B05"
    unassigned_bad["status"] = "PARTIAL"
    unassigned_bad["unknowns"] = ["STATIC_SOURCE_ONLY"]
    unassigned_bad["role"]["status"] = "PARTIAL"
    errs = B05.validate_operation_instance(unassigned_bad)
    assert any("OPERATION_ID_PENDING_B05" in e for e in errs)

    unassigned_ok = copy.deepcopy(unassigned_bad)
    unassigned_ok["unknowns"].append("OPERATION_ID_PENDING_B05")
    assert B05.validate_operation_instance(unassigned_ok) == []

    # 4. Invalid store_id grammar rejected (including uppercase instance); platform unknown allowed;
    #    unknown:unknown:unknown requires STORE_ID_PROPOSED:<val> (STORE_ID_UNRESOLVED dropped)
    for bad_store_val in [
        "postgres:fly:nuzantara-postgres/public",
        "pg:fly:Nuzantara-Postgres/public",
    ]:
        bad_store = _make_innocent_complete_contract()
        bad_store["store_id"] = bad_store_val
        errs = B05.validate_operation_instance(bad_store)
        assert any("store_id" in e for e in errs), f"Expected failure for {bad_store_val}"

    platform_unknown_ok = _make_innocent_complete_contract()
    platform_unknown_ok["store_id"] = "pg:unknown:restore-target/public"
    assert B05.validate_operation_instance(platform_unknown_ok) == []

    unknown_store_bad = copy.deepcopy(unassigned_ok)
    unknown_store_bad["store_id"] = "unknown:unknown:unknown"
    unknown_store_bad["unknowns"].append("STORE_ID_UNRESOLVED")
    errs = B05.validate_operation_instance(unknown_store_bad)
    assert any("STORE_ID_PROPOSED" in e for e in errs)

    unknown_store_ok = copy.deepcopy(unassigned_ok)
    unknown_store_ok["store_id"] = "unknown:unknown:unknown"
    unknown_store_ok["unknowns"].append("STORE_ID_PROPOSED:crm:pro:hubspot")
    assert B05.validate_operation_instance(unknown_store_ok) == []

    # 5. Non-canonical status vocabulary rejected
    bad_status = _make_innocent_complete_contract()
    bad_status["status"] = "VERIFIED_STATIC"
    errs = B05.validate_operation_instance(bad_status)
    assert any("Top-level status" in e for e in errs)

    # 6. EVIDENCED top-level status with non-EVIDENCED field or non-empty unknowns rejected
    inconsistent = _make_innocent_complete_contract()
    inconsistent["recovery"]["status"] = "BLOCKED"
    errs = B05.validate_operation_instance(inconsistent)
    assert any("not all 11 instance fields" in e for e in errs)
    assert B05.is_complete_contract(inconsistent) is False


def test_ast_counterexample_conversation_repository() -> None:
    """AST-verify that save_messages lacks advisory/row locks and anonymize_user_data lacks conn.transaction()."""
    res = B05.verify_conversation_repo_ast(REPO_ROOT)
    assert res["sha256"] == B05.PINNED_SHA256["conversation_repository.py"]
    assert res["counterexample_proven"] is True
    assert res["methods"]["save_messages"]["has_conn_transaction"] is True
    assert res["methods"]["save_messages"]["has_advisory_lock"] is False
    assert res["methods"]["save_messages"]["has_for_update_row_lock"] is False
    assert res["methods"]["anonymize_user_data"]["has_conn_transaction"] is False


def test_ast_counterexample_migration_lock_busy() -> None:
    """AST-verify that advisory-lock refusal in migration_manager.py + migrate.py exits 0, not nonzero."""
    res = B05.verify_migration_lock_busy_ast(REPO_ROOT)
    assert res["counterexample_proven"] is True
    assert res["apply_all_pending_lineno"] == 501
    assert res["not_locked_return"] is not None
    assert res["not_locked_return"]["if_not_locked_lineno"] == 539
    assert res["not_locked_return"]["lineno"] == 541
    assert res["not_locked_return"]["all_lists_empty"] is True
    assert res["cmd_apply_lineno"] == 77
    assert res["cmd_apply_exit_zero_when_failed_empty"] is True
    assert res["main_sys_exit_lineno"] == 170
    assert res["main_sys_exit_zero_when_not_false"] is True


def test_live_db_metadata_md5_join_and_unobserved_pool_role() -> None:
    """Verify producer MD5 joins against LIVE-DB-METADATA.json and POOL-FACTORY-SOURCE.json."""
    res = B05.join_live_db_metadata_md5(REPO_ROOT)
    assert res["live_db_metadata_sha256"] == B05.PINNED_SHA256["LIVE-DB-METADATA.json"]
    assert res["pool_factory_source_sha256"] == B05.PINNED_SHA256["POOL-FACTORY-SOURCE.json"]
    assert res["pool_factory_target_role"] == "UNOBSERVED"
    assert res["principal_role_binding_closed"] is False
    assert res["public_schema_md5"] == "4c9184f37cff01bcdc32dc486ec36961"
    assert (
        res["relation_id_derivation"]
        == "md5(database||chr(31)||schema||chr(31)||relation)"
    )

    expected_8_defaults = [
        "conversations",
        "clients",
        "visa_decisions",
        "events_outbox",
        "visa_decision_retention_policies",
        "garuda_orders",
        "research_os_objects",
        "schema_migrations",
    ]
    assert res["unmatched_relations"] == []
    assert set(res["matched_relations"].keys()) == set(expected_8_defaults)
    for rel in expected_8_defaults:
        expected_rel_id = hashlib.md5(
            chr(31).join(["nuzantara_rag", "public", rel]).encode("utf-8")
        ).hexdigest()
        rel_info = res["matched_relations"][rel]
        assert rel_info["relation_id"] == expected_rel_id
        assert rel_info["row_security"] is False
        assert rel_info["force_row_security"] is False
        assert isinstance(rel_info["grants"], list) and len(rel_info["grants"]) > 0

    # Guilt case: name-only md5(rel) lookup matches 0 of the 8 default relations in LIVE-DB-METADATA.json
    meta_path = (
        REPO_ROOT
        / ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json"
    )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    live_rel_ids = {
        r["relation_id"]
        for r in meta.get("native_metadata", {}).get("relations", [])
        if "relation_id" in r
    }
    name_only_matches = [
        rel
        for rel in expected_8_defaults
        if hashlib.md5(rel.encode("utf-8")).hexdigest() in live_rel_ids
    ]
    assert name_only_matches == []

    # Roles postgres and backend_rag_v2 match MD5 catalog entries
    assert "postgres" in res["matched_roles"]
    assert (
        res["matched_roles"]["postgres"]["role_id"]
        == "e8a48653851e28c69d0506508fb27fc5"
    )
    assert "backend_rag_v2" in res["matched_roles"]
    assert (
        res["matched_roles"]["backend_rag_v2"]["role_id"]
        == "7457cee812eeb67564c33b7acf10e393"
    )
    for rel in expected_8_defaults:
        assert rel in res["role_grants_for_matched"]["backend_rag_v2"]


def test_committed_json_and_csv_artifacts_roundtrip_and_denominator(tmp_path: Path) -> None:
    """Validate committed operation-contracts.json and operation-contracts.csv against computed census and conventions."""
    json_path = B05_DIR / "operation-contracts.json"
    csv_path = B05_DIR / "operation-contracts.csv"
    assert json_path.is_file()
    assert csv_path.is_file()

    # Compute every expectation from the pinned inputs
    matrix_path = REPO_ROOT / ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    lead_delta_path = (
        REPO_ROOT
        / ".agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json"
    )
    with matrix_path.open("r", encoding="utf-8", newline="") as f:
        csv_rows = list(csv.DictReader(f))
    expected_csv_rows = len(csv_rows)
    expected_retained_test = sum(
        1 for r in csv_rows if (r.get("disposition") or "").strip() == "RETAINED_TEST_SOURCE"
    )
    valid_ids = {r["consumer_id"] for r in csv_rows}

    lead_delta = json.loads(lead_delta_path.read_text(encoding="utf-8"))
    additions = lead_delta.get("additions", [])
    expected_delta_rows = len(additions)
    expected_union_rows = lead_delta["union_lead_rows"]
    for item in additions:
        valid_ids.add(item["consumer_id"])

    expected_census = B05.compute_census(matrix_path)
    expected_non_retained_plus_delta = (
        expected_csv_rows - expected_retained_test
    ) + expected_delta_rows

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    denom = payload["denominator_accounting"]
    assert denom["consumer_matrix_csv_rows"] == expected_csv_rows
    assert denom["lead_delta_rows"] == expected_delta_rows
    assert denom["total_leads"] == expected_union_rows
    assert denom["retained_test_source_rows"] == expected_retained_test
    assert denom["non_retained_test_plus_delta"] == expected_non_retained_plus_delta
    assert denom["active_consumer_denominator"] == lead_delta["active_consumer_denominator"]
    assert denom["instantiated_operation_contracts"] == len(payload["operation_contracts"])
    assert denom["complete_operation_contracts"] == 0
    assert denom["census_bucket_count"] == len(expected_census)
    assert denom["census_buckets"] == expected_census
    assert sum(b["count"] for b in denom["census_buckets"]) == expected_csv_rows

    instances = payload["operation_contracts"]
    assert len(instances) == 23
    for inst in instances:
        assert "x_evidence_ref" in inst and isinstance(inst["x_evidence_ref"], str)
        assert B05.validate_operation_instance(inst, valid_consumer_ids=valid_ids) == []
        assert B05.is_complete_contract(inst, valid_consumer_ids=valid_ids) is False

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        c_reader = csv.DictReader(f)
        assert tuple(c_reader.fieldnames or ()) == B05.REQUIRED_19_KEYS + ("x_evidence_ref",)
        csv_instances = [B05.csv_row_to_instance(row) for row in c_reader]

    assert csv_instances == instances
    assert B05.main(["--validate"]) == 0

    # Negative test: mutating one denominator in a copy written to tmp_path makes --validate return nonzero
    mutated_payload = copy.deepcopy(payload)
    mutated_payload["denominator_accounting"]["consumer_matrix_csv_rows"] = expected_csv_rows - 1
    (tmp_path / "operation-contracts.json").write_text(
        json.dumps(mutated_payload, indent=2) + "\n", encoding="utf-8"
    )
    (tmp_path / "operation-contracts.csv").write_text(
        csv_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert B05.main(["--validate", "--out-dir", str(tmp_path)]) != 0
