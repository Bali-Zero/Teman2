from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from backend.services.autonomous_lab.runtime_contracts import (
    LabArtifactKind,
    LabArtifactManifest,
    LabStageName,
    LabStageStatus,
    build_lab_checkpoint,
    build_runtime_snapshot,
)
from backend.services.autonomous_lab.sandbox_policy import default_sandbox_policy
from backend.services.autonomous_lab.state_store import resolve_runtime_placement
from backend.services.autonomous_lab.worker import AutonomousLabWorker


def test_runtime_snapshot_uses_canonical_stage_and_gate_vocabulary() -> None:
    placement = resolve_runtime_placement("Nuzantara", "nuzantara")

    snapshot = build_runtime_snapshot(
        placement=placement,
        updated_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
        sync_state="test sync state",
    )
    receipt = snapshot.to_receipt()

    assert receipt["machine"] == "Pro"
    assert receipt["syncState"] == "test sync state"
    assert [stage["id"] for stage in receipt["stages"]] == [
        "watch",
        "intake",
        "plan",
        "worker",
        "arena",
        "tribunal",
        "curator",
        "archive",
    ]
    assert {stage["artifact"] for stage in receipt["stages"]} == {
        "FrontierSignal",
        "ResearchMaterial",
        "LabRun",
        "LabCheckpoint",
        "SandboxRunResult",
        "EvaluationReport",
        "CuratorDecision",
        "TrajectorySummary",
    }
    assert receipt["runtime_placement"]["can_claim_runs"] is True


def test_worker_dry_run_pauses_at_curator_without_side_effects() -> None:
    with (
        patch("subprocess.run") as subprocess_run,
        patch("subprocess.Popen") as subprocess_popen,
        patch("os.system") as os_system,
        patch("urllib.request.urlopen") as urlopen,
        patch("socket.create_connection") as create_connection,
    ):
        dry_run = AutonomousLabWorker(
            placement=resolve_runtime_placement("Nuzantara", "nuzantara")
        ).dry_run(
            run_id="dry-run-test",
            objective_reference="objective_fingerprint:test",
            created_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
        )

    subprocess_run.assert_not_called()
    subprocess_popen.assert_not_called()
    os_system.assert_not_called()
    urlopen.assert_not_called()
    create_connection.assert_not_called()

    receipt = dry_run.to_receipt()
    receipt_text = json.dumps(receipt, sort_keys=True)
    assert receipt["run_id"] == "dry-run-test"
    assert receipt["paused_at_stage"] == "curate"
    assert receipt["execution_allowed"] is False
    assert receipt["manual_promotion_required"] is True
    assert receipt["blocked"] is False
    assert "fly deploy" not in receipt_text
    assert "git push" not in receipt_text
    assert all(checkpoint["executed"] is False for checkpoint in receipt["checkpoints"])
    assert all(checkpoint["external_calls"] == 0 for checkpoint in receipt["checkpoints"])


def test_stage_lifecycle_status_is_distinct_from_dashboard_status() -> None:
    assert LabStageStatus("succeeded") is LabStageStatus.SUCCEEDED
    assert LabStageStatus("paused") is LabStageStatus.PAUSED
    with pytest.raises(ValueError):
        LabStageStatus("live")


def test_lab_checkpoint_sanitizes_payload_values() -> None:
    checkpoint = build_lab_checkpoint(
        run_id="checkpoint-runtime-test",
        stage=LabStageName.NORMALIZE,
        status=LabStageStatus.SUCCEEDED,
        payload={
            "summary": "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR",
            "operator": "client@example.com",
            "count": 2,
        },
        created_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )

    receipt = checkpoint.to_receipt()
    receipt_text = json.dumps(receipt, sort_keys=True)

    assert receipt["stage"] == "normalize"
    assert receipt["status"] == "succeeded"
    assert receipt["fingerprint"].startswith("sha256:")
    assert "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR" not in receipt_text
    assert "client@example.com" not in receipt_text
    assert "evidence_fingerprint:sha256:" in receipt_text


def test_artifact_manifest_never_persists_raw_refs() -> None:
    manifest = LabArtifactManifest(
        artifact_id="artifact-client@example.com",
        kind=LabArtifactKind.SANDBOX_RUN_RESULT,
        path_or_ref="/tmp/private/client@example.com/result.json",
        sha256="sha256:1234-5678",
        data_class="synthetic_fixture",
        retention_policy="ephemeral",
    )

    receipt = manifest.to_receipt()
    receipt_text = json.dumps(receipt, sort_keys=True)

    assert receipt["kind"] == "SandboxRunResult"
    assert "client@example.com" not in receipt_text
    assert receipt["artifact_id"].startswith("evidence_fingerprint:sha256:")
    assert receipt["path_or_ref"].startswith("evidence_fingerprint:sha256:")


def test_default_sandbox_policy_requires_isolation_before_execution() -> None:
    policy = default_sandbox_policy().to_receipt()

    assert policy["require_policy_before_execution"] is True
    assert policy["filesystem"]["repo_read_only"] is True
    assert ".worktrees/<lane>-<task>/" in policy["filesystem"]["writable_roots"]
    assert "~/.ssh/" in policy["filesystem"]["forbidden_roots"]
    assert policy["network"]["mode"] == "deny_all"
    assert policy["network"]["allowed_hosts"] == []
    assert policy["execution_limits"]["timeout_seconds"] == 600
    assert policy["production_writes_allowed"] is False
    assert policy["deploy_merge_push_allowed"] is False
    assert policy["raw_data_persistence_allowed"] is False
