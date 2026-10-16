"""Pytest suite for B08 Cross-Store Operational Guarantees Adapter & Verifier.

Tests positive contract generation from pinned Wave 8 inputs, synthetic census
and nested restore-receipt fixtures, and negative (guilt) cases across all 8
cross-store dimensions and CONTRACT-CONVENTIONS.md rules.
Uses Python standard library + pytest only; zero network or live DB calls.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any
import pytest

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[3]

_SPEC = importlib.util.spec_from_file_location(
    "b08_crossstore_adapter", THIS_DIR / "b08_crossstore_adapter.py"
)
assert _SPEC is not None and _SPEC.loader is not None
adapter = importlib.util.module_from_spec(_SPEC)
sys.modules["b08_crossstore_adapter"] = adapter
_SPEC.loader.exec_module(adapter)

REAL_CSV_COLUMNS: list[str] = [
    "consumer_id",
    "domain",
    "entry_point",
    "evidence",
    "runtime_registration",
    "operations",
    "store",
    "schemas_tables_keys",
    "owner",
    "authority",
    "identity_relationships",
    "transaction_boundary",
    "authorization",
    "locality_sensitivity",
    "retention",
    "concurrency_idempotency",
    "latency_availability",
    "test_coverage",
    "disposition",
    "blocker",
    "domain_hint",
    "domain_classification",
    "store_signal_hint",
    "persistence_client_hints",
    "activation_status",
    "production_execution_evidence",
    "contract_coverage_status",
    "phase_source_path_evidence",
    "phase_factory_candidate_count",
    "phase_source_scope_status",
    "phase_registered_ingress_evidence",
    "phase_registered_source_route_candidates",
    "phase_registered_source_scope",
    "phase_ci_registration_evidence",
    "phase_ci_reported_states",
    "phase_ci_actor_identity",
]


def _make_realistic_nested_receipt() -> dict[str, Any]:
    """Build a realistic nested restore receipt matching REAL-RUN-RECEIPT.json shape."""
    return {
        "exit": 0,
        "elapsed_seconds": 87.658,
        "events": [
            {
                "event": "REQUEST_ACCEPTED",
                "job_trigger_requested": True,
                "started_at": "2026-10-15T03:00:43.925327+00:00",
                "source_pin_matches": 6,
            },
            {
                "event": "OBSERVING",
                "elapsed_seconds": 0.0,
                "private_report_fd_observed": False,
            },
            {
                "event": "TERMINAL",
                "job_trigger_requested": True,
                "elapsed_seconds": 87.337,
                "sidecar": {
                    "status": "error",
                    "timestamp": "2026-10-15T03:02:11+00:00",
                    "age_hours": 0.0,
                    "known_success_note": False,
                    "raw_note_exported": False,
                },
                "verifier_summary": {
                    "aggregate": "CANNOT-VERIFY",
                    "invariants": [
                        {
                            "relation": "conversations",
                            "status": "CANNOT-VERIFY",
                            "reason_classes": {"UNMEASURED_CHECK": 1},
                        },
                        {
                            "relation": "clients",
                            "status": "FAIL",
                            "reason_classes": {"VIOLATION": 1},
                        },
                        {
                            "relation": "visa_decisions",
                            "status": "PASS",
                            "reason_classes": {},
                        },
                        {
                            "relation": "events_outbox",
                            "status": "PASS",
                            "reason_classes": {},
                        },
                        {
                            "relation": "visa_decision_retention_policies",
                            "status": "PASS",
                            "reason_classes": {},
                        },
                    ],
                    "top_level_error_present": False,
                    "raw_report_sha256": "1d368c2d16d32a0834bb7d120d75005423227b77239107b1dc1873f8140b5744",
                    "rows_counts_and_raw_errors_exported": False,
                },
                "status": "FAILED_OR_CANNOT_VERIFY",
                "raw_logs_or_records_exported": False,
            },
        ],
        "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "raw_stderr_saved": False,
        "operator_sha256": "caa4e67070eb74c1a2e41f9f48c436b9246eb82f67d88eaf98c4d33aabb1aa08",
        "metadata_dependency_sha256": "d11ad9c5315600bb868f18378e3596e99413cd7550becff8596075584bea06f2",
        "bundle_sha256": "6ed38f416ca7e9a76c7b6a7762d3486d6eeb27ef4e5e8e24a99bf8a3355c9566",
    }


@pytest.fixture(scope="module")
def base_instances() -> list[dict[str, Any]]:
    """Build B08 operation instances from tracked repository files."""
    return adapter.build_b08_operation_instances(REPO_ROOT)


def test_census_matches_dux_req_b08_01_and_state_json() -> None:
    """Pinned parity test: compare scanned census against DUX-REQ-B08-01.out and STATE.json."""
    # Live .agent-receipts / dux-requests inputs when present, else the committed fixtures.
    inputs = adapter.resolve_wave8_inputs(REPO_ROOT)
    pinned_receipt = adapter.load_pinned_census_receipt(
        inputs.census_path,
        expected_sha256=adapter.PINNED_DUX_REQ_B08_01_OUT_SHA256,
    )
    scanned = adapter.scan_wave8_consumer_matrix(inputs)
    adapter.compare_census_to_receipt(scanned, pinned_receipt)

    report = adapter.generate_b08_report(REPO_ROOT)
    summary = report["census_summary"]
    assert summary["baseline_leads_preserved"] == 6029
    assert summary["additional_runtime_observations"] == 1
    assert summary["union_lead_rows"] == 6030
    assert summary["active_consumer_denominator"] == "UNKNOWN"
    assert summary["csv_total_rows"] == 6029
    assert summary["csv_column_count"] == 36
    assert summary["multi_store_or_boundary_rows"] == 1803
    assert summary["by_family"] == {
        "src": 1572,
        "runtime": 158,
        "NOTEBOOK-CONTAINER-REFERENCE-NLM": 67,
        "engine_pro": 2,
        "engine_mini": 2,
        "runtime-pro-plist": 1,
        "engine_M5": 1,
    }
    assert summary["by_store"] == pinned_receipt["by_store"]


def test_synthetic_census_fixture_and_tampered_receipt(tmp_path: Path) -> None:
    """Synthetic fixture test: verify producer predicate, family regex, and tampered receipt failure."""
    csv_file = tmp_path / "synthetic_consumer_matrix.csv"
    rows = [
        {
            "consumer_id": "src_0123456789abcdef",
            "store": "external",
        },
        {
            "consumer_id": "runtime_abcdef0123456789",
            "store": "object_storage",
        },
        {
            "consumer_id": "engine_pro",
            "store": "POSTGRES_LOCAL_CLUSTER_CANDIDATE_ON_pro; logical database set UNKNOWN",
        },
        {
            "consumer_id": "engine_mini",
            "store": "REDIS_LOCAL_ENGINE_CANDIDATE_ON_mini; keys/DB set UNKNOWN",
        },
        {
            "consumer_id": "runtime-pro-plist-1122334455667788",
            "store": "event_delivery",
        },
        {
            "consumer_id": "engine_M5",
            "store": "POSTGRES_LOCAL_CLUSTER_CANDIDATE_ON_M5; logical database set UNKNOWN",
        },
        {
            "consumer_id": "NOTEBOOK-CONTAINER-REFERENCE-NLM-aabbccddeeff0011",
            "store": "NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY",
        },
        # Single-store redis, qdrant, and file_state rows MUST NOT be selected
        {
            "consumer_id": "src_feedfacecafebeef",
            "store": "redis",
        },
        {
            "consumer_id": "src_deadbeef00112233",
            "store": "qdrant",
        },
        {
            "consumer_id": "src_1122334455667788",
            "store": "file_state",
        },
    ]

    with csv_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REAL_CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            full_row = {col: "" for col in REAL_CSV_COLUMNS}
            full_row.update(r)
            writer.writerow(full_row)

    scanned = adapter.scan_consumer_matrix(csv_file)
    assert scanned["total_rows"] == 10
    assert scanned["column_count"] == 36
    assert scanned["multi_store_or_boundary_rows"] == 7
    assert scanned["by_family"] == {
        "NOTEBOOK-CONTAINER-REFERENCE-NLM": 1,
        "engine_M5": 1,
        "engine_mini": 1,
        "engine_pro": 1,
        "runtime": 1,
        "runtime-pro-plist": 1,
        "src": 1,
    }
    assert "redis" not in scanned["by_store"]
    assert "qdrant" not in scanned["by_store"]
    assert "file_state" not in scanned["by_store"]
    assert scanned["by_store"]["external"] == 1
    assert scanned["by_store"]["object_storage"] == 1
    assert scanned["by_store"]["event_delivery"] == 1

    matching_receipt = {
        "total_rows": scanned["total_rows"],
        "multi_store_or_boundary_rows": scanned["multi_store_or_boundary_rows"],
        "by_store": copy.deepcopy(scanned["by_store"]),
        "by_family": copy.deepcopy(scanned["by_family"]),
    }
    adapter.compare_census_to_receipt(scanned, matching_receipt)

    tampered_receipt = copy.deepcopy(matching_receipt)
    tampered_receipt["multi_store_or_boundary_rows"] = 8
    with pytest.raises(adapter.ContractViolationError, match="Census mismatch"):
        adapter.compare_census_to_receipt(scanned, tampered_receipt)

    tampered_family = copy.deepcopy(matching_receipt)
    tampered_family["by_family"]["src"] = 999
    with pytest.raises(adapter.ContractViolationError, match="Census mismatch"):
        adapter.compare_census_to_receipt(scanned, tampered_family)

    tampered_out_file = tmp_path / "tampered.out"
    tampered_out_file.write_text(json.dumps(tampered_receipt), encoding="utf-8")
    with pytest.raises(adapter.ContractViolationError, match="SHA256 mismatch"):
        adapter.load_pinned_census_receipt(
            tampered_out_file,
            expected_sha256=adapter.PINNED_DUX_REQ_B08_01_OUT_SHA256,
        )


def test_eight_dimensions_separate_current_facts_and_desired_guarantees(
    base_instances: list[dict[str, Any]],
) -> None:
    """Verify all 8 dimensions exist and keep current facts separate from desired guarantees."""
    dims = adapter.build_dimensions_ledger(base_instances)
    assert set(dims.keys()) == set(adapter.EIGHT_DIMENSIONS)
    for dim_name, dim_payload in dims.items():
        assert "current_facts" in dim_payload
        assert "desired_guarantees" in dim_payload
        assert (
            len(dim_payload["current_facts"]) >= 1
        ), f"Missing current_facts for {dim_name}"
        assert (
            len(dim_payload["desired_guarantees"]) >= 1
        ), f"Missing desired_guarantees for {dim_name}"
        for fact in dim_payload["current_facts"]:
            assert fact["x_record_kind"] == "CURRENT_FACT"
            assert fact["x_guarantee_dimension"] == dim_name
        for desired in dim_payload["desired_guarantees"]:
            assert desired["x_record_kind"] == "DESIRED_GUARANTEE"
            assert desired.get("status") != "EVIDENCED"


def test_all_emitted_operation_instances_satisfy_19_key_contract(
    base_instances: list[dict[str, Any]],
) -> None:
    """Verify every operation instance obeys CONTRACT-CONVENTIONS.md (Findings X1-X5)."""
    assert len(base_instances) >= 9
    known_ids = {inst["consumer_id"] for inst in base_instances} | {
        "mini.restore_drill"
    }
    for inst in base_instances:
        adapter.validate_operation_instance(inst, known_consumer_ids=known_ids)
        assert adapter.REQUIRED_19_KEYS.issubset(inst.keys())
        extra = set(inst.keys()) - adapter.REQUIRED_19_KEYS
        assert all(k.startswith("x_") for k in extra)
        assert inst["operation_id"] == "UNASSIGNED_B05"
        assert "OPERATION_ID_PENDING_B05" in inst["unknowns"]
        assert inst["status"] in adapter.VALID_STATUSES


def test_rejects_unknown_consumer_id(
    base_instances: list[dict[str, Any]],
) -> None:
    """Negative test (Finding X10): reject a consumer_id not in consumer-matrix.csv + LEAD-DELTA."""
    bad = copy.deepcopy(base_instances[0])
    bad["consumer_id"] = "src_nonexistent_fake_0000"
    with pytest.raises(adapter.ContractViolationError, match="consumer_id"):
        adapter.validate_operation_instance(
            bad, known_consumer_ids={"src_e23395130cffca55"}
        )


def test_rejects_invalid_store_id_grammar(
    base_instances: list[dict[str, Any]],
) -> None:
    """Negative test (Finding X1): reject store_id outside <engine>:<platform>:<instance>."""
    bad = copy.deepcopy(base_instances[0])
    bad["store_id"] = "postgresql;redis"
    with pytest.raises(adapter.ContractViolationError, match="store_id"):
        adapter.validate_operation_instance(
            bad, known_consumer_ids={bad["consumer_id"]}
        )

    bad_unknown = copy.deepcopy(base_instances[0])
    bad_unknown["store_id"] = "unknown:unknown:unknown"
    with pytest.raises(
        adapter.ContractViolationError, match="STORE_ID_PROPOSED"
    ):
        adapter.validate_operation_instance(
            bad_unknown, known_consumer_ids={bad_unknown["consumer_id"]}
        )


def test_rejects_minted_operation_id_from_b08(
    base_instances: list[dict[str, Any]],
) -> None:
    """Negative test (Finding X2): reject B08 minting its own op:<domain>:<verb>:<object>."""
    bad = copy.deepcopy(base_instances[0])
    bad["operation_id"] = "op:cross_store:relay:events_outbox"
    with pytest.raises(adapter.ContractViolationError, match="UNASSIGNED_B05"):
        adapter.validate_operation_instance(
            bad, known_consumer_ids={bad["consumer_id"]}
        )


def test_rejects_custom_status_outside_enum(
    base_instances: list[dict[str, Any]],
) -> None:
    """Negative test (Finding X3): reject custom statuses like DEGRADED_LOSSY or BROKEN."""
    bad = copy.deepcopy(base_instances[0])
    bad["status"] = "DEGRADED_LOSSY"
    with pytest.raises(
        adapter.ContractViolationError, match="Invalid top-level status"
    ):
        adapter.validate_operation_instance(
            bad, known_consumer_ids={bad["consumer_id"]}
        )


def test_rejects_unprefixed_extra_keys_and_flat_instance_fields(
    base_instances: list[dict[str, Any]],
) -> None:
    """Negative test (Finding X4): reject non-x_ extra keys and non-object instance fields."""
    bad_extra = copy.deepcopy(base_instances[0])
    bad_extra["guarantee_dimension"] = "dependencies"
    with pytest.raises(
        adapter.ContractViolationError, match="without 'x_' prefix"
    ):
        adapter.validate_operation_instance(
            bad_extra, known_consumer_ids={bad_extra["consumer_id"]}
        )

    bad_field = copy.deepcopy(base_instances[0])
    bad_field["retries"] = "max_attempts=5"
    with pytest.raises(
        adapter.ContractViolationError, match="must be a dict object"
    ):
        adapter.validate_operation_instance(
            bad_field, known_consumer_ids={bad_field["consumer_id"]}
        )


def test_rejects_static_source_without_unknown_marker(
    base_instances: list[dict[str, Any]],
) -> None:
    """Negative test (Finding X5): static base-commit evidence requires STATIC_SOURCE_ONLY."""
    bad = copy.deepcopy(base_instances[0])
    bad["unknowns"] = ["OPERATION_ID_PENDING_B05"]
    with pytest.raises(
        adapter.ContractViolationError, match="STATIC_SOURCE_ONLY"
    ):
        adapter.validate_operation_instance(
            bad, known_consumer_ids={bad["consumer_id"]}
        )


def test_rejects_desired_guarantee_masquerading_as_evidenced(
    base_instances: list[dict[str, Any]],
) -> None:
    """Negative test: DESIRED_GUARANTEE cannot claim status='EVIDENCED'."""
    bad = copy.deepcopy(base_instances[-1])
    assert bad["x_record_kind"] == "DESIRED_GUARANTEE"
    bad["status"] = "EVIDENCED"
    with pytest.raises(
        adapter.ContractViolationError, match="DESIRED_GUARANTEE"
    ):
        adapter.validate_operation_instance(
            bad, known_consumer_ids={bad["consumer_id"]}
        )


def test_rejects_premature_closure_while_b01_b02_b04_missing(
    base_instances: list[dict[str, Any]],
) -> None:
    """Negative test (Findings X8, B08-F3): reject block_closed=True or EVIDENCED on blocked stores."""
    state_json = {
        "active_consumer_denominator": "UNKNOWN",
        "real_backup_restore_success_proved": False,
        "qdrant_model_binding_proved": False,
        "redis": {
            "pro": "AUTHORIZATION_REQUIRED",
            "mini": "AUTHORIZATION_REQUIRED",
        },
    }
    instances = copy.deepcopy(base_instances)

    with pytest.raises(
        adapter.ContractViolationError, match="block_closed cannot be True"
    ):
        adapter.validate_sibling_gate_constraints(
            records=instances, state_json=state_json, block_closed=True
        )

    bad_recovery = copy.deepcopy(instances[5])
    bad_recovery["status"] = "EVIDENCED"
    with pytest.raises(
        adapter.ContractViolationError,
        match="recovery_order record cannot be EVIDENCED",
    ):
        adapter.validate_sibling_gate_constraints(
            records=[bad_recovery], state_json=state_json, block_closed=False
        )


def test_ce01_pinned_real_run_receipt_parity() -> None:
    """Pinned parity test: evaluate CE-01 on .agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json."""
    # Live REAL-RUN-RECEIPT.json when present, else the byte-identical committed fixture.
    receipt_path = adapter.resolve_wave8_inputs(REPO_ROOT).receipt_path
    assert (
        adapter.sha256_file(receipt_path)
        == adapter.PINNED_REAL_RUN_RECEIPT_SHA256
    )
    receipt_json = json.loads(receipt_path.read_text(encoding="utf-8"))
    ce01 = adapter.evaluate_ce01_restore_verdict_and_epistemology(receipt_json)
    assert ce01["overall_status"] == "CANNOT-VERIFY"
    assert ce01["producer_aggregate"] == "CANNOT-VERIFY"
    assert ce01["aggregate_matches_producer"] is True
    assert ce01["fail_masked_by_cannot_verify"] is True
    assert ce01["clients_status"] == "FAIL"
    assert ce01["clients_violation_count"] == 1
    assert ce01["clients_lead_metadata_column_existed_in_backup"] is True
    assert (
        ce01["clients_lead_metadata_evidence_ref"]
        == "scripts/ci/restore_drill_verify.py:221-227"
    )
    assert (
        ce01["clients_invariant_checks_ref"]
        == "scripts/ci/restore_drill_verify.py:122"
    )
    assert (
        ce01["clients_violations_dispatch_ref"]
        == "scripts/ci/restore_drill_verify.py:281-288,345"
    )
    assert ce01["exact_failing_clients_subcheck_known"] is False
    assert ce01["exact_conversations_sql_error_known"] is False
    assert ce01["conversations_unmeasured_check_count"] == 1
    assert ce01["unmeasured_check_count"] == 1
    assert ce01["relations"]["conversations"] == {
        "status": "CANNOT-VERIFY",
        "reason_classes": {"UNMEASURED_CHECK": 1},
    }
    assert ce01["relations"]["clients"] == {
        "status": "FAIL",
        "reason_classes": {"VIOLATION": 1},
    }
    assert ce01["relations"]["visa_decisions"] == {
        "status": "PASS",
        "reason_classes": {},
    }
    assert ce01["relations"]["events_outbox"] == {
        "status": "PASS",
        "reason_classes": {},
    }
    assert ce01["relations"]["visa_decision_retention_policies"] == {
        "status": "PASS",
        "reason_classes": {},
    }


def test_ce01_nested_restore_receipt_counterexamples_and_attribution() -> None:
    """Test realistic nested restore receipts, malformed/duplicate/contradictory cases, and per-relation attribution."""
    # 1. Realistic valid nested receipt
    valid_receipt = _make_realistic_nested_receipt()
    ce01 = adapter.evaluate_ce01_restore_verdict_and_epistemology(valid_receipt)
    assert ce01["overall_status"] == "CANNOT-VERIFY"
    assert ce01["fail_masked_by_cannot_verify"] is True
    assert ce01["clients_lead_metadata_column_existed_in_backup"] is True
    assert (
        ce01["clients_lead_metadata_evidence_ref"]
        == "scripts/ci/restore_drill_verify.py:221-227"
    )
    assert ce01["exact_failing_clients_subcheck_known"] is False
    assert ce01["exact_conversations_sql_error_known"] is False

    # 2. Absent events list (or legacy flat dict) -> must raise ContractViolationError, never PASS
    with pytest.raises(adapter.ContractViolationError, match="events"):
        adapter.evaluate_ce01_restore_verdict_and_epistemology({})
    with pytest.raises(adapter.ContractViolationError, match="events"):
        adapter.evaluate_ce01_restore_verdict_and_epistemology(
            {"table_statuses": {}, "reason_counts": {}}
        )

    # 3. Zero TERMINAL events -> must raise ContractViolationError
    no_terminal = copy.deepcopy(valid_receipt)
    no_terminal["events"] = [
        ev for ev in no_terminal["events"] if ev.get("event") != "TERMINAL"
    ]
    with pytest.raises(
        adapter.ContractViolationError, match="exactly 1 TERMINAL"
    ):
        adapter.evaluate_ce01_restore_verdict_and_epistemology(no_terminal)

    # 4. Two TERMINAL events -> must raise ContractViolationError
    two_terminal = copy.deepcopy(valid_receipt)
    two_terminal["events"].append(copy.deepcopy(two_terminal["events"][-1]))
    with pytest.raises(
        adapter.ContractViolationError, match="exactly 1 TERMINAL"
    ):
        adapter.evaluate_ce01_restore_verdict_and_epistemology(two_terminal)

    # 5. Malformed or empty invariants -> must raise ContractViolationError
    empty_invariants = copy.deepcopy(valid_receipt)
    empty_invariants["events"][-1]["verifier_summary"]["invariants"] = []
    with pytest.raises(adapter.ContractViolationError, match="non-empty list"):
        adapter.evaluate_ce01_restore_verdict_and_epistemology(empty_invariants)

    bad_status_inv = copy.deepcopy(valid_receipt)
    bad_status_inv["events"][-1]["verifier_summary"]["invariants"][0][
        "status"
    ] = "UNKNOWN_BOGUS"
    with pytest.raises(adapter.ContractViolationError, match="invalid status"):
        adapter.evaluate_ce01_restore_verdict_and_epistemology(bad_status_inv)

    # 6. Duplicate relation -> must raise ContractViolationError
    dup_rel = copy.deepcopy(valid_receipt)
    dup_rel["events"][-1]["verifier_summary"]["invariants"].append(
        {
            "relation": "clients",
            "status": "FAIL",
            "reason_classes": {"VIOLATION": 1},
        }
    )
    with pytest.raises(
        adapter.ContractViolationError, match="Duplicate relation"
    ):
        adapter.evaluate_ce01_restore_verdict_and_epistemology(dup_rel)

    # 7. Aggregate contradiction (producer summary says PASS while a relation is FAIL) -> must raise
    contradictory = copy.deepcopy(valid_receipt)
    contradictory["events"][-1]["verifier_summary"]["aggregate"] = "PASS"
    with pytest.raises(
        adapter.ContractViolationError, match="Aggregate contradiction"
    ):
        adapter.evaluate_ce01_restore_verdict_and_epistemology(contradictory)

    # 8. VIOLATION on visa_decisions with clients PASS -> clients lead_metadata inference must be False
    other_rel_violation = copy.deepcopy(valid_receipt)
    other_rel_summary = other_rel_violation["events"][-1]["verifier_summary"]
    other_rel_summary["aggregate"] = "FAIL"
    other_rel_summary["invariants"] = [
        {
            "relation": "conversations",
            "status": "PASS",
            "reason_classes": {},
        },
        {
            "relation": "clients",
            "status": "PASS",
            "reason_classes": {},
        },
        {
            "relation": "visa_decisions",
            "status": "FAIL",
            "reason_classes": {"VIOLATION": 1},
        },
        {
            "relation": "events_outbox",
            "status": "PASS",
            "reason_classes": {},
        },
        {
            "relation": "visa_decision_retention_policies",
            "status": "PASS",
            "reason_classes": {},
        },
    ]
    res_other = adapter.evaluate_ce01_restore_verdict_and_epistemology(
        other_rel_violation
    )
    assert res_other["overall_status"] == "FAIL"
    assert res_other["overall_status"] != "PASS"
    assert res_other["clients_status"] == "PASS"
    assert res_other["clients_violation_count"] == 0
    assert res_other["clients_lead_metadata_column_existed_in_backup"] is False
    assert res_other["clients_lead_metadata_evidence_ref"] is None


def test_ce02_through_ce06_counterexamples_detected() -> None:
    """Verify CE-02 through CE-06 counterexample evaluations on pinned repository files."""
    ce02 = adapter.evaluate_ce02_polymorphic_provenance(
        (
            REPO_ROOT
            / "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql"
        ).read_text(encoding="utf-8")
    )
    assert ce02["polymorphic_asset_types_present"] is True
    assert ce02["unconstrained_text_asset_id"] is True
    assert ce02["has_db_foreign_key"] is False
    assert ce02["cross_store_dangling_pointer_possible"] is True

    ce03 = adapter.evaluate_ce03_organism_bridge(
        (REPO_ROOT / "scripts/pg-to-organism-bridge.py").read_text(
            encoding="utf-8"
        )
    )
    assert ce03["payload_truncated_at_2000_bytes"] is True
    assert ce03["wallclock_correlation_fallback"] is True
    assert ce03["redis_xadd_non_atomic_best_effort"] is True
    assert ce03["lossy_fanout_detected"] is True

    ce04 = adapter.evaluate_ce04_qdrant_health_probe(
        (
            REPO_ROOT
            / "apps/backend-rag/backend/services/monitoring/unified_health_service.py"
        ).read_text(encoding="utf-8")
    )
    assert ce04["checks_only_url_attribute"] is True
    assert ce04["performs_live_io"] is False
    assert ce04["false_positive_ok_possible"] is True

    ce05 = adapter.evaluate_ce05_war_room_cost_masking(
        (
            REPO_ROOT
            / "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts"
        ).read_text(encoding="utf-8")
    )
    assert ce05["catches_undefined_table_42p01"] is True
    assert ce05["returns_zero_usd_on_missing_table"] is True
    assert ce05["false_zero_cost_telemetry"] is True

    ce06 = adapter.evaluate_ce06_outbox_and_cost_retention(
        outbox_py_source=(
            REPO_ROOT / "apps/backend-rag/backend/services/events/outbox.py"
        ).read_text(encoding="utf-8"),
        outbox_prune_sh_source=(REPO_ROOT / "scripts/outbox-prune.sh").read_text(
            encoding="utf-8"
        ),
        llm_cost_recorder_source=(
            REPO_ROOT
            / "apps/backend-rag/backend/services/observability/llm_cost_recorder.py"
        ).read_text(encoding="utf-8"),
    )
    assert ce06["outbox_claim_window_60m"] is True
    assert ce06["outbox_prune_requires_processed_at_not_null"] is True
    assert ce06["unconsumed_older_than_60m_orphaned_forever"] is True
    assert ce06["llm_cost_jsonl_claims_90d_retention"] is True
    assert ce06["llm_cost_jsonl_prune_implemented"] is False
    assert ce06["llm_cost_retention_unimplemented"] is True


def test_cli_refuses_output_outside_b08_directory(tmp_path: Path) -> None:
    """Negative test (Findings B08-F1, B08-F5): CLI refuses writing outside B08 dir."""
    illegal_out = tmp_path / "illegal_outside_b08.json"
    with pytest.raises(adapter.ContractViolationError, match="must stay inside"):
        adapter.main(["--repo-root", str(REPO_ROOT), "--out", str(illegal_out)])


# --- Clean-checkout reproducibility: committed frozen fixtures instead of ignored inputs ---

B08_REL = "research/operations/udb-wave8/B08"
REPO_SOURCE_RELS: tuple[str, ...] = (
    "scripts/pg-to-organism-bridge.py",
    "apps/backend-rag/backend/services/events/outbox.py",
    "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql",
    "apps/backend-rag/backend/db/migrations_v2/165_reconcile_schema_migrations_duplicates.sql",
    "scripts/outbox-prune.sh",
    "scripts/ci/restore_drill_verify.py",
    "apps/backend-rag/backend/services/observability/llm_cost_recorder.py",
    "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts",
    "apps/backend-rag/backend/services/monitoring/unified_health_service.py",
)
BYTE_IDENTICAL_FIXTURE_PINS: dict[str, str] = {
    "STATE.json": adapter.PINNED_STATE_JSON_SHA256,
    "REAL-RUN-RECEIPT.json": adapter.PINNED_REAL_RUN_RECEIPT_SHA256,
    "DUX-REQ-B08-01.out": adapter.PINNED_DUX_REQ_B08_01_OUT_SHA256,
}
PROJECTION_FIXTURE = "consumer-matrix.projection.csv"
DATA_FIXTURES: tuple[str, ...] = (*BYTE_IDENTICAL_FIXTURE_PINS, PROJECTION_FIXTURE)
ALL_FIXTURES: tuple[str, ...] = (*DATA_FIXTURES, adapter.FIXTURE_PROVENANCE_NAME)
# Ledger pinned by ISOLATED-REGENERATION-RECEIPT.json (regenerated from the live inputs).
ISOLATED_LEDGER_SHA256 = (
    "46021291588f409b301df5672ce1262929f6408912157750195f65be2217af13"
)
ISOLATED_LEDGER_BYTES = 77786
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _clean_checkout_root(tmp_path: Path) -> Path:
    """Stand-in for a clean checkout: committed fixtures + repo sources, no ignored inputs."""
    root = tmp_path / "clean-checkout"
    shutil.copytree(THIS_DIR / "fixtures", root / adapter.FIXTURES_REL)
    for rel in REPO_SOURCE_RELS:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dest)
    assert not (root / ".agent-receipts").exists()
    assert not (root / B08_REL / "dux-requests").exists()
    return root


def _rewrite_provenance(root: Path, mutate: Any) -> None:
    path = root / adapter.FIXTURES_REL / adapter.FIXTURE_PROVENANCE_NAME
    doc = json.loads(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _matrix_entry(doc: dict[str, Any]) -> dict[str, Any]:
    return next(e for e in doc["entries"] if e["fixture"] == PROJECTION_FIXTURE)


def test_clean_checkout_resolves_every_input_from_committed_fixtures(
    tmp_path: Path,
) -> None:
    """No .agent-receipts and no dux-requests: all four inputs come from fixtures/."""
    root = _clean_checkout_root(tmp_path)
    inputs = adapter.resolve_wave8_inputs(root)
    assert inputs.origins == {
        "state": "fixture",
        "receipt": "fixture",
        "census": "fixture",
        "matrix": "fixture",
    }
    fixtures = root / adapter.FIXTURES_REL
    assert inputs.state_path == fixtures / "STATE.json"
    assert inputs.receipt_path == fixtures / "REAL-RUN-RECEIPT.json"
    assert inputs.census_path == fixtures / "DUX-REQ-B08-01.out"
    assert inputs.matrix_path == fixtures / PROJECTION_FIXTURE
    assert adapter.sha256_file(inputs.state_path) == adapter.PINNED_STATE_JSON_SHA256
    assert (
        adapter.sha256_file(inputs.receipt_path)
        == adapter.PINNED_REAL_RUN_RECEIPT_SHA256
    )
    assert (
        adapter.sha256_file(inputs.census_path)
        == adapter.PINNED_DUX_REQ_B08_01_OUT_SHA256
    )
    assert (
        adapter.sha256_file(inputs.matrix_path)
        == adapter.PINNED_CONSUMER_MATRIX_PROJECTION_SHA256
    )

    scanned = adapter.scan_wave8_consumer_matrix(inputs)
    assert scanned["total_rows"] == 6029
    assert scanned["column_count"] == 36
    assert len(scanned["columns"]) == 36
    assert scanned["multi_store_or_boundary_rows"] == 1803
    adapter.compare_census_to_receipt(
        scanned, adapter.load_pinned_census_receipt(inputs.census_path)
    )


def test_fixture_only_regeneration_reproduces_the_pinned_isolated_ledger(
    tmp_path: Path,
) -> None:
    """The documented CLI command on a clean checkout reproduces the pinned ledger bytes."""
    root = _clean_checkout_root(tmp_path)
    out_path = root / B08_REL / "regenerated-ledger.json"
    assert adapter.main(["--repo-root", str(root), "--out", str(out_path)]) == 0
    produced = out_path.read_bytes()
    assert len(produced) == ISOLATED_LEDGER_BYTES
    assert hashlib.sha256(produced).hexdigest() == ISOLATED_LEDGER_SHA256


def test_live_inputs_and_fixtures_generate_the_same_report(tmp_path: Path) -> None:
    """REPO_ROOT uses live inputs when present, fixtures otherwise; both must agree."""
    root = _clean_checkout_root(tmp_path)
    assert adapter.generate_b08_report(REPO_ROOT) == adapter.generate_b08_report(root)


def test_live_inputs_win_over_fixtures_when_present(tmp_path: Path) -> None:
    """Present .agent-receipts/dux-requests inputs are used unchanged, per input."""
    root = _clean_checkout_root(tmp_path)
    live = root / adapter.LIVE_INPUTS_REL
    live.mkdir(parents=True)
    (live / "STATE.json").write_text("{}\n", encoding="utf-8")
    (live / "consumer-matrix.csv").write_text(
        "consumer_id,store\nsrc_x,qdrant\n", encoding="utf-8"
    )
    census = root / adapter.LIVE_CENSUS_REL
    census.parent.mkdir(parents=True)
    census.write_text("{}\n", encoding="utf-8")

    inputs = adapter.resolve_wave8_inputs(root)
    assert inputs.origins == {
        "state": "live",
        "receipt": "fixture",
        "census": "live",
        "matrix": "live",
    }
    assert inputs.state_path == live / "STATE.json"
    assert inputs.census_path == census
    assert inputs.matrix_path == live / "consumer-matrix.csv"
    assert inputs.matrix_source_columns is None
    scanned = adapter.scan_wave8_consumer_matrix(inputs)
    assert scanned["total_rows"] == 1
    assert scanned["column_count"] == 2


@pytest.mark.parametrize("fixture_name", DATA_FIXTURES)
def test_tampered_fixture_is_rejected(tmp_path: Path, fixture_name: str) -> None:
    """A byte-identical fixture or the projection with one extra byte fails its pin."""
    root = _clean_checkout_root(tmp_path)
    target = root / adapter.FIXTURES_REL / fixture_name
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(adapter.ContractViolationError, match="Fixture SHA256 mismatch"):
        adapter.resolve_wave8_inputs(root)


@pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
def test_missing_fixture_is_rejected(tmp_path: Path, fixture_name: str) -> None:
    """A clean checkout missing any committed fixture fails closed, never silently."""
    root = _clean_checkout_root(tmp_path)
    (root / adapter.FIXTURES_REL / fixture_name).unlink()
    with pytest.raises(adapter.ContractViolationError, match="missing"):
        adapter.resolve_wave8_inputs(root)


def _drop_source_column(doc: dict[str, Any]) -> None:
    _matrix_entry(doc)["source_columns"].pop()


def _forge_source_sha(doc: dict[str, Any]) -> None:
    _matrix_entry(doc)["source_sha256"] = "0" * 64


def _forge_row_count(doc: dict[str, Any]) -> None:
    _matrix_entry(doc)["rows"] = 6030


def _forge_projected_columns(doc: dict[str, Any]) -> None:
    _matrix_entry(doc)["projected_columns"] = ["consumer_id", "store", "owner"]


def _relabel_kind(doc: dict[str, Any]) -> None:
    doc["kind"] = "NEW_NATIVE_OBSERVATIONS"


def _drop_matrix_entry(doc: dict[str, Any]) -> None:
    doc["entries"] = [e for e in doc["entries"] if e["fixture"] != PROJECTION_FIXTURE]


@pytest.mark.parametrize(
    "mutate",
    [
        _drop_source_column,
        _forge_source_sha,
        _forge_row_count,
        _forge_projected_columns,
        _relabel_kind,
        _drop_matrix_entry,
    ],
)
def test_forged_projection_provenance_is_rejected(tmp_path: Path, mutate: Any) -> None:
    """The projected-identity check is separate from the sha pin and rejects forged metadata."""
    root = _clean_checkout_root(tmp_path)
    _rewrite_provenance(root, mutate)
    with pytest.raises(
        adapter.ContractViolationError,
        match="Projected-identity mismatch|source header|no 'consumer-matrix",
    ):
        adapter.resolve_wave8_inputs(root)


def test_projection_with_wrong_header_is_rejected(tmp_path: Path) -> None:
    """scan_projected_consumer_matrix refuses anything but the consumer_id,store header."""
    wide = tmp_path / "wide.csv"
    wide.write_text("consumer_id,store,owner\nsrc_x,qdrant,someone\n", encoding="utf-8")
    with pytest.raises(adapter.ContractViolationError, match="Projected consumer matrix header"):
        adapter.scan_projected_consumer_matrix(wide, ("consumer_id", "store", "owner"))


def test_fixtures_are_labelled_pinned_and_free_of_local_paths_and_emails() -> None:
    """PROVENANCE.json names every fixture, its source sha256 and the not-new-observation kind."""
    fixtures = THIS_DIR / "fixtures"
    assert sorted(p.name for p in fixtures.iterdir()) == sorted(ALL_FIXTURES)
    provenance = json.loads(
        (fixtures / adapter.FIXTURE_PROVENANCE_NAME).read_text(encoding="utf-8")
    )
    assert provenance["kind"] == adapter.FIXTURE_KIND
    assert provenance["base_commit"] == adapter.BASE_COMMIT_SHA
    assert sorted(e["fixture"] for e in provenance["entries"]) == sorted(DATA_FIXTURES)
    for entry in provenance["entries"]:
        name = entry["fixture"]
        assert entry["kind"] == adapter.FIXTURE_KIND
        assert entry["output_sha256"] == adapter.sha256_file(fixtures / name)
        if name in BYTE_IDENTICAL_FIXTURE_PINS:
            assert entry["transform"] == "byte-identical copy"
            assert entry["source_sha256"] == entry["output_sha256"]
            assert entry["output_sha256"] == BYTE_IDENTICAL_FIXTURE_PINS[name]
        else:
            assert name == PROJECTION_FIXTURE
            assert entry["transform"] == "projection"
            assert entry["source_sha256"] == adapter.PINNED_CONSUMER_MATRIX_SOURCE_SHA256
            assert entry["output_sha256"] == adapter.PINNED_CONSUMER_MATRIX_PROJECTION_SHA256
    for name in ALL_FIXTURES:
        text = (fixtures / name).read_text(encoding="utf-8")
        assert "/Users/" not in text
        assert _EMAIL_RE.search(text) is None


# --- B08-FG-01 / B08-FG-02: rejected input and output containment regressions ---
_REJECTION_MARKER = "B08_SYNTHETIC_REJECTED_7f136c"
_ORIGINAL_TEST_PREFIX_SHA256 = "4b8d2379c50a834e123b1850b2209f49736e61391f95b99a4aaaa01eaa865ca4"


def _boundary_check(ok: bool, code: str) -> None:
    """Do not print rejected payloads even when a regression fails."""
    if not ok:
        pytest.fail(code, pytrace=False)


def _reject_without_export(call: Any) -> tuple[BaseException, str]:
    import traceback

    try:
        call()
    except adapter.ContractViolationError as exc:
        rendered = "".join(traceback.format_exception(exc))
        _boundary_check(_REJECTION_MARKER not in rendered, "FG01_EXCEPTION_EXPORTED_INPUT")
        _boundary_check(exc.__cause__ is None, "FG01_EXCEPTION_CHAIN_EXPORTED")
        return exc, rendered
    else:
        pytest.fail("FG01_EXPECTED_REJECTION", pytrace=False)


@pytest.mark.parametrize("validator", ["field", "store", "family"])
def test_fg01_field_validators_redact_rejected_values(validator: str) -> None:
    calls = {
        "field": lambda: adapter.make_field(None, _REJECTION_MARKER, None),
        "store": lambda: adapter.validate_store_id(_REJECTION_MARKER, []),
        "family": lambda: adapter.extract_consumer_family([_REJECTION_MARKER]),
    }
    exc, rendered = _reject_without_export(calls[validator])
    assert _REJECTION_MARKER not in rendered, "FG01_EXCEPTION_EXPORTED_INPUT"
    assert exc.__cause__ is None, "FG01_EXCEPTION_CHAIN_EXPORTED"


@pytest.mark.parametrize("field", [
    "consumer_id", "operation_id", "store_id", "status", "evidence_sha256",
    "x_record_kind", "x_guarantee_dimension", "extra_key", "instance_status",
    "instance_keys", "instance_object", "instance_reference",
])
def test_fg01_operation_validation_redacts_values_and_keys(
    base_instances: list[dict[str, Any]], field: str,
) -> None:
    record = copy.deepcopy(base_instances[0])
    known = {record["consumer_id"]}
    if field == "extra_key":
        record[_REJECTION_MARKER] = _REJECTION_MARKER
    elif field == "instance_status":
        record["principal"]["status"] = _REJECTION_MARKER
    elif field == "instance_keys":
        record["principal"][_REJECTION_MARKER] = _REJECTION_MARKER
    elif field == "instance_object":
        record["principal"] = _REJECTION_MARKER
    elif field == "instance_reference":
        record["principal"]["evidence_ref"] = [_REJECTION_MARKER]
    else:
        record[field] = _REJECTION_MARKER
    exc, rendered = _reject_without_export(lambda: adapter.validate_operation_instance(record, known))
    assert _REJECTION_MARKER not in rendered, "FG01_EXCEPTION_EXPORTED_INPUT"
    assert exc.__cause__ is None, "FG01_EXCEPTION_CHAIN_EXPORTED"


@pytest.mark.parametrize("case", [
    "aggregate", "relation_type", "duplicate", "status", "reasons_type",
    "reason_key", "reason_value", "pass_reasons", "fail_reasons",
])
def test_fg01_nested_restore_validation_redacts_rejected_fields(case: str) -> None:
    receipt = _make_realistic_nested_receipt()
    summary = receipt["events"][-1]["verifier_summary"]
    relation = summary["invariants"][0]
    relation["relation"] = _REJECTION_MARKER
    if case == "aggregate":
        summary["aggregate"] = _REJECTION_MARKER
    elif case == "relation_type":
        relation["relation"] = [_REJECTION_MARKER]
    elif case == "duplicate":
        summary["invariants"].append(copy.deepcopy(relation))
    elif case == "status":
        relation["status"] = _REJECTION_MARKER
    elif case == "reasons_type":
        relation["reason_classes"] = _REJECTION_MARKER
    elif case == "reason_key":
        relation["reason_classes"] = {_REJECTION_MARKER: -1}
    elif case == "reason_value":
        relation["reason_classes"] = {"VIOLATION": _REJECTION_MARKER}
    elif case == "pass_reasons":
        relation["status"] = "PASS"
        relation["reason_classes"] = {_REJECTION_MARKER: 1}
    elif case == "fail_reasons":
        relation["reason_classes"] = {_REJECTION_MARKER: 0}
    exc, rendered = _reject_without_export(lambda: adapter.evaluate_ce01_restore_verdict_and_epistemology(receipt))
    assert _REJECTION_MARKER not in rendered, "FG01_EXCEPTION_EXPORTED_INPUT"
    assert exc.__cause__ is None, "FG01_EXCEPTION_CHAIN_EXPORTED"


@pytest.mark.parametrize("field", [
    "total_rows", "multi_store_or_boundary_rows", "by_store", "by_family",
])
@pytest.mark.parametrize("side", ["scanned", "receipt"])
def test_fg01_census_comparison_redacts_mapping_keys_and_values(field: str, side: str) -> None:
    scanned = {field: 1}
    receipt = {field: 1}
    (scanned if side == "scanned" else receipt)[field] = {
        _REJECTION_MARKER: _REJECTION_MARKER,
    }
    exc, rendered = _reject_without_export(lambda: adapter.compare_census_to_receipt(scanned, receipt))
    assert _REJECTION_MARKER not in rendered, "FG01_EXCEPTION_EXPORTED_INPUT"
    assert exc.__cause__ is None, "FG01_EXCEPTION_CHAIN_EXPORTED"


@pytest.mark.parametrize("case", ["census_missing", "census_pin", "census_json", "fixture_pin"])
def test_fg01_loaders_redact_paths_pins_and_json_chains(tmp_path: Path, case: str) -> None:
    path = tmp_path / _REJECTION_MARKER
    if case != "census_missing":
        path.write_text(_REJECTION_MARKER, encoding="utf-8")
    try:
        if case == "fixture_pin":
            call = lambda: adapter._require_fixture_sha(path, _REJECTION_MARKER, _REJECTION_MARKER)
        else:
            expected = None if case == "census_json" else _REJECTION_MARKER
            call = lambda: adapter.load_pinned_census_receipt(path, expected)
        exc, rendered = _reject_without_export(call)
        assert _REJECTION_MARKER not in rendered, "FG01_EXCEPTION_EXPORTED_INPUT"
        assert exc.__cause__ is None, "FG01_EXCEPTION_CHAIN_EXPORTED"
    finally:
        path.unlink(missing_ok=True)


def _run_boundary_cli(root: Path, destination: Path, extra: list[str] | None = None) -> Any:
    import subprocess

    result = subprocess.run(
        [sys.executable, "-I", "-B", str(THIS_DIR / "b08_crossstore_adapter.py"),
         "--repo-root", str(root), "--out", str(destination), *(extra or [])],
        capture_output=True, check=False, timeout=20,
    )
    combined = result.stdout + result.stderr
    _boundary_check(_REJECTION_MARKER.encode() not in combined, "FG01_CLI_EXPORTED_INPUT")
    _boundary_check(b"Traceback" not in combined, "FG01_CLI_EXPORTED_TRACEBACK")
    return result


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("case", [
    "matrix_store", "matrix_consumer", "matrix_header", "restore_json",
    "state_json", "state_value", "provenance", "fixture", "arguments", "missing_source",
])
def test_fg01_cli_rejects_untrusted_inputs_without_creating_or_replacing_output(
    tmp_path: Path, existing: bool, case: str,
) -> None:
    root = _clean_checkout_root(tmp_path)
    destination = root / B08_REL / "boundary-result.json"
    sentinel = b"existing-artifact-must-survive\n"
    if existing:
        destination.write_bytes(sentinel)
    extra = []
    try:
        if case.startswith("matrix_"):
            live = root / adapter.LIVE_INPUTS_REL
            live.mkdir(parents=True)
            rows = {
                "matrix_store": f"consumer_id,store\nsrc_x,pg;{_REJECTION_MARKER}\n",
                "matrix_consumer": f"consumer_id,store\n{_REJECTION_MARKER},pg;redis\n",
                "matrix_header": f"{_REJECTION_MARKER},store\nsrc_x,pg;redis\n",
            }
            (live / "consumer-matrix.csv").write_text(rows[case], encoding="utf-8")
        elif case in {"restore_json", "state_json"}:
            live = root / adapter.LIVE_INPUTS_REL
            live.mkdir(parents=True)
            name = "REAL-RUN-RECEIPT.json" if case == "restore_json" else "STATE.json"
            (live / name).write_text(_REJECTION_MARKER, encoding="utf-8")
        elif case == "state_value":
            live = root / adapter.LIVE_INPUTS_REL
            live.mkdir(parents=True)
            state = json.loads((root / adapter.FIXTURES_REL / "STATE.json").read_text())
            state["campaign_id"] = _REJECTION_MARKER
            (live / "STATE.json").write_text(json.dumps(state), encoding="utf-8")
        elif case == "provenance":
            _rewrite_provenance(root, lambda doc: _matrix_entry(doc).update(rows=_REJECTION_MARKER))
        elif case == "fixture":
            (root / adapter.FIXTURES_REL / "STATE.json").write_text(
                _REJECTION_MARKER, encoding="utf-8",
            )
        elif case == "arguments":
            extra = ["--" + _REJECTION_MARKER]
        elif case == "missing_source":
            root.rename(tmp_path / _REJECTION_MARKER)
            root = tmp_path / _REJECTION_MARKER
            destination = root / B08_REL / "boundary-result.json"
            (root / REPO_SOURCE_RELS[0]).unlink()
        result = _run_boundary_cli(root, destination, extra)
        assert result.returncode != 0, "FG01_CLI_ACCEPTED_INPUT"
        assert destination.read_bytes() == sentinel if existing else not destination.exists(), "FG01_CLI_MODIFIED_OUTPUT"
    finally:
        shutil.rmtree(root)


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("escape", ["sibling", "traversal", "directory_symlink", "file_symlink"])
def test_fg02_cli_rejects_escaping_paths_without_touching_targets(
    tmp_path: Path, existing: bool, escape: str,
) -> None:
    root = _clean_checkout_root(tmp_path)
    allowed = root / B08_REL
    outside = allowed.parent / ("B08-" + _REJECTION_MARKER)
    outside.mkdir()
    target = outside / "outside.json"
    sentinel = b"outside-artifact-must-survive\n"
    if existing:
        target.write_bytes(sentinel)
    if escape == "sibling":
        destination = target
    elif escape == "traversal":
        destination = allowed / ".." / outside.name / target.name
    elif escape == "directory_symlink":
        (allowed / "escape-link").symlink_to(outside, target_is_directory=True)
        destination = allowed / "escape-link" / target.name
    else:
        destination = allowed / "escape-link.json"
        destination.symlink_to(target)
    try:
        result = _run_boundary_cli(root, destination)
        assert result.returncode != 0, "FG02_CLI_ACCEPTED_ESCAPE"
        assert target.read_bytes() == sentinel if existing else not target.exists(), "FG02_CLI_MODIFIED_OUTSIDE_TARGET"
        assert sorted(p.name for p in outside.iterdir()) == ([target.name] if existing else []), "FG02_CLI_CREATED_OUTSIDE_ARTIFACT"
    finally:
        shutil.rmtree(root)


def test_fg02_actual_cli_keeps_pinned_ledger_bytes_for_valid_destination(tmp_path: Path) -> None:
    root = _clean_checkout_root(tmp_path)
    destination = root / B08_REL / "valid-result.json"
    result = _run_boundary_cli(root, destination)
    assert result.returncode == 0, "FG02_CLI_REJECTED_VALID_DESTINATION"
    produced = destination.read_bytes()
    assert len(produced) == ISOLATED_LEDGER_BYTES, "FG02_LEDGER_SIZE_CHANGED"
    assert hashlib.sha256(produced).hexdigest() == ISOLATED_LEDGER_SHA256, "FG02_LEDGER_HASH_CHANGED"


# Keep historical source snapshots separate from the five frozen input fixtures.
REPO_SOURCE_RELS += (
    f"{B08_REL}/source-compatibility/restore-drill-base-source.txt",
    f"{B08_REL}/source-compatibility/restore-drill-main-source.txt",
)

def _known_restore_revision(root: Path, fixture_name: str) -> None:
    shutil.copy2(root / B08_REL / "source-compatibility" / fixture_name,
                 root / "scripts/ci/restore_drill_verify.py")


def test_main_compatibility_keeps_historical_ledger_identity(tmp_path: Path) -> None:
    root = _clean_checkout_root(tmp_path)
    _known_restore_revision(root, "restore-drill-main-source.txt")
    live = root / "scripts/ci/restore_drill_verify.py"
    assert adapter.sha256_file(live) == adapter.PINNED_COMPATIBLE_MAIN_RESTORE_SHA256
    report = adapter.generate_b08_report(root)
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    assert hashlib.sha256(encoded).hexdigest() == ISOLATED_LEDGER_SHA256
    assert report["base_commit"] == adapter.BASE_COMMIT_SHA
    assert report["operation_instances"][8]["evidence_sha256"] == (
        adapter.PINNED_RESTORE_DRILL_VERIFY_SHA256
    )
    assert report["block_closed"] is False


def test_legacy_restore_revision_keeps_original_acceptance(tmp_path: Path) -> None:
    root = _clean_checkout_root(tmp_path)
    _known_restore_revision(root, "restore-drill-base-source.txt")
    assert adapter.sha256_file(root / "scripts/ci/restore_drill_verify.py") == (
        adapter.PINNED_RESTORE_DRILL_VERIFY_SHA256
    )
    assert adapter.generate_b08_report(root)["block_closed"] is False


def test_unknown_restore_revision_is_rejected_despite_valid_snapshot(tmp_path: Path) -> None:
    root = _clean_checkout_root(tmp_path)
    _known_restore_revision(root, "restore-drill-main-source.txt")
    live = root / "scripts/ci/restore_drill_verify.py"
    live.write_bytes(live.read_bytes() + b"\n# unreviewed source change\n")
    with pytest.raises(adapter.ContractViolationError, match="B08_E_RESTORE_SOURCE_PIN"):
        adapter.generate_b08_report(root)


@pytest.mark.parametrize("failure", ["missing", "tampered"])
def test_main_compatibility_requires_exact_historical_snapshot(
    tmp_path: Path, failure: str
) -> None:
    root = _clean_checkout_root(tmp_path)
    _known_restore_revision(root, "restore-drill-main-source.txt")
    historical = (root / B08_REL / "source-compatibility"
                  / "restore-drill-base-source.txt")
    if failure == "missing":
        historical.unlink()
    else:
        historical.write_bytes(historical.read_bytes() + b"\n# altered snapshot\n")
    with pytest.raises(adapter.ContractViolationError, match="B08_E_FIXTURE_"):
        adapter.generate_b08_report(root)


def test_main_compatibility_actual_cli_replays_frozen_ledger(tmp_path: Path) -> None:
    root = _clean_checkout_root(tmp_path)
    _known_restore_revision(root, "restore-drill-main-source.txt")
    destination = root / B08_REL / "historical-report.json"
    result = _run_boundary_cli(root, destination)
    assert result.returncode == 0, "B08_COMPATIBLE_MAIN_CLI_FAILED"
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == ISOLATED_LEDGER_SHA256
